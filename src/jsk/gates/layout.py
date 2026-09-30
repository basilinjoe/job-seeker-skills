#!/usr/bin/env python3
"""The layout gate: what the render gate's checklist could measure, measured.

Usage: jsk check resume.pdf --only layout [--record R] [--region CC] [--pages N]
       python -m jsk.gates.layout resume.pdf [the same flags]
       --record R   the resume.json it rendered from: the region and page budget
                    are read from it. Default: a resume.json beside the PDF
       --region CC  the region whose paper the PDF must be on, e.g. US, AU
       --pages N    the page budget, when the record is not the one to ask

Exit 0 = pass. Exit 1 = do not send this file, or pymupdf is missing and nothing
was checked. Exit 2 = usage error.

A model reading page images was asked to see tofu, a second typeface, a heading
stranded at a page foot, a date out of its column and the wrong paper. Each is in
the PDF's own geometry and fonts, and a model reading pictures is neither reliable
nor free at any of them:

  FAIL  U+FFFD or a private-use codepoint in the text layer, or a Type3 font - the
        bitmap faces TeX falls back to without lmodern, which extract as garbage
  FAIL  more than one text family, unless the pair is one a shipped template
        declares for body and headings (circuit, atrium) - the check follows the
        templates, not the checklist's "one family", because two templates were
        designed with two
  FAIL  a section heading that is the last text on its page
  FAIL  a date range out of the right-hand column every other one sits in
  FAIL  paper neither A4 nor Letter, or not the one the region renders on

The page count is printed, never failed: `jsk fit` owns that verdict. What stays a
person's is whether it looks right as a whole, the region's work-rights line or
declaration, and whether it is true.
"""
import os
import sys

from ..cliutil import docstring_usage, utf8_stdout, wants_help
from ..domain.gates.layout_rules import SECTION_TITLES as SECTION_TITLES
from ..domain.gates.layout_rules import PDF_FAMILY as PDF_FAMILY
from ..domain.gates.layout_rules import SYMBOL_FACES as SYMBOL_FACES
from ..domain.gates.layout_rules import PAPERS as PAPERS
from ..domain.gates.layout_rules import PAPER_SLACK as PAPER_SLACK
from ..domain.gates.layout_rules import DATE_SLACK as DATE_SLACK
from ..domain.gates.layout_rules import MONTH as MONTH
from ..domain.gates.layout_rules import DATE_LINE as DATE_LINE
from ..domain.gates.layout_rules import SUBSET as SUBSET
from ..domain.gates.layout_rules import family as family
from ..domain.gates.layout_rules import declared_pairs as declared_pairs
from ..domain.gates.layout_rules import paper_name as paper_name
from ..domain.gates.layout_rules import expected_paper as expected_paper
from ..domain.gates.layout_rules import is_tofu as is_tofu
from ..domain.gates.layout_rules import check as check
from ..infra.pdf import lines as read


def arg(argv, flag):
    if flag in argv:
        at = argv.index(flag)
        return argv[at + 1] if at + 1 < len(argv) else ""
    return None


def from_record(record, pdf):
    """(region, page budget, None) from the plan the render built, or (None, None, why)."""
    from .check_ats import variant_of              # noqa: PLC0415
    from ..resume import build                     # noqa: PLC0415 - only with a record
    try:
        plan, _ = build.from_path(record, fmt=variant_of(pdf))
    except Exception as exc:                       # noqa: BLE001 - reported, never fatal
        return None, None, f"{type(exc).__name__}: {exc}"
    return plan.get("region"), plan.get("pages"), None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    utf8_stdout()
    if wants_help(argv):
        print(docstring_usage(__doc__))
        return 0
    if not argv or argv[0].startswith("-"):
        print("usage: python -m jsk.gates.layout resume.pdf [--record R] [--region CC] "
              "[--pages N]")
        return 2
    path = argv[0]
    if not path.lower().endswith(".pdf"):
        # `jsk check` finds a gate's file from whichever sibling was named.
        path = os.path.splitext(path)[0] + ".pdf"
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2
    region, pages_flag, record = arg(argv, "--region"), arg(argv, "--pages"), arg(argv, "--record")
    if "" in (region, pages_flag, record):
        print("--record, --region and --pages each need a value")
        return 2
    if pages_flag is not None and not pages_flag.isdigit():
        print(f"--pages needs a whole number of pages, got {pages_flag!r}")
        return 2
    if record is not None and not os.path.isfile(record):
        print(f"not a record file: {record}")
        print("fix:  --record takes the resume.json the PDF rendered from")
        return 2

    try:
        import pymupdf  # noqa: F401,PLC0415 - optional dependency
    except ImportError:
        print(f"SKIPPED - pymupdf is not installed, so {os.path.basename(path)} was not read.")
        print("  fix:  pip install pymupdf")
        print("  A gate that did not run is not a gate that passed.")
        return 1

    notes = []
    if record is None:
        beside = os.path.join(os.path.dirname(os.path.abspath(path)), "resume.json")
        record = beside if os.path.isfile(beside) else None
    budget = int(pages_flag) if pages_flag else None
    if record is not None and (region is None or budget is None):
        planned_region, planned_pages, why = from_record(record, path)
        if why:
            notes.append(f"{os.path.basename(record)} unread, so no region or budget: {why}")
        region = region or planned_region
        budget = budget or planned_pages

    try:
        pages, type3 = read(path)
    except Exception as exc:                       # noqa: BLE001 - the verdict, not a crash
        print(f"checking: {os.path.basename(path)}")
        print("\nFAIL 1   WARN 0")
        print(f"  FAIL  unreadable: {type(exc).__name__}: {exc}")
        print("\nDO NOT SEND - fix the failures above")
        return 1
    fails, warns, faces, papers = check(pages, type3, region)
    warns = notes + warns

    count = f"{len(pages)} page{'' if len(pages) == 1 else 's'}"
    if budget:
        count += f" of a budget of {budget} (reported; jsk fit owns that verdict)"
    print(f"checking: {os.path.basename(path)}   region: {(region or 'unknown').upper()}")
    print(f"pages: {count}   paper: {', '.join(papers)}   families: {', '.join(faces) or 'n/a'}")
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    for f in fails:
        print("  FAIL  " + f)
    for w in warns:
        print("  warn  " + w)
    print("\nPASS - the layout holds" if not fails else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
