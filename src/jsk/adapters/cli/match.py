"""jsk tailor match - a posting's requirements joined with the career, through the vocabulary.

Usage: jsk tailor match <applications/<dir>> [--cover N] [--json] [--today YYYY-MM-DD]
                 [--gaps <gaps.txt> | --draft-gaps <gaps.txt>]

  --cover N         the most projects the cover may use (default 3)
  --json            the same result, structured
  --today           the date recency is measured from (default: today)
  --gaps F          check the application's gaps.txt against the match, then write the
                    assessment and print it; a `<!-- jsk: ... -->` slot still in it is a
                    FAIL, and on a FAIL nothing is written
  --draft-gaps F    write the assessment from the match alone and print it, then draft
                    gaps.txt with a slot wherever judgement is needed; refuses an F that
                    exists

Reads the whole record of the workspace the application belongs to - the career, the
applications, the shipped vocabulary - and validates it first: a record with a FAIL is
not matched, because a match over a broken record would be a guess.

Exit 0 matched (missing requirements included: this is an assessment, not a gate),
1 the workspace has FAIL findings, or --gaps found a FAIL, 2 called wrong.

Each requirement lands in one bucket. `matched`: a project holds the concept, or one that
counts as it. `near`: only through an implies edge, for a required requirement, or the
project holds something broader. `missing`, `ambiguous` (the label names more than one
concept - the analyst answers with j:concept), `candidate` (it names none), `implicit`.
Each gets a default Verdict from its bucket and evidence; gaps.txt may lower it, never raise it.
"""
import datetime
import json
import os

from .cliutil import docstring_usage, wants_help
from .options import BadOption, take_values, tailor_options

USAGE = ("usage: jsk tailor match <applications/<dir>> [--cover N] [--json] "
         "[--today YYYY-MM-DD] [--gaps <gaps.txt> | --draft-gaps <gaps.txt>]")


