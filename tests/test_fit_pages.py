"""fit_pages.py exists because hand-shaving prose in a build/render loop does not
free lines, and because a stated floor with no mechanism gets breached. These tests
pin the two things that matter: the levers do what they say, and the floors hold.

They also pin the defect that moved this script off the .docx. It measured a .docx
through LibreOffice while the deliverable was a PDF built from LaTeX, the two did
not agree, and a document reported as 2 pages shipped as 3. The levers now rewrite
the .tex the PDF is compiled from, so what is measured is what is sent.

A TeX engine is external and may be absent, so the CLI paths tested here are the
ones that must work without it — chiefly the loud failure when none is installed.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import (EXAMPLE_URS, FIT_PAGES, RENDER_RESUME, load_script, run,
                      urs_module)

fp = load_script(FIT_PAGES)
emit_latex = urs_module("urs.emit_latex")
tex = urs_module("urs.tex")


def preamble(margin="0.8in", section="7pt", entry="4pt",
             topsep="2pt", itemsep="1pt", pt="11"):
    """The knobs emit_latex.py promises to keep literal and one per line."""
    return "\n".join([
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[margin=%s]{geometry}" % margin,
        r"\newlength{\sectiongap}\setlength{\sectiongap}{%s}" % section,
        r"\newlength{\entrygap}\setlength{\entrygap}{%s}" % entry,
        r"\setlist[itemize]{leftmargin=12pt,topsep=%s,itemsep=%s,parsep=0pt}"
        % (topsep, itemsep),
        r"\begin{document}",
        r"\fontsize{%spt}{%gpt}\selectfont" % (pt, float(pt) * 1.2),
        r"Body text.\par",
        r"\end{document}",
    ]) + "\n"


class Spacing(unittest.TestCase):
    """Levers 1 and 2 must be separable: the plan applies them in order, and
    applying both at once would make the report claim a lever that did nothing."""

    def test_paragraph_spacing_scales_the_section_and_entry_gaps(self):
        out = fp.scale_spacing(preamble(section="8pt", entry="4pt"), 0.5)
        self.assertIn(r"\setlength{\sectiongap}{4pt}", out)
        self.assertIn(r"\setlength{\entrygap}{2pt}", out)

    def test_paragraph_spacing_leaves_bullet_spacing_alone(self):
        out = fp.scale_spacing(preamble(topsep="2pt", itemsep="1pt"), 0.0)
        self.assertIn("topsep=2pt", out)
        self.assertIn("itemsep=1pt", out)

    def test_bullet_spacing_scales_only_the_list(self):
        out = fp.scale_bullet_spacing(preamble(section="7pt", topsep="2pt",
                                               itemsep="1pt"), 0.5)
        self.assertIn("topsep=1pt", out)
        self.assertIn("itemsep=0.5pt", out)
        self.assertIn(r"\setlength{\sectiongap}{7pt}", out)

    def test_zero_factor_reaches_the_floor_exactly(self):
        out = fp.scale_spacing(preamble(section="7pt", entry="4pt"), 0.0)
        self.assertIn(r"\setlength{\sectiongap}{0pt}", out)
        self.assertIn(r"\setlength{\entrygap}{0pt}", out)

    def test_a_lever_only_ever_removes_space(self):
        for factor in (0.75, 0.5, 0.25, 0.0):
            out = fp.scale_spacing(preamble(section="8pt"), factor)
            value = float(out.split(r"\setlength{\sectiongap}{")[1].split("pt")[0])
            self.assertLessEqual(value, 8.0)


class Margins(unittest.TestCase):
    def test_margins_shrink_to_the_request(self):
        self.assertIn("margin=0.6in", fp.set_margins(preamble(), 0.6))

    def test_margins_never_cross_the_half_inch_floor(self):
        out = fp.set_margins(preamble(), 0.1)
        self.assertIn("margin=0.5in", out)

    def test_already_tight_margins_are_not_widened(self):
        """set_margins is given a target, not a delta; the plan never asks for
        more room than the document already has."""
        plan_margins = [s[2] for _, s in fp.lever_plan() if s[2] is not None]
        self.assertTrue(all(m <= 0.8 for m in plan_margins), plan_margins)


class Fonts(unittest.TestCase):
    def test_font_shrinks_by_the_requested_points(self):
        out = fp.shrink_font(preamble(pt="11"), 0.5)
        self.assertIn(r"\fontsize{10.5pt}", out)

    def test_the_baseline_moves_with_the_size(self):
        out = fp.shrink_font(preamble(pt="11"), 1.0)
        self.assertIn(r"\fontsize{10pt}{12pt}", out)

    def test_font_never_crosses_the_ten_point_floor(self):
        out = fp.shrink_font(preamble(pt="11"), 5.0)
        self.assertIn(r"\fontsize{10pt}", out)

    def test_zero_delta_is_a_no_op(self):
        self.assertEqual(fp.shrink_font(preamble(pt="11"), 0), preamble(pt="11"))


class LeverPlan(unittest.TestCase):
    def setUp(self):
        self.plan = fp.lever_plan()

    def test_order_is_spacing_then_bullets_then_margins_then_font(self):
        labels = [label for label, _ in self.plan]
        kinds = [next(k for k in ("inter-paragraph", "bullet", "margins", "body font")
                      if label.startswith(k)) for label in labels]
        self.assertEqual(kinds, sorted(
            kinds, key=lambda k: ["inter-paragraph", "bullet", "margins",
                                  "body font"].index(k)))

    def test_no_step_requests_a_margin_below_the_floor(self):
        for label, (_, _, margin, _) in self.plan:
            if margin is not None:
                self.assertGreaterEqual(margin, fp.MARGIN_FLOOR_IN, label)

    def test_no_step_requests_a_font_below_the_floor(self):
        for label, state in self.plan:
            out = fp.apply_state(preamble(pt="11"), state)
            size = float(out.split(r"\fontsize{")[1].split("pt")[0])
            self.assertGreaterEqual(size, fp.FONT_FLOOR_PT, label)

    def test_every_state_applies_cleanly_to_a_real_template(self):
        """The levers are regexes over emit_latex.py's own output. If that file
        reformats a knob, this is what notices."""
        source = emit_latex.PREAMBLE % {
            "pt": 11, "baseline": "13.2", "paper": "a4paper",
            "bullet": r"\textbullet", "margin": "0.8in"}
        for label, state in self.plan:
            out = fp.apply_state(source, state)
            self.assertNotEqual(out, "", label)
            self.assertIsNotNone(fp.body_font_pt(out), label)
            self.assertIsNotNone(fp.current_margin_in(out), label)


class Geometry(unittest.TestCase):
    """The measurement the issue says was taken last instead of first: which block
    spilled, and how much room was actually available for it."""

    @staticmethod
    def page(height=792.0, bottom=700.0, text="", first_height=0.0):
        return {"height": height, "bottom": bottom,
                "first_text": text, "first_height": first_height}

    def test_fill_is_content_bottom_over_page_height(self):
        self.assertAlmostEqual(fp.fill_percent(self.page(bottom=396.0)), 50.0)

    def test_no_diagnosis_when_the_document_already_fits(self):
        self.assertIsNone(fp.diagnose([self.page(), self.page()], 2, 72.0))

    def test_diagnosis_names_the_spilled_block_and_the_space_left(self):
        pages = [self.page(bottom=700.0), self.page(bottom=690.0),
                 self.page(bottom=110.0, text="Education", first_height=41.0)]
        gap = fp.diagnose(pages, 2, 72.0)
        self.assertEqual(gap["text"], "Education")
        self.assertAlmostEqual(gap["needs"], 41.0)
        self.assertAlmostEqual(gap["free"], 30.0)   # 792 - 72 - 690

    def test_free_space_never_reports_negative(self):
        pages = [self.page(bottom=780.0), self.page(bottom=780.0), self.page(text="X")]
        self.assertGreaterEqual(fp.diagnose(pages, 2, 72.0)["free"], 0.0)


class CliContract(unittest.TestCase):
    """'Skip and say so loudly rather than silently passing' — a page count nobody
    measured must never be reported as a page count that is fine."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.tex = self.tmp / "resume.tex"
        self.tex.write_text(preamble(), encoding="utf-8")

    def test_missing_file_reports_a_verdict(self):
        code, out = run(FIT_PAGES, self.tmp / "absent.tex")
        self.assertEqual(code, 2)
        self.assertIn("not found", out.lower())

    def test_the_pdf_is_not_what_this_rewrites(self):
        """Handing it the deliverable instead of the source is the natural
        mistake now that the PDF is the deliverable."""
        pdf = self.tmp / "resume.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        code, out = run(FIT_PAGES, pdf)
        self.assertEqual(code, 2)
        self.assertIn("not a .tex", out)

    def test_a_tex_without_the_levers_is_refused(self):
        stray = self.tmp / "other.tex"
        stray.write_text(r"\documentclass{article}", encoding="utf-8")
        code, out = run(FIT_PAGES, stray)
        self.assertEqual(code, 2)
        self.assertIn("NO LEVERS", out)
        self.assertNotIn("PASS", out)

    def test_zero_target_pages_is_a_usage_error(self):
        code, out = run(FIT_PAGES, self.tex, "--target-pages", "0")
        self.assertEqual(code, 2)
        self.assertIn("usage", out.lower())

    def test_conflicting_output_flags_are_a_usage_error(self):
        code, out = run(FIT_PAGES, self.tex, "--in-place", "-o", str(self.tmp / "o.tex"))
        self.assertEqual(code, 2)
        self.assertIn("usage", out.lower())


