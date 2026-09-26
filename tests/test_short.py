"""The short resume.json: what one application chose, and nothing the career holds.

Reading it, finding the workspace it belongs to, and the two ways it can be wrong -
its own shape, and ids the career does not hold."""
import json
import tempfile
import unittest
from pathlib import Path

import careerkit
from jsk.resume import short

OK = {"resume": 2, "bullets": ["ach_events_latency", "ach_identity_sso"]}


class Read(unittest.TestCase):
    def test_a_short_file_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(tmp, short=OK)
            self.assertEqual(short.read(path)["bullets"], OK["bullets"])
            self.assertEqual(Path(short.workspace(path)), Path(root))

    def test_a_legacy_record_points_at_migrate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps({"urs": "1.0.0"}), encoding="utf-8")
            with self.assertRaises(short.ShortError) as err:
                short.read(p)
            # The file named, not a bare `jsk migrate`: the workspace sweep reads only
            # applications/*/resume.json, and this one could be anywhere.
            self.assertIn(f"jsk migrate {p}", err.exception.fix)

    def test_not_json_and_missing_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(short.ShortError):
                short.read(p)
            with self.assertRaises(short.ShortError):
                short.read(Path(tmp, "absent.json"))

    def test_another_version_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps({"resume": 3, "bullets": []}), encoding="utf-8")
            with self.assertRaises(short.ShortError):
                short.read(p)

    def test_outside_a_workspace_is_refused_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps(OK), encoding="utf-8")
            with self.assertRaises(short.ShortError) as err:
                short.workspace(p)
            self.assertIn("career/kb.ttl", err.exception.fix)

    def test_a_workspace_named_career_is_found(self):
        # The real one holds career/career/kb.ttl: the parent of the file's folder's
        # parent is the wrong answer, so the walk up is the only right one.
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(Path(tmp, "career"), short=OK)
            self.assertEqual(Path(short.workspace(path)), Path(root))


class Shape(unittest.TestCase):
    def check(self, **change):
        return short.shape({**OK, **change})

    def test_clean(self):
        self.assertEqual(short.shape(OK), [])
        self.assertEqual(self.check(format="ats-maximal", region="au", pages=2, ats_pages=3,
                                    floor="inferred", roles=["pos_meridian_lead"],
                                    skills=["skill_kubernetes"],
                                    summary={"text": "Platform engineer.", "status": "inferred"}),
                         [])

    def test_unknown_key(self):
        self.assertTrue(any("views" in f for f in self.check(views=[])))

    def test_no_bullets(self):
        self.assertTrue(self.check(bullets=[]))
        self.assertTrue(short.shape({"resume": 2}))

    def test_bad_format_status_and_floor(self):
        self.assertTrue(self.check(format="web"))
        self.assertTrue(self.check(summary={"text": "x", "status": "disputed"}))
        self.assertTrue(self.check(summary={"status": "inferred"}))
        self.assertTrue(self.check(floor="sure"))

    def test_a_region_is_a_two_letter_code(self):
        """Final review: "aus" validated and rendered the default profile - two pages and
        no work-rights line - over the person's AU country that would have been right."""
        self.assertTrue(any("region" in f for f in self.check(region="aus")))
        self.assertTrue(self.check(region="Australia"))
        for good in ("au", "in", "us", "xx"):
            self.assertEqual(self.check(region=good), [], good)

    def test_wrong_types(self):
        self.assertTrue(self.check(pages="2"))
        self.assertTrue(self.check(bullets="ach_events_latency"))
        self.assertTrue(self.check(pages=0))

    def test_wrong_prefix_and_duplicate(self):
        self.assertTrue(self.check(bullets=["prj_events"]))
        self.assertTrue(self.check(roles=["ach_events_latency"]))
        self.assertTrue(self.check(skills=["c:kafka"]))
        self.assertTrue(self.check(bullets=["ach_events_latency", "ach_events_latency"]))


