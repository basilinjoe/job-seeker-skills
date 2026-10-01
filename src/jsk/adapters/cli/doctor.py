"""`jsk doctor`: the preflight, verifying end to end unless told otherwise, then the record's store.

Nothing here imports pyoxigraph until the store is asked about, so `python -m jsk doctor`
runs on a machine without it and says so.
"""
import os

from ...application.guards import unloaded_refusal
from .cliutil import wants_help
from .dispatch import run_in_process


def cmd_doctor(args):
    """`jsk doctor`: preflight.main, with --verify unless --quick, then store_report.

    Args:
        args: the arguments after `doctor`.

    Returns:
        The exit code: the preflight's, or 1 when the store is broken. Prints both reports.
    """
    if "--quick" in args:
        args = [a for a in args if a != "--quick"]
    elif "--verify" not in args:
        args = list(args) + ["--verify"]
    code = run_in_process("preflight.py", args)
    if wants_help(args) or "--json" in args:
        return code
    kb = args[args.index("--kb") + 1] if "--kb" in args[:-1] else None
    lines, broken = store_report(kb)
    print("\nThe record:")
    print("\n".join(lines))
    return max(code, 1 if broken else 0)


def store_report(start=None):
    """(lines, broken) saying where the record's store stands: there, readable, its
    revision, and whether .jsk/backup.trig - the dump every write refreshes, and what
    `jsk kb load` restores from - is there, at which revision.

    Args:
        start: a workspace, a path inside one, or its career/store/; by default the
            current directory.

    Returns:
        (the lines, whether the store is broken). Opens the store read-only and reads the
        backup.
    """
    from ...infra.files import find_root
    from ...infra.oxigraph import db
    from ...infra.oxigraph import record as R

    here = start or os.getcwd()
    if os.path.isfile(here):
        here = os.path.dirname(os.path.abspath(here))
    root = find_root(here)
    if root is None:
        return [f"  gap   no workspace at or above {here}",
                "           `jsk kb new PATH --name NAME` starts one"], False
    refusal = unloaded_refusal(root)
    if refusal:
        return [f"  FAIL  {refusal[0]}", f"           {refusal[1]}"], True
    try:
        graphs = db.read(root)
    except db.StoreError as e:
        return [f"  FAIL  {db.path(root)}: {e}", f"           {e.fix}"], True
    revision = R.header_revision(graphs.get(R.KB, []))
    lines = [f"  ok    store    {db.path(root)}",
             f"           readable, at r{revision}" if revision is not None
             else "           readable, and it holds no career revision"]
    backup = os.path.join(root, R.BACKUP)
    if not os.path.isfile(backup):
        lines += ["  gap   backup   no .jsk/backup.trig yet",
                  "           the next write refreshes it; `jsk kb dump` writes one now"]
        return lines, False
    try:
        from ...infra.files import read_text
        at = R.header_revision(db.parse_dump(read_text(backup, R.BACKUP)).get(R.KB, []))
    except Exception as e:                   # noqa: BLE001 - reported, never a crash
        lines += [f"  gap   backup   {backup} does not read back: {e}"]
        return lines, False
    lines.append(f"  ok    backup   {backup}")
    lines.append(f"           at r{at}" + ("" if at == revision else
                                          f" - one write behind the store's r{revision}; the "
                                          "next write refreshes it"))
    return lines, False
