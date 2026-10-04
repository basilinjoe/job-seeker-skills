"""An unsent application set aside - its graphs removed, its folder kept.

This module is the entry point the app_drop tool calls (adapters/mcp/upkeep.py). `jsk app drop`
itself was retired on 2026-10-04 (docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 4) and
exits 2 naming the tool; the flags below are the ones the tool passes.

Usage: drop <app-dir> [--reason TEXT] [--dry-run] [--today YYYY-MM-DD]

  <app-dir>   applications/<stem>, or the stem alone inside the workspace
  --reason    why, written into DROPPED.txt
  --dry-run   say what would be removed and moved, and write nothing
  --today     the date DROPPED.txt carries, for a test; the clock's by default

Removes every graph career/store/ holds for an application that was never frozen - its
posting, review, gaps and selection - in one update, validated with the workspace first;
then moves its folder, files intact, to dropped/<stem>/ beside applications/ (dropped/<stem>-2
when that is taken) with a DROPPED.txt saying when, why and what left the store. A frozen
application, sent or held back, is an archive and is refused. It is how an application made
from files that will not be sent is cleared before jsk 6.0 (Ruling 5 of
docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, amended 2026-10-03).

Exit 0 dropped, or a dry run; 1 refused, or the folder not moved after the store was written;
2 called wrong, or the path is no application.

The drop is application/timeline/drop.py, bound by compose/timeline.py's drop_app. No agent
may call the tool: setting an application aside is the person's decision.
"""
import datetime
import os

from ...domain.timeline.events import is_date
from .cliutil import parse_flags, wants_help

USAGE = ("usage: app_drop(app, reason=, dry_run=)\n"
         "  as arguments: <app-dir> [--reason TEXT] [--dry-run] [--today YYYY-MM-DD]")


def usage(message):
    """Print a call error and the usage line.

    Args:
        message: what was wrong with the call.

    Returns:
        2, the exit code of a call made wrong.
    """
    print(message)
    print(USAGE)
    return 2


def located(target):
    """The application directory `target` names: a path as given, or - a bare stem that is no
    path here - applications/<stem> in the workspace around the current directory."""
    from ...infra.files import find_root

    if os.sep in target or "/" in target or os.path.exists(target):
        return target
    root = find_root(os.getcwd())
    return os.path.join(root, "applications", target) if root else target


def main(args):
    """The app_drop tool's entry point: set one unsent application aside.

    Args:
        args: the arguments after `drop`.

    Returns:
        The exit code: 0 dropped or a dry run, 1 refused or landed half, 2 called wrong.
        Reads the clock once, for --today's default; removes the graphs and moves the
        folder unless --dry-run.
    """
    if wants_help(args):
        # __doc__ is None only under -OO, which nothing runs jsk with.
        print(__doc__.split("\n\nRemoves", 1)[0].split("\n\n", 2)[2])  # pyright: ignore[reportOptionalMemberAccess]
        return 0
    parsed, problem = parse_flags(args, ("--reason", "--today"), ("--dry-run",))
    if parsed is None:
        return usage(problem)
    positional, flags = parsed
    if len(positional) != 1:
        return usage("app_drop takes one application directory")
    today = flags.get("--today", datetime.date.today().isoformat())
    if not is_date(today):
        return usage(f"--today needs YYYY-MM-DD, got {today!r}")
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  the app_drop tool needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    app_dir = located(positional[0].rstrip("/\\") or positional[0])
    return dropped(app_dir, flags.get("--reason"), datetime.date.fromisoformat(today),
                   "--dry-run" in flags)


def dropped(app_dir, reason, today, dry_run):
    """Drop the application, or say what a dry run would, and print it.

    Args:
        app_dir: the application directory.
        reason: --reason, or None.
        today: the date the command runs on.
        dry_run: write nothing.

    Returns:
        The exit code.
    """
    from ...application.timeline.drop import (NOTE, DropLanded, DropRefused,
                                              NotAnApplication)
    from ...infra.files import rel
    from ..compose.timeline import drop_app

    try:
        result = drop_app(app_dir, reason=reason, today=today, dry_run=dry_run)
    except NotAnApplication as e:
        print(f"FAIL  {e}")
        print(f"fix:  {e.fix}")
        return 2
    except DropRefused as e:
        print(f"FAIL  {e}")
        print(f"fix:  {e.fix}")
        print("nothing was written or moved")
        return 1
    except DropLanded as e:
        print(f"FAIL  {e}")
        print(f"fix:  {e.fix}")
        return 1
    root = os.path.dirname(os.path.dirname(result.to))
    to = rel(result.to, root)
    remove, move, write = (("would remove", "would move", "would write") if dry_run
                           else ("removed", "moved", "wrote"))
    for name in result.removed:
        print(f"ok    {remove} {name} from career/store/")
    if not result.removed:
        print("ok    career/store/ holds no graph for it - nothing to remove")
    if result.folder:
        print(f"ok    {move} {result.rel}/ -> {to}/")
    print(f"ok    {write} {to}/{NOTE}")
    if dry_run:
        print("dry run: nothing was written or moved")
    else:
        print(f"dropped {result.rel} - never frozen, so never sent; "
              + (f"its files are in {to}/" if result.folder else f"the note is in {to}/"))
    return 0
