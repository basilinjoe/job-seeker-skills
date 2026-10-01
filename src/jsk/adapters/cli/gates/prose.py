"""Check a generated resume against the rules in references/writing-rules.md

Usage: jsk resume check resume.pdf --only prose     (reads the .tex beside it)
       jsk resume check resume.tex --only prose
       jsk resume check resume.txt --only prose

Exit 0 = pass. Exit 1 = do not send this file. Exit 2 = usage error.
No third-party dependencies.

The sibling gate to check_ats.py. That one verifies a document *parses*; this one
verifies it *reads* - and reports how much of it is quantified, which nothing
else measures: the record gate checks that a number in a bullet traces to a metric,
never that any number is there at all. A bullet in the third person - "the platform followed him
through his promotion" - is not a parsing defect, so check_ats.py passes it with
0 failures and is right to. Nothing else was checking.
"""
import os

from ....cliutil import docstring_usage, utf8_stdout, wants_help
from . import present


def gate(args):
    """The prose gate over the arguments alone, as `jsk resume check` runs it.

    Args:
        args: the document.

    Returns:
        (exit code, the ProseResult or Unreadable - the GateStopped when it stopped, None
        when the call was wrong). Prints the verdict; reads the document.
    """
    from ....application.gates.prose import check_prose
    from ....application.gates.result import GateStopped, Unreadable
    from ....infra.documents import read_tex
    from ....infra.documents import read_txt_paragraphs as read_txt

    if wants_help(args):
        # Before the path is read: `--help` used to be looked up as a file and
        # reported "file not found: --help" with the usage-error exit.
        print(docstring_usage(__doc__))
        return 0, None
    if not args:
        print("usage: jsk resume check resume.tex | resume.txt --only prose")
        return 2, None
    path = args[0]
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2, None
    try:
        result = check_prose(path, read_tex=read_tex, read_txt=read_txt)
    except GateStopped as stop:
        print(f"unsupported file type {stop.detail!r} - pass the .tex or the .txt variant")
        return stop.code, stop
    if isinstance(result, Unreadable):
        return present.unreadable(result), result
    return report(result), result


def report(result):
    """Print the prose gate's heading, counts, findings and verdict.

    Args:
        result: the ProseResult.

    Returns:
        The exit code: 1 when anything failed.
    """
    counts = f"paragraphs: {result.paragraphs}   bullets: {result.bullets}"
    if result.quantified is not None and result.bullets:
        counts += (f"   quantified: {result.quantified}/{result.bullets} "
                   f"({result.quantified * 100 // result.bullets}%)")
    print(f"checking: {result.name}")
    print(counts)
    present.findings(result)
    return present.verdict(result, "PASS - prose rules satisfied")


def main(argv):
    """The prose gate (`jsk resume check --only prose`), as an exit code.

    Args:
        argv: the arguments alone.

    Returns:
        The exit code. Prints the verdict.
    """
    utf8_stdout()
    return gate(argv)[0]
