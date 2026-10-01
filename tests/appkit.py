"""An application's record graphs in a test workspace's store: read one back, put one in
from Turtle a test can read, drop one.

The store has no files to open, so a test that used to read or hand-write posting.ttl,
application.ttl or gaps.ttl reads and writes the graph instead - read-only through
db.read, written through record.write_graphs as every jsk write is.
"""
from jsk.infra.oxigraph import db
from jsk.infra.oxigraph import record as R
from jsk.infra.oxigraph.codec import parse_text
from jsk.domain.ontology import kind_of

PREFIXES = ("@prefix j: <tag:jsk,2026:ns#> .\n@prefix k: <tag:jsk,2026:id/> .\n"
            "@prefix c: <tag:jsk,2026:concept/> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n")


def seed(root):
    """storekit.seed, then - for a fixture whose career was never logged, as
    tests/match_fixtures' is not - the career stamped r1 with its log entry, as `jsk new`
    leaves one. A store holds a logged career or reads as written outside jsk."""
    import datetime

    import storekit

    record = storekit.seed(root)
    kb = record.get(R.KB)
    if kb is not None and R.header_revision(kb) is None:
        today = datetime.date(2026, 9, 24)
        kb = R.stamp(kb, 1, today)
        R.write_graphs(str(root), {
            R.KB: kb,
            R.LOG: list(record.get(R.LOG, [])) + R.entry(1, today, "new", "seeded",
                                                         R.career_sha(kb))})
    return record


def stored_copy(fixture):
    """A copy of the fixture tree in a store of its own, for tests that only read it -
    removed when the test process exits. The vocabulary.ttl a fixture ships stays a file."""
    import atexit
    import shutil
    import tempfile
    from pathlib import Path

    root = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, root, True)
    shutil.copytree(fixture, root, dirs_exist_ok=True)
    seed(root)
    return root


def name(app, kind):
    """`applications/<dir>/<kind>` for an application directory (a path) or its <dir>."""
    return f"applications/{str(app).replace(chr(92), '/').rstrip('/').rsplit('/', 1)[-1]}/{kind}"


def graphs(root):
    return db.read(str(root))


def triples(root, graph):
    """The graph's triples, or None when the store has no such graph."""
    return graphs(root).get(graph)


def has(root, graph):
    return graph in graphs(root)


def text(root, graph):
    """The graph laid out as Turtle, as `jsk kb show` prints entries; None when absent."""
    from jsk.domain.record.writer import write

    found = triples(root, graph)
    return None if found is None else write(found, kind_of(graph))


def facts(root, graph):
    """The graph as a set of (s, p, o) strings: what two writes of one graph compare by."""
    return {(str(t.subject), str(t.predicate), str(t.object)) for t in triples(root, graph) or ()}


def put(root, graph, turtle, prefixes=True):
    """Replace `graph` with the triples of `turtle` - the store-side twin of writing a .ttl
    file by hand. Prefixed with j:, k:, c: and xsd: unless `prefixes` is False."""
    parsed = parse_text((PREFIXES if prefixes else "") + turtle, graph)
    R.write_graphs(str(root), {graph: parsed.quads})


def drop(root, graph):
    R.write_graphs(str(root), {graph: None})


def refusing_store():
    """db.replace_graphs failing at run time, as a full disk would. A plain function, not
    a Mock: a Mock keeps its call's arguments, the open store among them, and on Windows
    the store's LOCK then outlives the test and its temporary directory."""
    from unittest import mock

    def refuse(_db, _new):
        raise RuntimeError("disk full")
    return mock.patch.object(db, "replace_graphs", refuse)


def failing_after_write():
    """The update lands, and closing the store after it fails, as a flush to a full disk
    would: the record holds the write, and the command must not say it does not."""
    from unittest import mock

    close = db.Writer.close

    def failing(w):
        close(w)
        raise OSError("flush failed")
    return mock.patch.object(db.Writer, "close", failing)
