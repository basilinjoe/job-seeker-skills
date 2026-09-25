"""Tier 2: every workspace rule fires, at the right place, on the one edit that breaks it.

Same machinery as tests/test_graph_shapes.py: copy the valid fixture workspace, make one
edit, load, assert the rule names the id at its line with the expected fix.
"""
import unittest

from test_graph_shapes import APPLICATION, KB, POSTING, assert_fires, mutated

from jsk.graph import rules

LOG = "career/log.ttl"

# rule: (file, old text, new text, focus id, the fix contains). old=None appends new.
MUTATIONS = {
    "dangling": (KB, "j:cites k:met_team ;", "j:cites k:met_teem ;",
                 "k:ach_clinical_events_led_migration", "did you mean k:met_team?"),
    "duplicate-id": (POSTING, None, '\nk:met_team j:subject "engineers" .\n', "k:met_team",
                     "keep it in one file"),
    "concept-typed": (KB, "c:healthcare a j:Domain .",
                      'c:healthcare a j:Domain .\nc:graphql j:label "GraphQL" .', "c:graphql",
                      "a j:Technology"),
    "primary-contact": (KB, 'j:primary "priya@example.com"', 'j:primary "priya@example.org"',
                        "k:person", "one of the email"),
    "headline-xor": (KB, "j:headlineMetric k:met_event_latency ;",
                     "j:headlineMetric k:met_event_latency ; j:noneQuantified true ;",
                     "k:prj_clinical_events", "not both"),
    "metric-open": (KB, '    j:validUntil "2026-03-01"^^xsd:date ;\n', "",
                    "k:met_event_latency", "exactly one version is current"),
    "version-orphan": (KB, "k:met_team.v1 j:of k:met_team", "k:met_team.v1 j:of k:met_sites",
                       "k:met_team.v1", "k:met_x.vN"),
    "version-gap": (KB, "k:met_sites.v1", "k:met_sites.v2", "k:met_sites", "no gap"),
    "range-upper": (KB, "    j:value 42 ;", "    j:value 42 ; j:upper 40 ;", "k:met_sites.v1",
                    "above its value"),
    "rank-unique": (KB, "j:rank 2 ;", "j:rank 1 ;", "k:ach_clinical_events_led_migration",
                    "its own rank"),
    "headline-cited": (KB, "j:cites k:met_sites ;", "j:cites k:met_team ;",
                       "k:prj_site_onboarding", "cite it"),
    "counts-as-cycle": (KB, "c:healthcare a j:Domain .",
                        # reported once per cycle, at its lowest id
                        "c:healthcare a j:Domain ; j:partOf c:aged-care .", "c:aged-care",
                        "one way"),
    "wall-crossed": (KB, "c:kafka j:isA c:event-driven-architecture .",
                     "c:kafka j:isA c:event-driven-architecture ; "
                     "j:distinct c:event-driven-architecture .", "c:kafka", "contradict"),
    "label-clash": (KB, 'j:label "people leadership"', 'j:label "Kafka", "people leadership"',
                    "c:team-leadership", "matching will ask"),
    "inferred-unasked": (KB, "k:q_sites_bullet j:about k:ach_site_onboarding_sites_one_platform",
                         "k:q_sites_bullet j:about k:prj_site_onboarding",
                         "k:ach_site_onboarding_sites_one_platform", "add a q_"),
    "retired-referenced": (KB, None,
                           '\nk:ach_intranet_refresh_pages j:project k:prj_intranet_refresh ; '
                           'j:rank 1 ; j:text "Rebuilt the intranet." ; '
                           'j:provenance j:confirmed .\n',
                           "k:ach_intranet_refresh_pages", "live entry"),
    "answered-before-asked": (KB, 'j:answered "2026-08-14"', 'j:answered "2026-08-10"',
                              "k:q_team_size", "correct one"),
    "application-posting": ("applications/other-role/application.ttl", None,
                            '@prefix j: <tag:jsk,2026:ns#> .\n@prefix k: <tag:jsk,2026:id/> .\n'
                            'k:app_other_role j:posting k:post_acme_platform_engineer ;\n'
                            '    j:submitted false .\n', "k:app_other_role", "beside it"),
    "event-before-submit": (APPLICATION, 'j:date "2026-09-15"^^xsd:date',
                            'j:date "2026-09-01"^^xsd:date',
                            "k:evt_acme_platform_engineer_2026_09_15_screen_scheduled",
                            "events follow"),
    "concept-class": (KB, "j:industry c:healthcare", "j:industry c:kafka", "k:org_meridian",
                      "of that class"),
    "narrows-nothing": (KB, "c:kafka j:isA c:event-driven-architecture .",
                        'c:kafka j:isA c:event-driven-architecture ; j:unlabel "Kafak" .',
                        "c:kafka", "check the spelling"),
    "concept-reclassed": (KB, "c:kafka j:isA c:event-driven-architecture .",
                          "c:kafka a j:Capability ; j:isA c:event-driven-architecture .",
                          "c:kafka", "keeps its class"),
    "quote-verbatim": (POSTING, 'j:quote "Deep, hands-on K8s experience in production"',
                       'j:quote "Ten years of K8s experience in production"',
                       "k:req_acme_platform_engineer_kubernetes", "the advert's own words"),
    "necessity-wording": (POSTING, 'j:asked "event-driven" ; j:necessity j:preferred ;',
                          'j:asked "event-driven" ; j:necessity j:required ;',
                          "k:req_acme_platform_engineer_eda", "check the necessity"),
    "log-sync": (KB, "j:revision 2 .", "j:revision 5 .", "k:kb", "restore the file"),
    "hand-edited": (KB, 'j:size "1001-5000"', 'j:size "1001-10000"', "k:kb", "jsk kb adopt"),
    "answer-placeholder": (LOG, 'j:answer "Six throughout; two joined in the second month '
                                'and two left."', 'j:answer "yes"', "k:rev_2", "in their words"),
}

