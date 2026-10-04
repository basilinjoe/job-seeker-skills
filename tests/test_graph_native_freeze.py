"""Freezing and letter-checking a graph-native application: P5 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md.

The rules pinned: app_freeze (`jsk app freeze` until 6.0) on a graph-native application reads its record from the
stored selection, never a resume.json (Ruling 11), and its `recordSha256` is the SHA-256 of
the selection's canonical text (Ruling 7); it renames the directory to the day it was sent
and moves the posting, review, gaps and resume graphs with the application graph, so all
five sit under the new name and none under the old (Ruling 10); afterwards the selection and
the posting refuse every change and a re-ship into the frozen directory is refused - a
held-back freeze (`submitted` false) as much as a sent one, saying it was not sent; a
graph-native application with no selection is refused naming `resume_select`; and letter_check
(`jsk letter check --record <stem>` until 6.0) traces a letter's numbers through the stored selection and
reads its quotes from the stored advert lines, failing a number the career cannot back as it
does for a resume.json.
"""
import hashlib
import os
import unittest
from pathlib import Path
from unittest import mock

import appkit
import recordkit
import shipkit
from jsk.adapters.compose import native, selection
from jsk.domain.posting.errors import Refused
from jsk.domain.resume.selection import canonical
from test_graph_native_apps import ADVERT, STEM
from test_graph_native_selection import SUMMARY, TODAY, Workspace, fails

SENT = "2026-10-02"
DATED = f"{SENT}-{STEM}"
KINDS = ("posting", "review", "gaps", "resume", "application")
# A letter with nothing a gate could object to: no numeral, short, plain.
CLEAN_LETTER = ("Dear Hiring Team,\n\n"
                "I run event platforms that other teams build on, and I would like to do "
                "the same for Acme. My resume sets out the work in detail.\n\n"
                "Sincerely,\nTest Person\n")


class Frozen(Workspace):
    """ADVERT analysed, selected and shipped into applications/acme-platform, faked TeX."""

    def setUp(self):
        super().setUp()
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)

    def shipped(self):
        from jsk.adapters.compose import render

        self.selected()
        # The parse gate's strict pass wants a summary heading, and a summary renders
        # only once the person has confirmed its words.
        self.assertEqual(fails(selection.update(self.root, STEM, summary=SUMMARY,
                                                today=TODAY).findings), [])
        selection.confirm(self.root, STEM, "summary", "Yes, that is what I do.")
        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile()):
            selection.ship_target(self.root, STEM, fit=False, today=TODAY)
        self.assertTrue(list(self.app.glob("*.pdf")))

    def freeze(self, app=None):
        return recordkit.freeze(self.root, app or self.app, SENT, "Workday portal")

    @property
    def sent(self):
        return Path(self.root) / "applications" / DATED

    def frozen(self, name):
        """The sorted values of the frozen application's `j:<name>`."""
        return sorted(t.object.value for t in
                      appkit.triples(self.root, f"applications/{DATED}/application") or ()
                      if t.predicate.value.endswith("#" + name))

    def expected_sha(self, doc):
        return [hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest()]


