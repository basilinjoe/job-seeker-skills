"""The career and its log kept in step: the revision they share, and the one gate every
write goes through.

Every command that writes the career - apply, confirm, new - stamps the career's header
with the next revision and adds the log entry for it, holding what the write touched and
minted, and writes both in one update of career/store/ (write_graphs): both change, or
neither does. So a stored record is clean unless something outside jsk wrote the store.

A workspace still laid out as files, career/kb.ttl and career/log.ttl, is only ever read -
by the one-time import (`jsk kb load`, legacy.py). Two files could not be replaced
atomically together, so for those the states below also tell a hand edit, a torn write and
a restored file apart: the import refuses each of them before it fills a store.
"""
import os

from ...domain.record.state import (KB, KB_FILE, LOG, LOG_FILE, Prepared, State, entry,
                                       header_revision, last_entry, next_revision, stamp,
                                       stored_state)
from ...domain.record.state import RecordError as RecordError
from ...domain.record.state import Written as Written
from ...domain.record.state import integer as integer
from ...domain.record.state import revision_of as revision_of
from ...domain.record.state import career_sha as career_sha
from ...domain.record.state import unrecorded as unrecorded
from ...domain.record.state import literal as literal
from ...domain.record.state import key as key
from ...domain.record.state import new_failures as new_failures
from ...domain.record.state import diff as diff


def state(store):
    """Where the career and its log stand with each other - in the store, or in the files
    the import reads."""
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


def prepared(store, kb_quads, today, by, summary, touched=(), minted=(), answer=None):
    """What a logged write of `kb_quads` would write - the career stamped with the next
    revision, the log with an entry naming what the write touched and minted."""
    from ...domain.record.parsed import sha256
    from ...domain.record.writer import write

    rev = next_revision(state(store))
    kb = stamp(kb_quads, rev, today)
    kb_text = write(kb, "kb")
    log_quads = list(store.graph(LOG)) if LOG in store.parsed else []
    log_quads += entry(rev, today, by, summary, sha256(kb_text), touched, minted, answer)
    return Prepared(rev, kb_text, kb, log_quads)


# --- the store: the one gate every write goes through ---------------------------------------

BACKUP = os.path.join(".jsk", "backup.trig")


def turn(root, dry_run=False):
    """The context a writing command runs in: with a store and not a dry run, this
    process's turn (db.write_turn), taken before the command reads the record - so what it
    validates is what it writes over, and a write that queued behind another applies to
    what that one left. Nothing else writes while it is held, so the command reads the
    store read-only as usual.

    Taken when there is no store yet, too (creating career/ for its lock): `jsk kb new` and
    `jsk kb load` ask whether one exists, then create it, and two of them must not both
    find none. Each asks again inside its turn."""
    import contextlib

    from . import db

    if dry_run:
        return contextlib.nullcontext()
    return db.write_turn(root)


def write_graphs(root, graphs, create=False):
    """Replace `graphs` ({name: triples, or None to drop}) in the store in one update, then
    refresh the backup. Every write to the store comes through here - the only caller of
    db.replace_graphs (tests/test_db.py checks). `create`: the store may not exist yet
    (`jsk kb new`, `jsk kb load`)."""
    from . import db

    failure, landed = None, False
    try:
        with db.writing(root, create=create) as w:
            try:
                w.replace_graphs(graphs)
            except (OSError, RuntimeError) as e:
                failure = RecordError(f"the store refused the write ({e}) - nothing was "
                                      "changed", "`jsk doctor` checks the store; run the "
                                      "command again")
            else:
                landed = True
                backup(root, w)
    except db.StoreError as e:
        # Raised by the open, before any update: nothing changed.
        failure = RecordError(str(e), e.fix)
    except (OSError, RuntimeError) as e:
        # The flush, or giving up access or the turn. After the update, the record holds
        # the write whatever went wrong here; before it (taking the locks), nothing did.
        failure = (Written(f"the write landed, but the store failed after it ({e})",
                           "the career_check tool (jsk mcp) shows the record as it now is; `jsk doctor` "
                           "checks the store") if landed else
                   RecordError(f"the store could not be opened for the write ({e}) - "
                               "nothing was changed",
                               "`jsk doctor` checks the store; run the command again"))
    # Raised out here, not inside the except: an exception raised there keeps the store's
    # error as its context, and that error's traceback holds the frame holding the open
    # store - which pyoxigraph closes only when its last reference goes. Left open, the
    # next reader in this process can find RocksDB mid-compaction.
    if failure is not None:
        raise failure


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
    except Exception:       # noqa: BLE001 - whatever it was, the write it follows stands
        pass
