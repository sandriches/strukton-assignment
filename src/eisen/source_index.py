"""Locate quotes in a document's text, ignoring whitespace and Unicode form.

Used for finding the source of a quote in a PDF document so that it can be cited. 
The quote must match the source text exactly (except for whitespace and Unicode
normalization).

The comparison follows the scoring rules of the assignment: whitespace, line
breaks and technical Unicode normalisation are ignored. Everything else (case,
punctuation, spelling mistakes) must match exactly.
"""

import bisect
import unicodedata
from dataclasses import dataclass


def normalize(text: str) -> str:
    return "".join(_normalize_char(c) for c in text)


def _normalize_char(c: str) -> str:
    # Whitespace and invisible format characters (soft hyphen, zero-width space)
    # carry no content. NFKD per character is safe because decomposition never
    # spans characters, unlike composition.
    if c.isspace() or unicodedata.category(c) == "Cf":
        return ""
    return unicodedata.normalize("NFKD", c)


@dataclass(frozen=True)
class Match:
    start: int  # offsets into SourceIndex.text
    end: int
    page_start: int
    page_end: int
    text: str  # the source passage, whitespace runs collapsed to single spaces

    @property
    def pages(self) -> str:
        if self.page_start == self.page_end:
            return str(self.page_start)
        return f"{self.page_start}-{self.page_end}"


class SourceIndex:
    def __init__(self, pages: list[str]):
        self.text = "\n".join(pages)
        self._page_starts = []
        offset = 0
        for page in pages:
            self._page_starts.append(offset)
            offset += len(page) + 1

        # _normalized[i] came from self.text[_origin[i]].
        chars, origin = [], []
        for offset, c in enumerate(self.text):
            for n in _normalize_char(c):
                chars.append(n)
                origin.append(offset)
        self._normalized = "".join(chars)
        self._origin = origin

    def find_all(self, quote: str) -> list[Match]:
        needle = normalize(quote)
        if not needle:
            return []
        matches = []
        i = self._normalized.find(needle)
        while i != -1:
            start = self._origin[i]
            end = self._origin[i + len(needle) - 1] + 1
            matches.append(
                Match(
                    start=start,
                    end=end,
                    page_start=self.page_of(start),
                    page_end=self.page_of(end - 1),
                    text=" ".join(self.text[start:end].split()),
                )
            )
            i = self._normalized.find(needle, i + 1)
        return matches

    def page_of(self, offset: int) -> int:
        return bisect.bisect_right(self._page_starts, offset)
