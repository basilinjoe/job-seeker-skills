"""career/kb.ttl and career/log.ttl kept in step: the revision and hash they share.

Every command that writes the career - apply, confirm, adopt, fmt - writes kb.ttl, then
log.ttl, then a copy of what it wrote in .jsk/. kb.ttl's header carries the revision it
was written at; log.ttl's last entry carries that revision and kb.ttl's hash. So on any
later load:

- same revision, same hash: clean;
- same revision, another hash: somebody edited kb.ttl by hand - legal, and reported, so
  `jsk kb adopt` can log it and list what it raised;
- kb.ttl one revision ahead: the write was torn - kb.ttl landed and log.ttl did not;
- anything else: one of the two files was restored on its own.

Two files cannot be replaced atomically together. This does not prevent a torn write; it
makes one impossible to miss. Detection, not prevention - the same is true of a hand
edit, and both are said plainly where they are reported.
"""
import os
import time
from dataclasses import dataclass

from . import ontology as O

KB = "kb"                                        # the graphs, by the names the store uses
LOG = "log"
KB_FILE = "career/kb.ttl"                        # and the files a workspace not yet loaded
LOG_FILE = "career/log.ttl"                      # into a store still holds them in
SHADOW = os.path.join(".jsk", "kb.last.ttl")     # what the last logged write wrote
REPLACE_TRIES = 6                                # a Windows lock usually clears in ms


class RecordError(Exception):
    """A write that could not happen. Says what was and was not changed, and the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


@dataclass(frozen=True)
class State:
    kind: str              # clean | unlogged | hand-edited | torn | out-of-sync | unreadable | missing
    kb_revision: int | None = None
    log_revision: int | None = None
    logged_sha: str | None = None
    detail: str = ""


def integer(value):
    """A revision's lexical value as an int, or None when it is not one (`3.0`): tier 1
    FAILs the datatype, so the record reads as though the revision were missing."""
    try:
        return int(value)
    except ValueError:
        return None


def header_revision(quads):
    for q in quads:
        if q.subject.value == O.K + "kb" and q.predicate.value == O.J + "revision":
            return integer(q.object.value)
    return None


def last_entry(quads):
    """(revision, kbSha256) of the log's newest entry, or (None, None). An entry whose
    revision is not an integer is never the newest."""
    entries = {}
    for q in quads:
        if O.class_of(q.subject.value) == "LogEntry":
            entries.setdefault(q.subject.value, {})[q.predicate.value[len(O.J):]] = q.object.value
    best = max(((r, e) for e in entries.values()
                if (r := integer(e.get("revision", ""))) is not None),
               key=lambda pair: pair[0], default=None)
    return (best[0], best[1].get("kbSha256")) if best else (None, None)


def state(store):
    """Where kb.ttl and log.ttl stand with each other."""
    if store.stored:
        return stored_state(store)
    on_disk = {g: os.path.isfile(os.path.join(store.root, f))
               for g, f in ((KB, KB_FILE), (LOG, LOG_FILE))}
    if KB not in store.parsed:
        return State("unreadable" if on_disk[KB] else "missing")
    if LOG not in store.parsed and on_disk[LOG]:
        return State("unreadable")
    kb_rev = header_revision(store.parsed[KB].quads)
    log_rev, sha = last_entry(store.parsed[LOG].quads) if LOG in store.parsed else (None, None)
    if log_rev is None:
        if kb_rev is None:
            return State("unlogged")
        return State("out-of-sync", kb_rev, None, None,
                     f"kb.ttl says r{kb_rev}, and log.ttl has no entries")
    if kb_rev is None:
        return State("out-of-sync", None, log_rev, sha,
                     f"kb.ttl carries no j:revision, and log.ttl ends at r{log_rev}")
    if kb_rev == log_rev:
        kind = "clean" if sha == store.parsed[KB].sha256 else "hand-edited"
        return State(kind, kb_rev, log_rev, sha,
                     "" if kind == "clean" else f"kb.ttl changed outside `jsk kb` since r{log_rev}")
    if kb_rev == log_rev + 1:
        return State("torn", kb_rev, log_rev, sha,
                     f"kb.ttl is at r{kb_rev} and log.ttl ends at r{log_rev}: the last write "
                     f"reached kb.ttl and not log.ttl")
    return State("out-of-sync", kb_rev, log_rev, sha,
                 f"kb.ttl is at r{kb_rev} and log.ttl ends at r{log_rev}: one of them was "
                 f"restored without the other")


def stored_state(store):
    """The same, for a record in career/store/: every write puts the career and its log
    entry in one update, so the two agree unless something outside jsk wrote the store.
    Nothing can be hand-edited or torn; the kb graph's hash is not re-checked."""
    if KB not in store.parsed:
        return State("missing")
    kb_rev = header_revision(store.parsed[KB].quads)
    log_rev, sha = last_entry(store.parsed[LOG].quads) if LOG in store.parsed else (None, None)
    if kb_rev is not None and kb_rev == log_rev:
        return State("clean", kb_rev, log_rev, sha)
    return State("out-of-sync", kb_rev, log_rev, sha,
                 f"the store's career says r{kb_rev} and its log ends at r{log_rev}: "
                 "something outside jsk wrote career/store/")


