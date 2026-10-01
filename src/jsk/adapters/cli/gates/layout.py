"""The layout gate: what the render gate's checklist could measure, measured.

Usage: jsk resume check resume.pdf --only layout [--record R] [--region CC] [--pages N]
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

The page count is printed, never failed: `jsk resume fit` owns that verdict. What stays a
person's is whether it looks right as a whole, the region's work-rights line or
declaration, and whether it is true.
"""
import os

from ..cliutil import docstring_usage, utf8_stdout, wants_help
from . import present


def arg(argv, flag):
    """The value after `flag` in `argv`: "" when the flag ends it, None when it is absent."""
    if flag in argv:
        at = argv.index(flag)
        return argv[at + 1] if at + 1 < len(argv) else ""
    return None


def refused(argv):
    """The exit code for a call that is wrong before anything is read, or None.

    Args:
        argv: the arguments alone.

    Returns:
        2 (0 for --help) after printing why, or None when the call can go ahead.
    """
    if wants_help(argv):
        print(docstring_usage(__doc__))
        return 0
    if not argv or argv[0].startswith("-"):
        print("usage: jsk resume check resume.pdf --only layout [--record R] [--region CC] "
              "[--pages N]")
        return 2
    path = pdf_of(argv[0])
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
    return None


def pdf_of(named):
    """The PDF a call names: `jsk resume check` finds a gate's file from whichever sibling was named."""
    return named if named.lower().endswith(".pdf") else os.path.splitext(named)[0] + ".pdf"


def gate(argv):
    """The layout gate over the arguments alone, as `jsk resume check` runs it.

    Args:
        argv: the PDF (or a sibling of it), then --record, --region and --pages.

    Returns:
        (exit code, the LayoutResult or Unreadable - the GateStopped when it stopped, None
        when the call was wrong). Prints the verdict; reads the PDF and maybe its record.
    """
    code = refused(argv)
    if code is not None:
        return code, None
    from ....application.gates.layout import check_layout
    from ....application.gates.result import GateStopped, Unreadable
    from ..compose.gates import from_record
    from ....infra import pdf

    path = pdf_of(argv[0])
    pages_flag = arg(argv, "--pages")
    try:
        result = check_layout(path, region=arg(argv, "--region"),
                              budget=int(pages_flag) if pages_flag else None,
                              record=arg(argv, "--record"), available=pdf.available,
                              read_lines=pdf.lines, plan_of=from_record)
    except GateStopped as stop:
        print(f"SKIPPED - pymupdf is not installed, so {stop.detail} was not read.")
        print("  fix:  pip install pymupdf")
        print("  A gate that did not run is not a gate that passed.")
        return stop.code, stop
    if isinstance(result, Unreadable):
        return present.unreadable(result), result
    return report(result), result


def report(result):
    """Print the layout gate's heading, measurements, findings and verdict.

    Args:
        result: the LayoutResult.

    Returns:
        The exit code: 1 when anything failed.
    """
    count = f"{result.pages} page{'' if result.pages == 1 else 's'}"
    if result.budget:
        count += f" of a budget of {result.budget} (reported; jsk resume fit owns that verdict)"
    print(f"checking: {result.name}   region: {(result.region or 'unknown').upper()}")
    print(f"pages: {count}   paper: {', '.join(result.papers)}   "
          f"families: {', '.join(result.faces) or 'n/a'}")
    present.findings(result)
    return present.verdict(result, "PASS - the layout holds")


def main(argv):
    """The layout gate (`jsk resume check --only layout`), as an exit code.

    Args:
        argv: the arguments alone.

    Returns:
        The exit code. Prints the verdict.
    """
    utf8_stdout()
    return gate(list(argv))[0]
