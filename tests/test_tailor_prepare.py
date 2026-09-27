"""jsk tailor prepare: the evidence phase of an assessment in one call - one digest where the
analyst used to make ten calls, each a model turn."""
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from test_graph_shapes import FIXTURES

from jsk import cli
from jsk.graph import prepare

APP = "applications/acme-platform-engineer"
TODAY = "2026-09-27"
SECTIONS = ["== posting.ttl", "== check - ", "== match", "== evidence - ", "== person",
            "== bullets - ", "== unconfirmed - ", "== gaps"]


class Prepare(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)

    def run_it(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "tailor", "prepare", str(self.root / APP),
                             "--today", TODAY, *extra])
        return code, out.getvalue()

    def edit(self, name, old, new):
        path = self.root / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def test_every_section_in_order(self):
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        at = [out.find(s) for s in SECTIONS]
        self.assertNotIn(-1, at, out)
        self.assertEqual(at, sorted(at))
        self.assertIn("# Match - Platform Engineer at Acme Health", out)
        self.assertIn("already canonical", out)

    def test_a_fail_in_another_application_does_not_stop_it(self):
        other = self.root / "applications/other"
        other.mkdir()
        (other / "posting.ttl").write_text(
            "@prefix j: <tag:jsk,2026:ns#> .\n@prefix k: <tag:jsk,2026:id/> .\n\n"
            'k:req_other_x j:posting k:post_nowhere ; j:asked "X" ;\n'
            '    j:necessity j:required ; j:quote "X is required" .\n', encoding="utf-8")
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"== check - applications/acme-platform-engineer, and any FAIL "
                              r"anywhere: [1-9]\d* FAIL")
        self.assertIn("== match", out)

    def test_a_fail_in_its_own_directory_stops_it(self):
        self.edit(f"{APP}/posting.ttl", "j:posting k:post_acme_platform_engineer",
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
        take application.ttl away to tailor it afresh."""
        (self.root / APP / "application.ttl").unlink()

    def test_a_sent_application_keeps_its_assessment_and_drafts_nothing(self):
        code, out = self.run_it("--draft-gaps")
        self.assertEqual(code, 0, out)
        self.assertIn("sent on 2026-09-10 - gaps.ttl and gaps.md are frozen", out)
        self.assertIn("no gaps.txt drafted: the application is sent", out)
        self.assertFalse((self.root / APP / "gaps.txt").exists())

    def test_every_run_writes_the_assessment_with_no_agent(self):
        self.unsend()
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        app = self.root / APP
        self.assertTrue((app / "gaps.ttl").exists() and (app / "gaps.md").exists())
        self.assertFalse((app / "gaps.txt").exists())
        self.assertRegex(out, r"wrote gaps\.ttl and gaps\.md - fit (strong|partial|poor) by "
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
