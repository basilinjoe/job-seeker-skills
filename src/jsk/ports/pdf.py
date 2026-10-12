"""A rendered PDF, read: its text, its fonts, its pages and where its text sits.

pymupdf is optional. Each caller keeps its own policy for a missing reader (the fitter exits,
the renderer says "not measured", the layout gate prints SKIPPED), so every method but
`available` raises ImportError without it and the caller decides.
"""
from typing import Any, Protocol


class PdfInspector(Protocol):
    """Everything jsk reads out of a PDF, one method per question asked of it."""

    def available(self) -> bool:
        """Whether a PDF reader is installed."""
        ...

    def keywords(self, path: str) -> str:
        """The document's keywords metadata; "" when it has none."""
        ...

    def lines(self, path: str) -> tuple[list[Any], list[str]]:
        """([(page rect, [(text, bbox, fonts)])] per page, the sorted Type3 font names)."""
        ...

    def measure(self, path: str) -> list[dict[str, Any]]:
        """Per page: its height, and the top, bottom and first line of its text, in points."""
        ...

    def page_count(self, path: str) -> int:
        """How many pages the PDF has."""
        ...

    def thumbnail(self, path: str, png: str, dpi: int = 110) -> int:
        """Write the first page as a PNG at `png`.

        Returns:
            The page count. Writes `png`.
        """
        ...
