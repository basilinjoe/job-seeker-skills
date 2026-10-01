"""`jsk kb load`: an empty career/store/ filled once - from a workspace still laid out as
.ttl files, or from a dump.

Four steps, because the command says what each found before the next can refuse: what is
imported is read (`from_files`, `from_dump`), the record it would make validated
(`validated`), then written (`written`). What reads the files, the store and the dump is
the caller's to give.
"""
import os
from dataclasses import dataclass

from ...domain.record.state import KB, LOG
from .refusals import Failing, Refused

SHADOW = os.path.join(".jsk", "kb.last.ttl")      # the file workspace's copy of its last write


def occupied(root, *, db):
    """Refuse a store that already holds a record.

    Args:
        root: the workspace loaded into.
        db: the store on disk (infra.oxigraph.db): exists, read, STORE_DIR.

    Raises:
        Refused: career/store/ holds a record.
    """
    if db.exists(root) and any(db.read(root).values()):
        raise Refused([f"{os.path.join(root, db.STORE_DIR)} already holds a record"],
                      "load into a new workspace (`jsk kb new` elsewhere is not needed - an "
                      "empty folder with --root will do)")


def hand_edit(before, src, *, state, files, parse_text):
    """(lines naming what a hand edit of kb.ttl raised, the ids it changed - every id in
    the career when there is nothing to compare against). A provenance raised by hand
    renders as confirmed with no answer behind it, and after the import no text is left
    to show it was: so each one is named now, against the shadow copy of the revision the
    log last recorded when there is one.

    Args:
        before: the files' record, as the file loader validated it.
        src: the workspace imported from.
        state: where the career and its log stand (infra.oxigraph.record.state).
        files: reads the shadow copy (infra.files.read_text).
        parse_text: parses Turtle (infra.oxigraph.codec.parse_text).

    Returns:
        The pair. Reads the shadow copy.
    """
    from ...domain.record.parsed import Unreadable, sha256
    from ...domain.record.provenance import upgrades

    st = state(before)
    after = before.graph(KB)
    try:
        old = files.read_text(os.path.join(src, SHADOW), "the shadow copy")
    except Unreadable:
        old = None
    if old is None or sha256(old) != st.logged_sha:
        return ([f"note     kb.ttl was edited by hand after r{st.log_revision}, and there is "
                 f"nothing to compare it against ({SHADOW} is not r{st.log_revision}): a "
                 "provenance the edit raised to confirmed cannot be named - check the "
                 "confirmed entries with the person"],
                {q.subject.value for q in after})
    was = parse_text(old, KB).quads
    raised = upgrades(was, after)
    lines = [f"raised   {line}" for line in raised]
    if raised:
        lines.append("         check each with the person; `jsk kb confirm <id> --answer` "
                     "records it")
    return lines, {q.subject.value for q in set(was) ^ set(after)}


@dataclass(frozen=True)
class Imported:
    """A workspace of files read for the import: the record to load, the numbers kept in
    the store's form, the files' WARN findings, and what a hand edit raised."""

    record: dict
    rewrites: list
    warns: list
    lines: list


def from_files(src, today, *, legacy, state, files, parse_text):
    """The record a workspace laid out as files imports as, with the import's log entry.

    The career is stamped at the next revision, and the log gains an entry `by load`
    holding its hash - so the store's newest entry hashes its career, as every jsk write
    leaves it, and a dump of it loads back.

    Args:
        src: the workspace imported from, which has career/kb.ttl.
        today: the day the entry is dated.
        legacy: reads the files (infra.legacy_import.read_workspace).
        state: where the career and its log stand (infra.oxigraph.record.state).
        files, parse_text: as hand_edit takes them.

    Returns:
        Imported. Reads the files.

    Raises:
        Failing: the files have FAILs.
    """
    import pyoxigraph as ox

    from ...domain.record.state import career_sha, entry, next_revision, stamp

    before, record, rewrites = legacy.read_workspace(src)
    if before.fails():
        raise Failing(before.fails(), f"REFUSED  {src} has {len(before.fails())} failures "
                                      "- fix them in the files first:")
    touched = {q.subject.value for name, q, _ in rewrites if name == KB}
    lines = []
    if state(before).kind == "hand-edited":
        lines, changed = hand_edit(before, src, state=state, files=files, parse_text=parse_text)
        touched |= changed
    rev = next_revision(state(before))
    kb = stamp([ox.Quad(t.subject, t.predicate, t.object) for t in record[KB]], rev, today)
    summary = (f"Imported from the files by jsk kb load: {len(record)} graphs, "
               f"{len(rewrites)} numbers kept by value.")
    log = [ox.Quad(t.subject, t.predicate, t.object) for t in record.get(LOG, [])]
    log += entry(rev, today, "load", summary, career_sha(kb), touched)
    return Imported({**record, KB: kb, LOG: log}, rewrites, before.warns(), lines)


