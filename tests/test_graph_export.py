"""`jsk kb export`: the short resume.json an application starts from, out of the career.

The short file names ids and settings only - what was chosen - so it cannot copy a
number from an old version or a status the career no longer holds: the render reads both
from the career. (The URS draft `export.urs` wrote went on 2026-09-25; what it checked of
numbers is tests/test_record_gate.py's now.)
"""
import atexit
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import appkit
import storekit

from jsk import cli
from jsk.graph import export
from jsk.graph import store as S
from jsk.resume import short

FIXTURES = Path(__file__).parent / "claims_fixtures"
STORE = None


def stored(root, text=None):
    """The fixture career, its kb.ttl replaced by `text` when given, in a store at `root`."""
    shutil.copytree(FIXTURES / "career", os.path.join(root, "career"), dirs_exist_ok=True)
    if text is not None:
        Path(root, "career", "kb.ttl").write_bytes(text.encode())
    appkit.seed(root)
    return S.load(root)


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
            export.short_file(store(), select=["prj_evnts"])
        self.assertIn("prj_evnts", str(caught.exception))
        self.assertIn("prj_events", caught.exception.fix)

    def test_an_id_that_selects_nothing_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            export.short_file(store(), select=["met_latency"])
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
        self.assertNotIn("ach_events_terraform", export.short_file(self.store)["bullets"])

    def test_selecting_a_retired_bullet_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            export.short_file(self.store, select=["ach_events_terraform"])
        self.assertIn("retired", str(caught.exception))

    def retire(self, iri):
        appkit.put(self.root, "kb", appkit.text(self.root, "kb")
                   + f'\n{iri} j:retired "2026-09-01"^^xsd:date ; j:reason "gone" .\n',
                   prefixes=False)
        self.store = S.load(self.root)

    def test_a_bullet_whose_project_is_retired_is_refused_not_dropped(self):
        """Only live projects are walked, so the bullet had no home and left the file
        with no word said - and a sole pick fell to "the selection holds no bullet"."""
        self.retire("k:prj_identity")
        with self.assertRaises(export.ExportError) as caught:
            export.short_file(self.store, select=["ach_events_team", "ach_identity_sso"])
        self.assertIn("ach_identity_sso", str(caught.exception))
        self.assertIn("prj_identity", str(caught.exception))
        self.assertIn("retired", str(caught.exception))

    def test_a_pick_whose_role_is_retired_is_refused(self):
        # The record gate fails a bullet under a retired role; export should not write one.
        self.retire("k:pos_meridian_engineer")
        for pick in ("ach_identity_sso", "prj_identity"):
            with self.subTest(pick), self.assertRaises(export.ExportError) as caught:
                export.short_file(self.store, select=[pick])
            self.assertIn("pos_meridian_engineer", str(caught.exception))


