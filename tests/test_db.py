"""career/store/: the one module that knows it is RocksDB, and the turn writers queue for."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from fixtures import SCRIPTS, child_env

from jsk.graph import db
from jsk.graph import record as R

NASTY = 'He said "hi"\\n and \\ left\nnew line\ttab é \U0001F680 }} ;. <x>'


def triple(s, o):
    import pyoxigraph as ox
    return ox.Triple(ox.NamedNode("tag:k#" + s), ox.NamedNode("tag:j#p"), o)


def lit(value, dtype=None):
    import pyoxigraph as ox
    if dtype:
        return ox.Literal(value, datatype=ox.NamedNode("http://www.w3.org/2001/XMLSchema#" + dtype))
    return ox.Literal(value)


def child(code, root):
    """Run `code` in another Python, with `root` bound; (returncode, stdout, stderr)."""
    src = f"import sys, time\nroot = {str(root)!r}\n" + textwrap.dedent(code)
    return subprocess.Popen([sys.executable, "-c", src], env=child_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class Store(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "career"))

    def write(self, graphs):
        R.write_graphs(self.root, graphs, create=True)

    def test_round_trips_text_exactly(self):
        self.write({"kb": [triple("a", lit(NASTY))], "applications/x y/posting": [triple("b", lit("1"))]})
        got = db.read(self.root)
        self.assertEqual(sorted(got), ["applications/x y/posting", "kb"])
        self.assertEqual(got["kb"][0].object.value, NASTY)

    def test_numbers_come_back_by_value(self):
        # Ruling 4: why a changeset's `8.40` is refused rather than stored.
        self.write({"kb": [triple("a", lit("8.40", "decimal")), triple("b", lit("007", "integer"))]})
        values = sorted(t.object.value for t in db.read(self.root)["kb"])
        self.assertEqual(values, ["7", "8.4"])

    def test_a_graph_is_replaced_and_dropped(self):
        self.write({"kb": [triple("a", lit("1"))], "log": [triple("r", lit("1"))]})
        self.write({"kb": [triple("b", lit("2"))], "log": None})
        got = db.read(self.root)
        self.assertEqual(sorted(got), ["kb"])
        self.assertEqual([t.subject.value for t in got["kb"]], ["tag:k#b"])

    def test_an_update_that_fails_changes_nothing(self):
        # The second operation fails at run time; the first is rolled back with it.
        self.write({"kb": [triple("a", lit("1"))]})
        with db.writing(self.root) as w:
            with self.assertRaises(RuntimeError):
                w._db.update(f"DROP GRAPH <{db.graph_iri('kb')}> ; CLEAR GRAPH <{db.graph_iri('missing')}>")
        self.assertEqual(len(db.read(self.root)["kb"]), 1)

    def test_dump_and_parse_are_inverse_and_deterministic(self):
        self.write({"kb": [triple("a", lit(NASTY)), triple("b", lit("3", "integer"))],
                    "applications/acme/posting": [triple("c", lit("x"))]})
        record = db.read(self.root)
        text = db.dump_text(record)
        back = db.parse_dump(text)
        self.assertEqual({k: sorted(map(str, v)) for k, v in back.items()},
                         {k: sorted(map(str, v)) for k, v in record.items()})
        self.assertEqual(db.dump_text(back), text)

    def test_a_dump_quad_outside_a_record_graph_is_refused(self):
        with self.assertRaises(db.StoreError):
            db.parse_dump("<tag:a> <tag:b> <tag:c> .\n")

    def test_every_write_refreshes_the_backup(self):
        self.write({"kb": [triple("a", lit("1"))]})
        backup = Path(self.root, R.BACKUP)
        self.assertEqual(db.parse_dump(backup.read_text(encoding="utf-8"))["kb"][0].object.value, "1")
        self.write({"kb": [triple("a", lit("2"))]})
        self.assertIn('"2"', backup.read_text(encoding="utf-8"))

    def test_no_store_is_its_own_error(self):
        with self.assertRaises(db.NoStore) as e:
            db.open_reader(os.path.join(self.root, "elsewhere"))
        self.assertIn("jsk kb load", e.exception.fix)

    def test_a_non_lock_error_is_not_busy(self):
        # A file where the store folder should be: an OSError that is not the lock.
        Path(self.root, db.STORE_DIR).write_text("not a store", encoding="utf-8")
        with self.assertRaises(db.StoreError) as e:
            db.open_writer(self.root, wait=0, create=True)
        self.assertNotIsInstance(e.exception, db.Busy)

    def test_a_corrupt_store_is_a_store_error_not_a_traceback(self):
        # RocksDB reports corruption as a RuntimeError, which open_reader let through.
        os.makedirs(os.path.join(self.root, db.STORE_DIR))
        Path(self.root, db.STORE_DIR, "CURRENT").write_text("garbage\n", encoding="utf-8")
        for opener in (db.open_reader, lambda root: db.open_writer(root, wait=0)):
            with self.assertRaises(db.StoreError) as e:
                opener(self.root)
            self.assertNotIsInstance(e.exception, db.Busy)
            self.assertIn("jsk doctor", e.exception.fix)

    def test_the_lock_is_told_from_other_errors_on_either_os(self):
        # RocksDB's own words for its LOCK being held. The Windows one is what open_writer
        # meets on this machine; the Linux one is flock's EAGAIN, which only the Linux CI job
        # would otherwise see - and read as "not the lock", reporting a queue as a fault.
        linux = OSError("IO error: While lock file: /home/u/ws/career/store/LOCK: "
                        "Resource temporarily unavailable")
        windows = OSError("IO error: Failed to create lock file: C:\\ws\\career\\store/LOCK: "
                          "The process cannot access the file because it is being used by "
                          "another process.")
        self.assertTrue(db.is_lock_error(linux))
        self.assertTrue(db.is_lock_error(windows))
        for other in ("IO error: No such file or directory: While opening a file for sequentially "
                      "reading: /ws/career/store/CURRENT: No such file or directory",
                      "Corruption: block checksum mismatch",
                      "IO error: While open a file for appending: /ws/career/store/LOCK: "
                      "Permission denied"):
            self.assertFalse(db.is_lock_error(OSError(other)), other)

    def test_the_store_is_closed_when_writing_ends(self):
        self.write({"kb": [triple("a", lit("1"))]})
        with db.writing(self.root) as w:
            kept = w                                    # a caller holding on to it
        db.open_writer(self.root, wait=0)               # would raise Busy if still open
        self.assertIsNone(kept._db)


class Turn(unittest.TestCase):
    """Writers queue for their turn instead of being turned away; readers never wait."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "career"))
        R.write_graphs(self.root, {"kb": [triple("a", lit("0"))]}, create=True)

    HOLD = """
        from jsk.graph import db
        with db.write_turn(root, say=lambda m: print('waited', flush=True)):
            print('got', time.time(), flush=True)
            time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 1.0)
    """

    def test_writers_are_granted_in_turn_not_refused(self):
        procs = []
        for _ in range(3):
            procs.append(child(self.HOLD, self.root))
            time.sleep(0.4)
        outs = [p.communicate(timeout=60) for p in procs]
        self.assertEqual([p.returncode for p in procs], [0, 0, 0], [o[1] for o in outs])
        got = [float(re.search(r"got (\S+)", o[0]).group(1)) for o in outs]
        self.assertEqual(got, sorted(got))
        for a, b in zip(got, got[1:], strict=False):
            self.assertGreaterEqual(b - a, 0.9)          # each waited for the one before
        self.assertTrue(all("waited" in o[0] for o in outs[1:]))

    def test_a_reader_does_not_wait_for_a_turn(self):
        holder = child(self.HOLD.replace("1.0", "3.0"), self.root)
        time.sleep(1.0)
        start = time.monotonic()
        self.assertEqual(db.read(self.root)["kb"][0].object.value, "0")
        self.assertLess(time.monotonic() - start, 1.5)
        holder.communicate(timeout=30)

    def test_a_reader_waits_only_while_a_write_has_the_store_open(self):
        # Exclusive access is held for the write itself; a read in that window waits for it
        # (a read-only open while another process writes is undefined behaviour).
        holder = child("""
            from jsk.graph import db
            with db.writing(root):
                print('open', flush=True)
                time.sleep(1.5)
        """, self.root)
        self.assertEqual(holder.stdout.readline().strip(), "open")
        start = time.monotonic()
        self.assertEqual(db.read(self.root)["kb"][0].object.value, "0")
        self.assertGreater(time.monotonic() - start, 0.8)
        holder.communicate(timeout=30)

    def test_reads_racing_many_writes_never_fail(self):
        # The race pyoxigraph calls undefined: a writer compacting while a reader opens.
        # Hundreds of writes against a reader in a loop; every read must succeed, and see
        # a whole write - never half of one.
        writer = child("""
            import pyoxigraph as ox
            from jsk.graph import record as R
            for n in range(150):
                big = [ox.Triple(ox.NamedNode(f"tag:s{i}"), ox.NamedNode("tag:p"),
                                 ox.Literal(str(n))) for i in range(300)]
                R.write_graphs(root, {"kb": big})
            print('done', flush=True)
        """, self.root)
        reads = 0
        while writer.poll() is None:
            got = db.read(self.root)["kb"]
            self.assertEqual(len({t.object.value for t in got}), 1, "a read saw half a write")
            reads += 1
        out, err = writer.communicate(timeout=120)
        self.assertEqual(writer.returncode, 0, err)
        self.assertIn("done", out)
        self.assertGreater(reads, 5)

    def test_a_writer_killed_mid_write_leaves_a_whole_revision(self):
        # Verification 3: kill a writer at arbitrary points, again and again. The store must
        # open every time and hold one whole write - the old one or the new - never a mix,
        # and the next writer must get in.
        import random

        loop = """
            import pyoxigraph as ox
            from jsk.graph import record as R
            n = int(sys.argv[1]) * 1000
            print('started', flush=True)
            while True:
                n += 1
                R.write_graphs(root, {"kb": [ox.Triple(ox.NamedNode(f"tag:s{i}"),
                    ox.NamedNode("tag:p"), ox.Literal(str(n))) for i in range(400)]})
        """
        rng = random.Random(7)
        for round_ in range(6):
            p = subprocess.Popen([sys.executable, "-c", f"import sys, time\nroot = {self.root!r}\n"
                                  + textwrap.dedent(loop), str(round_ + 1)], env=child_env(),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(p.stdout.readline().strip(), "started")
            time.sleep(rng.uniform(0.2, 1.5))
            p.kill()
            p.communicate(timeout=30)
            values = {t.object.value for t in db.read(self.root)["kb"]}
            self.assertEqual(len(values), 1, f"round {round_}: a mix of writes {sorted(values)[:3]}")
            R.write_graphs(self.root, {"probe": [triple("x", lit(str(round_)))]})

    def test_a_read_inside_this_process_s_own_write_is_refused(self):
        with db.writing(self.root):
            with self.assertRaises(RuntimeError):
                db.read(self.root)

    def test_a_writer_that_dies_holding_its_turn_releases_it(self):
        dead = child("""
            import os
            from jsk.graph import db
            with db.write_turn(root):
                os._exit(3)
        """, self.root)
        dead.communicate(timeout=30)
        self.assertEqual(dead.returncode, 3)
        start = time.monotonic()
        with db.write_turn(self.root, say=lambda m: self.fail("waited on a dead process")):
            pass
        self.assertLess(time.monotonic() - start, 1.0)

    def test_the_turn_is_reentrant(self):
        with db.write_turn(self.root, say=lambda m: self.fail(m)):
            with db.write_turn(self.root, say=lambda m: self.fail(m)):
                self.assertTrue(db.holds_turn(self.root))
            self.assertTrue(db.holds_turn(self.root))
        self.assertFalse(db.holds_turn(self.root))

    def test_queued_writes_all_land(self):
        # Four processes each add their own graph; every one lands, none is refused.
        add = """
            import pyoxigraph as ox
            from jsk.graph import record as R
            n = sys.argv[1]
            R.write_graphs(root, {"g" + n: [ox.Triple(ox.NamedNode("tag:s" + n),
                                                       ox.NamedNode("tag:p"), ox.Literal(n))]})
        """
        procs = [subprocess.Popen([sys.executable, "-c", f"import sys, time\nroot = {self.root!r}\n"
                                   + textwrap.dedent(add), str(i)], env=child_env(),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for i in range(4)]
        for p in procs:
            _, err = p.communicate(timeout=60)
            self.assertEqual(p.returncode, 0, err)
        self.assertEqual(sorted(db.read(self.root)), ["g0", "g1", "g2", "g3", "kb"])


class OnlyDbKnowsTheStore(unittest.TestCase):
    """Ruling 13: db.py is the only module that opens the store on disk, and record.py the
    only one that writes it."""

    def sources(self):
        for path in SCRIPTS.rglob("*.py"):
            yield path.relative_to(SCRIPTS).as_posix(), path.read_text(encoding="utf-8")

    def test_only_db_opens_a_store_on_disk(self):
        # ox.Store() with no argument is in memory; with a path, or read_only, it is the disk.
        opens = re.compile(r"\bStore\.read_only\(|\b(?:ox|pyoxigraph)\.Store\(\s*[^)\s]")
        found = [name for name, text in self.sources() if opens.search(text) and name != "graph/db.py"]
        self.assertEqual(found, [])

    def test_only_record_writes_the_store(self):
        found = [name for name, text in self.sources() if "replace_graphs" in text
                 and name not in ("graph/db.py", "graph/record.py")]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
