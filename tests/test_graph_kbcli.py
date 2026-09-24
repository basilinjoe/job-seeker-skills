"""`jsk kb`, end to end, on a copy of the fixture workspace."""
import contextlib
import datetime
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_graph_changeset import PFX
from test_graph_shapes import FIXTURES

from jsk import cli
from jsk.graph import ontology as O
from jsk.graph import record
from jsk.graph import store as S
from jsk.graph.io import sha256

BRAINDUMP = PFX + """
op:changeset op:base 2 ; op:summary "The payments project, from the 24 Sep braindump." .

op:add {
    k:prj_payments j:name "Payments platform" ; j:position k:pos_meridian_principal ;
        j:strength 4 ; j:recency 2025 ; j:uses c:kafka, c:payments ;
        j:headlineMetric k:met_settlement .
    [] j:project k:prj_payments ; j:rank 1 ;
        j:text "Cut settlement latency from 800 ms to 200 ms." ;
        j:cites k:met_settlement ; j:shows c:kafka .
    [] j:project k:prj_payments ; j:rank 2 ;
        j:text "Moved card payments onto the event backbone." ; j:shows c:payments .
    k:met_settlement j:subject "settlement latency" ; j:unit "ms" ; j:direction j:decrease .
    k:met_settlement.v1 j:of k:met_settlement ; j:baseline 800 ; j:value 200 ;
        j:confidence j:reported .
    c:payments a j:Domain ; j:label "payments" .
}
"""


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root)

    def path(self, name):
        return Path(self.root) / name

    def changeset(self, text, name="changes.trig"):
        self.path(name).write_text(text, encoding="utf-8")
        return str(self.path(name))

    def kb(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue()

    def loaded(self):
        return S.load(self.root)

    def edit_kb(self, old, new, logged=False):
        """Change kb.ttl by hand. `logged`: and make log.ttl agree, as though jsk had
        written it - how a kb.ttl in an older jsk's layout looks."""
        kb = self.path("career/kb.ttl")
        text = kb.read_text(encoding="utf-8")
        self.assertIn(old, text)
        text = text.replace(old, new)
        kb.write_text(text, encoding="utf-8", newline="\n")
        if logged:
            log = self.path("career/log.ttl")
            log.write_text(log.read_text(encoding="utf-8").replace(
                record.last_entry(self.loaded().graph(record.LOG))[1], sha256(text)),
                encoding="utf-8", newline="\n")
        return text

    def old_layout(self):
        return self.edit_kb("# == Metrics\n\n", "# == Metrics\n\n\n", logged=True)


class Apply(Workspace):
    def test_a_braindump_becomes_a_valid_logged_record(self):
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual(record.state(s).kind, "clean")
        self.assertEqual(record.state(s).log_revision, 3)
        for line in ("+k:prj_payments j:name \"Payments platform\" ;",
                     "+k:ach_payments_cut_settlement_latency j:project k:prj_payments ; j:rank 1 ;",
                     "+k:ach_payments_moved_card_payments j:project k:prj_payments ; j:rank 2 ;",
                     "+c:payments a j:Domain ; j:label \"payments\" .",
                     "minted   c:payments, k:ach_payments_cut_settlement_latency",
                     "r3 written: career/kb.ttl and career/log.ttl"):
            self.assertIn(line, out)
        log = self.path("career/log.ttl").read_text(encoding="utf-8")
        self.assertIn('j:summary "The payments project, from the 24 Sep braindump."', log)

    def test_applying_the_same_changeset_twice_changes_nothing_the_second_time(self):
        path = self.changeset(BRAINDUMP.replace("op:base 2 ; ", ""))
        self.assertEqual(self.kb("apply", path)[0], 0)
        # An agent that re-runs an apply it thought failed must not mint every bullet twice:
        # a new bullet with a live bullet's text, under the same project, is that bullet.
        code, out = self.kb("apply", path)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to change", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 3)

    def test_an_old_application_s_fault_does_not_block_the_career(self):
        posting = self.path("applications/acme-platform-engineer/posting.ttl")
        posting.write_text(posting.read_text(encoding="utf-8").replace(
            "Deep, hands-on K8s experience in production", "Ten years of K8s"), encoding="utf-8")
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 0, out)

    def test_a_label_that_clashes_is_a_warning_not_a_refusal(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:add { c:payments a j:Domain ; j:label "Kafka" . }\n'))
        self.assertEqual(code, 0, out)

    def test_both_files_restored_together_are_clean(self):
        kb, log = self.path("career/kb.ttl"), self.path("career/log.ttl")
        old = (kb.read_bytes(), log.read_bytes())
        self.assertEqual(self.kb("apply", self.changeset(BRAINDUMP))[0], 0)
        self.assertEqual(record.state(self.loaded()).log_revision, 3)
        kb.write_bytes(old[0])
        log.write_bytes(old[1])
        self.assertEqual(record.state(self.loaded()).kind, "clean")

    def test_a_dry_run_writes_nothing(self):
        kb = self.path("career/kb.ttl")
        before = (kb.read_bytes(), os.stat(kb).st_mtime_ns)
        code, out = self.kb("apply", self.changeset(BRAINDUMP), "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("+k:prj_payments", out)
        self.assertIn("dry run: r3 not written", out)
        self.assertEqual((kb.read_bytes(), os.stat(kb).st_mtime_ns), before)
        self.assertFalse(self.path(".jsk").exists())

    def test_stdin_is_refused(self):
        code, out = self.kb("apply", "-")
        self.assertEqual(code, 2)
        self.assertIn("stdin is refused", out)

    def test_a_hand_edit_is_adopted_before_anything_is_applied(self):
        kb = self.path("career/kb.ttl")
        kb.write_text(kb.read_text(encoding="utf-8").replace('"1001-5000"', '"5001-10000"'),
                      encoding="utf-8", newline="\n")
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 1)
        self.assertIn("jsk kb adopt", out)

    def test_a_change_that_breaks_the_record_is_refused_whole(self):
        before = self.path("career/kb.ttl").read_bytes()
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:add { k:prj_half j:name "Half a project" . }\n'))
        self.assertEqual(code, 1)
        self.assertIn("j:strength is required", out)
        self.assertEqual(self.path("career/kb.ttl").read_bytes(), before)

    def test_a_refusal_names_every_reason(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:set { k:prj_clinical_events j:provenance j:confirmed ; j:strenght 4 . }\n'))
        self.assertEqual(code, 1)
        self.assertIn("a changeset cannot confirm", out)
        self.assertIn("did you mean j:strength?", out)

    def test_nothing_to_change_writes_nothing(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:set { k:prj_clinical_events j:strength 5 . }\n'))
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))
        self.assertIn("nothing to change", out)

    def test_a_non_canonical_kb_is_formatted_first(self):
        self.old_layout()
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 1)
        self.assertIn("jsk kb fmt", out)

    def test_a_changeset_that_is_not_trig(self):
        code, out = self.kb("apply", self.changeset("x", "changes.ttl"))
        self.assertEqual(code, 2)
        self.assertIn("not a .trig file", out)


