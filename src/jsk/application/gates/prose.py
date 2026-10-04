"""The prose gate over one document: its paragraphs read, then judged by the writing rules.

The rules are domain/gates/prose_rules.py's. This decides which reader a document gets -
the .tex its PDF was compiled from, or the plain-text variant - and what a document that
will not read is. It prints nothing: adapters/entry/gates/prose.py says what it found.
"""
import os
from dataclasses import dataclass

from ...domain.gates.prose_rules import check
from .result import GateResult, GateStopped, unreadable


@dataclass(frozen=True)
class ProseResult(GateResult):
    """The prose gate's verdict, with the counts its heading reports."""

    name: str
    paragraphs: int
    bullets: int
    quantified: int | None      # bullets stating a number; None when not counted


def check_prose(path, *, read_tex, read_txt):
    """Judge the writing of the document at `path`.

    Args:
        path: a .tex, .txt or .md; it exists.
        read_tex: path -> [(is_bullet, text)], one per paragraph of a .tex.
        read_txt: the same for the plain-text variant.

    Returns:
        A ProseResult, or an Unreadable when the file raised OSError on reading.

    Raises:
        GateStopped: "format" (exit 2, `detail` the extension) for any other kind of file.
    """
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".tex":
            paragraphs = read_tex(path)
        elif ext in (".txt", ".md"):
            paragraphs = read_txt(path)
        else:
            raise GateStopped("format", ext, 2)
    except OSError as e:
        return unreadable(name, f"not a readable document: {e}")

    fails, warns, quantified = check(paragraphs)
    bullets = sum(1 for b, t in paragraphs if b and t.strip())
    return ProseResult(fails=tuple(fails), warns=tuple(warns), name=name,
                       paragraphs=len(paragraphs), bullets=bullets, quantified=quantified)
