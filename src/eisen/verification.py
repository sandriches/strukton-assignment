"""Turn the model's candidates into proposals that are checked against the source.

The model is trusted only to find and classify. Here, code decides everything
that must be exact:

- The requirement text is looked up in the document. If found, the proposal
  carries the source passage and its page range, not the model's quote. If not,
  it goes to the review sheet with the closest source passage next to it.
- A requirement code from the model is kept only if it appears on the matched
  pages; otherwise a traceable code is derived from document and section.
- Identical or nested proposals are moved to the review sheet, not dropped.
- A type that contradicts cue words in the text is flagged.

Signals and review reasons are shown to the user, so they are in Dutch.
"""

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from eisen.extraction import Candidate
from eisen.pdf_text import Document
from eisen.source_index import Match, SourceIndex, normalize

WISH_CUES = ("wenst", "wensen", "bij voorkeur", "streeft", "streven")
BINDING_CUES = ("dient", "dienen", "moet", "moeten", "uitsluitend", "verplicht")


@dataclass
class Proposal:
    document: str
    code: str
    code_source: str  # "bron" (from the document) or "afgeleid" (derived)
    text: str  # source passage if found, else the model's quote
    pages: str  # "1" or "1-2"; empty if the quote was not found
    section: str
    type: str
    model_reason: str
    doubt: bool
    found: bool
    closest: str | None = None  # closest source passage, when not found
    signals: list[str] = field(default_factory=list)
    review_reason: str | None = None  # set when the proposal belongs on the review sheet
    span: tuple[int, int] | None = None  # offsets into the document text

    @property
    def needs_review(self) -> bool:
        return self.review_reason is not None


def verify(doc: Document, candidates: list[Candidate]) -> list[Proposal]:
    index = SourceIndex(doc.pages)
    located = [_locate(doc.name, index, c) for c in candidates]
    _assign_codes(_document_prefix(doc.name), index, located, candidates)

    proposals = [proposal for proposal, _ in located]
    for proposal in proposals:
        if not proposal.found:
            proposal.review_reason = "Eistekst niet letterlijk in het document gevonden"
        elif proposal.doubt:
            proposal.review_reason = "Twijfelgeval volgens het model"
    _flag_overlaps([p for p in proposals if not p.needs_review])
    for proposal in proposals:
        _check_type(proposal)
    return proposals


def _locate(name: str, index: SourceIndex, candidate: Candidate) -> tuple[Proposal, Match | None]:
    matches = index.find_all(candidate.text)
    proposal = Proposal(
        document=name,
        code="",
        code_source="",
        text=candidate.text,
        pages="",
        section=candidate.section.strip(),
        type=candidate.type,
        model_reason=candidate.reason,
        doubt=candidate.doubt,
        found=bool(matches),
    )
    if not matches:
        proposal.closest = _closest_passage(index, candidate.text)
        return proposal, None

    match = matches[0]
    proposal.text, proposal.pages, proposal.span = match.text, match.pages, (match.start, match.end)
    if len(matches) > 1:
        proposal.signals.append(
            f"Tekst komt {len(matches)} keer voor in het document; eerste vindplaats gebruikt"
        )
    return proposal, match


def _assign_codes(
    prefix: str,
    index: SourceIndex,
    located: list[tuple[Proposal, Match | None]],
    candidates: list[Candidate],
) -> None:
    numbers: dict[str, int] = {}
    for (proposal, match), candidate in zip(located, candidates):
        model_code = (candidate.code or "").strip()
        if model_code and match and _code_on_pages(index, model_code, match):
            proposal.code, proposal.code_source = model_code, "bron"
            continue
        if model_code:
            proposal.signals.append(f"Eiscode '{model_code}' van het model staat niet bij deze eis")
        section = re.sub(r"\s+", "_", proposal.section) or "0"
        numbers[section] = numbers.get(section, 0) + 1
        proposal.code, proposal.code_source = f"{prefix}-{section}-{numbers[section]:02d}", "afgeleid"


def _code_on_pages(index: SourceIndex, code: str, match: Match) -> bool:
    return any(
        match.page_start <= m.page_start and m.page_end <= match.page_end
        for m in index.find_all(code)
    )


def _document_prefix(name: str) -> str:
    """'02_Programma_van_Eisen.pdf' -> 'D02'; otherwise the first word of the file name."""
    stem = Path(name).stem
    number = re.match(r"\d+", stem)
    if number:
        return f"D{number.group()}"
    return re.split(r"[\W_]+", stem)[0][:12] or "DOC"


def _flag_overlaps(proposals: list[Proposal]) -> None:
    """Move identical or nested proposals to the review sheet; flag partial overlaps."""
    for i, later in enumerate(proposals):
        for earlier in proposals[:i]:
            if earlier.needs_review or later.needs_review:
                continue
            (a_start, a_end), (b_start, b_end) = earlier.span, later.span
            if (a_start, a_end) == (b_start, b_end):
                later.review_reason = f"Dubbel voorstel: zelfde tekst als {earlier.code}"
            elif a_start <= b_start and b_end <= a_end:
                later.review_reason = f"Valt volledig binnen {earlier.code}"
            elif b_start <= a_start and a_end <= b_end:
                earlier.review_reason = f"Valt volledig binnen {later.code}"
            elif a_start < b_end and b_start < a_end:
                later.signals.append(f"Overlapt gedeeltelijk met {earlier.code}")
                earlier.signals.append(f"Overlapt gedeeltelijk met {later.code}")


def _check_type(proposal: Proposal) -> None:
    text = proposal.text.lower()
    wish = [cue for cue in WISH_CUES if re.search(rf"\b{cue}\b", text)]
    binding = [cue for cue in BINDING_CUES if re.search(rf"\b{cue}\b", text)]
    if proposal.type == "Bindend" and wish:
        proposal.signals.append(f"Type 'Bindend', maar de tekst bevat '{wish[0]}'; controleer het type")
    elif proposal.type == "Wens" and binding and not wish:
        proposal.signals.append(f"Type 'Wens', maar de tekst bevat '{binding[0]}'; controleer het type")


def _closest_passage(index: SourceIndex, quote: str) -> str | None:
    """The run of one to three source sentences that most resembles the quote."""
    sentences = re.split(r"(?<=[.!?;:])\s+", " ".join(index.text.split()))
    target = normalize(quote)
    best, best_score = None, 0.0
    for size in (1, 2, 3):
        for i in range(len(sentences) - size + 1):
            passage = " ".join(sentences[i : i + size])
            score = difflib.SequenceMatcher(None, normalize(passage), target, autojunk=False).ratio()
            if score > best_score:
                best, best_score = passage, score
    return best if best_score >= 0.5 else None
