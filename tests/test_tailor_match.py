"""`jsk tailor match`, end to end on the match fixtures."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from fixtures import CLI, run


JSK = CLI


def match_workspace(tmp, edit=None):
    """tests/match_fixtures copied to `tmp`, `edit(root)` applied to its files, then put
    into its store. Returns the root."""
    import shutil

    from appkit import seed
    shutil.copytree(Path(__file__).parent / "match_fixtures", tmp, dirs_exist_ok=True)
    if edit:
        edit(Path(tmp))
    seed(tmp)
    return Path(tmp)


class Match(unittest.TestCase):
    """`jsk match APP`: an assessment, so it exits 0 with gaps; 1 only for a broken record."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.FIX = match_workspace(cls._tmp.name)
        cls.CONTOSO = cls.FIX / "applications" / "contoso"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_it_prints_the_four_sections(self):
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--today", "2026-09-24")
        self.assertEqual(code, 0, out)
        for heading in ("# Match - Platform Engineer at Contoso (k:post_contoso)",
                        "## Requirements", "## Ranking", "## Cover", "## Questions"):
            self.assertIn(heading, out)
        self.assertIn("| K8s | required | matched | satisfied | k:prj_data; k:prj_events "
                      "(via c:aks, 1 hop) |", out)

    def test_json_is_the_same_result_structured(self):
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--json", "--today", "2026-09-24")
        self.assertEqual(code, 0, out)
        r = json.loads(out)
        self.assertEqual(r["posting"], "k:post_contoso")
        self.assertEqual({q["asked"]: q["state"] for q in r["requirements"]}["Go"], "ambiguous")

    def test_a_broken_record_is_not_matched(self):
        def broken(root):
            kb = root / "career" / "kb.ttl"
            kb.write_text(kb.read_text(encoding="utf-8").replace("j:uses c:aks,", "j:uses c:akss,"),
                          encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = match_workspace(tmp, broken)
            code, out = run(JSK, "tailor", "match", root / "applications" / "contoso")
        self.assertEqual(code, 1, out)
        self.assertIn("fix them before matching", out)
        self.assertIn("c:akss: nothing defines it", out)

    def test_another_postings_fault_does_not_stop_this_one(self):
        """A FAIL in the career, the vocabulary or this application's own directory stops
        the match; one in an unrelated application only gets mentioned - an old advert
        that no longer quotes cleanly must not block every new one."""
        with tempfile.TemporaryDirectory() as tmp:
            root = match_workspace(tmp)
            md = root / "applications" / "fabrikam" / "posting.md"
            md.write_text("Senior Developer at Fabrikam\n", encoding="utf-8")
            code, out = run(JSK, "tailor", "match", root / "applications" / "contoso")
            self.assertEqual(code, 0, out)
            self.assertIn("4 failures elsewhere in the workspace", out)
            code, out = run(JSK, "tailor", "match", root / "applications" / "fabrikam")
            self.assertEqual(code, 1, out)

    def test_the_warnings_are_named_not_waved_away(self):
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--today", "2026-09-24")
        self.assertIn("1 warning (label-clash)", out)
        self.assertNotIn("none changes the match", out)

    def test_an_implied_carrier_says_so(self):
        code, out = run(JSK, "tailor", "match", self.FIX / "applications" / "northwind",
                        "--today", "2026-09-24")
        self.assertIn("k:prj_events (via c:kafka, 1 hop, implied)", out)

    def test_a_relative_path_from_inside_the_workspace(self):
        from jsk.application.tailor.match_posting import application
        here = os.getcwd()
        try:
            os.chdir(self.FIX)
            root, app = application(os.path.join("applications", "contoso"))
            self.assertEqual((root, app), (str(self.FIX), str(self.CONTOSO)))
        finally:
            os.chdir(here)

    def test_the_posting_ttl_form_is_refused_with_the_new_one(self):
        """Ruling 11: the posting is a graph now, not a file to point at."""
        code, out = run(JSK, "tailor", "match", self.CONTOSO / "posting.ttl")
        self.assertEqual(code, 2, out)
        self.assertIn("takes the application now, not its posting.ttl", out)
        self.assertIn(f"fix:  jsk tailor match {self.CONTOSO}", out)

    def test_gaps_txt_that_raises_a_verdict_fails(self):
        """--gaps checks the analyst's gaps.txt against the match: .NET is carried only by
        tags, so `satisfied` is a raise; `unsatisfied`, with its reason, is a lowering."""
        with tempfile.TemporaryDirectory() as tmp:
            app = match_workspace(tmp) / "applications" / "contoso"
            gaps = app / "gaps.txt"
            gaps.write_text("dotnet | satisfied | it is on the projects\n", encoding="utf-8")
            args = (JSK, "tailor", "match", app, "--gaps", gaps, "--today", "2026-09-24")
            code, out = run(*args)
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL  gaps.txt line 1: dotnet: satisfied, above the match's "
                          "unevidenced", out)
            self.assertIn("the career needs the tag or the confirmation", out)
            gaps.write_text("dotnet | unsatisfied | the tags are all there is\n",
                            encoding="utf-8")
            code, out = run(*args)
            self.assertEqual(code, 0, out)
            self.assertIn("0 FAIL, 0 WARN - wrote applications/contoso/gaps and gaps.md", out)

    def test_outside_the_layout_is_a_usage_error(self):
        code, out = run(JSK, "tailor", "match", self.FIX / "career")
        self.assertEqual(code, 2, out)
        code, out = run(JSK, "tailor", "match", self.CONTOSO, "--cover", "none")
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
