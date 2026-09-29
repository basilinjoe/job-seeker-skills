"""The career and its log kept in step, in career/store/: the revision they share, and the
one gate every write goes through."""
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import storekit
from test_graph_shapes import FIXTURES, load

from jsk.graph import db, record

TODAY = datetime.date(2026, 9, 24)


def workspace(edits=()):
    """A copy of the fixture, each (file, old, new) applied to its text, seeded."""
    tmp = tempfile.mkdtemp()
    shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
    for file, old, new in edits:
        path = Path(tmp) / file
        text = path.read_text(encoding="utf-8")
        assert old in text, old
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    storekit.seed(tmp)
    return tmp


def logged_write(root, by="apply", summary="A change."):
    """The career written back through the gate, as every writing command does."""
    s = load(root)
    p = record.prepared(s, s.graph(record.KB), TODAY, by, summary)
    record.write_graphs(root, p.graphs())
    return p


class State(unittest.TestCase):
    def setUp(self):
        self.root = workspace()
        self.addCleanup(shutil.rmtree, self.root)

    def test_the_fixture_is_clean(self):
        s = load(self.root)
        self.assertTrue(s.stored)
        st = record.state(s)
        self.assertEqual((st.kind, st.kb_revision, st.log_revision), ("clean", 2, 2))

    def test_a_missing_career_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(record.state(load(tmp)).kind, "missing")

    def test_a_store_written_outside_jsk_is_out_of_sync(self):
        s = load(self.root)
        record.write_graphs(self.root, {record.KB: record.stamp(s.graph(record.KB), 7, TODAY)})
        st = record.state(load(self.root))
        self.assertEqual((st.kind, st.kb_revision, st.log_revision), ("out-of-sync", 7, 2))
        self.assertIn("outside jsk", st.detail)


class NotAnInteger(unittest.TestCase):
    """A revision that is not an integer reads as absent: tier 1 FAILs its datatype, so the
    person sees the real cause, and the load does not raise. The store keeps `3.0` as the
    decimal 3 - the datatype, not the digits, is what says it is not a revision."""

    def test_a_decimal_kb_revision_loads_and_fails_its_datatype(self):
        root = workspace([(record.KB_FILE, "j:revision 2 .", "j:revision 3.0 .")])
        self.addCleanup(shutil.rmtree, root)
        s = load(root)
        self.assertIsNone(record.header_revision(s.parsed[record.KB].quads))
        self.assertIn((record.KB, "j:revision is xsd:decimal; expected integer"),
                      {(f.file, f.detail) for f in s.fails() if f.rule == "object"})
        self.assertIsNone(record.state(s).kb_revision)

    def test_a_decimal_log_revision_is_skipped_for_the_newest(self):
        root = workspace([(record.LOG_FILE, "k:rev_2 j:revision 2 ;", "k:rev_2 j:revision 2.0 ;")])
        self.addCleanup(shutil.rmtree, root)
        s = load(root)
        self.assertEqual(record.last_entry(s.parsed[record.LOG].quads)[0], 1)
        self.assertIn((record.LOG, "j:revision is xsd:decimal; expected integer"),
                      {(f.file, f.detail) for f in s.fails() if f.rule == "object"})


class WriteGraphs(unittest.TestCase):
    def setUp(self):
        self.root = workspace()
        self.addCleanup(shutil.rmtree, self.root)

    def test_a_logged_write_leaves_the_record_clean_at_the_next_revision(self):
        p = logged_write(self.root)
        s = load(self.root)
        self.assertEqual(p.revision, 3)
        st = record.state(s)
        self.assertEqual((st.kind, st.kb_revision, st.log_revision), ("clean", 3, 3))
        self.assertEqual(s.findings, [])

    def test_the_career_and_its_log_change_in_one_update(self):
        s = load(self.root)
        p = record.prepared(s, s.graph(record.KB), TODAY, "apply", "A change.")
        before = db.dump_text(db.read(self.root))
        real = db.update_text

        def failing_last(new):
            # One more operation that fails at run time, after both graphs are replaced.
            return real(new) + f" ;\nCLEAR GRAPH <{db.graph_iri('missing')}>"
        with mock.patch.object(db, "update_text", failing_last), \
                self.assertRaises(record.RecordError) as e:
            record.write_graphs(self.root, p.graphs())
        self.assertIn("nothing was changed", str(e.exception))
        self.assertEqual(db.dump_text(db.read(self.root)), before)

    def test_every_write_refreshes_the_backup_and_the_folder_ignores_itself(self):
        logged_write(self.root)
        backup = (Path(self.root) / record.BACKUP).read_text(encoding="utf-8")
        self.assertEqual(backup, db.dump_text(db.read(self.root)))
        self.assertEqual((Path(self.root) / ".jsk" / ".gitignore").read_text(), "*\n")

    def test_the_log_entry_names_what_the_write_touched_and_minted(self):
        s = load(self.root)
        p = record.prepared(s, s.graph(record.KB), TODAY, "apply", "A change.",
                            touched=["tag:jsk,2026:id/prj_a"], minted=["tag:jsk,2026:id/ach_b"])
        entry = {(q.predicate.value.rsplit("#", 1)[1], q.object.value) for q in p.log_quads
                 if q.subject.value.endswith("rev_3")}
        self.assertLessEqual({("touched", "tag:jsk,2026:id/prj_a"),
                              ("minted", "tag:jsk,2026:id/ach_b"), ("by", "tag:jsk,2026:ns#apply"),
                              ("revision", "3")}, entry)



if __name__ == "__main__":
    unittest.main()
