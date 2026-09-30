#!/usr/bin/env python3
"""`python -m jsk.gates.check_prose`: the prose gate's documented entry point.

The command is adapters/cli/gates/prose.py and the gate application/gates/prose.py; this
module keeps the path, the names callers and tests reach through it, and the readers of a
.tex and a .txt (Ruling 4 of the onion design).
"""
import sys

from ..domain.gates.prose_rules import AI_TELLS as AI_TELLS
from ..domain.gates.prose_rules import AMBIGUOUS_PERSON as AMBIGUOUS_PERSON
from ..domain.gates.prose_rules import BANNED as BANNED
from ..domain.gates.prose_rules import DANGLING_HARD as DANGLING_HARD
from ..domain.gates.prose_rules import DANGLING_SOFT as DANGLING_SOFT
from ..domain.gates.prose_rules import FORMULA as FORMULA
from ..domain.gates.prose_rules import FORMULA_MIN as FORMULA_MIN
from ..domain.gates.prose_rules import FORMULA_SHARE as FORMULA_SHARE
from ..domain.gates.prose_rules import ITEM as ITEM
from ..domain.gates.prose_rules import LONG_BULLET as LONG_BULLET
from ..domain.gates.prose_rules import NEAR_DUPLICATE as NEAR_DUPLICATE
from ..domain.gates.prose_rules import PREAMBLE_CMD as PREAMBLE_CMD
from ..domain.gates.prose_rules import TEX_COMMAND as TEX_COMMAND
from ..domain.gates.prose_rules import TEX_INVISIBLE as TEX_INVISIBLE
from ..domain.gates.prose_rules import TEX_UNESCAPE as TEX_UNESCAPE
from ..domain.gates.prose_rules import THIRD_PERSON as THIRD_PERSON
from ..domain.gates.prose_rules import VERBS as VERBS
from ..domain.gates.prose_rules import VERB_SUFFIXES as VERB_SUFFIXES
from ..domain.gates.prose_rules import WORD as WORD
from ..domain.gates.prose_rules import ai_tells as ai_tells
from ..domain.gates.prose_rules import check as check
from ..domain.gates.prose_rules import dangling_tail as dangling_tail
from ..domain.gates.prose_rules import numerals as numerals
from ..domain.gates.prose_rules import opens_on_a_verb as opens_on_a_verb
from ..domain.gates.prose_rules import overlap as overlap
from ..domain.gates.prose_rules import placeholders as placeholders
from ..domain.gates.prose_rules import strip_tex as strip_tex
from ..domain.gates.prose_rules import tex_paragraphs as tex_paragraphs
from ..domain.gates.prose_rules import txt_paragraphs as txt_paragraphs


def read_tex(path):
    """[(is_bullet, text)] one entry per paragraph, in document order.

    The .tex is read rather than the PDF it compiles to, for two reasons. A
    bullet is unambiguous here - it is `\\item`, not a glyph a text extractor may
    or may not have kept - and reading it needs no third-party library, which
    keeps this gate runnable on a machine that cannot render.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        return tex_paragraphs(fh)


def read_txt(path):
    """The plain-text variant, where mode-resume.md step 6 prefixes list items '- '."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return txt_paragraphs(f)


def main(argv=None):
    """The gate, as an exit code (adapters.cli.gates.prose.main).

    Args:
        argv: the arguments alone; by default sys.argv's.

    Returns:
        The exit code. Prints the verdict.
    """
    from ..adapters.cli.gates.prose import main as prose

    return prose(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
