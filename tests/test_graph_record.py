"""kb.ttl and log.ttl kept in step: staged writes, the lock retry, torn writes, the shadow."""
import datetime
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_graph_shapes import FIXTURES, load

from jsk.graph import record
from jsk.graph.io import sha256

TODAY = datetime.date(2026, 9, 24)
REAL_REPLACE = os.replace


def workspace():
    tmp = tempfile.mkdtemp()
    shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
    return tmp


def logged_write(root, **kw):
    """Rewrite the fixture's kb.ttl through the record, as every writing command does."""
    s = load(root)
    rev, kb_text, log_text = record.prepare(s, s.graph(record.KB), TODAY, "fmt", "Reformatted.",
                                            **kw)
    record.commit(root, kb_text, log_text)
    return rev, kb_text


def failing(names, times):
    """An os.replace that raises PermissionError `times` times for files named in `names`."""
    left = {"n": times}

    def fake(src, dst):
        if os.path.basename(dst) in names and left["n"]:
            left["n"] -= 1
            raise PermissionError(13, "locked")
        return REAL_REPLACE(src, dst)
    return fake


class State(unittest.TestCase):
    def test_the_fixture_is_clean(self):
        st = record.state(load(FIXTURES))
        self.assertEqual((st.kind, st.kb_revision, st.log_revision), ("clean", 2, 2))

    def test_a_missing_kb_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(record.state(load(tmp)).kind, "missing")


class Commit(unittest.TestCase):
    def setUp(self):
        self.root = workspace()
        self.addCleanup(shutil.rmtree, self.root)

    def test_a_logged_write_leaves_the_record_clean_at_the_next_revision(self):
        rev, kb_text = logged_write(self.root)
        s = load(self.root)
        self.assertEqual(rev, 3)
        self.assertEqual(record.state(s).kind, "clean")
        self.assertEqual(s.findings, [])
        self.assertEqual(record.shadow(self.root, sha256(kb_text)), kb_text)
        self.assertEqual(sorted(os.listdir(Path(self.root) / "career")), ["kb.ttl", "log.ttl"])

    def test_a_reformat_moves_the_revision_and_not_the_day(self):
        _, kb_text = logged_write(self.root, content=False)
        self.assertIn('j:updated "2026-09-20"^^xsd:date ; j:revision 3 .', kb_text)

    def test_a_lock_that_clears_is_waited_out(self):
        with mock.patch("jsk.graph.record.os.replace", failing({"kb.ttl"}, 2)):
            rev, _ = logged_write(self.root)
        self.assertEqual(record.state(load(self.root)).kind, "clean")

    def test_a_lock_that_holds_on_kb_changes_nothing(self):
        before = {f: (Path(self.root) / f).read_bytes() for f in (record.KB, record.LOG)}
        with mock.patch("jsk.graph.record.os.replace", failing({"kb.ttl"}, 99)), \
                mock.patch("jsk.graph.record.time.sleep"):
            with self.assertRaises(record.RecordError) as e:
                logged_write(self.root)
        self.assertIn("kb.ttl is locked", str(e.exception))
        self.assertIn("nothing was changed", str(e.exception))
        self.assertEqual({f: (Path(self.root) / f).read_bytes() for f in before}, before)
        self.assertEqual(sorted(os.listdir(Path(self.root) / "career")), ["kb.ttl", "log.ttl"])

    def test_a_lock_that_holds_on_log_is_a_torn_write_the_next_load_names(self):
        with mock.patch("jsk.graph.record.os.replace", failing({"log.ttl"}, 99)), \
                mock.patch("jsk.graph.record.time.sleep"):
            with self.assertRaises(record.RecordError) as e:
                logged_write(self.root)
        self.assertIn("jsk kb adopt", e.exception.fix)
        s = load(self.root)
        self.assertEqual(record.state(s).kind, "torn")
        self.assertEqual([f.rule for f in s.fails()], ["log-sync"])

    def test_a_shadow_that_is_not_the_logged_revision_is_ignored(self):
        _, kb_text = logged_write(self.root)
        (Path(self.root) / record.SHADOW).write_text(kb_text + "\n", encoding="utf-8")
        self.assertIsNone(record.shadow(self.root, sha256(kb_text)))

    def test_the_shadow_folder_ignores_itself(self):
        logged_write(self.root)
        self.assertEqual((Path(self.root) / ".jsk" / ".gitignore").read_text(), "*\n")


if __name__ == "__main__":
    unittest.main()
