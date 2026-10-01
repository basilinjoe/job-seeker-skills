"""A workspace's record in career/store/, built from Turtle a test can read.

Fixtures stay as .ttl sources under tests/ - reviewable, diffable. A test copies one, edits
the text if it needs to, then calls seed(): the files are read by the loader that read them
before the store (legacy.read_workspace), put in a store, and removed - so nothing under
test can keep reading a file the record no longer lives in. Unlike `jsk kb load`, seed()
keeps a record with FAILs: tests of the rules need one.
"""
import glob
import os

from jsk.infra import legacy_import as legacy
from jsk.infra.oxigraph import record as R

RECORD_FILES = ("career/kb.ttl", "career/log.ttl")
APP_FILES = ("posting.ttl", "application.ttl", "gaps.ttl")


def record_files(root):
    found = [os.path.join(root, f) for f in RECORD_FILES]
    for name in APP_FILES:
        found += glob.glob(os.path.join(glob.escape(str(root)), "applications", "*", name))
    return [f for f in found if os.path.isfile(f)]


def seed(root, keep_files=False):
    """Put the record files under `root` into a new career/store/ and remove them. Returns
    the store's graphs by name. A file that does not parse is not seeded - a test of
    unparseable text is a test of input (a changeset, a posting build), not of the store."""
    root = str(root)
    _, record, _ = legacy.read_workspace(root)
    R.write_graphs(root, record, create=True)
    rehash(root)
    if not keep_files:
        for f in record_files(root):
            os.remove(f)
    return record


def rehash(root):
    """The log's newest entry made to hold the stored career's hash, as a jsk write leaves
    it: for a test that changes the career in the store as a write would, or seeds a
    fixture whose log hashed the file's text. `jsk kb check` FAILs a career its log's
    hash does not match - one written outside jsk."""
    import pyoxigraph as ox

    from jsk.infra.oxigraph import db
    from jsk.domain import ontology as O

    record = db.read(str(root))
    kb, log = record.get(R.KB), record.get(R.LOG)
    rev, sha = R.last_entry(log or [])
    if kb is None or rev is None:
        return
    from jsk.domain.record.writer import WriteError
    try:
        actual = R.career_sha(kb)
    except WriteError:
        return                  # a career with a FAIL the writer cannot lay out: left as it is
    if sha == actual:
        return
    newest = next(t.subject for t in log if t.predicate.value == O.J + "revision"
                  and R.revision_of(t.object) == rev)
    sha_p = ox.NamedNode(O.J + "kbSha256")
    log = [t for t in log if not (t.subject == newest and t.predicate == sha_p)]
    log.append(ox.Triple(newest, sha_p, ox.Literal(actual)))
    R.write_graphs(str(root), {R.LOG: log})


def graph_text(root, name=R.KB):
    """One graph of the store laid out as Turtle, as `jsk kb show` prints entries - for
    assertions that read the record the way a person would."""
    from jsk.graph import store as S
    from jsk.domain.record.writer import write

    store = S.load(str(root))
    return write(store.graph(name), store.parsed[name].kind) if name in store.parsed else None


def kb_text(root):
    return graph_text(root, R.KB)
