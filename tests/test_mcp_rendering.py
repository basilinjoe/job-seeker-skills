"""`jsk mcp`'s resume_check, resume_render, resume_preview and resume_fit: Rulings 2 and 5 of
docs/superpowers/plans/2026-10-04-mcp-first.md, which made `jsk resume check|render|preview|fit`
tools that call the entry points those commands called.

The rules pinned: each tool answers ok on a good target, and its `verdict` is the verdict line the
gate itself printed, never advice printed after it; resume_render, resume_preview and resume_fit say which files they wrote,
workspace-relative with forward slashes and sorted, the PDF only when one was asked for;
resume_check on a bad target is not ok and carries a FAIL with its fix; a relative path means
the workspace even when the server's working directory is somewhere else (captured.inside);
the server's working directory is put back after every call; and a workspace still laid out as
files is refused by each of the four, as by every tool.

TeX is faked (shipkit.fake_compile, margin_compile), so what runs is the real render, the real
gates and the real fitter. The fake writes its PDF with pymupdf, so every test skips without it.
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import careerkit
from shipkit import BROKEN, CONTACTED, GOOD, fake_compile, margin_compile
from test_mcp_server import HAS_MCP, Served, fails

HAS_PYMUPDF = importlib.util.find_spec("pymupdf") is not None
TARGET = "resumes/test"
OUT = "resumes/test"


@unittest.skipUnless(HAS_PYMUPDF, "pymupdf is not installed")
class Rendering(Served):
    """The claims fixture with a contact-detailed person and `resumes/test` selected, served
    from a working directory that is not the workspace."""

    def setUp(self):
        from jsk.adapters.mcp import server, session

        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", edits=[CONTACTED])
        careerkit.select(self.root, GOOD)
        self.session = session.Session(root=self.root)
        self.server = server.build(self.session)
        # The reason captured.inside exists: a relative path is the workspace's, not the
        # server's working directory's.
        elsewhere = Path(tmp.name) / "elsewhere"
        elsewhere.mkdir()
        before = os.getcwd()
        os.chdir(elsewhere)
        self.addCleanup(os.chdir, before)
        self.elsewhere = elsewhere

    def render(self, **args):
        from jsk.adapters.compose import render

        with mock.patch.object(render, "compile_pdf", fake_compile()):
            return self.call("resume_render", target=TARGET, **args)


class Check(Rendering):
    def test_a_target_passes_the_record_gate_and_the_verdict_is_its_pass_line(self):
        got = self.call("resume_check", target=TARGET)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["exit"], 0)
        self.assertEqual(got["verdict"], "PASS - safe to render")

    def test_a_selection_naming_a_bullet_the_career_lacks_is_not_ok_and_names_the_bullet(self):
        careerkit.select(self.root, BROKEN, name="broken")
        got = self.call("resume_check", target="resumes/broken")
        self.assertFalse(got["ok"], got)
        # The gate's own finding, not a bare "exited 1": the gate indents it under its tally,
        # which findings_in once missed, and this passed on the fallback FAIL alone.
        self.assertTrue(any("ach_nothing_like_it is not in the career" in text
                            for text in fails(got)), got)
        self.assertEqual(got["verdict"], "DO NOT RENDER - fix the failures above")

    def test_a_flag_the_targets_kind_does_not_take_is_refused_as_a_finding(self):
        # --pages fits a render's directory, not a target; ignoring it would read as a page
        # budget that was checked.
        got = self.call("resume_check", target=TARGET, pages=1)
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["exit"], 2)
        self.assertIn("--pages does not fit", got["output"])

    def test_a_render_in_the_workspace_is_found_by_a_relative_path(self):
        self.assertTrue(self.render(pdf=True)["ok"])
        pdf = next(p for p in (Path(self.root) / OUT).glob("*.pdf"))
        got = self.call("resume_check", target=f"{OUT}/{pdf.name}", only="parse")
        self.assertTrue(got["ok"], got)
        self.assertEqual(os.getcwd(), str(self.elsewhere.resolve()), "the directory came back")


class Render(Rendering):
    def test_a_render_writes_the_tex_into_the_targets_directory_and_lists_it(self):
        got = self.render()
        self.assertTrue(got["ok"], got)
        self.assertEqual(len(got["wrote"]), 1, got)
        [tex] = got["wrote"]
        self.assertTrue(tex.startswith(f"{OUT}/") and tex.endswith(".tex"), tex)
        self.assertTrue((Path(self.root) / tex).is_file())

    def test_a_pdf_is_listed_only_when_one_was_asked_for(self):
        got = self.render(pdf=True)
        self.assertTrue(got["ok"], got)
        self.assertEqual(sorted(os.path.splitext(p)[1] for p in got["wrote"]),
                         [".pdf", ".tex"])
        self.assertEqual(got["wrote"], sorted(got["wrote"]))
        self.assertNotIn("\\", "".join(got["wrote"]))

    def test_a_render_has_no_verdict_and_never_its_closing_advice(self):
        got = self.render(pdf=True)
        self.assertTrue(got["ok"], got)
        # The render prints no verdict line; its last line is advice on the gates to run, and
        # `verdict` once answered with it (the review, 2026-10-04).
        self.assertIsNone(got["verdict"], got)
        self.assertEqual(len(got["wrote"]), 2, got)
        # The advice names tool calls, not scripts that are no commands any more.
        self.assertIn('resume_check(target="', got["output"])
        self.assertIn('only="parse"', got["output"])
        self.assertIn('only="prose"', got["output"])
        self.assertNotIn(".py", got["output"].split("Now run the gates")[1])

    def test_out_dot_does_not_list_the_stores_files(self):
        from jsk.adapters.compose import render

        planted = Path(self.root) / "career" / "store" / "PLANTED-LOG"
        compile_pdf = fake_compile()

        def compile_and_touch(tex_path, out_dir):
            # A RocksDB file changing on its own while the render runs.
            planted.write_text("x", encoding="utf-8")
            return compile_pdf(tex_path, out_dir)

        with mock.patch.object(render, "compile_pdf", compile_and_touch):
            got = self.call("resume_render", target=TARGET, out=".", pdf=True)
        self.assertTrue(planted.is_file())
        self.assertTrue(got["ok"], got)
        self.assertTrue(got["wrote"], got)
        self.assertEqual([p for p in got["wrote"] if p.startswith(("career/store", ".jsk"))], [])

    def test_a_relative_out_is_inside_the_workspace_not_the_working_directory(self):
        got = self.render(out="drafts/one")
        self.assertTrue(got["ok"], got)
        [tex] = got["wrote"]
        self.assertTrue(tex.startswith("drafts/one/"), tex)
        self.assertTrue((Path(self.root) / tex).is_file())
        self.assertEqual(list(self.elsewhere.iterdir()), [], "nothing landed beside the server")

    def test_a_second_render_lists_only_what_it_changed(self):
        self.assertTrue(self.render(out="drafts/two")["ok"])
        again = self.render(out="drafts/two")
        # The same bytes are rewritten, but a file the call did not touch is never listed.
        stray = Path(self.root) / "drafts" / "two" / "stray.txt"
        stray.write_text("x", encoding="utf-8")
        third = self.render(out="drafts/two")
        self.assertTrue(again["ok"] and third["ok"])
        self.assertNotIn("drafts/two/stray.txt", third["wrote"])

    def test_a_target_that_is_nothing_fails_and_wrote_nothing(self):
        from jsk.adapters.compose import render

        with mock.patch.object(render, "compile_pdf", fake_compile()):
            got = self.call("resume_render", target="nonesuch/at/all")
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["wrote"], [])

    def test_an_unknown_template_is_a_call_error_with_nothing_written(self):
        got = self.render(template="nonesuch")
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["exit"], 2)
        self.assertEqual(got["wrote"], [])


class Preview(Rendering):
    def test_every_template_is_listed_under_the_out_directory(self):
        from jsk.adapters.compose import preview

        with mock.patch.object(preview, "compile_pdf", fake_compile()), \
                mock.patch.object(preview, "available_engine", lambda: "fake"):
            got = self.call("resume_preview", target=TARGET, out="looks")
        self.assertTrue(got["ok"], got)
        self.assertTrue(got["wrote"], got)
        self.assertTrue(all(p.startswith("looks/") for p in got["wrote"]), got["wrote"])
        self.assertTrue(any(p.endswith(".pdf") for p in got["wrote"]))
        self.assertTrue(any(p.endswith(".tex") for p in got["wrote"]))
        # The preview prints advice and no verdict line: `verdict` is None, not that advice.
        self.assertIsNone(got["verdict"], got)

    def test_a_target_that_is_nothing_fails_and_wrote_nothing(self):
        got = self.call("resume_preview", target="nonesuch/at/all", out="looks")
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["wrote"], [])


class Fit(Rendering):
    def fitted(self, fits_at, **args):
        """A render that is 3 pages long, then the fit, with TeX faked on both sides."""
        from jsk.adapters.compose import fit, render

        fake = margin_compile(fits_at)
        with mock.patch.object(render, "compile_pdf", fake), \
                mock.patch.object(fit, "compile_pdf", fake), \
                mock.patch.object(fit, "available_engine", lambda: "fake"):
            made = self.call("resume_render", target=TARGET, pdf=True)
            self.assertTrue(made["ok"], made)
            [tex] = [p for p in made["wrote"] if p.endswith(".tex")]
            return tex, self.call("resume_fit", tex=tex, **args)

    def test_a_fit_that_reaches_the_budget_passes_and_lists_the_fitted_tex(self):
        tex, got = self.fitted(fits_at=0.6)
        self.assertTrue(got["ok"], got)
        # The fit prints its advice after the PASS line: `verdict` is the PASS line, not the
        # advice a caller would otherwise read as the verdict (captured.VERDICTS).
        self.assertNotEqual(got["output"].strip().splitlines()[-1].strip(), got["verdict"])
        self.assertEqual(got["verdict"], "PASS - fits 2 pages")
        self.assertIn(tex.replace(".tex", "-fitted.tex"), got["wrote"])

    def test_a_fit_that_cannot_reach_the_budget_without_a_floor_is_not_ok(self):
        tex, got = self.fitted(fits_at=None)
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["exit"], 1)
        self.assertIn("FAIL - cannot reach 2 pages", got["output"])

    def test_a_pdf_is_refused_as_a_call_error(self):
        pdf = Path(self.root) / OUT / "x.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF-1.4\n")
        got = self.call("resume_fit", tex=f"{OUT}/x.pdf")
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["exit"], 2)
        self.assertIn("not a .tex", got["output"])
        self.assertEqual(got["wrote"], [])

    def test_an_argparse_refusal_answers_with_its_message_not_nothing_printed(self):
        # argparse prints to stderr and exits 2; stdout alone read "exited 2: nothing printed".
        # A tex that argparse reads as a flag leaves the positional missing.
        got = self.call("resume_fit", tex="--no-such-flag")
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["exit"], 2)
        self.assertIn("arguments are required: tex", got["output"])
        self.assertIn("arguments are required: tex", " ".join(fails(got)))
        self.assertNotIn("nothing printed", " ".join(fails(got)))

    def test_the_default_budget_is_the_commands_two_pages(self):
        from jsk.adapters.entry import fit

        self.assertEqual(fit.parse(["x.tex"]).target_pages, 2)


class WorkingDirectory(Rendering):
    def test_it_comes_back_when_an_entry_point_raises_or_exits(self):
        before = os.getcwd()
        with mock.patch("jsk.adapters.entry.resume.cmd_resume_check",
                        side_effect=RuntimeError("boom")):
            got = self.call("resume_check", target=TARGET)
        self.assertFalse(got["ok"], got)
        self.assertEqual(os.getcwd(), before)
        with mock.patch("jsk.adapters.entry.resume.cmd_resume_check",
                        side_effect=SystemExit(2)):
            got = self.call("resume_check", target=TARGET)
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["exit"], 2)
        self.assertEqual(os.getcwd(), before)


class Captured(unittest.TestCase):
    """captured.py's reading of what an entry point printed."""

    def test_a_render_s_lowercase_warn_line_is_a_warn_finding(self):
        from jsk.adapters.mcp import captured

        out = ("view: general\n  wrote  a.tex\n\nWARN 1\n  warn  [x/y] withheld bullet\n"
               "  fail  a sentence of prose\n")
        self.assertEqual(captured.findings_in(out),
                         [("WARN", "[x/y] withheld bullet", None)])
        answer = captured.answered(0, out)
        self.assertEqual([f["severity"] for f in answer["findings"]], ["WARN"])

    def test_stderr_is_appended_for_a_failed_call_only(self):
        from jsk.adapters.mcp import captured

        def refuses(args):
            print("out line")
            print("usage: bad", file=sys.stderr)
            return 2

        def passes(args):
            print("out line")
            print("chatter", file=sys.stderr)
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(captured.called(tmp, refuses, []),
                             (2, "out line\nusage: bad\n"))
            self.assertEqual(captured.called(tmp, passes, []), (0, "out line\n"))
            sink = io.StringIO()
            self.assertEqual(captured.called(tmp, refuses, [], err=sink), (2, "out line\n"))
            self.assertEqual(sink.getvalue(), "usage: bad\n")

    def test_a_string_exit_is_exit_2_with_its_message(self):
        from jsk.adapters.mcp import captured

        def exits(args):
            sys.exit("no such thing")

        with tempfile.TemporaryDirectory() as tmp:
            code, out = captured.called(tmp, exits, [])
        self.assertEqual((code, out.strip()), (2, "no such thing"))

    def test_ran_captures_stderr_the_same_way(self):
        from jsk.adapters.mcp import captured

        with tempfile.TemporaryDirectory() as tmp:
            code, out = captured.ran(tmp, "fit_pages.py", ["--no-such-flag"])
        self.assertEqual(code, 2)
        self.assertIn("arguments are required: tex", out)

    def test_no_verdict_line_is_no_verdict(self):
        from jsk.adapters.mcp import captured

        advice = captured.answered(0, "wrote a\n  resume_check(target=1)\n")
        self.assertIsNone(advice["verdict"])
        said = captured.answered(0, "x\nPASS - ok\nadvice\n")
        self.assertEqual(said["verdict"], "PASS - ok")


@unittest.skipUnless(HAS_MCP, "the mcp package is not installed")
class Unloaded(Served):
    """A workspace still laid out as files is refused by all four, as by every tool."""

    def setUp(self):
        from jsk.adapters.mcp import server, session

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(Path(__file__).parent / "match_fixtures", self.root,
                        dirs_exist_ok=True)
        self.server = server.build(session.Session(root=str(self.root)))

    def test_each_tool_is_refused_naming_kb_load_and_writes_nothing(self):
        for tool, args in (("resume_check", {"target": TARGET}),
                           ("resume_render", {"target": TARGET}),
                           ("resume_preview", {"target": TARGET, "out": "looks"}),
                           ("resume_fit", {"tex": "x.tex"})):
            with self.subTest(tool=tool):
                said = self.call(tool, **args)
                self.assertFalse(said["ok"], said)
                [finding] = said["findings"]
                self.assertIn("the career is still career/kb.ttl", finding["text"])
                self.assertIn("jsk kb load .", finding["fix"])
        self.assertFalse((self.root / "looks").exists())
        self.assertFalse((self.root / "career" / "store").exists())


if __name__ == "__main__":
    unittest.main()
