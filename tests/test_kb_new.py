"""`jsk new`: a graph workspace from nothing, that career_apply can write to at once.

P3's Ruling 9: writes need a clean record, so a workspace has to start logged. These
tests hold `jsk new` to that - the scaffold is a store that loads with no finding, clean at
r1, and takes docs/SCRIPTS.md's braindump changeset as written.
"""
import contextlib
import datetime
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import storekit
from fixtures import REPO_ROOT as REPO
from test_graph_shapes import FIXTURES

from jsk import cli
from jsk.adapters.cli.kb import new
from jsk.application.record import scaffold
from jsk.adapters.cli.compose import record
from jsk.infra.oxigraph import db
from jsk.domain import ontology as O
from jsk.infra.oxigraph import record as R
from jsk.adapters.cli.compose import record as S

TODAY = datetime.date(2026, 9, 25)


def scripts_changesets():
    """The ```trig blocks docs/SCRIPTS.md shows, in order: what a person copies."""
    text = (REPO / "docs" / "SCRIPTS.md").read_text(encoding="utf-8")
    return re.findall(r"^```trig\n(.*?)^```", text, re.M | re.S)


class Scaffold(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def path(self, name):
        return Path(self.root) / name

    def new(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "new", self.root, "--name", "Priya Raman", *args])
        return code, out.getvalue()

    def apply(self, text):
        """career_apply on the new workspace (`jsk kb apply` until 6.0)."""
        import recordkit

        return recordkit.apply(self.root, text)

    def record(self):
        """The whole record as its dump: what a refusal must leave as it was."""
        return db.dump_text(db.read(self.root))

    def kb_text(self):
        return storekit.kb_text(self.root)

    def log_text(self):
        return storekit.graph_text(self.root, R.LOG)


