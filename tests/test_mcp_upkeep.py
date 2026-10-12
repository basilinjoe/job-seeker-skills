"""`jsk mcp`'s career_check, career_pack, career_merge and app_drop: Rulings 2 and 5 of
docs/superpowers/plans/2026-10-04-mcp-first.md, which made `jsk kb check|pack|merge` and
`jsk app drop` tools that call the entry points those commands called.

The rules pinned: career_check is ok on a clean workspace and, on one with a planted FAIL, is
not ok and carries the FAIL with its fix and the verdict lines whole; career_pack returns the
changeset text, which career_preview accepts, and writes nothing; once the record holds the
pack there is no changeset and a note says why; career_merge returns a changeset for two
concepts and what the verb said on stderr (what to re-confirm), and refuses an unknown
concept as a FAIL with no changeset; app_drop on a dry run changes neither the store nor a
file, a real drop moves the folder under dropped/ and removes its graphs, and a frozen
application is refused naming app_event, with nothing changed; and a workspace still laid out
as files is refused by every one of them with the fix that imports it.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import appkit
import careerkit
import storekit
from test_app_drop import FILE_MADE, snapshot
from test_graph_merge import VOCAB
from test_graph_pack import edit_career
from test_graph_shapes import FIXTURES
from test_mcp_server import HAS_MCP, TODAY, Served

FOUR = ("career_check", "career_pack", "career_merge", "app_drop")


def fails(result):
    return [f for f in result["findings"] if f["severity"] == "FAIL"]


class Career(Served):
    """The graph fixture workspace, seeded into a store and served."""

    def setUp(self):
        from jsk.adapters.mcp import server, session

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = str(Path(tmp.name) / "ws")
        shutil.copytree(FIXTURES, self.root)
        storekit.seed(self.root)
        clock = mock.patch.object(session, "today", return_value=TODAY)
        clock.start()
        self.addCleanup(clock.stop)
        self.session = session.Session(root=self.root)
        self.server = server.build(self.session)

    def serve_again(self):
        """The server rebuilt, so a store edit made behind its read cache is seen."""
        from jsk.adapters.mcp import server, session

        self.session = session.Session(root=self.root)
        self.server = server.build(self.session)


@unittest.skipUnless(HAS_MCP, "the mcp package is not installed")
class Registered(Career):
    def test_the_four_tools_are_registered(self):
        import asyncio

        async def listed():
            from mcp.shared.memory import create_connected_server_and_client_session as connect

            async with connect(self.server._mcp_server) as client:
                return (await client.list_tools()).tools
        names = {t.name for t in asyncio.run(listed())}
        self.assertLessEqual(set(FOUR), names)


@unittest.skipUnless(HAS_MCP, "the mcp package is not installed")
class Check(Career):
    def test_a_clean_workspace_is_ok(self):
        said = self.call("career_check")
        self.assertTrue(said["ok"], said)
        self.assertEqual(said["exit"], 0)
        self.assertEqual(fails(said), [])
        self.assertTrue(said["output"].strip())

    def test_a_planted_fail_is_not_ok_and_carries_its_fix(self):
        # A citation to a metric that does not exist: the `dangling` rule.
        edit_career(self, self.root, "j:cites k:met_team ;", "j:cites k:met_teem ;")
        self.serve_again()
        said = self.call("career_check")
        self.assertFalse(said["ok"], said)
        self.assertEqual(said["exit"], 1)
        [dangling] = [f for f in fails(said) if "k:met_teem" in f["text"]]
        self.assertIn("did you mean k:met_team?", dangling["fix"])
        # The gate's own words are returned whole, not summarised.
        self.assertIn("k:met_teem", said["output"])


@unittest.skipUnless(HAS_MCP, "the mcp package is not installed")
class Pack(Career):
    def test_it_returns_a_changeset_career_preview_accepts_and_writes_nothing(self):
        before = storekit.kb_text(self.root)
        said = self.call("career_pack", pack="capabilities")
        self.assertTrue(said["ok"], said)
        self.assertTrue(said["changeset"].startswith("@prefix j:"), said["changeset"][:80])
        self.assertIn("c:system-design a j:Capability", said["changeset"])
        previewed = self.call("career_preview", changeset=said["changeset"])
        self.assertTrue(previewed["ok"], previewed)
        self.assertEqual(storekit.kb_text(self.root), before)

    def test_a_record_holding_the_whole_pack_gets_a_note_and_no_changeset(self):
        said = self.call("career_pack", pack="capabilities")
        applied = self.call("career_apply", changeset=said["changeset"])
        self.assertTrue(applied["ok"], applied)
        again = self.call("career_pack", pack="capabilities")
        self.assertTrue(again["ok"], again)
        self.assertIsNone(again["changeset"])
        self.assertIn("nothing to add", " ".join(f["text"] for f in again["findings"]))

    def test_what_the_pack_skipped_is_returned_as_notes(self):
        edit_career(self, self.root, "c:healthcare a j:Domain .",
                    "c:healthcare a j:Domain .\nc:mentoring a j:Domain .")
        self.serve_again()
        said = self.call("career_pack", pack="capabilities")
        self.assertTrue(said["ok"], said)
        self.assertIn("skipped  c:mentoring", said["notes"])
        self.assertNotIn("skipped  c:mentoring", said["changeset"])


@unittest.skipUnless(HAS_MCP, "the mcp package is not installed")
class Merge(Career):
    def test_two_concepts_come_back_as_a_changeset_career_preview_accepts(self):
        edit_career(self, self.root, VOCAB, VOCAB + '\nc:people-management a j:Capability ; '
                    'j:former "line management" .')
        self.serve_again()
        before = storekit.kb_text(self.root)
        said = self.call("career_merge", concept="c:team-leadership", into="c:people-management")
        self.assertTrue(said["ok"], said)
        self.assertIn("c:people-management", said["changeset"])
        self.assertTrue(self.call("career_preview", changeset=said["changeset"])["ok"])
        # The bullets whose claim moved are the re-confirm list, said on stderr by the verb.
        self.assertIn("re-confirm", said["notes"])
        self.assertEqual(storekit.kb_text(self.root), before)

    def test_an_unknown_concept_is_a_fail_and_no_changeset(self):
        said = self.call("career_merge", concept="c:no-such-thing", into="c:team-leadership")
        self.assertFalse(said["ok"], said)
        self.assertNotIn("changeset", said)
        self.assertIn("c:no-such-thing is not in the record", said["output"])
        self.assertTrue(fails(said))


@unittest.skipUnless(HAS_MCP, "the mcp package is not installed")
class Drop(Served):
    """The claims fixture: contoso-platform is made from files and unsent."""

    def test_a_dry_run_changes_neither_the_store_nor_a_file(self):
        before = snapshot(self.root)
        said = self.call("app_drop", app=FILE_MADE, dry_run=True)
        self.assertTrue(said["ok"], said)
        self.assertIn("dry run: nothing was written or moved", said["output"])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((Path(self.root) / "dropped").exists())

    def test_a_drop_moves_the_folder_under_dropped_and_removes_its_graphs(self):
        root = Path(self.root)
        files = sorted(p.name for p in (root / "applications" / FILE_MADE).iterdir())
        said = self.call("app_drop", app=FILE_MADE, reason="role filled before I applied")
        self.assertTrue(said["ok"], said)
        self.assertEqual(said["exit"], 0)
        self.assertFalse((root / "applications" / FILE_MADE).exists())
        aside = root / "dropped" / FILE_MADE
        self.assertEqual(sorted(p.name for p in aside.iterdir()), sorted(files + ["DROPPED.txt"]))
        self.assertIn("reason    role filled before I applied",
                      (aside / "DROPPED.txt").read_text(encoding="utf-8"))
        self.assertFalse(any(name.startswith(f"applications/{FILE_MADE}/")
                             for name in appkit.graphs(root)))

    def test_a_frozen_application_is_refused_naming_app_event_and_nothing_changes(self):
        root = Path(self.root)
        posting = appkit.text(root, f"applications/{FILE_MADE}/posting")
        shutil.copytree(root / "applications" / FILE_MADE, root / "applications" / "acme-sent")
        appkit.put(root, "applications/acme-sent/posting", posting, prefixes=False)
        appkit.put(root, "applications/acme-sent/application",
                   'k:app_acme_sent j:posting k:post_contoso_platform ; '
                   'j:submitted "2026-09-10"^^xsd:date ; j:channel "company site" .\n')
        self.serve_again_over(root)
        before = snapshot(root)
        said = self.call("app_drop", app="acme-sent")
        self.assertFalse(said["ok"], said)
        self.assertEqual(said["exit"], 1)
        [frozen] = fails(said)
        self.assertIn("applications/acme-sent is frozen", frozen["text"])
        self.assertIn("app_event", frozen["fix"])
        self.assertEqual(snapshot(root), before)
        self.assertFalse((root / "dropped").exists())

    def serve_again_over(self, root):
        from jsk.adapters.mcp import server, session

        self.server = server.build(session.Session(root=str(root)))

    def setUp(self):
        from jsk.adapters.mcp import server, session

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", short=careerkit.short())
        clock = mock.patch.object(session, "today", return_value=TODAY)
        clock.start()
        self.addCleanup(clock.stop)
        self.session = session.Session(root=self.root)
        self.server = server.build(self.session)


@unittest.skipUnless(HAS_MCP, "the mcp package is not installed")
class Unloaded(Served):
    """A workspace still laid out as files - career/kb.ttl, no career/store/ - is refused by
    every one of the four with the one fix that imports it, and nothing is made."""

    def setUp(self):
        from jsk.adapters.mcp import server, session

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(Path(__file__).parent / "match_fixtures", self.root,
                        dirs_exist_ok=True)
        self.server = server.build(session.Session(root=str(self.root)))

    def test_each_is_refused_naming_kb_load_and_no_store_is_made(self):
        for tool, args in (("career_check", {}),
                           ("career_pack", {"pack": "capabilities"}),
                           ("career_merge", {"concept": "c:a", "into": "c:b"}),
                           ("app_drop", {"app": "anything"})):
            with self.subTest(tool=tool):
                said = self.call(tool, **args)
                self.assertFalse(said["ok"], said)
                [finding] = said["findings"]
                self.assertIn("the career is still career/kb.ttl", finding["text"])
                self.assertIn("jsk kb load .", finding["fix"])
        self.assertFalse((self.root / "career" / "store").exists())


if __name__ == "__main__":
    unittest.main()
