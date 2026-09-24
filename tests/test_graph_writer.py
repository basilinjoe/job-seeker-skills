"""Writing the graph record: gofmt's contract.

The writer's promise is that the file is a function of the triples. These tests hold it
to that from three sides: the committed fixtures are already canonical (so rewriting them
changes nothing), random graphs survive write -> parse -> write, and input order never
reaches the output.
"""
import random
import unittest
from pathlib import Path

import pyoxigraph as ox

from graphgen import graph
from jsk.graph import io, writer
from jsk.graph import ontology as O

FIXTURES = Path(__file__).parent / "graph_fixtures"
FILES = sorted(FIXTURES.rglob("*.ttl"))
PFX = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES)


def triples(parsed):
    return {(str(q.subject), str(q.predicate), str(q.object)) for q in parsed.quads}


class FixturesAreCanonical(unittest.TestCase):
    def test_every_fixture_rewrites_to_itself(self):
        self.assertEqual(len(FILES), 4)
        for path in FILES:
            with self.subTest(file=path.name):
                text = path.read_bytes().decode("utf-8")
                parsed = io.parse_text(text, path.name)
                self.assertEqual(writer.write(parsed.quads, parsed.kind), text)

    def test_the_shipped_vocabulary_is_canonical(self):
        import jsk
        text = (Path(jsk.__file__).parent / "data" / "vocabulary.ttl").read_bytes().decode()
        parsed = io.parse_text(text, "vocabulary.ttl")
        self.assertEqual(writer.write(parsed.quads, "vocabulary"), text)


class RandomGraphsRoundTrip(unittest.TestCase):
    SEEDS = range(60)

    def test_write_parse_write(self):
        for kind in ("kb", "posting", "application", "log", "vocabulary"):
            for seed in self.SEEDS:
                with self.subTest(kind=kind, seed=seed):
                    ts, _ = graph(seed, kind)
                    out = writer.write(ts, kind)
                    back = io.parse_text(out, f"{kind}.ttl", kind)
                    self.assertEqual(triples(back), {(str(t.subject), str(t.predicate),
                                                      str(t.object)) for t in ts})
                    self.assertEqual(writer.write(back.quads, kind), out)

    def test_input_order_never_reaches_the_output(self):
        for seed in range(20):
            ts, _ = graph(seed, "kb")
            shuffled = list(ts)
            random.Random(seed + 1000).shuffle(shuffled)
            self.assertEqual(writer.write(shuffled, "kb"), writer.write(ts, "kb"), seed)


class Literals(unittest.TestCase):
    CASES = ['He said """hi""" and left', 'ends with a quote"', 'ends with two""',
             'five """"" quotes', 'back\\slash', 'back\\slash then quote\\"', 'tab\there',
             'line\nbreak', 'ends in newline\n', '\nstarts with one', 'arrow → and é',
             'a # is not a comment', "'''single'''", 'carriage\rreturn', '"', '""', '"""',
             '\\', '\\"', '"\n"']

    def test_every_awkward_string_round_trips(self):
        for value in self.CASES:
            with self.subTest(value=value):
                t = ox.Triple(ox.NamedNode(O.K + "met_x"), ox.NamedNode(O.J + "subject"),
                              ox.Literal(value))
                out = writer.write([t], "kb")
                back = io.parse_text(out, "kb.ttl")
                self.assertEqual([q.object.value for q in back.quads], [value])

    def test_multiline_prose_stays_readable(self):
        t = ox.Triple(ox.NamedNode(O.K + "prj_x"), ox.NamedNode(O.J + "problem"),
                      ox.Literal('It said "no".\nSo we did.'))
        out = writer.write([t], "kb")
        self.assertIn('j:problem """It said "no".\nSo we did.""" .', out)

    def test_numbers_and_dates_are_bare_or_typed(self):
        out = writer.write(io.parse_text(PFX + 'k:met_x.v1 j:value 42 ; j:baseline 8.5 ; '
                                         'j:validFrom "2026-09-01"^^xsd:date .', "kb.ttl").quads,
                           "kb")
        self.assertIn("j:baseline 8.5 ; j:value 42", out)
        self.assertIn('j:validFrom "2026-09-01"^^xsd:date', out)