def next_revision(st):
    return max(st.kb_revision or 0, st.log_revision or 0) + 1


def literal(value, dtype):
    import pyoxigraph as ox
    return ox.Literal(str(value), datatype=ox.NamedNode(O.XSD + dtype))


def stamp(quads, revision, today, content=True):
    """kb.ttl's triples with its header at `revision`. `updated` is the day the last
    change landed, so a reformat moves the revision and leaves the day alone."""
    import pyoxigraph as ox

    kb = ox.NamedNode(O.K + "kb")
    drop = {O.J + "revision"} | ({O.J + "updated"} if content else set())
    out = [q for q in quads if not (q.subject == kb and q.predicate.value in drop)]
    out.append(ox.Quad(kb, ox.NamedNode(O.J + "revision"), literal(revision, "integer")))
    if content:
        out.append(ox.Quad(kb, ox.NamedNode(O.J + "updated"), literal(today.isoformat(), "date")))
    return out


def entry(revision, today, by, summary, sha, touched=(), minted=(), answer=None):
    """One log entry, k:rev_<revision>, as quads."""
    import pyoxigraph as ox

    s = ox.NamedNode(f"{O.K}rev_{revision}")

    def q(p, o):
        return ox.Quad(s, ox.NamedNode(O.J + p), o)
    out = [q("revision", literal(revision, "integer")), q("date", literal(today.isoformat(), "date")),
           q("by", ox.NamedNode(O.J + by)), q("summary", ox.Literal(summary)),
           q("kbSha256", ox.Literal(sha))]
    out += [q("touched", ox.NamedNode(i)) for i in sorted(set(touched))]
    out += [q("minted", ox.NamedNode(i)) for i in sorted(set(minted))]
    if answer is not None:
        out.append(q("answer", ox.Literal(answer)))
    return out


@dataclass(frozen=True)
class Prepared:
    """A logged write, ready: the revision, both graphs as quads, and the text the writer
    lays the career out in - what the diff shows and kbSha256 hashes."""
    revision: int
    kb_text: str
    log_text: str
    kb_quads: list
    log_quads: list

    def graphs(self):
        return {KB: self.kb_quads, LOG: self.log_quads}


def prepared(store, kb_quads, today, by, summary, touched=(), minted=(), answer=None,
             content=True):
    """What a logged write of `kb_quads` would write - the career stamped with the next
    revision, the log with an entry holding the career's hash."""
    from .io import sha256
    from .writer import write

    rev = next_revision(state(store))
    kb = stamp(kb_quads, rev, today, content)
    kb_text = write(kb, "kb")
    log_quads = list(store.graph(LOG)) if LOG in store.parsed else []
    log_quads += entry(rev, today, by, summary, sha256(kb_text), touched, minted, answer)
    return Prepared(rev, kb_text, write(log_quads, "log"), kb, log_quads)


def prepare(store, kb_quads, today, by, summary, touched=(), minted=(), answer=None,
            content=True):
    """(revision, kb_text, log_text): prepared(), as the file layout writes it."""
    p = prepared(store, kb_quads, today, by, summary, touched, minted, answer, content)
    return p.revision, p.kb_text, p.log_text


