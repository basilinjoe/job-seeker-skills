"""The short resume an application starts from, out of the career (`jsk kb export` until 6.0;
now tailor.short_file and the resume_select tool).

The short file names ids and settings only - what was chosen - so it cannot copy a
number from an old version or a status the career no longer holds: the render reads both
from the career. (The URS draft `export.urs` wrote went on 2026-09-25; what it checked of
numbers is tests/test_record_gate.py's now.)
"""
import atexit
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import appkit
import storekit

from jsk.adapters.compose import tailor
from jsk.application.tailor import export
from jsk.adapters.compose import record
from jsk.domain.resume import short

FIXTURES = Path(__file__).parent / "claims_fixtures"
STORE = None


def stored(root, text=None):
    """The fixture career, its kb.ttl replaced by `text` when given, in a store at `root`."""
    shutil.copytree(FIXTURES / "career", os.path.join(root, "career"), dirs_exist_ok=True)
    if text is not None:
        Path(root, "career", "kb.ttl").write_bytes(text.encode())
    appkit.seed(root)
    return record.load(root)


def store():
    global STORE
    if STORE is None:
        root = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, root, True)
        STORE = stored(root)
    return STORE


class Chosen(unittest.TestCase):
    """What --select may name, and the refusals - shared by every export."""

    def test_an_id_not_in_the_career_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            tailor.short_file(store(), select=["prj_evnts"])
        self.assertIn("prj_evnts", str(caught.exception))
        self.assertIn("prj_events", caught.exception.fix)

    def test_an_id_that_selects_nothing_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            tailor.short_file(store(), select=["met_latency"])
        self.assertIn("met_latency", str(caught.exception))


RETIRED = """
k:ach_events_terraform j:project k:prj_events ; j:rank 3 ;
    j:text "Wrote the platform's Terraform." ;
    j:shows c:terraform ;
    j:retired "2026-09-01"^^xsd:date ; j:reason "not true any more" ;
    j:provenance j:confirmed .
"""


