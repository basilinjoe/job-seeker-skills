"""fit_pages.py exists because hand-shaving prose in a build/render loop does not
free lines, and because a stated floor with no mechanism gets breached. These tests
pin the two things that matter: the levers do what they say, and the floors hold.

The renderer is external and usually absent, so the CLI paths tested here are the
ones that must work without it — chiefly the loud failure when none is installed.
"""
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from fixtures import FIT_PAGES, load_script, run

fp = load_script(FIT_PAGES)

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def para(text, spacing=None, bullet=False, sz=None):
    props = "<w:numPr><w:ilvl w:val=\"0\"/></w:numPr>" if bullet else ""
    if spacing is not None:
        props += f'<w:spacing w:before="{spacing}" w:after="{spacing}"/>'
    rpr = f'<w:rPr><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>' if sz else ""
    return (f"<w:p><w:pPr>{props}</w:pPr>"
            f"<w:r>{rpr}<w:t>{text}</w:t></w:r></w:p>")


def document(body, margins=1440):
    sect = (f'<w:sectPr><w:pgMar w:top="{margins}" w:right="{margins}" '
            f'w:bottom="{margins}" w:left="{margins}" w:header="720" w:footer="720"/>'
            f"</w:sectPr>")
    return f"<w:document {W_NS}><w:body>{body}{sect}</w:body></w:document>"


class Spacing(unittest.TestCase):
    """Lever 1 and 2 must be separable: the plan applies them in order, and applying
    both at once would make the report claim a lever that did nothing."""

    def setUp(self):
        self.xml = document(para("body", spacing=200) + para("bullet", spacing=120, bullet=True))

    def test_paragraph_spacing_scales_only_non_list_paragraphs(self):
        out = fp.scale_spacing(self.xml, 0.5, lists=False)
        self.assertIn('w:before="100"', out)
        self.assertIn('w:after="100"', out)
        self.assertIn('w:before="120"', out, "bullet spacing must be untouched by lever 1")

    def test_bullet_spacing_scales_only_list_paragraphs(self):
        out = fp.scale_spacing(self.xml, 0.0, lists=True)
        self.assertIn('w:before="200"', out, "body spacing must be untouched by lever 2")
        self.assertIn('w:before="0"', out)

    def test_zero_factor_reaches_the_floor_exactly(self):
        out = fp.scale_spacing(self.xml, 0.0, lists=False)
        self.assertNotIn('w:after="200"', out)
        self.assertIn('w:after="0"', out)

    def test_none_factor_is_a_no_op(self):
        self.assertEqual(fp.scale_spacing(self.xml, None, lists=False), self.xml)

    def test_styles_mode_scales_every_spacing_tag(self):
        styles = '<w:styles><w:style><w:spacing w:after="240"/></w:style></w:styles>'
        self.assertIn('w:after="120"', fp.scale_spacing(styles, 0.5, lists=None))


class Margins(unittest.TestCase):
    """The floor the issue reports getting breached: a run ended at a 0.35in bottom
    margin because the skill stated 0.5in and gave nothing that respected it."""

    def test_margins_shrink_to_the_request(self):
        out = fp.set_margins(document(para("x"), margins=1440), 1080)
        self.assertIn('w:top="1080"', out)
        self.assertIn('w:left="1080"', out)

    def test_margins_never_cross_the_half_inch_floor(self):
        out = fp.set_margins(document(para("x"), margins=1440), 360)   # 0.25in requested
        self.assertIn(f'w:top="{fp.MARGIN_FLOOR}"', out)
        self.assertNotIn('w:top="360"', out)

    def test_already_tight_margins_are_not_widened(self):
        out = fp.set_margins(document(para("x"), margins=800), 1080)
        self.assertIn('w:top="800"', out, "a lever must only ever remove space")

    def test_header_and_footer_offsets_are_left_alone(self):
        out = fp.set_margins(document(para("x"), margins=1440), 720)
        self.assertIn('w:header="720"', out)


class Fonts(unittest.TestCase):
    def test_font_shrinks_by_the_requested_half_points(self):
        out = fp.shrink_fonts(document(para("x", sz=22)), 1)
        self.assertIn('w:val="21"', out)

    def test_font_never_crosses_the_ten_point_floor(self):
        out = fp.shrink_fonts(document(para("x", sz=21)), 4)
        self.assertIn(f'w:val="{fp.FONT_FLOOR_SZ}"', out)
        self.assertNotIn('w:val="17"', out)

    def test_szcs_moves_with_sz(self):
        out = fp.shrink_fonts(document(para("x", sz=24)), 2)
        self.assertEqual(out.count('w:val="22"'), 2)

    def test_zero_delta_is_a_no_op(self):
        xml = document(para("x", sz=22))
        self.assertEqual(fp.shrink_fonts(xml, 0), xml)


