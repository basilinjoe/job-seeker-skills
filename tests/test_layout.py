"""The layout gate measures what the render gate's checklist asked a model to see.

A model reading page images was asked to spot tofu, a second typeface, a heading
stranded at a page foot, a date out of its column and the wrong paper. The first test
here is the one the gate rests on: every shipped template, in both variants, passes it
on the shipped example. A gate that fails our own output teaches people to ignore it.
The rest pin that each defect, built directly into a PDF, fails.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixtures import CLI, CLEAN_RESUME, EXAMPLE_SHORT, RENDER_RESUME, run, urs_module
from jsk.gates import layout

tex = urs_module("urs.tex")
themes = urs_module("urs.themes")
LAYOUT = "jsk.gates.layout"


def has_pymupdf():
    try:
        import pymupdf  # noqa: F401,PLC0415
        return True
    except ImportError:
        return False


def pdf(path, pages, width=595.28, height=841.89):
    """One page per entry in `pages`, each a list of (x, y, text, fontname)."""
    import pymupdf

    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page(width=width, height=height)
        for x, y, text, font in lines:
            page.insert_text((x, y), text, fontsize=11, fontname=font)
    doc.save(str(path))
    doc.close()
    return str(path)


def column(lines, font="helv", x=72, y=72, step=14):
    return [(x, y + i * step, text, font) for i, text in enumerate(lines)]


@unittest.skipUnless(has_pymupdf(), "needs pymupdf")
class LayoutCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def gate(self, path, *args):
        return run(LAYOUT, path, *args)

    def assertFails(self, code, out, needle):
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)
        self.assertIn(needle, out)
        self.assertIn("fix:", out)


@unittest.skipUnless(tex.available_engine() and has_pymupdf(),
                     "needs a TeX engine and pymupdf")
class EveryShippedTemplatePasses(unittest.TestCase):
    """No false failures on our own output. circuit (Heros body, Adventor heads) and
    atrium (Pagella body, Heros heads) each embed two families by design, which is why
    the family rule follows the templates' declared pairs rather than "one family"."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.pdfs = {}
        for name in themes.names():
            for variant in ((), ("--ats-max",)):
                out = cls.tmp / (name + "".join(variant))
                code, output = run(RENDER_RESUME, EXAMPLE_SHORT, "--out", out, "--template",
                                   name, "--format", "latex", "--pdf", *variant)
                assert code == 0, output
                cls.pdfs[out.name] = next(out.glob("*.pdf"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_template_and_variant_passes_against_its_record(self):
        for name, path in self.pdfs.items():
            with self.subTest(template=name):
                code, out = run(LAYOUT, path, "--record", EXAMPLE_SHORT)
                self.assertEqual(code, 0, f"{name}:\n{out}")
                self.assertIn("region: AU", out)
                self.assertIn("paper: A4", out)

    def test_the_two_family_templates_are_the_ones_that_declare_two(self):
        for name, path in self.pdfs.items():
            _, out = run(LAYOUT, path)
            faces = out.split("families: ")[1].splitlines()[0].split(", ")
            theme = themes.get(name.replace("--ats-max", ""))
            self.assertEqual(len(faces), 1 + (theme["body"] != theme["head"]), f"{name}:\n{out}")

    def test_a_us_render_is_letter_and_fails_against_an_au_record(self):
        out_dir = self.tmp / "us"
        code, output = run(RENDER_RESUME, EXAMPLE_SHORT, "--out", out_dir, "--format", "latex",
                           "--pdf", "--region", "US")
        self.assertEqual(code, 0, output)
        path = next(out_dir.glob("*.pdf"))
        code, out = run(LAYOUT, path, "--region", "US")
        self.assertEqual(code, 0, out)
        code, out = run(LAYOUT, path, "--record", EXAMPLE_SHORT)
        self.assertEqual(code, 1, out)
        self.assertIn("paper Letter - the AU region renders on A4", out)


class Families(LayoutCase):
    def test_one_family_passes(self):
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME)])
        code, out = self.gate(path, "--region", "AU")
        self.assertEqual(code, 0, out)
        self.assertIn("families: Helvetica", out)

    def test_two_families_no_template_declares_fail(self):
        lines = column(CLEAN_RESUME) + [(72, 400, "Set in another face entirely.", "tiro")]
        path = pdf(self.tmp / "r.pdf", [lines])
        code, out = self.gate(path, "--region", "AU")
        self.assertFails(code, out, "2 type families: Helvetica, Times")

    def test_the_declared_pairs_are_circuit_and_atrium(self):
        pairs = layout.declared_pairs()
        self.assertEqual(pairs["circuit"], {"TeXGyreHeros", "TeXGyreAdventor"})
        self.assertEqual(pairs["atrium"], {"TeXGyrePagella", "TeXGyreHeros"})
        self.assertEqual(set(pairs), {"circuit", "atrium"})

    def test_every_theme_family_has_a_pdf_name(self):
        self.assertEqual(set(layout.PDF_FAMILY), set(themes.FAMILIES))

    def test_family_names_normalise(self):
        for font, want in (("IHAIZV+LMRoman12-Bold", "LMRoman"), ("TeXGyreHeros-Italic",
                           "TeXGyreHeros"), ("Times-Roman", "Times"), ("Arial,BoldItalic",
                           "Arial"), ("ArialMT", "Arial"), ("LMSans10-Regular", "LMSans")):
            self.assertEqual(layout.family(font), want, font)


