"""The claims gate, over the graph simulation's S8 draft: a resume.json joined with the
career it was written from.

tests/claims_fixtures/ is graphsim's career as a workspace - kb.ttl at r1 with a real hash,
the roles behind each project dated as graphsim dated the projects - and a clean record for
the Contoso posting. S8's draft is that record with graphsim's seven defects seeded into it;
each must be flagged, at its check's severity, and nothing else.
"""
import contextlib
import datetime
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.gates import claims
from jsk.graph import store as S

FIXTURES = Path(__file__).parent / "claims_fixtures"
APP = FIXTURES / "applications" / "contoso-platform"
TODAY = datetime.date(2026, 9, 24)
STORE = None


def store():
    global STORE
    if STORE is None:
        STORE = S.load(FIXTURES)
    return STORE


def clean():
    return json.loads((APP / "resume.json").read_text(encoding="utf-8"))


def achievement(doc, ident):
    for p in doc["projects"]:
        for a in p["achievements"]:
            if a["id"] == ident:
                return a
    raise KeyError(ident)


def skill(doc, ident):
    return next(s for s in doc["skills"] if s["id"] == ident)


# graphsim's DRAFT, one defect at a time: (what the draft says, the finding it earns).
def d1(doc):
    """'1 s' is the latency before the March re-measure; EKS was never held."""
    a = achievement(doc, "ach_events_latency")
    a["text"] = "Cut p95 event latency from 5 minutes to under 1 s on EKS with Kafka."
    a["metrics"][0]["baseline"] = {"value": 5, "unit": "min"}
    a["metrics"][0]["quantity"] = {"value": 1, "unit": "s"}


def d2(doc):
    """The former label of Entra ID: held, so nothing to say."""
    achievement(doc, "ach_identity_sso")["text"] = \
        "Migrated 40 applications to Azure AD single sign-on."


def d3(doc):
    """The ingestion bullet is inferred in kb.ttl; the draft calls it confirmed."""
    achievement(doc, "ach_data_ingestion")["provenance"]["status"] = "confirmed"


def d4(doc):
    """Six engineers, not eight."""
    a = achievement(doc, "ach_events_team")
    a["text"] = "Led 8 engineers across two squads."
    a["metrics"][0]["quantity"] = {"value": 8}


def aliases(doc):
    """AKS is held; EKS and .NET Framework are not."""
    skill(doc, "skill_kubernetes")["aliases"] = ["K8s", "AKS", "EKS"]
    skill(doc, "skill_dotnet")["aliases"] = ["C#", ".NET Framework"]


def summary(doc):
    """Eight years, against 61 months of roles behind the projects holding Kubernetes."""
    doc["narratives"][0]["text"] = "Platform engineer with 8 years of Kubernetes."


S8 = (d1, d2, d3, d4, aliases, summary)

EXPECTED = {
    ("number-superseded", "FAIL", "ach_events_latency"),
    ("provenance-raised", "FAIL", "ach_data_ingestion"),
    ("number-untraced", "FAIL", "ach_events_team"),
    ("label-unheld", "WARN", "ach_events_latency"),
    ("alias-unheld", "WARN", "skill_kubernetes"),
    ("alias-unheld", "WARN", "skill_dotnet"),
    ("years-overstated", "WARN", "nar_contoso"),
}


def draft(*defects):
    doc = clean()
    for defect in defects:
        defect(doc)
    return doc


def found(doc, s=None):
    return claims.findings(doc, s or store(), TODAY)


def keys(findings):
    return {(f.check, f.severity, f.focus) for f in findings}


class S8Draft(unittest.TestCase):
    def test_the_clean_record_passes(self):
        self.assertEqual([f.text() for f in found(clean())], [])

    def test_every_seeded_defect_is_flagged_and_nothing_else(self):
        self.assertEqual(keys(found(draft(*S8))), EXPECTED)

    def test_checks_1_to_3_fail_and_4_to_6_warn(self):
        rep = claims.check(draft(*S8), store(), TODAY)
        self.assertEqual(len(rep.fails), 3)
        self.assertEqual(len(rep.warns), 4)

    def test_the_superseded_number_names_the_version_that_replaced_it(self):
        text = [f.text() for f in found(draft(d1)) if f.check == "number-superseded"]
        self.assertEqual(len(text), 1, text)
        self.assertIn("'1' is k:met_latency.v1's number, replaced on 2026-03-01", text[0])
        self.assertIn("current: k:met_latency.v2", text[0])

    def test_a_number_nothing_holds_is_untraced(self):
        [f] = found(draft(d4))
        self.assertIn("'8' is in no current version of what it cites (k:met_team)", f.detail)

    def test_eks_is_named_on_the_bullet_and_kafka_is_not(self):
        text = [f.detail for f in found(draft(d1)) if f.check == "label-unheld"]
        self.assertEqual(len(text), 1, text)
        self.assertIn("'EKS' (c:eks), which k:prj_events does not hold", text[0])

    def test_a_former_label_of_a_held_concept_is_held(self):
        self.assertEqual(found(draft(d2)), [])

    def test_the_years_claim_names_what_the_roles_cover(self):
        [f] = found(draft(summary))
        self.assertIn("claims 8 years of Kubernetes; the roles behind the projects holding it "
                      "cover 5y1m", f.detail)

    def test_the_years_the_roles_cover_pass(self):
        # 61 months: five years is what the record claims, and it is covered.
        self.assertIn("5 years of Kubernetes", clean()["narratives"][0]["text"])
        self.assertEqual(found(clean()), [])