ANSWER = "Yes - 42 sites at hand-over, and a quarter each before the platform."


class Confirm(Workspace):
    def test_confirming_answers_the_open_questions_and_logs_the_answer(self):
        code, out = self.kb("confirm", "k:ach_site_onboarding_sites_one_platform",
                            "prj_site_onboarding", "--answer", ANSWER)
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual([f.text() for f in s.findings], [])
        text = self.path("career/kb.ttl").read_text(encoding="utf-8")
        self.assertIn("k:q_sites_bullet j:about k:ach_site_onboarding_sites_one_platform", text)
        self.assertEqual(text.count('j:answered "' + datetime.date.today().isoformat()), 2)
        log = self.path("career/log.ttl").read_text(encoding="utf-8")
        self.assertIn(f'j:answer "{ANSWER}"', log)
        self.assertIn("j:by j:confirm", log)

    def test_an_answer_that_says_nothing_is_refused(self):
        for said in ("yes", "OK.", "confirmed", "", "<answer>", "..."):
            with self.subTest(said=said):
                code, out = self.kb("confirm", "prj_site_onboarding", "--answer", said)
                self.assertEqual(code, 1)
                self.assertIn("is not an answer", out)

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.kb("confirm", "prj_site_onbording", "--answer", ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_site_onboarding?", out)

    def test_an_entry_that_is_not_a_claim(self):
        code, out = self.kb("confirm", "met_sites", "--answer", ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("a Metric is not a claim", out)

    def test_confirming_what_is_confirmed_changes_nothing(self):
        code, out = self.kb("confirm", "prj_clinical_events", "--answer", ANSWER)
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))


