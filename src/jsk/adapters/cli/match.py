"""jsk match - a posting's requirements joined with the career, through the vocabulary.

Usage: jsk match <applications/<dir>> [--cover N] [--json] [--today YYYY-MM-DD]
                 [--gaps <gaps.txt> | --draft-gaps <gaps.txt>]

  --cover N         the most projects the cover may use (default 3)
  --json            the same result, structured
  --today           the date recency is measured from (default: today)
  --gaps F          check the application's gaps.txt against the match, then write the
                    assessment and gaps.md; a `<!-- jsk: ... -->` slot still in it is a
                    FAIL, and on a FAIL nothing is written
  --draft-gaps F    write the assessment and gaps.md from the match alone, then draft
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

from ...cliutil import docstring_usage, wants_help
from .options import BadOption, take_values, tailor_options

USAGE = ("usage: jsk match <applications/<dir>> [--cover N] [--json] "
         "[--today YYYY-MM-DD] [--gaps <gaps.txt> | --draft-gaps <gaps.txt>]")


def main(argv):
    """`jsk match`: one application's posting matched, printed, or its assessment built.

    Args:
        argv: the arguments after `jsk match`.

    Returns:
        The exit code: 0 matched, 1 a FAIL blocks it or --gaps found one, 2 called wrong.
        Prints the match; --gaps and --draft-gaps write the assessment and gaps.md.
    """
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
        refused = flag in options and gaps_refusal(app, options[flag], flag == "--draft-gaps")
        if refused:
            print(refused)
            return 1

    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk match needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ...infra.oxigraph import record as R

    # --gaps and --draft-gaps write the assessment, so they take their turn before they
    # read: what they validate is what they write over. A plain match only reads.
    writes = "--gaps" in options or "--draft-gaps" in options
    with R.turn(root, dry_run=not writes):
        return matched(root, app, argv[0], options, opts, as_json)


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
    from ...graph import select as SEL
    from ...graph import store as S
    from ...infra.files import file_name
    from ...infra.oxigraph.queries import OxigraphQueries

    return match_posting(root, app, named, opts.today, opts.budget, load=S.load,
                         queries=OxigraphQueries, select=SEL.select, name_of=file_name)


def stopped(stop):
    """Print why a match stopped (application.tailor.match_posting.MatchStopped).

    Returns:
        1.
    """
    from ...cliutil import show

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


def gaps_refusal(app, path, drafting):
    """Why `path` is not this application's gaps.txt, or None. gaps.md is written by jsk
    now, and read by nothing: a gaps.md jsk did not write is an older assessment."""
    if path.endswith(".md"):
        return (f"FAIL  {path}: gaps.md is written by jsk now; one it did not write is an "
                f"older assessment, read by people only\n"
                f"      fix: pass the application's gaps.txt - --draft-gaps drafts one")
    want = os.path.join(os.path.abspath(app), "gaps.txt")
    if os.path.normcase(os.path.abspath(path)) != os.path.normcase(want):
        return (f"FAIL  {path}: not this application's gaps.txt\n"
                f"      fix: pass {want} - gaps.md is written beside it")
    if drafting and os.path.exists(path):
        # The analyst's filled slots are its judgement; a re-run must not wipe them.
        return (f"FAIL  {path} exists - the draft would overwrite it\n"
                f"      fix: check it with --gaps, or delete it to draft again")
    if not drafting and not os.path.isfile(path):
        return (f"FAIL  {path}: no such file\n"
                f"      fix: draft it with --draft-gaps, or let `jsk tailor prepare` write "
                f"the assessment alone")
    return None


def show_build(written, found, label):
    """Print gapsbuild.build's findings and what it wrote; 1 on any FAIL."""
    for severity, text, fix in found:
        print(f"{severity}  {text}\n      fix: {fix}")
    fails = sum(s == "FAIL" for s, _, _ in found)
    if written:
        from ...graph.gapsbuild import shown
        wrote = " - wrote " + " and ".join(shown(w) for w in written)
    else:
        wrote = " - nothing written" if fails else ""
    print(f"{label}: {fails} FAIL, {len(found) - fails} WARN{wrote}")
    return 1 if fails else 0


def report_gaps(report, app, today):
    """--gaps: check gaps.txt, then write the assessment and gaps.md; 1 on any FAIL."""
    from ...graph.gapsbuild import build

    written, found = build(app, report.store, report.result, today)
    return show_build(written, found, os.path.join(app, "gaps.txt"))


def write_draft(report, app, today, path):
    """--draft-gaps: the assessment from the match alone, then gaps.txt drafted over it."""
    from ...domain.naming import app_graph
    from ...graph.gapsbuild import build
    from ...graph.gapsderive import derive
    from ...graph.gapsdraft import MARK, draft_gaps

    r, store = report.result, report.store
    derived = derive(r, store)
    written, found = build(app, store, r, today, derived)
    if show_build(written, found, app_graph(report.rel, "gaps")):
        return 1
    text = draft_gaps(derived, store, os.path.join(app, "posting.md"))
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    slots = sum(MARK in line for line in text.split("\n"))
    print(f"wrote {path}: {len(r['requirements'])} requirements, {slots} slots to fill")
    return 0
