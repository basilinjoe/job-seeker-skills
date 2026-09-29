"""`jsk kb`, end to end, on a copy of the fixture workspace in its own store."""
import contextlib
import datetime
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import storekit
from test_graph_changeset import PFX
from test_graph_pack import edit_career
from test_graph_shapes import FIXTURES

from jsk import cli
from jsk.graph import db, record
from jsk.graph import ontology as O
from jsk.graph import store as S

BRAINDUMP = PFX + """
op:changeset op:base 2 ; op:summary "The payments project, from the 24 Sep braindump." .

op:add {
    k:prj_payments j:name "Payments platform" ; j:position k:pos_meridian_principal ;
        j:strength 4 ; j:recency 2025 ; j:uses c:kafka, c:payments ;
        j:headlineMetric k:met_settlement .
    [] j:project k:prj_payments ; j:rank 1 ;
        j:text "Cut settlement latency from 800 ms to 200 ms." ;
        j:cites k:met_settlement ; j:shows c:kafka .
    [] j:project k:prj_payments ; j:rank 2 ;
        j:text "Moved card payments onto the event backbone." ; j:shows c:payments .
    k:met_settlement j:subject "settlement latency" ; j:unit "ms" ; j:direction j:decrease .
    k:met_settlement.v1 j:of k:met_settlement ; j:baseline 800 ; j:value 200 ;
        j:confidence j:reported .
    c:payments a j:Domain ; j:label "payments" .
}
"""


def other_drive(root):
    """A drive letter that is not `root`'s: across drives, relpath and commonpath raise."""
    return "Q:" if os.path.splitdrive(os.path.abspath(root))[0].upper() != "Q:" else "R:"


class Workspace(unittest.TestCase):
    """The fixture copied, and put in a store the first time a test runs `jsk kb` on it -
    so a test can edit the fixture's text first (a record with a FAIL, say: the store
    keeps what it is given)."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.seeded = False

    def seed(self):
        if not self.seeded:
            storekit.seed(self.root)
            self.seeded = True

    def path(self, name):
        return Path(self.root) / name

    def changeset(self, text, name="changes.trig"):
        self.path(name).write_text(text, encoding="utf-8")
        return str(self.path(name))

    def kb(self, *args):
        self.seed()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue()

    def loaded(self):
        self.seed()
        return S.load(self.root)

    def record(self):
        """The whole record as its dump: what a refusal must leave as it was."""
        self.seed()
        return db.dump_text(db.read(self.root))

    def kb_text(self):
        return storekit.kb_text(self.root)

    def log_text(self):
        return storekit.graph_text(self.root, record.LOG)

    def edit_kb(self, old, new):
        """Change the career: its text before it is stored, the store after."""
        if self.seeded:
            return edit_career(self, self.root, old, new)
        kb = self.path("career/kb.ttl")
        text = kb.read_text(encoding="utf-8")
        self.assertIn(old, text)
        kb.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


class Apply(Workspace):
    def test_a_braindump_becomes_a_valid_logged_record(self):
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual(record.state(s).kind, "clean")
        self.assertEqual(record.state(s).log_revision, 3)
        for line in ("+k:prj_payments j:name \"Payments platform\" ;",
                     "+k:ach_payments_cut_settlement_latency j:project k:prj_payments ; j:rank 1 ;",
                     "+k:ach_payments_moved_card_payments j:project k:prj_payments ; j:rank 2 ;",
                     "+c:payments a j:Domain ; j:label \"payments\" .",
                     "minted   c:payments, k:ach_payments_cut_settlement_latency",
                     "r3 written: career/store/"):
            self.assertIn(line, out)
        log = self.log_text()
        self.assertIn('j:summary "The payments project, from the 24 Sep braindump."', log)

    def test_applying_the_same_changeset_twice_changes_nothing_the_second_time(self):
        path = self.changeset(BRAINDUMP.replace("op:base 2 ; ", ""))
        self.assertEqual(self.kb("apply", path)[0], 0)
        # An agent that re-runs an apply it thought failed must not mint every bullet twice:
        # a new bullet with a live bullet's text, under the same project, is that bullet.
        code, out = self.kb("apply", path)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to change", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 3)

    def test_an_old_application_s_fault_does_not_block_the_career(self):
        posting = self.path("applications/acme-platform-engineer/posting.ttl")
        posting.write_text(posting.read_text(encoding="utf-8").replace(
            "Deep, hands-on K8s experience in production", "Ten years of K8s"), encoding="utf-8")
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 0, out)

    def test_a_label_that_clashes_is_a_warning_not_a_refusal(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:add { c:payments a j:Domain ; j:label "Kafka" . }\n'))
        self.assertEqual(code, 0, out)

    def test_a_dry_run_writes_nothing(self):
        before = self.record()
        backup = self.path(record.BACKUP).read_bytes()
        code, out = self.kb("apply", self.changeset(BRAINDUMP), "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("+k:prj_payments", out)
        self.assertIn("dry run: r3 not written", out)
        self.assertEqual((self.record(), self.path(record.BACKUP).read_bytes()), (before, backup))

    def test_a_changeset_windows_powershell_wrote_is_read(self):
        # PowerShell 5.1's `>` and Out-File write UTF-16 with a byte-order mark.
        path = self.path("changes.trig")
        path.write_bytes(BRAINDUMP.encode("utf-16"))
        code, out = self.kb("apply", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("r3 written", out)

    def test_a_changeset_in_another_encoding_is_refused_not_crashed(self):
        path = self.path("changes.trig")
        path.write_bytes((PFX + 'op:add { k:prj_x j:name "Café" . }\n').encode("cp1252"))
        code, out = self.kb("apply", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("not UTF-8", out)
        self.assertIn("save it as UTF-8", out)

    def test_stdin_is_refused(self):
        code, out = self.kb("apply", "-")
        self.assertEqual(code, 2)
        self.assertIn("stdin is refused", out)

    def test_a_store_written_outside_jsk_is_refused(self):
        s = self.loaded()
        record.write_graphs(self.root, {record.KB: record.stamp(
            s.graph(record.KB), 9, datetime.date.today())})
        before = self.record()
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 1, out)
        self.assertIn("something outside jsk wrote career/store/", out)
        self.assertIn("backup.trig", out)
        self.assertEqual(self.record(), before)

    def test_a_change_that_breaks_the_record_is_refused_whole(self):
        before = self.record()
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:add { k:prj_half j:name "Half a project" . }\n'))
        self.assertEqual(code, 1)
        self.assertIn("j:strength is required", out)
        self.assertEqual(self.record(), before)

    def test_a_refusal_names_every_reason(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:set { k:prj_clinical_events j:provenance j:confirmed ; j:strenght 4 . }\n'))
        self.assertEqual(code, 1)
        self.assertIn("a changeset cannot confirm", out)
        self.assertIn("did you mean j:strength?", out)

    def test_rewording_a_disputed_entry_leaves_it_disputed(self):
        # Rank 0 must not become rank 2 because somebody edited the words.
        self.kb("apply", self.changeset(
            PFX + 'op:set { k:ach_clinical_events_led_migration j:provenance j:disputed . }\n'))
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:set { k:ach_clinical_events_led_migration j:text "Led 4 engineers." . }\n'))
        self.assertEqual(code, 0, out)
        self.assertNotIn("+    j:provenance j:inferred .", out)
        s = self.loaded()
        [pv] = [q.object.value for q in s.graph(record.KB)
                if q.subject.value == O.K + "ach_clinical_events_led_migration"
                and q.predicate.value == O.J + "provenance"]
        self.assertEqual(pv, O.J + "disputed")

    def test_nothing_to_change_writes_nothing(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:set { k:prj_clinical_events j:strength 5 . }\n'))
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))
        self.assertIn("nothing to change", out)

    def test_a_changeset_that_is_not_trig(self):
        code, out = self.kb("apply", self.changeset("x", "changes.ttl"))
        self.assertEqual(code, 2)
        self.assertIn("not a .trig file", out)


ANSWER = "Yes - 42 sites at hand-over, and a quarter each before the platform."


class Confirm(Workspace):
    def test_confirming_answers_the_open_questions_and_logs_the_answer(self):
        code, out = self.kb("confirm", "k:ach_site_onboarding_sites_one_platform",
                            "prj_site_onboarding", "--answer", ANSWER)
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
                code, out = self.kb("confirm", "prj_site_onboarding", "--answer", said)
                self.assertEqual(code, 1)
                self.assertIn("is not an answer", out)

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.kb("confirm", "prj_site_onbording", "--answer", ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_site_onboarding?", out)

    def test_an_entry_that_is_not_a_claim(self):
        code, out = self.kb("confirm", "met_sites", "--answer", ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("a Metric is not a claim", out)

    def test_a_denial_is_not_a_confirmation(self):
        for said in ("No.", "nope", "Wrong", "not true"):
            with self.subTest(said=said):
                code, out = self.kb("confirm", "prj_site_onboarding", "--answer", said)
                self.assertEqual(code, 1)
                self.assertIn("a denial is not a confirmation", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_confirming_what_is_confirmed_changes_nothing(self):
        code, out = self.kb("confirm", "prj_clinical_events", "--answer", ANSWER)
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))

    def test_an_answer_that_only_names_a_document_is_refused(self):
        # "From prior-resume.pdf" confirmed what was extracted, with nothing checking it.
        for said in ("From prior-resume.pdf", "per my CV.docx", "see resume.md",
                     "Source: old resume.txt", "prior-resume.pdf", "Yes, from the resume.pdf"):
            with self.subTest(said=said):
                code, out = self.kb("confirm", "prj_site_onboarding", "--answer", said)
                self.assertEqual(code, 1, out)
                self.assertIn("--source <file> --quote", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_an_answer_naming_a_file_among_its_words_passes(self):
        said = "Yes - it was 42 sites by hand-over; my old resume.pdf undersold it."
        code, out = self.kb("confirm", "k:ach_site_onboarding_sites_one_platform",
                            "--answer", said)
        self.assertEqual(code, 0, out)


QUOTE = ("brought 42 residential care sites onto one platform, cutting onboarding from a "
         "quarter to two weeks")
SOURCE = """# Prior resume

