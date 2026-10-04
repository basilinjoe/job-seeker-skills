"""What reads the record: career_show, career_view, career_query and career_log (the `jsk kb`
verbs they replaced in 6.0), and the career_check tool, whose entry point the Check tests call
(storekit.Workspace.kb, as the tool runs it)."""
import datetime
import json
import re
import unittest
from pathlib import Path

from storekit import Workspace
from test_graph_changeset import PFX
from test_graph_shapes import FIXTURES
from test_kb_write import BRAINDUMP

from jsk.infra.oxigraph import record
from jsk.domain import ontology as O
from jsk.adapters.cli.compose import record as S


class Show(Workspace):
    def test_a_project_is_shown_with_its_bullets_and_the_base_to_draft_against(self):
        code, out = self.show("prj_clinical_events")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("# r2 - op:base 2\n"))
        first = out.index("k:ach_clinical_events_event_latency j:project")
        second = out.index("k:ach_clinical_events_led_migration j:project")
        self.assertLess(out.index("k:prj_clinical_events j:name"), first)
        self.assertLess(first, second)

    def test_a_metric_is_shown_with_its_versions(self):
        code, out = self.show("k:met_event_latency")
        self.assertLess(out.index("k:met_event_latency.v1"), out.index("k:met_event_latency.v2"))

    def test_a_shipped_concept_is_shown_from_the_vocabulary(self):
        code, out = self.show("c:kafka")
        self.assertEqual(code, 0, out)
        self.assertIn("\n# vocabulary\n", out)
        self.assertIn("\n# kb\n", out)                # the career extends it

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.show("prj_clinical_event")
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_clinical_events?", out)


class View(Workspace):
    def test_the_whole_career_in_section_order(self):
        code, out = self.view()
        self.assertEqual(code, 0, out)
        at = [out.index(f"## {s}\n") for s in O.SECTIONS["kb"]]
        self.assertEqual(at, sorted(at))
        self.assertIn("- **Care-site onboarding** `k:prj_site_onboarding` _(inferred)_", out)
        self.assertIn("_(retired 2026-01-10: Too old and too small to earn a line.)_", out)
        self.assertIn("  - **Led a team of 6 engineers", out)
        self.assertIn("    problem: The legacy scheduler", out)

    def test_one_section(self):
        code, out = self.view("skills")
        self.assertIn("## Skills", out)
        self.assertNotIn("## Projects", out)

    def test_it_writes_nothing(self):
        before = self.record()
        self.assertEqual(self.view()[0], 0)
        self.assertEqual(self.record(), before)


