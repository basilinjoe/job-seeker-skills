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

from fixtures import SCRIPTS, child_env, source_path

from jsk.infra.oxigraph import db
from jsk.infra.oxigraph import record as R

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

    def test_round_trips_every_kind_of_literal(self):
        # Through the update's N-Triples and back, and through a dump: a language tag, a
        # datatype, a quote, and control characters N-Triples must escape (not only tab
        # and newline).
        import pyoxigraph as ox
        terms = [ox.Literal(NASTY, language="en-GB"), lit("2026-09-29", "date"),
                 lit('say "no" \\" twice'), lit("bell\x07 vt\x0b ff\x0c nul-ish\x01 del\x7f"),
                 lit(NASTY, "string"), ox.Literal("x", datatype=ox.NamedNode("tag:jsk,2026:t"))]
        self.write({"kb": [triple(f"t{i}", t) for i, t in enumerate(terms)]})
        got = {t.subject.value: t.object for t in db.read(self.root)["kb"]}
        self.assertEqual([got[f"tag:k#t{i}"] for i in range(len(terms))], terms)
        back = db.parse_dump(db.dump_text(db.read(self.root)))
        self.assertEqual(sorted(map(str, back["kb"])),
                         sorted(map(str, db.read(self.root)["kb"])))

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

    def test_the_store_is_dropped_even_when_its_flush_fails(self):
        class Failing:
            def flush(self):
                raise OSError("disk gone")
        w = db.Writer(Failing())
        with self.assertRaises(OSError):
            w.close()
        self.assertIsNone(w._db)


class WriteFailures(unittest.TestCase):
    """What a failed write says: "nothing was changed" only when the update itself failed.
    A failure after it landed - the flush, the backup - leaves the write in the store."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "career"))
        R.write_graphs(self.root, {"kb": [triple("a", lit("1"))]}, create=True)

    def value(self):
        return db.read(self.root)["kb"][0].object.value

    def test_a_refused_update_says_nothing_was_changed(self):
        import appkit
        with appkit.refusing_store(), self.assertRaises(R.RecordError) as e:
            R.write_graphs(self.root, {"kb": [triple("a", lit("2"))]})
        self.assertNotIsInstance(e.exception, R.Written)
        self.assertIn("nothing was changed", str(e.exception))
        self.assertEqual(self.value(), "1")

    def test_a_failure_after_the_update_does_not_say_nothing_changed(self):
        from unittest import mock
        close = db.Writer.close

        def failing(w):
            close(w)
            raise OSError("flush failed")
        with mock.patch.object(db.Writer, "close", failing), \
                self.assertRaises(R.Written) as e:
            R.write_graphs(self.root, {"kb": [triple("a", lit("2"))]})
        self.assertNotIn("nothing was changed", str(e.exception))
        self.assertIn("landed", str(e.exception))
        self.assertEqual(self.value(), "2")

    def test_any_failure_of_the_backup_leaves_the_write_standing(self):
        from unittest import mock

        def broken(_record):
            raise ValueError("cannot serialise")
        with mock.patch.object(db, "dump_text", broken):
            R.write_graphs(self.root, {"kb": [triple("a", lit("2"))]})
        self.assertEqual(self.value(), "2")


class Turn(unittest.TestCase):
    """Writers queue for their turn instead of being turned away; readers never wait."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "career"))
        R.write_graphs(self.root, {"kb": [triple("a", lit("0"))]}, create=True)

    HOLD = """
        from jsk.infra.oxigraph import db
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
            from jsk.infra.oxigraph import db
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
            from jsk.infra.oxigraph import record as R
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
            from jsk.infra.oxigraph import record as R
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
            from jsk.infra.oxigraph import db
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
            from jsk.infra.oxigraph import record as R
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


class TurnBeforeTheStore(unittest.TestCase):
    """`jsk new` and `jsk kb load` ask whether there is a store, then make one: two at once
    must not both find none. Each takes its turn with no store yet, and asks inside it."""

    FIRST = """
        from jsk import kb
        from jsk.infra.oxigraph import db
        with db.write_turn(root):
            print('got', flush=True)
            time.sleep(1.5)
            print('scaffold', kb.scaffold(root, 'First')[0], flush=True)
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_the_turn_is_taken_with_no_store_yet(self):
        with R.turn(self.root):
            self.assertTrue(db.holds_turn(self.root))

    def behind_a_new(self, *args):
        """Run `jsk *args` while another process holds the turn and then starts a career
        here; (its result, the name the store ends up holding)."""
        first = child(self.FIRST, self.root)
        self.assertEqual(first.stdout.readline().strip(), "got")
        second = subprocess.run([sys.executable, "-m", "jsk", *args], env=child_env(),
                                capture_output=True, text=True, timeout=120)
        out, err = first.communicate(timeout=60)
        self.assertIn("scaffold 0", out, err)
        names = [t.object.value for t in db.read(self.root)[R.KB]
                 if t.predicate.value.endswith("#name")]
        return second, names

    def test_a_new_queued_behind_another_is_refused(self):
        second, names = self.behind_a_new("kb", "new", self.root, "--name", "Second")
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertIn("already exists", second.stdout)
        self.assertIn("waiting for another jsk write", second.stderr)
        self.assertEqual(names, ["First"])

    def test_a_load_queued_behind_a_new_is_refused(self):
        import datetime

        from jsk import kb
        dump = Path(self.root, "other.trig")
        dump.write_text(db.dump_text(kb.first_write("Second", datetime.date(2026, 9, 29))),
                        encoding="utf-8")
        second, names = self.behind_a_new("kb", "load", str(dump), "--root", self.root)
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertIn("already holds a record", second.stdout)
        self.assertEqual(names, ["First"])


