"""The format's one definition is internally consistent."""
import re
import unittest

from jsk.graph import ontology as O


class OntologyTests(unittest.TestCase):
    def test_every_predicate_is_documented_and_typed(self):
        for cls in O.CLASSES:
            for p in cls.preds.values():
                with self.subTest(cls=cls.name, pred=p.name):
                    self.assertTrue(p.doc.strip())
                    self.assertIn(p.card, ("1", "?", "*", "+"))
                    self.assertIsInstance(p.obj, (O.Lit, O.Enum, O.Ref, O.Concept))
                    if isinstance(p.obj, O.Enum):
                        self.assertIn(p.obj.name, O.ENUMS)
                    if isinstance(p.obj, O.Ref) and p.obj.classes != O.ANY:
                        for target in p.obj.classes:
                            self.assertIn(target, O.BY_NAME)
                    if p.section:
                        self.assertIn(p.section, O.SECTIONS[cls.kinds[0]])

    def test_enums_are_nonempty_and_valid_local_names(self):
        for name, values in O.ENUMS.items():
            with self.subTest(enum=name):
                self.assertTrue(values)
                self.assertEqual(len(values), len(set(values)))
                for v in values:
                    self.assertRegex(v, r"^[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9]$")

    def test_prefixes_are_unique_and_every_class_has_a_home(self):
        prefixes = [c.prefix for c in O.CLASSES if c.prefix]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for cls in O.CLASSES:
            with self.subTest(cls=cls.name):
                self.assertTrue(cls.kinds)
                for kind in cls.kinds:
                    self.assertIn(kind, O.SECTIONS)
                    self.assertTrue(cls.section is None or cls.section in O.SECTIONS[kind])

    def test_each_head_class_lives_in_its_file_kind(self):
        for kind, name in O.HEADS.items():
            self.assertIn(kind, O.BY_NAME[name].kinds)

    def test_no_predicate_appears_twice_in_a_class(self):
        for cls in O.CLASSES:
            names = [p.name for line in cls.lines for p in line]
            self.assertEqual(len(names), len(set(names)), cls.name)

    def test_claim_classes_carry_provenance(self):
        for cls in O.CLASSES:
            has_claim = any(p.claim for p in cls.preds.values())
            with self.subTest(cls=cls.name):
                self.assertEqual("provenance" in cls.preds, cls.claims)
                if has_claim:
                    self.assertTrue(cls.claims, "a class with claim predicates needs provenance")

    def test_seniority_is_one_list(self):
        """The ranking's order and the ontology's enum were two copies of one list, one
        in the Markdown reader. There is one now, and the reader uses it too."""
        from jsk import kbindex
        from jsk.graph import scoring
        self.assertIs(scoring.SENIORITY, O.ENUMS["seniority"])
        self.assertIs(kbindex.SENIORITY, O.ENUMS["seniority"])
        self.assertEqual(O.ENUMS["seniority"][0], "architecture-ownership")

    def test_the_graph_does_not_import_the_markdown_reader(self):
        """Release N+1 deletes kbindex.py with `jsk migrate`. The career's ranking and
        its experience query imported it, so deleting it would have broken `jsk match`
        and `jsk kb query experience`."""
        import subprocess
        import sys

        from fixtures import child_env
        code = ("import sys\n"
                "import jsk.graph.queries, jsk.graph.named, jsk.graph.match, jsk.graph.kbcli\n"
                "print('jsk.kbindex' in sys.modules)\n")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             env=child_env())
        self.assertEqual(out.stdout.strip(), "False", out.stdout + out.stderr)

    def test_provenance_matches_the_renderer(self):
        from jsk.resume.build import PROVENANCE_RANK
        self.assertEqual(set(PROVENANCE_RANK), set(O.ENUMS["provenance"]))

    def test_class_of(self):
        cases = {O.K + "kb": "KB", O.K + "person": "Person", O.K + "prj_clinical_events": "Project",
                 O.K + "met_team": "Metric", O.K + "met_team.v2": "MetricVersion",
                 O.K + "prj_x.v1": None, O.K + "zzz_x": None, O.K + "Prj_x": None,
                 O.C + "kafka": "Concept", "https://example.com/x": None}
        for iri, name in cases.items():
            with self.subTest(iri=iri):
                self.assertEqual(O.class_of(iri), name)

    def test_kind_of(self):
        self.assertEqual(O.kind_of("career/kb.ttl"), "kb")
        self.assertEqual(O.kind_of("applications\\a\\posting.ttl"), "posting")
        self.assertEqual(O.kind_of("change.trig"), "changeset")
        self.assertIsNone(O.kind_of("career/notes.ttl"))

    def test_norm(self):
        self.assertEqual(O.norm("  Azure  AI\tFoundry "), "azure-ai-foundry")

    def test_ontology_does_not_import_pyoxigraph(self):
        import subprocess
        import sys
        code = "import sys, jsk.graph.ontology; print('pyoxigraph' in sys.modules)"
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "False", out.stderr)

    def test_the_id_pattern_refuses_what_it_should(self):
        self.assertTrue(re.fullmatch(O.ID, "ach_clinical_events_led_migration"))
        self.assertTrue(O.POSITIONAL.search("ach_clinical_events_2"))
        self.assertFalse(O.CONCEPT_SLUG.fullmatch("SQL_server"))


if __name__ == "__main__":
    unittest.main()
