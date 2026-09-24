"""The shipped vocabulary: technologies only, clean, and honest about what is ambiguous.

It ships to every user, so a wrong edge in it is a wrong match for everybody. These tests
hold it to the rules on its own, with no knowledge base beside it.
"""
import tempfile
import unittest
from pathlib import Path

import jsk
from jsk.graph import io, store, writer
from jsk.graph import ontology as O

SHIPPED = Path(jsk.__file__).parent / "data" / "vocabulary.ttl"

# Words that really do name two shipped technologies, and so are asked about, never
# guessed. Empty today; a label added here needs a comment saying what the two are.
AMBIGUOUS = set()


class TheShippedVocabulary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            cls.s = store.load(tmp)          # an empty workspace: the shipped file alone

    def test_it_loads_with_no_findings_bar_the_allowed_clashes(self):
        left = [f.text() for f in self.s.findings
                if not (f.rule == "label-clash" and any(f"'{w}'" in f.detail for w in AMBIGUOUS))]
        self.assertEqual(left, [])

    def test_it_is_canonical(self):
        text = SHIPPED.read_bytes().decode("utf-8")
        self.assertEqual(writer.write(io.parse_text(text, "vocabulary.ttl").quads, "vocabulary"),
                         text)

    def test_it_is_big_enough_to_matter(self):
        concepts = {q.subject.value for q in io.parse(SHIPPED).quads}
        self.assertGreaterEqual(len(concepts), 60)

    def test_every_wall_holds(self):
        rows = self.s.select(f"""PREFIX j: <{O.J}>
            SELECT ?a ?b WHERE {{ ?a j:distinct ?b }}""")
        self.assertTrue(rows)
        for r in rows:
            a, b = r["a"].value, r["b"].value
            crossing = self.s.select(f"""PREFIX j: <{O.J}>
                SELECT ?p WHERE {{ GRAPH j:derived {{
                  {{ ?p j:from <{a}> ; j:to <{b}> }} UNION {{ ?p j:from <{b}> ; j:to <{a}> }} }} }}""")
            self.assertEqual(crossing, [], f"{a} and {b} are distinct, yet joined")

    def test_no_shipped_label_is_a_word_with_another_meaning(self):
        # "ADO" is ADO.NET in a .NET advert as often as Azure DevOps; "Lambda" is any
        # anonymous function. A shipped label is matched against every advert everyone
        # pastes, so a word that means two things there is an overclaim waiting.
        labels = {O.norm(q.object.value) for q in io.parse(SHIPPED).quads
                  if q.predicate.value in (O.J + "label", O.J + "former")}
        self.assertEqual(labels & {"ado", "lambda"}, set())

    def test_no_shipped_edge_is_a_judgement(self):
        # Helm-only work is not Kubernetes work: charts are packaged for a cluster
        # somebody else may run. Close to fact ships; judgement stays in a person's kb.ttl.
        edges = {(q.subject.value, q.object.value) for q in io.parse(SHIPPED).quads
                 if q.predicate.value in (O.J + "isA", O.J + "partOf")}
        self.assertNotIn((O.C + "helm", O.C + "kubernetes"), edges)

    def test_the_labels_people_write_resolve(self):
        index = {}
        for r in self.s.select(f"PREFIX j: <{O.J}> SELECT ?c ?l WHERE {{ ?c j:label|j:former ?l }}"):
            index.setdefault(O.norm(r["l"].value), set()).add(r["c"].value)
        for label, concept in (("K8s", "kubernetes"), ("Dot Net", "dotnet"),
                               ("Azure AD", "entra-id"), ("MSSQL", "sql-server"),
                               ("Postgres", "postgresql"), ("C#", "csharp")):
            with self.subTest(label=label):
                self.assertEqual(index[O.norm(label)], {O.C + concept})


if __name__ == "__main__":
    unittest.main()