WARNS = {"version-gap", "headline-cited", "label-clash", "inferred-unasked",
         "retired-referenced", "event-before-submit", "necessity-wording", "hand-edited",
         "answer-placeholder"}


class EveryRuleFires(unittest.TestCase):
    def test_every_rule_has_a_mutation(self):
        self.assertEqual({r.id for r in rules.RULES}, set(MUTATIONS))

    def test_each_mutation_fires_its_rule_at_the_right_line(self):
        for rule, mutation in MUTATIONS.items():
            with self.subTest(rule=rule):
                assert_fires(self, rule, mutation)

    def test_severity(self):
        for r in rules.RULES:
            self.assertEqual(r.severity, "WARN" if r.id in WARNS else "FAIL", r.id)


class Findings(unittest.TestCase):
    def test_a_finding_names_file_line_id_and_fix(self):
        s, _ = mutated(MUTATIONS["dangling"])
        [f] = [f for f in s.findings if f.rule == "dangling"]
        self.assertRegex(f.text(), r"^career/kb\.ttl:\d+ k:ach_clinical_events_led_migration - "
                                   r"j:cites k:met_teem: nothing defines it\n        fix: "
                                   r"did you mean k:met_team\?$")

    def test_a_duplicate_is_reported_where_it_was_added(self):
        s, _ = mutated(MUTATIONS["duplicate-id"])
        [f] = [f for f in s.findings if f.rule == "duplicate-id"]
        self.assertEqual(f.file, POSTING)
        self.assertIn("also defined in career/kb.ttl", f.detail)

    def test_a_wall_holds_whichever_side_declares_it(self):
        # distinct is symmetric: written on the broader concept, it still stops kafka.
        assert_fires(self, "wall-crossed", (
            KB, "c:event-driven-architecture a j:Capability ;",
            "c:event-driven-architecture a j:Capability ; j:distinct c:kafka ;",
            "c:event-driven-architecture", "contradict"))

    def test_a_retired_bullet_keeps_its_rank(self):
        s, _ = mutated((KB, None, '\nk:ach_clinical_events_old_latency j:project '
                        'k:prj_clinical_events ; j:rank 1 ; j:text "Cut latency." ; '
                        'j:retired "2026-01-01"^^xsd:date ; '
                        'j:reason "Superseded by the measured figure." ; '
                        'j:provenance j:confirmed .\n', "", ""))
        self.assertEqual([f.text() for f in s.findings if f.rule == "rank-unique"], [])

    def test_a_domain_shared_by_two_classes_is_one_rule(self):
        # Project.domain and Posting.domain restrict the same predicate the same way; two
        # rules reported every such fault twice.
        assert_fires(self, "concept-class", (
            KB, "j:domain c:aged-care, c:healthcare", "j:domain c:aged-care, c:kafka",
            "k:prj_clinical_events", "of that class"))

    def test_a_quote_wrapped_across_lines_of_a_crlf_advert_is_still_verbatim(self):
        s, _ = mutated(("applications/acme-platform-engineer/posting.md",
                        "Deep, hands-on K8s experience in production.",
                        "Deep, hands-on K8s\r\n   experience in production.", "", ""))
        self.assertEqual([f.text() for f in s.findings if f.rule == "quote-verbatim"], [])

    def test_an_advert_formatted_as_markdown_still_says_it(self):
        s, _ = mutated(("applications/acme-platform-engineer/posting.md",
                        "Deep, hands-on K8s experience in production.",
                        "Deep, hands‑on **K8s** experience in _production_.", "", ""))
        self.assertEqual([f.text() for f in s.findings if f.rule == "quote-verbatim"], [])

    def test_typography_is_not_wording(self):
        self.assertEqual(rules.squash("You’ll own “the” platform — `Kafka`"),
                         rules.squash("You'll own \"the\" platform - Kafka"))

    def test_an_empty_quote_quotes_nothing(self):
        s, _ = mutated((POSTING, 'j:quote "Event-driven systems a plus"', 'j:quote "  "', "", ""))
        self.assertTrue([f for f in s.findings if f.rule == "quote-verbatim"
                         and f.focus == "k:req_acme_platform_engineer_eda"])

    def test_a_write_that_reached_only_kb_ttl_is_named_torn(self):
        s, _ = mutated((KB, "j:revision 2 .", "j:revision 3 .", "", ""))
        [f] = [f for f in s.findings if f.rule == "log-sync"]
        self.assertIn("reached kb.ttl and not log.ttl", f.detail)
        self.assertIn("jsk kb adopt", f.fix)
        self.assertEqual([f for f in s.findings if f.rule == "hand-edited"], [])

    def test_a_revision_with_no_log_entry_is_out_of_step(self):
        s, _ = mutated((LOG, "k:rev_2 ", "k:rev_9 ", "", ""))
        s2, _ = mutated((LOG, "j:revision 2 ;", "j:revision 4 ;", "", ""))
        # rev_9 still says revision 2: the entry is found by its revision, not its id.
        self.assertEqual([f.rule for f in s.findings if f.rule == "log-sync"], [])
        self.assertIn("one of them was restored",
                      [f for f in s2.findings if f.rule == "log-sync"][0].detail)

    def test_a_denial_logged_as_a_confirm_is_flagged(self):
        s, _ = mutated((LOG, 'j:answer "Six throughout; two joined in the second month and '
                             'two left."', 'j:answer "No."', "", ""))
        [f] = [f for f in s.findings if f.rule == "answer-placeholder"]
        self.assertEqual(f.detail, "a confirm whose answer is 'No.'")

    def test_a_confirm_with_no_answer_is_flagged(self):
        s, _ = mutated((LOG, '    j:answer "Six throughout; two joined in the second month and '
                             'two left." ;\n', "", "", ""))
        [f] = [f for f in s.findings if f.rule == "answer-placeholder"]
        self.assertEqual((f.focus, f.detail), ("k:rev_2", "a confirm with no answer"))

    def test_the_log_may_name_ids_that_no_longer_exist(self):
        s, _ = mutated(("career/log.ttl", "j:touched k:met_team.v1,", "j:touched k:met_gone.v1,",
                        "", ""))
        self.assertEqual([f.text() for f in s.findings if f.rule == "dangling"], [])


if __name__ == "__main__":
    unittest.main()
