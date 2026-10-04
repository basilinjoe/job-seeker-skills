"""The app_freeze tool (recordkit.freeze calls what it calls): it refuses to archive anything the gates would not pass, and
what it archives is the application record of what was sent.

The application is graph-native (tests/shipkit.py's GraphCase): its record is the stored
selection, hashed as its canonical text. A file-made one was frozen from its resume.json
until 6.0, which freezes none (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md,
P2); that refusal is tests/test_retired.py's. `jsk app freeze` itself is retired
(docs/superpowers/plans/2026-10-04-retire-duplicated-cli.md): its flag parsing is gone with it.
"""
import json
import unittest
from pathlib import Path

import appkit
import recordkit
from fixtures import CLEAN_RESUME, build_pdf
from shipkit import BAD, D1, GraphCase, ShortCase


def k(*ids):
    from jsk.domain import ontology as O
    return sorted(O.K + i for i in ids)


class FreezeGraph(GraphCase):
    def test_it_writes_application_ttl_with_what_it_carried(self):
        import hashlib

        from jsk.adapters.compose import selection
        from jsk.domain.resume.selection import canonical

        raw = canonical(selection.read(str(self.root), "contoso-platform")).encode("utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertFalse((self.sent / "application.md").exists())
        app, events = self.application()
        self.assertEqual(app["posting"], k("post_contoso_platform"))
        self.assertEqual((app["view"], app["submitted"], app["channel"]),
                         (["resume"], ["2026-09-24"], ["Workday portal"]))
        # The PDF alone: a render writes no plain-text file (Ruling 23 of the graph-native
        # plan), so the documents are the PDFs and the letters.
        self.assertEqual(app["document"], ["Jane_Doe_Resume.pdf"])
        self.assertEqual(app["recordSha256"], [hashlib.sha256(raw).hexdigest()])
        # The inferred ingestion bullet is under the file's floor: it was not sent.
        self.assertEqual(app["carried"], k("ach_events_latency", "ach_events_team",
                                           "ach_identity_sso"))
        self.assertEqual(app["carriedVersion"], k("met_apps.v1", "met_latency.v2", "met_team.v1"))
        self.assertEqual(events["evt_contoso_platform_2026_09_24_submitted"]["kind"],
                         "tag:jsk,2026:ns#submitted")

    def test_it_writes_the_application_graph_and_no_file(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn(f"froze  {self.graph(self.sent, 'application')}", out)
        self.assertFalse((self.sent / "application.ttl").exists())

    def test_the_rename_moves_the_applications_graphs_with_it_and_the_workspace_validates(self):
        """A graph is named by its directory: the posting and the assessment move to the
        new name in the update that writes the application, and none stays at the old."""
        appkit.put(self.root, self.graph(self.app, "gaps"),
                   "k:gap_contoso_platform j:posting k:post_contoso_platform ; "
                   'j:assessed "2026-09-24"^^xsd:date ; j:fit j:partial .\n')
        posting = appkit.facts(self.root, self.graph(self.app, "posting"))
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        s = self.store()
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual({k for k in s.parsed if k.startswith("applications/")},
                         {self.graph(self.sent, kind) for kind in
                          ("posting", "gaps", "resume", "application")})
        self.assertEqual(appkit.facts(self.root, self.graph(self.sent, "posting")), posting)

    def test_a_store_that_refuses_the_write_leaves_the_directory_where_it_was(self):
        before = appkit.graphs(self.root)
        with appkit.refusing_store():
            code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("the record was not written", out)
        self.assertTrue(self.app.exists())
        self.assertFalse(self.sent.exists())
        self.assertEqual(appkit.graphs(self.root).keys(), before.keys())

    def test_a_freeze_that_lands_while_this_one_waits_is_not_overwritten(self):
        """Frozen is asked again inside the turn: another freeze of this application can
        land between the first check and this one's turn."""
        from unittest import mock

        from jsk.infra.oxigraph import record as R
        turn = R.turn
        other = 'k:app_contoso_platform j:submitted "2026-09-23"^^xsd:date .\n'

        def landed_first(root, dry_run=False):
            appkit.put(self.root, self.graph(self.app, "application"), other)
            return turn(root, dry_run)
        with mock.patch.object(R, "turn", landed_first):
            code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("never re-frozen", out)
        self.assertTrue(self.app.exists())
        self.assertFalse(self.sent.exists())
        self.assertEqual(self.application(self.app)[0]["submitted"], ["2026-09-23"])

    def test_the_store_is_not_read_again_after_the_rename(self):
        """The graphs a rename moves are the ones freeze() validated inside the turn: read
        again after the rename, a store that will not open left the folder renamed."""
        from unittest import mock

        from jsk.infra.oxigraph import db
        read = db.read

        def before_the_rename_only(root):
            if not self.app.exists():
                raise db.StoreError("career/store/ could not be opened", "`jsk doctor`")
            return read(root)
        with mock.patch.object(db, "read", before_the_rename_only):
            code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertTrue(appkit.has(self.root, self.graph(self.sent, "posting")))

    def test_a_store_error_while_writing_renames_the_folder_back(self):
        from unittest import mock

        from jsk.adapters.compose import timeline; from jsk.infra.oxigraph import db

        def unopenable(*_args):
            raise db.StoreError("career/store/ could not be opened", "`jsk doctor` checks it")
        with mock.patch.object(timeline, "write_frozen", unopenable):
            code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("the record was not written", out)
        self.assertTrue(self.app.exists())
        self.assertFalse(self.sent.exists())

    def test_a_store_failing_after_the_write_landed_keeps_the_rename(self):
        """The application's graph is in the store under the new name: renaming the folder
        back would part it from its graphs, and "nothing was written" would be false."""
        with appkit.failing_after_write():
            code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertNotIn("nothing was written", out)
        self.assertIn("landed", out)
        self.assertTrue(self.sent.exists())
        self.assertFalse(self.app.exists())
        self.assertTrue(appkit.has(self.root, self.graph(self.sent, "application")))

    def test_an_application_typed_in_another_case_moves_its_graphs(self):
        other = self.app.parent / self.app.name.upper()
        if not other.is_dir():
            self.skipTest("a case-sensitive filesystem: another case is another folder")
        self.app = other
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertTrue(self.sent.is_dir())
        self.assertEqual(sorted(g for g in appkit.graphs(self.root) if g.startswith("appl")),
                         sorted(self.graph(self.sent, k)
                                for k in ("posting", "resume", "application")))

    def test_the_record_gate_runs_and_its_output_is_shown(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("--- record gate: record.py", out)
        self.assertIn("checking: applications/contoso-platform/resume   against: "
                      "career/store/", out)
        self.assertNotIn("claims gate", out)

    def test_the_career_is_never_touched(self):
        """Nor logged: the log is the career's history, and an application is not the
        career."""
        before = [appkit.facts(self.root, g) for g in ("kb", "log")]
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertEqual([appkit.facts(self.root, g) for g in ("kb", "log")], before)
        self.assertIn("app_event", out)

    def test_held_back_has_no_submitted_event(self):
        code, out = self.freeze(submitted="false")
        self.assertEqual(code, 0, out)
        app, events = self.application(self.app)
        self.assertEqual(app["submitted"], ["false"])
        self.assertEqual(events, {})

    def test_a_record_that_fails_the_record_gate_is_never_frozen(self):
        self.edit_career(*D1)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("number-superseded", out)
        self.assertIn("never frozen", out)
        self.assertTrue(self.app.exists())
        self.assertFalse(appkit.has(self.root, self.graph(self.app, "application")))
        self.assertFalse(self.sent.exists())

    def test_no_posting_is_refused(self):
        appkit.drop(self.root, self.graph(self.app, "posting"))
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("no posting in", out)
        self.assertIn("posting_capture", out)
        self.assertFalse(self.sent.exists())

    def test_a_frozen_application_is_never_refrozen(self):
        code, out = self.freeze(submitted="false")
        self.assertEqual(code, 0, out)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("never re-frozen", out)

    def test_it_says_what_is_true_afterwards(self):
        """It used to end, in a Markdown workspace, with "append the row to log.md" -
        a file nothing writes now. Later events are the app_event tool."""
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("app_event", out)
        self.assertNotIn("log.md", out)


class FreezeWrites(GraphCase):
    def test_the_directory_is_renamed_to_the_day_it_was_sent(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertFalse(self.app.exists())
        self.assertTrue(appkit.has(self.root, self.graph(self.sent, "posting")))
        self.assertIn(str(self.sent), out)

    def test_a_directory_already_named_for_the_day_stays_where_it_is(self):
        from jsk.infra.oxigraph import record as R

        moved = {}
        for kind in ("posting", "resume"):
            moved[self.graph(self.app, kind)] = None
            moved[self.graph(self.sent, kind)] = appkit.triples(self.root,
                                                                self.graph(self.app, kind))
        R.write_graphs(str(self.root), moved)
        self.app.rename(self.sent)
        self.app = self.sent
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertTrue(appkit.has(self.root, self.graph(self.sent, "application")))
        self.assertNotIn("moved", out)

    def test_a_named_document_is_the_only_one_gated_and_listed(self):
        """The render that was not sent is neither checked nor archived as sent."""
        build_pdf(self.app / "Jane_Doe_Resume_ATS.pdf", CLEAN_RESUME)
        (self.app / "Jane_Doe_Resume_ATS.tex").write_text(
            (self.app / "Jane_Doe_Resume.tex").read_text(encoding="utf-8"), encoding="utf-8")
        code, out = self.freeze("Jane_Doe_Resume_ATS.pdf")
        self.assertEqual(code, 0, out)
        self.assertNotIn("check_ats.py Jane_Doe_Resume.pdf", out)
        app, _ = self.application()
        self.assertEqual(app["document"], ["Jane_Doe_Resume_ATS.pdf"])

    def test_the_gates_output_is_shown(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)
        self.assertIn("--- prose gate", out)


class Untouched:
    def assertUntouched(self):
        self.assertTrue(self.app.exists())
        if (self.root / "career" / "store").exists():
            self.assertFalse([g for g in appkit.graphs(self.root)
                              if g.endswith("/application")])
        self.assertFalse((self.app / "application.ttl").exists())
        self.assertFalse(self.sent.exists())


class FreezeRefuses(Untouched, GraphCase):
    """Every refusal leaves the directory exactly as it was: no application record, and
    no rename."""

    def test_two_pdfs_and_no_doc_is_a_question_not_a_guess(self):
        """Only the person knows which render was sent; listing both archives one
        nobody submitted as though it was."""
        build_pdf(self.app / "Jane_Doe_Resume_ATS.pdf", CLEAN_RESUME)
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("2 PDFs", out)
        self.assertIn("--doc", out)
        self.assertUntouched()

    def test_an_applications_folder_away_from_the_career_is_refused(self):
        """A session once wrote its applications relative to its working directory.
        The been-here-before check looks beside the career, so a round frozen anywhere
        else is one no later round can see. The app_freeze tool only reaches a directory
        under its workspace, so "away from the career" is a workspace with no store: the
        retired command's own "no career/store/ beside" check is gone with it, and the
        refusal is the one the missing record gives."""
        import shutil
        shutil.rmtree(self.root / "career" / "store")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED", out)
        self.assertUntouched()

    def test_an_application_md_is_as_frozen_as_an_application_record(self):
        (self.app / "application.md").write_text("original\n", encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("never re-frozen", out)
        self.assertEqual((self.app / "application.md").read_text(encoding="utf-8"),
                         "original\n")
        self.assertUntouched()

    def test_a_failing_document_is_never_frozen(self):
        self.render(CLEAN_RESUME + [BAD])
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)
        self.assertIn("never frozen", out)
        self.assertUntouched()

    def test_a_resume_json_beside_it_is_never_read(self):
        """A full URS record, or any resume.json, was the record a freeze read until 6.0;
        a graph-native application's record is its stored selection (Ruling 11 of the
        graph-native plan), so a file beside it changes nothing frozen."""
        legacy = Path(__file__).parent / "legacy_fixtures" / "contoso-resume.urs.json"
        (self.app / "resume.json").write_bytes(legacy.read_bytes())
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertNotIn("URS", out)

    def test_a_directory_with_nothing_sendable_is_refused(self):
        (self.app / "Jane_Doe_Resume.pdf").unlink()
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("no .pdf or .txt", out)
        self.assertUntouched()

    def test_a_rename_target_that_exists_is_refused(self):
        self.sent.mkdir()
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("already exists", out)
        self.assertFalse([g for g in appkit.graphs(self.root) if g.endswith("/application")])

    def test_a_named_document_that_is_not_there_is_refused(self):
        code, out = self.freeze("Cover_Letter.pdf")
        self.assertEqual(code, 1, out)
        self.assertIn("Cover_Letter.pdf", out)
        self.assertUntouched()


LETTER = ("Dear Hiring Manager,\n\n"
          "I build event platforms that other teams build on, and the platform role asks "
          "for that work. At my last role I cut event latency on Kafka and led the team "
          "that ran it.\n\n"
          "I would welcome a conversation about the role.\n\n"
          "Best regards,\nJane Doe\n")


class FreezeLetters(Untouched, GraphCase):
    """Ruling 5 (2026-09-28): every document freeze lists has passed a gate that read it.
    The gates read `*_Resume*` renders and freeze listed every .pdf and .txt, so a cover
    letter went into the application record as sent with no gate having opened it."""

    def test_a_letter_holding_a_placeholder_is_never_frozen(self):
        (self.app / "cover-letter.txt").write_text(
            LETTER.replace("the platform role", "the role at [COMPANY]"), encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("--- letter gate: letter.py cover-letter.txt --record contoso-platform",
                      out)
        self.assertIn("[COMPANY]", out)
        self.assertIn("never frozen", out)
        self.assertUntouched()

    def test_a_clean_letter_is_gated_and_listed(self):
        (self.app / "cover-letter.txt").write_text(LETTER, encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - fit to send", out)
        app, _ = self.application()
        self.assertEqual(app["document"], ["Jane_Doe_Resume.pdf", "cover-letter.txt"])

    def test_a_pdf_letter_no_gate_reads_is_refused(self):
        """Named with --doc: two PDFs in the directory are otherwise a question first."""
        build_pdf(self.app / "Cover_Letter.pdf", LETTER.splitlines())
        code, out = self.freeze("Jane_Doe_Resume.pdf", "Cover_Letter.pdf")
        self.assertEqual(code, 1, out)
        self.assertIn("Cover_Letter.pdf", out)
        self.assertIn("send the letter's .txt beside it, or leave it out with --doc", out)
        self.assertUntouched()

    def test_a_pdf_letter_with_its_txt_beside_it_is_frozen(self):
        """The cost Ruling 5 names: one extra file, and it is what the letter gate reads."""
        build_pdf(self.app / "Cover_Letter.pdf", LETTER.splitlines())
        (self.app / "Cover_Letter.txt").write_text(LETTER, encoding="utf-8")
        code, out = self.freeze("Jane_Doe_Resume.pdf", "Cover_Letter.pdf", "Cover_Letter.txt")
        self.assertEqual(code, 0, out)
        app, _ = self.application()
        self.assertIn("Cover_Letter.pdf", app["document"])

    def test_the_tailoring_files_are_not_documents(self):
        """Every tailoring run leaves gaps.txt and decisions.txt beside the resume. Listed,
        the letter gate read them as letters - hundreds of words, advert line numbers
        traced as claims - and a clean application could not be frozen."""
        (self.app / "gaps.txt").write_text("fit: partial\n" + "word " * 400 + "\n",
                                           encoding="utf-8")
        (self.app / "decisions.txt").write_text("12 | need | 5 years of Kafka\n",
                                                encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertNotIn("letter gate", out)
        app, _ = self.application()
        self.assertEqual(app["document"], ["Jane_Doe_Resume.pdf"])

    def test_the_plain_text_an_earlier_render_left_is_not_a_document(self):
        """A render wrote <name>_Resume_ATS.txt before the gates read the plan's text in
        memory. Left in an application from then, it is neither a letter nor anything
        sent: listed, the letter gate would read a resume as a letter and fail it."""
        (self.app / "Jane_Doe_Resume_ATS.txt").write_text("Jane Doe\n" + "word " * 400 + "\n",
                                                          encoding="utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertNotIn("letter gate", out)
        app, _ = self.application()
        self.assertEqual(app["document"], ["Jane_Doe_Resume.pdf"])


class FreezeMarkdownWorkspace(GraphCase):
    """freeze once wrote an application.md for a workspace still on user-knowledgebase.md.
    jsk no longer reads that file: with no career/kb.ttl beside it, nothing is frozen."""

    def setUp(self):
        import shutil

        super().setUp()
        shutil.rmtree(self.root / "career" / "store")
        (self.root / "user-knowledgebase.md").write_text("# KB\n", encoding="utf-8")

    def test_it_is_refused_for_want_of_the_record(self):
        code, out = self.freeze()
        # The command said "no career/store/" and exited 2; the tool refuses on the record
        # it cannot find (exit 1 here), and still names no migration.
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED", out)
        self.assertNotIn("jsk migrate", out)
        self.assertTrue(self.app.exists())
        self.assertFalse(self.sent.exists())
        self.assertEqual(sorted(p.name for p in self.app.iterdir()
                                if p.name.startswith("application")), [])


class FreezeUsage(GraphCase):
    def test_submitted_must_be_a_date_or_false(self):
        for bad in ("yesterday", "2026-9-8", "2026-02-30", "no"):
            with self.subTest(submitted=bad):
                code, out = self.freeze(submitted=bad)
                self.assertEqual(code, 2, out)

    def test_a_channel_is_required(self):
        code, out = self.freeze(channel=" ")
        self.assertEqual(code, 2, out)
        self.assertIn("channel is required", out)

    def test_a_directory_that_does_not_exist_is_a_call_error(self):
        code, out = recordkit.freeze(self.root, self.root / "nowhere", "false", "email")
        self.assertEqual(code, 2, out)
        self.assertIn("no application directory", out)


class Stale(GraphCase):
    """graphsim S9: an application sent a metric's number; the number is revised; the
    application is named as having sent the old one."""

    def test_revising_a_carried_metric_makes_the_application_stale(self):
        from test_graph_changeset import PFX

        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        code, out = recordkit.query(self.root, "stale", json=True)
        self.assertEqual((code, json.loads(out)), (0, []))
        change = self.root / "revise.trig"
        change.write_text(PFX + 'op:changeset op:base 1 ; op:summary "Re-measured." .\n'
                          'op:set { k:met_latency.v2 j:value 350 . }\n', encoding="utf-8")
        code, out = recordkit.apply(self.root, change.read_text(encoding="utf-8"))
        self.assertEqual(code, 0, out)
        self.assertIn("the new number is k:met_latency.v3", out)
        code, out = recordkit.query(self.root, "stale", json=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out), [{
            "application": "k:app_contoso_platform", "sent": "k:met_latency.v2",
            "replaced": __import__("datetime").date.today().isoformat(),
            "current": "k:met_latency.v3"}])


class FreezeShort(ShortCase):
    def test_it_carries_only_the_bullets_that_rendered(self):
        import hashlib

        from jsk.domain.resume.selection import canonical

        raw = canonical(self.SHORT).encode("utf-8")
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        app, _ = self.application()
        # The inferred ingestion bullet is listed in the file but withheld by the floor:
        # it was never sent, so the application does not claim it was.
        self.assertEqual(app["carried"], k("ach_events_latency", "ach_events_team",
                                           "ach_identity_sso"))
        self.assertEqual(app["carriedVersion"], k("met_apps.v1", "met_latency.v2",
                                                  "met_team.v1"))
        self.assertEqual(app["recordSha256"], [hashlib.sha256(raw).hexdigest()])
        self.assertEqual(app["view"], ["resume"])

    def test_the_workspace_validates_with_it(self):
        code, out = self.freeze()
        self.assertEqual(code, 0, out)
        self.assertEqual([f.text() for f in self.store().fails()], [])

    def test_a_selection_that_does_not_build_is_never_frozen(self):
        self.selected({"resume": 2, "bullets": ["ach_nope"]})
        code, out = self.freeze()
        self.assertEqual(code, 1, out)
        self.assertIn("ach_nope", out)
        self.assertFalse(appkit.has(self.root, self.graph(self.app, "application")))
        self.assertFalse(self.sent.exists())


if __name__ == "__main__":
    unittest.main()
