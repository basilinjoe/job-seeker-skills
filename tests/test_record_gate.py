"""The record gate: the short resume.json and the career bullets it selects.

It replaced two gates. validate_urs checked a 41KB copy of the career against itself and
claims.py checked the copy against kb.ttl; with no copy there is one question left of a
number - does the career hold it now - and it is asked of the bullet in kb.ttl. The cases
are theirs, carried over: validate_urs's NumeralsMustBeBacked, claims' Numbers, Labels,
S8Draft and MatchAsks, each now a short file over an edited career (tests/careerkit.py).
"""
import contextlib
import datetime
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import careerkit
from jsk.gates import numbers, record
from jsk.graph import ontology as O
from jsk.urs import tex

TODAY = datetime.date(2026, 9, 24)
K = O.K
MERIDIAN = ["ach_events_latency", "ach_events_team", "ach_identity_sso"]
CLEAN_SUMMARY = {"text": "Platform engineer with 5 years of Kubernetes, building event "
                         "platforms that other teams build on.", "status": "confirmed"}

LATENCY = "Cut p95 event latency from 5 s to 400 ms on AKS with Kafka."
TEAM = "Led a team of 6 engineers."
SSO = "Moved 40 applications to Entra ID single sign-on."
TERRAFORM = "Wrote the platform's Terraform."
EVENTS = "Published sign-in events to Kafka."


def short(bullets=MERIDIAN, **keys):
    return {"resume": 2, "bullets": list(bullets), **keys}


