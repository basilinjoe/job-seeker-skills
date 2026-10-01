"""The career and its log in step: the revision they share, the states they can be in, and
the stamp and log entry every write adds. Nothing here opens the store; the write gate that
does is infra/oxigraph/record.py."""
import difflib
from dataclasses import dataclass

from .. import ontology as O

KB = "kb"                                        # the graphs, by the names the store uses
LOG = "log"
KB_FILE = "career/kb.ttl"                        # and the files a workspace from before the
LOG_FILE = "career/log.ttl"                      # store holds them in, which the import reads


class RecordError(Exception):
    """A write that could not happen. Says what was and was not changed, and the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


class Written(RecordError):
    """The update landed, and closing the store after it failed: the record holds the
    write, so nothing may be undone as though it had not (freeze's rename back), and
    nobody may be told nothing changed."""


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


def revision_of(term):
    """A revision literal as an int, or None unless it is an xsd:integer. The datatype, not
    only the digits: a store keeps `3.0`^^xsd:decimal as `3`, which int() would accept."""
    dtype = getattr(getattr(term, "datatype", None), "value", O.XSD + "integer")
    return integer(term.value) if dtype == O.XSD + "integer" else None


def header_revision(quads):
    """The career header's j:revision in `quads` as an int, or None when it has none."""
    for q in quads:
        if q.subject.value == O.K + "kb" and q.predicate.value == O.J + "revision":
            return revision_of(q.object)
    return None


def last_entry(quads):
    """(revision, kbSha256) of the log's newest entry, or (None, None). An entry whose
    revision is not an integer is never the newest."""
    entries = {}
    for q in quads:
        if O.class_of(q.subject.value) == "LogEntry":
            name = q.predicate.value[len(O.J):]
            value = q.object.value
            if name == "revision" and revision_of(q.object) is None:
                value = ""
            entries.setdefault(q.subject.value, {})[name] = value
    best = max(((r, e) for e in entries.values()
                if (r := integer(e.get("revision", ""))) is not None),
               key=lambda pair: pair[0], default=None)
    return (best[0], best[1].get("kbSha256")) if best else (None, None)


def stored_state(store):
    """The same, for a record in career/store/: every write puts the career and its log
    entry in one update, so the two agree unless something outside jsk wrote the store.
    Nothing can be hand-edited or torn. The career's hash is not re-checked here - it
    costs a full write of the career on every load; `jsk kb check` asks it (unrecorded)."""
    if KB not in store.parsed:
        return State("missing")
    kb_rev = header_revision(store.parsed[KB].quads)
    log_rev, sha = last_entry(store.parsed[LOG].quads) if LOG in store.parsed else (None, None)
    if kb_rev is not None and kb_rev == log_rev:
        return State("clean", kb_rev, log_rev, sha)
    return State("out-of-sync", kb_rev, log_rev, sha,
                 f"the store's career says r{kb_rev} and its log ends at r{log_rev}: "
                 "something outside jsk wrote career/store/")


def career_sha(kb_quads):
    """The career's hash as every log entry's kbSha256 holds it: sha256 of the career as
    the writer lays it out - the text a write's diff shows."""
    from .parsed import sha256
    from .writer import write

    return sha256(write(kb_quads, "kb"))


def unrecorded(kb_quads, log_quads):
    """None when the career is what its log's newest entry recorded - its kbSha256 is the
    career's hash; else why not. Only jsk writes the store, and every write it makes to
    the career carries that hash, so a mismatch is a write from outside jsk, or a dump
    edited before it was loaded. It costs a full write of the career, so only `jsk kb
    check` and `jsk kb load` ask it."""
    from .writer import WriteError

    rev, sha = last_entry(log_quads)
    if rev is None:
        return "its log has no entry to check it against"
    try:
        actual = career_sha(kb_quads)
    except WriteError as e:
        return f"it cannot be laid out to hash ({e})"
    if sha != actual:
        return f"it is not what its log last recorded at r{rev}"
    return None


def next_revision(st):
    """The revision the next write stamps: one past the higher of the career's and the log's."""
    return max(st.kb_revision or 0, st.log_revision or 0) + 1


def literal(value, dtype):
    """`value` as a literal of xsd:`dtype`."""
    import pyoxigraph as ox
    return ox.Literal(str(value), datatype=ox.NamedNode(O.XSD + dtype))


def stamp(quads, revision, today):
    """The career's triples with its header at `revision`, updated `today`."""
    import pyoxigraph as ox

    kb = ox.NamedNode(O.K + "kb")
    drop = {O.J + "revision", O.J + "updated"}
    out = [q for q in quads if not (q.subject == kb and q.predicate.value in drop)]
    out.append(ox.Quad(kb, ox.NamedNode(O.J + "revision"), literal(revision, "integer")))
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
    lays the career out in - what the diff shows and the entry's kbSha256 hashes."""
    revision: int
    kb_text: str
    kb_quads: list
    log_quads: list

    def graphs(self):
        """{graph name: quads} for the write: the career and its log."""
        return {KB: self.kb_quads, LOG: self.log_quads}


def key(f):
    """A finding's identity across two loads: its rule, graph, focus and detail."""
    return (f.rule, f.file, f.focus, f.detail)


def new_failures(before, after):
    """What a write would break: any FAIL in the career or the vocabulary, and a FAIL
    anywhere that was not already there - an old application's fault is not this one's."""
    from ..naming import is_own

    had = {key(f) for f in before.fails()}
    return [f for f in after.fails() if not is_own(f.file) or key(f) not in had]


def diff(old, new, name="kb"):
    """The unified diff from text `old` to `new`, headed a/`name` and b/`name`."""
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        f"a/{name}", f"b/{name}"))
