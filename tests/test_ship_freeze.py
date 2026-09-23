"""`jsk ship` and `jsk freeze`, the two commands mode-ship.md used to spell out as a
procedure for an agent to follow by hand.

Neither owns a verdict. ship strings together three that already exist - the record
gate, the render, the mechanical gates - and freeze refuses to archive anything they
would not pass. What these tests pin is the order, the stopping, and the one gate
both of them have to say out loud that they did not run.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixtures import (CLI, CLEAN_RESUME, build_pdf, build_text, run, urs_doc,
                      write_urs)

JSK = CLI
BAD = "Scaled the platform to [NUMBER] tenants."
TEX_PREAMBLE = "\\documentclass{article}\n\\begin{document}\n"


def fake_compile(pages=1, fail=False):
    """A compile_pdf that writes a PDF without a TeX engine.

    The words are CLEAN_RESUME's, which is what the parse gate reads from it; the
    .tex and .txt the renderer really wrote are what the prose gate reads.
    """
    def compile_pdf(tex_path, out_dir):
        from jsk.urs import tex
        if fail:
            return None, "UNVERIFIED - fake produced no PDF"
        pdf = tex.pdf_path_for(tex_path, out_dir)
        build_pdf(pdf, CLEAN_RESUME)
        if pages > 1:
            import pymupdf
            with pymupdf.open(pdf) as doc:
                for _ in range(pages - 1):
                    doc.new_page()
                doc.save(pdf + ".tmp")
            Path(pdf + ".tmp").replace(pdf)
        return pdf, "compiled with fake"
    return compile_pdf


class ShipCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.record = write_urs(self.tmp, urs_doc())
        self.out = self.tmp / "out"

    def ship(self, *extra, compile_pdf=None, view="view_default"):
        """cli.main() in this interpreter, with the TeX compile faked."""
        from jsk import cli
        from jsk.urs import render_resume
        args = ["jsk", "ship", str(self.record), "--out", str(self.out)]
        args += ["--view", view] if view else []
        buf = io.StringIO()
        with mock.patch.object(render_resume, "compile_pdf",
                               compile_pdf or fake_compile()), \
                contextlib.redirect_stdout(buf):
            code = cli.main(args + [str(a) for a in extra])
        return code, buf.getvalue()

    def headings(self, out):
        return [line[4:].split(":")[0] for line in out.splitlines()
                if line.startswith("--- ")]


class ShipOrder(ShipCase):
    """Record gate, render, mechanical gates - in that order, one process."""

    def test_a_clean_ship_runs_every_step_and_exits_0(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.headings(out),
                         ["record gate", "render", "parse gate", "parse gate",
                          "prose gate", "prose gate", "render gate"], out)
        self.assertIn("PASS - safe to render", out)
        self.assertIn("PASS - safe to send", out)
        self.assertIn("PASS - prose rules satisfied", out)

    def test_the_record_gate_runs_once(self):
        """Step three is what `jsk gates` runs, less the record gate step one has
        just run on the same file and would have stopped at."""
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("--- record gate"), 1, out)

    def test_each_steps_output_is_verbatim(self):
        """The render's own lines, not a summary of them: the page report included,
        because ship reports the page count and never fails on it."""
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("  pages  Test_Person_Resume.pdf: 1 page against a budget of 2", out)
        self.assertIn("  note   compiled with fake", out)

    def test_flags_reach_the_render(self):
        code, out = self.ship("--ats-max", "--template", "ember")
        self.assertEqual(code, 0, out)
        self.assertIn("--pdf --ats-max --template ember", out)
        self.assertTrue((self.out / "Test_Person_Resume_ATS.pdf").exists())
        self.assertIn("template: ember", out)


class ShipGatesOnlyItsOwnRender(ShipCase):
    """A directory keeps every earlier render. `--ats-max` after a default ship left
    both PDFs side by side, and gating the directory failed the second ship on a
    file it never made - then told the person to open that one."""

    def test_a_second_ship_gates_what_it_wrote_and_nothing_older(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.out / "Test_Person_Resume.pdf").exists())
        code, out = self.ship("--ats-max")
        self.assertEqual(code, 0, out)
        self.assertNotIn("check_ats.py Test_Person_Resume.pdf", out)
        self.assertNotIn("check_prose.py Test_Person_Resume.tex", out)
        self.assertIn("check_ats.py Test_Person_Resume_ATS.pdf", out)
        self.assertIn("open Test_Person_Resume_ATS.pdf", out)


class ShipStops(ShipCase):
    """A step that fails stops the ones after it. A record that fails its gate is
    never rendered: the PDF it would make looks sendable and is not."""

    def test_a_failing_record_renders_nothing(self):
        self.record = write_urs(self.tmp, urs_doc(views=[]))
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT RENDER", out)
        self.assertEqual(self.headings(out), ["record gate", "render gate"], out)
        self.assertFalse(self.out.exists() and any(self.out.iterdir()),
                         "a record that failed its gate was rendered")

    def test_a_stale_pdf_is_not_offered_for_reading_after_a_stop(self):
        """render_section() names the PDF in the directory. After a stop that PDF is
        an earlier run's, and telling somebody to read it is telling them to check a
        document this ship never made."""
        self.out.mkdir()
        build_pdf(self.out / "Old_Resume.pdf", CLEAN_RESUME)
        self.record = write_urs(self.tmp, urs_doc(views=[]))
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertNotIn("Old_Resume.pdf", out)
        self.assertIn("UNVERIFIED", out)

    def test_a_failed_render_stops_before_the_gates(self):
        code, out = self.ship(compile_pdf=fake_compile(fail=True))
        self.assertEqual(code, 1, out)
        self.assertIn("UNVERIFIED - --pdf was requested and no PDF was produced", out)
        self.assertNotIn("--- parse gate", out)
        self.assertEqual(self.headings(out)[-1], "render gate", out)

    def test_a_failing_document_gate_fails_the_ship(self):
        from jsk.urs import emit_text
        real = emit_text.emit
        with mock.patch.object(emit_text, "emit",
                               lambda rendered: real(rendered) + BAD + "\n"):
            code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)


class ShipRenderGate(ShipCase):
    """The trailer `jsk gates` ends with, and for the same reason."""

    def test_a_clean_ship_still_says_the_pdf_is_unread(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        render = out.split("--- render gate")[1]
        self.assertIn("UNVERIFIED", render)
        self.assertIn("read every page", render)
        self.assertNotIn("PASS", render)

    def test_over_budget_is_reported_and_never_failed(self):
        """`jsk fit` owns the page verdict. ship names an overrun and exits 0."""
        code, out = self.ship("--pages", "1", compile_pdf=fake_compile(pages=3))
        self.assertEqual(code, 0, out)
        self.assertIn("OVER BUDGET", out)

    def test_the_json_form_carries_every_step_and_the_render_gate(self):
        code, out = self.ship("--json")
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        self.assertEqual(report["exit"], 0)
        gates = [step["gate"] for step in report["steps"]]
        self.assertEqual(gates[:2], ["record gate", "render"])
        self.assertEqual(report["steps"][-1]["status"], "UNVERIFIED")
        self.assertIn("wrote  Test_Person_Resume.pdf", report["steps"][1]["output"])


class ShipUsage(ShipCase):
    def test_the_view_is_required(self):
        code, out = self.ship(view=None)
        self.assertEqual(code, 2, out)
        self.assertIn("--view is required", out)

    def test_the_out_directory_is_required(self):
        code, out = run(JSK, "ship", self.record, "--view", "view_default")
        self.assertEqual(code, 2, out)
        self.assertIn("--out is required", out)

    def test_an_unknown_template_is_a_call_error_before_anything_runs(self):
        code, out = self.ship("--template", "nope")
        self.assertEqual(code, 2, out)
        self.assertNotIn("--- record gate", out)

    def test_an_unknown_flag_is_a_call_error(self):
        code, out = self.ship("--recheck")
        self.assertEqual(code, 2, out)
        self.assertIn("usage: jsk ship", out)

    def test_the_knowledge_base_is_refused_as_validate_refuses_it(self):
        kb = self.tmp / "user-knowledgebase.md"
        kb.write_text("# Career knowledge base", encoding="utf-8")
        code, out = run(JSK, "ship", kb, "--out", self.out, "--view", "view_default")
        self.assertEqual(code, 2, out)
        self.assertIn("pass resume.json", out)

    def test_pages_must_be_a_number(self):
        code, out = self.ship("--pages", "two")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


# --- jsk freeze ----------------------------------------------------------------

POSTING = """---
company: Acme Health
title: Platform Engineer
url: https://example.com/job/1
requirements:
  - title: not the title
