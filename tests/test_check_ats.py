"""check_ats.py is the gate the whole skill rests on: "Never hand over a resume
you have not checked." These tests pin the failures it must catch, and — just as
importantly — pin that a correct resume still passes.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import (CHECK_ATS, CLEAN_RESUME, EXAMPLE_URS, RENDER_RESUME,
                      build_pdf, build_text, resume_with, run, urs_module)

tex = urs_module("urs.tex")

BODY = "Cut order-processing latency 62 percent by decomposing a monolithic service."


class CheckATSCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def check(self, paragraphs=None, strict=False, name="resume.txt", **kw):
        path = build_text(self.tmp / name,
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

    def test_a_pdf_that_is_not_a_pdf_reports_a_verdict(self):
        path = self.tmp / "fake.pdf"
        path.write_text("not a PDF at all", encoding="utf-8")
        code, out = run(CHECK_ATS, path)
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", out)
        self.assertIn("FAIL", out)

    def test_missing_file_reports_a_verdict(self):
        code, out = run(CHECK_ATS, self.tmp / "absent.pdf")
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", out)

    def test_the_docx_is_no_longer_accepted(self):
        """It was the deliverable; it is not one any more, and a gate that
        silently accepted it would be checking a file nobody sends."""
        path = self.tmp / "resume.docx"
        path.write_text("x", encoding="utf-8")
        code, out = run(CHECK_ATS, path)
        self.assertEqual(code, 1)
        self.assertIn(".pdf", out)


class BulletGlyphs(CheckATSCase):
    """The one structural rule with a text-level meaning.

    In a .docx a leading bullet character meant the list had no real numbering.
    A PDF has no list structure to compare against - the marker is a glyph in
    the text either way - so the question became which glyph, not whether one
    was typed. U+2022 and a hyphen are what the two templates emit and what
    every parser maps; the decorative ones are what break.
    """

    def test_a_decorative_glyph_fails(self):
        code, out = self.check(resume_with((BODY, "▪ Decorative bullet glyph")))
        self.assertFails(out, code, "bullet")

    def test_the_templates_own_bullet_passes(self):
        code, out = self.check(resume_with((BODY, "• Cut latency 62 percent by "
                                                  "decomposing a monolith.")))
        self.assertPasses(out, code)

    def test_the_ascii_variants_hyphen_passes(self):
        code, out = self.check(resume_with((BODY, "- Cut latency 62 percent by "
                                                  "decomposing a monolith.")))
        self.assertPasses(out, code)


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
    def test_a_break_inside_a_paragraph_does_not_hide_what_follows(self):
        """A rule that scans line starts only sees the lines it was given. The
        .docx form of this was <w:br/> having to become a newline; the text form
        is that an embedded break still splits."""
        fused = "Owned the migration.\n\u25aa Decorative bullet after a break"
        code, out = self.check(resume_with((BODY, fused)))
        self.assertFails(out, code, "bullet")


class ThePdfItself(CheckATSCase):
    """Rules about the deliverable, not about what it says.

    These are what replaced the font-name allowlist. A LaTeX PDF embeds Latin
    Modern, which no list of Office fonts would have contained, and the name was
    never the point: what matters is whether text comes back out at all.
    """

    def test_a_pdf_with_no_text_layer_fails(self):
        path = build_pdf(self.tmp / "scan.pdf", blank=True)
        code, out = run(CHECK_ATS, path)
        self.assertEqual(code, 1, out)
        self.assertIn("extractable text", out)

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to render")
    def test_the_rendered_presentation_pdf_passes(self):
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_au_default", "--pdf")
        self.assertEqual(code, 0, out)
        code, out = run(CHECK_ATS, self.tmp / "Priya_Raman_Resume.pdf")
        self.assertPasses(out, code)

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to render")
    def test_the_rendered_ats_pdf_passes_strict(self):
        """The ligature trap: T1 Computer Modern turns "fi" into U+FB01, so an
        ATS-maximal PDF failed its own ASCII rule until the emitter broke the
        pairs. The .docx never showed this, because nothing rendered it."""
        code, out = run(RENDER_RESUME, EXAMPLE_URS, "--out", self.tmp,
                        "--view", "view_au_default", "--pdf", "--ats-max")
        self.assertEqual(code, 0, out)
        code, out = run(CHECK_ATS, self.tmp / "Priya_Raman_Resume_ATS.pdf", "--strict")
        self.assertPasses(out, code)


if __name__ == "__main__":
    unittest.main()
