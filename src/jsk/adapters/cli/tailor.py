"""jsk tailor prepare - everything an assessment reads, in one call.

Usage: jsk tailor prepare <applications/<dir>> [--draft-gaps] [--cover N] [--today YYYY-MM-DD]

  --draft-gaps  also draft <dir>/gaps.txt, the analyst's overlay: a `<!-- jsk: -->` slot
                wherever judgement is needed (never over one there)
  --cover N     the most projects the cover may use (default 3)
  --today       the date recency is measured from (default: today)

One process, one digest, in this order: the check, scoped to this application plus any
FAIL anywhere; the match as `jsk tailor match` prints it; what the record holds for every missing
and candidate term; the person, for eligibility; the cover's projects with their bullets;
what those projects hold unconfirmed; and the assessment - the gaps graph and gaps.md,
derived from the match with gaps.txt folded in when there is one, written on every run.
Every section has a size cap and says when it was cut.

Exit 0 digest printed; 1 a FAIL blocks the match, or the draft could not be written; 2
called wrong. A gaps.txt the check refuses is reported in the digest, not an exit 1: the
analyst may be halfway through filling it.

Written after the JumpCloud run (2026-09-26), where the analyst made about ten calls
between the posting and gaps.md - fmt, check, match, evidence, person, show, show,
unconfirmed - and each was a model turn carrying long silent reasoning (53s, 128s). The
tools took two seconds apiece; the turns took four minutes.
"""
import datetime

from ...cliutil import docstring_usage, wants_help
from .options import BadOption, take_values, tailor_options

USAGE = ("usage: jsk tailor prepare <applications/<dir>> [--draft-gaps] [--cover N] "
         "[--today YYYY-MM-DD]")


def section(title, lines):
    """Print one section of the digest: its `== title` heading, then its lines."""
    print(f"\n== {title}\n")
    for line in lines:
        print(line)


def main(argv):
    """`jsk tailor prepare`: the digest printed, the assessment written.

    Args:
        argv: the arguments after `jsk tailor`.

    Returns:
        The exit code: 0 digest printed, 1 a FAIL blocks the match or pyoxigraph is
        missing, 2 called wrong.
    """
    from ...application.tailor.match_posting import application

    argv = list(argv)
    if wants_help(argv):
        print(docstring_usage(__doc__))
        return 0
    draft = "--draft-gaps" in argv
    argv = [a for a in argv if a != "--draft-gaps"]
    try:
        options = take_values(argv, ("--cover", "--today"))
    except BadOption as e:
        print(e)
        return 2
    if len(argv) != 2 or argv[0] != "prepare":
        print(USAGE)
        return 2
    try:
        opts = tailor_options(options.get("--cover"), options.get("--today"),
                              datetime.date.today)
    except BadOption as e:
        print(e)
        return 2
    root, app = application(argv[1], "jsk tailor prepare")
    if root is None:
        print("\n".join(app))
        return 2
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk tailor needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ...infra.oxigraph import record as R

    # It writes the assessment, so it takes its turn before it reads the record.
    with R.turn(root):
        return prepared(root, app, argv[1], opts, draft)


def prepared(root, app, named_as, opts, draft):
    """Run the digest over the real workspace and print it, inside the caller's turn.

    Returns:
        The digest's exit code.
    """
    from ...application.tailor.prepare import prepare
    from ...graph import select as SEL
    from ...graph import store as S
    from ...graph.gapsbuild import Folder
    from ...infra.files import file_name
    from ...infra.oxigraph.queries import OxigraphQueries
    from .compose.tailor import Reads

    digest = prepare(root, app, named_as, opts.budget, opts.today, draft, load=S.load,
                     queries=OxigraphQueries, select=SEL.select, name_of=file_name,
                     reads=Reads(), folder=Folder())
    for title, lines in digest.sections:
        section(title, lines)
    if digest.stop is not None:
        print(digest.stop)
    return digest.code
