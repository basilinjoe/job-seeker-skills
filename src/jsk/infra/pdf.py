"""Reading a rendered PDF, through pymupdf, imported only when a PDF is read.

pymupdf is optional: every function here raises ImportError without it, and each caller
keeps its own policy for that - the fitter exits, the renderer says "not measured", the
preview goes without its thumbnails.
"""


def available():
    """Whether pymupdf is installed.

    Returns:
        True when it imports. Imports it, which a test stops by setting
        sys.modules["pymupdf"] to None.
    """
    try:
        import pymupdf                             # noqa: F401,PLC0415 - optional dependency
    except ImportError:
        return False
    return True


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


def measure(pdf_path):
    """Where each page's text sits, the page fitter's and the renderer's measurement.

    Args:
        pdf_path: the PDF.

    Returns:
        [{height, top, bottom, first_text, first_height}], one per page, in points.

    Raises:
        ImportError: pymupdf is not installed.
    """
    import pymupdf                                    # noqa: PLC0415 - optional dependency

    pages = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            blocks = [b for b in page.get_text("blocks") if (b[4] or "").strip()]
            first = blocks[0] if blocks else None
            pages.append({
                "height": page.rect.height,
                "top": min((b[1] for b in blocks), default=0.0),
                "bottom": max((b[3] for b in blocks), default=0.0),
                "first_text": " ".join((first[4] or "").split())[:60] if first else "",
                "first_height": (float(first[3]) - float(first[1])) if first else 0.0,
            })
    return pages


def keywords(path):
    """The PDF's keywords metadata; "" when it has none.

    Raises:
        ImportError: pymupdf is not installed. Anything pymupdf raises on a damaged PDF
            propagates too.
    """
    import pymupdf                                 # noqa: PLC0415 - optional dependency

    with pymupdf.open(path) as doc:
        return (doc.metadata or {}).get("keywords") or ""


def lines(path):
    """Every line of text the PDF lays out, with where it sits and the fonts it is set in.

    Args:
        path: the PDF.

    Returns:
        ([(page rect, [(text, bbox, {font names})])], one per page; the sorted Type3 font
        names).

    Raises:
        ImportError: pymupdf is not installed.
    """
    import pymupdf                                 # noqa: PLC0415 - optional dependency

    pages, type3 = [], set()
    with pymupdf.open(path) as doc:
        for page in doc:
            found = []
            # pymupdf's stubs type every get_text() as str; the "dict" form is a dict.
            layout: dict = page.get_text("dict")  # pyright: ignore[reportAssignmentType]
            for block in layout["blocks"]:
                for line in block.get("lines", []):
                    spans = [s for s in line["spans"] if s["text"].strip()]
                    if spans:
                        found.append(("".join(s["text"] for s in line["spans"]).strip(),
                                      line["bbox"], {s["font"] for s in spans}))
            pages.append((page.rect, found))
            type3.update(f[3] for f in page.get_fonts() if f[2] == "Type3")
    return pages, sorted(type3)


def page_count(path):
    """How many pages the PDF has.

    Raises:
        ImportError: pymupdf is not installed. Anything pymupdf raises on a damaged PDF
            propagates too.
    """
    import pymupdf                                 # noqa: PLC0415 - optional dependency

    with pymupdf.open(path) as doc:
        return doc.page_count


def thumbnail(path, png, dpi=110):
    """Write the PDF's first page as a PNG.

    Args:
        path: the PDF.
        png: where the image goes.
        dpi: its resolution.

    Returns:
        The PDF's page count. Writes `png`.

    Raises:
        ImportError: pymupdf is not installed.
    """
    import pymupdf                                 # noqa: PLC0415 - optional dependency

    with pymupdf.open(path) as doc:
        doc[0].get_pixmap(dpi=dpi).save(png)
        return doc.page_count
