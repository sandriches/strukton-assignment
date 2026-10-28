from pathlib import Path

import pytest

from eisen.cli import run_evaluate
from eisen.evaluation import (
    DUPLICATE, FOUND, OTHER, REFERENCE_ITEM, SPLIT, WRONG, Reference, Row, document_number, load_output,
    load_reference, score,
)
from eisen.excel import MAIN_SHEET, REVIEW_SHEET, DocumentResult, write_workbook
from eisen.extraction import Extraction
from eisen.pdf_text import Document
from eisen.verification import Proposal

from conftest import REFERENCE

ROOT = Path(__file__).parent.parent
DOC = "01_test.pdf"
A = Reference(code="VS-1", text="De Opdrachtnemer dient de brug te schilderen.", type="Bindend", pages="1")
B = Reference(code="VS-2", text="Het hekwerk dient blauw te zijn. Het hekwerk is 1,2 m hoog.", type="Wens", pages="1-2")


def row(text, pages="1", number=2, sheet=MAIN_SHEET, type="Bindend", code=""):
    return Row(sheet=sheet, number=number, document=DOC, code=code, text=text, pages=pages, type=type)


def statuses(result):
    return [o.status for o in result.proposals]


def test_exact_match_ignores_whitespace_and_unicode_form():
    result = score(DOC, [A], [row("De Opdrachtnemer dient\nde  brug te schilderen.")])
    assert statuses(result) == [FOUND]
    assert (result.found, result.rate, result.missed) == (1, 100.0, [])


def test_text_must_match_letter_for_letter():
    result = score(DOC, [A], [row("De opdrachtnemer dient de brug te schilderen.")])
    assert statuses(result) == [WRONG]
    assert result.found == 0
    assert result.missed[0][0] == A


def test_wrong_page_is_not_found_and_says_why():
    result = score(DOC, [B], [row(B.text, pages="1")])
    [outcome] = result.proposals
    assert outcome.status == WRONG
    assert outcome.reason == "Tekst klopt met VS-2, maar pagina 1 in plaats van 1-2"


def test_second_match_of_the_same_item_is_a_duplicate():
    result = score(DOC, [A], [row(A.text, number=2), row(A.text, number=3)])
    assert statuses(result) == [FOUND, DUPLICATE]
    assert result.proposals[1].reason == "Zelfde eis als VS-1, al gevonden in rij 2"


def test_split_counts_as_found_and_is_reported():
    parts = [row("Het hekwerk is 1,2 m hoog.", pages="2", number=3), row("Het hekwerk dient blauw te zijn.", number=2)]
    result = score(DOC, [B], parts)
    assert statuses(result) == [SPLIT, SPLIT]
    assert result.found == 1
    assert result.splits == {B: [parts[1], parts[0]]}  # in text order


@pytest.mark.parametrize(
    "parts",
    [
        ["Het hekwerk dient blauw te zijn."],  # gap: second sentence missing
        ["Het hekwerk dient blauw te zijn.", "Het hekwerk is 1,2 m hoog. Extra."],  # adds text
        ["Het hekwerk dient blauw", "dient blauw te zijn.", "Het hekwerk is 1,2 m hoog."],  # overlap
    ],
)
def test_incomplete_or_extended_splits_are_wrong(parts):
    rows = [row(text, pages="1-2", number=i) for i, text in enumerate(parts, 2)]
    result = score(DOC, [B], rows)
    assert result.found == 0
    assert set(statuses(result)) == {WRONG}


def test_split_must_have_the_same_page_range():
    parts = [row("Het hekwerk dient blauw te zijn.", number=2), row("Het hekwerk is 1,2 m hoog.", number=3)]
    result = score(DOC, [B], parts)  # both on page 1, reference is 1-2
    assert result.found == 0
    assert result.proposals[0].reason == "Onvolledig: deel van VS-2"


def test_proposal_not_in_the_reference_list_is_wrong():
    result = score(DOC, [A], [row(A.text), row("De brug is groen.", number=3)])
    assert statuses(result) == [FOUND, WRONG]
    assert result.proposals[1].reason == "Geen eis volgens de referentielijst"


def test_review_sheet_is_scored_separately():
    rows = [row(A.text, sheet=REVIEW_SHEET, number=2), row("De brug is groen.", sheet=REVIEW_SHEET, number=3)]
    result = score(DOC, [A], rows)
    assert result.proposals == []
    assert result.found == 0  # a reference item on the review sheet is not found
    assert [o.status for o in result.review] == [REFERENCE_ITEM, OTHER]
    assert result.review[0].reason == "VS-1 (ontbreekt op Voorstellen)"
    assert result.review_references == 1


def test_missed_item_points_to_the_closest_proposal():
    near = row("De Opdrachtnemer dient de brug te schilderen.", pages="2")
    result = score(DOC, [A], [near, row("Iets heel anders.", number=3)])
    assert result.missed == [(A, near)]


def test_type_is_reported_but_does_not_count():
    result = score(DOC, [A], [row(A.text, type="Wens")])
    assert result.found == 1
    assert [o.reference for o in result.type_mismatches] == [A]


def test_other_documents_are_ignored():
    other = Row(MAIN_SHEET, 2, "02_ander.pdf", "", A.text, "1", "Bindend")
    assert score(DOC, [A], [other]).found == 0


def test_document_number_links_pdf_to_reference_sheet():
    assert document_number("01_Vraagspecificatie.pdf") == 1
    assert document_number("Vraagspecificatie.pdf") is None


def test_reference_list_is_read_per_document():
    references = load_reference(REFERENCE)
    assert sorted(references) == [1, 2]
    assert (len(references[1]), len(references[2])) == (14, 13)
    page_crossing = next(r for r in references[2] if r.code == "PvE-3.2-01")
    assert page_crossing.pages == "1-2"


def test_workbook_round_trip(tmp_path):
    def proposal(text, **overrides):
        values = dict(
            document=DOC, code="VS-1", code_source="bron", text=text, pages="1", section="1",
            type="Bindend", model_reason="", doubt=False, found=True,
        )
        return Proposal(**{**values, **overrides})

    extraction = Extraction(candidates=[], meta={}, path=Path("x.json"), from_cache=True)
    proposals = [proposal(A.text), proposal("Twijfel.", doubt=True, review_reason="Twijfelgeval volgens het model")]
    path = tmp_path / "eisen.xlsx"
    write_workbook(path, [DocumentResult(Document(DOC, ["tekst"], []), extraction, proposals)])

    documents, rows = load_output(path)
    assert documents == [DOC]
    assert [(r.sheet, r.number, r.text) for r in rows] == [(MAIN_SHEET, 2, A.text), (REVIEW_SHEET, 2, "Twijfel.")]


def test_committed_output_scores(tmp_path, capsys):
    report = tmp_path / "evaluatie.md"
    assert run_evaluate(ROOT / "output" / "eisen_voorstellen.xlsx", REFERENCE, report) == 0
    out = capsys.readouterr().out
    assert "14/14 gevonden (100,0%), 0 onterecht, 0 dubbel, 0 gesplitst" in out
    assert "13/13 gevonden (100,0%), 0 onterecht, 0 dubbel, 1 gesplitst" in out
    assert "**PvE-2-02** (pagina 1)" in report.read_text()


def test_missing_workbook_gives_a_clear_message(tmp_path, capsys):
    assert run_evaluate(tmp_path / "nee.xlsx", REFERENCE, tmp_path / "r.md") == 1
    assert "draai eerst 'eisen extract'" in capsys.readouterr().err
