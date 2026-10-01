"""Tier 2: every workspace rule fires, at the right place, on the one edit that breaks it.

Same machinery as tests/test_graph_shapes.py: copy the valid fixture workspace, make one
edit - to its Turtle, which is how a test states a record - then put it in career/store/
and load it from there, as every command does, and assert the rule names the graph and
the id with the expected fix. `log-sync` and `hand-edited` are the rules only files can
break - two files torn apart, a hash - so they belong to the import, and are tested there.
"""
import functools
import shutil
import tempfile
import unittest
from pathlib import Path

import test_graph_shapes as shapes_tests
from fixtures import one_test_each
from storekit import seed
from test_graph_shapes import APPLICATION_FILE, FIXTURES, KB, KB_FILE, POSTING, POSTING_FILE, load

from jsk.domain.record import rules
from jsk.domain.posting import advert as rules_advert

LOG = "career/log.ttl"
# Rules that only a workspace laid out as files can break - its hash, which the store
# does not keep - so their mutations are the import's.
FILE_ONLY = {"log-sync", "hand-edited"}

mutated = functools.partial(shapes_tests.mutated, stored=True)
assert_fires = functools.partial(shapes_tests.assert_fires, stored=True)

# One stored advert line for the fixture posting, which makes it graph-native (Ruling 11
# of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md).
NATIVE_LINE = ('\nk:line_acme_platform_engineer_1 j:posting k:post_acme_platform_engineer ; '
               'j:n 1 ; j:section j:qualification ; j:text "Kafka in production." .\n')
KAFKA_NO = ('\nk:abs_kafka j:concept c:kafka ; j:said "2026-09-01"^^xsd:date ; '
            'j:answer "Never used Kafka." ; j:provenance j:confirmed .\n')

