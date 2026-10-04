"""career_confirm (`jsk kb confirm` until 6.0), end to end: an answer, a source document, a selection's summary or
headline."""
import datetime
import os
import tempfile
import unittest

import careerkit
from pathlib import Path

from storekit import Workspace

from jsk.infra.oxigraph import record


def other_drive(root):
    """A drive letter that is not `root`'s: across drives, relpath and commonpath raise."""
    return "Q:" if os.path.splitdrive(os.path.abspath(root))[0].upper() != "Q:" else "R:"


ANSWER = "Yes - 42 sites at hand-over, and a quarter each before the platform."


class Confirm(Workspace):
    def test_confirming_answers_the_open_questions_and_logs_the_answer(self):
        code, out = self.confirm("k:ach_site_onboarding_sites_one_platform",
                                "prj_site_onboarding", answer=ANSWER)
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual([f.text() for f in s.findings], [])
        text = self.kb_text()
        self.assertIn("k:q_sites_bullet j:about k:ach_site_onboarding_sites_one_platform", text)
        self.assertEqual(text.count('j:answered "' + datetime.date.today().isoformat()), 2)
        log = self.log_text()
        self.assertIn(f'j:answer "{ANSWER}"', log)
        self.assertIn("j:by j:confirm", log)

    def test_an_answer_that_says_nothing_is_refused(self):
        for said in ("yes", "OK.", "confirmed", "", "<answer>", "..."):
            with self.subTest(said=said):
                code, out = self.confirm("prj_site_onboarding", answer=said)
                self.assertEqual(code, 1)
                self.assertIn("is not an answer", out)

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.confirm("prj_site_onbording", answer=ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_site_onboarding?", out)

    def test_an_entry_that_is_not_a_claim(self):
        code, out = self.confirm("met_sites", answer=ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("a Metric is not a claim", out)

    def test_a_denial_is_not_a_confirmation(self):
        for said in ("No.", "nope", "Wrong", "not true"):
            with self.subTest(said=said):
                code, out = self.confirm("prj_site_onboarding", answer=said)
                self.assertEqual(code, 1)
                self.assertIn("a denial is not a confirmation", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_confirming_what_is_confirmed_changes_nothing(self):
        code, out = self.confirm("prj_clinical_events", answer=ANSWER)
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))

    def test_an_answer_that_only_names_a_document_is_refused(self):
        # "From prior-resume.pdf" confirmed what was extracted, with nothing checking it.
        for said in ("From prior-resume.pdf", "per my CV.docx", "see resume.md",
                     "Source: old resume.txt", "prior-resume.pdf", "Yes, from the resume.pdf"):
            with self.subTest(said=said):
                code, out = self.confirm("prj_site_onboarding", answer=said)
                self.assertEqual(code, 1, out)
                self.assertIn('source="<file>" and quote=', out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_an_answer_naming_a_file_among_its_words_passes(self):
        said = "Yes - it was 42 sites by hand-over; my old resume.pdf undersold it."
        code, out = self.confirm("k:ach_site_onboarding_sites_one_platform",
                                answer=said)
        self.assertEqual(code, 0, out)


QUOTE = ("brought 42 residential care sites onto one platform, cutting onboarding from a "
         "quarter to two weeks")


SOURCE = """# Prior resume

Care Group, 2020-2023
- Led the site programme and brought 42 residential care
  sites onto one platform, cutting onboarding from a quarter to two weeks.
"""


class ConfirmFromSource(Workspace):
    """`source` and `quote`: a fact extracted from a document is confirmed by the
    document's own words, checked, not by an answer naming it."""

    def setUp(self):
        super().setUp()
        self.path("imports").mkdir()
        self.doc = self.path("imports/prior-resume.md")
        self.doc.write_text(SOURCE, encoding="utf-8")

    def confirm_quote(self, *ids, source=None, quote=QUOTE):
        return self.confirm(*ids, source=str(source or self.doc), quote=quote)

    def test_a_quote_the_document_holds_confirms_and_is_logged(self):
        code, out = self.confirm_quote("k:ach_site_onboarding_sites_one_platform")
        self.assertEqual(code, 0, out)
        log = self.log_text()
        self.assertIn(f'From imports/prior-resume.md: \\"{QUOTE}\\"', log)
        self.assertEqual([f.text() for f in self.loaded().findings], [])

    def test_a_quote_the_document_does_not_hold_is_refused(self):
        code, out = self.confirm_quote("k:ach_site_onboarding_sites_one_platform",
                                 quote="brought 45 residential care sites onto one platform")
        self.assertEqual(code, 1, out)
        self.assertIn("does not say", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_a_number_the_quote_does_not_state_is_refused(self):
        code, out = self.confirm_quote("k:ach_site_onboarding_sites_one_platform",
                                 quote="residential care sites onto one platform")
        self.assertEqual(code, 1, out)
        self.assertIn("'42'", out)
        # The fix sends it to the person: the number is theirs to confirm, not the document's.
        self.assertIn("ask the person and confirm with their answer", out)

    def test_a_clause_the_quote_does_not_hold_is_refused(self):
        # The document says the first half; the session added the second.
        code, out = self.confirm_quote("k:ach_site_onboarding_sites_one_platform",
                                 quote="brought 42 residential care sites onto one platform")
        self.assertEqual(code, 1, out)
        self.assertIn("'quarter'", out)
        self.assertIn("ask the person", out)

    def test_a_quote_about_something_else_is_refused(self):
        code, out = self.confirm_quote("k:ach_site_onboarding_sites_one_platform",
                                 quote="Led the site programme and brought 42")
        self.assertEqual(code, 1, out)
        self.assertIn("the quote does not", out)

    def test_an_entry_with_no_text_needs_only_the_quote(self):
        code, out = self.confirm_quote("prj_site_onboarding", quote="Led the site programme")
        self.assertEqual(code, 0, out)

    def test_a_short_quote_is_refused(self):
        for quote in ("yes", "42 sites", ""):
            with self.subTest(quote=quote):
                code, out = self.confirm_quote("prj_site_onboarding", quote=quote)
                self.assertEqual(code, 1, out)
                self.assertIn("three words", out)

    def test_source_and_answer_together_are_a_usage_error(self):
        code, out = self.confirm("prj_site_onboarding", answer=ANSWER,
                            source=str(self.doc), quote=QUOTE)
        self.assertEqual(code, 2, out)
        code, out = self.confirm("prj_site_onboarding", source=str(self.doc))
        self.assertEqual(code, 2, out)

    def test_a_file_outside_the_workspace_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp, "cv.md")
            outside.write_text(SOURCE, encoding="utf-8")
            code, out = self.confirm_quote("prj_site_onboarding", source=outside)
        self.assertEqual(code, 1, out)
        self.assertIn("inside this workspace", out)

    @unittest.skipUnless(os.name == "nt", "drives are a Windows thing")
    def test_a_file_on_another_drive_is_refused(self):
        from unittest import mock

        elsewhere = other_drive(self.root) + "\\cv.md"
        real = os.path.isfile
        with mock.patch("os.path.isfile", lambda p: p == elsewhere or real(p)):
            code, out = self.confirm_quote("prj_site_onboarding", source=elsewhere)
        self.assertEqual(code, 1, out)
        self.assertIn("inside this workspace", out)

    def test_a_docx_is_refused_with_the_fix(self):
        docx = self.path("imports/cv.docx")
        docx.write_bytes(b"PK\x03\x04")
        code, out = self.confirm_quote("prj_site_onboarding", source=docx)
        self.assertEqual(code, 1, out)
        self.assertIn("convert it to .md or .txt first", out)

    def test_a_document_in_another_encoding_is_refused_not_crashed(self):
        self.doc.write_bytes(SOURCE.replace("Care Group", "Café Group").encode("cp1252"))
        code, out = self.confirm_quote("prj_site_onboarding", quote="Led the site programme")
        self.assertEqual(code, 1, out)
        self.assertIn("prior-resume.md is not UTF-8 text", out)

    def test_a_pdf_without_pymupdf_is_refused_with_the_fix(self):
        import sys
        from unittest import mock

        pdf = self.path("imports/cv.pdf")
        pdf.write_bytes(b"%PDF-1.4\n")
        with mock.patch.dict(sys.modules, {"pymupdf": None}):
            code, out = self.confirm_quote("prj_site_onboarding", source=pdf)
        self.assertEqual(code, 1, out)
        self.assertIn("install pymupdf, or convert it to .md", out)


class ConfirmSummary(Workspace):
    """`block="summary"` with a target: a summary is confirmed by the person's answer, kept in the
    selection graph with the text's hash - not by flipping its status. A resume.json held it
    until 6.0 (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2); that form
    exits 2 naming the target form."""

    TEXT = "Architect who builds clinical event platforms other teams build on."
    TARGET = "resumes/globex"

    def setUp(self):
        super().setUp()
        self.write({"resume": 2, "bullets": ["ach_clinical_events_event_latency"],
                    "summary": {"text": self.TEXT, "status": "inferred"}, "pages": 2})

    def write(self, doc):
        self.seed()
        careerkit.select(self.root, doc, "globex")

    def doc(self):
        from jsk.adapters.cli.compose import selection

        return selection.read(str(self.root), self.TARGET)

    def confirm_summary(self, answer="Yes, that is exactly what I do.", target=None):
        return self.confirm(target=target or self.TARGET, block="summary", answer=answer)

    def test_the_answer_and_the_text_s_hash_are_written(self):
        from jsk.domain.resume import short

        code, out = self.confirm_summary()
        self.assertEqual(code, 0, out)
        self.assertIn(f"{self.TARGET}/resume", out, "the diff names the selection graph")
        doc = self.doc()
        self.assertEqual(doc["summary"], {"text": self.TEXT, "status": "confirmed",
                                          "answer": "Yes, that is exactly what I do.",
                                          "text_sha256": short.digest(self.TEXT)})
        self.assertEqual(short.shape(doc), [])
        self.assertEqual(record.state(self.loaded()).log_revision, 2)   # not in the career
        code, out = self.confirm_summary()
        self.assertEqual(code, 0, out)
        self.assertIn("confirmed already", out)

    def test_an_answer_that_says_nothing_is_refused(self):
        for said in ("yes", "ok", "nope"):
            with self.subTest(said=said):
                code, out = self.confirm_summary(said)
                self.assertEqual(code, 1, out)
        self.assertEqual(self.doc()["summary"]["status"], "inferred")

    def test_no_summary_is_refused(self):
        self.write({"resume": 2, "bullets": ["ach_clinical_events_event_latency"]})
        code, out = self.confirm_summary()
        self.assertEqual(code, 1, out)
        self.assertIn("has no summary to confirm", out)

    def test_ids_with_summary_are_a_usage_error(self):
        code, out = self.confirm("prj_site_onboarding", target=self.TARGET, block="summary",
                            answer=ANSWER)
        self.assertEqual(code, 2, out)


class ConfirmHeadline(Workspace):
    """`block="headline"` with a target: the posting's title under the name, confirmed the way the
    summary is - the person's answer and the text's hash, kept in the selection graph."""

    TITLE = "Principal Clinical Platform Architect"
    TARGET = "resumes/globex"

    def setUp(self):
        super().setUp()
        self.write({"resume": 2, "bullets": ["ach_clinical_events_event_latency"],
                    "headline": {"text": self.TITLE, "status": "inferred"}})

    def write(self, doc):
        self.seed()
        careerkit.select(self.root, doc, "globex")

    def test_the_headline_is_confirmed_beside_its_answer(self):
        from jsk.adapters.cli.compose import selection
        from jsk.domain.resume import short

        code, out = self.confirm(target=self.TARGET, block="headline",
                            answer="Yes, that is the title I held at Globex.")
        self.assertEqual(code, 0, out)
        self.assertIn("confirmed the headline", out)
        doc = selection.read(str(self.root), self.TARGET)
        self.assertEqual(doc["headline"]["status"], "confirmed")
        self.assertEqual(doc["headline"]["text_sha256"], short.digest(self.TITLE))
        self.assertEqual(short.shape(doc), [])

    def test_a_selection_with_no_headline_is_refused(self):
        self.write({"resume": 2, "bullets": ["ach_clinical_events_event_latency"]})
        code, out = self.confirm(target=self.TARGET, block="headline", answer=ANSWER)
        self.assertEqual(code, 1, out)
        self.assertIn("has no headline to confirm", out)

    def test_a_target_without_a_block_is_a_usage_error(self):
        code, out = self.confirm(target=self.TARGET, answer=ANSWER)
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
