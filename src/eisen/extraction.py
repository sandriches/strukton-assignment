"""Ask the language model for requirement candidates, with a response cache.

The model only proposes: it finds requirements, quotes them and classifies
them. Whether a quote really appears in the document is checked later, in code.

Every response is saved as JSON, keyed by a hash of everything that influences
it (model, effort, prompt, output schema, document text). A rerun with the same
inputs reads the saved response instead of calling the model, so results are
reproducible and can be shown without a model connection.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from eisen.pdf_text import Document

DEFAULT_MODEL = "claude-sonnet-5-5"
EFFORT = "high"
MAX_TOKENS = 16000
PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "extract_v1.md"


# Field descriptions are part of the output schema the model sees, so they are Dutch.
class Candidate(BaseModel):
    code: str | None = Field(description="Eiscode zoals in het document, of null als die ontbreekt.")
    text: str = Field(description="Letterlijke eistekst, exact zoals in het document.")
    section: str = Field(description="Paragraaf- of hoofdstuknummer, bijvoorbeeld '3.2'.")
    type: Literal["Bindend", "Wens"]
    doubt: bool = Field(description="true bij twijfel over eis, type of afbakening.")
    reason: str = Field(description="Korte toelichting in het Nederlands.")


class Candidates(BaseModel):
    requirements: list[Candidate]


class ExtractionError(Exception):
    """A model response that can't be used; the message is shown to the user."""


@dataclass(frozen=True)
class Extraction:
    candidates: list[Candidate]
    meta: dict  # model, prompt, hashes, usage and timestamp of the run
    path: Path  # where the response is saved
    from_cache: bool


def extract(
    doc: Document,
    cache_dir: Path,
    *,
    model: str = DEFAULT_MODEL,
    prompt_path: Path = PROMPT,
    refresh: bool = False,
    client: anthropic.Anthropic | None = None,
) -> Extraction:
    system = prompt_path.read_text(encoding="utf-8")
    user = render_document(doc)
    key = _cache_key(model, system, user)
    path = cache_dir / f"{Path(doc.name).stem}.{key[:12]}.json"

    if path.exists() and not refresh:
        saved = json.loads(path.read_text(encoding="utf-8"))
        candidates = [Candidate.model_validate(c) for c in saved.pop("candidates")]
        return Extraction(candidates, saved, path, from_cache=True)

    client = client or anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=Candidates,
            output_config={"effort": EFFORT},
        )
    except TypeError as error:
        # The SDK has no error class for missing credentials; it raises a plain TypeError.
        if "authentication method" not in str(error):
            raise
        raise ExtractionError("geen API-sleutel gevonden. Zet ANTHROPIC_API_KEY in .env (zie README).") from error
    _check(response, doc.name)

    candidates = response.parsed_output.requirements
    meta = {
        "document": doc.name,
        "model_requested": model,
        "model_served": response.model,
        "effort": EFFORT,
        "prompt": prompt_path.name,
        "prompt_sha256": _sha256(system),
        "input_sha256": _sha256(user),
        "cache_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_id": getattr(response, "_request_id", None),
        "stop_reason": response.stop_reason,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    saved = {**meta, "candidates": [c.model_dump() for c in candidates]}
    path.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Extraction(candidates, meta, path, from_cache=False)


def render_document(doc: Document) -> str:
    """The document as the model sees it: its name, then each page under a marker."""
    pages = "\n\n".join(f"=== PAGINA {i} ===\n{text}" for i, text in enumerate(doc.pages, 1))
    return f"Document: {doc.name}\n\n{pages}"


def _check(response, name: str) -> None:
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) or "onbekend"
        raise ExtractionError(f"Het model weigerde '{name}' te verwerken (categorie: {category}).")
    if response.stop_reason == "max_tokens":
        raise ExtractionError(
            f"Het antwoord voor '{name}' is afgekapt na {MAX_TOKENS} tokens; het document is te lang."
        )
    if response.parsed_output is None:
        raise ExtractionError(f"Het model gaf voor '{name}' geen antwoord in het verwachte formaat.")


def _cache_key(model: str, system: str, user: str) -> str:
    schema = Candidates.model_json_schema()
    payload = json.dumps(
        {"model": model, "effort": EFFORT, "system": system, "schema": schema, "user": user},
        sort_keys=True,
        ensure_ascii=False,
    )
    return _sha256(payload)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
