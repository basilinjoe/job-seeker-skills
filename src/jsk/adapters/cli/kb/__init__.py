"""jsk kb - the career record: changed through changesets, read by id.

Usage: jsk kb <verb> [arguments] [--root DIR]

  new <path> --name "Name" [--force]   scaffold a workspace: career/store/ at r1, and
                                       applications/ (no --root: the path is the workspace)
  apply <changeset.trig> [--dry-run]   merge a changeset into the career; prints the diff
  confirm <id>... --answer "..."       confirm entries with the person's answer, logged;
          <id>... --source F --quote "..."  or with a document's own words;
          --summary <resume.json> --answer "..."  or a resume.json's summary
  show <id>... [--bullets]             entries as Turtle, and the op:base to use;
                                       --bullets, a project's name and bullets only
  view [--section NAME]                the whole career as Markdown, to read
  query <name> [args] [--json]         open | unconfirmed | holds <concept> | stale |
                                       experience <concept> | pipeline |
                                       evidence <term>... | person |
                                       similar <words>... | duplicates |
                                       concepts | bare
  pack capabilities [--out FILE]       the capability starter pack, as a changeset of
                                       what the record lacks; not applied
  merge c:a --into c:b [--out FILE]    two concepts that are one, as a changeset; not applied
  export [--select <id>...]            the short resume.json: the bullets to show, as ids;
         [--from-match <app-dir>]      --from-match chooses them for an application,
         [--ranked] [--cover N]        --ranked with none
         [--today D] [--out FILE [--replace]]
  check                               validate the workspace; exit 1 on a FAIL
  path                                 the workspace, career/store/ and applications/,
                                       as absolute paths
  load <workspace | dump.trig>         fill an empty career/store/, once: from a workspace
                                       still laid out as .ttl files, or from a dump
  dump [--out FILE]                    the whole record as TriG: a backup, and what load reads
  log [--last N]                       the record's history, newest first

--root is the workspace, the folder holding career/; by default the nearest one above
the current directory. `jsk kb <verb> --help` says more about one verb.

The record lives in career/store/ and is read and written only through jsk. Every write
goes through the same gate: it waits its turn behind any other write, the workspace
validates, and the record it would write validates too. Then the career and its log
entry change in one update - both, or neither - and the diff is printed.

Exit 0 done (or nothing to do), 1 refused, 2 called wrong.
"""
import datetime
import inspect
import os
import sys

from ..cliutil import docstring_usage, parse_flags, wants_help
from ....infra.files import find_root
from ..presenters import usage
from . import confirm, draft, export, load, read, write

# The verbs that can write the career: each runs inside its turn (record.turn).
WRITES = {"apply", "confirm", "load"}

# verb -> (its handler, flags taking a value, switches, flags taking a list), beside --root,
# which every verb takes. main parses them, so an unknown flag is refused by name.
TABLE = {
    "apply": (write.cmd_apply, (), ("--dry-run",), ()),
    "pack": (draft.cmd_pack, ("--out",), (), ()),
    "merge": (draft.cmd_merge, ("--out", "--into"), (), ()),
    "confirm": (confirm.cmd_confirm, ("--answer", "--summary", "--source", "--quote"), (), ()),
    "show": (read.cmd_show, (), ("--bullets",), ()),
    "view": (read.cmd_view, ("--section",), (), ()),
    "export": (export.cmd_export, ("--out", "--from-match", "--cover", "--today"),
               ("--ranked", "--replace", "--urs", "--refresh"), ("--select",)),
    "query": (read.cmd_query, (), ("--json",), ("--near",)),
    "check": (read.cmd_check, ("--only",), (), ()),
    "path": (read.cmd_path, (), (), ()),
    "load": (load.cmd_load, (), (), ()),
    "dump": (load.cmd_dump, ("--out",), (), ()),
    "log": (read.cmd_log, ("--last",), (), ()),
}
VERBS = {name: row[0] for name, row in TABLE.items()}
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
        return usage(f"unknown verb: {name} - one of {', '.join(VERBS)}")
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
    if name == "path":
        return read.cmd_path(rest, flags, os.path.abspath(root), today)
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

