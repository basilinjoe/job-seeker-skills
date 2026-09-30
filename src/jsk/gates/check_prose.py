#!/usr/bin/env python3
"""Check a generated resume against the rules in references/writing-rules.md

Usage: jsk check resume.pdf --only prose     (reads the .tex beside it)
       python -m jsk.gates.check_prose resume.tex
       python -m jsk.gates.check_prose resume.txt

Exit 0 = pass. Exit 1 = do not send this file. Exit 2 = usage error.
No third-party dependencies.

The sibling gate to check_ats.py. That one verifies a document *parses*; this one
verifies it *reads* - and reports how much of it is quantified, which nothing
else measures: the record gate checks that a number in a bullet traces to a metric,
never that any number is there at all. A bullet in the third person - "the platform followed him
through his promotion" - is not a parsing defect, so check_ats.py passes it with
0 failures and is right to. Nothing else was checking.
"""
import sys, os

from ..cliutil import docstring_usage, utf8_stdout, wants_help
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
    argv = sys.argv[1:] if argv is None else argv
    utf8_stdout()

    if wants_help(argv):
        # Before the path is read: `--help` used to be looked up as a file and
        # reported "file not found: --help" with the usage-error exit.
        print(docstring_usage(__doc__))
        return 0
    if not argv:
        print("usage: python -m jsk.gates.check_prose resume.tex | resume.txt")
        return 2
    path = argv[0]
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2

    def unreadable(reason):
        print(f"checking: {os.path.basename(path)}")
        print("\nFAIL 1   WARN 0")
        print(f"  FAIL  not a readable document: {reason}")
        print("\nDO NOT SEND - fix the failures above")
        return 1

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".tex":
            paragraphs = read_tex(path)
        elif ext in (".txt", ".md"):
            paragraphs = read_txt(path)
        else:
            print(f"unsupported file type {ext!r} - pass the .tex or the .txt variant")
            return 2
    except OSError as e:
        return unreadable(str(e))

    fails, warns, quantified = check(paragraphs)
    bullets = sum(1 for b, t in paragraphs if b and t.strip())

    counts = f"paragraphs: {len(paragraphs)}   bullets: {bullets}"
    if quantified is not None and bullets:
        counts += f"   quantified: {quantified}/{bullets} ({quantified * 100 // bullets}%)"
    print(f"checking: {os.path.basename(path)}")
    print(counts)
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    for f in fails:
        print("  FAIL  " + f)
    for w in warns:
        print("  warn  " + w)
    print("\nPASS - prose rules satisfied" if not fails
          else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
