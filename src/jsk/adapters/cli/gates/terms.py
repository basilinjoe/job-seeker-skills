"""Check how much of the posting's own wording a rendered resume carries.

Usage: jsk resume check <out-dir> --record <applications/<dir>/resume.json>
       (runs after the layout gate whenever the record and a .txt render are there)

Exit 0 = every finding is a warning; this gate never stops a send. Exit 2 = usage error.
No third-party dependencies.

The sibling of the parse gate. That one asks whether a parser can read the page; this
one asks whether a recruiter's search for the posting's words would find it - the title
and each required and preferred term, matched as a string, as an ATS search matches.
"""
import os

from ..cliutil import docstring_usage, parse_flags, utf8_stdout, wants_help
from . import present


def gate(args):
    """The terms gate over the arguments alone, as `jsk resume check` runs it.

    Args:
        args: the .txt render, then --record <resume.json>.

    Returns:
        (exit code, the TermsResult or Unreadable, None when the call was wrong).
        Prints the verdict; reads the render and loads the workspace.
    """
    from ....application.gates.terms import check_terms
    from ....application.gates.result import Unreadable
    from ....infra.documents import read_txt
    from ..compose.gates import posting_terms

    if wants_help(args):
        print(docstring_usage(__doc__))
        return 0, None
    parsed, _ = parse_flags(list(args), ("--record",), ())
    if parsed is None or len(parsed[0]) != 1 or "--record" not in parsed[1]:
        print("usage: jsk resume check <out-dir> --record <resume.json>")
        return 2, None
    path, record = parsed[0][0], parsed[1]["--record"]
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2, None
    result = check_terms(path, record, read_txt=read_txt, terms=posting_terms)
    if isinstance(result, Unreadable):
        return present.unreadable(result), result
    return report(result), result


def report(result):
    """Print the terms gate's heading, counts, findings and verdict.

    Args:
        result: the TermsResult.

    Returns:
        The exit code: 0, as every finding is a warning.
    """
    print(f"checking: {result.name}")
    if result.posting is None:
        print("no posting beside the resume.json - nothing to cover; a general resume "
              "is searched by whatever a recruiter types")
        print("\nPASS - no posting to cover")
        return 0
    covered = "   ".join(f"{need}: {on}/{asked}" for need, (on, asked) in result.counts.items())
    print(f"posting: {result.posting}   on the page - {covered}")
    present.findings(result)
    return present.verdict(result, "PASS - terms reported")


def main(argv):
    """The terms gate, as an exit code.

    Args:
        argv: the arguments alone.

    Returns:
        The exit code. Prints the verdict.
    """
    utf8_stdout()
    return gate(list(argv))[0]
