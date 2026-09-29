"""A workspace's record in career/store/, built from Turtle a test can read.

Fixtures stay as .ttl sources under tests/ - reviewable, diffable. A test copies one, edits
the text if it needs to, then calls seed(): the files are read by the loader that read them
before the store (legacy.read_workspace), put in a store, and removed - so nothing under
test can keep reading a file the record no longer lives in. Unlike `jsk kb load`, seed()
keeps a record with FAILs: tests of the rules need one.
"""
import glob
import os

from jsk.graph import legacy
from jsk.graph import record as R

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
    if not keep_files:
        for f in record_files(root):
            os.remove(f)
    return record


def graph_text(root, name=R.KB):
    """One graph of the store laid out as Turtle, as `jsk kb show` prints entries - for
    assertions that read the record the way a person would."""
    from jsk.graph import store as S
    from jsk.graph.writer import write

    store = S.load(str(root))
    return write(store.graph(name), store.parsed[name].kind) if name in store.parsed else None


def kb_text(root):
    return graph_text(root, R.KB)
