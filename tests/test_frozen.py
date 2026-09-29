"""A sent application's files are refused where they are written, not by each command.

The review of 2026-09-28 found `jsk posting build --replace` deleting a sent application's
gaps.ttl and gaps.md: three commands checked for a sent application, and the fourth forgot.
"""
import os
import tempfile
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from jsk.graph import timeline

PFX = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES)


def application(app, submitted):
    literal = '"false"^^xsd:boolean' if submitted is False else f'"{submitted}"^^xsd:date'
    (app / "application.ttl").write_text(PFX + f"k:app_x j:submitted {literal} .\n",
                                         encoding="utf-8")


class Frozen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Path(self.tmp.name)
        (self.app / "gaps.ttl").write_bytes(b"what was sent\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_sent_application_refuses_a_write_and_a_removal(self):
        application(self.app, "2026-05-01")
        self.assertEqual(timeline.sent_day(self.app), "2026-05-01")
        with self.assertRaises(timeline.Frozen) as cm:
            timeline.write_app_file(self.app, "gaps.ttl", "rebuilt\n")
        self.assertIn("sent on 2026-05-01", str(cm.exception))
        with self.assertRaises(timeline.Frozen):
            timeline.remove_app_file(self.app, "gaps.ttl")
        self.assertEqual((self.app / "gaps.ttl").read_bytes(), b"what was sent\n")

    def test_an_unsent_application_writes_and_removes(self):
        self.assertIsNone(timeline.sent_day(self.app))
        path = timeline.write_app_file(self.app, "gaps.md", "drafted\n")
        self.assertEqual(Path(path).read_text(encoding="utf-8"), "drafted\n")
        self.assertTrue(timeline.remove_app_file(self.app, "gaps.ttl"))
        self.assertFalse(timeline.remove_app_file(self.app, "gaps.ttl"))
        self.assertFalse(os.path.exists(self.app / "gaps.md.tmp"))

    def test_held_back_is_frozen_but_not_sent(self):
        application(self.app, False)
        self.assertIsNone(timeline.sent_day(self.app))
        self.assertTrue(timeline.frozen(self.app))
        timeline.write_app_file(self.app, "gaps.ttl", "rebuilt\n")

    def test_an_application_md_is_frozen_and_says_when_it_was_sent(self):
        """Frozen before the career moved to kb.ttl: as frozen as an application.ttl."""
        (self.app / "application.md").write_text("---\nsubmitted: 2026-04-02\n---\n",
                                                 encoding="utf-8")
        self.assertTrue(timeline.frozen(self.app))
        self.assertEqual(timeline.sent_day(self.app), "2026-04-02")
        with self.assertRaises(timeline.Frozen):
            timeline.write_app_file(self.app, "gaps.ttl", "rebuilt\n")

    def test_a_held_back_application_md_is_frozen_but_not_sent(self):
        (self.app / "application.md").write_text("---\nsubmitted: false\n---\n",
                                                 encoding="utf-8")
        self.assertTrue(timeline.frozen(self.app))
        self.assertIsNone(timeline.sent_day(self.app))

    def test_an_application_md_is_read_as_a_person_saved_it(self):
        """Only its `submitted:` line is read, with no YAML parser: a BOM, CRLF, a quoted
        date and the lines around it must not hide it."""
        for text in ("﻿---\r\ntitle: \"Acme: Platform\"\r\nsubmitted: 2026-04-02\r\n---\r\n",
                     "---\ntype: Application\nsubmitted: \"2026-04-02\"  # sent\n---\n# Timeline\n"):
            with self.subTest(text=text):
                (self.app / "application.md").write_bytes(text.encode("utf-8"))
                self.assertEqual(timeline.sent_day(self.app), "2026-04-02")

    def test_an_application_md_that_never_closes_refuses(self):
        (self.app / "application.md").write_text("---\nsubmitted: 2026-04-02\n",
                                                 encoding="utf-8")
        with self.assertRaises(timeline.Frozen) as cm:
            timeline.write_app_file(self.app, "gaps.ttl", "rebuilt\n")
        self.assertIn("whether it was sent is unknown", str(cm.exception))

    def test_an_application_ttl_that_does_not_parse_refuses(self):
        (self.app / "application.ttl").write_text("not turtle", encoding="utf-8")
        with self.assertRaises(timeline.Frozen) as cm:
            timeline.write_app_file(self.app, "gaps.ttl", "rebuilt\n")
        self.assertIn("whether it was sent is unknown", str(cm.exception))
        self.assertEqual((self.app / "gaps.ttl").read_bytes(), b"what was sent\n")


class StoredFrozen(unittest.TestCase):
    """In a workspace with career/store/, sent is what the application graph says - and
    only that: `jsk kb load` leaves the old .ttl files where they were."""

    APP = "applications/acme-platform-engineer"

    def setUp(self):
        import shutil

        from appkit import seed
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(Path(__file__).parent / "graph_fixtures", self.root, dirs_exist_ok=True)
        seed(self.root)
        self.app = self.root / self.APP

    def test_the_application_graph_says_it_was_sent(self):
        self.assertEqual(timeline.frozen(self.app), f"{self.APP}/application")
        self.assertEqual(timeline.sent_day(self.app), "2026-09-10")

    def test_a_sent_application_refuses_its_posting_and_assessment(self):
        import appkit
        before = appkit.graphs(self.root)
        for kind in ("posting", "gaps"):
            with self.subTest(kind=kind), self.assertRaises(timeline.Frozen) as cm:
                timeline.write_app_graphs(self.app, {kind: None})
            self.assertIn(f"{self.APP}/{kind}: the application was sent on 2026-09-10",
                          str(cm.exception))
        with self.assertRaises(timeline.Frozen):
            timeline.write_app_file(self.app, "gaps.md", "rebuilt\n")
        self.assertEqual(appkit.graphs(self.root).keys(), before.keys())

    def test_with_no_application_graph_a_file_beside_it_freezes_nothing(self):
        import appkit
        appkit.drop(self.root, f"{self.APP}/application")
        application(self.app, "2026-05-01")
        self.assertIsNone(timeline.frozen(self.app))
        self.assertIsNone(timeline.sent_day(self.app))
        self.assertEqual(timeline.write_app_graphs(self.app, {"gaps": None}), [])


if __name__ == "__main__":
    unittest.main()