class Absent(unittest.TestCase):
    """Check 1: a bullet written for this application is inferred until confirmed."""

    def invented(self, status):
        doc = clean()
        doc["projects"][0]["achievements"].append({
            "id": "ach_events_invented", "text": "Rebuilt the deploy pipeline.",
            "metrics": [], "provenance": {"status": status}})
        return doc

    def test_a_confirmed_bullet_kb_ttl_does_not_hold_fails(self):
        self.assertEqual(keys(found(self.invented("confirmed"))),
                         {("absent-confirmed", "FAIL", "ach_events_invented")})

    def test_an_inferred_one_is_what_it_should_be(self):
        self.assertEqual(found(self.invented("inferred")), [])

    def test_its_words_are_checked_against_the_project_it_sits_under(self):
        doc = self.invented("inferred")
        doc["projects"][0]["achievements"][-1]["text"] = "Rebuilt the deploy pipeline on EKS."
        self.assertEqual(keys(found(doc)), {("label-unheld", "WARN", "ach_events_invented")})


class Provenance(unittest.TestCase):
    def test_any_id_the_record_and_kb_share_is_checked(self):
        """Not only bullets: an organisation, a role, a qualification - every claim the
        record states with a provenance, joined by id."""
        doc = clean()
        doc["organizations"][0]["provenance"]["status"] = "confirmed"
        self.assertEqual(found(doc), [])
        ws = workspace(self)
        edit(ws, "career/kb.ttl", 'k:org_meridian j:name "Meridian Health" ; '
             'j:relationship j:employer ; j:provenance j:confirmed .',
             'k:org_meridian j:name "Meridian Health" ; '
             'j:relationship j:employer ; j:provenance j:inferred .', relog=True)
        self.assertEqual(keys(found(doc, S.load(ws))),
                         {("provenance-raised", "FAIL", "org_meridian")})

    def test_a_lower_provenance_in_the_record_is_fine(self):
        doc = clean()
        achievement(doc, "ach_identity_sso")["provenance"]["status"] = "inferred"
        self.assertEqual(found(doc), [])


def carried(ident, text, metrics=()):
    """A kb bullet carried into the record under prj_identity."""
    doc = clean()
    doc["projects"][1]["achievements"].append({
        "id": ident, "text": text, "metrics": list(metrics),
        "provenance": {"status": "confirmed"}})
    return doc


REGULATORS = "Published sign-in events to Kafka that 3 state regulators accepted."