class Adopt(Workspace):
    def test_a_hand_edit_is_logged_with_what_it_raised(self):
        self.kb("apply", self.changeset(PFX + 'op:set { k:prj_clinical_events j:strength 4 . }\n'))
        self.edit_kb("j:outcome \"Onboarding fell to two weeks; 42 sites now run on it.\" ;\n"
                     "    j:provenance j:inferred .",
                     "j:outcome \"Onboarding fell to two weeks; 42 sites now run on it.\" ;\n"
                     "    j:provenance j:confirmed .")
        self.edit_kb('"Led a team of 6 engineers', '"Led a team of 8 engineers')
        self.assertEqual(record.state(self.loaded()).kind, "hand-edited")
        code, out = self.kb("adopt")
        self.assertEqual(code, 0, out)
        self.assertIn("raised   k:prj_site_onboarding: inferred -> confirmed", out)
        self.assertIn("raised   k:ach_clinical_events_led_migration: j:text changed while confirmed", out)
        self.assertIn("-    j:provenance j:inferred .", out)      # the diff is from r3
        s = self.loaded()
        self.assertEqual((record.state(s).kind, record.state(s).log_revision), ("clean", 4))
        log = self.path("career/log.ttl").read_text(encoding="utf-8")
        self.assertIn("Raised: k:ach_clinical_events_led_migration: j:text changed while confirmed", log)

    def test_with_no_copy_to_compare_every_confirmed_entry_is_listed(self):
        self.edit_kb('j:size "1001-5000"', 'j:size "5001-10000"')
        code, out = self.kb("adopt")
        self.assertEqual(code, 0, out)
        self.assertIn("raised   k:prj_clinical_events is confirmed", out)
        self.assertIn("No copy of r2 to compare against",
                      self.path("career/log.ttl").read_text(encoding="utf-8"))

    def test_a_torn_write_is_adopted(self):
        self.edit_kb("j:revision 2 .", "j:revision 3 .")
        self.assertEqual(record.state(self.loaded()).kind, "torn")
        code, out = self.kb("adopt")
        self.assertEqual(code, 0, out)
        self.assertEqual(record.state(self.loaded()).kind, "clean")

    def test_comments_are_refused_unless_dropped(self):
        self.edit_kb("# == Metrics\n", "# == Metrics\n# ask about the latency\n")
        code, out = self.kb("adopt")
        self.assertEqual(code, 1)
        self.assertIn("career/kb.ttl:", out)
        self.assertIn("# ask about the latency", out)
        code, out = self.kb("adopt", "--drop-comments")
        self.assertEqual(code, 0, out)
        self.assertNotIn("# ask", self.path("career/kb.ttl").read_text(encoding="utf-8"))

    def test_a_clean_record_has_nothing_to_adopt(self):
        code, out = self.kb("adopt")
        self.assertEqual(code, 0)
        self.assertIn("nothing to adopt", out)


