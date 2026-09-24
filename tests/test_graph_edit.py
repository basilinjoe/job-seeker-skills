"""A changeset merged into the fixture career: the four graphs, the refusals that need the
record, and what apply does unasked - provenance, questions, bullet ids, versions."""
import datetime
import unittest

from test_graph_changeset import PFX
from test_graph_shapes import FIXTURES, load

from jsk.graph import changeset, edit
from jsk.graph import ontology as O
from jsk.graph.changeset import Refused

TODAY = datetime.date(2026, 9, 24)
STORE = None


def store():
    global STORE
    if STORE is None:
        STORE = load(FIXTURES)
    return STORE


def run(body):
    return edit.apply(store(), changeset.read(PFX + body), TODAY)


def refused(body):
    try:
        run(body)
    except Refused as e:
        return "\n".join(r.text() for r in e.refusals)
    raise AssertionError("not refused")


def props(e, local):
    """{predicate: sorted values} of k:<local> after the edit."""
    out = {}
    for q in e.quads:
        if q.subject.value == O.K + local:
            out.setdefault(q.predicate.value[len(O.J):], []).append(q.object.value)
    return {p: sorted(v) for p, v in out.items()}


NEW_PROJECT = ('op:add { k:prj_payments j:name "Payments platform" ; '
               'j:position k:pos_meridian_principal ; j:strength 4 ; j:recency 2025 . }\n')


class Adding(unittest.TestCase):
    def test_a_new_entry_is_inferred_and_asked_about(self):
        e = run(NEW_PROJECT)
        self.assertEqual(props(e, "prj_payments")["provenance"], [O.J + "inferred"])
        self.assertEqual(props(e, "q_prj_payments")["about"], [O.K + "prj_payments"])
        self.assertEqual(e.minted, {O.K + "prj_payments", O.K + "q_prj_payments"})
        self.assertEqual(e.touched, set())

    def test_a_new_bullet_is_named_by_its_project_and_words(self):
        e = run(NEW_PROJECT[:-3] + ' [] j:project k:prj_payments ; j:rank 1 ; '
                'j:text "Cut settlement latency from 800 ms to 200 ms." . }\n')
        self.assertIn(O.K + "ach_payments_cut_settlement_latency", e.minted)
        self.assertIn("minted k:ach_payments_cut_settlement_latency", e.notes)

    def test_a_minted_id_is_never_one_already_used(self):
        e = run('op:add { [] j:project k:prj_clinical_events ; j:rank 3 ; '
                'j:text "Clinical event latency, halved again." . }\n')
        # ach_clinical_events_clinical_event_latency is free; the fixture's ids are not reused
        self.assertIn(O.K + "ach_clinical_events_clinical_event_latency", e.minted)
        e2 = run('op:add { [] j:project k:prj_clinical_events ; j:rank 3 ; '
                 'j:text "Event latency cut, again." . }\n'
                 'op:add { k:ach_clinical_events_event_latency_cut j:project k:prj_clinical_events ;'
                 ' j:rank 4 ; j:text "x" . }\n')
        # the three-word id is named by the changeset itself, so the bullet takes four
        self.assertIn(O.K + "ach_clinical_events_event_latency_cut", e2.minted)
        self.assertIn(O.K + "ach_clinical_events_event_latency_cut_again", e2.minted)

    def test_adding_a_second_value_where_one_is_allowed_says_use_set(self):
        self.assertIn("op:set replaces it", refused('op:add { k:prj_clinical_events j:strength 4 . }\n'))

    def test_a_shipped_concept_can_be_extended(self):
        e = run('op:add { c:docker j:label "Docker Engine" . }\n')
        self.assertEqual(props_c(e, "docker")["label"], ["Docker Engine"])


def props_c(e, slug):
    out = {}
    for q in e.quads:
        if q.subject.value == O.C + slug:
            out.setdefault(q.predicate.value[len(O.J):], []).append(q.object.value)
    return out


class Setting(unittest.TestCase):
    def test_a_changed_claim_is_an_unconfirmed_claim(self):
        e = run('op:set { k:ach_clinical_events_led_migration j:text "Led 6 engineers." . }\n')
        p = props(e, "ach_clinical_events_led_migration")
        self.assertEqual((p["text"], p["provenance"]), (["Led 6 engineers."], [O.J + "inferred"]))
        self.assertIn(O.K + "q_ach_clinical_events_led_migration", e.minted)
        self.assertIn("k:ach_clinical_events_led_migration is now inferred: j:text changed", e.notes)

    def test_a_change_that_is_not_a_claim_keeps_its_provenance(self):
        e = run('op:set { k:prj_clinical_events j:strength 4 . }\n')
        self.assertEqual(props(e, "prj_clinical_events")["provenance"], [O.J + "confirmed"])
        self.assertEqual(e.touched, {O.K + "prj_clinical_events"})

    def test_a_stated_provenance_stands(self):
        e = run('op:set { k:ach_clinical_events_led_migration j:text "Led 6." ; '
                'j:provenance j:needs-verification . }\n')
        self.assertEqual(props(e, "ach_clinical_events_led_migration")["provenance"],
                         [O.J + "needs-verification"])

    def test_an_open_question_is_not_asked_twice(self):
        e = run('op:set { k:ach_site_onboarding_sites_one_platform j:text "Brought 42 sites on." . }\n')
        self.assertFalse([m for m in e.minted if "q_" in m])

    def test_setting_what_is_already_there_changes_nothing(self):
        e = run('op:set { k:prj_clinical_events j:strength 5 . }\n')
        self.assertEqual((e.touched, e.minted), (set(), set()))

    def test_setting_an_entry_that_does_not_exist(self):
        self.assertIn("op:add it instead", refused('op:set { k:prj_nothing j:strength 2 . }\n'))