# rule: (file, old text, new text, focus id, the fix contains). old=None appends new.
MUTATIONS = {
    "dangling": (KB_FILE, "j:cites k:met_team ;", "j:cites k:met_teem ;",
                 "k:ach_clinical_events_led_migration", "did you mean k:met_team?"),
    "duplicate-id": (POSTING_FILE, None, '\nk:met_team j:subject "engineers" .\n', "k:met_team",
                     "keep it in one file"),
    "concept-typed": (KB_FILE, "c:healthcare a j:Domain .",
                      'c:healthcare a j:Domain .\nc:graphql j:label "GraphQL" .', "c:graphql",
                      "a j:Technology"),
    "primary-contact": (KB_FILE, 'j:primary "priya@example.com"', 'j:primary "priya@example.org"',
                        "k:person", "one of the email"),
    "headline-xor": (KB_FILE, "j:headlineMetric k:met_event_latency ;",
                     "j:headlineMetric k:met_event_latency ; j:noneQuantified true ;",
                     "k:prj_clinical_events", "not both"),
    "metric-open": (KB_FILE, '    j:validUntil "2026-03-01"^^xsd:date ;\n', "",
                    "k:met_event_latency", "exactly one version is current"),
    "version-orphan": (KB_FILE, "k:met_team.v1 j:of k:met_team", "k:met_team.v1 j:of k:met_sites",
                       "k:met_team.v1", "k:met_x.vN"),
    "version-gap": (KB_FILE, "k:met_sites.v1", "k:met_sites.v2", "k:met_sites", "no gap"),
    "range-upper": (KB_FILE, "    j:value 42 ;", "    j:value 42 ; j:upper 40 ;", "k:met_sites.v1",
                    "above its value"),
    "rank-unique": (KB_FILE, "j:rank 2 ;", "j:rank 1 ;", "k:ach_clinical_events_led_migration",
                    "its own rank"),
    "headline-cited": (KB_FILE, "j:cites k:met_sites ;", "j:cites k:met_team ;",
                       "k:prj_site_onboarding", "cite it"),
    "counts-as-cycle": (KB_FILE, "c:healthcare a j:Domain .",
                        # reported once per cycle, at its lowest id
                        "c:healthcare a j:Domain ; j:partOf c:aged-care .", "c:aged-care",
                        "one way"),
    "wall-crossed": (KB_FILE, "c:kafka j:isA c:event-driven-architecture .",
                     "c:kafka j:isA c:event-driven-architecture ; "
                     "j:distinct c:event-driven-architecture .", "c:kafka", "contradict"),
    "label-clash": (KB_FILE, 'j:label "people leadership"', 'j:label "Kafka", "people leadership"',
                    "c:team-leadership", "matching will ask"),
    "inferred-unasked": (KB_FILE, "k:q_sites_bullet j:about k:ach_site_onboarding_sites_one_platform",
                         "k:q_sites_bullet j:about k:prj_site_onboarding",
                         "k:ach_site_onboarding_sites_one_platform", "add a q_"),
    "retired-referenced": (KB_FILE, None,
                           '\nk:ach_intranet_refresh_pages j:project k:prj_intranet_refresh ; '
                           'j:rank 1 ; j:text "Rebuilt the intranet." ; '
                           'j:provenance j:confirmed .\n',
                           "k:ach_intranet_refresh_pages", "live entry"),
    "answered-before-asked": (KB_FILE, 'j:answered "2026-08-14"', 'j:answered "2026-08-10"',
                              "k:q_team_size", "correct one"),
    "application-posting": ("applications/other-role/application.ttl", None,
                            '@prefix j: <tag:jsk,2026:ns#> .\n@prefix k: <tag:jsk,2026:id/> .\n'
                            'k:app_other_role j:posting k:post_acme_platform_engineer ;\n'
                            '    j:submitted false .\n', "k:app_other_role", "beside it"),
    "event-before-submit": (APPLICATION_FILE, 'j:date "2026-09-15"^^xsd:date',
                            'j:date "2026-09-01"^^xsd:date',
                            "k:evt_acme_platform_engineer_2026_09_15_screen_scheduled",
                            "events follow"),
    "concept-class": (KB_FILE, "j:industry c:healthcare", "j:industry c:kafka", "k:org_meridian",
                      "of that class"),
    "narrows-nothing": (KB_FILE, "c:kafka j:isA c:event-driven-architecture .",
                        'c:kafka j:isA c:event-driven-architecture ; j:unlabel "Kafak" .',
                        "c:kafka", "check the spelling"),
    "concept-reclassed": (KB_FILE, "c:kafka j:isA c:event-driven-architecture .",
                          "c:kafka a j:Capability ; j:isA c:event-driven-architecture .",
                          "c:kafka", "keeps its class"),
    "concepts-bare": (KB_FILE, 'c:ai-platform-architecture a j:Capability ; '
                          'j:label "AI platform architecture" .',
                      "c:ai-platform-architecture a j:Capability .", "k:kb", "jsk kb query bare"),
    "quote-verbatim": (POSTING_FILE, 'j:quote "Deep, hands-on K8s experience in production"',
                       'j:quote "Ten years of K8s experience in production"',
                       "k:req_acme_platform_engineer_kubernetes", "the advert's own words"),
    "necessity-wording": (POSTING_FILE, 'j:asked "event-driven" ; j:necessity j:preferred ;',
                          'j:asked "event-driven" ; j:necessity j:required ;',
                          "k:req_acme_platform_engineer_eda", "check the necessity"),
    # The eda requirement re-pointed at the K8s line: the advert's "a plus" line is left
    # with no requirement quoting it.
    "advert-uncovered": (POSTING_FILE, 'j:quote "Event-driven systems a plus"',
                         'j:quote "Deep, hands-on K8s"', "k:post_acme_platform_engineer",
                         "write a requirement quoting it"),
    "log-sync": (KB_FILE, "j:revision 2 .", "j:revision 5 .", "k:kb",
                 "restore the file that went back on its own, then `jsk kb load .`"),
    "hand-edited": (KB_FILE, 'j:size "1001-5000"', 'j:size "1001-10000"', "k:kb",
                    "`jsk kb load .` imports kb.ttl as it is"),
    "answer-placeholder": (LOG, 'j:answer "Six throughout; two joined in the second month '
                                'and two left."', 'j:answer "yes"', "k:rev_2", "in their words"),
    "period": (KB_FILE, 'j:start "2016-08" ; j:end "2020-01"', 'j:start "2016-08" ; j:end "2015-01"',
               "k:pos_northbridge_architect", "the dates"),
    # The eda requirement pointed at a stored line that says something else.
    "quote-is-line": (POSTING_FILE, None, NATIVE_LINE + "k:req_acme_platform_engineer_eda "
                      "j:line k:line_acme_platform_engineer_1 .\n",
                      "k:req_acme_platform_engineer_eda", "quote the line whole"),
    # A confirmed no to Kafka, which k:prj_clinical_events is tagged with.
    "absence-contradicted": (KB_FILE, None, KAFKA_NO, "k:abs_kafka",
                             "retire the absence, or the project's claim"),
}

