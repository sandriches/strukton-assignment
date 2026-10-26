"""Read a PDF's text layer per page, without running headers and footers.

A running header or footer is printed by the page template at the same spot on
every page. A line is treated as one when its text (digits masked, so
"Pagina 1" matches "Pagina 2") recurs at the same vertical position on another
page, and it belongs to the outermost rows of text at the top or bottom of the
page. Body text that repeats, such as a table header row or a "Bindend" cell,
either lands at a different height or has other text above and below it.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf

# Allowed difference in vertical position, in points, for rounding in the PDF.
TOLERANCE = 2.0


@dataclass(frozen=True)
class Document:
    name: str
    pages: list[str]  # body text per page; pages[0] is page 1
    removed: list[str]  # header/footer lines that were dropped, for transparency

    @property
    def pages_without_text(self) -> list[int]:
        """Page numbers with no text layer (scanned or empty pages)."""
        return [i + 1 for i, text in enumerate(self.pages) if not text.strip()]


@dataclass(frozen=True)
class _Line:
    text: str
    key: str  # text with digits masked
    y0: float
    y1: float


def load_document(path: Path) -> Document:
    with pymupdf.open(path) as pdf:
        pages = [_read_lines(page) for page in pdf]

    positions = defaultdict(list)  # key -> [(page number, line)]
    for number, lines in enumerate(pages):
        for line in lines:
            positions[line.key].append((number, line))

    body, removed = [], []
    for number, lines in enumerate(pages):
        def recurs(line: _Line) -> bool:
            return any(
                other_number != number
                and abs(other.y0 - line.y0) <= TOLERANCE
                and abs(other.y1 - line.y1) <= TOLERANCE
                for other_number, other in positions[line.key]
            )

        running = _outermost_matching(lines, recurs)
        body.append("\n".join(line.text for i, line in enumerate(lines) if i not in running))
        removed.extend(line.text for i, line in enumerate(lines) if i in running)
    return Document(name=Path(path).name, pages=body, removed=removed)


def _read_lines(page: pymupdf.Page) -> list[_Line]:
    """Lines in PyMuPDF's reading order, which keeps table cells together."""
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip():
                continue
            _, y0, _, y1 = line["bbox"]
            key = re.sub(r"\d+", "#", " ".join(text.split()))
            lines.append(_Line(text, key, y0, y1))
    return lines


def _outermost_matching(lines: list[_Line], matches) -> set[int]:
    """Indices of matching lines in the rows at the top and bottom of the page.

    Walks inwards from each edge, row by row, and stops at the first row
    without a match, so only the outer rows can ever be removed.
    """
    rows = _rows(lines)
    found = set()
    for ordered in (rows, rows[::-1]):
        for row in ordered:
            hits = {i for i in row if matches(lines[i])}
            if not hits:
                break
            found |= hits
    return found


def _rows(lines: list[_Line]) -> list[list[int]]:
    """Line indices grouped into rows (same height), top to bottom."""
    rows: list[list[int]] = []
    for i in sorted(range(len(lines)), key=lambda i: lines[i].y0):
        if rows and abs(lines[i].y0 - lines[rows[-1][0]].y0) <= TOLERANCE:
            rows[-1].append(i)
        else:
            rows.append([i])
    return rows
