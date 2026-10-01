"""The documents the gates judge, read from disk: a rendered .txt or .tex, and a cover letter.

Deliberately lenient where infra.files.read_text is strict: a gate reads a rendered document
to judge it, and a stray byte in what was rendered is a finding in its own right, not a
reason to stop. So each is read as UTF-8 with errors replaced.
"""


def read_txt(path):
    """The parse gate's read of a rendered .txt: its text, and no fonts.

    Args:
        path: the .txt.

    Returns:
        (text, []). Reads the file.

    Raises:
        OSError: the file will not open.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read(), []


def read_tex(path):
    """[(is_bullet, text)] one entry per paragraph of a .tex, in document order.

    The .tex is read rather than the PDF it compiles to, for two reasons. A bullet is
    unambiguous here - it is `\\item`, not a glyph a text extractor may or may not have
    kept - and reading it needs no third-party library, which keeps the prose gate
    runnable on a machine that cannot render.

    Args:
        path: the .tex.

    Returns:
        domain.gates.prose_rules.tex_paragraphs over the file. Reads it.

    Raises:
        OSError: the file will not open.
    """
    from ..domain.gates.prose_rules import tex_paragraphs

    with open(path, encoding="utf-8", errors="replace") as fh:
        return tex_paragraphs(fh)


def read_txt_paragraphs(path):
    """[(is_bullet, text)] one entry per paragraph of the plain-text variant, where
    mode-resume.md step 6 prefixes list items '- '.

    Args:
        path: the .txt or .md.

    Returns:
        domain.gates.prose_rules.txt_paragraphs over the file. Reads it.

    Raises:
        OSError: the file will not open.
    """
    from ..domain.gates.prose_rules import txt_paragraphs

    with open(path, encoding="utf-8", errors="replace") as f:
        return txt_paragraphs(f)


def read_letter(path):
    """A cover letter's text; .md is read as written - its markup is not words. Lenient on
    a stray byte, as the gates are, but a BOM is stripped: kept, it hid the salutation.

    Args:
        path: the letter, or the posting.md beside its resume.json.

    Returns:
        The text, normalised (domain.record.parsed.normalise). Reads the file.

    Raises:
        OSError: the file will not open.
    """
    from ..domain.record.parsed import normalise

    with open(path, encoding="utf-8", errors="replace") as fh:
        return normalise(fh.read())
