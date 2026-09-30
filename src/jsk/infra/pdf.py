"""Reading a rendered PDF, through pymupdf, imported only when a PDF is read."""


def read_pdf(path):
    """Read a PDF's text layer and the fonts it embeds.

    Args:
        path: the PDF.

    Returns:
        (text, sorted embedded font names); the pages' text joined by newlines.

    Raises:
        ImportError: pymupdf is not installed - it is optional, and each caller decides
            what a missing reader means for it.
    """
    import pymupdf                                 # noqa: PLC0415 - optional dependency

    pages, fonts = [], set()
    with pymupdf.open(path) as doc:
        for page in doc:
            pages.append(page.get_text())
            for font in page.get_fonts(full=False):
                fonts.add(font[3])
    return "\n".join(pages), sorted(fonts)