# --- the store: the one gate every write goes through ---------------------------------------

BACKUP = os.path.join(".jsk", "backup.trig")


def turn(root, dry_run=False):
    """The context a writing command runs in: with a store and not a dry run, this
    process's turn (db.write_turn), taken before the command reads the record - so what it
    validates is what it writes over, and a write that queued behind another applies to
    what that one left. Nothing else writes while it is held, so the command reads the
    store read-only as usual."""
    import contextlib

    from . import db

    if dry_run or not db.exists(root):
        return contextlib.nullcontext()
    return db.write_turn(root)


def write_graphs(root, graphs, create=False):
    """Replace `graphs` ({name: triples, or None to drop}) in the store in one update, then
    refresh the backup. Every write to the store comes through here - the only caller of
    db.replace_graphs (tests/test_db.py checks). `create`: the store may not exist yet
    (`jsk new`, `jsk kb load`)."""
    from . import db

    try:
        with db.writing(root, create=create) as w:
            w.replace_graphs(graphs)
            backup(root, w)
    except db.StoreError as e:
        raise RecordError(str(e), e.fix) from None
    except (OSError, RuntimeError) as e:
        raise RecordError(f"the store refused the write ({e}) - nothing was changed",
                          "`jsk doctor` checks the store; run the command again") from None


def backup(root, writer):
    """The whole record as TriG in .jsk/backup.trig, after every write: the store's format
    is tied to the pyoxigraph version, and this survives a pin bump or a store that will not
    open (`jsk kb load .jsk/backup.trig`). Best effort - the write already happened."""
    from . import db

    folder = os.path.join(root, ".jsk")
    try:
        text = db.dump_text(writer.graphs())
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, ".gitignore"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("*\n")
        tmp = os.path.join(root, BACKUP + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, os.path.join(root, BACKUP))
    except OSError:
        pass


def replace(src, dst, tries=REPLACE_TRIES, wait=0.05):
    """os.replace, retried: on Windows an editor, a sync client or a virus scanner holding
    the file makes it fail for a moment, and a moment later it succeeds."""
    for n in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if n == tries - 1:
                raise RecordError(f"{os.path.basename(dst)} is locked by another program - an "
                                  f"editor, a sync client or a virus scanner",
                                  "close it and run the command again") from None
            time.sleep(wait * (n + 1))


def staged(path, text):
    """`text` written beside `path` as path.tmp, flushed to disk: replacing is then the
    only step left, and it is the one step the filesystem makes atomic."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    return tmp


def commit(root, kb_text, log_text):
    """Write kb.ttl, then log.ttl, then the shadow copy. Both files are staged before
    either is replaced, so the window a crash can tear is two renames wide."""
    kb, log = os.path.join(root, KB_FILE), os.path.join(root, LOG_FILE)
    tmps = [staged(kb, kb_text), staged(log, log_text)]
    try:
        try:
            replace(tmps[0], kb)
        except RecordError as e:
            raise RecordError(f"{e} - nothing was changed", e.fix) from None
        try:
            replace(tmps[1], log)
        except RecordError as e:
            raise RecordError(f"{e} - kb.ttl was written and log.ttl was not",
                              "close it, then run `jsk kb adopt`: it logs the write") from None
    finally:
        for tmp in tmps:
            if os.path.exists(tmp):
                os.remove(tmp)
    write_shadow(root, kb_text)


def write_shadow(root, text):
    """A copy of what was logged, so `jsk kb adopt` can say what a later hand edit
    changed. Kept in .jsk/, which ignores itself: it is a cache, never a second record.
    Best effort - without it adopt still works, and says it had nothing to compare."""
    folder = os.path.join(root, ".jsk")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, ".gitignore"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("*\n")
        with open(os.path.join(root, SHADOW), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except OSError:
        pass


def shadow(root, sha):
    """The text the last logged write wrote, or None when the copy is missing or is not
    the revision the log says it is."""
    from .io import Unreadable, read_text, sha256

    try:
        text = read_text(os.path.join(root, SHADOW), "the shadow copy")
    except Unreadable:
        return None
    return text if sha and sha256(text) == sha else None
