"""select.py: what a resume for one posting selects, worked by hand in the plan
(docs/superpowers/plans/2026-09-25-export-from-match.md, "Fixture")."""
import datetime
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from jsk.graph import select as SEL
from jsk.graph import store as S

FIXTURES = Path(__file__).parent / "claims_fixtures"
TODAY = datetime.date(2026, 9, 25)
POST = O.K + "post_contoso_select"
POSTING = """@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

k:post_contoso_select j:company "Contoso" ; j:title "Platform Engineer" ;
    j:captured "2026-09-20"^^xsd:date ; j:advert "posting.md" .

k:req_sel_k8s j:posting k:post_contoso_select ; j:asked "K8s" ;
    j:necessity j:required ; j:quote "Production K8s required." .
k:req_sel_kafka j:posting k:post_contoso_select ; j:asked "Kafka" ;
    j:necessity j:required ; j:quote "Kafka is required." .
k:req_sel_python j:posting k:post_contoso_select ; j:asked "Python" ;
    j:necessity j:required ; j:quote "Python is required." .
k:req_sel_rust j:posting k:post_contoso_select ; j:asked "Rust" ;
    j:necessity j:required ; j:quote "Rust is required." .
k:req_sel_sqlserver j:posting k:post_contoso_select ; j:asked "SQL Server" ;
    j:necessity j:required ; j:quote "SQL Server is required." .
k:req_sel_team j:posting k:post_contoso_select ; j:asked "Team leadership" ;
    j:necessity j:preferred ; j:quote "Team leadership is a plus." .
k:req_sel_terraform j:posting k:post_contoso_select ; j:asked "Terraform" ;
    j:necessity j:required ; j:quote "Terraform is required." .
k:req_sel_widgets j:posting k:post_contoso_select ; j:asked "Quantum widgets" ;
    j:necessity j:required ; j:quote "Quantum widgets are required." .
"""


def workspace(test, posting=POSTING):
    root = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, root, True)
    shutil.copytree(FIXTURES / "career", os.path.join(root, "career"))
    app = os.path.join(root, "applications", "contoso-select")
    os.makedirs(app)
    Path(app, "posting.ttl").write_bytes(posting.encode())
    Path(app, "posting.md").write_bytes(b"# Contoso\n")
    return root


def ids(iris):
    return [i[len(O.K):] for i in iris]


class Selected(unittest.TestCase):
    def setUp(self):
        self.store = S.load(workspace(self))
        self.sel = SEL.select(self.store, POST, TODAY, 3)

    def test_projects_are_the_cover_then_what_carries_evidence(self):
        self.assertEqual(ids(self.sel.projects), ["prj_events", "prj_identity"])

    def test_a_strong_project_carrying_nothing_is_not_selected(self):
        self.assertNotIn(O.K + "prj_portal", self.sel.projects)

    def test_bullets_by_score_then_rank(self):
        self.assertEqual(ids(self.sel.bullets[O.K + "prj_events"]),
                         ["ach_events_latency", "ach_events_terraform", "ach_events_team"])
        self.assertEqual(ids(self.sel.bullets[O.K + "prj_identity"]),
                         ["ach_identity_events", "ach_identity_sso"])

    def test_skills_the_posting_asks_for_first(self):
        self.assertEqual(ids(self.sel.skills), ["skill_kubernetes", "skill_dotnet"])

    def test_gaps(self):
        self.assertEqual([(g.kind, g.requirement) for g in self.sel.gaps],
                         [("tag-only", "SQL Server"), ("unconfirmed", "Python"),
                          ("uncovered", "Rust"), ("unresolved", "Quantum widgets")])
        lines = [g.line() for g in self.sel.gaps]
        self.assertIn("k:prj_portal tags c:sql-server", lines[0])
        self.assertIn("k:ach_data_ingestion", lines[1])
        self.assertIn("inferred", lines[1])
        self.assertIn("nothing carries it", lines[2])
        self.assertTrue(lines[0].startswith("GAP   tag-only    SQL Server (required): "))

    def test_k8s_carried_with_evidence_is_no_gap(self):
        self.assertNotIn("K8s", [g.requirement for g in self.sel.gaps])
        self.assertNotIn("Terraform", [g.requirement for g in self.sel.gaps])

    def test_deterministic(self):
        again = SEL.select(S.load(self.store.root), POST, TODAY, 3)
        self.assertEqual(again, self.sel)


class Extra(unittest.TestCase):
    def setUp(self):
        self.store = S.load(workspace(self))

    def test_a_project_added_brings_its_first_bullet(self):
        sel = SEL.select(self.store, POST, TODAY, 3, extra=[O.K + "prj_game"])
        self.assertEqual(ids(sel.projects)[-1], "prj_game")
        self.assertEqual(ids(sel.bullets[O.K + "prj_game"]), ["ach_game_players"])

    def test_a_bullet_added_brings_exactly_itself(self):
        sel = SEL.select(self.store, POST, TODAY, 3, extra=[O.K + "ach_portal_frontend"])
        self.assertEqual(ids(sel.bullets[O.K + "prj_portal"]), ["ach_portal_frontend"])

    def test_an_id_already_selected_is_not_duplicated(self):
        sel = SEL.select(self.store, POST, TODAY, 3,
                         extra=[O.K + "prj_events", O.K + "ach_events_team"])
        self.assertEqual(ids(sel.projects), ["prj_events", "prj_identity"])
        self.assertEqual(len(sel.bullets[O.K + "prj_events"]), 3)


class Nothing(unittest.TestCase):
    def test_nothing_carried_selects_nothing_and_says_why(self):
        posting = POSTING.split("k:req_sel_k8s")[0] + (
            'k:req_sel_rust j:posting k:post_contoso_select ; j:asked "Rust" ;\n'
            '    j:necessity j:required ; j:quote "Rust is required." .\n')
        sel = SEL.select(S.load(workspace(self, posting)), POST, TODAY, 3)
        self.assertEqual(sel.projects, [])
        self.assertEqual([g.kind for g in sel.gaps], ["uncovered"])


class Pick(unittest.TestCase):
    def test_bands(self):
        self.assertEqual([SEL.band(n) for n in (1, 2, 3, 5, 6, 8, 9)],
                         [(5, 3), (5, 3), (2, 1), (2, 1), (1, 1), (1, 1), (1, 1)])

    def test_the_cover_beats_the_band(self):
        cands = [("a", 3, {"r1"}), ("b", 3, {"r2"}), ("c", 1, set())]
        self.assertEqual(SEL.pick(cands, {"r1", "r2"}, 1, 1), ["a", "b"])

    def test_greedy_takes_the_bullet_showing_most(self):
        cands = [("b", 6, {"r1", "r2"}), ("a", 3, {"r1"})]
        self.assertEqual(SEL.pick(cands, {"r1", "r2"}, 1, 1), ["b"])

    def test_fill_to_the_floor_with_non_scoring(self):
        cands = [("a", 3, {"r1"}), ("b", 0, set()), ("c", 0, set()), ("d", 0, set())]
        self.assertEqual(SEL.pick(cands, set(), 5, 3), ["a", "b", "c"])

    def test_cap_counts_the_cover(self):
        cands = [("a", 3, {"r1"}), ("b", 3, {"r2"}), ("c", 3, {"r3"})]
        self.assertEqual(SEL.pick(cands, {"r1", "r2"}, 2, 1), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