Care Group, 2020-2023
- Led the site programme and brought 42 residential care
  sites onto one platform, cutting onboarding from a quarter to two weeks.
"""


class ConfirmFromSource(Workspace):
    """`--source <file> --quote`: a fact extracted from a document is confirmed by the
    document's own words, checked, not by an --answer naming it."""

    def setUp(self):
        super().setUp()
        self.path("imports").mkdir()
        self.doc = self.path("imports/prior-resume.md")
        self.doc.write_text(SOURCE, encoding="utf-8")

    def confirm(self, *ids, source=None, quote=QUOTE):
        return self.kb("confirm", *ids, "--source", str(source or self.doc), "--quote", quote)

    def test_a_quote_the_document_holds_confirms_and_is_logged(self):
        code, out = self.confirm("k:ach_site_onboarding_sites_one_platform")
        self.assertEqual(code, 0, out)
        log = self.log_text()
        self.assertIn(f'From imports/prior-resume.md: \\"{QUOTE}\\"', log)
        self.assertEqual([f.text() for f in self.loaded().findings], [])

    def test_a_quote_the_document_does_not_hold_is_refused(self):
        code, out = self.confirm("k:ach_site_onboarding_sites_one_platform",
                                 quote="brought 45 residential care sites onto one platform")
        self.assertEqual(code, 1, out)
        self.assertIn("does not say", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_a_number_the_quote_does_not_state_is_refused(self):
        code, out = self.confirm("k:ach_site_onboarding_sites_one_platform",
                                 quote="residential care sites onto one platform")
        self.assertEqual(code, 1, out)
        self.assertIn("'42'", out)
        self.assertIn("--answer", out)

    def test_a_clause_the_quote_does_not_hold_is_refused(self):
        # The document says the first half; the session added the second.
        code, out = self.confirm("k:ach_site_onboarding_sites_one_platform",
                                 quote="brought 42 residential care sites onto one platform")
        self.assertEqual(code, 1, out)
        self.assertIn("'quarter'", out)
        self.assertIn("ask the person", out)

    def test_a_quote_about_something_else_is_refused(self):
        code, out = self.confirm("k:ach_site_onboarding_sites_one_platform",
                                 quote="Led the site programme and brought 42")
        self.assertEqual(code, 1, out)
        self.assertIn("the quote does not", out)

    def test_an_entry_with_no_text_needs_only_the_quote(self):
        code, out = self.confirm("prj_site_onboarding", quote="Led the site programme")
        self.assertEqual(code, 0, out)

    def test_a_short_quote_is_refused(self):
        for quote in ("yes", "42 sites", ""):
            with self.subTest(quote=quote):
                code, out = self.confirm("prj_site_onboarding", quote=quote)
                self.assertEqual(code, 1, out)
                self.assertIn("three words", out)

    def test_source_and_answer_together_are_a_usage_error(self):
        code, out = self.kb("confirm", "prj_site_onboarding", "--answer", ANSWER,
                            "--source", str(self.doc), "--quote", QUOTE)
        self.assertEqual(code, 2, out)
        code, out = self.kb("confirm", "prj_site_onboarding", "--source", str(self.doc))
        self.assertEqual(code, 2, out)

    def test_a_file_outside_the_workspace_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp, "cv.md")
            outside.write_text(SOURCE, encoding="utf-8")
            code, out = self.confirm("prj_site_onboarding", source=outside)
        self.assertEqual(code, 1, out)
        self.assertIn("inside this workspace", out)

    @unittest.skipUnless(os.name == "nt", "drives are a Windows thing")
    def test_a_file_on_another_drive_is_refused(self):
        from unittest import mock

        elsewhere = other_drive(self.root) + "\\cv.md"
        real = os.path.isfile
        with mock.patch("os.path.isfile", lambda p: p == elsewhere or real(p)):
            code, out = self.confirm("prj_site_onboarding", source=elsewhere)
        self.assertEqual(code, 1, out)
        self.assertIn("inside this workspace", out)

    def test_a_docx_is_refused_with_the_fix(self):
        docx = self.path("imports/cv.docx")
        docx.write_bytes(b"PK\x03\x04")
        code, out = self.confirm("prj_site_onboarding", source=docx)
        self.assertEqual(code, 1, out)
        self.assertIn("convert it to .md or .txt first", out)

    def test_a_document_in_another_encoding_is_refused_not_crashed(self):
        self.doc.write_bytes(SOURCE.replace("Care Group", "Café Group").encode("cp1252"))
        code, out = self.confirm("prj_site_onboarding", quote="Led the site programme")
        self.assertEqual(code, 1, out)
        self.assertIn("prior-resume.md is not UTF-8 text", out)

    def test_a_pdf_without_pymupdf_is_refused_with_the_fix(self):
        import sys
        from unittest import mock

        pdf = self.path("imports/cv.pdf")
        pdf.write_bytes(b"%PDF-1.4\n")
        with mock.patch.dict(sys.modules, {"pymupdf": None}):
            code, out = self.confirm("prj_site_onboarding", source=pdf)
        self.assertEqual(code, 1, out)
        self.assertIn("install pymupdf, or convert it to .md", out)


