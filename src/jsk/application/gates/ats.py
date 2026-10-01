"""The parse gate over one document: its text extracted, then judged by the ATS rules.

The rules are domain/gates/ats_rules.py's. This decides how the document is read - a PDF
through the PDF reader, a .txt as text - and what a document that will not open is. It
prints nothing: adapters/cli/gates/ats.py says what it found.
"""
import os
from dataclasses import dataclass

from ...domain.gates.ats_rules import judge
from .result import GateResult, GateStopped, unreadable


@dataclass(frozen=True)
class AtsResult(GateResult):
    """The parse gate's verdict, with what its heading reports."""

    name: str
    strict: bool
    lines: int          # lines of extracted text
    fonts: tuple        # the embedded font names; empty for a .txt


def check_ats(path, *, strict, read_pdf, read_txt):
    """Judge the document at `path` as an ATS would read it.

    Args:
        path: a .pdf or a .txt; it exists.
        strict: also enforce the ATS-maximal rules (ASCII only, employer per role).
        read_pdf: path -> (text, fonts); raises ImportError without a PDF reader.
        read_txt: path -> (text, fonts); raises OSError when the file will not read.

    Returns:
        An AtsResult, or an Unreadable when the document would not open.

    Raises:
        GateStopped: "no-pdf-library" (exit 2) when a PDF cannot be read on this machine,
            "format" (exit 1, `detail` the extension) for any other kind of file.
    """
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            txt, fonts = read_pdf(path)
        except ImportError:
            raise GateStopped("no-pdf-library", name, 2) from None
        except Exception as e:  # noqa: BLE001 - any pymupdf failure is the verdict "unreadable"
            return unreadable(name, f"unreadable: {type(e).__name__}: {e}")
    elif ext == ".txt":
        try:
            txt, fonts = read_txt(path)
        except OSError as e:
            return unreadable(name, f"unreadable: {e}")
    else:
        raise GateStopped("format", ext, 1)

    lines, report = judge(txt, fonts, pdf=ext == ".pdf", strict=strict)
    return AtsResult(fails=tuple(report.fails), warns=tuple(report.warns), name=name,
                     strict=strict, lines=len(lines), fonts=tuple(fonts))