WARNS = {"version-gap", "headline-cited", "label-clash", "inferred-unasked",
         "retired-referenced", "event-before-submit", "necessity-wording", "hand-edited",
         "answer-placeholder", "advert-uncovered", "concepts-bare", "absence-contradicted"}


@one_test_each(list(MUTATIONS), "test_{}_fires_at_the_right_place", "fires")
class EveryRuleFires(unittest.TestCase):
    def test_every_rule_has_a_mutation(self):
        self.assertEqual({r.id for r in rules.RULES}, set(MUTATIONS))

    def fires(self, rule):
        shapes_tests.assert_fires(self, rule, MUTATIONS[rule], stored=rule not in FILE_ONLY)

    def test_severity(self):
        for r in rules.RULES:
            self.assertEqual(r.severity, "WARN" if r.id in WARNS else "FAIL", r.id)


class Periods(unittest.TestCase):
    """validate_urs's PeriodsAreUnambiguous, carried to kb.ttl: the roles' dates are what
    the resume prints, and the URS record that was checked for them is gone."""

    def detail(self, old, new):
        s, _ = mutated((KB_FILE, old, new))
        [f] = [f for f in s.findings if f.rule == "period"]
        return f.focus, f.detail

    def test_ongoing_must_not_carry_an_end_date(self):
        self.assertEqual(self.detail('j:start "2023-07" ; j:state j:ongoing ;',
                                     'j:start "2023-07" ; j:end "2024-02" ; j:state j:ongoing ;'),
                         ("k:pos_meridian_principal", "ongoing, but it ends 2024-02"))

    def test_ended_requires_an_end_date(self):
        self.assertEqual(self.detail('j:start "2020-02" ; j:end "2023-06" ; j:state j:ended ;',
                                     'j:start "2020-02" ; j:state j:ended ;'),
                         ("k:pos_meridian_senior", "ended, with no j:end"))

    def test_end_before_start(self):
        self.assertEqual(self.detail('j:start "2016-08" ; j:end "2020-01"',
                                     'j:start "2016-08" ; j:end "2015-01"')[1],
                         "ends 2015-01, before it starts 2016-08")

    def test_a_year_against_a_month_compares_the_year(self):
        s, _ = mutated((KB_FILE, 'j:start "2016-08" ; j:end "2020-01"',
                        'j:start "2016-08" ; j:end "2016"'))
        self.assertEqual([f for f in s.findings if f.rule == "period"], [])


