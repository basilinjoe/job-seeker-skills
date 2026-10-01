"""The record on disk: one Oxigraph store (RocksDB) per workspace, at career/store/.

This is the only module that knows the record is RocksDB. Every record is a named graph -
`kb`, `log`, `applications/<stem>/posting`, `.../application`, `.../gaps` - and nothing
else opens the store on disk or updates it (tests/test_db.py fails if anything does).

Two OS locks, both blocking, both released with the file handle when a process dies:

- the turn (career/store.lock): writers queue for it in the order they arrive, instead of
  being turned away. A writing command holds it from before it reads the record until it
  has written, so what it validates is what it writes over.
- access (career/store.access): a reader holds it shared while it opens, reads and closes
  the store; a writer holds it exclusively while it opens, updates and closes it. pyoxigraph
  says a read-only open while another process writes is undefined behaviour - and it is: a
  read racing a writer's compaction sees RocksDB delete a table under it. So a reader waits
  for at most one write's open-update-close, never for a writing command's whole run.

pyoxigraph is imported inside the functions that need it, never at module top.
"""
import os
import sys
import time
from contextlib import contextmanager

from ...domain.naming import GRAPH, graph_iri, name_of

STORE_DIR = os.path.join("career", "store")
LOCK_FILE = os.path.join("career", "store.lock")        # the writers' turn
ACCESS_FILE = os.path.join("career", "store.access")    # readers shared, a writer alone
# RocksDB's own LOCK, held by something outside jsk's turn (a stray pyoxigraph session):
# retried this long before it is reported. Inside a turn no jsk process holds it.
LOCK_WAIT = 5.0


class StoreError(Exception):
    """The store could not be opened or written. Carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


class NoStore(StoreError):
    """No career/store/ in this workspace."""


class Busy(StoreError):
    """RocksDB's lock is held by a process outside jsk's turn."""


def path(root):
    return os.path.join(root, STORE_DIR)


def exists(root):
    return os.path.isdir(path(root))


def graph_node(name):
    import pyoxigraph as ox
    return ox.NamedNode(graph_iri(name))


def open_reader(root):
    """The store, read-only. Raises NoStore when there is none. Callers hold shared access
    (read() does); a bare open while another process writes is undefined behaviour."""
    import pyoxigraph as ox

    if not exists(root):
        raise NoStore(f"no career/store/ in {root}",
                      "run `jsk kb new`, or `jsk kb load` to import a workspace or a dump")
    try:
        return ox.Store.read_only(path(root))
    except (OSError, RuntimeError) as e:
        # RuntimeError: RocksDB's "Corruption: ..." (a damaged CURRENT or table file)
        # comes out of pyoxigraph as one, not as an OSError.
        raise StoreError(f"career/store/ could not be opened: {e}",
                         "`jsk doctor` checks it; `jsk kb load` restores .jsk/backup.trig") from None


def is_lock_error(e):
    text = str(e).lower()
    return "lock" in text and ("resource temporarily unavailable" in text
                               or "being used by another process" in text
                               or "lock file" in text or "lock hold" in text)


def open_writer(root, wait=LOCK_WAIT, create=False):
    """The store, for writing. Callers hold their turn and exclusive access (writing()
    does)."""
    import pyoxigraph as ox

    if not create and not exists(root):
        raise NoStore(f"no career/store/ in {root}",
                      "run `jsk kb new`, or `jsk kb load` to import a workspace or a dump")
    deadline = time.monotonic() + wait
    delay = 0.05
    while True:
        try:
            return ox.Store(path(root))
        except RuntimeError as e:
            raise StoreError(f"career/store/ could not be opened for writing: {e}",
                             "`jsk doctor` checks the store; `jsk kb load` restores "
                             ".jsk/backup.trig into an empty workspace") from None
        except OSError as e:
            if not is_lock_error(e):
                raise StoreError(f"career/store/ could not be opened for writing: {e}",
                                 "check the folder is writable; `jsk doctor` checks the store") \
                    from None
            if time.monotonic() >= deadline:
                raise Busy("career/store/ is held open by a process outside jsk",
                           "close it (another Python session using pyoxigraph?) and run the "
                           "command again") from None
            time.sleep(delay)
            delay = min(delay * 2, 0.5)


# --- the turn: a blocking, cross-process lock ----------------------------------------------

_LOCKER = []


def _locker():
    """(lock(fh, wait, shared=False) -> bool, unlock(fh)) for this OS - built on first use,
    so a command that never touches the store never imports ctypes."""
    if _LOCKER:
        return _LOCKER[0]
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        class OVERLAPPED(ctypes.Structure):
            _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                        ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                        ("hEvent", wintypes.HANDLE)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(OVERLAPPED)]
        k32.UnlockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.DWORD, ctypes.POINTER(OVERLAPPED)]
        exclusive, nowait = 0x2, 0x1

        def lock(fh, wait, shared=False):
            flags = (0 if shared else exclusive) | (0 if wait else nowait)
            if k32.LockFileEx(msvcrt.get_osfhandle(fh.fileno()), flags, 0, 1, 0,
                              ctypes.byref(OVERLAPPED())):
                return True
            if not wait:
                return False
            raise ctypes.WinError(ctypes.get_last_error())

        def unlock(fh):
            k32.UnlockFileEx(msvcrt.get_osfhandle(fh.fileno()), 0, 1, 0,
                             ctypes.byref(OVERLAPPED()))
    else:
        import fcntl

        def lock(fh, wait, shared=False):
            try:
                fcntl.flock(fh.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
                            | (0 if wait else fcntl.LOCK_NB))
                return True
            except BlockingIOError:
                return False

        def unlock(fh):
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    _LOCKER.append((lock, unlock))
    return _LOCKER[0]


# Roots whose turn this process holds, and how deep: a command takes its turn around all
# of its work, and the commit inside it takes it again without waiting on itself.
_HELD = {}


def holds_turn(root):
    return _HELD.get(os.path.normcase(os.path.abspath(root)), 0) > 0


@contextmanager
def write_turn(root, say=None):
    """Block until it is this process's turn to write the workspace; re-entrant. `say` is
    told once when the turn is not free at once (default: stderr).

    A command that writes takes its turn before it reads the record, so a write that
    queued behind another reads - and validates, and applies to - what that one left."""
    key = os.path.normcase(os.path.abspath(root))
    if _HELD.get(key):
        _HELD[key] += 1
        try:
            yield
        finally:
            _HELD[key] -= 1
        return
    lock_, unlock = _locker()
    lock = os.path.join(root, LOCK_FILE)
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "a+b") as fh:
        if not lock_(fh, wait=False):
            (say or (lambda m: print(m, file=sys.stderr, flush=True)))(
                f"waiting for another jsk write to finish ({lock})")
            lock_(fh, wait=True)
        _HELD[key] = 1
        try:
            yield
        finally:
            _HELD.pop(key, None)
            unlock(fh)


class Writer:
    """The store open for writing, inside a turn. pyoxigraph closes a store when its last
    reference goes, and has no close(): so callers get this, never the store, and leaving
    `writing` drops the one reference - the store is closed before the turn is given up,
    whatever the caller's variable still holds."""

    def __init__(self, db):
        self._db = db

    def graphs(self):
        return graphs(self._db)

    def replace_graphs(self, new):
        replace_graphs(self._db, new)

    def close(self):
        """Flush and drop the store - dropped even when the flush fails, or the caller's
        reference would keep RocksDB's lock past the turn."""
        if self._db is not None:
            try:
                self._db.flush()
            finally:
                self._db = None


