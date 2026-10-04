"""The career_merge tool: two concepts made one, as a changeset to review. The tool calls the kb
adapter's `merge c:a --into c:b`, which these tests call the same way (recordkit.merge)."""
import unittest

from test_graph_pack import Fixture

from jsk.adapters.cli.compose import record as changeset
from jsk.domain import ontology as O
from jsk.infra.oxigraph import record
from jsk.adapters.cli.compose import record as S

VOCAB = "c:healthcare a j:Domain ."


def c(name):
    return O.C + name


class Merge(Fixture):
    def seed(self):
        if self._testMethodName == "test_a_concept_a_posting_still_names_is_retired_not_deleted":
            posting = self.path("applications/acme-platform-engineer/posting.ttl")
            text = posting.read_text(encoding="utf-8")
            old = 'j:asked "event-driven" ; j:necessity j:preferred ;'
            self.assertIn(old, text)
            posting.write_text(text.replace(old, old + " j:concept c:event-driven-architecture ;"),
                               encoding="utf-8", newline="\n")
        super().seed()

    def merge(self, a, b, name="merge.trig"):
        code, out, err = self.kb("merge", a, "--into", b, "--out", str(self.path(name)))
        return code, out + err

    def drafted(self, name="merge.trig"):
        return changeset.read_changeset(self.path(name).read_text(encoding="utf-8"))

    def kb_quads(self):
        return {(q.subject.value, q.predicate.value, q.object.value)
                for q in S.load(self.root).graph(record.KB)}

    def test_every_reference_points_at_the_concept_it_became(self):
        self.edit_kb(VOCAB, VOCAB + '\nc:people-management a j:Capability ; '
                     'j:former "line management" .')
        code, out = self.merge("c:team-leadership", "c:people-management")
        self.assertEqual(code, 0, out)
        cs = self.drafted()
        gone = {(s.value, p.value, o.value) for s, p, o in cs.delete}
        new = {(s.value, p.value, o.value) for s, p, o in cs.add}
        bullet, project = O.K + "ach_clinical_events_led_migration", O.K + "prj_site_onboarding"
        self.assertLessEqual({(bullet, O.J + "shows", c("team-leadership")),
                              (project, O.J + "uses", c("team-leadership"))}, gone)
        self.assertLessEqual({(bullet, O.J + "shows", c("people-management")),
                              (project, O.J + "uses", c("people-management")),
                              # its label moves, and its id comes as words
                              (c("people-management"), O.J + "label", "people leadership"),
                              (c("people-management"), O.J + "label", "team leadership")}, new)
        self.assertIn((c("team-leadership"), O.RDF_TYPE, O.OP + "Entry"), gone)
        self.assertEqual(cs.retire, [])
        code, dry, _ = self.apply(str(self.path("merge.trig")), dry_run=True)
        self.assertEqual(code, 0, dry)
        code, applied, _ = self.apply(str(self.path("merge.trig")))
        self.assertEqual(code, 0, applied)
        after = self.kb_quads()
        self.assertNotIn(c("team-leadership"), {s for s, _, _ in after})
        self.assertIn((bullet, O.J + "shows", c("people-management")), after)
        self.assertEqual(self.kb("check")[0], 0)

    def test_the_bullets_whose_shows_changed_are_the_re_confirm_list(self):
        self.edit_kb(VOCAB, VOCAB + "\nc:people-management a j:Capability .")
        code, out = self.merge("c:team-leadership", "c:people-management")
        self.assertEqual(code, 0, out)
        self.assertIn("re-confirm k:ach_clinical_events_led_migration\n", out)
        self.apply(str(self.path("merge.trig")))
        self.assertIn((O.K + "ach_clinical_events_led_migration", O.J + "provenance",
                       O.J + "inferred"), self.kb_quads())

    def test_edges_pointing_at_it_and_its_own_edges_move(self):
        self.edit_kb('c:event-driven-architecture a j:Capability ; j:label "EDA", "event-driven" .',
                     'c:event-driven-architecture a j:Capability ; j:label "EDA", "event-driven" ; '
                     'j:isA c:ai-platform-architecture .\n'
                     'c:event-architecture a j:Capability ; j:label "event architecture" .')
        code, out = self.merge("event-driven-architecture", "event-architecture")
        self.assertEqual(code, 0, out)
        self.assertNotIn("re-confirm", out)
        new = {(s.value, p.value, o.value) for s, p, o in self.drafted().add}
        self.assertIn((c("kafka"), O.J + "isA", c("event-architecture")), new)
        self.assertIn((c("event-architecture"), O.J + "isA", c("ai-platform-architecture")), new)
        self.assertIn((c("event-architecture"), O.J + "label", "event driven architecture"), new)
        self.assertEqual(self.apply(str(self.path("merge.trig")))[0], 0)
        self.assertEqual(self.kb("check")[0], 0)

    def test_a_concept_a_posting_still_names_is_retired_not_deleted(self):
        # The dangling rule is a FAIL, and a changeset cannot edit a posting: deleting
        # c:event-driven-architecture would leave this requirement pointing at nothing.
        self.edit_kb(VOCAB, VOCAB + "\nc:event-architecture a j:Capability .")
        code, out = self.merge("c:event-driven-architecture", "c:event-architecture")
        self.assertEqual(code, 0, out)
        self.assertIn("k:req_acme_platform_engineer_eda still name c:event-driven-architecture, "
                      "so it is retired", out)
        cs = self.drafted()
        self.assertEqual([(s.value, p.value) for s, p, o in cs.retire],
                         [(c("event-driven-architecture"), O.J + "reason")])
        gone = {(s.value, p.value, o.value) for s, p, o in cs.delete}
        self.assertNotIn((c("event-driven-architecture"), O.RDF_TYPE, O.OP + "Entry"), gone)
        self.assertIn((c("event-driven-architecture"), O.J + "label", "EDA"), gone)
        code, dry, _ = self.apply(str(self.path("merge.trig")))
        self.assertEqual(code, 0, dry)
        store = S.load(self.root)
        self.assertEqual([f.text() for f in store.fails()], [])
        self.assertIn("retired-referenced", {f.rule for f in store.warns()})

    def test_what_it_refuses(self):
        self.edit_kb(VOCAB, VOCAB + "\nc:people-management a j:Capability ; "
                     "j:distinct c:team-leadership .")
        for a, b, said in (
                ("c:team-leadership", "c:team-leadership", "into itself"),
                ("c:no-such-thing", "c:team-leadership", "c:no-such-thing is not in the record"),
                ("c:team-leadership", "c:nowhere", "c:nowhere is not in the record"),
                ("c:terraform", "c:kafka", "defined by the shipped vocabulary"),
                ("c:healthcare", "c:team-leadership", "c:healthcare is Domain, "
                                                      "c:team-leadership is Capability"),
                ("c:team-leadership", "c:people-management", "declared distinct")):
            with self.subTest(a=a, b=b):
                code, out = self.merge(a, b)
                self.assertEqual(code, 1, out)
                self.assertIn(said, out)
                self.assertIn("nothing was written", out)
                self.assertFalse(self.path("merge.trig").exists())

    def test_called_wrong(self):
        self.assertEqual(self.kb("merge", "c:team-leadership")[0], 2)
        self.assertEqual(self.kb("merge", "c:team-leadership", "--into", "c:healthcare",
                                 "--out", "x.ttl")[0], 2)


if __name__ == "__main__":
    unittest.main()