class Layout(unittest.TestCase):
    def test_kb_prints_every_banner_even_when_empty(self):
        out = writer.write([], "kb")
        for section in O.SECTIONS["kb"]:
            self.assertIn(f"# == {section}\n", out)

    def test_other_kinds_omit_empty_sections(self):
        self.assertNotIn("# ==", writer.write([], "posting"))

    def test_lf_only_one_final_newline(self):
        for path in FILES:
            text = path.read_bytes().decode("utf-8")
            self.assertNotIn("\r", text)
            self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))

    def test_roles_newest_first_and_bullets_under_their_project(self):
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8")
        order = [text.index(x) for x in ("k:pos_meridian_principal", "k:pos_meridian_senior",
                                         "k:pos_northbridge_architect")]
        self.assertEqual(order, sorted(order))
        order = [text.index(x) for x in ("k:prj_clinical_events j:",
                                         "k:ach_clinical_events_event_latency j:",
                                         "k:ach_clinical_events_led_migration j:",
                                         "k:prj_site_onboarding j:")]
        self.assertEqual(order, sorted(order))

    def test_types_are_never_written_for_ids(self):
        t = ox.Triple(ox.NamedNode(O.K + "org_x"), ox.NamedNode(O.RDF_TYPE),
                      ox.NamedNode(O.J + "Organisation"))
        with self.assertRaises(writer.WriteError):
            writer.write([t], "kb")

    def test_a_class_outside_its_file_kind_is_refused(self):
        t = ox.Triple(ox.NamedNode(O.K + "pos_x"), ox.NamedNode(O.J + "title"), ox.Literal("x"))
        with self.assertRaises(writer.WriteError):
            writer.write([t], "posting")


class HandEdits(unittest.TestCase):
    """What a person's editor does to the file, undone by one rewrite."""

    KB_TEXT = (FIXTURES / "career" / "kb.ttl").read_bytes().decode("utf-8")

    def rewrite(self, text):
        parsed = io.parse_text(text, "career/kb.ttl")
        return writer.write(parsed.quads, "kb")

    def test_a_windows_editor_crlf_bom_and_tabs(self):
        edited = "﻿" + self.KB_TEXT.replace("\n    ", "\n\t").replace("\n", "\r\n")
        self.assertEqual(self.rewrite(edited), self.KB_TEXT)

    def test_a_subject_written_in_two_places_becomes_one_block(self):
        text = PFX + ('k:met_team j:subject "engineers led" .\n\n'
                      'k:met_team.v1 j:of k:met_team ; j:value 6 ; j:confidence j:measured ; '
                      'j:provenance j:confirmed .\n\nk:met_team j:unit "engineers" .\n')
        out = self.rewrite(text)
        self.assertIn('k:met_team j:subject "engineers led" ; j:unit "engineers" .', out)
        self.assertEqual(out.count("k:met_team j:"), 1)

    def test_sparql_style_prefixes_full_iris_and_stray_prefixes(self):
        text = ('PREFIX j: <tag:jsk,2026:ns#>\n@prefix ex: <http://example.com/> .\n'
                '<tag:jsk,2026:id/met_team> j:subject "engineers led" ; '
                '<tag:jsk,2026:ns#unit> "engineers" .\n')
        out = self.rewrite(text)
        self.assertIn('k:met_team j:subject "engineers led" ; j:unit "engineers" .', out)
        self.assertNotIn("example.com", out)
        self.assertTrue(out.startswith(PFX))


class NeverUnparseable(unittest.TestCase):
    """The writer's output always parses back to the same triples, whatever it is given
    that it does not refuse outright."""

    def round_trip(self, triples, kind="kb"):
        out = writer.write(triples, kind)
        back = io.parse_text(out, f"{kind}.ttl", kind)
        return out, {(str(q.subject), str(q.predicate), str(q.object)) for q in back.quads}

    def test_a_triple_given_twice_is_written_once(self):
        t = ox.Triple(ox.NamedNode(O.K + "met_x"), ox.NamedNode(O.J + "subject"), ox.Literal("A"))
        out, _ = self.round_trip([t, t])
        self.assertIn('k:met_x j:subject "A" .', out)

    def test_a_language_tagged_value_with_a_newline(self):
        t = ox.Triple(ox.NamedNode(O.K + "met_x"), ox.NamedNode(O.J + "subject"),
                      ox.Literal("a\nb", language="en"))
        _, back = self.round_trip([t])
        self.assertEqual(back, {(str(t.subject), str(t.predicate), str(t.object))})

    def test_an_iri_from_a_namespace_the_file_does_not_declare(self):
        t = ox.Triple(ox.NamedNode(O.K + "met_x"), ox.NamedNode(O.J + "note"),
                      ox.NamedNode(O.OP + "set"))
        out, back = self.round_trip([t])
        self.assertNotIn("op:", out)
        self.assertEqual(back, {(str(t.subject), str(t.predicate), str(t.object))})


class SubjectLines(unittest.TestCase):
    def test_findings_can_point_into_the_fixture(self):
        parsed = io.parse(FIXTURES / "career" / "kb.ttl")
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8").split("\n")
        line = parsed.lines[O.K + "met_team.v1"]
        self.assertTrue(text[line - 1].startswith("k:met_team.v1 "))
        self.assertEqual(parsed.lines[O.C + "kafka"],
                         text.index("c:kafka j:isA c:event-driven-architecture .") + 1)


if __name__ == "__main__":
    unittest.main()
