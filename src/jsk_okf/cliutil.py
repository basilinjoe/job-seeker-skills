"""Shared help-text handling for the hand-rolled entry points.

The argparse-backed write commands already do the right thing: `--help` prints
every flag and exits 0. The commands whose usage is hand-written did neither -
they printed one paragraph of the module docstring and returned 2 - so
`okf render --help` named none of the flags SKILL.md tells a reader to look up
there, and a caller checking exit codes saw "called wrong" for asking a question.

Both halves are fixed here so the surface answers the same way whichever kind of
command a caller happens to have reached.
"""
from __future__ import annotations

HELP_FLAGS = frozenset({"-h", "--help", "help"})

def wants_help(argv) -> bool:
    """Did the caller actually ask for help, rather than call the thing wrongly?"""
    return any(a in HELP_FLAGS for a in argv)


def docstring_usage(doc: str | None) -> str:
    """The operator-facing half of a module docstring: usage, flags, exit codes.

    Splitting on blank lines and taking `[1]` - what these entry points used to do -
    yields the two-line invocation and drops the flag list that follows it, which is
    the part anyone reading `--help` came for.

    These docstrings all run operator-facing first and design commentary second,
    with the exit-code paragraph as the seam. Cutting there keeps the flags and
    leaves out the essay about why the emitters are split - which belongs to
    whoever opens the file, not to whoever typed `--help`.
    """
    if not doc:
        return ""
    paragraphs = doc.strip().split("\n\n")
    if len(paragraphs) < 2:
        return doc.strip()

    kept = []
    for para in paragraphs[1:]:
        kept.append(para)
        if para.lstrip().startswith("Exit "):
            break
    return "\n\n".join(kept).rstrip()
