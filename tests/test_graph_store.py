"""Loading a workspace: every record graph out of career/store/, types derived, the closure
built - and the import's front end, which reads a workspace still laid out as files.

The closure numbers are worked by hand from the fixture's edges, not read back from the
code: 16 concepts give 16 zero-hop paths, and the 4 isA/partOf edges give 4 one-hop
paths; nothing chains, so there are no two-hop paths.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from storekit import seed
from test_graph_shapes import load

from jsk.graph import db, legacy, store
from jsk.graph import ontology as O
from jsk.graph import record as R
from jsk.graph.io import GraphError

FIXTURES = Path(__file__).parent / "graph_fixtures"
PRE = f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
APP = "applications/acme-platform-engineer"


def paths(s, hops=None):
    where = f"FILTER(?h = {hops})" if hops is not None else ""
    rows = s.select(PRE + f"SELECT ?a ?b ?h ?i WHERE {{ GRAPH j:derived {{ ?p a j:Path ; "
                          f"j:from ?a ; j:to ?b ; j:hops ?h ; j:implied ?i }} {where} }}")
    return sorted((r["a"].value.rsplit("/", 1)[-1], r["b"].value.rsplit("/", 1)[-1],
                   int(r["h"].value), r["i"].value == "true") for r in rows)


def stored_copy(case, root=None, edit=None):
    """The fixture workspace copied (to `root`, or a temp folder), `edit(root)` applied to
    its files, and put in career/store/."""
    root = Path(root or tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, root, True)
    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
    if edit:
        edit(root)
    seed(root)
    return root


class Loading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        shutil.copytree(FIXTURES, cls.tmp, dirs_exist_ok=True)
        seed(cls.tmp)
        cls.s = load(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_every_graph_is_its_own_graph(self):
        self.assertTrue(self.s.stored)
        self.assertEqual(sorted(self.s.parsed), [f"{APP}/application", f"{APP}/posting", "kb",
                                                 "log", "vocabulary"])
        self.assertEqual(self.s.file_of(O.K + "req_acme_platform_engineer_kubernetes"),
                         f"{APP}/posting")

    def test_a_graph_in_memory_has_the_iri_it_has_in_the_store(self):
        rows = self.s.select(PRE + "SELECT DISTINCT ?g WHERE { GRAPH ?g { k:kb ?p ?o } "
                                   "FILTER(?g != j:derived) }")
        self.assertEqual([r["g"].value for r in rows], [db.graph_iri("kb")])

    def test_types_are_derived_from_the_prefix(self):
        rows = self.s.select(PRE + "SELECT ?t WHERE { GRAPH j:derived { "
                                   "k:met_event_latency.v2 a ?t } }")
        self.assertEqual([r["t"].value for r in rows], [O.J + "MetricVersion"])

    def test_derived_triples_are_not_in_any_record_graph(self):
        rows = self.s.select(PRE + "SELECT ?g WHERE { GRAPH ?g { ?s a j:Path } "
                                   "FILTER(?g != j:derived) }")
        self.assertEqual(rows, [])

    def test_a_kb_concept_extends_a_shipped_one(self):
        # c:kafka is typed in the shipped vocabulary; kb adds an edge to it.
        self.assertIn(("kafka", "event-driven-architecture", 1, False), paths(self.s, 1))

    def test_the_closure(self):
        self.assertEqual(len(paths(self.s, 0)), 16)
        self.assertEqual(paths(self.s, 1), [
            ("aged-care", "healthcare", 1, False),
            ("azure-ai-foundry", "azure", 1, False),
            ("bicep", "azure", 1, False),
            ("kafka", "event-driven-architecture", 1, False)])
        self.assertEqual(paths(self.s, 2), [])

    def test_the_store_and_the_files_it_came_from_load_alike(self):
        # The import is lossless: the same triples, the same findings (none), the same
        # closure - so a person's record reads the same the day after `jsk kb load`.
        files = load(FIXTURES)
        for name in self.s.parsed:
            self.assertEqual(sorted(map(str, self.s.graph(name))),
                             sorted(map(str, files.graph(name))), name)
        self.assertEqual(paths(self.s), paths(files))


class Closure(unittest.TestCase):
    """Two hops and no more, one way, and an implies edge marks every path it is on."""

    def load(self, edges):
        text = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES) + edges
        with tempfile.TemporaryDirectory() as tmp:
            return store.load(tmp, vocabulary=None, texts={R.KB: text})

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


class StandIns(unittest.TestCase):
    """What a write validates before it writes: `graphs` in place of the store's, `texts`
    in place of a graph - so the record a command is about to write is checked whole."""

    def setUp(self):
        self.root = stored_copy(self)

    def test_a_graph_stands_in_for_the_stores_and_none_drops_one(self):
        before = load(self.root)
        posting = list(before.graph(f"{APP}/posting"))
        s = store.load(self.root, vocabulary=self.root / "vocabulary.ttl",
                       graphs={f"{APP}/posting": posting[:-1], f"{APP}/application": None})
        self.assertNotIn(f"{APP}/application", s.parsed)
        self.assertEqual(len(s.graph(f"{APP}/posting")), len(posting) - 1)
        self.assertTrue(s.stored)

    def test_a_text_wins_over_the_store_and_over_a_graph(self):
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8").replace(
            'j:size "1001-5000"', 'j:sise "1001-5000"')
        s = store.load(self.root, vocabulary=self.root / "vocabulary.ttl",
                       texts={R.KB: text}, graphs={R.KB: []})
        [f] = [f for f in s.findings if f.rule == "closed"]
        # A text has lines, so its finding names one: the write is refused where it was made.
        self.assertRegex(f.text(), r"^kb:\d+ k:org_meridian ")

    def test_a_file_name_is_taken_for_its_graph(self):
        # `career/kb.ttl` and `kb` name one graph: a caller that still says the file does not
        # load a second career beside the first.
        text = (FIXTURES / "career" / "kb.ttl").read_text(encoding="utf-8")
        s = store.load(self.root, vocabulary=self.root / "vocabulary.ttl",
                       texts={"career/kb.ttl": text})
        self.assertIn(R.KB, s.parsed)
        self.assertNotIn("career/kb.ttl", s.parsed)
        self.assertEqual([f.text() for f in s.findings], [])

    def test_the_career_is_each_ids_home(self):
        # The career loads first, whatever the names sort to: an id defined again in an
        # application is reported there, and the career stays its home.
        s = load(self.root)
        self.assertEqual(list(s.parsed)[:2], [R.KB, R.LOG])
        self.assertEqual(s.file_of(O.K + "person"), R.KB)


class Discovery(unittest.TestCase):
    def test_a_workspace_with_nothing_in_it_is_absent_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = store.load(tmp)
            self.assertEqual(sorted(s.parsed), ["vocabulary"])
            self.assertEqual(s.findings, [])
            self.assertEqual(R.state(s).kind, "missing")

    def test_a_career_still_in_files_is_refused_with_the_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
            with self.assertRaises(GraphError) as e:
                store.load(tmp)
        self.assertEqual(e.exception.file, "career/kb.ttl")
        self.assertIn("jsk kb load .", e.exception.fix)

    def test_an_empty_store_holds_no_career(self):
        with tempfile.TemporaryDirectory() as tmp:
            R.write_graphs(tmp, {"kb": None}, create=True)
            s = store.load(tmp)
            self.assertTrue(s.stored)
            self.assertEqual(sorted(s.parsed), ["vocabulary"])
            self.assertEqual(R.state(s).kind, "missing")

    def test_a_store_that_will_not_open_is_named_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, db.STORE_DIR))
            Path(tmp, db.STORE_DIR, "CURRENT").write_text("garbage\n", encoding="utf-8")
            with self.assertRaises(GraphError) as e:
                store.load(tmp)
        self.assertEqual(e.exception.file, "career/store/")
        self.assertIn("could not be opened", str(e.exception))
        self.assertTrue(e.exception.fix)

    def test_a_folder_name_with_a_space_or_accent_loads(self):
        """A hand-made application folder is named however its owner likes; a graph name
        is an IRI, which cannot hold a space - so the store must encode it, and give it
        back decoded."""
        def rename(root):
            apps = root / "applications"
            (apps / "acme-platform-engineer").rename(apps / "Acme Platform é")
        s = load(stored_copy(self, edit=rename))
        self.assertEqual([f.text() for f in s.findings], [])
        self.assertEqual(s.file_of(O.K + "app_acme_platform_engineer"),
                         "applications/Acme Platform é/application")

    def test_a_root_with_glob_characters_still_finds_its_applications(self):
        # The import globs for applications/*/posting.ttl, and "[2026]" is a character
        # class: unescaped, it would import a career with no applications at all.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs [2026]"
            s = load(stored_copy(self, root))
            self.assertIn(f"{APP}/posting", s.parsed)
            self.assertEqual([f.text() for f in s.findings], [])

    def test_a_file_on_another_drive_is_named_not_a_crash(self):
        """os.path.relpath raises across Windows drives - the shipped vocabulary in
        site-packages on C:, the workspace on D:."""
        from unittest import mock
        with mock.patch("os.path.relpath", side_effect=ValueError("path is on mount 'C:'")):
            self.assertEqual(store.file_name("C:/py/jsk/data/vocabulary.ttl", "D:/career"),
                             "vocabulary.ttl")
            self.assertEqual(store.graph_name("C:/py/jsk/data/vocabulary.ttl", "D:/career"),
                             "vocabulary")

    def test_graph_returns_the_triples_as_loaded(self):
        """A stored graph's triples as the store keeps them - numbers by value, `4.50` is
        4.5 - and a file's as parsed: the import's report of each rewrite compares the two,
        and a writer never rewrites a number it was not asked to."""
        def baseline(root):
            kb = root / "career" / "kb.ttl"
            kb.write_text(kb.read_text(encoding="utf-8").replace(
                "k:met_team.v1 j:of k:met_team ;", "k:met_team.v1 j:of k:met_team ; "
                "j:baseline 4.50 ;"), encoding="utf-8", newline="\n")

        def value(s):
            return [q.object.value for q in s.graph(R.KB) if q.predicate.value == O.J + "baseline"
                    and q.subject.value == O.K + "met_team.v1"]
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
            baseline(Path(tmp))
            self.assertEqual(value(load(tmp)), ["4.50"])
            _, _, rewrites = legacy.read_workspace(tmp)
            self.assertEqual([(n, kept.value) for n, _, kept in rewrites], [(R.KB, "4.5")])
        self.assertEqual(value(load(stored_copy(self, edit=baseline))), ["4.5"])

    def test_the_import_reads_only_the_record_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
            (Path(tmp) / "career" / "notes.ttl").write_text("not turtle at all", encoding="utf-8")
            imported, record, _ = legacy.read_workspace(tmp)
            self.assertEqual(sorted(record), [f"{APP}/application", f"{APP}/posting", "kb",
                                              "log"])
            self.assertEqual([f for f in imported.findings if f.rule == "syntax"], [])


class Paths(unittest.TestCase):
    """rel and inside never raise across Windows drives, where relpath and commonpath do."""

    def test_rel_and_inside_on_one_drive(self):
        root = os.path.abspath("ws")
        self.assertEqual(store.rel(os.path.join(root, "career", "kb.ttl"), root), "career/kb.ttl")
        self.assertTrue(store.inside(os.path.join(root, "career"), root))
        self.assertFalse(store.inside(os.path.dirname(root), root))

    def test_graph_names(self):
        for path, name in (("career/kb.ttl", "kb"), ("career/log.ttl", "log"),
                           (f"{APP}/posting.ttl", f"{APP}/posting"),
                           (f"{APP}/gaps.ttl", f"{APP}/gaps"), ("kb", "kb"),
                           ("career/notes.ttl", "career/notes.ttl")):
            self.assertEqual(store.short_name(path), name, path)

    @unittest.skipUnless(os.name == "nt", "only Windows has drives")
    def test_another_drive_answers_rather_than_raising(self):
        self.assertFalse(store.inside("D:\\x", "C:\\y"))
        self.assertEqual(store.rel("D:\\x\\a.ttl", "C:\\y"), "D:/x/a.ttl")
        self.assertEqual(store.file_name("D:\\x\\a.ttl", "C:\\y"), "a.ttl")


if __name__ == "__main__":
    unittest.main()
