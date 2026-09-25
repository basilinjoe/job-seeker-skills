"""select.py: what a resume for one posting selects, worked by hand in the plan
(docs/superpowers/plans/2026-09-25-export-from-match.md, "Fixture")."""
import contextlib
import datetime
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk import cli
from jsk.gates import validate_urs
from jsk.graph import export
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
    quotes = [line.split('j:quote "')[1].split('"')[0] for line in posting.splitlines()
              if 'j:quote "' in line]
    Path(app, "posting.md").write_bytes(("# Contoso\n\n" + "\n".join(quotes) + "\n").encode())
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


def career_plus(root, text):
    kb = Path(root, "career", "kb.ttl")
    kb.write_bytes(kb.read_bytes() + text.encode())


def asking(*labels, need="required"):
    return POSTING.split("k:req_sel_k8s")[0] + "".join(
        f'k:req_p_{n} j:posting k:post_contoso_select ; j:asked "{a}" ;\n'
        f'    j:necessity j:{need} ; j:quote "{a} is asked for." .\n'
        for n, a in enumerate(labels))


class NoCover(unittest.TestCase):
    """--cover 1 cannot carry five required requirements spread over three projects: the
    selection goes by ranking, and a project placed 3rd (cap 2) carrying three of them must
    still show all three - or say which it could not."""
    def test_every_carried_requirement_keeps_a_bullet(self):
        root = workspace(self, asking("K8s", "Entra ID", "Python", "Rust", "SQL Server"))
        career_plus(root, """
k:prj_x j:name "X" ; j:position k:pos_harbour_engineer ; j:strength 1 ; j:recency 2015 ;
    j:uses c:python, c:rust, c:sql-server ; j:noneQuantified true ; j:provenance j:confirmed .
k:ach_x1 j:project k:prj_x ; j:rank 1 ; j:text "Wrote Python." ; j:shows c:python ;
    j:provenance j:confirmed .
k:ach_x2 j:project k:prj_x ; j:rank 2 ; j:text "Wrote Rust." ; j:shows c:rust ;
    j:provenance j:confirmed .
k:ach_x3 j:project k:prj_x ; j:rank 3 ; j:text "Wrote SQL." ; j:shows c:sql-server ;
    j:provenance j:confirmed .
""")
        sel = SEL.select(S.load(root), POST, TODAY, 1)
        self.assertIn(O.K + "prj_x", sel.projects)
        self.assertEqual(ids(sel.bullets[O.K + "prj_x"]), ["ach_x1", "ach_x2", "ach_x3"])
        self.assertEqual(sel.gaps, [])


class Reworded(unittest.TestCase):
    """The author rewords the flagship bullet, which makes it inferred, and names it."""
    def setUp(self):
        root = workspace(self)
        kb = Path(root, "career", "kb.ttl")
        text = kb.read_text(encoding="utf-8")
        at = text.index("k:ach_events_latency")
        end = text.index("k:ach_events_team")
        kb.write_bytes((text[:at] + text[at:end].replace("j:confirmed", "j:inferred")
                        + text[end:]).encode())
        self.sel = SEL.select(S.load(root), POST, TODAY, 3,
                              extra=[O.K + "ach_events_latency"])

    def test_it_is_placed_by_what_it_shows(self):
        self.assertEqual(ids(self.sel.bullets[O.K + "prj_events"])[0], "ach_events_latency")

    def test_it_is_a_confirmation_not_a_shortfall(self):
        k8s = [g for g in self.sel.gaps if g.requirement == "K8s"]
        self.assertEqual([g.kind for g in k8s], ["unconfirmed"])
        self.assertIn("k:ach_events_latency (inferred) is selected", k8s[0].detail)


class Implied(unittest.TestCase):
    def test_a_bullet_showing_what_only_implies_it_is_named(self):
        sel = SEL.select(S.load(workspace(self, asking("IaC", need="preferred"))),
                         POST, TODAY, 3)
        self.assertIn("k:ach_events_terraform shows c:terraform, which only implies",
                      sel.gaps[0].detail)


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