class ConfirmSummary(Workspace):
    """`--summary <resume.json>`: a summary is confirmed by the person's answer, kept in
    resume.json with the text's hash - not by flipping its status."""

    TEXT = "Architect who builds clinical event platforms other teams build on."

    def setUp(self):
        super().setUp()
        app = self.path("applications/globex-architect")
        app.mkdir()
        self.file = app / "resume.json"
        self.write({"resume": 2, "bullets": ["ach_clinical_events_event_latency"],
                    "summary": {"text": self.TEXT, "status": "inferred"}, "pages": 2})

    def write(self, doc, path=None):
        (path or self.file).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    def confirm(self, answer="Yes, that is exactly what I do.", path=None):
        return self.kb("confirm", "--summary", str(path or self.file), "--answer", answer)

    def test_the_answer_and_the_text_s_hash_are_written(self):
        from jsk.resume import short

        code, out = self.confirm()
        self.assertEqual(code, 0, out)
        text = self.file.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("}\n") and '\n  "summary": {\n    "text"' in text, text)
        doc = json.loads(text)
        self.assertEqual(list(doc), ["resume", "bullets", "summary", "pages"])
        self.assertEqual(doc["summary"], {"text": self.TEXT, "status": "confirmed",
                                          "answer": "Yes, that is exactly what I do.",
                                          "text_sha256": short.digest(self.TEXT)})
        self.assertEqual(short.shape(doc), [])
        self.assertEqual(record.state(self.loaded()).log_revision, 2)   # not in the career
        code, out = self.confirm()
        self.assertEqual(code, 0, out)
        self.assertIn("confirmed already", out)

    def test_an_answer_that_says_nothing_is_refused(self):
        for said in ("yes", "ok", "nope"):
            with self.subTest(said=said):
                code, out = self.confirm(said)
                self.assertEqual(code, 1, out)
        self.assertEqual(json.loads(self.file.read_text(encoding="utf-8"))["summary"]["status"],
                         "inferred")

    def test_no_summary_is_refused(self):
        self.write({"resume": 2, "bullets": ["ach_clinical_events_event_latency"]})
        code, out = self.confirm()
        self.assertEqual(code, 1, out)
        self.assertIn("no summary to confirm", out)

    def test_a_frozen_application_is_refused(self):
        frozen = self.path("applications/acme-platform-engineer/resume.json")
        self.write({"resume": 2, "bullets": ["ach_clinical_events_event_latency"],
                    "summary": {"text": self.TEXT, "status": "inferred"}}, frozen)
        code, out = self.confirm(path=frozen)
        self.assertEqual(code, 1, out)
        self.assertIn("frozen", out)
        self.assertIn("new dated directory", out)

    @unittest.skipUnless(os.name == "nt", "drives are a Windows thing")
    def test_a_resume_on_another_drive_is_refused(self):
        code, out = self.confirm(path=other_drive(self.root) + "\\resume.json")
        self.assertEqual(code, 1, out)
        self.assertIn("not inside this workspace", out)

    def test_an_edit_after_confirming_drops_it(self):
        from jsk.resume import short

        self.assertEqual(self.confirm()[0], 0)
        doc = json.loads(self.file.read_text(encoding="utf-8"))
        doc["summary"]["text"] += " And more."
        self.assertTrue(any("changed since it was confirmed" in f for f in short.shape(doc)))
        self.write(doc)
        code, out = self.confirm("Yes, the longer one is right too.")
        self.assertEqual(code, 0, out)
        self.assertEqual(short.shape(json.loads(self.file.read_text(encoding="utf-8"))), [])

    def test_ids_with_summary_are_a_usage_error(self):
        code, out = self.kb("confirm", "prj_site_onboarding", "--summary", str(self.file),
                            "--answer", ANSWER)
        self.assertEqual(code, 2, out)