@unittest.skipUnless(tex.available_engine(), "needs a TeX engine to render")
class WithAnEngine(unittest.TestCase):
    """The end-to-end path, when the machine can actually compile."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def render(self, *args):
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_au_default", *args)
        self.assertEqual(code, 0, out)
        return self.tmp / "Priya_Raman_Resume.tex"

    def test_a_short_document_already_fits(self):
        code, out = run(FIT_PAGES, self.render(), "--target-pages", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("already fits", out)

    def test_it_measures_the_document_that_ships(self):
        """The defect this change exists for: the page count has to describe the
        PDF the .tex compiles to, not a second document built another way."""
        source = self.render()
        code, out = run(FIT_PAGES, source, "--target-pages", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("baseline: 1 pages", out)

    def test_an_over_budget_document_does_not_pass(self):
        source = self.render()
        body = source.read_text(encoding="utf-8")
        head, rest = body.split("selectfont", 1)
        middle, tail = rest.rsplit(r"\end{document}", 1)
        fat = self.tmp / "fat.tex"
        fat.write_text(head + "selectfont" + middle * 6 + r"\end{document}" + tail,
                       encoding="utf-8")
        code, out = run(FIT_PAGES, fat, "--target-pages", "1", "--dry-run")
        self.assertEqual(code, 1, out)
        self.assertNotIn("PASS", out)


if __name__ == "__main__":
    unittest.main()