class Numbers(unittest.TestCase):
    def regulators(self, provenance="confirmed"):
        """A kb bullet with a number in its own words and no metric behind it."""
        ws = workspace(self)
        edit(ws, "career/kb.ttl", 'j:text "Published sign-in events to Kafka." ;\n'
             '    j:shows c:kafka ;\n    j:provenance j:confirmed .',
             f'j:text "{REGULATORS}" ;\n    j:shows c:kafka ;\n'
             f'    j:provenance j:{provenance} .', relog=True)
        return S.load(ws)

    def test_a_number_in_the_confirmed_kb_bullets_own_words_is_traced(self):
        """The person confirmed those words; carried word for word, nothing is new."""
        s = self.regulators()
        self.assertEqual(s.fails(), [])
        self.assertEqual(found(carried("ach_identity_events", REGULATORS), s), [])

    def test_not_when_the_kb_bullet_is_unconfirmed(self):
        s = self.regulators("inferred")
        doc = carried("ach_identity_events", REGULATORS)
        achievement(doc, "ach_identity_events")["provenance"]["status"] = "inferred"
        self.assertEqual(keys(found(doc, s)),
                         {("number-untraced", "FAIL", "ach_identity_events")})

    def test_a_number_the_kb_bullets_words_do_not_hold_is_still_untraced(self):
        doc = carried("ach_identity_events", REGULATORS.replace("3", "5"))
        self.assertEqual(keys(found(doc, self.regulators())),
                         {("number-untraced", "FAIL", "ach_identity_events")})

    def test_a_kb_bullet_traces_only_through_what_kb_ttl_cites(self):
        """Naming another kb metric in the record does not launder a number: 40 is
        met_apps's, and kb.ttl's ach_events_team cites only met_team."""
        doc = clean()
        a = achievement(doc, "ach_events_team")
        a["text"] = "Led a team of 40 engineers."
        self.assertEqual(keys(found(doc)), {("number-untraced", "FAIL", "ach_events_team")})
        a["metrics"].append({"id": "met_apps"})
        [f] = found(doc)
        self.assertEqual((f.check, f.focus), ("number-untraced", "ach_events_team"))
        self.assertIn("(k:met_team)", f.detail)

    def test_a_bullet_kb_ttl_does_not_hold_traces_through_the_metrics_it_names(self):
        doc = clean()
        doc["projects"][1]["achievements"].append({
            "id": "ach_identity_rollout", "text": "Rolled 40 applications onto SSO.",
            "metrics": [{"id": "met_apps"}], "provenance": {"status": "inferred"}})
        self.assertEqual(found(doc), [])

    def test_an_older_versions_number_is_superseded_even_in_the_kb_bullets_words(self):
        """kb text that still states a replaced number is stale; the version says so."""
        ws = workspace(self)
        stale = "Cut p95 event latency from 5 s to 1 s on AKS with Kafka."
        edit(ws, "career/kb.ttl", "from 5 s to 400 ms on AKS", "from 5 s to 1 s on AKS",
             relog=True)
        doc = clean()
        achievement(doc, "ach_events_latency")["text"] = stale
        self.assertEqual(keys(found(doc, S.load(ws))),
                         {("number-superseded", "FAIL", "ach_events_latency")})


GAME = "Grew a Go server to 100,000 players."


class Carried(unittest.TestCase):
    """A kb bullet's id carries its confirmation only onto its own words and project."""

    def test_a_kb_bullet_moved_under_another_project_fails(self):
        doc = clean()
        doc["projects"][0]["achievements"].append({
            "id": "ach_game_players", "text": GAME,
            "metrics": [{"kind": "count", "subject": "players",
                         "quantity": {"value": 100000}}],
            "provenance": {"status": "confirmed"}})
        fails = {k for k in keys(found(doc)) if k[1] == "FAIL"}
        self.assertEqual(fails, {("project-moved", "FAIL", "ach_game_players")})
        [f] = [f for f in found(doc) if f.check == "project-moved"]
        self.assertIn("k:prj_game", f.detail)
        self.assertIn("prj_events", f.detail)

    def test_or_under_another_engagement(self):
        doc = clean()
        doc["engagements"][0]["achievements"].append({
            "id": "ach_game_players", "text": GAME, "metrics": [],
            "provenance": {"status": "confirmed"}})
        self.assertIn(("project-moved", "FAIL", "ach_game_players"), keys(found(doc)))

    def test_under_the_engagement_its_project_belongs_to_it_stays_put(self):
        doc = clean()
        a = doc["projects"][0]["achievements"].pop(1)          # ach_events_team
        doc["engagements"][0]["achievements"].append(a)
        self.assertEqual(found(doc), [])

    def test_words_that_are_not_kbs_warn(self):
        doc = clean()
        achievement(doc, "ach_events_team")["text"] = \
            "Designed the bank's entire payments architecture single-handedly."
        self.assertEqual(keys(found(doc)), {("text-changed", "WARN", "ach_events_team")})

    def test_so_does_a_claim_appended_to_kbs_words(self):
        doc = clean()
        achievement(doc, "ach_events_team")["text"] = (
            "Led a team of 6 engineers and single-handedly designed the bank's entire "
            "payments architecture.")
        self.assertEqual(keys(found(doc)), {("text-changed", "WARN", "ach_events_team")})

    def test_wording_retuned_for_a_posting_does_not(self):
        doc = clean()
        achievement(doc, "ach_identity_sso")["text"] = (
            "Moved 40 internal applications onto Entra ID single sign-on, retiring the "
            "legacy identity providers.")
        self.assertEqual(found(doc), [])