class Show(Workspace):
    def test_a_project_is_shown_with_its_bullets_and_the_base_to_draft_against(self):
        code, out = self.kb("show", "prj_clinical_events")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("# r2 - op:base 2\n"))
        first = out.index("k:ach_clinical_events_event_latency j:project")
        second = out.index("k:ach_clinical_events_led_migration j:project")
        self.assertLess(out.index("k:prj_clinical_events j:name"), first)
        self.assertLess(first, second)

    def test_a_metric_is_shown_with_its_versions(self):
        code, out = self.kb("show", "k:met_event_latency")
        self.assertLess(out.index("k:met_event_latency.v1"), out.index("k:met_event_latency.v2"))

    def test_a_shipped_concept_is_shown_from_the_vocabulary(self):
        code, out = self.kb("show", "c:kafka")
        self.assertEqual(code, 0, out)
        self.assertIn("\n# vocabulary\n", out)
        self.assertIn("\n# kb\n", out)                # the career extends it

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.kb("show", "prj_clinical_event")
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_clinical_events?", out)


class View(Workspace):
    def test_the_whole_career_in_section_order(self):
        code, out = self.kb("view")
        self.assertEqual(code, 0, out)
        at = [out.index(f"## {s}\n") for s in O.SECTIONS["kb"]]
        self.assertEqual(at, sorted(at))
        self.assertIn("- **Care-site onboarding** `k:prj_site_onboarding` _(inferred)_", out)
        self.assertIn("_(retired 2026-01-10: Too old and too small to earn a line.)_", out)
        self.assertIn("  - **Led a team of 6 engineers", out)
        self.assertIn("    problem: The legacy scheduler", out)

    def test_one_section(self):
        code, out = self.kb("view", "--section", "skills")
        self.assertIn("## Skills", out)
        self.assertNotIn("## Projects", out)

    def test_it_writes_nothing(self):
        before = self.record()
        self.assertEqual(self.kb("view")[0], 0)
        self.assertEqual(self.record(), before)


class Query(Workspace):
    def test_open_questions(self):
        code, out = self.kb("query", "open")
        self.assertIn("| k:q_sites_bullet | k:ach_site_onboarding_sites_one_platform | 2026-09-01 |", out)
        self.assertNotIn("q_team_size", out)          # answered

    def test_a_question_about_several_entries_is_one_row(self):
        self.edit_kb("k:q_sites_confirm j:about k:prj_site_onboarding ;",
                     "k:q_sites_confirm j:about k:prj_clinical_events, k:prj_site_onboarding ;")
        rows = [r for r in json.loads(self.kb("query", "open", "--json")[1])
                if r["question"] == "k:q_sites_confirm"]
        self.assertEqual([r["about"] for r in rows],
                         ["k:prj_clinical_events, k:prj_site_onboarding"])

    def test_unconfirmed_entries(self):
        code, out = self.kb("query", "unconfirmed", "--json")
        rows = json.loads(out)
        self.assertEqual([r["entry"] for r in rows],
                         ["k:ach_site_onboarding_sites_one_platform", "k:prj_site_onboarding"])

    def test_what_holds_a_concept(self):
        code, out = self.kb("query", "holds", "c:azure")
        self.assertIn("| k:prj_clinical_events | c:azure-ai-foundry | 1 | False | tag |", out)

    def test_a_revised_metric_makes_the_application_that_sent_it_stale(self):
        code, _ = self.kb("query", "stale")
        self.kb("apply", self.changeset(PFX + "op:set { k:met_team.v1 j:value 7 . }\n"))
        code, out = self.kb("query", "stale")
        today = datetime.date.today().isoformat()
        self.assertIn(f"| k:app_acme_platform_engineer | k:met_team.v1 | {today} | k:met_team.v2 |",
                      out)

    def evidence(self, *terms):
        code, out = self.kb("query", "evidence", *terms, "--json")
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def test_evidence_reports_the_projects_holding_a_term_s_concept(self):
        rows = self.evidence("event-driven")
        self.assertIn({"term": "event-driven", "found": "c:event-driven-architecture",
                       "entry": "k:prj_clinical_events", "via": "holds c:kafka, 1 hop",
                       "evidence": "tag", "text": ""}, rows)

    def test_evidence_finds_the_text_naming_a_term_but_not_the_vocabulary_s_labels(self):
        rows = [r for r in self.evidence("event-driven") if r["found"] == "text"]
        self.assertEqual([(r["entry"], r["via"], r["evidence"]) for r in rows],
                         [("k:person", "j:positioning", "confirmed")])
        self.assertTrue(rows[0]["text"].startswith("Architect who turns"))

    def test_evidence_names_a_bullet_s_project(self):
        rows = self.evidence("platform")
        self.assertIn("k:ach_site_onboarding_sites_one_platform (k:prj_site_onboarding)",
                      [r["entry"] for r in rows])

    def test_evidence_says_so_when_the_record_holds_nothing(self):
        self.assertEqual(self.evidence("Haskell"),
                         [{"term": "Haskell", "found": "nothing", "entry": "",
                           "via": "no concept, and no text in the record names it",
                           "evidence": "", "text": ""}])

    def test_evidence_matches_an_acronym_in_capitals_only(self):
        def text(term):
            return [r["entry"] for r in self.evidence(term) if r["found"] == "text"]
        self.assertEqual(text("EVENT-DRIVEN"), [])
        self.assertEqual(text("Event-Driven"), ["k:person"])

    def test_evidence_answers_every_term_in_one_call_and_needs_one(self):
        rows = self.evidence("Kafka", "Haskell")
        self.assertEqual({r["term"] for r in rows}, {"Kafka", "Haskell"})
        self.assertEqual(self.kb("query", "evidence")[0], 2)

    def test_evidence_shows_fewer_text_hits_when_the_term_names_a_concept(self):
        from jsk.graph import named
        self.assertLess(named.TEXT_HITS_RESOLVED, named.TEXT_HITS)
        kb = self.path("career/kb.ttl")                 # before it is stored
        kb.write_text(kb.read_text(encoding="utf-8") + "".join(
            f'\nk:ach_intranet_refresh_kafka_{i} j:project k:prj_intranet_refresh ; j:rank {10 + i} ;\n'
            f'    j:text "Kafka note {i}." ; j:provenance j:inferred .\n' for i in range(8)),
            encoding="utf-8")
        rows = [r for r in self.evidence("Kafka") if r["found"] == "text"]
        self.assertEqual(len([r for r in rows if r["entry"]]), named.TEXT_HITS_RESOLVED)
        self.assertIn("more - a narrower term finds them", rows[-1]["via"])

    def test_the_vocabulary_as_one_table(self):
        rows = {r["concept"]: r for r in json.loads(self.kb("query", "concepts", "--json")[1])}
        self.assertEqual(rows["c:event-driven-architecture"]["labels"], "EDA, event-driven")
        self.assertEqual(rows["c:kafka"]["counts as"], "c:event-driven-architecture")
        self.assertEqual(rows["c:kafka"]["held"], 1)
        self.assertEqual(rows["c:terraform"]["held"], "")     # shipped, held by no project

    def test_concepts_near_a_term_is_what_it_names_then_the_closest(self):
        code, out = self.kb("query", "concepts", "--near", "Apache Kafka", "--json")
        self.assertEqual(code, 0, out)
        # Keyed by term, since --near takes several (2026-09-29-tailor-time Ruling 2).
        rows = [r["concept"] for r in json.loads(out)["Apache Kafka"]]
        self.assertEqual(rows[0], "c:kafka")
        self.assertLessEqual(len(rows), 6)

    def test_concepts_near_several_terms_is_a_table_each(self):
        """The analyst ran --near 21 times in a shell loop; one call takes every term."""
        code, out = self.kb("query", "concepts", "--near", "Apache Kafka", "Terraform")
        self.assertEqual(code, 0, out)
        self.assertEqual([x for x in out.splitlines() if x.startswith("== ")],
                         ["== Apache Kafka", "== Terraform"])
        kafka, terraform = out.split("== Terraform")
        self.assertIn("c:kafka", kafka)
        self.assertIn("c:terraform", terraform)

    def test_concepts_near_needs_a_term(self):
        code, out = self.kb("query", "concepts", "--near")
        self.assertEqual(code, 2)
        self.assertIn("one or more terms", out)

    def test_near_is_only_for_concepts(self):
        code, out = self.kb("query", "person", "--near", "Kafka")
        self.assertEqual(code, 2)
        self.assertIn("--near is for", out)

    def test_bare_lists_the_unlabelled_capabilities_most_held_first(self):
        self.edit_kb('c:data-sovereignty a j:Capability ; j:label "data residency" .',
                     "c:api-design a j:Capability .\nc:data-sovereignty a j:Capability .")
        code, out = self.kb("query", "bare", "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out), [
            {"concept": "c:data-sovereignty", "held": 1, "shown by": 0},
            {"concept": "c:api-design", "held": 0, "shown by": 0}])    # labelled ones absent

    def test_show_bullets_prints_a_project_s_name_and_bullets_only(self):
        full = self.kb("show", "prj_site_onboarding")[1]
        code, out = self.kb("show", "prj_site_onboarding", "--bullets")
        self.assertEqual(code, 0, out)
        self.assertIn("# k:prj_site_onboarding - Care-site onboarding", out)
        self.assertIn("k:ach_site_onboarding_sites_one_platform j:project", out)
        self.assertNotIn("j:uses", out)
        self.assertLess(len(out), len(full))

    def test_the_person_behind_eligibility(self):
        code, out = self.kb("query", "person")
        self.assertEqual(code, 0, out)
        self.assertIn("| location | Sydney, AU | k:person | confirmed |", out)
        self.assertIn("| work mode | hybrid | k:person | confirmed |", out)
        self.assertIn("| work authorization | AU: citizen, held | k:auth_au | confirmed |", out)
        self.assertIn("| ongoing role | Principal Solution Architect at Meridian Health, "
                      "since 2023-07 (employment) | k:pos_meridian_principal | confirmed |", out)

    def test_an_unknown_query(self):
        code, out = self.kb("query", "everything")
        self.assertEqual(code, 2)
        self.assertIn("open, unconfirmed, holds, stale", out)