class Query(Workspace):
    def test_open_questions(self):
        code, out = self.query("open")
        self.assertIn("| k:q_sites_bullet | k:ach_site_onboarding_sites_one_platform | 2026-09-01 |", out)
        self.assertNotIn("q_team_size", out)          # answered

    def test_a_question_about_several_entries_is_one_row(self):
        self.edit_kb("k:q_sites_confirm j:about k:prj_site_onboarding ;",
                     "k:q_sites_confirm j:about k:prj_clinical_events, k:prj_site_onboarding ;")
        rows = [r for r in json.loads(self.query("open", json=True)[1])
                if r["question"] == "k:q_sites_confirm"]
        self.assertEqual([r["about"] for r in rows],
                         ["k:prj_clinical_events, k:prj_site_onboarding"])

    def test_unconfirmed_entries(self):
        code, out = self.query("unconfirmed", json=True)
        rows = json.loads(out)
        self.assertEqual([r["entry"] for r in rows],
                         ["k:ach_site_onboarding_sites_one_platform", "k:prj_site_onboarding"])

    def test_what_holds_a_concept(self):
        code, out = self.query("holds", "c:azure")
        self.assertIn("| k:prj_clinical_events | c:azure-ai-foundry | 1 | False | tag |", out)

    def test_a_revised_metric_makes_the_application_that_sent_it_stale(self):
        code, _ = self.query("stale")
        self.apply(self.changeset(PFX + "op:set { k:met_team.v1 j:value 7 . }\n"))
        code, out = self.query("stale")
        today = datetime.date.today().isoformat()
        self.assertIn(f"| k:app_acme_platform_engineer | k:met_team.v1 | {today} | k:met_team.v2 |",
                      out)

    def evidence(self, *terms):
        code, out = self.query("evidence", *terms, json=True)
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def test_evidence_reports_the_projects_holding_a_term_s_concept(self):
        rows = self.evidence("event-driven")
        self.assertIn({"term": "event-driven", "found": "c:event-driven-architecture",
                       "entry": "k:prj_clinical_events", "via": "holds c:kafka, 1 hop",
                       "evidence": "tag", "text": ""}, rows)

    def test_evidence_finds_the_text_naming_a_term_but_not_the_vocabulary_s_labels(self):
        rows = [r for r in self.evidence("event-driven") if r["found"] == "text"]
        self.assertEqual([(r["entry"], r["via"], r["evidence"]) for r in rows],
                         [("k:person", "j:positioning", "confirmed")])
        self.assertTrue(rows[0]["text"].startswith("Architect who turns"))

    def test_evidence_names_a_bullet_s_project(self):
        rows = self.evidence("platform")
        self.assertIn("k:ach_site_onboarding_sites_one_platform (k:prj_site_onboarding)",
                      [r["entry"] for r in rows])

    def test_evidence_says_so_when_the_record_holds_nothing(self):
        self.assertEqual(self.evidence("Haskell"),
                         [{"term": "Haskell", "found": "nothing", "entry": "",
                           "via": "no concept, and no text in the record names it",
                           "evidence": "", "text": ""}])

    def test_evidence_matches_an_acronym_in_capitals_only(self):
        def text(term):
            return [r["entry"] for r in self.evidence(term) if r["found"] == "text"]
        self.assertEqual(text("EVENT-DRIVEN"), [])
        self.assertEqual(text("Event-Driven"), ["k:person"])

    def test_evidence_answers_every_term_in_one_call_and_needs_one(self):
        rows = self.evidence("Kafka", "Haskell")
        self.assertEqual({r["term"] for r in rows}, {"Kafka", "Haskell"})
        self.assertEqual(self.query("evidence")[0], 2)

    def test_evidence_shows_fewer_text_hits_when_the_term_names_a_concept(self):
        from jsk.application.record import queries as named
        self.assertLess(named.TEXT_HITS_RESOLVED, named.TEXT_HITS)
        kb = self.path("career/kb.ttl")                 # before it is stored
        kb.write_text(kb.read_text(encoding="utf-8") + "".join(
            f'\nk:ach_intranet_refresh_kafka_{i} j:project k:prj_intranet_refresh ; j:rank {10 + i} ;\n'
            f'    j:text "Kafka note {i}." ; j:provenance j:inferred .\n' for i in range(8)),
            encoding="utf-8")
        rows = [r for r in self.evidence("Kafka") if r["found"] == "text"]
        self.assertEqual(len([r for r in rows if r["entry"]]), named.TEXT_HITS_RESOLVED)
        self.assertIn("more - a narrower term finds them", rows[-1]["via"])

    def test_the_vocabulary_as_one_table(self):
        rows = {r["concept"]: r for r in json.loads(self.query("concepts", json=True)[1])}
        self.assertEqual(rows["c:event-driven-architecture"]["labels"], "EDA, event-driven")
        self.assertEqual(rows["c:kafka"]["counts as"], "c:event-driven-architecture")
        self.assertEqual(rows["c:kafka"]["held"], 1)
        self.assertEqual(rows["c:terraform"]["held"], "")     # shipped, held by no project

    def test_concepts_near_a_term_is_what_it_names_then_the_closest(self):
        code, out = self.query("concepts", "Apache Kafka", json=True)
        self.assertEqual(code, 0, out)
        # Keyed by term, since concepts takes several (2026-09-29-tailor-time Ruling 2).
        rows = [r["concept"] for r in json.loads(out)["Apache Kafka"]]
        self.assertEqual(rows[0], "c:kafka")
        self.assertLessEqual(len(rows), 6)

    def test_concepts_near_several_terms_is_a_table_each(self):
        """The analyst ran `concepts --near` 21 times in a shell loop; one call takes every term."""
        code, out = self.query("concepts", "Apache Kafka", "Terraform")
        self.assertEqual(code, 0, out)
        self.assertEqual([x for x in out.splitlines() if x.startswith("== ")],
                         ["== Apache Kafka", "== Terraform"])
        kafka, terraform = out.split("== Terraform")
        self.assertIn("c:kafka", kafka)
        self.assertIn("c:terraform", terraform)

    def test_bare_lists_the_unlabelled_capabilities_most_held_first(self):
        self.edit_kb('c:data-sovereignty a j:Capability ; j:label "data residency" .',
                     "c:api-design a j:Capability .\nc:data-sovereignty a j:Capability .")
        code, out = self.query("bare", json=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out), [
            {"concept": "c:data-sovereignty", "held": 1, "shown by": 0},
            {"concept": "c:api-design", "held": 0, "shown by": 0}])    # labelled ones absent

    def test_show_bullets_prints_a_project_s_name_and_bullets_only(self):
        full = self.show("prj_site_onboarding")[1]
        code, out = self.show("prj_site_onboarding", bullets=True)
        self.assertEqual(code, 0, out)
        self.assertIn("# k:prj_site_onboarding - Care-site onboarding", out)
        self.assertIn("k:ach_site_onboarding_sites_one_platform j:project", out)
        self.assertNotIn("j:uses", out)
        self.assertLess(len(out), len(full))

    def test_the_person_behind_eligibility(self):
        code, out = self.query("person")
        self.assertEqual(code, 0, out)
        self.assertIn("| location | Sydney, AU | k:person | confirmed |", out)
        self.assertIn("| work mode | hybrid | k:person | confirmed |", out)
        self.assertIn("| work authorization | AU: citizen, held | k:auth_au | confirmed |", out)
        self.assertIn("| ongoing role | Principal Solution Architect at Meridian Health, "
                      "since 2023-07 (employment) | k:pos_meridian_principal | confirmed |", out)

    def test_an_unknown_query(self):
        code, out = self.query("everything")
        self.assertEqual(code, 2)
        self.assertIn("open, unconfirmed, holds, stale", out)


