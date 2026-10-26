from pathlib import Path

import openpyxl
import pymupdf
import pytest

DATA = Path(__file__).parent.parent / "data"
KOLKBRUG = DATA / "01_Vraagspecificatie_Kolkbrug_Provincie_Noorderveld.pdf"
DORPSSTRAAT = DATA / "02_Programma_van_Eisen_Dorpsstraat_Gemeente_Rijnhoven.pdf"
REFERENCE = DATA / "Referentielijst_oefendocumenten.xlsx"


def reference_items() -> list[tuple[Path, str, str, str]]:
    """(pdf, code, text, pages) for every row in the reference list."""
    sheets = {"Doc 1 Kolkbrug": KOLKBRUG, "Doc 2 Dorpsstraat": DORPSSTRAAT}
    workbook = openpyxl.load_workbook(REFERENCE, read_only=True)
    items = []
    for sheet, pdf in sheets.items():
        for row in workbook[sheet].iter_rows(min_row=4, values_only=True):
            if row[0] is None:
                continue
            _, code, text, _, pages, _ = row
            items.append((pdf, code, text, str(pages)))
    return items


@pytest.fixture
def make_pdf(tmp_path):
    """Build a PDF from (y, text) or (y, text, x) lines per page, in points; A4 is 842pt high."""

    def build(pages: list[list[tuple]]) -> Path:
        pdf = pymupdf.open()
        for lines in pages:
            page = pdf.new_page(width=595, height=842)
            for y, text, *x in lines:
                page.insert_text((x[0] if x else 72, y), text)
        path = tmp_path / "test.pdf"
        pdf.save(path)
        return path

    return build