# The clinical event pipeline told again months later, in other words: the same role, the
# same technologies, not one sentence in common.
RETOLD = '''k:prj_care_streaming j:name "Real-time care event streaming" ;
    j:position k:pos_meridian_principal ;
    j:strength 4 ; j:recency 2025 ;
    j:domain c:healthcare ;
    j:uses c:azure-ai-foundry, c:kafka ;
    j:problem "Care-plan changes took minutes to reach each site because the old scheduler batched them." ;
    j:outcome "Schedule changes now reach 15 applications in under a second." ;
    j:provenance j:inferred .

k:ach_care_streaming_one j:project k:prj_care_streaming ; j:rank 1 ;
    j:text "Streamed care-plan events through Kafka so 15 integrated applications saw schedule changes in under a second." ;
    j:provenance j:inferred .

'''


class Similar(Workspace):
    def query(self, *args):
        code, out = self.kb("query", *args, "--json")
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def retold(self):
        self.edit_kb("k:prj_site_onboarding j:name", RETOLD + "k:prj_site_onboarding j:name")

    def test_similar_finds_a_project_by_the_words_that_describe_it(self):
        rows = self.query("similar", "moving", "every", "residential", "site", "onto", "templates")
        self.assertEqual(set(rows[0]), {"project", "name", "score", "words", "concepts"})
        self.assertEqual(rows[0]["project"], "k:prj_site_onboarding")
        self.assertEqual(rows[0]["words"], "residential, site, templates")   # templated

    def test_similar_finds_a_project_by_a_concept_its_text_never_names(self):
        """Kafka counts as event-driven architecture; the pipeline's prose says neither."""
        [row] = self.query("similar", "EDA")
        self.assertEqual((row["project"], row["words"], row["concepts"]),
                         ("k:prj_clinical_events", "", "c:event-driven-architecture"))

    def test_similar_ranks_the_retelling_first(self):
        self.retold()
        rows = self.query("similar", "streaming care plan changes to every site with Kafka")
        self.assertEqual([r["project"] for r in rows][:2],
                         ["k:prj_care_streaming", "k:prj_clinical_events"])
        self.assertIn("c:kafka", rows[1]["concepts"])

    def test_nothing_similar_is_the_answer(self):
        code, out = self.kb("query", "similar", "React Native mobile app")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing similar", out)
        self.assertNotIn("k:prj_", out)
        self.assertEqual(self.kb("query", "similar")[0], 2)

    def test_a_retired_project_is_never_a_candidate(self):
        rows = self.query("similar", "intranet refresh")
        self.assertEqual(rows[0]["name"], "nothing similar")

    def test_duplicates_finds_the_retelling(self):
        self.retold()
        [row] = self.query("duplicates")
        self.assertEqual(set(row), {"a", "b", "score", "names", "why"})
        self.assertEqual((row["a"], row["b"]), ("k:prj_care_streaming", "k:prj_clinical_events"))
        self.assertIn("concepts c:azure-ai-foundry, c:healthcare, c:kafka", row["why"])
        self.assertIn("same role, 2025 and 2026", row["why"])

    def test_duplicates_reports_nothing_in_the_clean_careers(self):
        """The thresholds' calibration: none of the fixture careers holds a project twice."""
        from appkit import stored_copy

        from jsk.graph import named

        tests = Path(__file__).parent
        for root in (FIXTURES, tests / "match_fixtures", tests / "claims_fixtures",
                     tests.parent / "src" / "jsk" / "data" / "example"):
            with self.subTest(root=Path(root).name):
                _, rows = named.duplicates(S.load(stored_copy(root)))
                self.assertEqual([r["names"] for r in rows],
                                 ["nothing looks like one project twice"])


