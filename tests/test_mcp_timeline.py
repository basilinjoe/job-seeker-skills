"""`jsk mcp`'s app_freeze, app_event and letter_check: the amendment to Ruling 21 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md (2026-10-03), which made
freezing, recording an event and checking a letter tools, so the main session needs no
shell for a jsk job.

The rules pinned: app_freeze on a shipped graph-native application runs the gates, renames
the directory to the day it was sent, moves the five graphs under the new name, and reports
the recordSha256 the store holds, which is the SHA-256 of the selection's canonical text
(Ruling 7); a second freeze is refused as a finding with nothing written; app_event after a
freeze records the event and `career_query("pipeline")` shows it as the stage; letter_check
passes a clean letter and returns ok false with the DO NOT SEND verdict for a number the
career cannot back; and a bad kind, date or submitted is a finding with its fix, never a
protocol error.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import appkit
import careerkit
from test_graph_native_apps import ADVERT, DROPS, ROWS, STEM
from test_graph_native_freeze import CLEAN_LETTER, KINDS
from test_graph_native_selection import SUMMARY, TODAY
from test_mcp_server import Served, fails

# A day before the clock's TODAY, so an event on TODAY is the latest and is the stage.
SENT = "2026-10-01"
DATED = f"{SENT}-{STEM}"


class Shipped(Served):
    """ADVERT analysed, its resume selected, summarised, confirmed and shipped with fake
    TeX, every step but the analysis through the tools."""

    def setUp(self):
        import shipkit
        from jsk.adapters.compose import native, render
        from jsk.adapters.mcp import server, session

        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # The parse gate reads contact details and a summary off the render.
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", edits=[shipkit.CONTACTED])
        self.session = session.Session(root=self.root)
        self.server = server.build(self.session)
        native.capture(self.root, STEM, text=ADVERT, today=TODAY)
        native.decide(self.root, STEM, rows=ROWS, drops=DROPS, today=TODAY)
        native.complete_posting(self.root, STEM, today=TODAY)
        native.derive_assessment(self.root, STEM, today=TODAY)
        native.review(self.root, STEM, fit="partial", short=["Rust"], today=TODAY)
        native.complete_review(self.root, STEM, today=TODAY)
        for tool, args in (("resume_select", {"target": STEM, "mode": "from_match"}),
                           ("resume_update", {"target": STEM, "summary": SUMMARY}),
                           ("career_confirm", {"target": STEM, "block": "summary",
                                               "answer": "Yes, that is what I do."})):
            got = self.call(tool, **args)
            self.assertTrue(got["ok"], got)
        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile()):
            shipped = self.call("resume_ship", target=STEM, fit=False)
        self.assertTrue(shipped["ok"], shipped)
        self.app = Path(self.root) / "applications" / STEM

    def freeze(self, app=STEM, submitted=SENT):
        return self.call("app_freeze", app=app, submitted=submitted, channel="Workday portal")


class Freeze(Shipped):
    def test_a_freeze_renames_moves_five_graphs_and_reports_the_canonical_hash(self):
        from jsk.adapters.compose import selection
        from jsk.domain.resume.selection import canonical

        doc = selection.read(self.root, STEM)
        got = self.freeze()
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["renamed_to"], f"applications/{DATED}")
        self.assertEqual(got["written"], f"applications/{DATED}/application")
        self.assertFalse(self.app.exists(), "the directory was renamed")
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assertIsNone(appkit.triples(self.root, f"applications/{STEM}/{kind}"))
                self.assertIsNotNone(appkit.triples(self.root, f"applications/{DATED}/{kind}"))
        # Ruling 7: the hash is the selection's canonical text's; there is no resume.json.
        self.assertEqual(got["recordSha256"],
                         hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest())
        self.assertTrue(got["carried"])
        self.assertTrue(got["documents"] and all(d.endswith(".pdf") for d in got["documents"]))
        # The gates the freeze ran are there to read, not only their verdict.
        self.assertIn("record gate", {s["gate"] for s in got["steps"]})

    def test_a_second_freeze_is_refused_as_a_finding_and_writes_nothing(self):
        self.assertTrue(self.freeze()["ok"])
        before = appkit.facts(self.root, f"applications/{DATED}/application")
        again = self.freeze(app=DATED)
        self.assertFalse(again["ok"])
        self.assertTrue(any("never re-frozen" in t for t in fails(again)), again)
        self.assertIsNone(again["written"])
        self.assertEqual(appkit.facts(self.root, f"applications/{DATED}/application"), before)

    def test_a_bad_submitted_or_an_unknown_application_is_a_finding(self):
        for args, said in (({"submitted": "02/10/2026"}, "YYYY-MM-DD or false"),
                           ({"app": "nonesuch"}, "no application directory")):
            with self.subTest(args=args):
                got = self.freeze(**args)
                self.assertFalse(got["ok"])
                self.assertIn(said, fails(got)[0])
                self.assertTrue(got["findings"][0]["fix"])
        self.assertTrue(self.app.is_dir(), "nothing was renamed")


class Event(Shipped):
    def test_an_event_after_a_freeze_is_recorded_and_is_the_pipelines_stage(self):
        self.assertTrue(self.freeze()["ok"])
        got = self.call("app_event", app=DATED, kind="acknowledged", date=TODAY.isoformat(),
                        channel="email")
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["event"]["kind"], "acknowledged")
        self.assertTrue(got["event"]["id"].startswith("k:evt_"))
        rows = self.call("career_query", name="pipeline")["rows"]
        self.assertEqual(len(rows), 1, rows)
        [row] = rows
        self.assertEqual(row["stage"], "acknowledged")

    def test_a_bad_kind_or_date_is_a_finding_not_a_protocol_error(self):
        self.assertTrue(self.freeze()["ok"])
        for args, said in (({"kind": "acknowleged"}, "unknown kind"),
                           ({"date": "yesterday"}, "YYYY-MM-DD or unknown"),
                           ({"due": "soon"}, "due needs YYYY-MM-DD")):
            with self.subTest(args=args):
                # called() asserts the result is not a protocol error before it parses it.
                got = self.call("app_event", **{"app": DATED, "kind": "acknowledged",
                                                "date": TODAY.isoformat(), **args})
                self.assertFalse(got["ok"])
                self.assertIn(said, fails(got)[0])
        near = self.call("app_event", app=DATED, kind="acknowleged", date="unknown")
        self.assertIn("'acknowledged'", near["findings"][0]["fix"], "the near kind is named")

    def test_an_application_not_yet_frozen_is_told_to_freeze_first(self):
        got = self.call("app_event", app=STEM, kind="note", date=TODAY.isoformat(),
                        note="Called the recruiter.")
        self.assertFalse(got["ok"])
        self.assertIn("app_freeze", got["findings"][0]["fix"])


class Letter(Shipped):
    def letter(self, text):
        path = self.app / "cover-letter.txt"
        path.write_text(text, encoding="utf-8")
        return f"applications/{STEM}/cover-letter.txt"

    def test_a_clean_letter_passes(self):
        got = self.call("letter_check", letter=self.letter(CLEAN_LETTER), record=STEM)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["verdict"], "PASS - fit to send")
        self.assertIn(f"against: applications/{STEM}/resume", got["output"])

    def test_an_untraceable_number_is_do_not_send_with_its_finding_and_fix(self):
        text = CLEAN_LETTER.replace("in detail.", "in detail, including 9137 tenants.")
        got = self.call("letter_check", letter=self.letter(text), record=STEM)
        self.assertFalse(got["ok"])
        self.assertTrue(got["verdict"].startswith("DO NOT SEND"), got["verdict"])
        [untraced] = [f for f in got["findings"] if "'9137'" in f["text"]]
        self.assertEqual(untraced["severity"], "FAIL")
        self.assertTrue(untraced["fix"], "each finding carries its fix")

    def test_a_file_made_application_is_refused_as_having_no_selection(self):
        # The 2026-10-04 replay: the claims fixture's contoso-platform is made from files, and
        # the gate read its name as a path holding a resume.json jsk no longer reads.
        got = self.call("letter_check", letter=self.letter(CLEAN_LETTER),
                        record="contoso-platform")
        self.assertFalse(got["ok"])
        self.assertIsNone(got["verdict"])
        [said] = fails(got)
        self.assertIn("applications/contoso-platform, an application made from files", said)
        self.assertNotIn("resume.json", said)

    def test_a_missing_letter_is_a_finding(self):
        got = self.call("letter_check", letter="applications/nope.txt", record=STEM)
        self.assertFalse(got["ok"])
        self.assertIn("file not found", fails(got)[0])


if __name__ == "__main__":
    unittest.main()