class Tofu(LayoutCase):
    def test_a_replacement_character_fails(self):
        """Built as the text layer rather than a PDF: pymupdf's base-14 fonts draw
        U+FFFD as a middle dot, so a PDF made here cannot carry one."""
        rect = mock.Mock(width=595.28, height=841.89)
        lines = [("Cut latency � by half", (72, 60, 300, 72), {"Helvetica"})]
        fails, _, _, _ = layout.check([(rect, lines)], [], "AU")
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("U+FFFD", fails[0])
        self.assertIn("fix:", fails[0])

    def test_a_private_use_codepoint_fails(self):
        rect = mock.Mock(width=595.28, height=841.89)
        lines = [(" Led the team", (72, 60, 300, 72), {"Helvetica"})]
        fails, _, _, _ = layout.check([(rect, lines)], [], "AU")
        self.assertIn("U+E000", fails[0])

    def test_a_type3_font_fails(self):
        rect = mock.Mock(width=595.28, height=841.89)
        fails, _, _, _ = layout.check([(rect, [])], ["SFRM1095"], "AU")
        self.assertIn("Type3", fails[0])
        self.assertIn("lmodern", fails[0])


class StrandedHeadings(LayoutCase):
    def test_a_heading_at_the_foot_of_a_page_fails(self):
        first = CLEAN_RESUME[:CLEAN_RESUME.index("Education") + 1]
        path = pdf(self.tmp / "r.pdf", [column(first), column(CLEAN_RESUME[-1:])])
        code, out = self.gate(path, "--region", "AU")
        self.assertFails(code, out, "heading 'Education' is the last text on page 1")

    def test_a_heading_with_its_content_below_passes(self):
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME)])
        code, out = self.gate(path, "--region", "AU")
        self.assertEqual(code, 0, out)


class DateColumn(LayoutCase):
    def test_a_date_out_of_the_column_fails(self):
        lines = column(["Acme Corp", "Globex"]) + [
            (440, 72, "Jun 2025 - Present", "helv"), (400, 86, "Jan 2018 - May 2025", "helv")]
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME, y=200) + lines])
        code, out = self.gate(path, "--region", "AU")
        self.assertFails(code, out, "not flush with the date column: 'Jan 2018 - May 2025'")


class Paper(LayoutCase):
    def test_letter_for_an_a4_region_fails(self):
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME)], width=612, height=792)
        code, out = self.gate(path, "--region", "AU")
        self.assertFails(code, out, "paper Letter - the AU region renders on A4")

    def test_letter_for_the_us_passes(self):
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME)], width=612, height=792)
        code, out = self.gate(path, "--region", "US")
        self.assertEqual(code, 0, out)

    def test_neither_a4_nor_letter_fails_without_a_region(self):
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME)], width=500, height=700)
        code, out = self.gate(path)
        self.assertFails(code, out, "neither A4 nor Letter")

    def test_no_region_is_a_warning_not_a_pass_on_paper(self):
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME)])
        code, out = self.gate(path)
        self.assertEqual(code, 0, out)
        self.assertIn("paper not checked against a region", out)


class PageCount(LayoutCase):
    def test_over_budget_is_reported_never_failed(self):
        """`jsk fit` owns that verdict; two places failing one count is how they start
        disagreeing."""
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME), column(["More."])])
        code, out = self.gate(path, "--region", "AU", "--pages", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("2 pages of a budget of 1 (reported; jsk fit owns that verdict)", out)


@unittest.skipUnless(has_pymupdf(), "needs pymupdf to build the PDF")
class WithoutPymupdf(LayoutCase):
    def test_skipped_and_a_failure(self):
        path = pdf(self.tmp / "r.pdf", [column(CLEAN_RESUME)])
        buf = io.StringIO()
        with mock.patch.dict(sys.modules, {"pymupdf": None}), contextlib.redirect_stdout(buf):
            code = layout.main([path, "--region", "AU"])
        self.assertEqual(code, 1, buf.getvalue())
        self.assertTrue(buf.getvalue().startswith("SKIPPED"), buf.getvalue())
        self.assertIn("pip install pymupdf", buf.getvalue())

    def test_jsk_gates_reports_it_skipped(self):
        from jsk import cli
        (self.tmp / "Jane_Resume.pdf").write_bytes(Path(pdf(self.tmp / "x.pdf",
                                                           [column(CLEAN_RESUME)])).read_bytes())
        with mock.patch.dict(sys.modules, {"pymupdf": None}):
            code, output = cli.call_gate("layout.py", [str(self.tmp / "Jane_Resume.pdf")])
        result = cli.gate_result("layout gate", "layout.py Jane_Resume.pdf", code, output)
        self.assertEqual((result["status"], result["exit"]), ("SKIPPED", 1), output)


class CheckOnlyLayout(LayoutCase):
    def test_jsk_check_runs_it_by_name_from_a_sibling(self):
        path = pdf(self.tmp / "Jane_Resume.pdf", [column(CLEAN_RESUME)])
        (self.tmp / "Jane_Resume.tex").write_text("", encoding="utf-8")
        code, out = run(CLI, "check", Path(path).with_suffix(".tex"), "--only", "layout",
                        "--region", "AU")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - the layout holds", out)

    def test_the_section_titles_are_the_builders(self):
        """Headings are found by their words, so a title build.py renames is a heading
        this gate stops seeing."""
        from jsk.resume import build
        for fmt in ("presentation", "ats-maximal"):
            plan, _ = build.from_path(EXAMPLE_SHORT, fmt=fmt)
            for section in plan["sections"]:
                if section.get("heading"):
                    self.assertIn(section["heading"], layout.SECTION_TITLES)


if __name__ == "__main__":
    unittest.main()
