"""`jsk kb dump`: the record out as TriG, the text a load reads back in."""
import sys

from ..presenters import refuse, usage


def cmd_dump(args, flags, root, today):
    """jsk kb dump [--out FILE.trig]

    The whole record - the career, its log, every application's graphs - as TriG, to
    stdout or FILE: a backup, and what `jsk kb load` reads back. jsk writes one after every
    write to .jsk/backup.trig as well. Raising pyoxigraph's version is `dump` with the old
    one, then `load` into a new store with the new one.
    """
    from ....application.record.dump import dump
    from ....infra.oxigraph import db

    if args:
        return usage("jsk kb dump takes no arguments - --out FILE.trig, or stdout")
    out = flags.get("--out")
    if out is not None and not out.endswith(".trig"):
        return usage(f"{out}: a dump is a .trig file")
    try:
        text = dump(root, db=db)
    except db.StoreError as e:
        return refuse([str(e)], e.fix)
    if out is None:
        sys.stdout.write(text)
        return 0
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {out}")
    return 0
