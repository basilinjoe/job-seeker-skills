"""A graph-native resume's selection: P3b of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md.

The rules pinned: `resume_select` makes the selection graph from the match for a graph-native
application whose posting is complete, or by the career's ranking for a general resume
(`resumes/<name>`), and writes no resume.json (Ruling 6); a second select is refused unless
told to replace; `resume_update` checks the whole dict, refuses an unknown id with nothing
written, and drops a summary whose text changed back to inferred, its answer and hash with
it; `career_confirm` on a target confirms the block in the graph; a sent application refuses
every change; the render, the record gate and the ship take a target and leave only the .pdf
and the .tex in its directory (Rulings 12 and 22), while a resume.json inside a graph-native
application is refused by the path form, naming the tool (Ruling 11); and what a later freeze
would hash (`canonical`) does not move under an update that changes nothing (Ruling 7).
"""
import contextlib
import datetime
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import appkit
import careerkit
import shipkit
from jsk.adapters.cli.compose import native, selection
from jsk.application.record.refusals import Refused as ConfirmRefused
from jsk.domain.posting.errors import Refused
from jsk.domain.resume.selection import canonical
from test_graph_native_apps import ADVERT, DROPS, ROWS, STEM

TODAY = datetime.date(2026, 10, 2)
GRAPH = f"applications/{STEM}/resume"
SUMMARY = ("Platform engineer who runs event platforms other teams build on, from the "
           "cluster up.")


def fails(findings):
    return [text for severity, text, _ in findings if severity == "FAIL"]


