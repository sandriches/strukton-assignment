import pytest
from conftest import DORPSSTRAAT, KOLKBRUG, reference_items

from eisen.pdf_text import load_document
from eisen.source_index import SourceIndex, normalize


@pytest.fixture(scope="module")
def indexes():
    return {pdf: SourceIndex(load_document(pdf).pages) for pdf in (KOLKBRUG, DORPSSTRAAT)}


def test_normalize_ignores_whitespace_and_unicode_form():
    assert normalize("a  b\nc") == normalize("abc")
    assert normalize("geïnfiltreerd") == normalize("geïnfiltreerd")  # composed vs decomposed
    assert normalize("ﬁetspad") == normalize("fietspad")  # ligature
    assert normalize("riool­inspectie") == normalize("rioolinspectie")  # soft hyphen


def test_normalize_keeps_content_differences():
    assert normalize("aangemeldt") != normalize("aangemeld")
    assert normalize("DWG- en") != normalize("DWGen")
    assert normalize("Wens") != normalize("wens")


@pytest.mark.parametrize(
    "pdf, code, text, pages", reference_items(), ids=lambda v: v if isinstance(v, str) else None
)
def test_every_reference_item_is_found_on_its_reference_pages(indexes, pdf, code, text, pages):
    matches = indexes[pdf].find_all(text)
    assert len(matches) == 1
    assert matches[0].pages == pages
    assert matches[0].text == " ".join(text.split())


def test_page_crossing_requirement_gets_full_range(indexes):
    match = indexes[DORPSSTRAAT].find_all("sinusvormige hellingen conform de CROW-richtlijn")[0]
    assert match.pages == "1-2"
    assert match.text == "sinusvormige hellingen conform de CROW-richtlijn"


def test_typo_is_matched_only_as_written(indexes):
    index = indexes[KOLKBRUG]
    assert index.find_all("zijn aangemeldt bij de")[0].pages == "2"
    assert index.find_all("zijn aangemeld bij de") == []


def test_rewritten_quote_is_not_found(indexes):
    assert indexes[DORPSSTRAAT].find_all("revisietekeningen in DWG en PDF") == []


def test_repeated_phrase_returns_every_occurrence(indexes):
    assert len(indexes[KOLKBRUG].find_all("De Opdrachtnemer dient")) == 4


def test_empty_quote_finds_nothing(indexes):
    assert indexes[KOLKBRUG].find_all(" \n") == []