class LeverPlan(unittest.TestCase):
    """Order and floors are the contract; the report names the lever that worked."""

    def setUp(self):
        self.plan = fp.lever_plan()

    def test_order_is_spacing_then_bullets_then_margins_then_font(self):
        labels = [label for label, _ in self.plan]
        order = [next(i for i, l in enumerate(labels) if l.startswith(prefix))
                 for prefix in ("inter-paragraph", "bullet", "margins", "body font")]
        self.assertEqual(order, sorted(order))

    def test_no_step_requests_a_margin_below_the_floor(self):
        for label, (_, _, margins, _) in self.plan:
            if margins is not None:
                self.assertGreaterEqual(margins, fp.MARGIN_FLOOR, label)

    def test_every_state_applies_cleanly_to_a_real_document(self):
        parts = {"word/document.xml": document(para("body", spacing=200, sz=22)
                                               + para("b", spacing=120, bullet=True, sz=22))}
        for label, state in self.plan:
            out = fp.apply_state(parts, state)["word/document.xml"]
            for _, size in fp.SZ.findall(out):
                self.assertGreaterEqual(int(size), fp.FONT_FLOOR_SZ, label)
            for attr, value in fp.MAR_ATTR.findall(fp.PGMAR.search(out).group(0)):
                self.assertGreaterEqual(int(value), fp.MARGIN_FLOOR, f"{label} {attr}")


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


class DocxRoundTrip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def build(self, name="in.docx", doc=None, extra=None):
        path = self.tmp / name
        with zipfile.ZipFile(str(path), "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", doc or document(para("x", spacing=200)))
            for n, c in (extra or {}).items():
                z.writestr(n, c)
        return path

    def test_non_xml_parts_survive_a_rewrite(self):
        src = self.build(extra={"word/numbering.xml": "<w:numbering/>"})
        parts, raw = fp.read_docx(src)
        out = self.tmp / "out.docx"
        fp.write_docx(out, fp.apply_state(parts, (0.5, None, None, 0)), raw)
        with zipfile.ZipFile(str(out)) as z:
            self.assertIn("word/numbering.xml", z.namelist())
            self.assertIn("[Content_Types].xml", z.namelist())
            self.assertIn('w:after="100"', z.read("word/document.xml").decode())

    def test_current_margins_are_read_back_in_twips(self):
        parts, _ = fp.read_docx(self.build(doc=document(para("x"), margins=1080)))
        self.assertEqual(fp.current_margins(parts["word/document.xml"])["bottom"], 1080)

    def test_smallest_font_is_reported_in_points(self):
        parts, _ = fp.read_docx(
            self.build(doc=document(para("a", sz=28) + para("b", sz=21))))
        self.assertEqual(fp.smallest_font_pt(parts), 10.5)


class MissingRenderer(unittest.TestCase):
    """'Skip and say so loudly rather than silently passing' — a page count nobody
    measured must never be reported as a page count that is fine."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.docx = self.tmp / "resume.docx"
        with zipfile.ZipFile(str(self.docx), "w") as z:
            z.writestr("word/document.xml", document(para("x")))

    def test_absent_renderer_fails_loudly_and_does_not_pass(self):
        code, out = run(FIT_PAGES, self.docx, "--renderer",
                        str(self.tmp / "no-such-soffice"))
        self.assertEqual(code, 2, out)
        self.assertIn("NO RENDERER", out)
        self.assertNotIn("PASS", out)

    def test_missing_file_reports_a_verdict(self):
        code, out = run(FIT_PAGES, self.tmp / "absent.docx")
        self.assertEqual(code, 2)
        self.assertIn("not found", out.lower())

    def test_non_docx_input_reports_a_verdict(self):
        junk = self.tmp / "notes.docx"
        junk.write_text("this is not a zip", encoding="utf-8")
        code, out = run(FIT_PAGES, junk, "--renderer", str(self.tmp / "none"))
        self.assertEqual(code, 2)
        self.assertIn("not a readable .docx", out)

    def test_zero_target_pages_is_a_usage_error(self):
        code, out = run(FIT_PAGES, self.docx, "--target-pages", "0")
        self.assertEqual(code, 2)
        self.assertIn("usage", out.lower())

    def test_conflicting_output_flags_are_a_usage_error(self):
        code, out = run(FIT_PAGES, self.docx, "--in-place", "-o", str(self.tmp / "o.docx"))
        self.assertEqual(code, 2)
        self.assertIn("usage", out.lower())


@unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"),
                     "needs LibreOffice to render")
class WithRenderer(unittest.TestCase):
    """The end-to-end path, when the machine happens to have a renderer."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_a_short_document_already_fits(self):
        path = self.tmp / "short.docx"
        with zipfile.ZipFile(str(path), "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", document(para("One short line.")))
        code, out = run(FIT_PAGES, path, "--target-pages", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("already fits", out)


if __name__ == "__main__":
    unittest.main()
