"""Reading a changeset: its four graphs and header, and one test per refusal it can make
without the career in front of it."""
import unittest

from jsk.graph import changeset as C
from jsk.graph.io import GraphError

PFX = """@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix op: <tag:jsk,2026:op#> .
"""


def read(body):
    return C.read(PFX + body)


def refusals(body):
    try:
        read(body)
    except C.Refused as e:
        return [x.text() for x in e.refusals]
    raise AssertionError("not refused")


class Reading(unittest.TestCase):
    def test_the_four_graphs_and_the_header(self):
        cs = read('op:changeset op:base 7 ; op:summary "From the braindump." .\n'
                  'op:add { k:prj_payments j:name "Payments" . }\n'
                  'op:set { k:prj_legacy j:strength 2 . }\n'
                  'op:retire { k:prj_intranet j:reason "Too old." . }\n'
                  'op:delete { k:q_dup a op:Entry . k:ach_x_did_thing j:shows c:java . }\n')
        self.assertEqual((cs.base, cs.summary), (7, "From the braindump."))
        self.assertEqual([len(cs.add), len(cs.set), len(cs.retire), len(cs.delete)], [1, 1, 1, 2])

    def test_a_new_bullet_may_leave_its_id_to_jsk(self):
        cs = read('op:add { [] j:project k:prj_payments ; j:rank 1 ; j:text "Cut it." . }\n')
        self.assertEqual(len(cs.add), 3)

    def test_a_changeset_saved_by_a_windows_editor_reads_the_same(self):
        body = 'op:add { k:prj_payments j:name "Payments" . }\n'
        cs = C.read("﻿" + (PFX + body).replace("\n", "\r\n"))
        self.assertEqual(len(cs.add), 1)
        self.assertEqual(cs.add[0][2].value, "Payments")

    def test_a_syntax_error_is_a_graph_error(self):
        with self.assertRaises(GraphError):
            read("op:add { k:prj_x j:name . }\n")


class Refusals(unittest.TestCase):
    def assertRefused(self, body, *says):
        found = "\n".join(refusals(body))
        for s in says:
            self.assertIn(s, found)

    def test_a_triple_outside_any_graph(self):
        self.assertRefused('k:prj_x j:name "X" .\n', "outside any graph", "op:add")

    def test_an_unknown_graph(self):
        self.assertRefused('op:insert { k:prj_x j:name "X" . }\n', "a graph named op:insert")

    def test_the_derived_graph(self):
        self.assertRefused('j:derived { k:prj_x j:name "X" . }\n', "a graph named j:derived")

    def test_confirmed_provenance(self):
        self.assertRefused('op:set { k:prj_x j:provenance j:confirmed . }\n',
                           "a changeset cannot confirm", "jsk kb confirm")

    def test_a_blank_node_object(self):
        self.assertRefused('op:add { k:prj_x j:headlineMetric [ j:subject "x" ] . }\n',
                           "points at a blank node")

    def test_a_blank_node_outside_add(self):
        self.assertRefused('op:set { [] j:project k:prj_x . }\n', "a blank node in op:set")

    def test_a_blank_node_that_is_not_a_bullet(self):
        self.assertRefused('op:add { [] j:name "Payments" . }\n', "a blank node with no j:project")

    def test_an_unknown_predicate_names_the_nearest(self):
        self.assertRefused('op:add { k:prj_x j:strenght 3 . }\n',
                           "j:strenght is not a Project predicate", "did you mean j:strength?")

    def test_a_foreign_predicate(self):
        self.assertRefused('op:add { k:prj_x <http://schema.org/name> "X" . }\n',
                           "is not a Project predicate")

    def test_a_derived_type(self):
        self.assertRefused('op:add { k:prj_x a j:Project . }\n', "rdf:type is derived")

    def test_not_a_jsk_id(self):
        self.assertRefused('op:add { k:project_x j:name "X" . }\n', "not a jsk id")

    def test_an_entry_of_another_file(self):
        self.assertRefused('op:add { k:evt_x j:kind j:note . }\n', "an Event lives in application.ttl",
                           "writes career/kb.ttl only")

    def test_the_log(self):
        self.assertRefused('op:add { k:rev_9 j:summary "x" . }\n', "lives in log.ttl")

    def test_the_header_jsk_writes(self):
        self.assertRefused('op:set { k:kb j:updated "2026-01-01"^^xsd:date . }\n',
                           "j:updated is written by jsk")

    def test_retire_takes_a_reason_only(self):
        self.assertRefused('op:retire { k:prj_x j:retired "2026-01-01"^^xsd:date . }\n',
                           "op:retire takes j:reason only")

    def test_op_terms_inside_a_graph(self):
        self.assertRefused('op:add { k:prj_x j:uses op:Entry . }\n', "op: terms name graphs")

    def test_every_refusal_is_reported_not_the_first(self):
        self.assertEqual(len(refusals('op:add { k:prj_x j:strenght 3 ; a j:Project . }\n')), 2)


if __name__ == "__main__":
    unittest.main()