class Retired(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8")
        start = text.index("k:ach_events_terraform")
        end = text.index("k:prj_identity")
        self.store = stored(self.root, text[:start] + RETIRED.strip() + "\n\n" + text[end:])

    def test_a_retired_bullet_is_left_out(self):
        self.assertNotIn("ach_events_terraform", tailor.short_file(self.store)["bullets"])

    def test_selecting_a_retired_bullet_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            tailor.short_file(self.store, select=["ach_events_terraform"])
        self.assertIn("retired", str(caught.exception))

    def retire(self, iri):
        appkit.put(self.root, "kb", appkit.text(self.root, "kb")
                   + f'\n{iri} j:retired "2026-09-01"^^xsd:date ; j:reason "gone" .\n',
                   prefixes=False)
        self.store = record.load(self.root)

    def test_a_bullet_whose_project_is_retired_is_refused_not_dropped(self):
        """Only live projects are walked, so the bullet had no home and left the file
        with no word said - and a sole pick fell to "the selection holds no bullet"."""
        self.retire("k:prj_identity")
        with self.assertRaises(export.ExportError) as caught:
            tailor.short_file(self.store, select=["ach_events_team", "ach_identity_sso"])
        self.assertIn("ach_identity_sso", str(caught.exception))
        self.assertIn("prj_identity", str(caught.exception))
        self.assertIn("retired", str(caught.exception))

    def test_a_pick_whose_role_is_retired_is_refused(self):
        # The record gate fails a bullet under a retired role; export should not write one.
        self.retire("k:pos_meridian_engineer")
        for pick in ("ach_identity_sso", "prj_identity"):
            with self.subTest(pick), self.assertRaises(export.ExportError) as caught:
                tailor.short_file(self.store, select=[pick])
            self.assertIn("pos_meridian_engineer", str(caught.exception))


class Workspace(unittest.TestCase):
    """A copy of the fixture career to run `jsk kb` in - put into its store at the first
    command, so a test may edit kb.ttl before then."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(self.root, "career"))

class ShortFile(unittest.TestCase):
    """export.short_file: what an application chose, as ids - the career stays in kb.ttl."""

    def test_the_whole_career_is_every_bullet_with_a_role(self):
        doc = tailor.short_file(store())
        self.assertEqual(doc["resume"], 2)
        self.assertEqual(doc["pages"], 2)
        self.assertEqual(doc["bullets"], [
            "ach_events_latency", "ach_events_team", "ach_events_terraform",
            "ach_identity_sso", "ach_identity_events", "ach_portal_frontend",
            "ach_data_ingestion", "ach_game_players"])
        self.assertNotIn("skills", doc)            # absent: every skill, as the career has them
        self.assertNotIn("region", doc)            # the fixture's person names no country
        self.assertEqual(short.shape(doc), [])
        self.assertEqual(short.ids(doc, store()), [])

    def test_select_narrows_to_projects_bullets_and_roles(self):
        doc = tailor.short_file(store(), select=["prj_identity", "ach_events_team",
                                                 "pos_pixel_developer"])
        self.assertEqual(doc["bullets"], ["ach_events_team", "ach_identity_sso",
                                          "ach_identity_events"])
        self.assertEqual(doc["roles"], ["pos_pixel_developer"])

    def test_a_bullet_named_narrows_its_project(self):
        doc = tailor.short_file(store(), select=["prj_events", "ach_events_terraform"])
        self.assertEqual(doc["bullets"], ["ach_events_terraform"])

    def test_the_selection_s_order_and_skills_are_kept(self):
        from jsk.domain import ontology as O
        from jsk.domain.selection.select import Selection

        sel = Selection([O.K + "prj_identity", O.K + "prj_events"],
                        {O.K + "prj_identity": [O.K + "ach_identity_events"],
                         O.K + "prj_events": [O.K + "ach_events_team", O.K + "ach_events_latency"]},
                        [O.K + "skill_kubernetes", O.K + "skill_dotnet"], [])
        doc = tailor.short_file(store(), selection=sel, select=["pos_pixel_developer"])
        self.assertEqual(doc["bullets"], ["ach_identity_events", "ach_events_team",
                                          "ach_events_latency"])
        self.assertEqual(doc["skills"], ["skill_kubernetes", "skill_dotnet"])
        self.assertEqual(doc["roles"], ["pos_pixel_developer"])

    def test_a_country_with_a_profile_names_its_region(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8")
        s = stored(root, text.replace('j:headline "Platform Engineer" ;',
                                      'j:headline "Platform Engineer" ; j:country "AU" ;', 1))
        self.assertEqual(tailor.short_file(s)["region"], "au")

    def test_select_takes_several_ids_in_either_spelling(self):
        doc = tailor.short_file(store(), select=["prj_identity", "k:ach_events_team"])
        self.assertEqual(doc["bullets"],
                         ["ach_events_team", "ach_identity_sso", "ach_identity_events"])

    def test_a_bad_select_is_refused(self):
        with self.assertRaises(export.ExportError):
            tailor.short_file(store(), select=["prj_evnts"])


class Selecting(Workspace):
    """What `jsk kb export` did before 6.0 - draft a short resume from the career, refuse a
    career that fails, warn of a number no metric holds - as the resume_select tool does it
    (compose.selection.select, mode ranked). Its flags - --out, --replace, --urs, --refresh,
    --json-resume, a bare --select - went with the command; test_retired.py pins the refusal."""

    def select(self):
        import datetime

        from jsk.adapters.compose import selection

        if not os.path.isdir(os.path.join(self.root, "career", "store")):
            appkit.seed(self.root)
        return selection.select(self.root, "resumes/draft", mode="ranked",
                                today=datetime.date.today())

    def test_a_ranked_selection_is_the_short_file_of_the_career(self):
        made = self.select()
        self.assertEqual(made.doc["resume"], 2)
        self.assertIn("ach_events_latency", made.doc["bullets"])
        self.assertEqual(made.target, "resumes/draft/resume")

    def test_a_career_that_fails_is_refused_and_nothing_is_written(self):
        path = os.path.join(self.root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        Path(path).write_bytes(text.replace("j:rank 2 ;", "j:rank 0 ;", 1).encode())
        made = self.select()
        self.assertIsNone(made.target)
        self.assertEqual({severity for severity, _, _ in made.findings}, {"FAIL"})
        self.assertIn("a resume would carry it", made.findings[0][1])

    def test_a_number_no_metric_holds_is_a_question_before_anything_is_authored(self):
        """The Everforth author found these one gate at a time, three changesets deep."""
        path = os.path.join(self.root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        Path(path).write_bytes(text.replace("a team of 6 engineers",
                                            "a team of 6 engineers across 3 sites", 1).encode())
        warns = [t for severity, t, _ in self.select().findings if severity == "WARN"]
        self.assertTrue(any("'3'" in w for w in warns), warns)


OPEN_SOURCE = ('k:os_widget j:name "Widget" ; j:url "https://github.com/test/widget" ; '
               'j:role j:maintainer ; j:provenance j:confirmed .\n')


class OpenSource(unittest.TestCase):
    def test_selecting_open_source_names_its_url_and_where_it_can_go(self):
        """On the ElevenLabs run the old refusal ("select the bullets that cite it") sent
        the author to rewrite a confirmed bullet around the repo's URL."""
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(root, "career"))
        path = os.path.join(root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        Path(path).write_bytes(text.replace("# == Open source\n",
                                            "# == Open source\n\n" + OPEN_SOURCE).encode())
        storekit.seed(root)
        with self.assertRaises(export.ExportError) as caught:
            tailor.short_file(record.load(root), select=["os_widget"])
        self.assertIn("os_widget is open source (https://github.com/test/widget)",
                      str(caught.exception))
        self.assertIn("contacts carry their github profile", caught.exception.fix)
        self.assertIn("only if the person confirms that wording", caught.exception.fix)
        self.assertIn("drops to inferred", caught.exception.fix)


if __name__ == "__main__":
    unittest.main()