captured: 2026-09-01
---

The advertisement, verbatim.
"""

EXPECTED = """---
company: Acme Health
title: Platform Engineer
view: view_default
submitted: 2026-09-08
channel: Workday portal
documents:
  - Jane_Doe_Resume.pdf
  - Jane_Doe_Resume_ATS.txt
---

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-09-08 | submitted | Workday portal | | |
"""


class FreezeCase(unittest.TestCase):
    """One application directory as mode-tailor.md leaves it: posting, gaps, record
    and the files a render wrote - built without a TeX engine."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.apps = self.tmp / "applications"
        self.app = self.apps / "2026-09-01-acme-platform"
        self.app.mkdir(parents=True)
        (self.app / "posting.md").write_text(POSTING, encoding="utf-8")
        (self.app / "gaps.md").write_text("# Gaps\n", encoding="utf-8")
        write_urs(self.app, urs_doc())
        self.render()

    def render(self, lines=None):
        lines = CLEAN_RESUME if lines is None else lines
        build_pdf(self.app / "Jane_Doe_Resume.pdf", lines)
        build_text(self.app / "Jane_Doe_Resume_ATS.txt", lines)
        (self.app / "Jane_Doe_Resume.tex").write_text(
            TEX_PREAMBLE + "\n".join("\\item " + l for l in lines) + "\n\\end{document}\n",
            encoding="utf-8")

    def freeze(self, *args, submitted="2026-09-08", channel="Workday portal"):
        extra = []
        extra += ["--submitted", submitted] if submitted is not None else []
        extra += ["--channel", channel] if channel is not None else []
        return run(JSK, "freeze", self.app, *extra, *args)

    @property
    def sent(self):
        return self.apps / "2026-09-08-acme-platform"


