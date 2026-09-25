"""`jsk new`: a graph workspace from nothing, that `jsk kb apply` can write to at once.

P3's Ruling 9: writes need a clean record, so a workspace has to start logged. These
tests hold `jsk new` to that - the scaffold loads with no finding, is clean at r1, is in
the canonical layout, and takes docs/SCRIPTS.md's braindump changeset as written.
"""
import contextlib
import datetime
import io
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from fixtures import REPO_ROOT as REPO
from test_graph_shapes import FIXTURES

from jsk import cli, kb
from jsk.graph import changeset
from jsk.graph import ontology as O
from jsk.graph import record as R
from jsk.graph import store as S
from jsk.graph.writer import write

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
            code = cli.main(["jsk", "new", self.root, "--name", "Priya Raman", *args])
        return code, out.getvalue()

    def kb(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue()

    def apply(self, text):
        cs = self.path("changes.trig")
        cs.write_text(text, encoding="utf-8")
        return self.kb("apply", str(cs))


class FromNothing(Scaffold):
    def test_it_writes_the_workspace(self):
        code, out = self.new()
        self.assertEqual(code, 0, out)
        for name in (kb.KB, kb.LOG, "applications/README.md", ".gitattributes"):
            with self.subTest(file=name):
                self.assertTrue(self.path(name).is_file(), out)
        self.assertIn("(r1, by new)", out)
        self.assertFalse(self.path("user-knowledgebase.md").exists())
        self.assertFalse(self.path("log.md").exists())

    def test_the_record_loads_clean_at_r1_with_no_finding(self):
        self.new()
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.findings], [])
        st = R.state(store)
        self.assertEqual((st.kind, st.kb_revision, st.log_revision), ("clean", 1, 1))

    def test_it_is_the_writers_own_layout_with_every_banner(self):
        self.new()
        text = self.path(kb.KB).read_text(encoding="utf-8")
        store = S.load(self.root)
        self.assertEqual(write(store.graph(R.KB), "kb"), text)
        banners = re.findall(r"^# == (.+)$", text, re.M)
        self.assertEqual(tuple(banners), O.SECTIONS["kb"])
        self.assertIn('j:name "Priya Raman"', text)
        self.assertNotIn("\r", text)

    def test_the_log_says_jsk_new_wrote_it(self):
        self.new()
        log = self.path(kb.LOG).read_text(encoding="utf-8")
        self.assertIn("j:by j:new", log)
        self.assertIn("k:rev_1 ", log)

    def test_the_gitattributes_keep_record_files_lf(self):
        self.new()
        lines = self.path(".gitattributes").read_text(encoding="utf-8").splitlines()
        for rule in ("*.ttl text eol=lf", "*.trig text eol=lf"):
            self.assertIn(rule, lines)

    def test_an_existing_gitattributes_is_added_to_never_replaced(self):
        self.path(".gitattributes").write_text("*.pdf binary", encoding="utf-8")
        self.new()
        lines = self.path(".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["*.pdf binary", "*.ttl text eol=lf", "*.trig text eol=lf"])
        self.new("--force")
        again = self.path(".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertEqual(again, lines)

    def test_doctor_finds_the_new_record(self):
        from jsk import preflight

        self.new()
        checks, found = preflight.gather(self.root)
        check = next(c for c in checks if c.name.startswith("knowledge base"))
        self.assertTrue(check.ok, check.disables)
        self.assertEqual(Path(found), self.path(kb.KB))
        self.assertEqual(Path(preflight.find_kb(self.root)), self.path(kb.KB))

    def test_a_name_is_required(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "new", self.root])
        self.assertEqual(code, 2)
        self.assertIn("--name is required", out.getvalue())
        self.assertFalse(self.path(kb.KB).exists())


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
        text = self.path(kb.KB).read_text(encoding="utf-8")
        self.assertIn("k:prj_payments", text)
        self.assertIn("k:ach_payments_", text)            # the bullet got its id

    def test_every_changeset_in_the_docs_parses(self):
        """The others name entries a new workspace does not have, so they are read, not
        applied: a block that does not parse is one nobody can copy."""
        blocks = scripts_changesets()
        self.assertGreaterEqual(len(blocks), 2)
        for n, block in enumerate(blocks):
            with self.subTest(block=n):
                cs = changeset.read(block, f"block{n}.trig")
                self.assertIsNotNone(cs.base)


class Refusals(Scaffold):
    def test_an_existing_record_is_refused_and_untouched(self):
        self.new()
        before = {n: self.path(n).read_bytes() for n in (kb.KB, kb.LOG)}
        code, out = self.new()
        self.assertEqual(code, 1)
        self.assertIn("REFUSED  already exists", out)
        self.assertIn("jsk kb apply", out)
        self.assertEqual({n: self.path(n).read_bytes() for n in (kb.KB, kb.LOG)}, before)

    def test_a_markdown_career_is_pointed_at_migrate(self):
        self.path("user-knowledgebase.md").write_text("---\nkb: 2\n---\n", encoding="utf-8")
        code, out = self.new()
        self.assertEqual(code, 1)
        self.assertIn("jsk migrate", out)
        self.assertFalse(self.path(kb.KB).exists())

    def test_force_starts_an_empty_record_beside_a_markdown_one(self):
        self.path("user-knowledgebase.md").write_text("---\nkb: 2\n---\n", encoding="utf-8")
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.path("user-knowledgebase.md").exists())