class Check(Workspace):
    def test_a_clean_workspace(self):
        code, out = self.kb("check")
        self.assertEqual(code, 0)
        self.assertIn("record   clean at r2", out)
        # One WARN, and a true one: "40,000 daily ingestion jobs" is in confirmed words but
        # in no metric, so the record gate refuses it in any record that selects the bullet.
        self.assertIn("0 FAIL, 1 WARN", out)
        self.assertIn("'40,000' appears in the text but in no metric", out)

    def test_a_bullet_every_record_would_fail_on_is_warned_of_once(self):
        """A number no metric holds fails the record gate in whatever record selects
        the bullet - found, on the Everforth run, by the author one gate at a time."""
        self.edit_kb("a team of 6 engineers", "a team of 6 engineers across 3 sites")
        code, out = self.kb("check")
        self.assertEqual(code, 0, out)                     # a WARN, not a FAIL
        self.assertIn("a record selecting it fails a gate:", out)
        self.assertIn("'3' appears in the text but in no metric", out)

    def test_export_names_the_bullets_its_draft_already_fails(self):
        self.edit_kb("a team of 6 engineers", "a team of 6 engineers across 3 sites")
        out_file = self.path("applications/draft/resume.json")
        code, out = self.kb("export", "--out", str(out_file))
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  ", out)
        self.assertIn("a question for the person", out)
        self.assertIn("'3'", out)
        self.assertTrue(out_file.exists())

    def test_a_career_written_outside_jsk_fails_its_hash(self):
        """The store holds what jsk wrote, unless something else wrote it: a provenance
        raised there would render as confirmed, and only the log's hash notices."""
        self.seed()
        s = S.load(self.root)
        raised = [q for q in s.graph(record.KB)
                  if q.predicate.value == O.J + "provenance" and q.object.value == O.J + "inferred"]
        self.assertTrue(raised)
        import pyoxigraph as ox
        kb = [ox.Quad(q.subject, q.predicate, ox.NamedNode(O.J + "confirmed"))
              if q == raised[0] else q for q in s.graph(record.KB)]
        record.write_graphs(self.root, {record.KB: kb})         # not through a jsk verb
        code, out = self.kb("check")
        self.assertEqual(code, 1, out)
        self.assertIn("the career is not what its log last recorded - written outside jsk", out)
        self.assertIn(".jsk/backup.trig", out)

    def test_a_fail_exits_1_and_names_the_graph_and_the_entry(self):
        self.edit_kb("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb("check")
        self.assertEqual(code, 1)
        self.assertIn("record   clean at r2", out)
        self.assertIn("did you mean k:met_team?", out)
        self.assertRegex(out, r"FAIL  kb k:ach_\w+ - j:cites k:met_teem")    # no line number

    APP = "applications/acme-platform-engineer"

    def uncover(self):
        advert = self.path(f"{self.APP}/posting.md")
        advert.write_text(advert.read_text(encoding="utf-8").replace(
            "## Benefits", "- Must have Terraform in production.\n\n## Benefits"), encoding="utf-8")

    def test_only_one_application_s_findings(self):
        self.uncover()
        code, out = self.kb("check", "--only", self.APP)
        self.assertEqual(code, 0, out)
        self.assertIn("0 FAIL, 1 WARN", out)
        self.assertIn("Must have Terraform in production", out)
        self.assertNotIn("appears in the text but in no metric", out)     # the career's
        code, out = self.kb("check", "--only", str(self.path(self.APP)))    # a path works too
        self.assertIn("0 FAIL, 1 WARN", out)

    def test_only_still_shows_a_fail_anywhere(self):
        self.edit_kb("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb("check", "--only", self.APP)
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:met_team?", out)

    def test_only_somewhere_clean(self):
        self.uncover()
        code, out = self.kb("check", "--only", "log")
        self.assertEqual(code, 0, out)
        self.assertIn("0 FAIL, 0 WARN", out)


class Dispatch(Workspace):
    def test_help_lists_the_verbs_and_exits_0(self):
        code, out = self.kb("--help")
        self.assertEqual(code, 0)
        self.assertIn("apply <changeset.trig>", out)
        verbs = re.findall(r"^  (\w+)", out, re.M)
        self.assertEqual(verbs, ["apply", "confirm", "show", "view", "query", "pack", "merge",
                                 "export", "check", "path", "load", "dump", "log"])
        from jsk.graph import kbcli
        self.assertEqual(sorted(kbcli.VERBS), sorted(verbs))

    def test_a_verb_s_help(self):
        code, out = self.kb("apply", "--help")
        self.assertEqual(code, 0)
        self.assertIn("--dry-run prints the diff", out)

    def test_an_unknown_verb(self):
        code, out = self.kb("aply")
        self.assertEqual(code, 2)
        self.assertIn("unknown verb: aply", out)

    def test_the_workspace_is_found_from_inside_it(self):
        self.seed()
        here = os.getcwd()
        os.chdir(self.path("applications"))
        self.addCleanup(os.chdir, here)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "apply", self.changeset(BRAINDUMP), "--dry-run"])
        self.assertEqual(code, 0, out.getvalue())