class Versions(unittest.TestCase):
    def test_a_sent_version_is_never_changed_its_new_number_is_the_next_version(self):
        e = run('op:set { k:met_team.v1 j:value 7 . }\n')
        self.assertEqual(props(e, "met_team.v1")["value"], ["6"])
        self.assertEqual(props(e, "met_team.v1")["validUntil"], ["2026-09-24"])
        v2 = props(e, "met_team.v2")
        self.assertEqual((v2["value"], v2["validFrom"], v2["provenance"], v2["source"]),
                         (["7"], ["2026-09-24"], [O.J + "inferred"], ["org chart"]))
        self.assertTrue(any("sent in k:app_acme_platform_engineer" in n for n in e.notes))
        self.assertIn(O.K + "q_met_team_v2", e.minted)

    def test_a_version_never_sent_is_corrected_in_place(self):
        e = run('op:set { k:met_sites.v1 j:value 43 . }\n')
        self.assertEqual(props(e, "met_sites.v1")["value"], ["43"])
        self.assertNotIn(O.K + "met_sites.v2", e.minted)

    def test_anything_else_on_a_sent_version_is_refused(self):
        self.assertIn("sent in k:app_acme_platform_engineer",
                      refused('op:set { k:met_team.v1 j:source "HR system" . }\n'))

    def test_a_new_version_closes_the_current_one(self):
        e = run('op:add { k:met_sites.v2 j:of k:met_sites ; j:value 50 ; j:confidence j:measured ; '
                'j:validFrom "2026-09-01"^^xsd:date . }\n')
        self.assertEqual(props(e, "met_sites.v1")["validUntil"], ["2026-09-01"])
        self.assertIn("closed k:met_sites.v1: k:met_sites.v2 is current", e.notes)


class Retiring(unittest.TestCase):
    def test_retiring_dates_it_and_keeps_the_reason(self):
        e = run('op:retire { k:prj_site_onboarding j:reason "Superseded." . }\n')
        p = props(e, "prj_site_onboarding")
        self.assertEqual((p["retired"], p["reason"]), (["2026-09-24"], ["Superseded."]))

    def test_retiring_what_is_retired(self):
        self.assertIn("already retired",
                      refused('op:retire { k:prj_intranet_refresh j:reason "Old." . }\n'))


class Deleting(unittest.TestCase):
    def test_an_entry_nothing_points_at(self):
        e = run('op:delete { k:q_team_size a op:Entry . }\n')
        self.assertEqual(props(e, "q_team_size"), {})
        self.assertEqual(e.touched, {O.K + "q_team_size"})

    def test_an_entry_something_points_at_is_retired_instead(self):
        text = refused('op:delete { k:met_sites a op:Entry . }\n')
        self.assertIn("referenced by k:ach_site_onboarding_sites_one_platform", text)
        self.assertIn("retire it", text)

    def test_a_reference_from_an_application_counts(self):
        self.assertIn("k:app_acme_platform_engineer",
                      refused('op:delete { k:ach_clinical_events_led_migration a op:Entry . }\n'))

    def test_a_triple_that_is_not_there(self):
        self.assertIn("has no j:shows c:java to delete",
                      refused('op:delete { k:ach_clinical_events_led_migration j:shows c:java . }\n'))


class Base(unittest.TestCase):
    def test_an_entry_changed_since_the_base_is_a_conflict(self):
        text = refused('op:changeset op:base 1 .\nop:set { k:met_team.v1 j:source "x" . }\n')
        self.assertIn("changed at r2, after this changeset's op:base r1", text)

    def test_the_base_the_record_is_at_is_no_conflict(self):
        run('op:changeset op:base 2 .\nop:set { k:prj_clinical_events j:strength 4 . }\n')

    def test_a_base_ahead_of_the_log(self):
        self.assertIn("ahead of log.ttl", refused('op:changeset op:base 9 .\n'
                                                  'op:set { k:prj_clinical_events j:strength 4 . }\n'))


if __name__ == "__main__":
    unittest.main()
