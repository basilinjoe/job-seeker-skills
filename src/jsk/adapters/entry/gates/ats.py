"""Check a generated resume against the rules in references/ats-rules.md

Usage: resume_check(resume.pdf, only="parse", strict=False)
       resume_check(resume.txt, only="parse", strict=False)
       --strict  (the strict argument) also enforce ATS-maximal rules (ASCII only, employer per role)

Exit 0 = pass. Exit 1 = do not send this file. Exit 2 = usage error.
Reading a PDF needs pymupdf; the .txt path is standard library only.

A render writes no .txt. Its plain text is emitted in memory from the selection's plan:
resume_check(<out-dir>, record=<stem>) judges it --strict, and holds the PDF to its
reading order. The selection of the target whose directory holds a PDF checked alone is read
for that order too.

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

from ..cliutil import docstring_usage, utf8_stdout, wants_help
from . import present


def gate(args):
    """The parse gate over the arguments alone, as the resume_check tool runs it.

    The document is a .pdf, a .txt passed by hand, or a target's ref - whose plan's plain
    text is judged in memory, as no render writes it to disk. `--record <ref>` beside a PDF
    holds the PDF to that text's reading order.

    Args:
        args: the document, then --strict when asked for, then --record <ref>.

    Returns:
        (exit code, the AtsResult or Unreadable - the GateStopped when it stopped, None
        when the call was wrong).
        Prints the verdict; reads the document, and the record's career.
    """
    from ....application.gates.ats import check_ats, check_text
    from ....application.gates.result import GateStopped, Unreadable, unreadable
    from ....domain.resume.short import ShortError
    from ....infra.documents import read_txt
    from ....infra.pdf import read_pdf
    from ...compose.gates import plan_text

    if wants_help(args):
        # Before the path is read: `--help` used to be looked up as a file and
        # reported "file not found: --help" with the usage-error exit.
        print(docstring_usage(__doc__))
        return 0, None
    args, record = list(args), None
    if "--record" in args:
        at = args.index("--record")
        if at + 1 >= len(args):
            print("usage: resume_check(resume.pdf | resume.txt, only=\"parse\", strict=False)")
            return 2, None
        record = args[at + 1]
        del args[at:at + 2]
    if not args:
        print("usage: resume_check(resume.pdf | resume.txt, only=\"parse\", strict=False)")
        return 2, None
    from ....application.render.selection import parse_ref, shown_name

    path = args[0]
    strict = "--strict" in args
    # A target's ref is a record, with no file to find; a resume.json was one until 6.0, and
    # is told so by the plan it cannot be read for.
    selected = parse_ref(path) is not None
    if not selected and not os.path.exists(path):
        print(f"file not found: {path}")
        return 2, None
    if selected or path.lower().endswith(".json"):
        name = f"plain text of {shown_name(path)} (in memory)"
        try:
            text = plan_text(path)
        except ShortError as err:
            result = unreadable(name, f"not emitted: {err} - {err.fix}")
            return present.unreadable(result), result
        result = check_text(text, name, strict=strict)
        return report(result), result
    stream = no_stream = None
    if record is not None and path.lower().endswith(".pdf"):
        try:
            stream = plan_text(record)
        except ShortError as err:
            no_stream = f"the plain text of {os.path.basename(record)} could not be " \
                        f"emitted: {err}"
    try:
        result = check_ats(path, strict=strict, read_pdf=read_pdf, read_txt=read_txt,
                           stream=stream, no_stream=no_stream)
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
        print("  The parse gate needs pymupdf to extract text from a PDF:")
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
    """The parse gate (the resume_check tool), as an exit code.

    Args:
        argv: the arguments alone, as check_prose.py takes them.

    Returns:
        The exit code. Prints the verdict.
    """
    # The non-ASCII findings would otherwise be unprintable on a cp1252 console.
    utf8_stdout()
    return gate(list(argv))[0]
