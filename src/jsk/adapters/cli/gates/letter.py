"""The letter check: a cover letter, against the resume.json it goes out beside.

Usage: jsk check <cover-letter.txt|.md> --only letter --record <resume.json>
       python -m jsk.gates.letter <cover-letter.txt|.md> [--record <resume.json>]
       --record R    the application's resume.json; without it the number check is
                     SKIPPED, and a gate that did not run is a failure

Exit 0 = fit to send. Exit 1 = do not send this letter. Exit 2 = usage, or a
resume.json outside a workspace.
"""
import datetime
import os

from ....cliutil import docstring_usage, parse_flags, utf8_stdout, wants_help
from . import present


def parse(argv):
    """Read the letter check's arguments.

    Args:
        argv: the arguments alone.

    Returns:
        (letter, record, problem): the letter, --record's value or None, and what was
        wrong with the call, or None.
    """
    no_value = "--record needs a value\nfix:  --record applications/<dir>/resume.json"
    parsed, problem = parse_flags(argv, ("--record",), ())
    if parsed is None:
        return None, None, no_value if problem.kind == "missing" else \
            f"{problem}\n{docstring_usage(__doc__)}"
    positional, flags = parsed
    record = flags.get("--record")
    if record == "":
        return None, None, no_value
    if len(positional) != 1:
        return None, None, docstring_usage(__doc__)
    return positional[0], record, None


def gate(argv):
    """The letter check over the arguments alone.

    Args:
        argv: the letter, then --record R.

    Returns:
        (exit code, the LetterResult - the GateStopped when it stopped, None when the call
        or the resume.json was wrong). Prints the verdict; reads the letter, and with a
        record its career and the posting.md beside it.
    """
    if wants_help(argv):
        print(docstring_usage(__doc__))
        return 0, None
    path, record, problem = parse(argv)
    if problem:
        print(problem)
        return 2, None
    assert path is not None, "parse names the letter whenever it reports no problem"
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2, None
    if os.path.splitext(path)[1].lower() not in (".txt", ".md"):
        print(f"unsupported file type {os.path.splitext(path)[1]!r} - write the letter as "
              ".txt or .md")
        return 2, None
    from ....application.gates.letter import check_letter
    from ....application.gates.result import GateStopped
    from ....domain.resume.short import ShortError
    from ....gates.letter import number_lines, read
    from ....resume import short
    from .record import has_engine

    try:
        result = check_letter(path, record, read=read, read_short=short.read,
                              workspace=short.workspace, has_engine=has_engine,
                              career=short.career, number_lines=number_lines,
                              today=datetime.date.today())
    except ShortError as err:
        print(f"FAIL  {err}")
        print(f"fix:  {err.fix}")
        return 2, None
    except GateStopped as stop:
        print("FAIL  the number check needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return stop.code, stop
    return report(result), result


def report(result):
    """Print the letter check's heading, findings and verdict.

    Args:
        result: the LetterResult.

    Returns:
        The exit code: 1 when anything failed.
    """
    from ....domain.gates.letter_rules import LIMIT

    print(f"checking: {result.name}   against: {result.against}")
    print(f"words: {result.words} (limit {LIMIT})")
    present.findings(result)
    return present.verdict(result, "PASS - fit to send")


def main(argv):
    """`python -m jsk.gates.letter` and `jsk check --only letter`, as an exit code.

    Args:
        argv: the arguments alone.

    Returns:
        The exit code. Prints the verdict.
    """
    utf8_stdout()
    return gate(argv)[0]
