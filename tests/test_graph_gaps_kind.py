"""The gaps graph as a record kind: laid out by the writer, loaded beside the posting,
validated like every other record graph - and a fault in one application's assessment
stops only that application's match."""
import shutil
import tempfile
import unittest
from pathlib import Path

import pyoxigraph as ox
from storekit import seed

from jsk.domain.matching import report
from jsk.domain import ontology as O
from jsk.adapters.compose import match
from jsk.adapters.compose import record
from jsk.domain.record.writer import write

FIXTURES = Path(__file__).parent / "match_fixtures"


def j(name):
    return ox.NamedNode(O.J + name)


def k(name):
    return ox.NamedNode(O.K + name)


def assessment(requirement="req_contoso_k8s", gap="gap_contoso"):
    """A gaps.ttl for contoso: its assessment and one verdict, as quads."""
    a, v = k(gap), k("vrd_" + requirement[len("req_"):])
    date = ox.Literal("2026-09-27", datatype=ox.NamedNode(O.XSD + "date"))
    return [ox.Quad(a, j("posting"), k("post_contoso")), ox.Quad(a, j("assessed"), date),
            ox.Quad(a, j("fit"), j("partial")),
            ox.Quad(a, j("questions"), ox.Literal("Which cluster?\nWho ran it?")),
            ox.Quad(v, j("assessment"), a), ox.Quad(v, j("requirement"), k(requirement)),
            ox.Quad(v, j("matched"), j("satisfied")), ox.Quad(v, j("verdict"), j("partial")),
            ox.Quad(v, j("flag"), j("listed-names")), ox.Quad(v, j("evidence"), k("prj_events")),
            ox.Quad(v, j("basis"), ox.Literal("confirmed on prj_events")),
            ox.Quad(v, j("shortfall"), ox.Literal("AKS only, never EKS | GKE"))]


class GapsKind(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def load(self):
        return record.load(self.root, vocabulary=self.root / "vocabulary.ttl")

    def put(self, quads, app="contoso"):
        """The assessment written into the store - seeded from the fixture first, so an
        edit a test made to its kb.ttl goes in with it."""
        from appkit import seed

        from jsk.infra.oxigraph import record as R
        if not (self.root / "career" / "store").exists():
            seed(self.root)
        R.write_graphs(str(self.root), {f"applications/{app}/gaps": quads})

    def test_kind_and_sections(self):
        self.assertEqual(O.kind_of("applications/x/gaps"), "gaps")
        self.assertEqual(O.class_of(O.K + "gap_contoso"), "Assessment")
        self.assertEqual(O.class_of(O.K + "vrd_contoso_k8s"), "Verdict")
        text = write(assessment(), "gaps")
        self.assertLess(text.index("# == Assessment"), text.index("# == Verdicts"))

    def test_a_written_assessment_loads_clean_and_round_trips(self):
        self.put(assessment())
        s = self.load()
        name = "applications/contoso/gaps"
        self.assertIn(name, s.parsed)
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual([f.text() for f in s.warns() if f.file == name], [])
        self.assertEqual(write(s.graph(name), "gaps"), write(assessment(), "gaps"))

    def test_a_dangling_requirement_fails_there_and_blocks_only_that_posting(self):
        self.put(assessment(requirement="req_contoso_gone"))
        fails = self.load().fails()
        self.assertEqual({(f.rule, f.file) for f in fails},
                         {("dangling", "applications/contoso/gaps")})
        self.assertTrue(all(report.blocks(f, "applications/contoso/") for f in fails))
        self.assertFalse(any(report.blocks(f, "applications/fabrikam/") for f in fails))

    def test_two_assessments_in_one_file_fail_the_head_rule(self):
        quads = assessment() + [q for q in assessment(gap="gap_contoso_two")
                                if q.subject == k("gap_contoso_two")]
        self.put(quads)
        self.assertIn("cardinality", {f.rule for f in self.load().fails()})

    def test_retired_evidence_is_not_a_warning(self):
        # A sent assessment keeps the project it cited; retiring that project later is not
        # a fault in the assessment, any more than in application.ttl's j:carried.
        kb = self.root / "career" / "kb.ttl"
        kb.write_text(kb.read_text(encoding="utf-8").replace(
            'k:prj_events j:name "Event platform" ;',
            'k:prj_events j:name "Event platform" ; j:retired "2026-09-01"^^xsd:date ;\n'
            '    j:reason "sold" ;'), encoding="utf-8", newline="\n")
        self.put(assessment())
        found = [f for f in self.load().warns() if f.rule == "retired-referenced"
                 and f.file == "applications/contoso/gaps"]
        self.assertEqual(found, [])


class ConfirmedTexts(unittest.TestCase):
    def test_only_live_confirmed_bullets_showing_the_concept(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        root = Path(tmp)
        shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
        kb = root / "career" / "kb.ttl"
        extra = "".join(
            f'\nk:ach_events_kafka_{slug} j:project k:prj_events ; j:rank {rank} ;\n'
            f'    j:text "{slug} Kafka." ; j:shows c:kafka ;{more}\n'
            f'    j:provenance j:{pv} .\n'
            for slug, rank, pv, more in (
                ("guess", 4, "inferred", ""), ("argued", 5, "disputed", ""),
                ("old", 6, "confirmed", ' j:retired "2026-01-01"^^xsd:date ; j:reason "gone" ;')))
        kb.write_text(kb.read_text(encoding="utf-8") + extra, encoding="utf-8", newline="\n")
        seed(root)
        s = record.load(root, vocabulary=root / "vocabulary.ttl")
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual(match.confirmed_texts(s, O.K + "prj_events", O.C + "kafka"),
                         ["Cut p95 event latency from 5 s to 400 ms on AKS with Kafka."])
        self.assertEqual(match.confirmed_texts(s, O.K + "prj_data", [O.C + "fastapi"]), [])


if __name__ == "__main__":
    unittest.main()
