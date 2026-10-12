"""A workspace's record in career/store/, built from Turtle a test can read.

Fixtures stay as .ttl sources under tests/ - reviewable, diffable. A test copies one, edits
the text if it needs to, then calls seed(): the files are read by the loader that read them
before the store (legacy.read_workspace), put in a store, and removed - so nothing under
test can keep reading a file the record no longer lives in. Unlike `jsk kb load`, seed()
keeps a record with FAILs: tests of the rules need one.
"""
import contextlib
import glob
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import fixtures  # noqa: F401 - puts this checkout's src/ first on sys.path
from jsk.infra import legacy_import as legacy
from jsk.infra.oxigraph import record as R

RECORD_FILES = ("career/kb.ttl", "career/log.ttl")
APP_FILES = ("posting.ttl", "application.ttl", "gaps.ttl")


def record_files(root):
    found = [os.path.join(root, f) for f in RECORD_FILES]
    for name in APP_FILES:
        found += glob.glob(os.path.join(glob.escape(str(root)), "applications", "*", name))
    found += glob.glob(os.path.join(glob.escape(str(root)), "resumes", "*", "resume.ttl"))
    return [f for f in found if os.path.isfile(f)]


def seed(root, keep_files=False):
    """Put the record files under `root` into a new career/store/ and remove them. Returns
    the store's graphs by name. A file that does not parse is not seeded - a test of
    unparseable text is a test of input (a changeset, a posting build), not of the store."""
    root = str(root)
    seeded = _SEEDED.get(_tree_key(root))
    if seeded is None:
        seeded = _seed_template(root)
    if seeded is None:
        # Seeding this tree raised: seed it in place, so the test sees the error and
        # whatever the failed write left, as before there was a cache.
        _, record, _ = legacy.read_workspace(root)
        R.write_graphs(root, record, create=True)
        rehash(root)
    else:
        template, made, record = seeded
        for rel in made:
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            shutil.copyfile(os.path.join(template, rel), os.path.join(root, rel))
        record = {name: None if g is None else list(g) for name, g in record.items()}
    if not keep_files:
        for f in record_files(root):
            os.remove(f)
    return record


# A store is two writes and a read - a third of a second each time, and the suite seeded
# the same few fixtures some five hundred times a run. So each distinct tree is seeded
# once per test process, in a template, and a later seed of the same bytes copies the
# files that seeding made. A closed RocksDB directory is plain files; its copy opens.
_SEEDED = {}


def _digests(root):
    """{relative path: sha256 of its bytes} for every file under `root`."""
    import hashlib

    found = {}
    for d, _, names in os.walk(root):
        for name in names:
            path = os.path.join(d, name)
            with open(path, "rb") as f:
                found[os.path.relpath(path, root)] = hashlib.sha256(f.read()).hexdigest()
    return found


def _tree_key(root):
    return repr(sorted((rel.replace(os.sep, "/"), sha) for rel, sha in _digests(root).items()))


def _seed_template(root):
    """(template dir, the files seeding made or changed in it, the record), cached under
    the tree's key; None if seeding the tree raises."""
    import atexit

    key = _tree_key(root)
    template = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, template, True)
    shutil.copytree(root, template, dirs_exist_ok=True)
    before = _digests(template)
    try:
        _, record, _ = legacy.read_workspace(template)
        R.write_graphs(template, record, create=True)
        rehash(template)
    except Exception:  # noqa: BLE001
        # Whatever seeding raises is the test's business, and seed() repeats it in place.
        return None
    made = sorted(rel for rel, sha in _digests(template).items() if before.get(rel) != sha)
    _SEEDED[key] = seeded = (template, made, record)
    return seeded


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
    from jsk.adapters.compose import record as S
    from jsk.domain.record.writer import write

    store = S.load(str(root))
    return write(store.graph(name), store.parsed[name].kind) if name in store.parsed else None


def kb_text(root):
    return graph_text(root, R.KB)


class Workspace(unittest.TestCase):
    """The fixture copied, and put in a store the first time a test runs `jsk kb` on it -
    so a test can edit the fixture's text first (a record with a FAIL, say: the store
    keeps what it is given)."""

    def setUp(self):
        # Imported here, not at the top: test_graph_shapes imports this module.
        from test_graph_shapes import FIXTURES

        self.root = tempfile.mkdtemp()
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.seeded = False

    def seed(self):
        if not self.seeded:
            seed(self.root)
            self.seeded = True

    def path(self, name):
        return Path(self.root) / name

    def changeset(self, text, name="changes.trig"):
        self.path(name).write_text(text, encoding="utf-8")
        return str(self.path(name))

    def kb(self, *args):
        """(exit code, stdout) of `kb <args> --root`: check, pack and merge as the career_check,
        career_pack and career_merge tools run them (`jsk kb` refuses those three), the rest
        through `jsk kb`."""
        from jsk import cli
        import recordkit

        self.seed()
        if args and args[0] in ("check", "pack", "merge"):
            code, out, _ = recordkit.kb_verb(self.root, *args)
            return code, out
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue()

    # The record's reads and writes, as the career_* tools make them (recordkit): the
    # `jsk kb apply|confirm|show|view|query|log` verbs were retired in 6.0.

    def apply(self, path, dry_run=False, today=None):
        """What career_apply (career_preview with `dry_run`) says of the changeset file at
        `path`, read as UTF-8 text: (exit code, output)."""
        import recordkit

        self.seed()
        with open(path, encoding="utf-8") as f:
            return recordkit.apply(self.root, f.read(), dry_run=dry_run, today=today)

    def confirm(self, *ids, **kw):
        import recordkit

        self.seed()
        return recordkit.confirm(self.root, ids, **kw)

    def show(self, *ids, **kw):
        import recordkit

        self.seed()
        return recordkit.show(self.root, ids, **kw)

    def view(self, section=None):
        import recordkit

        self.seed()
        return recordkit.view(self.root, section)

    def query(self, name, *args, **kw):
        import recordkit

        self.seed()
        return recordkit.query(self.root, name, *args, **kw)

    def log(self, last=10):
        import recordkit

        self.seed()
        return recordkit.log(self.root, last)

    def loaded(self):
        from jsk.adapters.compose import record as S

        self.seed()
        return S.load(self.root)

    def record(self):
        """The whole record as its dump: what a refusal must leave as it was."""
        from jsk.infra.oxigraph import db

        self.seed()
        return db.dump_text(db.read(self.root))

    def kb_text(self):
        return kb_text(self.root)

    def log_text(self):
        return graph_text(self.root, R.LOG)

    def edit_kb(self, old, new):
        """Change the career: its text before it is stored, the store after."""
        from test_graph_pack import edit_career

        if self.seeded:
            return edit_career(self, self.root, old, new)
        kb = self.path("career/kb.ttl")
        text = kb.read_text(encoding="utf-8")
        self.assertIn(old, text)
        kb.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