class Force(Scaffold):
    def test_force_starts_over_as_the_next_revision_and_keeps_the_log(self):
        self.new()
        code, out = self.apply(scripts_changesets()[0])
        self.assertEqual(code, 0, out)
        old_log = self.path(kb.LOG).read_text(encoding="utf-8")
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        self.assertIn("(r3, by new)", out)
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.fails()], [])
        st = R.state(store)
        self.assertEqual((st.kind, st.kb_revision), ("clean", 3))
        log = self.path(kb.LOG).read_text(encoding="utf-8")
        for entry in ("k:rev_1 ", "k:rev_2 ", "k:rev_3 "):
            self.assertIn(entry, log)
        self.assertIn(old_log.split("# == Log\n", 1)[1].strip(), log)
        self.assertNotIn("k:prj_payments", self.path(kb.KB).read_text(encoding="utf-8"))

    def hand_edit(self):
        """A confirmed k:person typed straight into kb.ttl, not adopted."""
        path = self.path(kb.KB)
        path.write_text(path.read_text(encoding="utf-8") +
                        '\nk:person j:fullName "Priya Raman" ; j:email "priya@example.com" ; '
                        'j:phone "+61 400 000 000" ; j:provenance j:confirmed .\n',
                        encoding="utf-8", newline="\n")

    def test_force_over_a_hand_edit_is_refused_until_it_is_adopted(self):
        """The log would never have seen the edit, and the empty record would erase it."""
        self.new()
        self.hand_edit()
        before = {n: self.path(n).read_bytes() for n in (kb.KB, kb.LOG)}
        code, out = self.new("--force")
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED", out)
        self.assertIn("jsk kb adopt", out)
        self.assertIn("nothing was written", out)
        self.assertNotRegex(out, r"\bgit\b")
        self.assertEqual({n: self.path(n).read_bytes() for n in (kb.KB, kb.LOG)}, before)
        self.assertEqual(list(self.path("career").glob("kb.r*.ttl")), [])

    def test_force_over_a_torn_record_is_refused(self):
        self.new()
        store = S.load(self.root)
        text = write(R.stamp(store.graph(kb.KB), 2, TODAY), "kb")
        self.path(kb.KB).write_text(text, encoding="utf-8", newline="\n")
        code, out = self.new("--force")
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb adopt", out)

    def test_force_keeps_the_replaced_record_beside_it(self):
        """No git, no shadow: the only copy of what --force replaces is the one it keeps."""
        self.new()
        self.hand_edit()
        code, out = self.kb("adopt")
        self.assertEqual(code, 0, out)
        old = self.path(kb.KB).read_bytes()
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        kept = self.path("career/kb.r2.ttl")
        self.assertEqual(kept.read_bytes(), old)
        self.assertIn("k:person", kept.read_text(encoding="utf-8"))
        self.assertIn("kb.r2.ttl", out)
        self.assertNotRegex(out, r"\bgit\b")
        self.assertNotIn("k:person", self.path(kb.KB).read_text(encoding="utf-8"))
        log = self.path(kb.LOG).read_text(encoding="utf-8")
        self.assertIn("career/kb.r2.ttl", log)
        self.assertNotRegex(log, r"\bgit\b")

    def test_the_kept_copy_is_not_a_record_file(self):
        from jsk import preflight

        self.new()
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.path("career/kb.r1.ttl").is_file())
        files = [Path(f) for f in S.workspace_files(self.root, vocabulary=None)]
        self.assertEqual(files, [self.path(kb.KB), self.path(kb.LOG)])
        self.assertEqual(Path(preflight.find_kb(self.root)), self.path(kb.KB))
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.fails()], [])
        self.assertEqual(R.state(store).kind, "clean")

    def test_the_kept_copy_never_overwrites_a_file(self):
        self.new()
        self.path("career/kb.r1.ttl").write_text("someone else's", encoding="utf-8")
        old = self.path(kb.KB).read_bytes()
        code, out = self.new("--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.path("career/kb.r1.ttl").read_text(encoding="utf-8"),
                         "someone else's")
        self.assertEqual(self.path("career/kb.r1-2.ttl").read_bytes(), old)
        self.assertIn("kb.r1-2.ttl", out)

    def test_the_refusal_over_an_existing_record_does_not_promise_git(self):
        self.new()
        code, out = self.new()
        self.assertEqual(code, 1, out)
        self.assertNotRegex(out, r"\bgit\b")
        self.assertIn("kept", out)

    def test_force_is_refused_where_an_application_carried_the_old_record(self):
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        before = self.path(kb.KB).read_bytes()
        code, out = self.new("--force")
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED  starting over would leave", out)
        self.assertIn("nothing was written", out)
        self.assertEqual(self.path(kb.KB).read_bytes(), before)

    def test_force_is_refused_over_a_log_that_does_not_parse(self):
        self.new()
        self.path(kb.LOG).write_text("this is not turtle", encoding="utf-8")
        code, out = self.new("--force")
        self.assertEqual(code, 1, out)
        self.assertIn("does not parse", out)


