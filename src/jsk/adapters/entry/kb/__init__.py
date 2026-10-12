"""jsk kb - the career record: scaffolded, loaded and dumped from the command line; checked,
drafted, read and changed through the career_* tools (jsk mcp).

Usage: jsk kb <verb> [arguments] [--root DIR]

  new <path> --name "Name" [--force]   scaffold a workspace: career/store/ at r1, and
                                       applications/ (no --root: the path is the workspace)
  load <workspace | dump.trig>         fill an empty career/store/, once: from a workspace
                                       still laid out as .ttl files, or from a dump
  dump [--out FILE]                    the whole record as TriG: a backup, and what load reads

Checking the record, and drafting a starter pack or a merge as a changeset, are the career_check,
career_pack and career_merge tools of `jsk mcp`. This adapter still has the verbs - the tools
call them through dispatch.call_gate - but `jsk kb check|pack|merge` went on 2026-10-04
(docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 4): adapters/cli/main.py refuses them
before they get here, exit 2 naming the tool.

--root is the workspace, the folder holding career/; by default the nearest one above
the current directory. `jsk kb <verb> --help` says more about one verb.

The record lives in career/store/ and is read and written only through jsk. A changeset is
merged by the career_apply tool (career_preview shows its diff first), an entry confirmed by
career_confirm, and the record read by career_show, career_view, career_query and career_log;
`jsk kb apply|confirm|show|view|query|log|export|path` were retired in 6.0 and exit 2 naming
them (adapters/cli/main.py's RETIRED). Every write goes through the same gate: it waits its
turn behind any other write, the workspace validates, and the record it would write
validates too. Then the career and its log entry change in one update - both, or neither.

Exit 0 done (or nothing to do), 1 refused, 2 called wrong.
"""
import datetime
import inspect
import os
import sys

from ..cliutil import docstring_usage, parse_flags, wants_help
from ....infra.files import find_root
from ..presenters import usage
from . import draft, load, read

# The verbs that can write the career: each runs inside its turn (record.turn). Only the import
# is left: 6.0 moved every other write to the career_* tools.
WRITES = {"load"}

# verb -> (its handler, flags taking a value, switches, flags taking a list), beside --root,
# which every verb takes. main parses them, so an unknown flag is refused by name.
TABLE = {
    "pack": (draft.cmd_pack, ("--out",), (), ()),
    "merge": (draft.cmd_merge, ("--out", "--into"), (), ()),
    "check": (read.cmd_check, ("--only",), (), ()),
    "load": (load.cmd_load, (), (), ()),
    "dump": (load.cmd_dump, ("--out",), (), ()),
}
VERBS = {name: row[0] for name, row in TABLE.items()}

# The verbs a person can run from a shell. VERBS also holds check, pack and merge, because the
# career_check, career_pack and career_merge tools call them through dispatch.call_gate, but
# adapters/cli/main.py refuses those three at the shell (2026-10-04, the review of the
# MCP-first change: an unknown verb offered them, and the next try exited 2 again).
SHELL_VERBS = ("new", "load", "dump")
FLAGS = {name: row[1:] for name, row in TABLE.items()}


def main(argv=None):
    """`jsk kb`: find the workspace, parse the verb's flags, and run it inside its turn.

    Args:
        argv: the arguments after `kb`; by default sys.argv's.

    Returns:
        The verb's exit code; 2 for a call made wrongly, 0 for --help. Reads the clock once
        and hands the date to the verb.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (wants_help(args) and args[0] not in VERBS):
        print(docstring_usage(__doc__))
        return 0 if args else 2
    name, rest = args[0], args[1:]
    if name not in VERBS:
        return usage(f"unknown verb: {name} - one of {', '.join(SHELL_VERBS)} "
                     "(check, pack and merge are the career_check, career_pack and "
                     "career_merge tools of `jsk mcp`)")
    if wants_help(rest):
        print(inspect.cleandoc(VERBS[name].__doc__))
        return 0
    values, switches, lists = FLAGS[name]
    # A lone `-` is apply's to refuse (stdin is refused there), not an unknown flag.
    parsed, problem = parse_flags(rest, (*values, "--root"), switches, lists=lists,
                                  dash=True)
    if parsed is None:
        return usage(problem)
    rest, flags = parsed
    root = flags.pop("--root", None) or find_root(os.getcwd())
    today = datetime.date.today()
    if root is None or not os.path.isdir(root):
        return usage("no workspace here: run it inside one, or pass --root DIR "
                     "(the folder holding career/)")
    if name != "load":
        # `load` is the import itself; every other verb would answer from, or write to, a
        # record jsk no longer keeps.
        from ....application.guards import unloaded_refusal
        from ..cliutil import refused
        refusal = unloaded_refusal(os.path.abspath(root))
        if refusal:
            return refused(refusal)
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk kb needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ....infra.oxigraph import record as R

    root = os.path.abspath(root)
    # A verb that writes the store takes its turn before it reads it (record.turn).
    with R.turn(root, dry_run=name not in WRITES or "--dry-run" in flags):
        return VERBS[name](rest, flags, root, today)