class Findings(unittest.TestCase):
    def test_a_finding_names_graph_id_and_fix(self):
        s, _ = mutated(MUTATIONS["dangling"])
        [f] = [f for f in s.findings if f.rule == "dangling"]
        self.assertEqual(f.text(), "kb k:ach_clinical_events_led_migration - j:cites "
                                   "k:met_teem: nothing defines it\n        fix: did you mean "
                                   "k:met_team?")

    def test_the_import_names_the_line_too(self):
        # A workspace still laid out as files is validated as `jsk kb load` reads it, and
        # there a line is something a person can go to.
        s, _ = shapes_tests.mutated(MUTATIONS["dangling"])
        [f] = [f for f in s.findings if f.rule == "dangling"]
        self.assertRegex(f.text(), r"^kb:\d+ k:ach_clinical_events_led_migration - ")

    def test_a_duplicate_is_reported_where_it_was_added(self):
        s, _ = mutated(MUTATIONS["duplicate-id"])
        [f] = [f for f in s.findings if f.rule == "duplicate-id"]
        self.assertEqual(f.file, POSTING)
        self.assertIn("also defined in kb", f.detail)

    def test_a_wall_holds_whichever_side_declares_it(self):
        # distinct is symmetric: written on the broader concept, it still stops kafka.
        assert_fires(self, "wall-crossed", (
            KB_FILE, "c:event-driven-architecture a j:Capability ;",
            "c:event-driven-architecture a j:Capability ; j:distinct c:kafka ;",
            "c:event-driven-architecture", "contradict"))

    def test_a_retired_bullet_keeps_its_rank(self):
        s, _ = mutated((KB_FILE, None, '\nk:ach_clinical_events_old_latency j:project '
                        'k:prj_clinical_events ; j:rank 1 ; j:text "Cut latency." ; '
                        'j:retired "2026-01-01"^^xsd:date ; '
                        'j:reason "Superseded by the measured figure." ; '
                        'j:provenance j:confirmed .\n', "", ""))
        self.assertEqual([f.text() for f in s.findings if f.rule == "rank-unique"], [])

    def test_a_domain_shared_by_two_classes_is_one_rule(self):
        # Project.domain and Posting.domain restrict the same predicate the same way; two
        # rules reported every such fault twice.
        assert_fires(self, "concept-class", (
            KB_FILE, "j:domain c:aged-care, c:healthcare", "j:domain c:aged-care, c:kafka",
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

    def test_an_advert_that_is_not_utf8_is_named_not_a_traceback(self):
        """A Windows editor's cp1252 save (`\\x93` is its curly quote) raised
        UnicodeDecodeError out of the load, past the `except OSError` for a missing one."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
        advert = tmp / "applications/acme-platform-engineer/posting.md"
        advert.write_bytes(advert.read_bytes() + b"\n\x93Nice to have\x94\n")
        seed(tmp)
        s = load(tmp)
        quotes = [f.text() for f in s.findings if f.rule == "quote-verbatim"]
        self.assertTrue(quotes)
        self.assertTrue(all("posting.md beside it is not UTF-8" in t for t in quotes), quotes)
        self.assertEqual([f for f in s.findings if f.rule == "advert-uncovered"], [])

    def test_typography_is_not_wording(self):
        self.assertEqual(rules_advert.squash("You’ll own “the” platform — `Kafka`"),
                         rules_advert.squash("You'll own \"the\" platform - Kafka"))

    def test_an_empty_quote_quotes_nothing(self):
        s, _ = mutated((POSTING_FILE, 'j:quote "Event-driven systems a plus"', 'j:quote "  "', "", ""))
        self.assertTrue([f for f in s.findings if f.rule == "quote-verbatim"
                         and f.focus == "k:req_acme_platform_engineer_eda"])

    def test_the_import_names_a_torn_write(self):
        # Two files could be torn apart; a workspace still laid out as them is refused by
        # `jsk kb load` until they agree, and this is what it says.
        s, _ = shapes_tests.mutated((KB_FILE, "j:revision 2 .", "j:revision 3 .", "", ""))
        [f] = [f for f in s.findings if f.rule == "log-sync"]
        self.assertIn("reached kb.ttl and not log.ttl", f.detail)
        self.assertIn("set kb.ttl's k:kb j:revision back to 2, then run `jsk kb load .` again",
                      f.fix)
        self.assertNotIn("adopt", f.fix)
        # Not `jsk kb check`: every verb but load is refused before the import.
        self.assertNotIn("kb check", f.fix)
        self.assertEqual([f for f in s.findings if f.rule == "hand-edited"], [])

    def test_the_import_finds_a_revision_with_no_log_entry(self):
        s, _ = shapes_tests.mutated((LOG, "k:rev_2 ", "k:rev_9 ", "", ""))
        s2, _ = shapes_tests.mutated((LOG, "j:revision 2 ;", "j:revision 4 ;", "", ""))
        # rev_9 still says revision 2: the entry is found by its revision, not its id.
        self.assertEqual([f.rule for f in s.findings if f.rule == "log-sync"], [])
        [f] = [f for f in s2.findings if f.rule == "log-sync"]
        self.assertIn("one of them was restored", f.detail)
        self.assertEqual(f.file, KB)

    def test_a_stored_career_is_never_out_of_step_or_hand_edited(self):
        # Every jsk write lands the career and its log entry in one update, and the store
        # keeps no text to hash: what would part two files, or edit one by hand, is once
        # stored simply the career - the rules that watch for it say nothing.
        for edit in (MUTATIONS["hand-edited"][:3], MUTATIONS["log-sync"][:3],
                     (LOG, "j:revision 2 ;", "j:revision 4 ;")):
            with self.subTest(edit=edit[1]):
                s, _ = mutated(edit)
                self.assertEqual([f.text() for f in s.findings
                                  if f.rule in ("log-sync", "hand-edited")], [])

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


class BareCapabilities(unittest.TestCase):
    """concepts-bare: a capability of kb.ttl's with no label and no place matches only its
    own id. One finding for the lot; `jsk kb query bare` lists them."""

    BARE = ('c:ai-platform-architecture a j:Capability ; j:label "AI platform architecture" .\n'
            'c:data-sovereignty a j:Capability ; j:label "data residency" .')

    def bare(self, new):
        s, _ = mutated((KB_FILE, self.BARE, new))
        return [f for f in s.findings if f.rule == "concepts-bare"]

    def test_several_are_one_finding_that_counts_them(self):
        [f] = self.bare("c:ai-platform-architecture a j:Capability .\n"
                        "c:data-sovereignty a j:Capability .")
        self.assertEqual((f.file, f.focus), (KB, "k:kb"))
        self.assertTrue(f.detail.startswith("2 capabilities in the career have no label"),
                        f.detail)

    def test_an_edge_alone_places_it(self):
        self.assertEqual(self.bare("c:ai-platform-architecture a j:Capability ; "
                                   "j:isA c:event-driven-architecture .\n"
                                   "c:data-sovereignty a j:Capability ; "
                                   "j:partOf c:team-leadership ."), [])

    def test_a_label_in_another_statement_counts(self):
        self.assertEqual(self.bare("c:ai-platform-architecture a j:Capability .\n"
                                   'c:ai-platform-architecture j:label "AI platform" .\n'
                                   'c:data-sovereignty a j:Capability ; j:label "residency" .'),
                         [])

    def test_a_retired_one_is_not_counted(self):
        self.assertEqual(self.bare('c:ai-platform-architecture a j:Capability ; '
                                   'j:label "AI platform architecture" .\n'
                                   'c:data-sovereignty a j:Capability ; '
                                   'j:retired "2026-01-01"^^xsd:date .'), [])


ADVERT = "applications/acme-platform-engineer/posting.md"


class AdvertCoverage(unittest.TestCase):
    """advert-uncovered: a requirement the analyst left out is invisible to everything
    downstream, so the advert's requirement-like lines are read back against the quotes."""

    def uncovered(self, old, new):
        s, _ = mutated((ADVERT, old, new))
        return [f.detail for f in s.findings if f.rule == "advert-uncovered"]

    BRING = "## What you'll bring\n"

    def test_an_unquoted_must_under_a_requirements_heading(self):
        self.assertEqual(self.uncovered(self.BRING, self.BRING + "\n- Must have Terraform in "
                                                                  "production.\n"),
                         ["the advert asks 'Must have Terraform in production.' and no "
                          "requirement quotes it"])

    def test_a_bold_or_colon_heading_opens_a_section_too(self):
        for heading in ("**Requirements**", "You have:"):
            with self.subTest(heading=heading):
                self.assertEqual(len(self.uncovered(
                    "## Benefits\n", f"{heading}\n\n* Must have Terraform in production\n\n"
                                     "## Benefits\n")), 1)

    def test_not_under_benefits_or_responsibilities(self):
        for heading in ("## Benefits\n", "## What you'll do\n"):
            with self.subTest(heading=heading):
                self.assertEqual(self.uncovered(heading, heading + "- Must have a good time at "
                                                               "the offsite.\n"), [])

    def test_not_an_eligibility_line(self):
        self.assertEqual(self.uncovered(self.BRING, self.BRING + "- Must hold Australian work "
                                                                  "authorisation.\n"), [])

    def test_not_a_short_line(self):
        self.assertEqual(self.uncovered(self.BRING, self.BRING + "- Terraform.\n"), [])

    def test_a_quoted_line_is_covered_whatever_its_typography(self):
        self.assertEqual(self.uncovered("- Deep, hands-on K8s experience in production.",
                                        "- Deep, hands‑on K8s experience in production — "
                                        "at scale."), [])
        self.assertEqual(self.uncovered("- Event-driven systems a plus.",
                                        "- **Event‑driven** systems a plus."), [])

    def edited(self, *edits):
        """advert-uncovered's details after several (file, old, new) edits; old=None
        writes the file whole."""
        import shutil
        import tempfile
        from pathlib import Path

        from test_graph_shapes import FIXTURES, load

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
        for file, old, new in edits:
            path = Path(tmp) / file
            if old is None:
                text = new
            else:
                text = path.read_text(encoding="utf-8")
                self.assertIn(old, text)
                text = text.replace(old, new)
            path.write_text(text, encoding="utf-8", newline="\n")
        seed(tmp)
        return [f.detail for f in load(tmp).findings if f.rule == "advert-uncovered"]

    def test_a_quote_ending_in_a_full_stop_covers_a_labelled_line(self):
        # JumpCloud, 2026-09-26: "Experience: 12+ years of ... environments." quoted from
        # "12+" to the full stop warned, because only the line lost its stop.
        self.assertEqual(self.edited(
            (ADVERT, "- Deep, hands-on K8s", "- Kubernetes: Deep, hands-on K8s"),
            (POSTING_FILE, 'K8s experience in production" .', 'K8s experience in production." .')),
            [])

    def test_a_line_decisions_txt_drops_is_answered(self):
        added = (ADVERT, self.BRING, self.BRING + "- Must have run Origin CI in anger.\n")
        self.assertEqual(len(self.edited(added)), 1)
        # The line's number as `jsk posting extract` prints it: the first under the heading.
        drops = "applications/acme-platform-engineer/decisions.txt"
        self.assertEqual(self.edited(added, (drops, None, "company: Acme Health\ntitle: x\n"
                                                          "3 | - | internal tooling\n")), [])
        self.assertEqual(len(self.edited(added, (drops, None, "company: Acme Health\n"
                                                                "4 | - | the wrong line\n"))), 1)

    def test_a_wrapped_item_is_one_line(self):
        self.assertEqual(self.uncovered("- Event-driven systems a plus.",
                                        "- Event-driven systems a\n  plus."), [])

    def test_a_long_line_is_cut_where_it_is_named(self):
        [said] = self.uncovered(self.BRING, self.BRING + "- Must have " + "very " * 30 + "much.\n")
        self.assertLess(len(said), 120)
        self.assertIn("…", said)


class GraphNativeAdvert(unittest.TestCase):
    """quote-verbatim and advert-uncovered on a graph-native posting read the stored lines,
    not posting.md, and leave a draft alone (Rulings 2 and 3 of
    docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md)."""

    STEM = "acme_platform_engineer"

    def load(self, reqs, drops=None, state="complete"):
        """The fixture workspace with its posting replaced by a graph-native one built from
        posting.md's lines - and posting.md removed, so nothing can read it."""
        from appkit import put
        from jsk.domain.posting.advert import advert_lines
        from jsk.domain.posting.decide import triples
        from jsk.domain import ontology as O
        from jsk.domain.record.writer import write

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
        advert = tmp / ADVERT
        lines = advert_lines(advert.read_text(encoding="utf-8"))
        seed(tmp)
        advert.unlink()
        built = triples(O.K + "post_" + self.STEM, self.STEM,
                        {"company": "Acme Health", "title": "Platform Engineer"}, "", [],
                        "2026-09-08", reqs, lines=lines, drops=drops, state=state)
        put(tmp, POSTING, write(built, "posting"), prefixes=False)
        return load(tmp)

    def setUp(self):
        from jsk.domain.posting.advert import advert_lines

        found = advert_lines((FIXTURES / ADVERT).read_text(encoding="utf-8"))
        self.k8s, self.eda = (next(x.n for x in found if x.text.startswith(words))
                              for words in ("Deep, hands-on K8s", "Event-driven systems"))
        self.text = {x.n: x.text for x in found}

    def req(self, slug, n, quote=None):
        """A requirement row quoting line `n` - its text, unless `quote` says otherwise."""
        return (slug, slug, "required", [], self.text[n] if quote is None else quote, n)

    def findings(self, store, *names):
        return [f.text() for f in store.findings if f.rule in names]

    def test_every_quote_a_line_and_every_ask_answered_is_clean_without_posting_md(self):
        s = self.load([self.req("k8s", self.k8s), self.req("eda", self.eda)])
        self.assertEqual(self.findings(s, "quote-verbatim", "advert-uncovered", "quote-is-line"),
                         [])
        self.assertEqual([f.text() for f in s.fails()], [])

    def test_a_quote_no_line_says_is_invented(self):
        s = self.load([self.req("k8s", self.k8s, quote="Ten years of K8s"),
                       self.req("eda", self.eda)])
        [said] = self.findings(s, "quote-verbatim")
        self.assertIn("no line of the advert says it", said)
        # The quote parts from its line too, and that is named on its own.
        self.assertEqual(len(self.findings(s, "quote-is-line")), 1)

    def test_an_unanswered_qualification_line_is_uncovered_and_a_dropped_one_is_not(self):
        reqs = [self.req("k8s", self.k8s)]
        [said] = [f.detail for f in self.load(reqs).findings if f.rule == "advert-uncovered"]
        self.assertIn("Event-driven systems a plus.", said)
        dropped = self.load(reqs, drops={self.eda: "not this role"})
        self.assertEqual(self.findings(dropped, "advert-uncovered"), [])

    def test_a_draft_is_not_judged(self):
        s = self.load([self.req("k8s", self.k8s, quote="Ten years of K8s")], state="draft")
        self.assertEqual(self.findings(s, "quote-verbatim", "advert-uncovered"), [])

    def test_a_posting_built_from_files_is_written_as_it_always_was(self):
        # Rulings 1-3 are additions: without lines, decide.triples writes j:advert and no
        # state, line or AdvertLine - the triples every file-built posting already holds.
        from jsk.domain.posting.decide import triples
        from jsk.domain import ontology as O

        built = triples(O.K + "post_x", "x", {"company": "A", "title": "B"}, "", [],
                        "2026-09-08", [("k8s", "K8s", "required", [], "K8s in prod")])
        preds = {t.predicate.value[len(O.J):] for t in built}
        self.assertEqual(preds, {"company", "title", "captured", "advert", "posting", "asked",
                                 "necessity", "quote"})


class AbsenceContradicted(unittest.TestCase):
    """absence-contradicted: a no against what a live project holds - one of the two is
    stale, and only the person can say which (Ruling 8)."""

    def fired(self, absence):
        s, _ = mutated((KB_FILE, None, absence))
        return [f for f in s.findings if f.rule == "absence-contradicted"]

    def test_a_no_to_a_broader_concept_a_project_holds_through_isa(self):
        # c:kafka isA c:event-driven-architecture: a Kafka project holds EDA too.
        [f] = self.fired(KAFKA_NO.replace("c:kafka", "c:event-driven-architecture")
                         .replace("abs_kafka", "abs_event_driven_architecture"))
        self.assertIn("k:prj_clinical_events", f.detail)

    def test_a_retired_no_contradicts_nothing(self):
        self.assertEqual(self.fired(KAFKA_NO.replace(
            "j:provenance j:confirmed", 'j:provenance j:confirmed ; j:retired '
            '"2026-09-20"^^xsd:date ; j:reason "they learnt it"')), [])

    def test_a_no_nothing_holds_is_quiet(self):
        self.assertEqual(self.fired(KAFKA_NO.replace("c:kafka", "c:healthcare-x")
                                    + '\nc:healthcare-x a j:Technology .\n'), [])


if __name__ == "__main__":
    unittest.main()