class Workspace(unittest.TestCase):
    """The claims fixture, stored, with ADVERT captured, decided, completed, derived and
    reviewed as applications/acme-platform: what the analyst leaves for the author."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws",
                                           edits=[shipkit.CONTACTED])
        self.app = Path(self.root) / "applications" / STEM

    def analysed(self):
        native.capture(self.root, STEM, text=ADVERT, today=TODAY)
        self.assertEqual(fails(native.decide(self.root, STEM, rows=ROWS, drops=DROPS,
                                             today=TODAY).findings), [])
        self.assertEqual(fails(native.complete_posting(self.root, STEM,
                                                       today=TODAY).findings), [])
        native.derive_assessment(self.root, STEM, today=TODAY)
        native.review(self.root, STEM, fit="partial", short=["Rust"], today=TODAY)
        self.assertEqual(native.complete_review(self.root, STEM, today=TODAY).state,
                         "complete")

    def selected(self, headline=None):
        self.analysed()
        done = selection.select(self.root, STEM, mode="from_match", today=TODAY)
        self.assertEqual(fails(done.findings), [])
        if headline:
            done = selection.update(self.root, STEM, headline=headline, today=TODAY)
            self.assertEqual(fails(done.findings), [])
        return done

    def facts(self, graph=GRAPH):
        return appkit.facts(self.root, graph)


class Select(Workspace):
    def test_from_match_writes_the_selection_graph_and_no_file(self):
        done = self.selected()
        self.assertEqual((done.target, done.written), (GRAPH, (GRAPH,)))
        self.assertTrue(done.doc["bullets"])
        # The posting's title is the career's own headline, so export retunes none.
        self.assertNotIn("headline", done.doc)
        self.assertEqual(selection.read(self.root, STEM), done.doc)
        self.assertFalse(self.app.exists(), "the directory is the first render's")

    def test_a_retuned_headline_is_confirmed_through_the_tool_not_a_file(self):
        # The note named `jsk kb confirm --headline <resume.json>`, a file a graph-native
        # application never has (2026-10-02).
        native.capture(self.root, STEM, text=ADVERT.replace("# Platform Engineer",
                                                            "# Staff Platform Engineer"),
                       today=TODAY)
        native.decide(self.root, STEM, rows=ROWS, drops=DROPS, today=TODAY)
        native.complete_posting(self.root, STEM, today=TODAY)
        done = selection.select(self.root, STEM, mode="from_match", today=TODAY)
        [note] = [n for n in done.notes if "headline" in n]
        self.assertIn(f'`career_confirm` (target "{STEM}", block "headline")', note)
        self.assertNotIn("resume.json", note)

    def test_the_selection_part_shows_each_bullets_words(self):
        done = self.selected()
        shown = native.show(self.root, STEM, "selection", today=TODAY)
        self.assertEqual(shown["doc"], done.doc)
        self.assertEqual([b["id"] for b in shown["bullets"]], done.doc["bullets"])
        self.assertTrue(all(b["text"] for b in shown["bullets"]))

    def test_a_second_select_is_refused_unless_replace(self):
        self.selected()
        with self.assertRaises(Refused) as caught:
            selection.select(self.root, STEM, mode="from_match", today=TODAY)
        self.assertIn("replace", caught.exception.fix)
        done = selection.select(self.root, STEM, mode="ranked", replace=True, today=TODAY)
        self.assertEqual(done.written, (GRAPH,))

    def test_from_match_on_a_draft_posting_is_refused(self):
        native.capture(self.root, STEM, text=ADVERT, today=TODAY)
        with self.assertRaises(Refused) as caught:
            selection.select(self.root, STEM, mode="from_match", today=TODAY)
        self.assertIn("draft", str(caught.exception))
        self.assertIsNone(appkit.triples(self.root, GRAPH))

    def test_ranked_selects_a_general_resume_and_from_match_is_refused_for_one(self):
        done = selection.select(self.root, "resumes/general", mode="ranked", today=TODAY)
        self.assertEqual(done.written, ("resumes/general/resume",))
        self.assertEqual(selection.read(self.root, "resumes/general"), done.doc)
        with self.assertRaises(Refused) as caught:
            selection.select(self.root, "resumes/cv", mode="from_match", today=TODAY)
        self.assertIn("ranked", caught.exception.fix)

    def test_a_legacy_application_is_refused_naming_the_file_path(self):
        with self.assertRaises(Refused) as caught:
            selection.select(self.root, "contoso-platform", mode="ranked", today=TODAY)
        self.assertIn("jsk posting build", caught.exception.fix)

    def test_a_sent_application_refuses_every_change(self):
        self.selected(headline="Senior Platform Engineer")
        appkit.put(self.root, f"applications/{STEM}/application",
                   f'k:app_acme_platform j:posting k:post_acme_platform ; '
                   'j:submitted "2026-09-30"^^xsd:date .\n')
        calls = (lambda: selection.select(self.root, STEM, mode="ranked", replace=True,
                                          today=TODAY),
                 lambda: selection.update(self.root, STEM, pages=1, today=TODAY),
                 lambda: selection.confirm(self.root, STEM, "headline", "I am one."))
        for call in calls:
            with self.subTest(call=call), self.assertRaises((Refused, ConfirmRefused)) as caught:
                call()
            self.assertIn("was sent on 2026-09-30", str(caught.exception))


class Update(Workspace):
    def setUp(self):
        super().setUp()
        self.doc = self.selected().doc

    def test_order_and_pages_are_changed_and_read_back(self):
        order = list(reversed(self.doc["bullets"]))
        done = selection.update(self.root, STEM, bullets=order, pages=1, today=TODAY)
        self.assertEqual(fails(done.findings), [])
        doc = selection.read(self.root, STEM)
        self.assertEqual((doc["bullets"], doc["pages"]), (order, 1))

    def test_an_unknown_id_is_refused_and_nothing_is_written(self):
        before = self.facts()
        done = selection.update(self.root, STEM, bullets=self.doc["bullets"] + ["ach_gone"],
                                today=TODAY)
        self.assertTrue(any("ach_gone is not in the career" in f for f in fails(done.findings)),
                        done.findings)
        self.assertIsNone(done.target)
        self.assertEqual(self.facts(), before, "a FAIL writes nothing")

    def test_a_changed_summary_drops_to_inferred_with_its_answer_and_hash(self):
        selection.update(self.root, STEM, summary=SUMMARY, today=TODAY)
        selection.confirm(self.root, STEM, "summary", "Yes, that is how I put it.")
        confirmed = selection.read(self.root, STEM)["summary"]
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertIn("text_sha256", confirmed)
        # The same words keep the confirmation; new words lose it.
        selection.update(self.root, STEM, summary=SUMMARY, today=TODAY)
        self.assertEqual(selection.read(self.root, STEM)["summary"], confirmed)
        selection.update(self.root, STEM, summary=SUMMARY + " Mostly Kafka.", today=TODAY)
        self.assertEqual(selection.read(self.root, STEM)["summary"],
                         {"text": SUMMARY + " Mostly Kafka.", "status": "inferred"})

    def test_an_update_that_changes_nothing_leaves_the_canonical_text_alone(self):
        before = canonical(selection.read(self.root, STEM))
        done = selection.update(self.root, STEM, bullets=self.doc["bullets"],
                                pages=self.doc.get("pages"), today=TODAY)
        self.assertEqual((done.target, done.findings), (None, ()))
        self.assertEqual(canonical(selection.read(self.root, STEM)), before)


class Confirm(Workspace):
    def test_a_headline_is_confirmed_in_the_graph_through_kb_confirm(self):
        self.selected(headline="Senior Platform Engineer")
        done = selection.confirm(self.root, STEM, "headline", "Yes, that is my title.")
        self.assertIsNotNone(done.new)
        headline = selection.read(self.root, STEM)["headline"]
        self.assertEqual((headline["status"], headline["answer"]),
                         ("confirmed", "Yes, that is my title."))
        again = selection.confirm(self.root, STEM, "headline", "Yes, that is my title.")
        self.assertIsNone(again.new, "confirmed already: nothing to change")

    def test_an_answer_that_says_nothing_is_refused(self):
        self.selected(headline="Senior Platform Engineer")
        with self.assertRaises(ConfirmRefused):
            selection.confirm(self.root, STEM, "headline", "yes")

    def test_the_cli_confirms_a_target_where_it_took_a_resume_json(self):
        from jsk import cli

        self.selected(headline="Senior Platform Engineer")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["jsk", "kb", "confirm", "--headline", STEM, "--answer",
                             "It is the title I hold.", "--root", self.root])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertEqual(selection.read(self.root, STEM)["headline"]["status"], "confirmed")


class Ship(Workspace):
    """The render, the gates and the ship by target, with the TeX compile faked."""

    def shipped(self, target=STEM):
        from jsk.adapters.cli.compose import render

        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile()):
            return selection.ship_target(self.root, target, fit=False, today=TODAY)

    def test_a_ship_by_target_leaves_only_the_pdf_and_the_tex(self):
        self.selected()
        result = self.shipped()
        steps = {s.gate: s for s in result.steps}
        self.assertEqual(steps["record gate"].status, "PASS", steps["record gate"].output)
        self.assertEqual(steps["render"].status, "PASS", steps["render"].output)
        kinds = sorted(os.path.splitext(n)[1] for n in os.listdir(self.app))
        self.assertEqual(kinds, [".pdf", ".tex"], "no resume.json, no .txt, no .log")
        # The terms gate found the posting through the target's directory.
        self.assertIn("terms gate", steps)

    def test_a_general_resume_ships_into_its_own_directory(self):
        selection.select(self.root, "resumes/general", mode="ranked", today=TODAY)
        result = self.shipped("resumes/general")
        steps = {s.gate: s for s in result.steps}
        self.assertEqual(steps["render"].status, "PASS", steps["render"].output)
        home = Path(self.root) / "resumes" / "general"
        self.assertEqual(sorted(os.path.splitext(n)[1] for n in os.listdir(home)),
                         [".pdf", ".tex"])

    def test_a_target_with_no_selection_is_refused(self):
        self.analysed()
        with self.assertRaises(Refused) as caught:
            self.shipped()
        self.assertIn("resume_select", caught.exception.fix)

    def test_the_cli_ships_and_checks_a_target(self):
        from jsk import cli
        from jsk.adapters.cli.compose import render

        self.selected()
        buf = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile()), \
                contextlib.redirect_stdout(buf):
            check = cli.main(["jsk", "resume", "check", STEM])
            ship = cli.main(["jsk", "resume", "ship", STEM, "--no-fit"])
        out = buf.getvalue()
        self.assertEqual(check, 0, out)
        self.assertIn(f"checking: {GRAPH}", out)
        self.assertIn("--- render", out)
        self.assertNotEqual(ship, 2, out)
        self.assertTrue(list(self.app.glob("*.pdf")))

    def cli_in_root(self, *args):
        """(exit code, output) of `jsk *args` run from the workspace, the compile faked."""
        from jsk import cli
        from jsk.adapters.cli.compose import preview, render

        buf = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        with mock.patch.object(render, "compile_pdf", shipkit.fake_compile()), \
                mock.patch.object(preview, "compile_pdf", shipkit.fake_compile()), \
                mock.patch.object(preview, "available_engine", lambda: "fake"), \
                contextlib.redirect_stdout(buf):
            code = cli.main(["jsk", *args])
        return code, buf.getvalue()

    def test_render_takes_a_target_and_writes_into_its_own_directory(self):
        # P2 of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md: render gains
        # the target form before the resume.json positional goes.
        self.selected()
        code, out = self.cli_in_root("resume", "render", STEM, "--pdf")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(os.path.splitext(n)[1] for n in os.listdir(self.app)),
                         [".pdf", ".tex"])

    def test_render_of_a_general_resume_may_go_elsewhere_with_out(self):
        selection.select(self.root, "resumes/general", mode="ranked", today=TODAY)
        elsewhere = Path(self.root).parent / "look"
        code, out = self.cli_in_root("resume", "render", "resumes/general", "--out",
                                     str(elsewhere))
        self.assertEqual(code, 0, out)
        self.assertTrue(list(elsewhere.glob("*.tex")), out)
        self.assertFalse((Path(self.root) / "resumes" / "general").exists())

    def test_preview_takes_a_target(self):
        self.selected()
        out_dir = Path(self.root).parent / "previews"
        code, out = self.cli_in_root("resume", "preview", STEM, "--out", str(out_dir),
                                     "--only", "monolith")
        self.assertEqual(code, 0, out)
        self.assertIn(f"previewing {STEM}", out)
        self.assertTrue((out_dir / "monolith.pdf").exists(), out)

    def test_a_resume_json_in_a_graph_native_application_is_refused_naming_the_tool(self):
        from jsk import cli

        doc = self.selected().doc
        self.app.mkdir(parents=True)
        path = self.app / "resume.json"
        path.write_text(__import__("json").dumps(doc), encoding="utf-8")
        for verb in (["resume", "check", str(path)],
                     ["resume", "render", str(path), "--out", str(self.app)]):
            buf = io.StringIO()
            with self.subTest(verb=verb[1]), contextlib.redirect_stdout(buf):
                code = cli.main(["jsk", *verb])
                self.assertEqual(code, 2, buf.getvalue())
                self.assertIn("resume_update", buf.getvalue())
        self.assertFalse(list(self.app.glob("*.tex")), "nothing rendered")


if __name__ == "__main__":
    unittest.main()
