#!/usr/bin/env python3
"""Check a generated resume against the rules in references/ats-rules.md

Usage: jsk check resume.pdf --only parse [--strict]
       python -m jsk.gates.check_ats resume.pdf [--strict]
       python -m jsk.gates.check_ats resume.txt [--strict]
       --strict  also enforce ATS-maximal rules (ASCII only, employer per role)

Exit 0 = pass. Exit 1 = do not send this file. Exit 2 = usage error.
Reading a PDF needs pymupdf; the .txt path is standard library only.

This used to read a .docx and check seven structural hazards inside its XML - a
table, a text box, an image, a drawing, SmartArt, header content, a second
column. Those checks are gone because the thing they guarded against is gone:
the document is produced by one LaTeX template with no way to emit any of them.
A hazard the generator cannot express does not need re-checking on every render;
it needs a test on the generator, which is what the golden-file test over
emit_latex.py is for.

What remains is everything that was never structural in the first place - what
the extracted text says, and whether a parser can extract it at all.
"""
import sys, os, re

from ..cliutil import docstring_usage, utf8_stdout, wants_help
from ..domain.gates.ats_rules import HEADING_MAX as HEADING_MAX
from ..domain.gates.ats_rules import LIGATURES as LIGATURES
from ..domain.gates.ats_rules import MIN_EXTRACTED_CHARS as MIN_EXTRACTED_CHARS
from ..domain.gates.ats_rules import RISKY_BULLETS as RISKY_BULLETS
from ..domain.gates.ats_rules import ROLE_WORDS as ROLE_WORDS
from ..domain.gates.ats_rules import SAFE_BULLETS as SAFE_BULLETS
from ..domain.gates.ats_rules import SPLIT_WORD as SPLIT_WORD
from ..domain.gates.ats_rules import codepoint as codepoint
from ..domain.gates.ats_rules import has_phone as has_phone
from ..domain.gates.ats_rules import is_heading as is_heading
from ..domain.gates.ats_rules import judge as judge
from ..infra.pdf import read_pdf

# The keyword emit_latex.py writes into the PDF's metadata to name the variant.
VARIANT_KEYWORD = re.compile(r"jsk-variant:([A-Za-z0-9_-]+)")


def variant_of(pdf_path):
    """The render variant the PDF was built as - "ats-maximal", "presentation" -
    or None when its metadata carries no marker.

    Read from the metadata rather than the file name, because the name is the
    person's to change: "_ATS" in the stem was the only marker, and a renamed
    file silently lost its strict check. None for a file that cannot be opened
    as a PDF - the gate itself reports that. Raises ImportError without
    pymupdf, as read_pdf() does: a variant nobody could read is not the same
    answer as a variant that is not there.
    """
    from ..infra.pdf import keywords as keywords_of

    try:
        keywords = keywords_of(pdf_path)
    except ImportError:
        raise
    except Exception:  # noqa: BLE001 - pymupdf raises its own types on a damaged PDF; no keyword then
        return None
    m = VARIANT_KEYWORD.search(keywords)
    return m.group(1) if m else None


def read_txt(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read(), []


def main(argv=None):
    """The gate, as an exit code. `argv` is the arguments alone, as check_prose.py takes them.

    It read `sys.argv` directly until `jsk gates` needed to call it in-process
    rather than pay a fresh interpreter to do the same work. The CLI is the
    documented API and has not moved: the default reproduces it exactly.
    """
    argv = sys.argv[1:] if argv is None else list(argv)
    # The non-ASCII findings would otherwise be unprintable on a cp1252 console.
    utf8_stdout()

    if wants_help(argv):
        # Before the path is read: `--help` used to be looked up as a file and
        # reported "file not found: --help" with the usage-error exit.
        print(docstring_usage(__doc__))
        return 0
    if not argv:
        print("usage: python -m jsk.gates.check_ats resume.pdf | resume.txt [--strict]")
        return 2
    path = argv[0]
    strict = "--strict" in argv
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2

    ext = os.path.splitext(path)[1].lower()

    def unreadable(reason):
        print(f"checking: {os.path.basename(path)}")
        print("\nFAIL 1   WARN 0")
        print(f"  FAIL  unreadable: {reason}")
        print("\nDO NOT SEND - fix the failures above")
        return 1

    if ext == ".pdf":
        try:
            txt, fonts = read_pdf(path)
        except ImportError:
            print("NO PDF LIBRARY - cannot read the deliverable.")
            print("  check_ats.py needs pymupdf to extract text from a PDF:")
            print("      pip install pymupdf")
            print("  Without it the parse gate is unverifiable; treat the resume as unchecked.")
            return 2
        except Exception as e:  # noqa: BLE001 - any pymupdf failure is the verdict "unreadable"
            return unreadable(f"{type(e).__name__}: {e}")
    elif ext == ".txt":
        try:
            txt, fonts = read_txt(path)
        except OSError as e:
            return unreadable(str(e))
    else:
        print(f"FAIL  format: {ext or '(none)'} - pass the .pdf or the .txt")
        return 1

    lines, report = judge(txt, fonts, pdf=ext == ".pdf", strict=strict)
    fails, warns = report.fails, report.warns

    # --- report ---
    mode = "ATS-maximal (strict)" if strict else "presentation"
    print(f"checking: {os.path.basename(path)}   mode: {mode}")
    print(f"lines of extracted text: {len(lines)}   fonts: {', '.join(fonts) or 'n/a'}")
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    for f in fails:
        print("  FAIL  " + f)
    for w in warns:
        print("  warn  " + w)
    print("\nPASS - safe to send" if not fails else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
