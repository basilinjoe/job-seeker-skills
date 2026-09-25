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

    def test_gate_failures_names_a_claims_gate_fail_rather_than_raising(self):
        """It read `.focus` off check()'s strings, so the one case it exists for - a
        draft the claims gate fails - raised AttributeError instead."""
        doc = json.loads(json.dumps(self.doc))
        _, bullet = achievements(doc)["ach_data_ingestion"]      # inferred in kb.ttl
        bullet["provenance"]["status"] = "confirmed"
        lines = export.gate_failures(store(), doc, today=TODAY)
        self.assertTrue(any("ach_data_ingestion" in line for line in lines), lines)

    def test_a_country_with_no_profile_gets_the_default_profile_s_own_id(self):
        """The fallback was "urs:profile:default/1", which no profile declares, so the
        record gate refused it as unresolvable."""
        self.assertEqual(export.region("IN"), "urs:profile:in/1")
        for country in ("US", None):
            doc = json.loads(json.dumps(self.doc))
            doc["views"][0]["region_profile"] = export.region(country)
            self.assertEqual(doc["views"][0]["region_profile"], "urs:profile:xx/1")
            self.assertEqual(validate_urs.check_doc(doc).fails, [], country)

    def test_the_draft_renders_each_bullet_under_its_employer(self):
        from jsk.urs.resolve import build

        doc = build(self.doc, "view_draft")
        experience = next(s for s in doc["sections"] if s["heading"] == "Professional Experience")
        meridian = next(e for e in experience["entries"] if e["org_line"] == "Meridian Health")
        # Read from the roles: the draft carries each project's position now, so the
        # bullets sit under the role they were done in, not in one block after all
        # of them (entry["bullets"] is empty once any project names a role).
        bullets = [b for r in meridian["roles"] for b in r["bullets"]] + meridian["bullets"]
        self.assertEqual(bullets[:2], [
            "Cut p95 event latency from 5 s to 400 ms on AKS with Kafka.",
            "Led a team of 6 engineers."])
        self.assertIn("withheld bullet ach_data_ingestion - provenance 'inferred' is below "
                      "the view floor", doc["warnings"])

    def test_a_project_carries_the_position_it_was_done_in(self):
        """The Experion draft had no `position`, so the renderer put six roles' work
        under the latest title. Export writes kb.ttl's j:position, and only a position
        of the project's own engagement."""
        by_id = {p["id"]: p for p in self.doc["projects"]}
        self.assertEqual(by_id["prj_events"]["position"], "pos_meridian_lead")
        self.assertEqual(by_id["prj_identity"]["position"], "pos_meridian_engineer")
        held = {e["id"]: {q["id"] for q in e["positions"]} for e in self.doc["engagements"]}
        for p in self.doc["projects"]:
            if "position" in p:
                self.assertIn(p["position"], held[p["engagement"]], p["id"])

    def test_the_draft_renders_each_bullet_under_its_role(self):
        from jsk.urs.resolve import build

        plan = build(self.doc, "view_draft")
        experience = next(s for s in plan["sections"] if s["heading"] == "Professional Experience")
        meridian = next(e for e in experience["entries"] if e["org_line"] == "Meridian Health")
        by_role = {r["left"]: r["bullets"] for r in meridian["roles"]}
        lead = next(v for k, v in by_role.items() if "Lead" in k)
        self.assertIn("Led a team of 6 engineers.", lead)

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


