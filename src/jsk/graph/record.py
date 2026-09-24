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
from dataclasses import dataclass

from . import ontology as O

KB = "career/kb.ttl"
LOG = "career/log.ttl"
SHADOW = os.path.join(".jsk", "kb.last.ttl")     # what the last logged write wrote


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