class Freeze(Frozen):
    def test_a_graph_native_freeze_hashes_the_canonical_selection_and_moves_five_graphs(self):
        self.shipped()
        doc = selection.read(self.root, STEM)
        before = {kind: appkit.facts(self.root, f"applications/{STEM}/{kind}")
                  for kind in KINDS[:-1]}
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertFalse(self.app.exists(), "the directory was renamed")
        self.assertTrue(self.sent.is_dir(), out)
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assertIsNone(appkit.triples(self.root, f"applications/{STEM}/{kind}"),
                                  "nothing stays under the old name")
                self.assertIsNotNone(appkit.triples(self.root, f"applications/{DATED}/{kind}"))
                if kind in before:
                    # Moved whole: the same facts under the new name.
                    self.assertEqual(appkit.facts(self.root, f"applications/{DATED}/{kind}"),
                                     before[kind])
        # Ruling 7: the hash is canonical()'s, not a file's - there is no resume.json.
        self.assertEqual(self.frozen("recordSha256"), self.expected_sha(doc))
        self.assertFalse(list(self.sent.glob("*.json")), "no resume.json was written")
        documents = self.frozen("document")
        self.assertTrue(documents and all(d.endswith(".pdf") for d in documents), documents)
        # What was sent is the plan's `sent`, built from the selection.
        self.assertTrue(self.frozen("carried"))

    def test_a_frozen_graph_native_application_refuses_every_change(self):
        self.shipped()
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        calls = {"resume_update": lambda: selection.update(self.root, DATED, pages=1,
                                                           today=TODAY),
                 "posting_decide": lambda: native.decide(self.root, DATED, remove=["x"],
                                                         today=TODAY)}
        for name, call in calls.items():
            with self.subTest(tool=name), self.assertRaises(Refused) as caught:
                call()
            self.assertIn(f"was sent on {SENT}", str(caught.exception))

    def test_a_held_back_freeze_refuses_every_change_and_says_it_was_not_sent(self):
        """`submitted` false freezes without sending: the guards keyed on the day it was
        sent let every tool keep writing under the record that froze it (2026-10-02)."""
        from jsk.adapters.compose import render
        from jsk.application.record.refusals import Refused as ConfirmRefused

        self.shipped()
        code, out = recordkit.freeze(self.root, self.app, "false", "held back")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.app.is_dir(), "a held-back freeze keeps its name")
        names = [f"applications/{STEM}/{kind}" for kind in KINDS]
        before = {n: appkit.facts(self.root, n) for n in names}
        sha = [t.object.value for t in appkit.triples(self.root, names[-1])
               if t.predicate.value.endswith("#recordSha256")]
        calls = {
            "resume_update": lambda: selection.update(self.root, STEM, pages=1, today=TODAY),
            "resume_select": lambda: selection.select(self.root, STEM, mode="from_match",
                                                      replace=True, today=TODAY),
            "posting_decide": lambda: native.decide(self.root, STEM, rows=[], drops=[],
                                                    today=TODAY),
            "posting_capture": lambda: native.capture(self.root, STEM, text=ADVERT,
                                                      replace=True, today=TODAY),
            "assessment_review": lambda: native.review(self.root, STEM, fit="poor",
                                                       today=TODAY),
            "assessment_derive": lambda: native.derive_assessment(self.root, STEM,
                                                                  today=TODAY),
            "career_confirm": lambda: selection.confirm(self.root, STEM, "summary",
                                                        "Yes, that is what I do."),
        }
        for name, call in calls.items():
            with self.subTest(tool=name), self.assertRaises((Refused, ConfirmRefused)) as e:
                call()
            said = str(e.exception) + " " + str(getattr(e.exception, "fix", ""))
            self.assertIn("frozen (held back, not sent)", said)
            self.assertIn("posting_capture", said)
        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile()), \
                self.assertRaises(Refused) as caught:
            selection.ship_target(self.root, STEM, fit=False, today=TODAY)
        self.assertIn("held back, not sent", str(caught.exception))
        self.assertNotIn("what was sent", str(caught.exception))
        self.assertIn("posting_capture", caught.exception.fix)
        self.assertEqual({n: appkit.facts(self.root, n) for n in names}, before,
                         "nothing was written")
        self.assertEqual(sha, self.expected_sha(selection.read(self.root, STEM)))

    def test_a_reship_by_target_into_the_frozen_directory_is_refused(self):
        from jsk.adapters.compose import render

        self.shipped()
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile()), \
                self.assertRaises(Refused) as caught:
            selection.ship_target(self.root, DATED, fit=False, today=TODAY)
        self.assertIn("frozen", str(caught.exception).lower() + caught.exception.fix.lower())

    def test_a_graph_native_application_with_no_selection_is_refused_naming_the_tool(self):
        self.analysed()
        self.app.mkdir(parents=True)
        shipkit.build_pdf(self.app / "Test_Person_Resume.pdf", shipkit.CLEAN_RESUME)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn(f"no resume stored for {STEM}", out)
        self.assertIn("resume_select", out)
        self.assertTrue(self.app.is_dir(), "nothing was renamed")
        self.assertIsNone(appkit.triples(self.root, f"applications/{STEM}/application"))

    def test_a_resume_json_beside_a_graph_native_application_is_never_the_record(self):
        """Ruling 11: the selection is the record, so a file planted beside it - with a
        bullet the selection does not carry - changes nothing the freeze writes."""
        self.shipped()
        doc = selection.read(self.root, STEM)
        (self.app / "resume.json").write_text('{"resume": 2, "bullets": ["ach_nothing"]}',
                                              encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frozen("recordSha256"), self.expected_sha(doc))

    def test_a_clean_letter_beside_the_resume_is_gated_and_frozen(self):
        self.shipped()
        (self.app / "cover-letter.txt").write_text(CLEAN_LETTER, encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn(f"letter.py cover-letter.txt --record {STEM}", out)
        self.assertIn("cover-letter.txt", self.frozen("document"))


class Letter(Frozen):
    def letter(self, text):
        path = Path(self.root) / "cover-letter.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_clean_letter_passes_against_a_graph_native_application(self):
        self.selected()
        code, out = recordkit.letter(str(self.letter(CLEAN_LETTER)), STEM, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - fit to send", out)
        self.assertIn(f"against: applications/{STEM}/resume", out)

    def test_a_number_the_career_cannot_back_fails_as_it_does_for_a_file(self):
        self.selected()
        text = CLEAN_LETTER.replace("in detail.", "in detail, including 9137 tenants.")
        code, out = recordkit.letter(str(self.letter(text)), STEM, self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("'9137'", out)
        self.assertIn("DO NOT SEND", out)

    def test_the_advert_a_letter_may_quote_is_the_stored_lines(self):
        """No posting.md exists for a graph-native application; the lines the store holds
        are what a quotation in the letter is matched against."""
        from jsk.adapters.compose import resume
        from jsk.application.gates.letter import advert

        self.selected()
        ref = selection.ref_for(STEM, root=self.root)
        text = advert(ref, resume.career(self.root))
        self.assertIn("Run the clinical event platform for forty hospitals.", text)
        self.assertIn("Rust experience required.", text)
        self.assertFalse((self.app / "posting.md").exists())

    def test_an_application_with_no_selection_is_refused_naming_the_tool(self):
        self.analysed()
        code, out = recordkit.letter(str(self.letter(CLEAN_LETTER)), STEM, self.root)
        self.assertEqual(code, 2, out)
        self.assertIn("resume_select", out)


if __name__ == "__main__":
    unittest.main()