class FreezeWrites(FreezeCase):
    def test_it_writes_mode_ships_shape_exactly(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertEqual((self.sent / "application.md").read_text(encoding="utf-8"),
                         EXPECTED)

    def test_a_channel_yaml_would_misread_is_quoted(self):
        """`Referral: Jane` bare will not parse, and `#slack` bare is a comment. A
        frozen application.md is never edited again, so either would stay wrong."""
        import yaml

        for channel in ("Referral: Jane", "#slack"):
            with self.subTest(channel=channel):
                code, out = self.freeze(channel=channel)
                self.assertEqual(code, 0, out)
                text = (self.sent / "application.md").read_text(encoding="utf-8")
                front = yaml.safe_load(text.split("---")[1])
                self.assertEqual(front["channel"], channel)
                (self.sent / "application.md").unlink()
                self.sent.rename(self.app)

    def test_a_named_document_is_the_only_one_gated_and_listed(self):
        """The render that was not sent is neither checked nor archived as sent."""
        build_pdf(self.app / "Jane_Doe_Resume_ATS.pdf", CLEAN_RESUME)
        (self.app / "Jane_Doe_Resume_ATS.tex").write_text(
            (self.app / "Jane_Doe_Resume.tex").read_text(encoding="utf-8"), encoding="utf-8")
        code, out = self.freeze("--doc", "Jane_Doe_Resume_ATS.pdf")
        self.assertEqual(code, 0, out)
        self.assertNotIn("check_ats.py Jane_Doe_Resume.pdf", out)
        application = (self.sent / "application.md").read_text(encoding="utf-8")
        self.assertIn("  - Jane_Doe_Resume_ATS.pdf", application)
        self.assertNotIn("  - Jane_Doe_Resume.pdf", application)

    def test_the_directory_is_renamed_to_the_day_it_was_sent(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertFalse(self.app.exists())
        self.assertTrue((self.sent / "posting.md").exists())
        self.assertIn(str(self.sent), out)

    def test_a_directory_already_named_for_the_day_stays_where_it_is(self):
        code, out = self.freeze(submitted="2026-09-01")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.app / "application.md").exists())

    def test_held_back_has_no_submitted_row(self):
        """`submitted: false` is an accurate blank. A submitted row written to fill
        it is the false green mode-ship.md forbids."""
        code, out = self.freeze(submitted="false")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.app.exists(), "a held-back application was renamed")
        text = (self.app / "application.md").read_text(encoding="utf-8")
        self.assertIn("submitted: false\n", text)
        self.assertTrue(text.endswith(
            "| Date | Event | Channel | Note | Due |\n|---|---|---|---|---|\n"), text)
        self.assertNotIn("| submitted |", text)

    def test_named_documents_are_the_ones_listed(self):
        code, out = self.freeze("--doc", "Jane_Doe_Resume.pdf")
        self.assertEqual(code, 0, out)
        text = (self.sent / "application.md").read_text(encoding="utf-8")
        self.assertIn("documents:\n  - Jane_Doe_Resume.pdf\n---", text)

    def test_the_only_view_is_used_without_being_named(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("view: view_default",
                      (self.sent / "application.md").read_text(encoding="utf-8"))

    def test_the_gates_output_is_shown(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)
        self.assertIn("--- prose gate", out)

    def test_the_knowledge_base_is_never_touched(self):
        """The log row stays the agent's to write."""
        kb = self.tmp / "user-knowledgebase.md"
        log = self.tmp / "log.md"
        kb.write_text("# KB\n\n## Open questions\n", encoding="utf-8")
        log.write_text("# Log\n\n| date | what changed |\n|---|---|\n", encoding="utf-8")
        before = kb.read_bytes(), log.read_bytes()
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertEqual((kb.read_bytes(), log.read_bytes()), before)
        self.assertIn("log.md", out)


class FreezeRefuses(FreezeCase):
    """Every refusal leaves the directory exactly as it was: no application.md, and
    no rename."""

    def assertUntouched(self):
        self.assertTrue(self.app.exists())
        self.assertFalse(self.sent.exists())

    def test_two_pdfs_and_no_doc_is_a_question_not_a_guess(self):
        """Only the person knows which render was sent; listing both archives one
        nobody submitted as though it was."""
        build_pdf(self.app / "Jane_Doe_Resume_ATS.pdf", CLEAN_RESUME)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("2 PDFs", out)
        self.assertIn("--doc", out)
        self.assertUntouched()

    def test_a_frozen_application_is_never_refrozen(self):
        (self.app / "application.md").write_text("original\n", encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("never re-frozen", out)
        self.assertEqual((self.app / "application.md").read_text(encoding="utf-8"),
                         "original\n")
        self.assertUntouched()

    def test_a_failing_document_is_never_frozen(self):
        self.render(CLEAN_RESUME + [BAD])
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)
        self.assertIn("never frozen", out)
        self.assertFalse((self.app / "application.md").exists())
        self.assertUntouched()

    def test_a_failing_record_is_never_frozen(self):
        write_urs(self.app, urs_doc(urs="9.0.0"))
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT RENDER", out)
        self.assertUntouched()

    def test_a_posting_without_a_company_is_named(self):
        (self.app / "posting.md").write_text(POSTING.replace("company: Acme Health\n", ""),
                                             encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("`company:`", out)
        self.assertUntouched()

    def test_an_indented_title_is_not_the_postings_title(self):
        """`requirements:` items carry a `title:` of their own. Only a top-level line
        is the posting's."""
        (self.app / "posting.md").write_text(POSTING.replace("title: Platform Engineer\n", ""),
                                             encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("`title:`", out)

    def test_several_views_and_none_named_is_a_call_error(self):
        doc = urs_doc()
        doc["views"].append(dict(doc["views"][0], id="view_other"))
        write_urs(self.app, doc)
        code, out = self.freeze()
        self.assertEqual(code, 2, out)
        self.assertIn("view_default, view_other", out)
        self.assertUntouched()
        code, out = self.freeze("--view", "view_other")
        self.assertEqual(code, 0, out)

    def test_a_view_the_record_does_not_hold_is_a_call_error(self):
        code, out = self.freeze("--view", "view_nope")
        self.assertEqual(code, 2, out)
        self.assertUntouched()

    def test_a_directory_with_nothing_sendable_is_refused(self):
        for name in ("Jane_Doe_Resume.pdf", "Jane_Doe_Resume_ATS.txt"):
            (self.app / name).unlink()
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("no .pdf or .txt", out)
        self.assertUntouched()

    def test_a_rename_target_that_exists_is_refused(self):
        self.sent.mkdir()
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("already exists", out)
        self.assertFalse((self.app / "application.md").exists())
        self.assertFalse((self.sent / "application.md").exists())

    def test_a_named_document_that_is_not_there_is_refused(self):
        code, out = self.freeze("--doc", "Cover_Letter.pdf")
        self.assertEqual(code, 1, out)
        self.assertIn("Cover_Letter.pdf", out)
        self.assertUntouched()


class FreezeUsage(FreezeCase):
    def test_submitted_is_required(self):
        code, out = self.freeze(submitted=None)
        self.assertEqual(code, 2, out)
        self.assertIn("--submitted is required", out)

    def test_submitted_must_be_a_date_or_false(self):
        for bad in ("yesterday", "2026-9-8", "2026-02-30", "no"):
            with self.subTest(submitted=bad):
                code, out = self.freeze(submitted=bad)
                self.assertEqual(code, 2, out)

    def test_channel_is_required(self):
        code, out = self.freeze(channel=None)
        self.assertEqual(code, 2, out)
        self.assertIn("--channel is required", out)

    def test_a_directory_that_does_not_exist_is_a_call_error(self):
        code, out = run(JSK, "freeze", self.tmp / "nowhere", "--submitted", "false",
                        "--channel", "email")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


if __name__ == "__main__":
    unittest.main()