class Workspace(unittest.TestCase):
    """A copy of the fixture career to run `jsk kb` in - put into its store at the first
    command, so a test may edit kb.ttl before then."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(self.root, "career"))

    def kb(self, *args):
        if not os.path.isdir(os.path.join(self.root, "career", "store")):
            appkit.seed(self.root)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue(), err.getvalue()


class ShortFile(unittest.TestCase):
    """export.short_file: what an application chose, as ids - the career stays in kb.ttl."""

    def test_the_whole_career_is_every_bullet_with_a_role(self):
        doc = export.short_file(store())
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
        doc = export.short_file(store(), select=["prj_identity", "ach_events_team",
                                                 "pos_pixel_developer"])
        self.assertEqual(doc["bullets"], ["ach_events_team", "ach_identity_sso",
                                          "ach_identity_events"])
        self.assertEqual(doc["roles"], ["pos_pixel_developer"])

    def test_a_bullet_named_narrows_its_project(self):
        doc = export.short_file(store(), select=["prj_events", "ach_events_terraform"])
        self.assertEqual(doc["bullets"], ["ach_events_terraform"])

    def test_the_selection_s_order_and_skills_are_kept(self):
        from jsk.graph import ontology as O
        from jsk.graph.select import Selection

        sel = Selection([O.K + "prj_identity", O.K + "prj_events"],
                        {O.K + "prj_identity": [O.K + "ach_identity_events"],
                         O.K + "prj_events": [O.K + "ach_events_team", O.K + "ach_events_latency"]},
                        [O.K + "skill_kubernetes", O.K + "skill_dotnet"], [])
        doc = export.short_file(store(), selection=sel, select=["pos_pixel_developer"])
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
        self.assertEqual(export.short_file(s)["region"], "au")

    def test_a_bad_select_is_refused(self):
        with self.assertRaises(export.ExportError):
            export.short_file(store(), select=["prj_evnts"])


class Command(Workspace):
    def test_stdout_is_the_short_file(self):
        code, out, _ = self.kb("export")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc["resume"], 2)
        self.assertIn("ach_events_latency", doc["bullets"])

    def test_select_takes_several_ids(self):
        code, out, _ = self.kb("export", "--select", "prj_identity", "k:ach_events_team")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["bullets"],
                         ["ach_events_team", "ach_identity_sso", "ach_identity_events"])

    def test_out_writes_the_short_file_and_says_what_is_next(self):
        path = os.path.join(self.root, "applications", "x", "resume.json")
        code, out, _ = self.kb("export", "--select", "prj_identity", "--out", path)
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8")),
                         {"resume": 2, "pages": 2,
                          "bullets": ["ach_identity_sso", "ach_identity_events"]})
        self.assertIn("2 bullets", out)
        self.assertIn("jsk resume check", out)

    def test_out_lists_each_bullet_chosen_by_its_first_100_characters(self):
        """The author read 42KB of `kb show --bullets` over 16 projects to learn what the
        export then chose; these lines are that survey, one a bullet."""
        path = os.path.join(self.root, "applications", "x", "resume.json")
        code, out, _ = self.kb("export", "--select", "prj_identity", "prj_events", "--out", path)
        self.assertEqual(code, 0, out)
        lines = [line for line in out.splitlines() if " | " in line]
        self.assertEqual([line.split(" | ")[0] for line in lines],
                         json.loads(Path(path).read_text(encoding="utf-8"))["bullets"])
        from jsk.graph import ontology as O
        from jsk.graph import record as R

        text = export.Career(store().graph(R.KB)).get(O.K + "ach_events_latency", "text")
        self.assertIn(f"ach_events_latency | {text[:100]}", lines)
        self.assertTrue(all(len(line.split(" | ", 1)[1]) <= 100 for line in lines))
        after = out.index("wrote ")
        self.assertTrue(all(out.index(line) > after for line in lines))

    def test_out_never_replaces_a_resume(self):
        path = os.path.join(self.root, "resume.json")
        Path(path).write_text("{}", encoding="utf-8")
        code, out, _ = self.kb("export", "--out", path)
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)
        self.assertIn("pass --replace to export it again", out)
        self.assertEqual(Path(path).read_text(encoding="utf-8"), "{}")

    def test_replace_writes_over_it(self):
        """The Arrow author deleted resume.json by hand to export again after a changeset."""
        path = os.path.join(self.root, "resume.json")
        Path(path).write_text("{}", encoding="utf-8")
        code, out, _ = self.kb("export", "--select", "prj_identity", "--out", path, "--replace")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8"))["bullets"],
                         ["ach_identity_sso", "ach_identity_events"])

    def test_replace_without_out_is_a_usage_error(self):
        self.assertEqual(self.kb("export", "--replace")[0], 2)

    def test_an_unknown_id_exits_1_and_writes_nothing(self):
        path = os.path.join(self.root, "resume.json")
        code, out, _ = self.kb("export", "--select", "prj_nope", "--out", path)
        self.assertEqual(code, 1)
        self.assertIn("prj_nope", out)
        self.assertFalse(os.path.exists(path))

    def test_select_with_no_ids_is_a_usage_error(self):
        code, _, _ = self.kb("export", "--select")
        self.assertEqual(code, 2)

    def test_another_format_is_a_usage_error(self):
        code, _, _ = self.kb("export", "--json-resume")
        self.assertEqual(code, 2)

    def test_a_career_that_fails_is_refused(self):
        path = os.path.join(self.root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        Path(path).write_bytes(text.replace("j:rank 2 ;", "j:rank 0 ;", 1).encode())
        code, out, _ = self.kb("export")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)

    def test_a_number_no_metric_holds_is_a_question_before_anything_is_authored(self):
        """The Everforth author found these one gate at a time, three changesets deep."""
        path = os.path.join(self.root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        Path(path).write_bytes(text.replace("a team of 6 engineers",
                                            "a team of 6 engineers across 3 sites", 1).encode())
        dest = os.path.join(self.root, "applications", "x", "resume.json")
        code, out, _ = self.kb("export", "--select", "prj_events", "--out", dest)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN", out)
        self.assertIn("ach_events_team", out)
        self.assertIn("'3'", out)


class Removed(Workspace):
    """`--urs` and `--refresh` went with the copy: a short file holds ids, and the next
    render reads kb.ttl as it stands, so there is nothing to refresh."""

    def test_urs_is_a_usage_error_naming_what_replaced_it(self):
        code, out, _ = self.kb("export", "--urs")
        self.assertEqual(code, 2)
        self.assertIn("--urs", out)
        self.assertIn("short resume.json", out)

    def test_refresh_is_a_usage_error_naming_what_replaced_it(self):
        path = os.path.join(self.root, "resume.json")
        Path(path).write_text('{"urs": "1.0.0"}', encoding="utf-8")
        code, out, _ = self.kb("export", "--refresh", path)
        self.assertEqual(code, 2)
        self.assertIn("--refresh", out)
        self.assertIn("builds from the career as it stands", out)
        self.assertEqual(Path(path).read_text(encoding="utf-8"), '{"urs": "1.0.0"}')



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
            export.short_file(S.load(root), select=["os_widget"])
        self.assertIn("os_widget is open source (https://github.com/test/widget)",
                      str(caught.exception))
        self.assertIn("contacts carry their github profile", caught.exception.fix)
        self.assertIn("only if the person confirms that wording", caught.exception.fix)
        self.assertIn("drops to inferred", caught.exception.fix)


if __name__ == "__main__":
    unittest.main()