class Qualified(unittest.TestCase):
    def setUp(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(root, "career"))
        path = os.path.join(root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        old = "k:met_team.v1 j:of k:met_team ; j:value 6 ;"
        Path(path).write_bytes(text.replace(
            old, old + " j:upper 8 ; j:qualifier j:about ;").encode())
        # Adopted, as a person would: until then the claims gate reports the hand edit
        # and checks nothing else.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["jsk", "kb", "adopt", "--root", root]), 0)
        self.store = S.load(root)
        self.assertEqual([f.text() for f in self.store.fails()], [])

    def test_a_range_is_exported_with_its_written_form(self):
        doc = export.urs(self.store, today=TODAY)
        (m,) = achievements(doc)["ach_events_team"][1]["metrics"]
        self.assertEqual((m["quantity"], m["value"]), ({"value": 6}, "~6-8"))

    def test_either_end_of_a_range_traces_and_nothing_else_does(self):
        doc = export.urs(self.store, today=TODAY)
        a = achievements(doc)["ach_events_team"][1]
        a["text"] = "Led a team of 6-8 engineers."
        self.assertEqual(self.claim_fails(doc), [])
        self.assertEqual(validate_urs.check_doc(doc).fails, [])
        a["text"] = "Led a team of 9 engineers."
        self.assertTrue(any("number-untraced" in f for f in self.claim_fails(doc)))

    def claim_fails(self, doc):
        return claims.check(doc, self.store, today=TODAY).fails


class Workspace(unittest.TestCase):
    """A copy of the fixture career to run `jsk kb` in."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(self.root, "career"))

    def kb(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue(), err.getvalue()


class Command(Workspace):
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


class Aliases(unittest.TestCase):
    """The claims gate warns of an alias no project holds, and export copied every alias
    kb.ttl holds - so the draft shipped the warning, and someone hand-edited it away."""

    def setUp(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(FIXTURES / "career", os.path.join(root, "career"))
        path = os.path.join(root, "career", "kb.ttl")
        text = Path(path).read_text(encoding="utf-8")
        old = 'j:alias "AKS", "K8s" .'
        self.assertIn(old, text)
        Path(path).write_bytes(text.replace(old, 'j:alias "AKS", "EKS", "K8s" .').encode())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["jsk", "kb", "adopt", "--root", root]), 0)
        self.store = S.load(root)

    def test_an_unheld_alias_is_left_out_and_a_held_one_kept(self):
        notes = []
        doc = export.urs(self.store, today=TODAY, notes=notes)
        skill = {s["id"]: s for s in doc["skills"]}["skill_kubernetes"]
        self.assertEqual(skill["aliases"], ["AKS", "K8s"])
        (note,) = notes
        self.assertIn("skill_kubernetes alias 'EKS' left out", note)
        self.assertTrue(note.startswith("NOTE  "))
        found = [f for f in claims.findings(doc, self.store, TODAY) if f.check == "alias-unheld"]
        self.assertEqual(found, [])

    def test_the_rule_is_the_claims_gate_s(self):
        """Put back, the gate warns of exactly the alias export left out."""
        doc = export.urs(self.store, today=TODAY)
        {s["id"]: s for s in doc["skills"]}["skill_kubernetes"]["aliases"].append("EKS")
        found = [f for f in claims.findings(doc, self.store, TODAY) if f.check == "alias-unheld"]
        self.assertEqual([(f.focus, "'EKS'" in f.detail) for f in found],
                         [("skill_kubernetes", True)])


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
        with self.assertRaises(export.ExportError) as caught:
            export.urs(S.load(root), select=["os_widget"], today=TODAY)
        self.assertIn("os_widget is open source (https://github.com/test/widget)",
                      str(caught.exception))
        self.assertIn("contacts carry their github profile", caught.exception.fix)
        self.assertIn("only if the person confirms that wording", caught.exception.fix)
        self.assertIn("drops to inferred", caught.exception.fix)


PFX = """@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix op: <tag:jsk,2026:op#> .
"""


class Refresh(Workspace):
    """`--refresh`: on the ElevenLabs run every change to kb.ttl after exporting cost an
    `rm`, a re-export and the author's view and summary redone by hand - and a confirm was
    hand-patched into resume.json with ad-hoc Python, since re-exporting would wipe them."""

    def setUp(self):
        super().setUp()
        self.path = os.path.join(self.root, "applications", "x", "resume.json")
        code, out, _ = self.kb("export", "--urs", "--select", "prj_events", "prj_data",
                               "--out", self.path)
        self.assertEqual(code, 0, out)
        doc = self.record()
        # What the author wrote: a view retuned, a summary, a key export never writes.
        view = doc["views"][0]
        view["id"] = "view_elevenlabs"
        view["budget"] = {"pages": 1}
        view["format_profile"] = "ats-safe"
        view["skills"] = ["skill_kubernetes"]
        for i in view["include"]:
            if i["ref"] == "prj_events":
                i["achievements"] = ["ach_events_team", "ach_events_terraform",
                                     "ach_events_latency"]
        doc["narratives"] = [{"id": "nar_elevenlabs", "kind": "summary",
                              "text": "Platform engineer who ships event systems.",
                              "provenance": {"status": "inferred"}}]
        view["narrative"] = "nar_elevenlabs"
        doc["availability"] = {"notice_period_days": 30}
        doc["meta"]["lang"] = "en-GB"
        self.authored = json.loads(json.dumps(doc))
        Path(self.path).write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def record(self):
        return json.loads(Path(self.path).read_text(encoding="utf-8"))

    def apply(self, body):
        cs = os.path.join(self.root, "changes.trig")
        Path(cs).write_text(PFX + body, encoding="utf-8")
        code, out, _ = self.kb("apply", cs)
        self.assertEqual(code, 0, out)

    def test_a_confirm_and_a_text_change_come_in_and_what_was_authored_stays(self):
        code, out, _ = self.kb("confirm", "ach_data_ingestion", "--answer",
                               "I built it, from the first commit")
        self.assertEqual(code, 0, out)
        self.apply('op:set { k:ach_events_team j:text "Led a team of 6 platform engineers." . }\n')
        code, out, _ = self.kb("export", "--urs", "--refresh", self.path)
        self.assertEqual(code, 0, out)
        self.assertIn("changed  ach_data_ingestion  inferred -> confirmed", out)
        self.assertIn("changed  ach_events_team  confirmed -> inferred; text changed", out)
        self.assertIn(f"wrote {self.path}: 2 projects, 4 bullets", out)
        doc = self.record()
        got = achievements(doc)
        self.assertEqual(got["ach_data_ingestion"][1]["provenance"], {"status": "confirmed"})
        self.assertEqual(got["ach_events_team"][1]["text"], "Led a team of 6 platform engineers.")
        self.assertEqual(doc["views"], self.authored["views"])
        self.assertEqual(doc["narratives"], self.authored["narratives"])
        self.assertEqual(doc["availability"], {"notice_period_days": 30})
        self.assertEqual(doc["meta"]["lang"], "en-GB")
        self.assertEqual(list(doc), list(self.authored))
        self.assertNotIn("ach_events_latency", out)          # what did not change is quiet

    def test_a_metric_s_new_number_is_named(self):
        self.apply("op:set { k:met_latency.v2 j:value 350 . }\n")
        code, out, _ = self.kb("export", "--urs", "--refresh", self.path)
        self.assertEqual(code, 0, out)
        self.assertIn("changed  ach_events_latency  met_latency 400 -> 350", out)
        # The words still say 400, and the gates say so, as they do for any export.
        self.assertIn("WARN  the draft fails", out)
        (m,) = achievements(self.record())["ach_events_latency"][1]["metrics"]
        self.assertEqual(m["quantity"], {"value": 350})

    def test_a_refresh_with_nothing_changed_changes_nothing(self):
        code, out, _ = self.kb("export", "--urs", "--refresh", self.path)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing the career holds for this record has changed", out)
        doc = self.record()
        self.assertEqual({k: v for k, v in doc.items() if k != "meta"},
                         {k: v for k, v in self.authored.items() if k != "meta"})

    def test_a_retired_bullet_is_dropped_from_its_project_and_the_view(self):
        self.apply('op:retire { k:ach_events_terraform j:reason "Not mine after all." . }\n')
        code, out, _ = self.kb("export", "--urs", "--refresh", self.path)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"DROPPED  ach_events_terraform  retired on \S+ "
                              r"\(Not mine after all\.\)")
        self.assertIn("view     view_elevenlabs  include less ach_events_terraform", out)
        doc = self.record()
        self.assertNotIn("ach_events_terraform", achievements(doc))
        for i in doc["views"][0]["include"]:
            self.assertNotIn("ach_events_terraform", i.get("achievements", []), i)

    def test_select_adds_a_bullet_to_its_project_and_the_view(self):
        code, out, _ = self.kb("export", "--urs", "--refresh", self.path,
                               "--select", "ach_identity_sso")
        self.assertEqual(code, 0, out)
        self.assertIn("added    ach_identity_sso  by --select, under prj_identity; appended to "
                      "view_elevenlabs", out)
        doc = self.record()
        self.assertEqual(achievements(doc)["ach_identity_sso"][0], "prj_identity")
        by_ref = {i["ref"]: i for i in doc["views"][0]["include"]}
        self.assertEqual(by_ref["prj_identity"]["achievements"], ["ach_identity_sso"])
        # A project the record listed keeps its bullets, and the view the author's order.
        self.assertEqual(by_ref["prj_events"]["achievements"],
                         ["ach_events_team", "ach_events_terraform", "ach_events_latency"])
        self.assertEqual(validate_urs.check_doc(doc).fails, [])

    def test_a_project_keeps_the_bullets_the_record_lists_in_its_order(self):
        doc = self.record()
        events = next(p for p in doc["projects"] if p["id"] == "prj_events")
        events["achievements"] = [events["achievements"][2], events["achievements"][0]]
        Path(self.path).write_text(json.dumps(doc), encoding="utf-8")
        code, out, _ = self.kb("export", "--urs", "--refresh", self.path)
        self.assertEqual(code, 0, out)
        events = next(p for p in self.record()["projects"] if p["id"] == "prj_events")
        self.assertEqual([a["id"] for a in events["achievements"]],
                         ["ach_events_terraform", "ach_events_latency"])

    def test_with_out_or_from_match_is_a_usage_error(self):
        other = os.path.join(self.root, "other.json")
        code, _, _ = self.kb("export", "--urs", "--refresh", self.path, "--out", other)
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(other))
        code, _, _ = self.kb("export", "--urs", "--refresh", self.path, "--from-match",
                             os.path.join(self.root, "posting.ttl"))
        self.assertEqual(code, 2)
        self.assertEqual(self.record(), self.authored)

    def test_a_file_that_is_not_a_record_is_refused(self):
        for name, text in (("notes.json", '{"views": []}'), ("broken.json", "{not json")):
            path = os.path.join(self.root, name)
            Path(path).write_text(text, encoding="utf-8")
            code, out, _ = self.kb("export", "--urs", "--refresh", path)
            self.assertEqual(code, 1, name)
            self.assertIn("REFUSED", out)
            self.assertIn("fix:", out)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), text)
        code, out, _ = self.kb("export", "--urs", "--refresh",
                               os.path.join(self.root, "missing.json"))
        self.assertEqual(code, 1)
        self.assertIn("does not exist", out)

    def test_out_over_a_record_points_at_refresh(self):
        code, out, _ = self.kb("export", "--urs", "--out", self.path)
        self.assertEqual(code, 1)
        self.assertIn(f"`jsk kb export --urs --refresh {self.path}`", out)


if __name__ == "__main__":
    unittest.main()
