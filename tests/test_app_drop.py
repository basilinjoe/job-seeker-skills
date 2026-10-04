"""The app_drop tool (jsk mcp) sets an unsent application aside: the amended Ruling 5 of
docs/superpowers/plans/2026-10-03-retire-file-pipeline.md (2026-10-03).

The rules pinned: an application that was never frozen - made from files or graph-native - has
every graph the store holds for it (posting, review, gaps, resume) removed in one validated
update, and its folder moved, files intact, to `dropped/<stem>/` beside applications/
(`<stem>-2` when that is taken) with a DROPPED.txt saying the day, the reason and what left the
store; it is then no longer named unsent by `file_made_unsent` or the career_check tool. A frozen
application, sent or held back, is refused with nothing changed, the fix saying it is an
archive. A removal the workspace would not validate without is refused with nothing changed.
`dry_run` names everything it would remove and move, and changes nothing. A path that is no
application - no folder and no graph - is a call made wrongly, exit 2. The tool calls
adapters/entry/drop.main, so the tests call it the same way (recordkit.drop) and read what it
printed; `jsk app drop` itself is retired and exits 2 naming the tool (tests/test_retired.py).
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import appkit
import careerkit
import recordkit

FILE_MADE = "contoso-platform"
TODAY = "2026-10-03"


def snapshot(root):
    """The store's graphs as fact sets and every file under the workspace but the store:
    what "nothing changed" compares."""
    root = Path(root)
    graphs = {name: appkit.facts(root, name) for name in appkit.graphs(root)}
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
             if p.is_file() and "career" not in p.relative_to(root).parts}
    return graphs, files


class FileMade(unittest.TestCase):
    """The claims fixture: contoso-platform, made from files and unsent, its posting graph in
    the store and posting.md and resume.json in its folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", short=careerkit.short())
        self.root = Path(self.root)
        self.app = self.root / "applications" / FILE_MADE

    def drop(self, *extra, app=None):
        return recordkit.drop(self.root, app or self.app, "--today", TODAY, *extra)

    def test_it_removes_the_graphs_and_moves_the_folder_with_a_note(self):
        files = sorted(p.name for p in self.app.iterdir())
        self.assertTrue(appkit.has(self.root, f"applications/{FILE_MADE}/posting"))
        code, out = self.drop("--reason", "role filled before I applied")
        self.assertEqual(code, 0, out)
        self.assertIn(f"ok    removed applications/{FILE_MADE}/posting from career/store/", out)
        self.assertIn(f"ok    moved applications/{FILE_MADE}/ -> dropped/{FILE_MADE}/", out)
        self.assertFalse(any(name.startswith(f"applications/{FILE_MADE}/")
                             for name in appkit.graphs(self.root)), "every graph left the store")
        aside = self.root / "dropped" / FILE_MADE
        self.assertFalse(self.app.exists())
        # The files are kept as they were: the note is the only thing added.
        self.assertEqual(sorted(p.name for p in aside.iterdir()), sorted(files + ["DROPPED.txt"]))
        note = (aside / "DROPPED.txt").read_text(encoding="utf-8")
        self.assertIn(f"dropped   {TODAY}", note)
        self.assertIn("reason    role filled before I applied", note)
        self.assertIn(f"  applications/{FILE_MADE}/posting", note)

    def test_it_is_no_longer_named_unsent(self):
        from jsk.application.timeline.unsent import file_made_unsent
        from jsk.infra.files import application_listing

        before = file_made_unsent(appkit.graphs(self.root), application_listing(self.root))
        self.assertIn(FILE_MADE, before)
        code, out = recordkit.kb_check(self.root)
        self.assertIn("file-made-unsent", out)
        # The fix names the tool that exists, never a changeset that cannot do it.
        self.assertIn(f'or drop it: the app_drop tool (jsk mcp), app_drop(app="{FILE_MADE}")',
                      out)
        self.assertNotIn("retiring its posting", out)
        self.assertEqual(self.drop()[0], 0)
        self.assertEqual(file_made_unsent(appkit.graphs(self.root),
                                          application_listing(self.root)), ())
        code, out = recordkit.kb_check(self.root)
        self.assertNotIn("file-made-unsent", out)

    def test_a_dry_run_names_everything_and_changes_nothing(self):
        before = snapshot(self.root)
        code, out = self.drop("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / "dropped").exists())
        self.assertIn(f"ok    would remove applications/{FILE_MADE}/posting from career/store/",
                      out)
        self.assertIn(f"ok    would move applications/{FILE_MADE}/ -> dropped/{FILE_MADE}/", out)
        self.assertIn(f"ok    would write dropped/{FILE_MADE}/DROPPED.txt", out)
        self.assertIn("dry run: nothing was written or moved", out)

    def test_a_name_taken_in_dropped_gets_the_next_number(self):
        earlier = self.root / "dropped" / FILE_MADE
        earlier.mkdir(parents=True)
        (earlier / "DROPPED.txt").write_text("an earlier drop\n", encoding="utf-8")
        code, out = self.drop()
        self.assertEqual(code, 0, out)
        self.assertIn(f"-> dropped/{FILE_MADE}-2/", out)
        self.assertTrue((self.root / "dropped" / f"{FILE_MADE}-2" / "posting.md").is_file())
        # The earlier drop is never covered.
        self.assertEqual((earlier / "DROPPED.txt").read_text(encoding="utf-8"),
                         "an earlier drop\n")

    def test_a_folder_with_no_graph_is_moved(self):
        globex = self.root / "applications" / "globex-data"
        globex.mkdir()
        (globex / "resume.json").write_text("{}", encoding="utf-8")
        code, out = self.drop(app=globex)
        self.assertEqual(code, 0, out)
        self.assertIn("ok    career/store/ holds no graph for it - nothing to remove", out)
        self.assertTrue((self.root / "dropped" / "globex-data" / "resume.json").is_file())
        self.assertIn("removed from career/store/: nothing",
                      (self.root / "dropped" / "globex-data" / "DROPPED.txt")
                      .read_text(encoding="utf-8"))

    def test_a_bare_stem_names_the_application_in_the_workspace(self):
        code, out = self.drop("--dry-run", app=FILE_MADE)
        self.assertEqual(code, 0, out)
        self.assertIn(f"would move applications/{FILE_MADE}/", out)

    def test_a_removal_that_breaks_a_rule_elsewhere_is_refused(self):
        class Broken:
            def text(self):
                return "k:app_other: its posting is gone"

        before = snapshot(self.root)
        with mock.patch("jsk.domain.record.state.new_failures", lambda a, b: [Broken()]):
            code, out = self.drop()
        self.assertEqual(code, 1, out)
        self.assertIn("would not validate without its graphs - k:app_other", out)
        self.assertIn("nothing was written or moved", out)
        self.assertEqual(snapshot(self.root), before)

    def test_a_path_that_is_no_application_is_a_call_made_wrongly(self):
        before = snapshot(self.root)
        code, out = self.drop(app=self.root / "applications" / "nothing-here")
        self.assertEqual(code, 2, out)
        self.assertIn("FAIL  applications/nothing-here is no application", out)
        code, out = self.drop(app=self.root / "career")
        self.assertEqual(code, 2, out)
        self.assertIn("is not an application in a workspace", out)
        self.assertEqual(snapshot(self.root), before)

    def test_called_wrong_is_exit_two(self):
        from jsk.adapters.entry import drop
        from jsk.adapters.mcp import captured

        self.assertEqual(captured.called(self.root, drop.main, [])[0], 2)
        self.assertEqual(self.drop("--today", "yesterday")[0], 2)


class FrozenIsRefused(unittest.TestCase):
    """A frozen application, sent or held back, is an archive and is never dropped."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root, _ = careerkit.workspace(Path(tmp.name) / "ws", short=careerkit.short())
        self.root = Path(root)
        posting = appkit.text(self.root, f"applications/{FILE_MADE}/posting")
        for stem, submitted in (("acme-sent", '"2026-09-10"^^xsd:date'),
                                ("acme-held", '"false"^^xsd:boolean')):
            shutil.copytree(self.root / "applications" / FILE_MADE,
                            self.root / "applications" / stem)
            appkit.put(self.root, f"applications/{stem}/posting", posting, prefixes=False)
            appkit.put(self.root, f"applications/{stem}/application",
                       f'k:app_{stem.replace("-", "_")} j:posting k:post_contoso_platform ; '
                       f'j:submitted {submitted} ; j:channel "company site" .\n')

    def test_a_sent_and_a_held_back_application_are_refused_with_nothing_changed(self):
        for stem in ("acme-sent", "acme-held"):
            with self.subTest(stem=stem):
                before = snapshot(self.root)
                code, out = recordkit.drop(self.root, self.root / "applications" / stem)
                self.assertEqual(code, 1, out)
                self.assertIn(f"FAIL  applications/{stem} is frozen", out)
                self.assertIn("a frozen application is an archive", out)
                self.assertIn("fix:  record what became of it instead: the app_event tool "
                              f'(jsk mcp), app_event(app="applications/{stem}", '
                              'kind="withdrawn"', out)
                self.assertEqual(snapshot(self.root), before)
                self.assertFalse((self.root / "dropped").exists())


class GraphNative(unittest.TestCase):
    """A graph-native application analysed and selected, never shipped: four graphs in the
    store and no folder yet."""

    def setUp(self):
        from test_graph_native_apps import STEM
        from test_graph_native_selection import Workspace

        class Selected(Workspace):
            def runTest(self):
                pass

        self.made = Selected()
        self.made.setUp()
        self.addCleanup(self.made.doCleanups)
        self.made.selected()
        self.root, self.stem = Path(self.made.root), STEM

    def test_its_four_graphs_are_removed_and_the_note_is_kept(self):
        kinds = ("posting", "review", "gaps", "resume")
        held = {name for name in appkit.graphs(self.root)
                if name.startswith(f"applications/{self.stem}/")}
        self.assertEqual(held, {f"applications/{self.stem}/{k}" for k in kinds})
        code, out = recordkit.drop(self.root, self.root / "applications" / self.stem,
                                   "--today", TODAY)
        self.assertEqual(code, 0, out)
        for kind in kinds:
            self.assertIn(f"ok    removed applications/{self.stem}/{kind} from career/store/",
                          out)
        self.assertNotIn("ok    moved", out, "there was no folder to move")
        self.assertFalse(any(name.startswith(f"applications/{self.stem}/")
                             for name in appkit.graphs(self.root)))
        note = (self.root / "dropped" / self.stem / "DROPPED.txt").read_text(encoding="utf-8")
        self.assertIn("no folder; this note is all there is", note)
        # The P3 review (2026-10-04): it went on of files "as they were" and "moving this
        # folder back", of a folder there never was.
        self.assertIn("It had no folder, so no file was moved.", note)
        self.assertNotIn("The files are as they were", note)
        self.assertNotIn("moving", note)


if __name__ == "__main__":
    unittest.main()
