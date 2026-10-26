import json
from types import SimpleNamespace

import pytest

from eisen.cli import run_extract
from eisen.extraction import PROMPT, Candidate, Candidates, ExtractionError, extract, render_document
from eisen.pdf_text import Document

DOC = Document(name="test.pdf", pages=["Eerste pagina.", "Tweede pagina."], removed=[])
CANDIDATE = Candidate(
    code=None, text="Eerste pagina.", section="1", type="Bindend", doubt=False, reason="Test."
)


class FakeClient:
    """Stands in for anthropic.Anthropic: records requests, returns a canned response."""

    def __init__(self, stop_reason="end_turn", parsed=Candidates(requirements=[CANDIDATE])):
        self.requests = []
        self.messages = self
        self._response = SimpleNamespace(
            parsed_output=parsed,
            stop_reason=stop_reason,
            stop_details=SimpleNamespace(category="cyber"),
            model="claude-sonnet-5-5",
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
            _request_id="req_test",
        )

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        return self._response


class NoCallClient:
    messages = property(lambda self: pytest.fail("the model should not be called"))


def test_document_is_rendered_with_page_markers():
    assert render_document(DOC) == (
        "Document: test.pdf\n\n=== PAGINA 1 ===\nEerste pagina.\n\n=== PAGINA 2 ===\nTweede pagina."
    )


def test_request_uses_prompt_schema_and_effort(tmp_path):
    client = FakeClient()
    extract(DOC, tmp_path, client=client)
    request = client.requests[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["system"] == PROMPT.read_text(encoding="utf-8")
    assert request["output_format"] is Candidates
    assert request["output_config"] == {"effort": "high"}
    assert request["messages"] == [{"role": "user", "content": render_document(DOC)}]
    assert "temperature" not in request  # rejected by the API since 2026-10-21


def test_response_is_saved_with_metadata(tmp_path):
    result = extract(DOC, tmp_path, client=FakeClient())
    saved = json.loads(result.path.read_text(encoding="utf-8"))
    assert not result.from_cache
    assert result.candidates == [CANDIDATE]
    assert saved["candidates"] == [CANDIDATE.model_dump()]
    assert saved["model_served"] == "claude-sonnet-5-5"
    assert saved["prompt"] == "extract_v1.md"
    assert saved["output_tokens"] == 20


def test_second_run_reads_the_saved_response(tmp_path):
    first = extract(DOC, tmp_path, client=FakeClient())
    second = extract(DOC, tmp_path, client=NoCallClient())
    assert second.from_cache
    assert second.path == first.path
    assert second.candidates == first.candidates


def test_refresh_calls_the_model_again(tmp_path):
    extract(DOC, tmp_path, client=FakeClient())
    client = FakeClient()
    assert not extract(DOC, tmp_path, client=client, refresh=True).from_cache
    assert len(client.requests) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"model": "claude-opus-5-5"},
        {"doc": Document(name="test.pdf", pages=["Andere tekst."], removed=[])},
        {"prompt": "Een andere prompt."},
    ],
)
def test_any_input_change_invalidates_the_cache(tmp_path, change):
    first = extract(DOC, tmp_path, client=FakeClient())

    prompt_path = PROMPT
    if "prompt" in change:
        prompt_path = tmp_path / "extract_v2.md"
        prompt_path.write_text(change["prompt"], encoding="utf-8")
    client = FakeClient()
    second = extract(
        change.get("doc", DOC),
        tmp_path,
        model=change.get("model", "claude-sonnet-5-5"),
        prompt_path=prompt_path,
        client=client,
    )
    assert not second.from_cache
    assert second.path != first.path
    assert len(client.requests) == 1


@pytest.mark.parametrize(
    "client, message",
    [
        (FakeClient(stop_reason="refusal"), "weigerde"),
        (FakeClient(stop_reason="max_tokens"), "afgekapt"),
        (FakeClient(parsed=None), "verwachte formaat"),
    ],
)
def test_unusable_responses_raise_and_are_not_saved(tmp_path, client, message):
    with pytest.raises(ExtractionError, match=message):
        extract(DOC, tmp_path, client=client)
    assert list(tmp_path.iterdir()) == []


def test_missing_api_key_gives_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(ExtractionError, match="geen API-sleutel"):
        extract(DOC, tmp_path)


def test_scanned_pdf_is_skipped_with_a_message(make_pdf, capsys):
    path = make_pdf([[]])
    assert run_extract([path]) == 1
    assert "geen tekstlaag" in capsys.readouterr().err
