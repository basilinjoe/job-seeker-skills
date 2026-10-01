"""`jsk kb load`: a workspace's files into a new store, and the checks on what it
is given.
"""
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import storekit
from test_graph_shapes import FIXTURES

from jsk import cli
from jsk.infra.oxigraph import db, record
from jsk.adapters.cli.compose import record as S


class Load(unittest.TestCase):
    """`jsk kb load`: an empty store filled once - from a workspace still laid out as files,
    or from a dump."""

    APP = "applications/acme-platform-engineer"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.files = os.path.join(self.tmp, "files")        # a workspace not yet loaded
        shutil.copytree(FIXTURES, self.files)
        self.empty = os.path.join(self.tmp, "empty")
        os.makedirs(self.empty)

    def documents(self):
        """The application's documents copied into the empty workspace, as a person moving
        a record would: they are files beside the record, not in it."""
        os.makedirs(os.path.join(self.empty, self.APP))
        shutil.copy(os.path.join(self.files, self.APP, "posting.md"),
                    os.path.join(self.empty, self.APP, "posting.md"))

    def kb(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", *args, "--root", root])
        return code, out.getvalue()

    def edit(self, old, new, file="career/kb.ttl"):
        path = Path(self.files, file)
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def test_a_workspace_of_files_loads_in_place_and_its_files_are_no_longer_read(self):
        kb = Path(self.files, "career/kb.ttl")
        before = kb.read_bytes()
        here = os.getcwd()
        os.chdir(self.files)                                        # `jsk kb load .`, as the fix says
        self.addCleanup(os.chdir, here)
        code, out = self.kb(self.files, "load", ".")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"loaded   \d+ triples in 4 graphs into career/store/, at r3")
        self.assertIn("career/kb.ttl and the other .ttl files are no longer read", out)
        self.assertNotIn("not in this workspace", out)
        self.assertEqual(kb.read_bytes(), before)                  # left where it is
        s = S.load(self.files)
        self.assertTrue(s.stored)
        self.assertEqual(record.state(s).kind, "clean")
        self.assertEqual(sorted(s.parsed), ["applications/acme-platform-engineer/application",
                                            "applications/acme-platform-engineer/posting",
                                            "kb", "log", "vocabulary"])
        kb.write_text(before.decode("utf-8").replace('"Meridian Health"', '"Elsewhere"'),
                      encoding="utf-8")
        self.assertNotIn("Elsewhere", storekit.kb_text(self.files))

    def test_a_number_the_store_would_rewrite_is_kept_by_value_and_said(self):
        self.edit("    j:value 42 ;", "    j:value 42.0 ;")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"number   kb k:met_\w+\.v1 j:value 42\.0 kept as 42\n")

    def test_a_workspace_with_a_fail_is_refused_and_nothing_is_stored(self):
        self.edit("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 1, out)
        self.assertIn("did you mean k:met_team?", out)
        self.assertIn("nothing was written", out)
        self.assertFalse(db.exists(self.empty))

    def test_a_store_that_holds_a_record_is_refused(self):
        self.assertEqual(self.kb(self.empty, "load", self.files)[0], 0)
        before = db.dump_text(db.read(self.empty))
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 1, out)
        self.assertIn("already holds a record", out)
        self.assertEqual(db.dump_text(db.read(self.empty)), before)

    def test_a_dump_loads_back_to_the_same_record(self):
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        self.documents()
        dump = os.path.join(self.tmp, "career.trig")
        code, out = self.kb(self.files, "dump", "--out", dump)
        self.assertEqual(code, 0, out)
        code, out = self.kb(self.empty, "load", dump)
        self.assertEqual(code, 0, out)
        self.assertIn("at r3", out)                 # the fixture's r2, and the import's entry
        self.assertNotIn("note", out)
        self.assertEqual(db.dump_text(db.read(self.empty)), db.dump_text(db.read(self.files)))
        self.assertEqual(self.kb(self.empty, "view"), self.kb(self.files, "view"))
        self.assertEqual(self.kb(self.empty, "check")[0], 0)

    def test_the_import_is_logged_as_one_entry_of_its_own(self):
        """By j:load, holding the career's hash: so every store's newest entry hashes its
        career, and a dump of an imported workspace loads back."""
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn("at r3", out)
        s = S.load(self.empty)
        self.assertEqual(record.state(s).kind, "clean")
        self.assertIsNone(record.unrecorded(s.graph(record.KB), s.graph(record.LOG)))
        code, out = self.kb(self.empty, "log", "--last", "1")
        self.assertRegex(out, r"^r3  \d{4}-\d\d-\d\d  load     Imported from the files by jsk kb "
                              r"load: 4 graphs, 0 numbers kept by value")

    def dumped(self):
        """An imported workspace, dumped: (its dump's path, the dump's text)."""
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        dump = os.path.join(self.tmp, "career.trig")
        self.assertEqual(self.kb(self.files, "dump", "--out", dump)[0], 0)
        return dump, Path(dump).read_text(encoding="utf-8")

    def test_an_imported_workspace_dumps_and_loads_back(self):
        dump, _ = self.dumped()
        self.documents()
        code, out = self.kb(self.empty, "load", dump)
        self.assertEqual(code, 0, out)
        code, out = self.kb(self.empty, "check")
        self.assertEqual(code, 0, out)

    def refused_dump(self, old, new):
        dump, text = self.dumped()
        self.assertIn(old, text)
        Path(dump).write_text(text.replace(old, new, 1), encoding="utf-8")
        code, out = self.kb(self.empty, "load", dump)
        self.assertEqual(code, 1, out)
        self.assertIn("nothing was written", out)
        self.assertFalse(db.exists(self.empty))
        return out

    def test_a_dump_whose_provenance_was_raised_is_refused(self):
        out = self.refused_dump("<tag:jsk,2026:ns#provenance> <tag:jsk,2026:ns#inferred>",
                                "<tag:jsk,2026:ns#provenance> <tag:jsk,2026:ns#confirmed>")
        self.assertIn("not what its log last recorded", out)
        self.assertIn("jsk kb apply", out)

    def test_a_dump_whose_number_was_changed_is_refused(self):
        out = self.refused_dump('<tag:jsk,2026:ns#value> 42 .', '<tag:jsk,2026:ns#value> 43 .')
        self.assertIn("not what its log last recorded", out)

    def test_a_dump_holding_a_number_the_store_would_rewrite_names_it(self):
        out = self.refused_dump('<tag:jsk,2026:ns#value> 42 .',
                                '<tag:jsk,2026:ns#value> "42.0"^^<http://www.w3.org/2001/XMLSchema#decimal> .')
        self.assertIn("j:value 42.0 is kept as 42", out)

    def test_a_hand_edited_kb_ttl_is_imported_with_its_warning_and_what_it_raised(self):
        self.edit("j:provenance j:inferred", "j:provenance j:confirmed")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN", out)
        self.assertIn("changed outside `jsk kb`", out)
        # No copy of the logged revision to compare with: said, not guessed.
        self.assertIn("nothing to compare", out)

    def test_what_a_hand_edit_raised_is_listed_against_the_shadow_copy(self):
        shadow = Path(self.files, ".jsk", "kb.last.ttl")
        shadow.parent.mkdir(exist_ok=True)
        shadow.write_bytes(Path(self.files, "career/kb.ttl").read_bytes())
        self.edit("j:cites k:met_sites ;\n    j:provenance j:inferred .",
                  "j:cites k:met_sites ;\n    j:provenance j:confirmed .")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn("raised   k:ach_site_onboarding_sites_one_platform: inferred -> confirmed",
                      out)
        self.assertNotIn("k:prj_site_onboarding:", out)

    def test_elsewhere_an_application_s_documents_are_named_to_copy(self):
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn(f"note     {self.APP}: its documents (posting.md", out)
        self.assertIn("failures in applications - `jsk kb check` lists them", out)
        self.assertEqual(self.kb(self.empty, "check")[0], 1)          # until it is copied

    def test_the_backup_every_write_leaves_is_a_dump(self):
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        code, out = self.kb(self.empty, "load", os.path.join(self.files, record.BACKUP))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.kb(self.empty, "view"), self.kb(self.files, "view"))

    def test_a_dump_to_stdout_is_what_the_store_holds(self):
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        code, out = self.kb(self.files, "dump")
        self.assertEqual(code, 0)
        self.assertEqual(out, db.dump_text(db.read(self.files)))

    def test_what_is_not_a_record_is_refused(self):
        bad = os.path.join(self.tmp, "bad.trig")
        Path(bad).write_text("<tag:a> <tag:b> <tag:c> .\n", encoding="utf-8")
        code, out = self.kb(self.empty, "load", bad)
        self.assertEqual(code, 1, out)
        self.assertIn("outside any record graph", out)
        Path(bad).write_text("this is not trig", encoding="utf-8")
        code, out = self.kb(self.empty, "load", bad)
        self.assertEqual(code, 1, out)
        self.assertFalse(db.exists(self.empty))
        self.assertEqual(self.kb(self.empty, "load", self.empty)[0], 2)     # no kb.ttl in it
        self.assertEqual(self.kb(self.empty, "load")[0], 2)

    def test_a_dump_with_no_store_is_refused(self):
        code, out = self.kb(self.empty, "dump")
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb load", out)


if __name__ == "__main__":
    unittest.main()
