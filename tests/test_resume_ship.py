"""`jsk resume ship`, the command mode-ship.md used to spell out as a procedure for an
agent to follow by hand.

It owns no verdict. It strings together three that already exist - the record gate,
the render, the mechanical gates - and what these tests pin is the order, the
stopping, and the one gate it has to say out loud that it did not run.
"""
import contextlib
import io
import json
import re
import unittest
from unittest import mock

import appkit
from fixtures import CLI, CLEAN_RESUME, build_pdf, run
from shipkit import (BAD, BROKEN, CONTACTED, D1, GOOD, GraphCase, MERIDIAN, ShipCase, ShortCase,
                     fake_compile, margin_compile)


JSK = CLI


class ShipOrder(ShipCase):
    """Record gate, render, mechanical gates - in that order, one process."""

    def test_a_clean_ship_runs_every_step_and_exits_0(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        # The parse gate twice - the PDF, and the plain text emitted in memory - and the
        # prose gate once: no .txt is written for it to read a second time.
        self.assertEqual(self.headings(out),
                         ["record gate", "render", "parse gate", "parse gate",
                          "prose gate", "layout gate", "render gate"], out)

    def test_every_gate_says_its_own_pass(self):
        """There is no claims gate: the record gate reads the career itself, and the
        copy the claims gate joined with the career went with the URS record."""
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertNotIn("claims gate", out)
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
        self.assertTrue((self.out / "Test_Person_Resume.pdf").exists())
        self.assertIn("template: ember", out)


class ShipGatesOnlyItsOwnRender(ShipCase):
    """A directory keeps every earlier render. `--ats-max` after a default ship left
    both PDFs side by side, and gating the directory failed the second ship on a
    file it never made - then told the person to open that one.

    Both variants now share one name, so the second ship replaces the first; what it
    must get right is holding the replacement to the ATS rules, which it reads from
    the render rather than from a suffix."""

    def test_a_second_ship_gates_what_it_wrote_as_the_variant_it_holds(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("check_ats.py Test_Person_Resume.pdf\n", out)      # not strict
        code, out = self.ship("--ats-max")
        self.assertEqual(code, 0, out)
        self.assertIn("check_ats.py Test_Person_Resume.pdf --strict", out)
        self.assertIn("open Test_Person_Resume.pdf", out)
        self.assertEqual(len(list(self.out.glob("*.pdf"))), 1)


class ShipStops(ShipCase):
    """A step that fails stops the ones after it. A record that fails its gate is
    never rendered: the PDF it would make looks sendable and is not."""

    def test_a_failing_record_renders_nothing(self):
        self.write(BROKEN)
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
        self.out.mkdir(parents=True)
        build_pdf(self.out / "Old_Resume.pdf", CLEAN_RESUME)
        self.write(BROKEN)
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
        from jsk.domain.render import emit_text
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
        # The section, not the summary under it - which says PASS for the gates above.
        render = out.split("--- render gate")[1].split("=== summary")[0]
        self.assertIn("UNVERIFIED", render)
        self.assertIn("read every page", render)
        self.assertNotIn("PASS", render)

    def test_over_budget_is_reported_and_never_failed(self):
        """`jsk fit` owns the page verdict. ship names an overrun and exits 0. Under
        --no-fit, which keeps ship as it was before it fitted (ShipFits covers the fit)."""
        code, out = self.ship("--pages", "1", "--no-fit", compile_pdf=fake_compile(pages=3))
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


class ShipSummary(ShipCase):
    """The block the output ends with. The ElevenLabs ship (2026-09-25) was read
    through `tail -60`, which cut the record gate off the top."""

    def summary(self, out):
        self.assertIn("=== summary", out)
        return out.split("=== summary\n")[1].splitlines()

    def step(self, line):
        """The gate a summary line is for: the name before its two-space column."""
        return line.strip().split("  ")[0]

    def test_it_is_last_with_one_line_a_step_and_a_verdict(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        lines = self.summary(out)
        self.assertEqual([self.step(line) for line in lines[:-1]], self.headings(out), out)
        self.assertTrue(lines[-1].startswith("verdict: PASS"), out)
        self.assertTrue(out.rstrip().endswith(lines[-1]), out)

    def test_the_counts_are_the_gates_own(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        lines = self.summary(out)
        sections = out.split("=== summary")[0].split("\n--- ")[1:]
        for section, line in zip(sections, lines, strict=False):
            counts = re.findall(r"^FAIL (\d+)\s+WARN (\d+)\s*$", section, re.M)
            with self.subTest(step=line):
                if counts:
                    self.assertIn(f"FAIL {counts[-1][0]}   WARN {counts[-1][1]}", line)
        self.assertIn("record gate  PASS   FAIL 0   WARN 0", out)
        self.assertIn("Test_Person_Resume.pdf 1 of 2 pages", lines[1])
        self.assertIn("render gate  UNVERIFIED", out)

    def test_it_counts_the_lines_the_render_withheld_once_each(self):
        """build.py warns once per variant rendered; the line held back is one. ach_data_ingestion is j:inferred in the fixture, under the
        default floor. (The render builds one variant now - no plain-text file rides
        along - so the warning can come once; the summary still names it once.)"""
        self.write(dict(GOOD, bullets=MERIDIAN + ["ach_data_ingestion"]))
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("withheld bullet ach_data_ingestion", out)
        [render] = [line for line in self.summary(out) if self.step(line) == "render"]
        # Named: the Arrow run shipped a second time only to grep for which one it was.
        self.assertIn("withheld 1 below the floor: ach_data_ingestion", render)
        self.assertEqual(render.count("ach_data_ingestion"), 1, render)

    def test_a_stop_names_the_step_that_failed(self):
        self.write(BROKEN)
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        lines = self.summary(out)
        self.assertEqual(len(lines), 3, out)
        self.assertTrue(lines[0].split()[2] == "FAIL", out)
        self.assertEqual(lines[-1].split(";")[0], "verdict: FAIL - record gate", out)

    def test_jsk_gates_ends_with_it_too(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        code, out = run(JSK, "resume", "check", self.out, "--record", self.record)
        self.assertEqual(code, 0, out)
        lines = self.summary(out)
        self.assertEqual([self.step(line) for line in lines[:-1]], self.headings(out), out)
        self.assertTrue(lines[-1].startswith("verdict: PASS"), out)

    def test_the_json_form_has_no_summary(self):
        code, out = self.ship("--json")
        self.assertEqual(code, 0, out)
        self.assertNotIn("=== summary", out)


class ShipFits(ShipCase):
    """Ruling 3 of the tailor-time plan (2026-09-29): ship fits the page budget itself.

    The Arrow run rendered 3 pages against 2, ran `jsk fit` three times, cut three
    confirmed bullets, and then moved, recompiled and gated the fitted .tex by hand.
    The first fit had already reached 2 pages at 0.6in, inside the 0.5in floor."""

    def fit_ship(self, *extra, fits_at=None):
        from jsk import cli
        from jsk.adapters.cli.compose import fit, render as render_resume
        self.fake = fake = margin_compile(fits_at)
        args = ["jsk", "resume", "ship", str(self.record), "--out", str(self.out)]
        buf = io.StringIO()
        with mock.patch.object(render_resume, "compile_pdf", fake), \
                mock.patch.object(fit, "compile_pdf", fake), \
                mock.patch.object(fit, "available_engine", lambda: "fake"), \
                contextlib.redirect_stdout(buf):
            code = cli.main(args + [str(a) for a in extra])
        return code, buf.getvalue()

    def pdf_pages(self):
        import pymupdf
        with pymupdf.open(self.out / "Test_Person_Resume.pdf") as doc:
            return doc.page_count

    def tex(self):
        return (self.out / "Test_Person_Resume.tex").read_text(encoding="utf-8")

    def summary_line(self, out, step):
        lines = out.split("=== summary\n")[1].splitlines()
        return next(line for line in lines if line.strip().split("  ")[0] == step)

    def test_an_overrun_comes_back_inside_the_budget_naming_its_levers(self):
        code, out = self.fit_ship(fits_at=0.6)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.pdf_pages(), 2, out)
        levers = "inter-paragraph spacing x0, bullet spacing x0, margins 0.6in"
        self.assertIn(f"fit: {levers}, 2 pages", self.summary_line(out, "fit"))
        self.assertIn("margin=0.6in]", self.tex())
        # Moved over the original, not left beside it for somebody to move.
        self.assertEqual(list(self.out.glob("*-fitted.tex")), [], out)
        # Each value beside its floor: `margins 0.6in` alone was read as the floor.
        self.assertIn("margins 0.6in (floor 0.5in)", out)
        self.assertIn("(floor 10pt)", out)

    def test_the_gates_read_the_fitted_render(self):
        code, out = self.fit_ship(fits_at=0.6)
        self.assertEqual(code, 0, out)
        heads = self.headings(out)
        self.assertEqual(heads[:3], ["record gate", "render", "fit"], out)
        self.assertIn("layout gate", heads)
        layout = out.split("--- layout gate")[1].split("\n--- ")[0]
        self.assertIn("pages: 2 pages", layout)

    def test_no_fit_keeps_the_overrun(self):
        code, out = self.fit_ship("--no-fit", fits_at=0.6)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.pdf_pages(), 3, out)
        self.assertNotIn("--- fit", out)
        self.assertIn("OVER BUDGET", out)
        self.assertIn("margin=0.8in]", self.tex())

    def test_at_the_floors_it_counts_the_lines_and_changes_nothing(self):
        code, out = self.fit_ship("--no-fit")
        self.assertEqual(code, 0, out)
        tex = (self.out / "Test_Person_Resume.tex").read_bytes()
        code, out = self.fit_ship()
        # The page count is reported and never failed, as it was before ship fitted.
        self.assertEqual(code, 0, out)
        line = self.summary_line(out, "fit")
        self.assertIn("OVER BUDGET", line)
        over = int(re.search(r"over by ~(\d+) lines at the floors$", line).group(1))
        # Ten of the fake's 15pt lines, counted in 12pt lines of the 10pt floor body.
        self.assertTrue(10 <= over <= 13, line)
        self.assertIn("nothing was cut", out)
        # The .tex is the one a ship without the fit writes; the PDF is the render's own,
        # compiled once into the output directory - every other compile was the fitter's
        # scratch - and still over.
        self.assertEqual((self.out / "Test_Person_Resume.tex").read_bytes(), tex)
        self.assertEqual(self.fake.into.count(self.out.resolve()), 1, self.fake.into)
        self.assertGreater(len(self.fake.into), 1, "the fitter never compiled")
        self.assertEqual(self.pdf_pages(), 3, out)
        self.assertEqual(list(self.out.glob("*-fitted.tex")), [], out)

    def test_it_fits_to_the_budget_the_render_measured(self):
        """--ats-max renders against `ats_pages`: 3 pages of 3 is no overrun."""
        self.write(dict(GOOD, ats_pages=3))
        code, out = self.fit_ship("--ats-max", fits_at=0.6)
        self.assertEqual(code, 0, out)
        self.assertNotIn("--- fit", out)
        self.assertEqual(self.pdf_pages(), 3, out)

    def test_pages_is_the_budget_when_given(self):
        code, out = self.fit_ship("--pages", "3", fits_at=0.6)
        self.assertEqual(code, 0, out)
        self.assertNotIn("--- fit", out)

    def test_a_render_inside_its_budget_is_not_fitted(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertNotIn("--- fit", out)


class ShipUsage(ShipCase):
    def test_a_view_is_a_usage_error_naming_one_resume(self):
        code, out = self.ship("--view", "view_default")
        self.assertEqual(code, 2, out)
        self.assertIn("a resume.json is one resume", out)
        self.assertNotIn("--- record gate", out)

    def test_a_target_ships_into_its_own_directory_and_no_other(self):
        # A resume.json shipped with --out until 6.0 (docs/superpowers/plans/
        # 2026-10-03-retire-file-pipeline.md, P2); a target has a directory of its own.
        code, out = self.ship("--out", self.tmp / "elsewhere")
        self.assertEqual(code, 2, out)
        self.assertIn("renders into its own directory", out)
        self.assertIn("fix:  drop --out", out)
        self.assertFalse((self.tmp / "elsewhere").exists())

    def test_an_unknown_template_is_a_call_error_before_anything_runs(self):
        code, out = self.ship("--template", "nope")
        self.assertEqual(code, 2, out)
        self.assertNotIn("--- record gate", out)

    def test_an_unknown_flag_is_a_call_error(self):
        code, out = self.ship("--recheck")
        self.assertEqual(code, 2, out)
        self.assertIn("usage: jsk resume ship", out)

    def test_the_knowledge_base_is_refused_as_validate_refuses_it(self):
        kb = self.tmp / "user-knowledgebase.md"
        kb.write_text("# Career knowledge base", encoding="utf-8")
        code, out = run(JSK, "resume", "ship", kb, "--out", self.out)
        self.assertEqual(code, 2, out)
        self.assertIn("name the target", out)

    def test_pages_must_be_a_number(self):
        code, out = self.ship("--pages", "two")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)


class ShipGraph(GraphCase):
    EDITS = (CONTACTED,)

    def ship(self):
        from jsk.adapters.cli.compose import render as render_resume

        with mock.patch.object(render_resume, "compile_pdf", fake_compile()):
            return self.jsk("resume", "ship", self.short)

    def test_a_clean_record_ships_through_the_record_gate(self):
        code, out = self.ship()
        self.assertEqual(code, 0, out)
        self.assertIn("--- record gate: record.py", out)
        self.assertIn("PASS - safe to render", out)
        self.assertNotIn("claims gate", out)

    def test_a_replaced_number_stops_at_the_record_gate_and_renders_nothing(self):
        self.edit_career(*D1)
        code, out = self.ship()
        self.assertEqual(code, 1, out)
        self.assertIn("number-superseded ach_events_latency", out)
        self.assertIn("the record gate did not pass", out)
        self.assertNotIn("--- render:", out)


class ShipFrozen(ShortCase):
    """Review Focus 5: a frozen application is what was sent. Re-rendering into it would
    overwrite the PDF the application's record says went out."""

    def ship(self, *args):
        from jsk.adapters.cli.compose import render as render_resume

        with mock.patch.object(render_resume, "compile_pdf", fake_compile()):
            return self.jsk("resume", "ship", *args)

    def frozen(self, submitted='"false"^^xsd:boolean'):
        appkit.put(self.root, self.graph(self.app, "application"),
                   'k:app_contoso_platform j:posting k:post_contoso_platform ; '
                   f'j:submitted {submitted} .\n')

    def test_it_refuses_to_render_into_a_frozen_directory(self):
        self.frozen()
        before = (self.app / "Jane_Doe_Resume.pdf").read_bytes()
        code, out = self.ship(self.short, "--out", self.app)
        self.assertEqual(code, 1, out)
        self.assertIn(f"frozen: {self.graph(self.app, 'application')}", out)
        # Held back, so nothing was sent: the refusal says what was frozen. It said "what
        # was sent" of every freeze until 2026-10-02.
        self.assertIn("re-rendering would overwrite what was frozen (held back, not sent)", out)
        self.assertIn("fix:", out)
        # A graph-native application is reused by capturing its posting again.
        self.assertIn("posting_capture", out)
        self.assertNotIn("--- ", out)                       # no step ran
        self.assertEqual((self.app / "Jane_Doe_Resume.pdf").read_bytes(), before)

    def test_a_sent_application_is_refused_as_sent(self):
        self.frozen('"2026-09-20"^^xsd:date')
        code, out = self.ship(self.short, "--out", self.app)
        self.assertEqual(code, 1, out)
        self.assertIn("re-rendering would overwrite what was sent", out)
        self.assertIn("posting_capture", out)

    def test_a_stray_application_ttl_file_freezes_nothing_in_a_stored_workspace(self):
        """`jsk kb load` leaves the old files where they were; the store alone says."""
        (self.app / "application.ttl").write_text("# frozen\n", encoding="utf-8")
        code, out = self.ship(self.short)
        self.assertNotIn("frozen:", out)

    def test_it_refuses_a_record_from_a_frozen_directory_rendered_elsewhere(self):
        # A ship keeps the target's own directory; a render may go elsewhere with --out,
        # and is refused for a frozen target all the same.
        from jsk.adapters.cli.compose import render as render_resume

        self.frozen()
        out_dir = self.root / "out"
        with mock.patch.object(render_resume, "compile_pdf", fake_compile()):
            code, out = self.jsk("resume", "render", self.short, "--out", out_dir)
        self.assertEqual(code, 1, out)
        self.assertIn("frozen:", out)
        self.assertFalse(list(out_dir.glob("*.tex")) if out_dir.exists() else [])

    def test_view_is_a_call_error(self):
        code, out = self.ship(self.short, "--view", "view_x")
        self.assertEqual(code, 2, out)
        self.assertIn("drop --view", out)

    def test_a_selection_needs_no_view(self):
        code, out = self.ship(self.short)
        self.assertNotIn("--view is required", out)


if __name__ == "__main__":
    unittest.main()
