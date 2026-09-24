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

KB = "career/kb.ttl"
LOG = "career/log.ttl"
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
    kb_revision: int = None
    log_revision: int = None
    logged_sha: str = None
    detail: str = ""


def header_revision(quads):
    for q in quads:
        if q.subject.value == O.K + "kb" and q.predicate.value == O.J + "revision":
            return int(q.object.value)
    return None


def last_entry(quads):
    """(revision, kbSha256) of the log's newest entry, or (None, None)."""
    entries = {}
    for q in quads:
        if O.class_of(q.subject.value) == "LogEntry":
            entries.setdefault(q.subject.value, {})[q.predicate.value[len(O.J):]] = q.object.value
    best = max((e for e in entries.values() if "revision" in e),
               key=lambda e: int(e["revision"]), default=None)
    return (int(best["revision"]), best.get("kbSha256")) if best else (None, None)


def state(store):
    """Where kb.ttl and log.ttl stand with each other."""
    on_disk = {f: os.path.isfile(os.path.join(store.root, f)) for f in (KB, LOG)}
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


def prepare(store, kb_quads, today, by, summary, touched=(), minted=(), answer=None,
            content=True):
    """(revision, kb_text, log_text): what a logged write of `kb_quads` would write -
    kb.ttl stamped with the next revision, log.ttl with an entry holding its hash."""
    from .io import sha256
    from .writer import write

    rev = next_revision(state(store))
    kb_text = write(stamp(kb_quads, rev, today, content), "kb")
    log_quads = list(store.graph(LOG)) if LOG in store.parsed else []
    log_quads += entry(rev, today, by, summary, sha256(kb_text), touched, minted, answer)
    return rev, kb_text, write(log_quads, "log")


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
    kb, log = os.path.join(root, KB), os.path.join(root, LOG)
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
    from .io import normalise, sha256

    try:
        with open(os.path.join(root, SHADOW), encoding="utf-8") as fh:
            text = normalise(fh.read())
    except (OSError, UnicodeDecodeError):
        return None
    return text if sha and sha256(text) == sha else None
