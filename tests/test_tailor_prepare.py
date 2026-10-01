"""jsk tailor prepare: the evidence phase of an assessment in one call - one digest where the
analyst used to make ten calls, each a model turn."""
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import appkit
from test_graph_shapes import FIXTURES

from jsk import cli
from jsk.application.tailor import prepare

APP = "applications/acme-platform-engineer"
TODAY = "2026-09-27"
SECTIONS = ["== check - ", "== match", "== evidence - ", "== person",
            "== bullets - ", "== unconfirmed - ", "== gaps"]


class Prepare(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        appkit.seed(self.root)

    def run_it(self, *extra, app=APP):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "tailor", "prepare", str(self.root / app),
                             "--today", TODAY, *extra])
        return code, out.getvalue()

    def edit(self, graph, old, new):
        text = appkit.text(self.root, graph)
        self.assertIn(old, text)
        appkit.put(self.root, graph, text.replace(old, new), prefixes=False)

    def test_every_section_in_order(self):
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        at = [out.find(s) for s in SECTIONS]
        self.assertNotIn(-1, at, out)
        self.assertEqual(at, sorted(at))
        self.assertIn("# Match - Platform Engineer at Acme Health", out)
        # The store has no layout, so there is no canonical-layout step to report.
        self.assertNotIn("== posting.ttl", out)
        self.assertNotIn("jsk kb fmt", out)

    def test_a_fail_in_another_application_does_not_stop_it(self):
        other = self.root / "applications/other"
        other.mkdir()
        appkit.put(self.root, "applications/other/posting",
                   'k:req_other_x j:posting k:post_nowhere ; j:asked "X" ;\n'
                   '    j:necessity j:required ; j:quote "X is required" .\n')
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"== check - applications/acme-platform-engineer, and any FAIL "
                              r"anywhere: [1-9]\d* FAIL")
        self.assertIn("== match", out)

    def test_the_posting_ttl_form_is_refused_with_the_application_form(self):
        code, out = self.run_it(app=f"{APP}/posting.ttl")
        self.assertEqual(code, 2, out)
        self.assertIn("takes the application now, not its posting.ttl", out)
        self.assertIn(f"fix:  jsk tailor prepare {self.root / APP}", out)

    def test_a_fail_in_its_own_directory_stops_it(self):
        self.edit(f"{APP}/posting", "j:posting k:post_acme_platform_engineer",
                  "j:posting k:post_acme_platform_engineeer")
        code, out = self.run_it()
        self.assertEqual(code, 1, out)
        self.assertIn("stop the match", out)
        self.assertNotIn("== match", out)

    def test_a_cut_section_says_so(self):
        old = prepare.CAP["match"]
        prepare.CAP["match"] = 3
        self.addCleanup(prepare.CAP.__setitem__, "match", old)
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"… \d+ more cut")

    def unsend(self):
        """The fixture's application was sent on 2026-09-10, which freezes its assessment:
        take its record away to tailor it afresh."""
        appkit.drop(self.root, f"{APP}/application")

    def test_a_sent_application_keeps_its_assessment_and_drafts_nothing(self):
        code, out = self.run_it("--draft-gaps")
        self.assertEqual(code, 0, out)
        self.assertIn("sent on 2026-09-10 - its assessment and gaps.md are frozen", out)
        self.assertIn("no gaps.txt drafted: the application is sent", out)
        self.assertFalse((self.root / APP / "gaps.txt").exists())
        self.assertFalse(appkit.has(self.root, f"{APP}/gaps"))

    def test_every_run_writes_the_assessment_with_no_agent(self):
        self.unsend()
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        app = self.root / APP
        self.assertTrue(appkit.has(self.root, f"{APP}/gaps") and (app / "gaps.md").exists())
        self.assertFalse((app / "gaps.ttl").exists() or (app / "gaps.txt").exists())
        self.assertRegex(out, rf"wrote {APP}/gaps and gaps\.md - fit (strong|partial|poor) by "
                              r"default; ")

    def test_the_draft_is_written_once(self):
        self.unsend()
        code, out = self.run_it("--draft-gaps")
        self.assertEqual(code, 0, out)
        gaps = self.root / APP / "gaps.txt"
        self.assertTrue(gaps.exists())
        self.assertIn("slots to fill", out)
        before = gaps.read_bytes()
        code, out = self.run_it("--draft-gaps")
        self.assertEqual(code, 0, out)
        self.assertIn("already exists - left as it is", out)
        # Half filled, its slots FAIL in the digest - which is not prepare failing.
        self.assertIn("unfilled slot", out)
        self.assertEqual(gaps.read_bytes(), before)

    def test_called_wrong(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["jsk", "tailor", "prepare"]), 2)
            self.assertEqual(cli.main(["jsk", "tailor", "prepare", str(self.root / "nowhere")]), 2)
            self.assertEqual(cli.main(["jsk", "tailor", "prepare", str(self.root / APP),
                                       "--cover", "0"]), 2)


if __name__ == "__main__":
    unittest.main()
