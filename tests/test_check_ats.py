"""check_ats.py is the gate the whole skill rests on: "Never hand over a resume
you have not checked." These tests pin the failures it must catch, and — just as
importantly — pin that a correct resume still passes.
"""
import tempfile
import unittest
import zipfile
from pathlib import Path

from fixtures import CHECK_ATS, CLEAN_RESUME, build_docx, resume_with, run

BODY = "Cut order-processing latency 62 percent by decomposing a monolithic service."


class CheckATSCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def check(self, paragraphs=None, strict=False, name="resume.docx", **kw):
        path = build_docx(self.tmp / name,
                          CLEAN_RESUME if paragraphs is None else paragraphs, **kw)
        args = [path, "--strict"] if strict else [path]
        return run(CHECK_ATS, *args)

    def assertFails(self, out, code, needle=None):
        self.assertEqual(code, 1, f"expected FAIL, got exit {code}:\n{out}")
        self.assertIn("DO NOT SEND", out)
        if needle:
            self.assertIn(needle, out.lower())

    def assertPasses(self, out, code):
        self.assertEqual(code, 0, f"expected PASS, got exit {code}:\n{out}")
        self.assertIn("PASS - safe to send", out)


class CleanResume(CheckATSCase):
    """The regression guard: the fixes must not make the gate unusable."""

    def test_clean_resume_passes(self):
        code, out = self.check()
        self.assertPasses(out, code)

    def test_clean_resume_passes_strict(self):
        code, out = self.check(strict=True)
        self.assertPasses(out, code)


class Placeholders(CheckATSCase):
    """ats-rules.md: "Search the finished text for `[` before delivering."

    The narrow allowlist regex missed the shapes an LLM actually leaves behind.
    """

    CAUGHT_BEFORE = ["[X%]", "[TBD]", "[Y]", "[metric needed]"]
    MISSED_BEFORE = ["[NUMBER]", "[insert metric]", "[X% reduction]", "[62%]",
                     "[quantify]", "[add scale here]"]

    def test_every_placeholder_form_is_caught(self):
        for ph in self.CAUGHT_BEFORE + self.MISSED_BEFORE:
            with self.subTest(placeholder=ph):
                code, out = self.check(resume_with((BODY, f"Scaled the platform to {ph} tenants.")))
                self.assertFails(out, code, "placeholder")

    def test_unmatched_open_bracket_is_caught(self):
        code, out = self.check(resume_with((BODY, "Scaled the platform to [NUMBER tenants.")))
        self.assertFails(out, code, "bracket")

    def test_multiple_placeholders_are_all_reported(self):
        lines = resume_with((BODY, "Cut latency [X% reduction] across [NUMBER] tenants."))
        code, out = self.check(lines)
        self.assertFails(out, code, "placeholder")
        self.assertIn("X% reduction", out)


class SectionHeadings(CheckATSCase):
    """ats-rules.md:28 - "A heading like 'Core Competencies' is invisible to a
    parser matching on 'Skills'." The check must look at headings, not prose.
    """

    TRAP = [
        "Jane Doe",
        "Phone: +61 400 123 456 | Email: jane.doe@example.com",
        "Professional Summary",
        "Architect with deep skills in distributed systems and a strong education in formal methods.",
        "Core Competencies",
        "Azure, Bicep, Kubernetes",
        "Professional Experience",
        "Senior Architect, Acme Corp | Jun 2025 - Present",
        "Owned the platform migration.",
        "Architect, Globex | Jan 2018 - May 2025",
        "Built event-driven services.",
        "Lead Engineer, Initech | Mar 2015 - Dec 2017",
        "Ran the delivery team.",
        "Academic Background",
        "BSc Computer Science, 2014",
    ]

    def test_words_in_prose_do_not_satisfy_the_heading_rule(self):
        code, out = self.check(self.TRAP)
        self.assertFails(out, code)
        self.assertIn("skills", out.lower())
        self.assertIn("education", out.lower())

    def test_unstyled_short_headings_are_recognised(self):
        code, out = self.check()
        self.assertPasses(out, code)

    def test_styled_headings_are_recognised(self):
        styled = [(t, "Heading1") if t in ("Professional Summary", "Technical Skills",
                                           "Professional Experience", "Education") else t
                  for t in CLEAN_RESUME]
        code, out = self.check(styled)
        self.assertPasses(out, code)

    def test_missing_section_entirely_still_fails(self):
        code, out = self.check(resume_with(("Education", None),
                                           ("BSc Computer Science, University of Melbourne, 2014", None)))
        self.assertFails(out, code, "education")