class KbPath(unittest.TestCase):
    """`jsk kb path` - where the record is, printed rather than worked out."""

    def setUp(self):
        # A workspace that is itself named `career`: the store sits at career/career/store/.
        self.outer = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.outer)
        self.root = os.path.join(self.outer, "career")
        shutil.copytree(FIXTURES, self.root)
        storekit.seed(self.root)

    def run_path(self, *args, cwd=None):
        here = os.getcwd()
        if cwd:
            os.chdir(cwd)
            self.addCleanup(os.chdir, here)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "path", *args])
        return code, out.getvalue()

    def test_it_prints_the_absolute_paths(self):
        code, out = self.run_path("--root", self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out, f"workspace     {self.root}\n"
                              f"store         {os.path.join(self.root, 'career', 'store')}\n"
                              f"applications  {os.path.join(self.root, 'applications')}\n")

    def test_it_finds_the_workspace_from_an_application_directory(self):
        code, out = self.run_path(cwd=os.path.join(self.root, "applications"))
        self.assertEqual(code, 0, out)
        self.assertIn(os.path.join(self.root, "career", "store"), out)

    def test_the_career_folder_itself_is_named_as_the_mistake(self):
        inner = os.path.join(self.root, "career")
        code, out = self.run_path("--root", inner)
        self.assertEqual(code, 1)
        self.assertIn(f"no career/store/ under {inner}", out)
        self.assertIn(f"the workspace is {self.root}", out)

    def test_a_workspace_still_laid_out_as_files_is_told_to_load(self):
        files = os.path.join(self.outer, "files")
        shutil.copytree(FIXTURES, files)
        code, out = self.run_path("--root", files)
        self.assertEqual(code, 1)
        self.assertIn("`jsk kb load .`", out)

    def test_it_takes_no_arguments(self):
        code, out = self.run_path("kb.ttl", "--root", self.root)
        self.assertEqual(code, 2)
        self.assertIn("takes no arguments", out)


class UnknownFlags(Workspace):
    """A flag a verb does not take is refused by name. Every verb used to lift its own
    flags out by name and leave the rest as arguments, so a mistyped one was caught only
    when the count came out wrong - and then as "takes one changeset", not as the typo."""

    CALLS = [("apply", "changes.trig"), ("path",), ("load", "x.trig"), ("dump",), ("log",),
             ("confirm", "k:prj_identity", "--answer", "It shipped in March."),
             ("pack", "capabilities"), ("merge", "c:kafka", "--into", "c:python"),
             ("show", "k:prj_identity"), ("view",), ("export", "--select", "prj_identity"),
             ("query", "open"), ("check",)]

    def test_a_quote_may_start_with_a_dash(self):
        # A value is whatever follows its flag, as it was when each verb lifted its own.
        code, out = self.kb("confirm", "k:prj_identity", "--source", "notes.md",
                            "--quote", "-40% in a quarter")
        self.assertEqual(code, 1, out)          # it got as far as looking for the file
        self.assertIn("REFUSED  notes.md", out)

    def test_each_verb_names_the_flag(self):
        for call in self.CALLS:
            with self.subTest(verb=call[0]):
                code, out = self.kb(*call, "--no-such-flag")
                self.assertEqual(code, 2, out)
                self.assertIn("unknown flag: --no-such-flag", out)


