from conftest import DORPSSTRAAT, KOLKBRUG

from eisen.pdf_text import load_document


def test_running_footer_is_removed_from_every_page():
    doc = load_document(DORPSSTRAAT)
    for page in doc.pages:
        assert "Terp & Vliet Ingenieurs B.V. | TV-24-1173-PvE" not in page
        assert "Pagina" not in page
    assert len(doc.removed) == 6  # two footer lines on each of three pages


def test_table_header_and_type_column_are_kept():
    # These recur on every page of doc 1, but at different heights.
    doc = load_document(KOLKBRUG)
    for page in doc.pages:
        assert "Eiscode" in page
    assert "Bindend" in doc.pages[0]
    assert "Wens" in doc.pages[2]


def test_page_crossing_text_joins_without_footer():
    doc = load_document(DORPSSTRAAT)
    assert doc.pages[0].endswith("sinusvormige hellingen")
    assert doc.pages[1].startswith("conform de CROW-richtlijn")


def test_running_header_with_page_number_is_removed(make_pdf):
    path = make_pdf(
        [
            [(20, "Bestek 12 - pagina 1"), (400, "eerste")],
            [(20, "Bestek 12 - pagina 2"), (400, "tweede")],
        ]
    )
    doc = load_document(path)
    assert doc.pages == ["eerste", "tweede"]
    assert doc.removed == ["Bestek 12 - pagina 1", "Bestek 12 - pagina 2"]


def test_header_is_found_wherever_the_template_puts_it(make_pdf):
    # No fixed margin: a header well below the usual band is still recognised.
    path = make_pdf([[(150, "Kop"), (400, "eerste")], [(150, "Kop"), (400, "tweede")]])
    assert load_document(path).pages == ["eerste", "tweede"]


def test_small_rounding_differences_are_tolerated(make_pdf):
    path = make_pdf([[(20, "Kop"), (400, "eerste")], [(21.5, "Kop"), (400, "tweede")]])
    assert load_document(path).pages == ["eerste", "tweede"]


def test_difference_beyond_tolerance_is_a_different_position(make_pdf):
    path = make_pdf([[(20, "Kop"), (400, "eerste")], [(25, "Kop"), (400, "tweede")]])
    assert load_document(path).pages == ["Kop\neerste", "Kop\ntweede"]


def test_same_text_at_a_different_height_is_kept(make_pdf):
    path = make_pdf([[(20, "Eiscode"), (400, "eerste")], [(60, "Eiscode"), (400, "tweede")]])
    assert load_document(path).pages == ["Eiscode\neerste", "Eiscode\ntweede"]


def test_repeated_line_inside_the_body_is_kept(make_pdf):
    # Same text at the same height, but with other text above and below it.
    path = make_pdf(
        [
            [(100, "boven een"), (400, "Bindend"), (700, "onder een")],
            [(100, "boven twee"), (400, "Bindend"), (700, "onder twee")],
        ]
    )
    assert load_document(path).pages == [
        "boven een\nBindend\nonder een",
        "boven twee\nBindend\nonder twee",
    ]


def test_varying_text_in_the_footer_row_is_kept(make_pdf):
    # A chapter title next to the page number changes per page; only the page number goes.
    path = make_pdf(
        [
            [(400, "eerste"), (820, "3 Wegontwerp", 72), (820, "Pagina 1", 450)],
            [(400, "tweede"), (820, "4 Riolering", 72), (820, "Pagina 2", 450)],
        ]
    )
    doc = load_document(path)
    assert doc.pages == ["eerste\n3 Wegontwerp", "tweede\n4 Riolering"]
    assert doc.removed == ["Pagina 1", "Pagina 2"]


def test_single_page_document_keeps_everything(make_pdf):
    path = make_pdf([[(20, "Pagina 1"), (400, "tekst")]])
    assert load_document(path).pages == ["Pagina 1\ntekst"]


def test_pages_without_text_are_reported(make_pdf):
    path = make_pdf([[(400, "tekst")], []])
    assert load_document(path).pages_without_text == [2]