def main(argv):
    """`jsk tailor match`: one application's posting matched, printed, or its assessment built.

    Args:
        argv: the arguments after `jsk tailor match`.

    Returns:
        The exit code: 0 matched, 1 a FAIL blocks it or --gaps found one, 2 called wrong.
        Prints the match; --gaps and --draft-gaps write the assessment and print it.
    """
    from ...application.tailor.check_gaps import gaps_refusal
    from ...application.tailor.match_posting import application

    argv = list(argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2
    try:
        options = take_values(argv, ("--cover", "--today", "--gaps", "--draft-gaps"))
    except BadOption as e:
        print(e)
        return 2
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if len(argv) != 1 or {"--gaps", "--draft-gaps"} <= options.keys():
        print(USAGE)
        return 2
    try:
        opts = tailor_options(options.get("--cover"), options.get("--today"),
                              datetime.date.today)
    except BadOption as e:
        print(e)
        return 2
    root, app = application(argv[0])
    if root is None:
        print("\n".join(app))
        return 2
    for flag in ("--gaps", "--draft-gaps"):
        refused = flag in options and graph_native(app, f"jsk tailor match {flag}")
        if refused:
            print(refused)
            return 1
        refused = flag in options and gaps_refusal(app, options[flag], flag == "--draft-gaps")
        if refused:
            print(refused)
            return 1

    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk tailor match needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ...infra.oxigraph import record as R

    # --gaps and --draft-gaps write the assessment, so they take their turn before they
    # read: what they validate is what they write over. A plain match only reads.
    writes = "--gaps" in options or "--draft-gaps" in options
    with R.turn(root, dry_run=not writes):
        return matched(root, app, argv[0], options, opts, as_json)


def graph_native(app, verb):
    """The refusal's two lines when `app` is graph-native - its review is the store's, not
    gaps.txt (Ruling 11 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md)
    - else None."""
    from ...application.posting.native import refused_verb
    from .compose.timeline import app_graphs, records

    rel = records().workspace_of_app(app)[1] or app
    try:
        graphs = app_graphs(app)
    except ImportError:
        return None         # no pyoxigraph: main says so next, and nothing is matched
    return refused_verb(graphs, rel, verb)


def run_match(root, app, named, opts):
    """The match over the real workspace: application.tailor.match_posting.match_posting
    with the store on disk, the engine's queries and the selection.

    Args:
        root: the workspace root.
        app: the application's absolute directory.
        named: the application as the caller named it.
        opts: the TailorOptions.

    Returns:
        The MatchReport.

    Raises:
        MatchStopped: a FAIL blocks the match, or the application holds no posting.
    """
    from ...application.tailor.match_posting import match_posting
    from .compose import match
    from .compose.record import load
    from ...infra.files import file_name
    from ...infra.oxigraph.queries import OxigraphQueries

    return match_posting(root, app, named, opts.today, opts.budget, load=load,
                         queries=OxigraphQueries, select=match.select, name_of=file_name)


def stopped(stop):
    """Print why a match stopped (application.tailor.match_posting.MatchStopped).

    Returns:
        1.
    """
    from .cliutil import show

    if stop.kind == "blocked":
        print(f"FAIL  the workspace has {len(stop.detail)} failures - fix them before matching:")
        show(stop.detail, "FAIL", 25)
        return 1
    print(f"{stop.detail}: holds no posting\n"
          f"      fix: `jsk posting build {stop.detail}` writes it from posting.md")
    return 1


def matched(root, app, named, options, opts, as_json):
    """Match, then print it or build the assessment from it, inside the caller's turn.

    Returns:
        The exit code.
    """
    from ...application.tailor.match_posting import MatchStopped
    from ...application.tailor.match_text import markdown

    try:
        report = run_match(root, app, named, opts)
    except MatchStopped as stop:
        return stopped(stop)
    if "--gaps" in options:
        return report_gaps(report, app, opts.today)
    if "--draft-gaps" in options:
        return write_draft(report, app, opts.today, options["--draft-gaps"])
    r = report.result
    print(json.dumps(r, indent=2, ensure_ascii=False) if as_json else markdown(r), end="")
    return 0


def show_build(written, found, label):
    """Print check_gaps.build's findings and what it wrote.

    Args:
        written: the graphs and files written.
        found: the (severity, text, fix) findings.
        label: what the summary line names.

    Returns:
        1 on any FAIL, else 0.
    """
    from ...application.tailor.check_gaps import shown

    for severity, text, fix in found:
        print(f"{severity}  {text}\n      fix: {fix}")
    fails = sum(s == "FAIL" for s, _, _ in found)
    if written:
        wrote = " - wrote " + " and ".join(shown(w) for w in written)
    else:
        wrote = " - nothing written" if fails else ""
    print(f"{label}: {fails} FAIL, {len(found) - fails} WARN{wrote}")
    return 1 if fails else 0


def show_assessment(text):
    """Print the assessment after the lines above it: it is not written to a file (Ruling 24
    of the graph-native plan - no gaps.md), so this is where the person and the author read it.

    Args:
        text: the assessment rendered (check_gaps.render), or None when none was written.
    """
    if text:
        print()
        print(text, end="" if text.endswith("\n") else "\n")


def report_gaps(report, app, today):
    """--gaps: check gaps.txt, then write the assessment and print it; 1 on any FAIL."""
    from ...application.tailor.check_gaps import build
    from .compose.tailor import Folder

    written, found, text = build(app, report.store, report.result, today, None,
                                 folder=Folder())
    code = show_build(written, found, os.path.join(app, "gaps.txt"))
    show_assessment(text)
    return code


def write_draft(report, app, today, path):
    """--draft-gaps: the assessment from the match alone, then gaps.txt drafted over it."""
    from ...application.tailor.draft_gaps import draft_over_match
    from ...domain.naming import app_graph
    from .compose.tailor import Folder

    done = draft_over_match(report, app, today, path, folder=Folder())
    if show_build(done.written, done.found, app_graph(report.rel, "gaps")):
        return 1
    print(f"wrote {path}: {len(report.result['requirements'])} requirements, "
          f"{done.slots} slots to fill")
    show_assessment(done.assessment)
    return 0
