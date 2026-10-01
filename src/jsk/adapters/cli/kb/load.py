"""`jsk kb load` and `jsk kb dump`: the record into an empty store, once
(application/record/load_import.py), and out as TriG, the text a load reads back in."""
import os
import sys

from ..presenters import refuse, unwritten, usage


def cmd_load(args, flags, root, today):
    """jsk kb load <workspace folder | dump.trig>

    Fills this workspace's empty career/store/ - once. From a workspace still laid out as
    files (career/kb.ttl, log.ttl, applications/*/*.ttl): they are read and validated as
    they always were, every number is kept as the store keeps it (`8.40` becomes `8.4`, each
    one listed), and the files are left where they are - jsk stops reading them. Or from a
    `jsk kb dump` (or .jsk/backup.trig): the record as it was dumped.

    Refused when the store already holds a record, when a workspace of files has any FAIL,
    and when the career it would load has one. An application's documents - posting.md and
    the rest - are files beside it, not the record: loaded into another workspace, its
    folder is named so it can be copied across.
    """
    from ....application.record import load_import as L
    from ....application.record.refusals import Failing, Refused
    from ....domain.record.state import RecordError
    from ....domain.record.writer import curies
    from ..compose.record import load
    from ....infra import legacy_import as legacy
    from ....infra.workspace import SHIPPED_VOCABULARY
    from ....infra.oxigraph import db
    from ....infra.oxigraph import record as R
    from .write import refused

    if len(args) != 1:
        return usage("jsk kb load takes one workspace folder or one .trig dump")
    src = os.path.abspath(args[0])
    try:
        L.occupied(root, db=db)
        got = read_import(src, args[0], today, db)
        if isinstance(got, int):
            return got
        record, rewrites = got
        after = L.validated(root, record, load=load, vocabulary=SHIPPED_VOCABULARY)
    except (Failing, Refused) as err:
        return refused(err)
    for name, q, kept in rewrites:
        print(f"number   {name} {curies([q.subject.value])} {curies([q.predicate.value])} "
              f"{q.object.value} kept as {kept.value}")
    try:
        done = L.written(root, record, after, gate=R, load=load, legacy=legacy.has_files)
    except RecordError as e:
        return unwritten(e)
    print(f"loaded   {done.triples} triples in {done.graphs} graphs into "
          f"career/store/, at r{done.revision}")
    if done.legacy_files:
        print("note     career/kb.ttl and the other .ttl files are no longer read - the record "
              "is career/store/; `jsk kb dump` writes it out as text")
    for app in done.missing_apps:
        print(f"note     {app}: its documents (posting.md, gaps.md, resume.json, the files "
              f"sent) are not in this workspace - copy the folder into {root}")
    if done.app_failures:
        print(f"note     {done.app_failures} failures in applications - `jsk kb check` lists them")
    return 0


def read_import(src, given, today, db):
    """(record, rewrites) read from a workspace of files or a dump; the exit code for one
    that is neither, its usage printed. A workspace's WARNs and what a hand edit raised
    are printed as it is read.

    Raises:
        Failing, Refused: as application.record.load_import's readers raise them.
    """
    from ....application.record import load_import as L
    from ....cliutil import show
    from ....domain.record.store import Store
    from ..compose.record import numbers_as_kept
    from ....infra import files
    from ....infra import legacy_import as legacy
    from ....infra.oxigraph import record as R
    from ....infra.oxigraph.codec import parse_text

    if os.path.isdir(src):
        if not legacy.has_files(src):
            return usage(f"{src}: no career/kb.ttl - not a workspace laid out as files")
        got = L.from_files(src, today, legacy=legacy, state=R.state, files=files,
                           parse_text=parse_text)
        if got.warns:
            print(f"{len(got.warns)} WARN in the files, imported as they are:")
            show(Store("", findings=got.warns).report().warns, "WARN", 0)
        for line in got.lines:
            print(line)
        return got.record, got.rewrites
    if src.endswith(".trig") and os.path.isfile(src):
        return L.from_dump(src, db=db, files=files, numbers_as_kept=numbers_as_kept), []
    return usage(f"{given}: not a folder, nor a .trig file")


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