# The clinical event pipeline told again months later, in other words: the same role, the
# same technologies, not one sentence in common.
RETOLD = '''k:prj_care_streaming j:name "Real-time care event streaming" ;
    j:position k:pos_meridian_principal ;
    j:strength 4 ; j:recency 2025 ;
    j:domain c:healthcare ;
    j:uses c:azure-ai-foundry, c:kafka ;
    j:problem "Care-plan changes took minutes to reach each site because the old scheduler batched them." ;
    j:outcome "Schedule changes now reach 15 applications in under a second." ;
    j:provenance j:inferred .

k:ach_care_streaming_one j:project k:prj_care_streaming ; j:rank 1 ;
    j:text "Streamed care-plan events through Kafka so 15 integrated applications saw schedule changes in under a second." ;
    j:provenance j:inferred .

'''


class Similar(Workspace):
    def rows(self, *args):
        code, out = self.query(*args, json=True)
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def retold(self):
        self.edit_kb("k:prj_site_onboarding j:name", RETOLD + "k:prj_site_onboarding j:name")

    def test_similar_finds_a_project_by_the_words_that_describe_it(self):
        rows = self.rows("similar", "moving", "every", "residential", "site", "onto", "templates")
        self.assertEqual(set(rows[0]), {"project", "name", "score", "words", "concepts"})
        self.assertEqual(rows[0]["project"], "k:prj_site_onboarding")
        self.assertEqual(rows[0]["words"], "residential, site, templates")   # templated

    def test_similar_finds_a_project_by_a_concept_its_text_never_names(self):
        """Kafka counts as event-driven architecture; the pipeline's prose says neither."""
        [row] = self.rows("similar", "EDA")
        self.assertEqual((row["project"], row["words"], row["concepts"]),
                         ("k:prj_clinical_events", "", "c:event-driven-architecture"))

    def test_similar_ranks_the_retelling_first(self):
        self.retold()
        rows = self.rows("similar", "streaming care plan changes to every site with Kafka")
        self.assertEqual([r["project"] for r in rows][:2],
                         ["k:prj_care_streaming", "k:prj_clinical_events"])
        self.assertIn("c:kafka", rows[1]["concepts"])

    def test_nothing_similar_is_the_answer(self):
        code, out = self.query("similar", "React Native mobile app")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing similar", out)
        self.assertNotIn("k:prj_", out)
        self.assertEqual(self.query("similar")[0], 2)

    def test_a_retired_project_is_never_a_candidate(self):
        rows = self.rows("similar", "intranet refresh")
        self.assertEqual(rows[0]["name"], "nothing similar")

    def test_duplicates_finds_the_retelling(self):
        self.retold()
        [row] = self.rows("duplicates")
        self.assertEqual(set(row), {"a", "b", "score", "names", "why"})
        self.assertEqual((row["a"], row["b"]), ("k:prj_care_streaming", "k:prj_clinical_events"))
        self.assertIn("concepts c:azure-ai-foundry, c:healthcare, c:kafka", row["why"])
        self.assertIn("same role, 2025 and 2026", row["why"])

    def test_duplicates_reports_nothing_in_the_clean_careers(self):
        """The thresholds' calibration: none of the fixture careers holds a project twice."""
        from appkit import stored_copy

        from jsk.application.record import likeness as named

        tests = Path(__file__).parent
        for root in (FIXTURES, tests / "match_fixtures", tests / "claims_fixtures",
                     tests.parent / "src" / "jsk" / "data" / "example"):
            with self.subTest(root=Path(root).name):
                _, rows = named.duplicates(S.load(stored_copy(root)))
                self.assertEqual([r["names"] for r in rows],
                                 ["nothing looks like one project twice"])


