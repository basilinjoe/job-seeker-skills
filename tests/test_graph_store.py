"""Loading a workspace: every file its own graph, types derived, the closure built.

The closure numbers are worked by hand from the fixture's edges, not read back from the
code: 16 concepts give 16 zero-hop paths, and the 4 isA/partOf edges give 4 one-hop
paths; nothing chains, so there are no two-hop paths.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from test_graph_shapes import load

from jsk.graph import store

FIXTURES = Path(__file__).parent / "graph_fixtures"
PRE = f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"


def paths(s, hops=None):
    where = f"FILTER(?h = {hops})" if hops is not None else ""
    rows = s.select(PRE + f"SELECT ?a ?b ?h ?i WHERE {{ GRAPH j:derived {{ ?p a j:Path ; "
                          f"j:from ?a ; j:to ?b ; j:hops ?h ; j:implied ?i }} {where} }}")
    return sorted((r["a"].value.rsplit("/", 1)[-1], r["b"].value.rsplit("/", 1)[-1],
                   int(r["h"].value), r["i"].value == "true") for r in rows)


class Loading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load(FIXTURES)

    def test_every_file_is_its_own_graph(self):
        self.assertEqual(sorted(self.s.parsed), [
            "applications/acme-platform-engineer/application.ttl",
            "applications/acme-platform-engineer/posting.ttl",
            "career/kb.ttl", "career/log.ttl", "vocabulary.ttl"])
        self.assertEqual(self.s.file_of(O.K + "req_acme_platform_engineer_kubernetes"),
                         "applications/acme-platform-engineer/posting.ttl")

    def test_types_are_derived_from_the_prefix(self):
        rows = self.s.select(PRE + "SELECT ?t WHERE { GRAPH j:derived { "
                                   "k:met_event_latency.v2 a ?t } }")
        self.assertEqual([r["t"].value for r in rows], [O.J + "MetricVersion"])

    def test_derived_triples_are_not_in_any_file_graph(self):
        rows = self.s.select(PRE + "SELECT ?g WHERE { GRAPH ?g { ?s a j:Path } "
                                   "FILTER(?g != j:derived) }")
        self.assertEqual(rows, [])

    def test_a_kb_concept_extends_a_shipped_one(self):
        # c:kafka is typed in the shipped vocabulary; kb.ttl adds an edge to it.
        self.assertIn(("kafka", "event-driven-architecture", 1, False), paths(self.s, 1))

    def test_the_closure(self):
        self.assertEqual(len(paths(self.s, 0)), 16)
        self.assertEqual(paths(self.s, 1), [
            ("aged-care", "healthcare", 1, False),
            ("azure-ai-foundry", "azure", 1, False),
            ("bicep", "azure", 1, False),
            ("kafka", "event-driven-architecture", 1, False)])
        self.assertEqual(paths(self.s, 2), [])


class Closure(unittest.TestCase):
    """Two hops and no more, one way, and an implies edge marks every path it is on."""

    def load(self, edges):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "career").mkdir()
        text = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES) + edges
        (tmp / "career" / "kb.ttl").write_text(text, encoding="utf-8")
        try:
            return store.load(tmp, vocabulary=None)
        finally:
            shutil.rmtree(tmp)

    def test_hop_limit_and_direction(self):
        s = self.load("c:a a j:Technology ; j:isA c:b .\nc:b a j:Capability ; j:partOf c:c .\n"
                      "c:c a j:Capability ; j:isA c:d .\nc:d a j:Capability .\n")
        got = [(a, b, h) for a, b, h, _ in paths(s) if h]
        self.assertEqual(got, [("a", "b", 1), ("a", "c", 2), ("b", "c", 1), ("b", "d", 2),
                               ("c", "d", 1)])      # a->d is three hops: not a path

    def test_implies_marks_the_path(self):
        s = self.load("c:a a j:Capability ; j:implies c:b .\nc:b a j:Capability ; j:isA c:c .\n"
                      "c:c a j:Capability .\n")
        self.assertEqual([p for p in paths(s) if p[2]],
                         [("a", "b", 1, True), ("a", "c", 2, True), ("b", "c", 1, False)])


class Discovery(unittest.TestCase):
    def test_a_missing_file_is_absent_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = store.load(tmp)
            self.assertEqual(sorted(s.parsed), ["vocabulary.ttl"])
            self.assertEqual(s.findings, [])

    def test_a_folder_name_with_a_space_or_accent_loads(self):
        """A hand-made application folder is named however its owner likes; a graph name
        is an IRI, which cannot hold a space - so the loader must encode it."""
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
            apps = Path(tmp) / "applications"
            (apps / "acme-platform-engineer").rename(apps / "Acme Platform é")
            s = load(tmp)
            self.assertEqual([f.text() for f in s.findings], [])
            self.assertEqual(s.file_of(O.K + "app_acme_platform_engineer"),
                             "applications/Acme Platform é/application.ttl")

    def test_a_root_with_glob_characters_still_finds_its_applications(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs [2026]"
            shutil.copytree(FIXTURES, root)
            s = load(root)
            self.assertIn("applications/acme-platform-engineer/posting.ttl", s.parsed)
            self.assertEqual([f.text() for f in s.findings], [])

    def test_a_file_on_another_drive_is_named_not_a_crash(self):
        """os.path.relpath raises across Windows drives - the shipped vocabulary in
        site-packages on C:, the workspace on D:."""
        from unittest import mock
        with mock.patch("os.path.relpath", side_effect=ValueError("path is on mount 'C:'")):
            self.assertEqual(store.file_name("C:/py/jsk/data/vocabulary.ttl", "D:/career"),
                             "vocabulary.ttl")

    def test_graph_returns_a_files_own_triples_for_the_writer(self):
        """As parsed, not read back out of Oxigraph, which stores numbers by value:
        "8.40" would come back as 8.4 and the rewrite would change the person's file."""
        from jsk.graph import writer
        s = load(FIXTURES)
        text = (FIXTURES / "career" / "kb.ttl").read_bytes().decode("utf-8")
        self.assertEqual(writer.write(s.graph("career/kb.ttl"), "kb"), text)

    def test_files_outside_the_layout_are_not_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
            (Path(tmp) / "career" / "notes.ttl").write_text("not turtle at all", encoding="utf-8")
            self.assertEqual(load(tmp).findings, [])


if __name__ == "__main__":
    unittest.main()