class Fmt(Workspace):
    def test_a_reformat_is_logged_on_its_own_and_keeps_the_day(self):
        self.old_layout()
        code, out = self.kb("fmt")
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual((record.state(s).kind, record.state(s).log_revision), ("clean", 3))
        self.assertIn('j:updated "2026-09-20"^^xsd:date ; j:revision 3 .',
                      self.path("career/kb.ttl").read_text(encoding="utf-8"))
        self.assertIn("j:by j:fmt", self.path("career/log.ttl").read_text(encoding="utf-8"))

    def test_a_canonical_file_is_left_alone(self):
        code, out = self.kb("fmt")
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))
        self.assertIn("already canonical", out)

    def test_a_hand_edit_is_adopted_not_formatted(self):
        self.edit_kb("# == Metrics\n\n", "# == Metrics\n\n\n")
        code, out = self.kb("fmt")
        self.assertEqual(code, 1)
        self.assertIn("jsk kb adopt", out)

    def test_another_record_file_is_rewritten_unlogged(self):
        posting = self.path("applications/acme-platform-engineer/posting.ttl")
        posting.write_text(posting.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
        code, out = self.kb("fmt", str(posting))
        self.assertEqual(code, 0, out)
        self.assertIn("posting.ttl: rewritten", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_the_log_is_not_a_file_to_format(self):
        code, out = self.kb("fmt", str(self.path("career/log.ttl")))
        self.assertEqual(code, 1)
        self.assertIn("written by jsk only", out)


class Show(Workspace):
    def test_a_project_is_shown_with_its_bullets_and_the_base_to_draft_against(self):
        code, out = self.kb("show", "prj_clinical_events")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("# r2 - op:base 2\n"))
        first = out.index("k:ach_clinical_events_event_latency j:project")
        second = out.index("k:ach_clinical_events_led_migration j:project")
        self.assertLess(out.index("k:prj_clinical_events j:name"), first)
        self.assertLess(first, second)

    def test_a_metric_is_shown_with_its_versions(self):
        code, out = self.kb("show", "k:met_event_latency")
        self.assertLess(out.index("k:met_event_latency.v1"), out.index("k:met_event_latency.v2"))

    def test_a_shipped_concept_is_shown_from_the_vocabulary(self):
        code, out = self.kb("show", "c:kafka")
        self.assertEqual(code, 0, out)
        self.assertIn("# vocabulary.ttl", out)
        self.assertIn("# career/kb.ttl", out)       # kb.ttl extends it

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.kb("show", "prj_clinical_event")
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_clinical_events?", out)


class View(Workspace):
    def test_the_whole_career_in_section_order(self):
        code, out = self.kb("view")
        self.assertEqual(code, 0, out)
        at = [out.index(f"## {s}\n") for s in O.SECTIONS["kb"]]
        self.assertEqual(at, sorted(at))
        self.assertIn("- **Care-site onboarding** `k:prj_site_onboarding` _(inferred)_", out)
        self.assertIn("_(retired 2026-01-10: Too old and too small to earn a line.)_", out)
        self.assertIn("  - **Led a team of 6 engineers", out)
        self.assertIn("    problem: The legacy scheduler", out)

    def test_one_section(self):
        code, out = self.kb("view", "--section", "skills")
        self.assertIn("## Skills", out)
        self.assertNotIn("## Projects", out)

    def test_it_writes_nothing(self):
        before = sorted(p.name for p in Path(self.root).rglob("*"))
        self.assertEqual(self.kb("view")[0], 0)
        self.assertEqual(sorted(p.name for p in Path(self.root).rglob("*")), before)


class Query(Workspace):
    def test_open_questions(self):
        code, out = self.kb("query", "open")
        self.assertIn("| k:q_sites_bullet | k:ach_site_onboarding_sites_one_platform | 2026-09-01 |", out)
        self.assertNotIn("q_team_size", out)          # answered

    def test_unconfirmed_entries(self):
        code, out = self.kb("query", "unconfirmed", "--json")
        rows = json.loads(out)
        self.assertEqual([r["entry"] for r in rows],
                         ["k:ach_site_onboarding_sites_one_platform", "k:prj_site_onboarding"])

    def test_what_holds_a_concept(self):
        code, out = self.kb("query", "holds", "c:azure")
        self.assertIn("| k:prj_clinical_events | c:azure-ai-foundry | 1 | False | tag |", out)

    def test_a_revised_metric_makes_the_application_that_sent_it_stale(self):
        code, _ = self.kb("query", "stale")
        self.kb("apply", self.changeset(PFX + "op:set { k:met_team.v1 j:value 7 . }\n"))
        code, out = self.kb("query", "stale")
        today = datetime.date.today().isoformat()
        self.assertIn(f"| k:app_acme_platform_engineer | k:met_team.v1 | {today} | k:met_team.v2 |",
                      out)

    def test_an_unknown_query(self):
        code, out = self.kb("query", "everything")
        self.assertEqual(code, 2)
        self.assertIn("open, unconfirmed, holds, stale", out)


class Check(Workspace):
    def test_a_clean_workspace(self):
        code, out = self.kb("check")
        self.assertEqual(code, 0)
        self.assertIn("record   clean at r2", out)
        self.assertIn("0 FAIL, 0 WARN", out)

    def test_a_fail_exits_1_and_a_hand_edit_is_named(self):
        self.edit_kb("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb("check")
        self.assertEqual(code, 1)
        self.assertIn("record   hand-edited at r2", out)
        self.assertIn("did you mean k:met_team?", out)

    def test_a_file_out_of_layout_is_named(self):
        self.old_layout()
        code, out = self.kb("check")
        self.assertEqual(code, 0)
        self.assertIn("career/kb.ttl - not in the canonical layout", out)


class Dispatch(Workspace):
    def test_help_lists_the_verbs_and_exits_0(self):
        code, out = self.kb("--help")
        self.assertEqual(code, 0)
        self.assertIn("apply <changeset.trig>", out)

    def test_a_verb_s_help(self):
        code, out = self.kb("apply", "--help")
        self.assertEqual(code, 0)
        self.assertIn("--dry-run prints the diff", out)

    def test_an_unknown_verb(self):
        code, out = self.kb("aply")
        self.assertEqual(code, 2)
        self.assertIn("unknown verb: aply", out)

    def test_the_workspace_is_found_from_inside_it(self):
        here = os.getcwd()
        os.chdir(self.path("applications"))
        self.addCleanup(os.chdir, here)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "apply", self.changeset(BRAINDUMP), "--dry-run"])
        self.assertEqual(code, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