# Roots whose store this process has open for writing: a read there would wait on its own
# exclusive access for ever, so it is refused as the bug it would be.
_WRITING = set()


@contextmanager
def access(root, shared):
    """Hold access to the store: shared to read it, exclusive to write it."""
    key = os.path.normcase(os.path.abspath(root))
    if key in _WRITING:
        raise RuntimeError("the store was read while this process had it open for writing "
                           "- a jsk bug; read through the Writer")
    lock_, unlock = _locker()
    lock = os.path.join(root, ACCESS_FILE)
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "a+b") as fh:
        lock_(fh, wait=True, shared=shared)
        try:
            yield
        finally:
            unlock(fh)


@contextmanager
def writing(root, create=False):
    """The turn, then exclusive access and the store open for writing; the store is closed,
    and access given up, before the turn is."""
    key = os.path.normcase(os.path.abspath(root))
    with write_turn(root), access(root, shared=False):
        w = Writer(open_writer(root, create=create))
        _WRITING.add(key)
        try:
            yield w
        finally:
            _WRITING.discard(key)
            w.close()


# --- graphs in, graphs out ------------------------------------------------------------------

def graphs(db):
    """{name: [Triple]} for every record graph in `db`."""
    import pyoxigraph as ox

    out = {}
    for q in db.quads_for_pattern(None, None, None, None):
        name = name_of(q.graph_name)
        if name is not None:
            out.setdefault(name, []).append(ox.Triple(q.subject, q.predicate, q.object))
    return out


def read(root):
    """{name: [Triple]} of the workspace's store, read-only, under shared access."""
    if not exists(root):
        open_reader(root)                     # raises NoStore, and takes no lock for it
    with access(root, shared=True):
        db = open_reader(root)
        try:
            return graphs(db)
        finally:
            del db


def update_text(new):
    """The one SPARQL update replacing each graph in `new` ({name: triples, or None to
    drop it}). Terms print as N-Triples, which SPARQL reads as they are."""
    ops = []
    for name, triples in new.items():
        g = graph_iri(name)
        ops.append(f"DROP SILENT GRAPH <{g}>")
        if triples:
            body = " .\n".join(f"{t.subject} {t.predicate} {t.object}" for t in triples)
            ops.append(f"INSERT DATA {{ GRAPH <{g}> {{\n{body} .\n}} }}")
    return " ;\n".join(ops)


def replace_graphs(db, new):
    """Replace every graph in `new` in one update: all of them change, or none does.
    Only record.py calls this (tests/test_db.py checks)."""
    if new:
        db.update(update_text(new))


# --- dump and load --------------------------------------------------------------------------

def dump_text(record):
    """{name: triples} as TriG, graphs in name order and triples sorted: the same record
    always dumps to the same text."""
    import pyoxigraph as ox

    quads = []
    for name in sorted(record):
        g = graph_node(name)
        quads += sorted((ox.Quad(t.subject, t.predicate, t.object, g) for t in record[name]),
                        key=str)
    return ox.serialize(quads, format=ox.RdfFormat.TRIG).decode("utf-8")


def parse_dump(text):
    """A TriG dump back to {name: triples}. Quads outside a record graph are refused."""
    import pyoxigraph as ox

    out = {}
    for q in ox.parse(text.encode("utf-8"), format=ox.RdfFormat.TRIG):
        name = name_of(q.graph_name)
        if name is None:
            raise StoreError(f"a quad outside any record graph: {q}",
                             "a dump holds only graphs named <" + GRAPH + "...>")
        out.setdefault(name, []).append(ox.Triple(q.subject, q.predicate, q.object))
    return out
