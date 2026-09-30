"""The record gate: a short resume.json, and the career bullets it selects.

Usage: jsk validate <resume.json> [--strict] [--max-findings N]
       python -m jsk.gates.record <resume.json> [--strict] [--max-findings N]
       --strict            treat warnings as failures
       --max-findings N    print at most N failures and N warnings (default 25;
                           0 prints every one)

Exit 0 = safe to render. Exit 1 = do not render this. Exit 2 = usage, or no career to
check it against.
"""
import datetime

from ....cliutil import parse_flags, utf8_stdout, wants_help
from . import present

MAX_FINDINGS = 25


def parse(argv):
    """Read the record gate's arguments.

    Args:
        argv: the arguments alone.

    Returns:
        (path or None, strict, limit, problem): the resume.json, --strict, how many
        findings of each kind to print (None for every one), and what was wrong with the
        call, or None.
    """
    strict, limit = False, MAX_FINDINGS
    not_a_number = ("--max-findings needs a whole number, got {!r}\n"
                    "fix:  --max-findings 50   - or 0 to print every finding")
    parsed, problem = parse_flags(argv, ("--max-findings",), ("--strict",))
    if parsed is None:
        if problem.kind == "missing":
            return None, strict, limit, not_a_number.format(None)
        return None, strict, limit, f"{problem}\n{__doc__.split(chr(10) * 2)[1]}"
    positional, flags = parsed
    if "--max-findings" in flags:
        raw = flags["--max-findings"]
        if not raw.isdigit():
            return None, strict, limit, not_a_number.format(raw)
        limit = int(raw) or None
    strict = "--strict" in flags
    if len(positional) != 1:
        return None, strict, limit, __doc__.split("\n\n")[1]
    return positional[0], strict, limit, None


def gate(args):
    """The record gate over the arguments alone, as `jsk gates` runs it.

    Args:
        args: the resume.json, then --strict and --max-findings N.

    Returns:
        (exit code, the RecordResult - the GateStopped when it stopped, None when the call
        or the file was wrong). Prints the verdict; loads the workspace.
    """
    if wants_help(args):
        print(__doc__.split("\n\n")[1])
        return 0, None
    path, strict, limit, problem = parse(args)
    if problem:
        print(problem)
        return 2, None
    from ....application.gates.record import record_gate
    from ....application.gates.result import GateStopped
    from ....domain.resume.short import ShortError
    from ....gates.record import findings
    from ....infra.oxigraph import record as R
    from ....resume import short

    try:
        result = record_gate(path, strict=strict, read=short.read, workspace=short.workspace,
                             has_engine=has_engine, career=short.career, findings=findings,
                             state=R.state, today=datetime.date.today())
    except ShortError as err:
        print(f"FAIL  {err}")
        print(f"fix:  {err.fix}")
        return 2, None
    except GateStopped as stop:
        print("FAIL  the record gate needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return stop.code, stop
    return report(result, limit), result


def has_engine():
    """Whether pyoxigraph imports: the record gate reads the career through it."""
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        return False
    return True


def report(result, limit):
    """Print the record gate's heading, findings and verdict.

    Args:
        result: the RecordResult.
        limit: how many findings of each kind to print; None prints every one.

    Returns:
        The exit code: 1 when anything failed.
    """
    at = f" r{result.revision}" if result.revision else ""
    print(f"checking: {result.name}   against: career/store/{at}")
    present.findings(result, limit)
    return present.verdict(result, "PASS - safe to render",
                           "DO NOT RENDER - fix the failures above")


def main(argv):
    """`python -m jsk.gates.record` and `jsk validate`, as an exit code.

    Args:
        argv: the whole argv, the program name first.

    Returns:
        The exit code. Prints the verdict.
    """
    utf8_stdout()
    return gate(list(argv[1:]))[0]