class Check(Workspace):
    def test_a_clean_workspace(self):
        code, out = self.kb("check")
        self.assertEqual(code, 0)
        self.assertIn("record   clean at r2", out)
        # One WARN, and a true one: "40,000 daily ingestion jobs" is in confirmed words but
        # in no metric, so the record gate refuses it in any record that selects the bullet.
        self.assertIn("0 FAIL, 1 WARN", out)
        self.assertIn("'40,000' appears in the text but in no metric", out)

    def test_a_bullet_every_record_would_fail_on_is_warned_of_once(self):
        """A number no metric holds fails the record gate in whatever record selects
        the bullet - found, on the Everforth run, by the author one gate at a time."""
        self.edit_kb("a team of 6 engineers", "a team of 6 engineers across 3 sites")
        code, out = self.kb("check")
        self.assertEqual(code, 0, out)                     # a WARN, not a FAIL
        self.assertIn("a record selecting it fails a gate:", out)
        self.assertIn("'3' appears in the text but in no metric", out)

    def test_a_selection_names_the_bullets_its_draft_already_fails(self):
        # The draft a ranked selection makes warns of a number no metric holds, before
        # the record gate would fail the bullet (this was `jsk kb export`'s stderr).
        from jsk.adapters.cli.compose import selection

        self.edit_kb("a team of 6 engineers", "a team of 6 engineers across 3 sites")
        self.seed()
        made = selection.select(self.root, "resumes/draft", mode="ranked",
                                today=datetime.date.today())
        warns = [text for severity, text, _ in made.findings if severity == "WARN"]
        self.assertTrue(any("the career cannot back" in w and "'3'" in w for w in warns), warns)
        self.assertEqual(made.doc["resume"], 2)
    def test_a_career_written_outside_jsk_fails_its_hash(self):
        """The store holds what jsk wrote, unless something else wrote it: a provenance
        raised there would render as confirmed, and only the log's hash notices."""
        self.seed()
        s = S.load(self.root)
        raised = [q for q in s.graph(record.KB)
                  if q.predicate.value == O.J + "provenance" and q.object.value == O.J + "inferred"]
        self.assertTrue(raised)
        import pyoxigraph as ox
        kb = [ox.Quad(q.subject, q.predicate, ox.NamedNode(O.J + "confirmed"))
              if q == raised[0] else q for q in s.graph(record.KB)]
        record.write_graphs(self.root, {record.KB: kb})         # not through a jsk verb
        code, out = self.kb("check")
        self.assertEqual(code, 1, out)
        self.assertIn("the career is not what its log last recorded - written outside jsk", out)
        self.assertIn(".jsk/backup.trig", out)

    def test_a_fail_exits_1_and_names_the_graph_and_the_entry(self):
        self.edit_kb("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb("check")
        self.assertEqual(code, 1)
        self.assertIn("record   clean at r2", out)
        self.assertIn("did you mean k:met_team?", out)
        self.assertRegex(out, r"FAIL  kb k:ach_\w+ - j:cites k:met_teem")    # no line number

    APP = "applications/acme-platform-engineer"

    def uncover(self):
        advert = self.path(f"{self.APP}/posting.md")
        advert.write_text(advert.read_text(encoding="utf-8").replace(
            "## Benefits", "- Must have Terraform in production.\n\n## Benefits"), encoding="utf-8")

    def test_only_one_application_s_findings(self):
        self.uncover()
        code, out = self.kb("check", "--only", self.APP)
        self.assertEqual(code, 0, out)
        self.assertIn("0 FAIL, 1 WARN", out)
        self.assertIn("Must have Terraform in production", out)
        self.assertNotIn("appears in the text but in no metric", out)     # the career's
        code, out = self.kb("check", "--only", str(self.path(self.APP)))    # a path works too
        self.assertIn("0 FAIL, 1 WARN", out)

    def test_only_still_shows_a_fail_anywhere(self):
        self.edit_kb("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb("check", "--only", self.APP)
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:met_team?", out)

    def test_only_somewhere_clean(self):
        self.uncover()
        code, out = self.kb("check", "--only", "log")
        self.assertEqual(code, 0, out)
        self.assertIn("0 FAIL, 0 WARN", out)


class Log(Workspace):
    def test_the_history_newest_first(self):
        self.assertEqual(self.apply(self.changeset(BRAINDUMP))[0], 0)
        code, out = self.log()
        self.assertEqual(code, 0, out)
        revs = re.findall(r"^r(\d+) ", out, re.M)
        self.assertEqual(revs, ["3", "2", "1"])
        today = datetime.date.today().isoformat()
        self.assertIn(f"r3  {today}  apply    The payments project, from the 24 Sep braindump.",
                      out)
        self.assertRegex(out, r"    minted   c:payments, k:ach_payments_cut_settlement_latency")

    def test_last_n(self):
        self.assertEqual(self.apply(self.changeset(BRAINDUMP))[0], 0)
        code, out = self.log(1)
        self.assertEqual(code, 0, out)
        self.assertEqual(re.findall(r"^r(\d+) ", out, re.M), ["3"])
        for bad in (0, -1):
            with self.subTest(last=bad):
                self.assertEqual(self.log(bad)[0], 2)


if __name__ == "__main__":
    unittest.main()