class Exported(unittest.TestCase):
    def setUp(self):
        self.store = S.load(workspace(self))
        self.doc = export.urs(self.store, today=TODAY,
                              selection=SEL.select(self.store, POST, TODAY, 3))
        self.view = self.doc["views"][0]

    def test_only_the_selected_projects(self):
        self.assertEqual(sorted(p["id"] for p in self.doc["projects"]),
                         ["prj_events", "prj_identity"])

    def test_the_view_orders_bullets_and_skills(self):
        inc = {i["ref"]: i.get("achievements") for i in self.view["include"]}
        self.assertEqual(inc["prj_events"],
                         ["ach_events_latency", "ach_events_terraform", "ach_events_team"])
        self.assertEqual(self.view["skills"], ["skill_kubernetes", "skill_dotnet"])

    def test_it_validates(self):
        self.assertEqual(list(validate_urs.check_doc(self.doc).fails), [])

    def test_byte_identical(self):
        store = S.load(self.store.root)
        again = export.urs(store, today=TODAY, selection=SEL.select(store, POST, TODAY, 3))
        self.assertEqual(json.dumps(again), json.dumps(self.doc))


class Command(unittest.TestCase):
    def setUp(self):
        self.root = workspace(self)
        self.posting = os.path.join(self.root, "applications", "contoso-select", "posting.ttl")

    def kb(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue(), err.getvalue()

    def test_from_match_prints_the_record_and_the_gaps(self):
        code, out, err = self.kb("export", "--urs", "--from-match", self.posting,
                                 "--today", "2026-09-25")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["views"][0]["skills"][0], "skill_kubernetes")
        self.assertIn("GAP   tag-only    SQL Server (required)", err)

    def test_with_out_the_gaps_go_to_stdout(self):
        dest = os.path.join(self.root, "applications", "contoso-select", "resume.json")
        code, out, _ = self.kb("export", "--urs", "--from-match", self.posting, "--out", dest)
        self.assertEqual(code, 0)
        self.assertIn("GAP   uncovered   Rust (required): nothing carries it", out)
        self.assertTrue(os.path.isfile(dest))

    def test_select_adds_to_the_match(self):
        code, out, _ = self.kb("export", "--urs", "--from-match", self.posting,
                               "--select", "prj_game")
        self.assertEqual(code, 0)
        self.assertIn("prj_game", [p["id"] for p in json.loads(out)["projects"]])

    def test_a_project_added_with_no_confirmed_bullet_is_named(self):
        code, _, err = self.kb("export", "--urs", "--from-match", self.posting,
                               "--select", "prj_data")
        self.assertEqual(code, 0)
        self.assertIn("NOTE  k:prj_data has no confirmed bullet", err)

    def test_a_posting_outside_applications_is_a_usage_error(self):
        stray = os.path.join(self.root, "posting.ttl")
        shutil.copy(self.posting, stray)
        self.assertEqual(self.kb("export", "--urs", "--from-match", stray)[0], 2)

    def test_a_posting_from_another_workspace_is_a_usage_error(self):
        other = workspace(self)
        theirs = os.path.join(other, "applications", "contoso-select", "posting.ttl")
        self.assertEqual(self.kb("export", "--urs", "--from-match", theirs)[0], 2)

    def test_cover_and_today_need_from_match(self):
        self.assertEqual(self.kb("export", "--urs", "--cover", "2")[0], 2)
        self.assertEqual(self.kb("export", "--urs", "--today", "2026-09-25")[0], 2)

    def test_bad_cover_and_today(self):
        for flag, value in (("--cover", "0"), ("--cover", "x"), ("--today", "soon")):
            self.assertEqual(self.kb("export", "--urs", "--from-match", self.posting,
                                     flag, value)[0], 2, (flag, value))

    def test_a_broken_posting_refuses(self):
        Path(self.posting).write_bytes(b"this is not turtle")
        self.assertEqual(self.kb("export", "--urs", "--from-match", self.posting)[0], 1)


if __name__ == "__main__":
    unittest.main()
