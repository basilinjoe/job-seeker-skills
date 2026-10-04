"""Check how much of the posting's own wording a rendered resume carries.

Usage: resume_check(<out-dir>, record=<stem>)
       as arguments: <out-dir> --record <stem>
       (runs after the layout gate whenever there is a record; it reads the render's
       plain text, emitted in memory from the record's plan)

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
    """The terms gate over the arguments alone, as the resume_check tool runs it.

    Args:
        args: --record <target's ref>, whose plan's plain text is read in memory - or a .txt
            passed by hand before it.

    Returns:
        (exit code, the TermsResult or Unreadable, None when the call was wrong).
        Prints the verdict; emits or reads the text and loads the workspace.
    """
    from ....application.gates.result import unreadable
    from ....application.gates.terms import check_terms
    from ....domain.resume.short import ShortError
    from ....infra.documents import read_txt
    from ..compose.gates import plan_text, posting_terms

    if wants_help(args):
        print(docstring_usage(__doc__))
        return 0, None
    parsed, _ = parse_flags(list(args), ("--record",), ())
    if parsed is None or len(parsed[0]) > 1 or "--record" not in parsed[1]:
        print("usage: resume_check(<out-dir>, record=<stem>)")
        return 2, None
    record = parsed[1]["--record"]
    # The posting first: a general resume has nothing to cover, and emitting its text
    # would load its career for no finding.
    found = posting_terms(record)
    if parsed[0]:
        path = parsed[0][0]
        if not os.path.exists(path):
            print(f"file not found: {path}")
            return 2, None
        name = os.path.basename(path)
        try:
            text, _ = read_txt(path)
        except OSError as e:
            result = unreadable(name, f"unreadable: {e}")
            return present.unreadable(result), result
    else:
        from ....application.render.selection import shown_name

        # Named as the parse gate names it: the selection's graph, not its ref's last part.
        name, text = f"plain text of {shown_name(record)} (in memory)", ""
        if found is not None:
            try:
                text = plan_text(record)
            except ShortError as err:
                result = unreadable(name, f"not emitted: {err} - {err.fix}")
                return present.unreadable(result), result
    result = check_terms(text, name, record, terms=lambda _: found)
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
        print("no posting for this selection - nothing to cover; a general resume "
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
