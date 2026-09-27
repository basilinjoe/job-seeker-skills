"""gaps.ttl and gaps.md: the derived assessment with gaps.txt folded in - checked against the
match, written only when nothing FAILs, frozen once the application is sent."""
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.graph import assessment as A
from jsk.graph import gapsbuild as B
from jsk.graph import match as M
from jsk.graph import ontology as O
from jsk.graph import queries as Q
from jsk.graph import store
from jsk.graph.gapsderive import derive

FIXTURES = Path(__file__).parent / "match_fixtures"
TODAY = datetime.date(2026, 9, 24)
SECTIONS = ["# Eligibility", "# Requirements", "# Ranking", "# Where this falls short",
            "# New terms", "# Questions"]


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = Path(self.tmp)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)

    def app(self, posting="contoso"):
        return self.root / "applications" / posting

    def load(self):
        return store.load(self.root, vocabulary=self.root / "vocabulary.ttl")

    def result(self, s, posting="contoso", flag_k8s=False):
        r = M.result(s, O.K + "post_" + posting, TODAY, 3)
        if flag_k8s:
            # prj_events' confirmed kubernetes bullet says AKS, never Nomad: the flag fires.
            r["requirements"] = [dict(q, asked="Container platforms (AKS, Nomad)")
                                 if q["id"] == "k:req_contoso_k8s" else q
                                 for q in r["requirements"]]
        return r

    def build(self, txt=None, posting="contoso", today=TODAY, flag_k8s=False):
        if txt is not None:
            (self.app(posting) / "gaps.txt").write_text(txt, encoding="utf-8", newline="\n")
        s = self.load()
        return B.build(str(self.app(posting)), s, self.result(s, posting, flag_k8s), today)

    def fails(self, found):
        return [t for sev, t, _ in found if sev == "FAIL"]

    def read(self, name, posting="contoso"):
        return (self.app(posting) / name).read_text(encoding="utf-8")

    # --- the agent-free path -----------------------------------------------------------

    def test_with_no_gaps_txt_the_derived_assessment_is_written_and_loads_clean(self):
        written, found = self.build()
        self.assertEqual((sorted(Path(w).name for w in written), found),
                         (["gaps.md", "gaps.ttl"], []))
        s = self.load()
        name = "applications/contoso/gaps.ttl"
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual([f.text() for f in s.findings if f.file == name], [])
        # SPARQL reaches it: one verdict per contoso requirement.
        self.assertEqual(len(s.select(Q.PRE + "SELECT ?v WHERE { ?x j:verdict ?v }")), 10)

    def test_gaps_md_has_every_section_in_order_and_no_slot(self):
        self.build()
        md = self.read("gaps.md")
        at = [md.find(s) for s in SECTIONS]
        self.assertNotIn(-1, at)
        self.assertEqual(at, sorted(at))
        self.assertNotIn(A.MARK, md)
        self.assertIn(B.HEADER, md)
        self.assertTrue(md.startswith("---\ntype: Gap Assessment"))
        self.assertIn("fit: partial", md)
        self.assertIn("Not judged", md)
        # With no analyst, where it falls short is still said: the required rows left short.
        self.assertIn("- **.NET** (required): unevidenced - carried by prj_events (tag), "
                      "prj_identity (tag) only", md)

    def test_a_rebuild_is_byte_identical_and_keeps_its_day(self):
        self.build()
        ttl, md = self.read("gaps.ttl"), self.read("gaps.md")
        self.build(today=TODAY + datetime.timedelta(days=3))
        self.assertEqual((self.read("gaps.ttl"), self.read("gaps.md")), (ttl, md))

    # --- the overlay folded in ---------------------------------------------------------

    def test_a_lowered_verdict_stands_with_its_reason(self):
        written, found = self.build("fit: poor\neligibility: meets it - based in Pune\n"
                                    "k8s | partial | one AKS cluster | never on call\n"
                                    "short: no on-call ownership\nask: Who ran it?\n")
        self.assertEqual(found, [])
        ttl, md = self.read("gaps.ttl"), self.read("gaps.md")
        self.assertIn('k:vrd_contoso_k8s j:assessment k:gap_contoso', ttl)
        self.assertIn("j:matched j:satisfied ; j:verdict j:partial", ttl)
        self.assertIn('j:shortfall "one AKS cluster | never on call"', ttl)
        self.assertIn("j:fit j:poor", ttl)
        self.assertIn("| K8s | required | partial (match: satisfied) | prj_events | "
                      "one AKS cluster \\| never on call |", md)
        self.assertIn("meets it - based in Pune", md)
        self.assertIn("- no on-call ownership", md)
        self.assertEqual(md.split("# Questions\n\n", 1)[1], "- Who ran it?\n")

    def test_with_no_gaps_txt_a_flagged_row_waits_and_the_assessment_is_written(self):
        """Found on the real corpus: four of 24 postings had a flagged row, and the path with
        no agent wrote nothing for them. A flag asks the analyst; until there is one, the
        derived assessment stands and says the row is waiting."""
        written, found = self.build(flag_k8s=True)
        self.assertEqual((len(written), found), (2, []))
        self.assertIn("| satisfied | prj_events | flagged, not yet reviewed: names Nomad; the "
                      "evidence never does |", self.read("gaps.md"))

    def test_a_flagged_row_must_be_answered_and_keep_is_marked(self):
        _, found = self.build("", flag_k8s=True)
        self.assertEqual(self.fails(found), [
            "k8s is flagged (names Nomad; the evidence never does) and gaps.txt has no row "
            "for it"])
        self.assertFalse((self.app() / "gaps.ttl").exists())
        written, found = self.build("k8s | keep\n", flag_k8s=True)
        self.assertEqual(found, [])
        self.assertIn("| satisfied | prj_events | kept after review: names Nomad; the evidence "
                      "never does |", self.read("gaps.md"))
        self.assertIn("j:flag j:listed-names", self.read("gaps.ttl"))

    # --- what FAILs, and writes nothing ------------------------------------------------

    def assert_fails(self, txt, *expected, posting="contoso"):
        written, found = self.build(txt, posting=posting)
        self.assertEqual(written, [])
        self.assertFalse((self.app(posting) / "gaps.ttl").exists())
        self.assertEqual(self.fails(found), list(expected))

    def test_an_unknown_slug_fails(self):
        self.assert_fails("kotlin | unsatisfied | none\n",
                          "gaps.txt line 1: 'kotlin' is not a requirement of this posting")

    def test_a_raised_verdict_fails(self):
        self.assert_fails("angular | satisfied | the portal\n",
                          "gaps.txt line 1: angular: satisfied, above the match's unsatisfied",
                          posting="fabrikam")
        self.assert_fails("dotnet | satisfied | tagged\n",
                          "gaps.txt line 1: dotnet: satisfied, above the match's unevidenced")

    def test_indeterminate_may_not_become_partial_but_an_implicit_row_is_open(self):
        self.assert_fails("go | partial | the language\n",
                          "gaps.txt line 1: go: partial, above the match's indeterminate")
        _, found = self.build("mentoring | unsatisfied | never mentored anyone\n")
        self.assertEqual(found, [])

    def test_a_lowered_verdict_needs_its_reason(self):
        self.assert_fails("k8s | partial\n",
                          "gaps.txt line 1: k8s is lowered to partial with no reason")

    def test_keep_on_a_row_no_flag_asked_about_fails(self):
        self.assert_fails("k8s | keep\n",
                          "gaps.txt line 1: `keep` on k8s, which no flag asked about")

    def test_an_unfilled_slot_fails(self):
        self.assert_fails("fit: partial\neligibility: <!-- jsk: judge it -->\n",
                          "gaps.txt line 2: unfilled slot")

    def test_a_gaps_txt_that_does_not_parse_fails(self):
        written, found = self.build("fit: brilliant\n")
        self.assertEqual(written, [])
        self.assertEqual(len(self.fails(found)), 1)
        self.assertIn("line 1", self.fails(found)[0])

    # --- WARNs: the row is still honoured, or the match is ---------------------------

    def test_a_row_that_repeats_the_match_warns(self):
        _, found = self.build("dotnet | unevidenced | tagged only\n")
        self.assertEqual([(s, t) for s, t, _ in found],
                         [("WARN", "gaps.txt line 1: dotnet says unevidenced, which is the "
                                   "match's verdict already")])

    def test_when_the_match_moves_the_row_is_named(self):
        s = self.load()
        d = derive(self.result(s), s)
        # The match used to say satisfied for .NET, the analyst lowered it to partial, and the
        # career has since lost the evidence: the match's unevidenced stands.
        o = A.parse("dotnet | partial | only one service\n")
        found = B.check(d, o, "", {"dotnet": "satisfied"})
        self.assertEqual([(sev, t) for sev, t, _ in found],
                         [("WARN", "gaps.txt line 1: the match now says unevidenced; the row "
                                   "lowers nothing - delete it")])
        self.assertEqual(next(v.verdict for v in B.fold(d, o, {"dotnet": "satisfied"}).verdicts
                              if v.row.slug == "dotnet"), "unevidenced")
        # The match rose from unsatisfied to satisfied under a lowering to partial.
        o = A.parse("k8s | partial | one cluster\n")
        found = B.check(d, o, "", {"k8s": "unsatisfied"})
        self.assertEqual([(sev, t) for sev, t, _ in found],
                         [("WARN", "gaps.txt line 1: the match now says satisfied; you lowered "
                                   "it to partial because one cluster - still true?")])

    # --- frozen at submission ----------------------------------------------------------

    def test_a_sent_application_is_frozen(self):
        self.build()
        before = self.read("gaps.ttl")
        (self.app() / "application.ttl").write_text(
            "@prefix j: <tag:jsk,2026:ns#> .\n@prefix k: <tag:jsk,2026:id/> .\n"
            "@prefix c: <tag:jsk,2026:concept/> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n# == Application\n\n"
            'k:app_contoso j:posting k:post_contoso ; j:submitted "2026-09-20"^^xsd:date .\n',
            encoding="utf-8", newline="\n")
        written, found = self.build("k8s | partial | changed my mind\n")
        self.assertEqual(written, [])
        self.assertEqual(self.fails(found), ["applications/contoso: sent on 2026-09-20 - "
                                             "gaps.ttl and gaps.md are frozen"])
        self.assertEqual(self.read("gaps.ttl"), before)


if __name__ == "__main__":
    unittest.main()