class Load(unittest.TestCase):
    """`jsk kb load`: an empty store filled once - from a workspace still laid out as files,
    or from a dump."""

    APP = "applications/acme-platform-engineer"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.files = os.path.join(self.tmp, "files")        # a workspace not yet loaded
        shutil.copytree(FIXTURES, self.files)
        self.empty = os.path.join(self.tmp, "empty")
        os.makedirs(self.empty)

    def documents(self):
        """The application's documents copied into the empty workspace, as a person moving
        a record would: they are files beside the record, not in it."""
        os.makedirs(os.path.join(self.empty, self.APP))
        shutil.copy(os.path.join(self.files, self.APP, "posting.md"),
                    os.path.join(self.empty, self.APP, "posting.md"))

    def kb(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", *args, "--root", root])
        return code, out.getvalue()

    def edit(self, old, new, file="career/kb.ttl"):
        path = Path(self.files, file)
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def test_a_workspace_of_files_loads_in_place_and_its_files_are_no_longer_read(self):
        kb = Path(self.files, "career/kb.ttl")
        before = kb.read_bytes()
        here = os.getcwd()
        os.chdir(self.files)                                        # `jsk kb load .`, as the fix says
        self.addCleanup(os.chdir, here)
        code, out = self.kb(self.files, "load", ".")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"loaded   \d+ triples in 4 graphs into career/store/, at r3")
        self.assertIn("career/kb.ttl and the other .ttl files are no longer read", out)
        self.assertNotIn("not in this workspace", out)
        self.assertEqual(kb.read_bytes(), before)                  # left where it is
        s = S.load(self.files)
        self.assertTrue(s.stored)
        self.assertEqual(record.state(s).kind, "clean")
        self.assertEqual(sorted(s.parsed), ["applications/acme-platform-engineer/application",
                                            "applications/acme-platform-engineer/posting",
                                            "kb", "log", "vocabulary"])
        kb.write_text(before.decode("utf-8").replace('"Meridian Health"', '"Elsewhere"'),
                      encoding="utf-8")
        self.assertNotIn("Elsewhere", storekit.kb_text(self.files))

    def test_a_number_the_store_would_rewrite_is_kept_by_value_and_said(self):
        self.edit("    j:value 42 ;", "    j:value 42.0 ;")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"number   kb k:met_\w+\.v1 j:value 42\.0 kept as 42\n")

    def test_a_workspace_with_a_fail_is_refused_and_nothing_is_stored(self):
        self.edit("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 1, out)
        self.assertIn("did you mean k:met_team?", out)
        self.assertIn("nothing was written", out)
        self.assertFalse(db.exists(self.empty))

    def test_a_store_that_holds_a_record_is_refused(self):
        self.assertEqual(self.kb(self.empty, "load", self.files)[0], 0)
        before = db.dump_text(db.read(self.empty))
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 1, out)
        self.assertIn("already holds a record", out)
        self.assertEqual(db.dump_text(db.read(self.empty)), before)

    def test_a_dump_loads_back_to_the_same_record(self):
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        self.documents()
        dump = os.path.join(self.tmp, "career.trig")
        code, out = self.kb(self.files, "dump", "--out", dump)
        self.assertEqual(code, 0, out)
        code, out = self.kb(self.empty, "load", dump)
        self.assertEqual(code, 0, out)
        self.assertIn("at r3", out)                 # the fixture's r2, and the import's entry
        self.assertNotIn("note", out)
        self.assertEqual(db.dump_text(db.read(self.empty)), db.dump_text(db.read(self.files)))
        self.assertEqual(self.kb(self.empty, "view"), self.kb(self.files, "view"))
        self.assertEqual(self.kb(self.empty, "check")[0], 0)

    def test_the_import_is_logged_as_one_entry_of_its_own(self):
        """By j:load, holding the career's hash: so every store's newest entry hashes its
        career, and a dump of an imported workspace loads back."""
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn("at r3", out)
        s = S.load(self.empty)
        self.assertEqual(record.state(s).kind, "clean")
        self.assertIsNone(record.unrecorded(s.graph(record.KB), s.graph(record.LOG)))
        code, out = self.kb(self.empty, "log", "--last", "1")
        self.assertRegex(out, r"^r3  \d{4}-\d\d-\d\d  load     Imported from the files by jsk kb "
                              r"load: 4 graphs, 0 numbers kept by value")

    def dumped(self):
        """An imported workspace, dumped: (its dump's path, the dump's text)."""
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        dump = os.path.join(self.tmp, "career.trig")
        self.assertEqual(self.kb(self.files, "dump", "--out", dump)[0], 0)
        return dump, Path(dump).read_text(encoding="utf-8")

    def test_an_imported_workspace_dumps_and_loads_back(self):
        dump, _ = self.dumped()
        self.documents()
        code, out = self.kb(self.empty, "load", dump)
        self.assertEqual(code, 0, out)
        code, out = self.kb(self.empty, "check")
        self.assertEqual(code, 0, out)

    def refused_dump(self, old, new):
        dump, text = self.dumped()
        self.assertIn(old, text)
        Path(dump).write_text(text.replace(old, new, 1), encoding="utf-8")
        code, out = self.kb(self.empty, "load", dump)
        self.assertEqual(code, 1, out)
        self.assertIn("nothing was written", out)
        self.assertFalse(db.exists(self.empty))
        return out

    def test_a_dump_whose_provenance_was_raised_is_refused(self):
        out = self.refused_dump("<tag:jsk,2026:ns#provenance> <tag:jsk,2026:ns#inferred>",
                                "<tag:jsk,2026:ns#provenance> <tag:jsk,2026:ns#confirmed>")
        self.assertIn("not what its log last recorded", out)
        self.assertIn("jsk kb apply", out)

    def test_a_dump_whose_number_was_changed_is_refused(self):
        out = self.refused_dump('<tag:jsk,2026:ns#value> 42 .', '<tag:jsk,2026:ns#value> 43 .')
        self.assertIn("not what its log last recorded", out)

    def test_a_dump_holding_a_number_the_store_would_rewrite_names_it(self):
        out = self.refused_dump('<tag:jsk,2026:ns#value> 42 .',
                                '<tag:jsk,2026:ns#value> "42.0"^^<http://www.w3.org/2001/XMLSchema#decimal> .')
        self.assertIn("j:value 42.0 is kept as 42", out)

    def test_a_hand_edited_kb_ttl_is_imported_with_its_warning_and_what_it_raised(self):
        self.edit("j:provenance j:inferred", "j:provenance j:confirmed")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN", out)
        self.assertIn("changed outside `jsk kb`", out)
        # No copy of the logged revision to compare with: said, not guessed.
        self.assertIn("nothing to compare", out)

    def test_what_a_hand_edit_raised_is_listed_against_the_shadow_copy(self):
        shadow = Path(self.files, ".jsk", "kb.last.ttl")
        shadow.parent.mkdir(exist_ok=True)
        shadow.write_bytes(Path(self.files, "career/kb.ttl").read_bytes())
        self.edit("j:cites k:met_sites ;\n    j:provenance j:inferred .",
                  "j:cites k:met_sites ;\n    j:provenance j:confirmed .")
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn("raised   k:ach_site_onboarding_sites_one_platform: inferred -> confirmed",
                      out)
        self.assertNotIn("k:prj_site_onboarding:", out)

    def test_elsewhere_an_application_s_documents_are_named_to_copy(self):
        code, out = self.kb(self.empty, "load", self.files)
        self.assertEqual(code, 0, out)
        self.assertIn(f"note     {self.APP}: its documents (posting.md", out)
        self.assertIn("failures in applications - `jsk kb check` lists them", out)
        self.assertEqual(self.kb(self.empty, "check")[0], 1)          # until it is copied

    def test_the_backup_every_write_leaves_is_a_dump(self):
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        code, out = self.kb(self.empty, "load", os.path.join(self.files, record.BACKUP))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.kb(self.empty, "view"), self.kb(self.files, "view"))

    def test_a_dump_to_stdout_is_what_the_store_holds(self):
        self.assertEqual(self.kb(self.files, "load", self.files)[0], 0)
        code, out = self.kb(self.files, "dump")
        self.assertEqual(code, 0)
        self.assertEqual(out, db.dump_text(db.read(self.files)))

    def test_what_is_not_a_record_is_refused(self):
        bad = os.path.join(self.tmp, "bad.trig")
        Path(bad).write_text("<tag:a> <tag:b> <tag:c> .\n", encoding="utf-8")
        code, out = self.kb(self.empty, "load", bad)
        self.assertEqual(code, 1, out)
        self.assertIn("outside any record graph", out)
        Path(bad).write_text("this is not trig", encoding="utf-8")
        code, out = self.kb(self.empty, "load", bad)
        self.assertEqual(code, 1, out)
        self.assertFalse(db.exists(self.empty))
        self.assertEqual(self.kb(self.empty, "load", self.empty)[0], 2)     # no kb.ttl in it
        self.assertEqual(self.kb(self.empty, "load")[0], 2)

    def test_a_dump_with_no_store_is_refused(self):
        code, out = self.kb(self.empty, "dump")
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb load", out)


class Log(Workspace):
    def test_the_history_newest_first(self):
        self.assertEqual(self.kb("apply", self.changeset(BRAINDUMP))[0], 0)
        code, out = self.kb("log")
        self.assertEqual(code, 0, out)
        revs = re.findall(r"^r(\d+) ", out, re.M)
        self.assertEqual(revs, ["3", "2", "1"])
        today = datetime.date.today().isoformat()
        self.assertIn(f"r3  {today}  apply    The payments project, from the 24 Sep braindump.",
                      out)
        self.assertRegex(out, r"    minted   c:payments, k:ach_payments_cut_settlement_latency")

    def test_last_n(self):
        self.assertEqual(self.kb("apply", self.changeset(BRAINDUMP))[0], 0)
        code, out = self.kb("log", "--last", "1")
        self.assertEqual(code, 0, out)
        self.assertEqual(re.findall(r"^r(\d+) ", out, re.M), ["3"])
        for bad in ("0", "x", "-1"):
            with self.subTest(last=bad):
                self.assertEqual(self.kb("log", "--last", bad)[0], 2)


if __name__ == "__main__":
    unittest.main()
