"""`jsk kb export --urs`: a draft resume.json out of career/kb.ttl, ids and all.

The record is where hand transcription went wrong - a number copied from an old version,
a confirmed status on a bullet the career holds as inferred, a bullet under the wrong
employer. Export writes those parts from the career itself, so the draft passes the
record gate and the claims gate as it comes out; the author retunes words and the view.
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk import cli
from jsk.gates import claims, validate_urs
from jsk.graph import export
from jsk.graph import store as S

FIXTURES = Path(__file__).parent / "claims_fixtures"
TODAY = datetime.date(2026, 9, 25)
STORE = None


def store():
    global STORE
    if STORE is None:
        STORE = S.load(FIXTURES)
    return STORE


def achievements(doc):
    return {a["id"]: (p["id"], a) for p in doc["projects"] for a in p["achievements"]}


class Draft(unittest.TestCase):
    def setUp(self):
        self.doc = export.urs(store(), today=TODAY)

    def test_the_draft_passes_the_record_gate(self):
        rep = validate_urs.check_doc(self.doc)
        self.assertEqual(rep.fails, [])

    def test_the_draft_passes_the_claims_gate(self):
        rep = claims.check(self.doc, store(), today=TODAY)
        self.assertEqual(rep.fails, [])

    def test_the_draft_renders_each_bullet_under_its_employer(self):
        from jsk.urs.resolve import build

        doc = build(self.doc, "view_draft")
        experience = next(s for s in doc["sections"] if s["heading"] == "Professional Experience")
        meridian = next(e for e in experience["entries"] if e["org_line"] == "Meridian Health")
        self.assertEqual(meridian["bullets"][:2], [
            "Cut p95 event latency from 5 s to 400 ms on AKS with Kafka.",
            "Led a team of 6 engineers."])
        self.assertIn("withheld bullet ach_data_ingestion - provenance 'inferred' is below "
                      "the view floor", doc["warnings"])

    def test_provenance_is_the_careers_exactly(self):
        got = achievements(self.doc)
        self.assertEqual(got["ach_events_latency"][1]["provenance"], {"status": "confirmed"})
        self.assertEqual(got["ach_data_ingestion"][1]["provenance"], {"status": "inferred"})

    def test_a_bullet_sits_under_its_project_and_its_project_under_its_employer(self):
        got = achievements(self.doc)
        self.assertEqual(got["ach_events_team"][0], "prj_events")
        eng = {e["id"]: e for e in self.doc["engagements"]}
        self.assertEqual(eng["eng_meridian"]["organization"], "org_meridian")
        self.assertEqual(eng["eng_meridian"]["projects"], ["prj_events", "prj_identity"])
        self.assertEqual([p["id"] for p in eng["eng_meridian"]["positions"]],
                         ["pos_meridian_lead", "pos_meridian_engineer"])
        projects = {p["id"]: p for p in self.doc["projects"]}
        self.assertEqual(projects["prj_identity"]["engagement"], "eng_meridian")

    def test_an_engagement_spans_its_roles_and_takes_their_kind(self):
        eng = {e["id"]: e for e in self.doc["engagements"]}
        self.assertEqual(eng["eng_meridian"]["period"], {
            "start": {"value": "2021-09", "precision": "month"},
            "end": {"value": "2026-06", "precision": "month"}, "state": "ended"})
        self.assertEqual(eng["eng_lakeside"]["kind"], "contract")
        self.assertEqual(eng["eng_meridian"]["kind"], "employment")

    def test_bullets_keep_the_careers_order(self):
        projects = {p["id"]: p for p in self.doc["projects"]}
        self.assertEqual([a["id"] for a in projects["prj_events"]["achievements"]],
                         ["ach_events_latency", "ach_events_team", "ach_events_terraform"])

    def test_a_metric_is_its_current_version_only(self):
        a = achievements(self.doc)["ach_events_latency"][1]
        self.assertEqual(a["metrics"], [{
            "id": "met_latency", "subject": "p95 event latency",
            "baseline": {"value": 5}, "quantity": {"value": 400},
            "confidence": "measured"}])

    def test_a_bullet_citing_nothing_carries_no_metrics(self):
        a = achievements(self.doc)["ach_events_terraform"][1]
        self.assertEqual(a["metrics"], [])

    def test_the_header_education_and_skills_come_across(self):
        self.assertEqual(self.doc["person"]["name"], {"full": "Test Person"})
        self.assertEqual(self.doc["person"]["headline"], "Platform Engineer")
        self.assertEqual(self.doc["education"][0]["id"], "edu_bsc")
        self.assertEqual(self.doc["education"][0]["period"]["state"], "ended")
        self.assertEqual(self.doc["education"][0]["provenance"], {"status": "confirmed"})
        skill = {s["id"]: s for s in self.doc["skills"]}["skill_kubernetes"]
        self.assertEqual(skill, {"id": "skill_kubernetes", "name": "Kubernetes",
                                 "category": "Platforms", "aliases": ["AKS", "K8s"]})

    def test_one_view_selects_everything_exported_in_order(self):
        (view,) = self.doc["views"]
        self.assertEqual(view["provenance_floor"], "confirmed")
        refs = [i["ref"] for i in view["include"] if i["ref"].startswith("eng_")]
        self.assertEqual(refs, ["eng_meridian", "eng_harbour", "eng_lakeside", "eng_pixel"])
        by_ref = {i["ref"]: i for i in view["include"]}
        self.assertEqual(by_ref["prj_events"]["achievements"],
                         ["ach_events_latency", "ach_events_team", "ach_events_terraform"])

    def test_only_organisations_an_exported_role_names_come_across(self):
        self.assertEqual(sorted(o["id"] for o in self.doc["organizations"]),
                         ["org_harbour", "org_lakeside", "org_meridian", "org_pixel"])


class Select(unittest.TestCase):
    def test_a_project_brings_its_bullets_its_employer_and_every_role_there(self):
        doc = export.urs(store(), select=["prj_identity"], today=TODAY)
        self.assertEqual([p["id"] for p in doc["projects"]], ["prj_identity"])
        self.assertEqual(sorted(achievements(doc)), ["ach_identity_events", "ach_identity_sso"])
        (eng,) = doc["engagements"]
        self.assertEqual(eng["projects"], ["prj_identity"])
        self.assertEqual(len(eng["positions"]), 2)
        self.assertEqual([o["id"] for o in doc["organizations"]], ["org_meridian"])
        self.assertEqual(claims.check(doc, store(), today=TODAY).fails, [])
        self.assertEqual(validate_urs.check_doc(doc).fails, [])

    def test_a_bullet_brings_only_itself(self):
        doc = export.urs(store(), select=["ach_events_team"], today=TODAY)
        self.assertEqual(sorted(achievements(doc)), ["ach_events_team"])

    def test_bullets_and_their_project_together_are_the_bullets(self):
        doc = export.urs(store(), select=["prj_events", "ach_events_latency"], today=TODAY)
        self.assertEqual(sorted(achievements(doc)), ["ach_events_latency"])

    def test_a_role_brings_itself_with_no_projects(self):
        doc = export.urs(store(), select=["pos_pixel_developer", "prj_events"], today=TODAY)
        self.assertEqual([e["id"] for e in doc["engagements"]], ["eng_meridian", "eng_pixel"])
        self.assertEqual({e["id"]: e["projects"] for e in doc["engagements"]}["eng_pixel"], [])

    def test_the_rest_of_the_career_comes_across_whole(self):
        doc = export.urs(store(), select=["ach_events_team"], today=TODAY)
        self.assertEqual(len(doc["skills"]), 2)
        self.assertEqual(len(doc["education"]), 1)

    def test_an_id_not_in_the_career_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            export.urs(store(), select=["prj_evnts"], today=TODAY)
        self.assertIn("prj_evnts", str(caught.exception))
        self.assertIn("prj_events", caught.exception.fix)

    def test_an_id_that_selects_nothing_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            export.urs(store(), select=["met_latency"], today=TODAY)
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
        shutil.copytree(FIXTURES / "career", os.path.join(self.root, "career"))
        path = os.path.join(self.root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        start = text.index("k:ach_events_terraform")
        end = text.index("k:prj_identity")
        Path(path).write_bytes((text[:start] + RETIRED.strip() + "\n\n" + text[end:]).encode())
        self.store = S.load(self.root)

    def test_a_retired_bullet_is_left_out(self):
        doc = export.urs(self.store, today=TODAY)
        self.assertNotIn("ach_events_terraform", achievements(doc))

    def test_selecting_a_retired_bullet_is_refused(self):
        with self.assertRaises(export.ExportError) as caught:
            export.urs(self.store, select=["ach_events_terraform"], today=TODAY)
        self.assertIn("retired", str(caught.exception))


class Replaced(unittest.TestCase):
    def test_a_metric_with_no_current_version_is_left_off_so_its_number_fails(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(root, "career"))
        path = os.path.join(root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        old = "k:met_team.v1 j:of k:met_team ; j:value 6 ;"
        self.assertIn(old, text)
        Path(path).write_bytes(text.replace(
            old, old + ' j:validUntil "2026-01-01"^^xsd:date ;').encode())
        doc = export.urs(S.load(root), today=TODAY)
        self.assertEqual(achievements(doc)["ach_events_team"][1]["metrics"], [])
        self.assertTrue(any("ach_events_team" in f for f in validate_urs.check_doc(doc).fails))


class Command(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(self.root, "career"))

    def kb(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue(), err.getvalue()

    def test_stdout_is_the_record(self):
        code, out, _ = self.kb("export", "--urs")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["urs"], "1.0.0")

    def test_select_takes_several_ids(self):
        code, out, _ = self.kb("export", "--urs", "--select", "prj_identity", "k:ach_events_team")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(achievements(json.loads(out))),
                         ["ach_events_team", "ach_identity_events", "ach_identity_sso"])

    def test_out_writes_the_file_and_says_what_is_next(self):
        path = os.path.join(self.root, "applications", "x", "resume.json")
        code, out, _ = self.kb("export", "--urs", "--select", "prj_identity", "--out", path)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8"))["projects"][0]["id"],
                         "prj_identity")
        self.assertIn("2 bullets", out)
        self.assertIn("jsk validate", out)

    def test_out_never_replaces_a_record(self):
        path = os.path.join(self.root, "resume.json")
        Path(path).write_text("{}", encoding="utf-8")
        code, out, _ = self.kb("export", "--urs", "--out", path)
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)
        self.assertEqual(Path(path).read_text(encoding="utf-8"), "{}")

    def test_an_unknown_id_exits_1_and_writes_nothing(self):
        path = os.path.join(self.root, "resume.json")
        code, out, _ = self.kb("export", "--urs", "--select", "prj_nope", "--out", path)
        self.assertEqual(code, 1)
        self.assertIn("prj_nope", out)
        self.assertFalse(os.path.exists(path))

    def test_select_with_no_ids_is_a_usage_error(self):
        code, _, _ = self.kb("export", "--urs", "--select")
        self.assertEqual(code, 2)

    def test_another_format_is_a_usage_error(self):
        code, _, _ = self.kb("export", "--json-resume")
        self.assertEqual(code, 2)

    def test_a_career_that_fails_is_refused(self):
        path = os.path.join(self.root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        Path(path).write_bytes(text.replace("j:rank 2 ;", "j:rank 0 ;", 1).encode())
        code, out, _ = self.kb("export", "--urs")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)


if __name__ == "__main__":
    unittest.main()