def edited_dump(record, name, *, numbers_as_kept):
    """Refuse a dump changed outside jsk. A number in a spelling the store would rewrite,
    or a career whose hash is not what its log's newest entry recorded, is a dump changed
    outside jsk: loaded, the change would enter the record unlogged - a provenance raised
    by hand renders as confirmed.

    Args:
        record: {graph name: triples}, as the dump parsed.
        name: the dump's file name.
        numbers_as_kept: refuses a number the store would rewrite
            (graph.changeset.numbers_as_kept).

    Raises:
        Refused: it was changed outside jsk.
    """
    import pyoxigraph as ox

    from ...domain.record.state import unrecorded

    fix = ("load the dump as `jsk kb dump` wrote it (or .jsk/backup.trig), then change the "
           "record through `jsk kb apply`")
    found = []
    for graph, triples in sorted(record.items()):
        numbers_as_kept([ox.Quad(t.subject, t.predicate, t.object) for t in triples],
                        lambda focus, detail, _fix, g=graph: found.append(f"{g} {focus} {detail}"))
    if found:
        raise Refused([f"{name}: {line}" for line in found] + ["the dump was changed outside jsk"],
                      fix)
    if KB in record:
        kb = [ox.Quad(t.subject, t.predicate, t.object) for t in record[KB]]
        why = unrecorded(kb, record.get(LOG, []))
        if why:
            raise Refused([f"{name}: the career in it - {why} - was changed outside jsk"], fix)


def from_dump(src, *, db, files, numbers_as_kept):
    """The record a `jsk kb dump` (or .jsk/backup.trig) holds, checked as jsk wrote it.

    Args:
        src: the .trig file.
        db: parses a dump (infra.oxigraph.db.parse_dump, StoreError).
        files: reads it (infra.files.read_text).
        numbers_as_kept: as edited_dump takes it.

    Returns:
        {graph name: triples}. Reads the file.

    Raises:
        Refused: it will not read or parse, or it was changed outside jsk.
    """
    from ...domain.record.parsed import Unreadable

    name = os.path.basename(src)
    try:
        record = db.parse_dump(files.read_text(src, name))
    except (Unreadable, db.StoreError) as e:
        raise Refused([str(e)], e.fix) from None
    except SyntaxError as e:
        raise Refused([f"{name}:{e.lineno}: {e.msg}"],
                      "a dump is TriG as `jsk kb dump` writes it") from None
    edited_dump(record, name, numbers_as_kept=numbers_as_kept)
    return record


def validated(root, record, *, load, vocabulary):
    """The record as it would load, validated as for any write.

    As for any write: the career must validate, and an application's fault does not stop
    it. An application's rules read the documents beside it (posting.md), so one loaded
    into another workspace fails them until its folder is copied across.

    Args:
        root: the workspace loaded into.
        record: {graph name: triples}.
        load: loads a workspace (graph.store.load).
        vocabulary: the shipped vocabulary's file.

    Returns:
        The store it loads as.

    Raises:
        Failing: the career would load with FAILs.
    """
    after = load(root, files=[vocabulary], graphs=record)
    blocking = [f for f in after.fails()
                if not f.file.startswith("applications/") or f.rule == "syntax"]
    if blocking:
        raise Failing(blocking, f"REFUSED  the record would load with {len(blocking)} failures:")
    return after


@dataclass(frozen=True)
class Loaded:
    """A record loaded into career/store/: its size, its revision, and what is left to do."""

    triples: int
    graphs: int
    revision: int | None
    legacy_files: bool          # career/kb.ttl is still there, and no longer read
    missing_apps: tuple         # applications whose documents are not in this workspace
    app_failures: int           # FAILs in applications, which do not stop the load


def written(root, record, after, *, gate, load, legacy):
    """Write the record into the empty store.

    Args:
        root: the workspace loaded into.
        record: {graph name: triples}.
        after: the store it validated as.
        gate: the write gate (infra.oxigraph.record): write_graphs, state.
        load: loads a workspace (graph.store.load).
        legacy: whether a workspace is laid out as files (infra.legacy_import.has_files).

    Returns:
        Loaded. Writes career/store/ and its backup.

    Raises:
        RecordError: the store refused the write.
    """
    gate.write_graphs(root, record, create=True)
    st = gate.state(load(root))
    apps = sorted({n.rsplit("/", 1)[0] for n in record if n.startswith("applications/")})
    return Loaded(sum(map(len, record.values())), len(record), st.kb_revision, legacy(root),
                  tuple(a for a in apps if not os.path.isdir(os.path.join(root, a))),
                  sum(f.file.startswith("applications/") for f in after.fails()))