class Labels(unittest.TestCase):
    def test_a_short_label_matches_only_as_written(self):
        """"Go" is the language; "go" is a verb, and "go live" claims nothing."""
        doc = clean()
        achievement(doc, "ach_identity_sso")["text"] = \
            "Moved 40 applications to Entra ID single sign-on before go live."
        self.assertEqual(found(doc), [])
        achievement(doc, "ach_identity_sso")["text"] = \
            "Moved 40 applications to Entra ID single sign-on, in Go."
        self.assertEqual(keys(found(doc)), {("label-unheld", "WARN", "ach_identity_sso")})

    def test_a_longer_label_may_start_a_sentence_in_lower_case(self):
        doc = clean()
        achievement(doc, "ach_identity_sso")["text"] = \
            "Moved 40 applications to Entra ID single sign-on, over kafka."
        self.assertEqual(found(doc), [])        # kafka: identity holds it

    def test_the_longest_label_is_read_first(self):
        doc = clean()
        achievement(doc, "ach_identity_sso")["text"] = \
            "Moved 40 .NET Framework applications to Entra ID single sign-on."
        details = [f.detail for f in found(doc)]
        self.assertEqual(len(details), 1, details)
        self.assertIn("'.NET Framework'", details[0])

    def test_an_alias_that_names_no_concept_is_not_a_claim_this_gate_reads(self):
        doc = clean()
        skill(doc, "skill_kubernetes")["aliases"].append("container orchestration")
        self.assertEqual(found(doc), [])


class Career(unittest.TestCase):
    def test_a_hand_edit_not_yet_adopted_is_refused(self):
        """A provenance raised by hand is exactly what the gate compares against."""
        ws = workspace(self)
        edit(ws, "career/kb.ttl", 'j:shows c:fastapi ;\n    j:provenance j:inferred .',
             'j:shows c:fastapi ;\n    j:provenance j:confirmed .')
        doc = draft(d3)
        self.assertEqual(keys(found(doc, S.load(ws))),
                         {("career-unlogged", "FAIL", "career/kb.ttl")})

    def test_a_career_that_does_not_validate_is_refused(self):
        ws = workspace(self)
        edit(ws, "career/kb.ttl", "j:cites k:met_team ;", "j:cites k:met_teem ;", relog=True)
        [f] = found(clean(), S.load(ws))
        self.assertEqual((f.check, f.severity), ("career-invalid", "FAIL"))


class Command(unittest.TestCase):
    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = claims.main(["claims.py", *map(str, args)])
        return code, out.getvalue()

    def test_a_clean_record_exits_0(self):
        code, out = self.run_main(APP / "resume.json")
        self.assertEqual(code, 0, out)
        self.assertIn("against: career/kb.ttl r1", out)
        self.assertIn("PASS", out)

    def test_the_s8_draft_exits_1_with_every_finding(self):
        ws = workspace(self)
        path = Path(ws) / "applications" / "contoso-platform" / "resume.json"
        path.write_text(json.dumps(draft(*S8)), encoding="utf-8")
        code, out = self.run_main(path)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL 3   WARN 4", out)
        self.assertIn("DO NOT RENDER", out)

    def test_a_record_outside_any_workspace_is_a_call_error(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "resume.json").write_text(json.dumps(clean()), encoding="utf-8")
        code, out = self.run_main(tmp / "resume.json")
        self.assertEqual(code, 2, out)
        self.assertIn("no career/kb.ttl above", out)
        self.assertIn("jsk migrate", out)

    def test_root_names_the_workspace(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "resume.json").write_text(json.dumps(clean()), encoding="utf-8")
        code, out = self.run_main(tmp / "resume.json", "--root", FIXTURES)
        self.assertEqual(code, 0, out)


class ExperienceQuery(unittest.TestCase):
    def test_kb_query_experience_counts_overlaps_once(self):
        from jsk import cli

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "query", "experience", "c:kubernetes", "--json",
                             "--root", str(FIXTURES)])
        self.assertEqual(code, 0, out.getvalue())
        rows = json.loads(out.getvalue())
        self.assertEqual([r["project"] for r in rows[:-1]], ["k:prj_data", "k:prj_events"])
        self.assertEqual(rows[-1]["months"], 61)


def workspace(case):
    root = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, root)
    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
    return root


def edit(root, name, old, new, relog=False):
    """Change a file by hand; `relog` makes log.ttl agree, as if jsk had written it."""
    from jsk.graph import record
    from jsk.graph.io import sha256

    path = Path(root) / name
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    before = sha256(text)
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")
    if relog:
        log = Path(root) / record.LOG
        log.write_text(log.read_text(encoding="utf-8").replace(before, sha256(text)),
                       encoding="utf-8", newline="\n")


if __name__ == "__main__":
    unittest.main()