class ContactDetails(CheckATSCase):
    """A date range satisfied the phone regex, so a resume with no phone passed."""

    NO_PHONE = "Email: jane.doe@example.com | Melbourne, Australia"

    def test_year_range_is_not_a_phone_number(self):
        lines = resume_with(
            ("Phone: +61 400 123 456 | Email: jane.doe@example.com", self.NO_PHONE),
            ("Architect, Globex | Jan 2018 - May 2025", "Architect, Globex | 2018 - 2021"),
        )
        code, out = self.check(lines)
        self.assertFails(out, code, "phone")

    def test_missing_phone_is_caught(self):
        code, out = self.check(resume_with(
            ("Phone: +61 400 123 456 | Email: jane.doe@example.com", self.NO_PHONE)))
        self.assertFails(out, code, "phone")

    def test_real_phone_formats_are_accepted(self):
        for phone in ("+61 400 123 456", "(555) 123-4567", "+1 555 123 4567", "0400 123 456"):
            with self.subTest(phone=phone):
                code, out = self.check(resume_with(
                    ("Phone: +61 400 123 456 | Email: jane.doe@example.com",
                     f"Phone: {phone} | Email: jane.doe@example.com")))
                self.assertPasses(out, code)

    def test_missing_email_is_caught(self):
        code, out = self.check(resume_with(
            ("Phone: +61 400 123 456 | Email: jane.doe@example.com",
             "Phone: +61 400 123 456 | Melbourne, Australia")))
        self.assertFails(out, code, "email")


class MalformedInput(CheckATSCase):
    """A gate that crashes gives no verdict. It must always report."""

    def test_renamed_non_zip_reports_a_verdict(self):
        path = self.tmp / "fake.docx"
        path.write_text("not a zip at all", encoding="utf-8")
        code, out = run(CHECK_ATS, path)
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", out)
        self.assertIn("FAIL", out)

    def test_zip_without_document_xml_reports_a_verdict(self):
        path = self.tmp / "nodoc.docx"
        with zipfile.ZipFile(str(path), "w") as z:
            z.writestr("word/other.xml", "<a/>")
        code, out = run(CHECK_ATS, path)
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", out)
        self.assertIn("FAIL", out)

    def test_missing_file_reports_a_verdict(self):
        code, out = run(CHECK_ATS, self.tmp / "absent.docx")
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", out)

    def test_wrong_extension_is_rejected(self):
        path = self.tmp / "resume.pdf"
        path.write_text("x", encoding="utf-8")
        code, out = run(CHECK_ATS, path)
        self.assertEqual(code, 1)
        self.assertIn("docx", out)


class StructuralKillers(CheckATSCase):
    """Positive controls: these already worked and must not regress."""

    def test_table(self):
        code, out = self.check(body_extra="<w:tbl><w:tr><w:tc/></w:tr></w:tbl>")
        self.assertFails(out, code, "table")

    def test_text_box(self):
        code, out = self.check(body_extra="<w:p><w:r><w:pict><v:shape><w:txbxContent/></v:shape></w:pict></w:r></w:p>")
        self.assertFails(out, code, "text box")

    def test_image(self):
        code, out = self.check(extra_parts={"word/media/image1.png": "fake"})
        self.assertFails(out, code, "image")

    def test_drawing(self):
        code, out = self.check(body_extra="<w:p><w:r><w:drawing/></w:r></w:p>")
        self.assertFails(out, code, "drawing")

    def test_smartart(self):
        code, out = self.check(extra_parts={"word/diagrams/data1.xml": "<a/>"})
        self.assertFails(out, code, "smartart")

    def test_header_content(self):
        hdr = ('<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               "<w:p><w:r><w:t>jane@example.com</w:t></w:r></w:p></w:hdr>")
        code, out = self.check(extra_parts={"word/header1.xml": hdr})
        self.assertFails(out, code, "header")

    def test_multi_column(self):
        code, out = self.check(body_extra='<w:sectPr><w:cols w:num="2"/></w:sectPr>')
        self.assertFails(out, code, "column")

    def test_typed_bullet_glyph(self):
        code, out = self.check(resume_with((BODY, "• Typed bullet glyph as text")))
        self.assertFails(out, code, "bullet")


class StrictMode(CheckATSCase):
    def test_non_ascii_fails_under_strict_only(self):
        lines = resume_with(("Phone: +61 400 123 456 | Email: jane.doe@example.com",
                             "Phone: +61 400 123 456 · Email: jane.doe@example.com"))
        code, _ = self.check(lines)
        self.assertEqual(code, 0, "middle dot is fine in the presentation variant")
        code, out = self.check(lines, strict=True)
        self.assertFails(out, code, "non-ascii")

    def test_arrow_warns_normally_and_fails_under_strict(self):
        lines = resume_with((BODY, "Engineer → Senior Engineer → Lead → Architect"))
        code, out = self.check(lines)
        self.assertEqual(code, 0)
        self.assertIn("arrow", out.lower())
        code, out = self.check(lines, strict=True)
        self.assertFails(out, code, "arrow")

    def test_en_dash_date_range_fails_under_strict(self):
        lines = resume_with(("Architect, Globex | Jan 2018 - May 2025",
                             "Architect, Globex | 2018 – 2025"))
        code, out = self.check(lines, strict=True)
        self.assertFails(out, code)


class TextExtraction(CheckATSCase):
    def test_line_break_does_not_fuse_text(self):
        """<w:br/> must become a newline, or a typed bullet after a break hides."""
        para = ('<w:p><w:r><w:t>Owned the migration.</w:t><w:br/>'
                '<w:t>• Typed bullet after a break</w:t></w:r></w:p>')
        code, out = self.check(resume_with((BODY, None)), body_extra=para)
        self.assertFails(out, code, "bullet")


if __name__ == "__main__":
    unittest.main()