class OnlyDbKnowsTheStore(unittest.TestCase):
    """Ruling 13: db.py is the only module that opens the store on disk, and record.py the
    only one that writes it."""

    def sources(self):
        for path in SCRIPTS.rglob("*.py"):
            yield path.relative_to(SCRIPTS).as_posix(), path.read_text(encoding="utf-8")

    # ox.Store() with no argument is in memory; with a path, or read_only, it is the disk.
    OPENS = re.compile(r"\bStore\.read_only\(|\b(?:ox|pyoxigraph)\.Store\(\s*[^)\s]")
    # The same through `from pyoxigraph import Store`: a bare Store( with an argument.
    IMPORTS_STORE = re.compile(r"^\s*from\s+pyoxigraph\s+import\s+[^\n]*\bStore\b", re.M)
    BARE_OPEN = re.compile(r"(?<![\w.])Store\(\s*[^)\s]")
    # db.py's openers and the Writer's context: only record.py's write gate calls them.
    GATE = re.compile(r"\bopen_reader\(|\bopen_writer\(|\.writing\(")
    HANDLE = re.compile(r"\._db\b")

    def violations(self, sources):
        """(module, what it does that only db.py or record.py may) for each source."""
        out = []
        db, record = source_path("jsk.infra.oxigraph.db"), source_path("jsk.infra.oxigraph.record")
        for name, text in sources:
            if name == db:
                continue
            if self.OPENS.search(text) or (self.IMPORTS_STORE.search(text)
                                           and self.BARE_OPEN.search(text)):
                out.append((name, "opens a store on disk"))
            if self.HANDLE.search(text):
                out.append((name, "reaches the Writer's store"))
            if name == record:
                continue
            if self.GATE.search(text):
                out.append((name, "opens the store for itself"))
            if "replace_graphs" in text:
                out.append((name, "writes the store"))
        return out

    def test_only_db_and_record_touch_the_store(self):
        self.assertEqual(self.violations(self.sources()), [])

    def test_the_guard_sees_each_way_round_it(self):
        record = source_path("jsk.infra.oxigraph.record")
        planted = [("a.py", "db = ox.Store(path)"), ("b.py", "pyoxigraph.Store.read_only(p)"),
                   ("c.py", "from pyoxigraph import Literal, Store\ns = Store(p)"),
                   ("d.py", "s = db.open_reader(root)"), ("e.py", "db.open_writer(root)"),
                   ("f.py", "with db.writing(root) as w:"), ("g.py", "w._db.update(u)"),
                   ("h.py", "db.replace_graphs(s, g)"), (record, "w._db")]
        self.assertEqual([n for n, _ in self.violations(planted)],
                         ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py", "h.py",
                          record])
        fine = [("a.py", "s = ox.Store()"), ("b.py", "S.Store(root, findings=f)"),
                ("c.py", "from pyoxigraph import Store\ns = Store()"),
                (record, "with db.writing(root) as w:\n db.replace_graphs")]
        self.assertEqual(self.violations(fine), [])


if __name__ == "__main__":
    unittest.main()