class FromNothing(Scaffold):
    def test_it_writes_the_workspace(self):
        code, out = self.new()
        self.assertEqual(code, 0, out)
        self.assertTrue(self.path(scaffold.STORE).is_dir(), out)
        for name in ("applications/README.md", ".gitattributes"):
            with self.subTest(file=name):
                self.assertTrue(self.path(name).is_file(), out)
        self.assertIn("(r1, by new)", out)
        self.assertEqual(list(Path(self.root).rglob("*.ttl")), [])      # no file is the record
        self.assertFalse(self.path("user-knowledgebase.md").exists())

    def test_it_makes_a_place_for_general_resumes(self):
        # Ruling 10 of the graph-native plan: a general resume's selection is the graph
        # resumes/<name>/resume, and its render lands in resumes/<name>/.
        code, out = self.new()
        self.assertEqual(code, 0, out)
        self.assertTrue(self.path("resumes").is_dir(), out)

    def test_the_record_loads_clean_at_r1_with_no_finding(self):
        self.new()
        store = S.load(self.root)
        self.assertTrue(store.stored)
        self.assertEqual([f.text() for f in store.findings], [])
        st = R.state(store)
        self.assertEqual((st.kind, st.kb_revision, st.log_revision), ("clean", 1, 1))
        self.assertEqual(sorted(db.read(self.root)), [R.KB, R.LOG])

    def test_the_career_is_the_header_naming_the_person(self):
        self.new()
        text = self.kb_text()
        self.assertIn('k:kb j:format 3 ; j:name "Priya Raman" ; j:updated', text)
        self.assertIn("j:revision 1 .", text)
        self.assertEqual(tuple(re.findall(r"^# == (.+)$", text, re.M)), O.SECTIONS["kb"])

    def test_the_log_says_jsk_new_wrote_it(self):
        self.new()
        log = self.log_text()
        self.assertIn("j:by j:new", log)
        self.assertIn("k:rev_1 ", log)

    def test_every_write_leaves_a_backup(self):
        self.new()
        backup = self.path(R.BACKUP).read_text(encoding="utf-8")
        self.assertEqual(backup, self.record())

    def test_the_gitattributes_keep_git_off_the_store(self):
        self.new()
        lines = self.path(".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["career/store/** binary"])

    def test_an_existing_gitattributes_is_added_to_never_replaced(self):
        self.path(".gitattributes").write_text("*.pdf binary", encoding="utf-8")
        self.new()
        lines = self.path(".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["*.pdf binary", "career/store/** binary"])
        self.assertEqual(self.new("--force")[0], 0)
        again = self.path(".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertEqual(again, lines)

    def test_a_cp1252_gitattributes_is_left_alone_with_the_rules_to_add(self):
        """The person's own file: bytes that are not UTF-8 are not appended to, and the
        record is still written."""
        raw = b"# \x93mine\x94\n*.pdf binary\n"
        self.path(".gitattributes").write_bytes(raw)
        code, out = self.new()
        self.assertEqual(code, 0, out)
        self.assertNotIn("Traceback", out)
        self.assertIn("not UTF-8", out)
        self.assertIn("career/store/** binary", out)
        self.assertEqual(self.path(".gitattributes").read_bytes(), raw)
        self.assertTrue(db.exists(self.root))

    def test_a_name_is_required(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "new", self.root])
        self.assertEqual(code, 2)
        self.assertIn("--name is required", out.getvalue())
        self.assertFalse(db.exists(self.root))


class ThenApply(Scaffold):
    def test_the_braindump_in_the_docs_applies_to_a_new_workspace(self):
        """The first ```trig block in docs/SCRIPTS.md, copied as it stands."""
        self.new()
        code, out = self.apply(scripts_changesets()[0])
        self.assertEqual(code, 0, out)
        self.assertIn("r2 written", out)
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.fails()], [])
        st = R.state(store)
        self.assertEqual((st.kind, st.log_revision), ("clean", 2))
        text = self.kb_text()
        self.assertIn("k:prj_payments", text)
        self.assertIn("k:ach_payments_", text)            # the bullet got its id

    def test_every_changeset_in_the_docs_parses(self):
        """The others name entries a new workspace does not have, so they are read, not
        applied: a block that does not parse is one nobody can copy."""
        blocks = scripts_changesets()
        self.assertGreaterEqual(len(blocks), 2)
        for n, block in enumerate(blocks):
            with self.subTest(block=n):
                cs = record.read_changeset(block, f"block{n}.trig")
                self.assertIsNotNone(cs.base)


class Refusals(Scaffold):
    def test_an_existing_record_is_refused_and_untouched(self):
        self.new()
        before = self.record()
        code, out = self.new()
        self.assertEqual(code, 1)
        self.assertIn("REFUSED  already exists", out)
        self.assertIn("career_apply tool", out)
        self.assertIn("career/kb.r<N>.trig", out)
        self.assertNotRegex(out, r"\bgit\b")
        self.assertEqual(self.record(), before)

    def test_a_workspace_still_laid_out_as_files_is_loaded_not_started_over(self):
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        before = self.path("career/kb.ttl").read_bytes()
        for force in ((), ("--force",)):
            with self.subTest(force=force):
                code, out = self.new(*force)
                self.assertEqual(code, 1, out)
                self.assertIn("jsk kb load .", out)
                self.assertFalse(db.exists(self.root))
                self.assertEqual(self.path("career/kb.ttl").read_bytes(), before)

    def test_an_old_markdown_career_is_left_alone(self):
        """jsk no longer reads user-knowledgebase.md: `jsk new` starts the record beside
        it, without --force, and never touches the old file."""
        self.path("user-knowledgebase.md").write_text("---\nkb: 2\n---\n", encoding="utf-8")
        code, out = self.new()
        self.assertEqual(code, 0, out)
        self.assertTrue(db.exists(self.root))
        self.assertEqual(self.path("user-knowledgebase.md").read_text(encoding="utf-8"),
                         "---\nkb: 2\n---\n")

    def test_pyoxigraph_is_needed_and_the_fix_says_how(self):
        from unittest import mock
        with mock.patch.dict("sys.modules", {"pyoxigraph": None}):
            code, lines = new.scaffold(self.root, "Priya Raman", today=TODAY)
        self.assertEqual(code, 1)
        text = "\n".join(lines)
        self.assertIn("pyoxigraph", text)
        self.assertIn("pip install", text)
        self.assertFalse(db.exists(self.root))


class Force(Scaffold):
    def test_force_starts_over_as_the_next_revision_and_keeps_the_log(self):
        self.new()
        code, out = self.apply(scripts_changesets()[0])
        self.assertEqual(code, 0, out)
        old_log = self.log_text()
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        self.assertIn("(r3, by new)", out)
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.fails()], [])
        st = R.state(store)
        self.assertEqual((st.kind, st.kb_revision), ("clean", 3))
        log = self.log_text()
        for entry in ("k:rev_1 ", "k:rev_2 ", "k:rev_3 "):
            self.assertIn(entry, log)
        self.assertIn(old_log.split("# == Log\n", 1)[1].strip(), log)
        self.assertNotIn("k:prj_payments", self.kb_text())

    def test_force_keeps_the_whole_replaced_record_as_a_dump(self):
        """No git, no shadow: the only copy of what --force replaces is the one it keeps -
        and it is a dump, so `jsk kb load` brings it back."""
        self.new()
        self.assertEqual(self.apply(scripts_changesets()[0])[0], 0)
        old = self.record()
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        kept = self.path("career/kb.r2.trig")
        self.assertEqual(kept.read_text(encoding="utf-8"), old)
        self.assertIn("kb.r2.trig", out)
        self.assertNotRegex(out, r"\bgit\b")
        self.assertIn("career/kb.r2.trig", self.log_text())
        # and it loads, into a workspace of its own
        with tempfile.TemporaryDirectory() as elsewhere:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli.main(["jsk", "kb", "load", str(kept), "--root", elsewhere])
            self.assertEqual(code, 0, buf.getvalue())
            self.assertIn("k:prj_payments", storekit.kb_text(elsewhere))

    def test_a_changeset_drafted_before_a_start_over_is_refused(self):
        """It was drafted against the career --force replaced: applied to the empty one, it
        would bring back part of a record the person chose to start over from."""
        self.new()
        drafted = scripts_changesets()[0]
        self.assertIn("op:base 1", drafted)
        self.assertEqual(self.new("--force")[0], 0)
        before = self.record()
        code, out = self.apply(drafted)
        self.assertEqual(code, 1, out)
        self.assertIn("started over", out)
        self.assertIn("r2", out)
        self.assertEqual(self.record(), before)

    def test_the_kept_copy_never_overwrites_a_file(self):
        self.new()
        self.path("career/kb.r1.trig").write_text("someone else's", encoding="utf-8")
        old = self.record()
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.path("career/kb.r1.trig").read_text(encoding="utf-8"),
                         "someone else's")
        self.assertEqual(self.path("career/kb.r1-2.trig").read_text(encoding="utf-8"), old)
        self.assertIn("kb.r1-2.trig", out)

    def test_force_over_a_record_written_outside_jsk_is_refused(self):
        """The career's revision and its log's disagree: something other than jsk wrote the
        store, and starting over would erase what the log never saw."""
        self.new()
        graphs = db.read(self.root)
        R.write_graphs(self.root, {R.KB: R.stamp(graphs[R.KB], 5, TODAY)})
        before = self.record()
        code, out = self.new("--force")
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED", out)
        self.assertIn("nothing was written", out)
        self.assertEqual(self.record(), before)
        self.assertEqual(list(self.path("career").glob("kb.r*.trig")), [])

    def test_force_is_refused_where_an_application_carried_the_old_record(self):
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        storekit.seed(self.root)
        before = self.record()
        code, out = self.new("--force")
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED  starting over would leave", out)
        self.assertIn("nothing was written", out)
        self.assertEqual(self.record(), before)


class Direct(unittest.TestCase):
    def test_scaffold_takes_a_day(self):
        with tempfile.TemporaryDirectory() as root:
            code, lines = new.scaffold(root, "Ada Lovelace", today=TODAY)
            self.assertEqual(code, 0, lines)
            self.assertIn('j:updated "2026-09-25"^^xsd:date', storekit.kb_text(root))


if __name__ == "__main__":
    unittest.main()