class Example(unittest.TestCase):
    """The workspace jsk doctor renders: a small career and a short file over it."""

    def test_the_example_reads_and_every_id_is_held(self):
        from jsk import paths
        from jsk.graph import store as S

        doc = short.read(paths.EXAMPLE_SHORT)
        self.assertEqual(short.shape(doc), [])
        self.assertEqual(Path(short.workspace(paths.EXAMPLE_SHORT)),
                         Path(paths.EXAMPLE_WORKSPACE))
        self.assertEqual(short.ids(doc, S.load(paths.EXAMPLE_WORKSPACE)), [])

    def test_the_example_career_is_clean(self):
        from jsk import paths
        from jsk.graph import record as R
        from jsk.graph import store as S

        store = S.load(paths.EXAMPLE_WORKSPACE)
        self.assertEqual(store.fails(), [])
        self.assertEqual(R.state(store).kind, "clean")


class Ids(unittest.TestCase):
    def ids(self, doc, edits=()):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = careerkit.workspace(tmp, edits=edits, short=doc)
            return short.ids(doc, careerkit.store(root))

    def test_ids_the_career_holds(self):
        self.assertEqual(self.ids(OK), [])

    def test_an_unknown_id_names_the_near_one(self):
        found = self.ids({**OK, "bullets": ["ach_events_latencyy"]})
        self.assertTrue(any("ach_events_latencyy" in f and "did you mean ach_events_latency"
                            in f for f in found), found)

    def test_an_id_of_another_kind_is_refused(self):
        # Right prefix, wrong thing: a pos_ in the career's text as a skill id would not
        # be caught by the prefix check.
        self.assertTrue(self.ids({**OK, "skills": ["skill_nothing_here"]}))

    def test_a_retired_bullet_is_named_with_its_reason(self):
        # Review Focus 2: retired after the file was written.
        found = self.ids({**OK, "bullets": ["ach_events_terraform"]}, edits=[careerkit.RETIRE])
        self.assertTrue(any("ach_events_terraform" in f and "not true any more" in f
                            for f in found), found)

    def test_a_bullet_whose_role_or_project_is_retired(self):
        """Final review: a retired role passed the gate, and its live bullet then vanished
        from the render without a warning - and from what freeze carried."""
        role = ('    j:seniority j:hands-on-senior ;\n    j:provenance j:confirmed .\n',
                '    j:seniority j:hands-on-senior ;\n'
                '    j:retired "2026-09-01"^^xsd:date ; j:reason "merged into lead" ;\n'
                '    j:provenance j:confirmed .\n')
        found = self.ids({**OK, "bullets": ["ach_identity_sso"]}, edits=[role])
        self.assertTrue(any("ach_identity_sso" in f and "pos_meridian_engineer" in f
                            and "retired" in f for f in found), found)

    def test_a_bullet_whose_project_has_no_role(self):
        edit = ("k:prj_data j:name \"Data\" ;\n    j:position k:pos_lakeside_contractor ;\n",
                "k:prj_data j:name \"Data\" ;\n")
        found = self.ids({**OK, "bullets": ["ach_data_ingestion"]}, edits=[edit])
        self.assertTrue(any("ach_data_ingestion" in f and "role" in f for f in found), found)


class Main(unittest.TestCase):
    """`python -m jsk.resume.short <resume.json>`: the check doctor spawns over the
    example, until the record gate (jsk validate) takes its place."""

    def main(self, *args):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = short.main(["short.py", *map(str, args)])
        return code, out.getvalue()

    def test_the_example_passes(self):
        from jsk import paths

        code, out = self.main(paths.EXAMPLE_SHORT)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)

    def test_a_retired_bullet_fails_naming_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, path = careerkit.workspace(
                tmp, edits=[careerkit.RETIRE],
                short={**OK, "bullets": ["ach_events_terraform"]})
            code, out = self.main(path)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("ach_events_terraform", out)
        self.assertNotIn("PASS", out)

    def test_a_legacy_record_fails_with_the_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps({"urs": "1.0.0"}), encoding="utf-8")
            code, out = self.main(p)
        self.assertEqual(code, 1, out)
        self.assertIn("jsk migrate", out)

    def test_called_wrong_exits_two(self):
        self.assertEqual(self.main()[0], 2)

    def test_it_runs_as_a_module(self):
        # Doctor spawns it: an entry point that only works imported proves nothing there.
        from fixtures import run
        from jsk import paths

        code, out = run("jsk.resume.short", paths.EXAMPLE_SHORT)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)
