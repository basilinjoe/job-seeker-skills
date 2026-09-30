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
import os

from ....cliutil import docstring_usage, utf8_stdout, wants_help
from . import present


def gate(args):
    """The parse gate over the arguments alone, as `jsk gates` runs it.

    Args:
        args: the document, then --strict when asked for.

    Returns:
        (exit code, the AtsResult or Unreadable - the GateStopped when it stopped, None
        when the call was wrong).
        Prints the verdict; reads the document.
    """
    from ....application.gates.ats import check_ats
    from ....application.gates.result import GateStopped, Unreadable
    from ....gates.check_ats import read_txt
    from ....infra.pdf import read_pdf

    if wants_help(args):
        # Before the path is read: `--help` used to be looked up as a file and
        # reported "file not found: --help" with the usage-error exit.
        print(docstring_usage(__doc__))
        return 0, None
    if not args:
        print("usage: python -m jsk.gates.check_ats resume.pdf | resume.txt [--strict]")
        return 2, None
    path = args[0]
    strict = "--strict" in args
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2, None
    try:
        result = check_ats(path, strict=strict, read_pdf=read_pdf, read_txt=read_txt)
    except GateStopped as stop:
        return stopped(stop), stop
    if isinstance(result, Unreadable):
        return present.unreadable(result), result
    return report(result), result


def stopped(stop):
    """Print why the parse gate judged nothing (application.gates.ats.check_ats).

    Returns:
        The stop's exit code.
    """
    if stop.kind == "no-pdf-library":
        print("NO PDF LIBRARY - cannot read the deliverable.")
        print("  check_ats.py needs pymupdf to extract text from a PDF:")
        print("      pip install pymupdf")
        print("  Without it the parse gate is unverifiable; treat the resume as unchecked.")
    else:
        print(f"FAIL  format: {stop.detail or '(none)'} - pass the .pdf or the .txt")
    return stop.code


def report(result):
    """Print the parse gate's heading, findings and verdict.

    Args:
        result: the AtsResult.

    Returns:
        The exit code: 1 when anything failed.
    """
    mode = "ATS-maximal (strict)" if result.strict else "presentation"
    print(f"checking: {result.name}   mode: {mode}")
    print(f"lines of extracted text: {result.lines}   fonts: {', '.join(result.fonts) or 'n/a'}")
    present.findings(result)
    return present.verdict(result, "PASS - safe to send")


def main(argv):
    """`python -m jsk.gates.check_ats`, as an exit code.

    Args:
        argv: the arguments alone, as check_prose.py takes them.

    Returns:
        The exit code. Prints the verdict.
    """
    # The non-ASCII findings would otherwise be unprintable on a cp1252 console.
    utf8_stdout()
    return gate(list(argv))[0]