def relog(root):
    """log.ttl made to agree with kb.ttl as edited, as if jsk had written it: the gate
    refuses a hand edit it has not been told about, and these edits stand for ones made
    with `jsk kb apply`."""
    from jsk.graph import record as R
    from jsk.graph.io import sha256

    before = sha256((careerkit.FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8"))
    after = sha256(Path(root, "career", "kb.ttl").read_text(encoding="utf-8"))
    log = Path(root) / R.LOG
    log.write_text(log.read_text(encoding="utf-8").replace(before, after),
                   encoding="utf-8", newline="\n")


class GateCase(unittest.TestCase):
    def workspace(self, edits=(), doc=None, logged=True):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        root, path = careerkit.workspace(Path(tmp, "ws"), edits=list(edits),
                                         short=doc or short())
        if logged:
            relog(root)
        return root, path

    def store(self, edits=(), logged=True):
        root, _ = self.workspace(edits, logged=logged)
        return careerkit.store(root)

    def findings(self, doc=None, edits=(), logged=True):
        doc = doc or short()
        root, _ = self.workspace(edits, doc, logged)
        return record.findings(doc, careerkit.store(root), TODAY)

    def reworded(self, old, new):
        return [(f'"{old}"', f'"{new}"')]


class Untraced(GateCase):
    """numbers.untraced over graph bullets: validate_urs's NumeralsMustBeBacked and claims'
    Numbers, asked of kb.ttl's words and the metrics the bullet cites."""

    def faults(self, ident, text=None):
        edits = self.reworded(self.original(ident), text) if text else ()
        return numbers.untraced(self.store(edits), [K + ident], TODAY)

    @staticmethod
    def original(ident):
        return {"ach_events_latency": LATENCY, "ach_events_team": TEAM, "ach_identity_sso": SSO,
                "ach_events_terraform": TERRAFORM, "ach_identity_events": EVENTS,
                "ach_game_players": "Grew a Go server to 100,000 players."}[ident]

    def test_the_elevenlabs_drive_names_both_numbers(self):
        """kb.ttl held six bullets like this one on the ElevenLabs run, citing nothing; the
        author moved 300-400 to 300-800 to fit an unrelated metric."""
        faults = self.faults("ach_events_terraform",
                             "Wrote the Terraform per 300-400 candidate drive.")
        self.assertEqual(faults, [numbers.Fault(K + "ach_events_terraform", ["300", "400"],
                                                [], [])])

    def test_a_number_a_cited_metric_holds_now_is_traced(self):
        self.assertEqual(self.faults("ach_events_team"), [])
        self.assertEqual(self.faults("ach_identity_sso"), [])
        self.assertEqual(self.faults("ach_events_latency"), [])     # 5 is v2's baseline

    def test_a_number_nothing_holds_is_untraced(self):
        [f] = self.faults("ach_events_team", "Led 8 engineers across two squads.")
        self.assertEqual((f.numbers, f.cites), (["8"], [K + "met_team"]))

    def test_a_replaced_versions_number_is_superseded(self):
        [f] = self.faults("ach_events_latency", LATENCY.replace("400 ms", "1 s"))
        self.assertEqual(f.numbers, [])
        self.assertEqual(f.superseded, [{"number": "1", "version": K + "met_latency.v1",
                                         "until": "2026-03-01"}])

    def test_a_bullet_traces_only_through_what_it_cites(self):
        # 40 is met_apps's; ach_events_team cites only met_team.
        [f] = self.faults("ach_events_team", "Led a team of 40 engineers.")
        self.assertEqual(f.numbers, ["40"])

    def test_confirmed_words_carry_no_number_of_their_own(self):
        """claims.py let a confirmed kb bullet's own words trace a number - but that was a
        copy's words checked against the career's. Here the words are the career's, so the
        exemption would pass every confirmed bullet; the record gate refused this one in
        any record that selected it, and so does this."""
        [f] = self.faults("ach_identity_events",
                          "Published sign-in events to Kafka that 3 state regulators accepted.")
        self.assertEqual(f.numbers, ["3"])

    def test_a_percentage_no_metric_holds_is_untraced(self):
        [f] = self.faults("ach_identity_sso", "Moved 40 applications to Entra ID, cutting cost 31%.")
        self.assertEqual(f.numbers, ["31%"])

    def test_designators_years_and_identifiers_are_not_quantities(self):
        for text in ("Led the workstream for ISO 27001 and SOC 2 audits.",
                     "Tuned p95 read latency on S3 and IPv6 endpoints.",
                     "Ran the 2024 platform consolidation."):
            self.assertEqual(self.faults("ach_events_terraform", text), [], text)

    def test_a_scaled_suffix_matches_the_metric(self):
        self.assertEqual(self.faults("ach_game_players", "Grew a Go server to 100k players."), [])

    def test_order_and_unknown_iris(self):
        s = self.store(self.reworded(TEAM, "Led 8 engineers."))
        faults = numbers.untraced(s, [K + "ach_identity_sso", K + "ach_nothing",
                                      K + "ach_events_team"], TODAY)
        self.assertEqual([f.bullet for f in faults], [K + "ach_events_team"])


class Numbers(GateCase):
    def test_the_elevenlabs_bullet_fails_the_gate_naming_both(self):
        doc = short(["ach_events_terraform"])
        fails, _ = self.findings(doc, self.reworded(
            TERRAFORM, "Wrote the Terraform per 300-400 candidate drive."))
        [line] = fails
        self.assertIn("ach_events_terraform", line)
        self.assertIn("'300' and '400'", line)
        self.assertIn("no metric", line)

    def test_a_bullet_the_file_does_not_select_is_not_its_business(self):
        fails, warns = self.findings(short(), self.reworded(TERRAFORM, "Wrote 12 modules."))
        self.assertEqual((fails, warns), ([], []))


class Ids(GateCase):
    def test_a_retired_bullet_fails_with_its_reason(self):
        # Review Focus 2: retired after the file was written.
        fails, _ = self.findings(short(MERIDIAN + ["ach_events_terraform"]), [careerkit.RETIRE])
        [line] = fails
        self.assertIn("ach_events_terraform was retired on 2026-09-01 (not true any more)", line)
        self.assertIn("drop it", line)

    def test_shape_and_unknown_ids_fail(self):
        fails, _ = self.findings({**short(), "views": []})
        self.assertTrue(any("unknown key 'views'" in f for f in fails), fails)
        fails, _ = self.findings(short(["ach_events_latencyy"]))
        self.assertTrue(any("did you mean ach_events_latency" in f for f in fails), fails)


class Career(GateCase):
    def test_a_hand_edit_not_yet_adopted_is_refused(self):
        """A provenance raised by hand in kb.ttl renders as confirmed: the gate refuses a
        career log.ttl does not vouch for, as the claims gate did."""
        fails, _ = self.findings(edits=[("j:shows c:fastapi ;\n    j:provenance j:inferred .",
                                         "j:shows c:fastapi ;\n    j:provenance j:confirmed .")],
                                 logged=False)
        [line] = fails
        self.assertIn("career-unlogged", line)
        self.assertIn("jsk kb adopt", line)

    def test_a_career_that_does_not_validate_is_refused(self):
        fails, _ = self.findings(edits=[("j:cites k:met_team ;", "j:cites k:met_teem ;")])
        [line] = fails
        self.assertIn("career-invalid", line)


class Labels(GateCase):
    def warns(self, text):
        fails, warns = self.findings(edits=self.reworded(SSO, text))
        self.assertEqual(fails, [])
        return warns

    def test_a_short_label_matches_only_as_written(self):
        """"Go" is the language; "go" is a verb, and "go live" claims nothing."""
        self.assertEqual(self.warns(
            "Moved 40 applications to Entra ID single sign-on before go live."), [])
        [w] = self.warns("Moved 40 applications to Entra ID single sign-on, in Go.")
        self.assertIn("label-unheld ach_identity_sso", w)

    def test_a_longer_label_may_start_a_sentence_in_lower_case(self):
        self.assertEqual(self.warns(
            "Moved 40 applications to Entra ID single sign-on, over kafka."), [])

    def test_the_longest_label_is_read_first(self):
        [w] = self.warns("Moved 40 .NET Framework applications to Entra ID single sign-on.")
        self.assertIn("'.NET Framework'", w)


# graphsim's S8 draft, as edits to the career and to the short file: claims' d1, d2, d4
# and summary. d3 (a provenance raised in the record) and the aliases have nothing to be
# written in - the file holds no provenance but the summary's, and no skill aliases.
D1 = ("Cut p95 event latency from 5 s to 400 ms on AKS with Kafka.",
      "Cut p95 event latency from 5 minutes to under 1 s on EKS with Kafka.")
D2 = (SSO, "Migrated 40 applications to Azure AD single sign-on.")
D4 = (TEAM, "Led 8 engineers across two squads.")
EIGHT = {"text": "Platform engineer with 8 years of Kubernetes.", "status": "inferred"}


class S8Draft(GateCase):
    def draft(self, *edits, summary=CLEAN_SUMMARY):
        doc = short(MERIDIAN + ["ach_data_ingestion"], summary=summary)
        return self.findings(doc, [(f'"{a}"', f'"{b}"') for a, b in edits])

    def test_the_clean_file_passes(self):
        self.assertEqual(self.draft(), ([], []))

    def test_every_seeded_defect_is_flagged_and_nothing_else(self):
        fails, warns = self.draft(D1, D2, D4, summary=EIGHT)
        self.assertEqual([f.split(" - ")[0] for f in fails],
                         ["number-superseded ach_events_latency",
                          "number-untraced ach_events_team"])
        self.assertEqual([w.split(" - ")[0] for w in warns],
                         ["label-unheld ach_events_latency", "years-overstated summary"])

    def test_the_superseded_number_names_the_version_that_replaced_it(self):
        [line], _ = self.draft(D1)
        self.assertIn("'1' is k:met_latency.v1's number, replaced on 2026-03-01 "
                      "(current: k:met_latency.v2)", line)

    def test_a_number_nothing_holds_is_untraced(self):
        [line], _ = self.draft(D4)
        self.assertIn("'8' is in no current version of what it cites (k:met_team)", line)

    def test_eks_is_named_on_the_bullet_and_kafka_is_not(self):
        _, [w] = self.draft(D1)
        self.assertIn("'EKS' (c:eks), which k:prj_events does not hold", w)

    def test_a_former_label_of_a_held_concept_is_held(self):
        self.assertEqual(self.draft(D2), ([], []))

    def test_the_years_claim_names_what_the_roles_cover(self):
        _, [w] = self.draft(summary=EIGHT)
        self.assertIn("claims 8 years of Kubernetes; the roles behind the projects holding it "
                      "cover 5y1m", w)

    def test_the_headline_is_read_too(self):
        fails, [w] = self.findings(edits=[('j:headline "Platform Engineer"',
                                           'j:headline "Platform Engineer, 9 years of Kafka"')])
        self.assertTrue(w.startswith("years-overstated headline"), w)

    def test_without_a_summary_the_positioning_is_read(self):
        # It is what renders in the summary's place.
        fails, [w] = self.findings(edits=[(
            'j:headline "Platform Engineer" ;',
            'j:headline "Platform Engineer" ; j:positioning "8 years of Kubernetes." ;')])
        self.assertTrue(w.startswith("years-overstated positioning"), w)


class Brackets(GateCase):
    def test_a_bracket_in_the_summary_or_a_bullet_warns(self):
        doc = short(summary={"text": "Engineer with [N] years on platforms.",
                             "status": "inferred"})
        fails, warns = self.findings(doc, self.reworded(TEAM, "Led a team of 6 [ENGINEERS]."))
        self.assertEqual(fails, [])
        self.assertEqual([w.split(" - ")[0] for w in warns],
                         ["bracket summary", "bracket ach_events_team"])


class MatchAsks(unittest.TestCase):
    """`jsk match` asks round 1 about a selected bullet's number the gate would refuse -
    through numbers.untraced now, not by exporting a record and parsing gate lines."""

    POST = "tag:jsk,2026:id/post_contoso_platform"

    def test_a_number_its_metric_held_once_is_asked_as_replaced(self):
        from jsk.graph import match as M
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        root, _ = careerkit.workspace(tmp, edits=[("from 5 s to 400 ms on AKS",
                                                   "from 5 s to 1 s on AKS")])
        [q] = M.record_faults(careerkit.store(root), self.POST, TODAY, 3)
        self.assertEqual((q["bullet"], q["numbers"]), ("k:ach_events_latency", []))
        self.assertEqual(M.fault_question(q),
                         "'1' in k:ach_events_latency is k:met_latency.v1's number, replaced "
                         "on 2026-03-01 - what is the figure, and where does it come from "
                         "(dashboards, retros, release notes)? Or should the words change?")

    def test_the_fixture_as_shipped_asks_nothing(self):
        from jsk.graph import match as M
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        root, _ = careerkit.workspace(tmp)
        self.assertEqual(M.record_faults(careerkit.store(root), self.POST, TODAY, 3), [])


def run_cli(*args):
    from jsk import cli
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(["jsk", *map(str, args)])
    return code, buf.getvalue()


class Validate(GateCase):
    def test_a_clean_short_file_passes(self):
        _, path = self.workspace()
        code, out = run_cli("validate", path)
        self.assertEqual(code, 0, out)
        self.assertIn("checking: resume.json   against: career/kb.ttl r1", out)
        self.assertIn("FAIL 0   WARN 0", out)
        self.assertIn("PASS - safe to render", out)

    def test_a_failing_one_says_do_not_render(self):
        _, path = self.workspace([careerkit.RETIRE], short(MERIDIAN + ["ach_events_terraform"]))
        code, out = run_cli("validate", path)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL 1   WARN 0", out)
        self.assertIn("  FAIL  bullets: ach_events_terraform was retired", out)
        self.assertIn("DO NOT RENDER", out)

    def test_outside_a_workspace_is_refused_with_the_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "resume.json")
            path.write_text(json.dumps(short()), encoding="utf-8")
            code, out = run_cli("validate", path)
        self.assertEqual(code, 2, out)
        self.assertIn("career/kb.ttl", out)
        self.assertNotIn("Traceback", out)

    def test_a_legacy_record_still_goes_to_the_urs_gate(self):
        # Until Task 8 deletes it: the fixture's own resume.json is a URS record.
        code, out = run_cli("validate", careerkit.FIXTURES / careerkit.APP / "resume.json")
        self.assertIn("urs: ", out)

    def test_strict_counts_a_warn_as_a_fail(self):
        _, path = self.workspace(doc=short(summary={"text": "Engineer [TBD].",
                                                    "status": "inferred"}))
        self.assertEqual(run_cli("validate", path)[0], 0)
        self.assertEqual(run_cli("validate", path, "--strict")[0], 1)


class Ship(GateCase):
    def ship(self, path, *extra, fake=True):
        from test_ship_freeze import fake_compile

        from jsk.urs import render_resume
        out = Path(path).parent / "out"
        patch = (mock.patch.object(render_resume, "compile_pdf", fake_compile()) if fake
                 else contextlib.nullcontext())
        with patch:
            code, text = run_cli("ship", path, "--out", out, *extra)
        return code, text, out

    def heads(self, text):
        return [line[4:].split(":")[0] for line in text.splitlines() if line.startswith("--- ")]

    def test_a_record_gate_fail_stops_before_the_render(self):
        _, path = self.workspace([careerkit.RETIRE], short(MERIDIAN + ["ach_events_terraform"]))
        code, text, out = self.ship(path)
        self.assertEqual(code, 1, text)
        self.assertEqual(self.heads(text), ["record gate", "render gate"], text)
        self.assertIn("the record gate did not pass", text)
        self.assertFalse(out.exists())

    def test_a_clean_file_renders_and_is_gated_with_no_claims_step(self):
        _, path = self.workspace()
        code, text, out = self.ship(path)
        heads = self.heads(text)
        self.assertEqual(heads[:2], ["record gate", "render"], text)
        self.assertNotIn("claims gate", heads)
        self.assertIn("parse gate", heads)
        self.assertIn("prose gate", heads)
        self.assertTrue((out / "Test_Person_Contoso_Resume_ATS.txt").exists())

    def test_view_is_refused_for_a_short_file(self):
        _, path = self.workspace()
        code, text, out = self.ship(path, "--view", "view_x")
        self.assertEqual(code, 2, text)
        self.assertIn("drop --view", text)

    @unittest.skipUnless(tex.available_engine(), "needs a TeX engine to compile")
    def test_a_clean_file_compiles(self):
        _, path = self.workspace()
        code, text, out = self.ship(path, fake=False)
        self.assertTrue((out / "Test_Person_Contoso_Resume.pdf").exists(), text)
        self.assertNotIn("UNVERIFIED - the render", text)


class Gates(GateCase):
    def test_jsk_gates_runs_the_record_gate_and_no_claims_gate(self):
        _, path = self.workspace()
        code, out = run_cli("gates", Path(path).parent)
        heads = [line[4:].split(":")[0] for line in out.splitlines() if line.startswith("--- ")]
        self.assertEqual(heads[0], "record gate", out)
        self.assertNotIn("claims gate", heads)
        self.assertIn("PASS - safe to render", out)


if __name__ == "__main__":
    unittest.main()