NAMES = ("Priya Raman", 'Dana "DJ" O\'Neil', "Zoë Ñúñez-Łukasz 王秀英", "C:\\path\\like",
         "A " + "very " * 40 + "long name")


class WithoutPyoxigraph(unittest.TestCase):
    """A sandbox that cannot install pyoxigraph can still start: `jsk new` writes the
    empty record from fixed text, and changesets are drafted for later (SKILL.md)."""

    def test_the_fixed_text_is_the_writers_output_byte_for_byte(self):
        for name in NAMES:
            with self.subTest(name=name):
                self.assertEqual(kb.plain_first_write(name, TODAY), kb.first_write("", name, TODAY))

    def test_jsk_new_starts_a_workspace_with_no_pyoxigraph(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("sys.modules", {"pyoxigraph": None}):
                code, lines = kb.scaffold(tmp, "Priya Raman", today=TODAY)
            self.assertEqual(code, 0, lines)
            self.assertTrue(any("pyoxigraph" in line for line in lines))
            s = S.load(tmp)
            self.assertEqual([f.text() for f in s.findings], [])
            self.assertEqual(R.state(s).kind, "clean")

    def test_force_still_needs_pyoxigraph(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            kb.scaffold(tmp, "Priya Raman", today=TODAY)
            with mock.patch.dict("sys.modules", {"pyoxigraph": None}):
                code, lines = kb.scaffold(tmp, "Priya Raman", force=True, today=TODAY)
            self.assertEqual(code, 1)
            self.assertIn("needs pyoxigraph", "\n".join(lines))


class Direct(unittest.TestCase):
    def test_empty_record_is_the_header_and_the_banners(self):
        text = kb.empty_record("Ada Lovelace", TODAY)
        self.assertIn('k:kb j:format 3 ; j:name "Ada Lovelace" ; j:updated "2026-09-25"^^xsd:date'
                      ' ; j:revision 1 .', text)
        self.assertEqual(len(re.findall(r"^# == ", text, re.M)), len(O.SECTIONS["kb"]))

    def test_scaffold_takes_a_day(self):
        with tempfile.TemporaryDirectory() as root:
            code, lines = kb.scaffold(root, "Ada Lovelace", today=TODAY)
            self.assertEqual(code, 0, lines)
            text = (Path(root) / kb.KB).read_text(encoding="utf-8")
            self.assertIn('"2026-09-25"^^xsd:date', text)
            self.assertTrue(os.path.isfile(os.path.join(root, ".jsk", "kb.last.ttl")))


if __name__ == "__main__":
    unittest.main()
