"""The assessment (the gaps graph, printed - no gaps.md): the derived assessment with gaps.txt folded
in - checked against the match, written only when nothing FAILs, frozen once the
application is sent."""
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

import appkit
from appkit import seed

from jsk.domain.assessment import overlay
from jsk.domain.assessment import fold
from jsk.application.tailor import check_gaps
from jsk.adapters.cli.compose import tailor
from jsk.adapters.cli.compose import match
from jsk.adapters.cli import match as M_match
from jsk.domain import ontology as O
from jsk.infra.oxigraph import queries
from jsk.adapters.cli.compose import record
from jsk.adapters.cli.compose.tailor import derive

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
        seed(self.root)

    def app(self, posting="contoso"):
        return self.root / "applications" / posting

    def gaps(self, posting="contoso"):
        return f"applications/{posting}/gaps"

    def ttl(self, posting="contoso"):
        return appkit.text(self.root, self.gaps(posting))

    def assessed(self, posting="contoso"):
        return appkit.has(self.root, self.gaps(posting))

    def load(self):
        return record.load(self.root, vocabulary=self.root / "vocabulary.ttl")

    def result(self, s, posting="contoso", flag_k8s=False):
        r = match.result(s, O.K + "post_" + posting, TODAY, 3)
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
        written, found, self.shown = tailor.build(str(self.app(posting)), s,
                                                  self.result(s, posting, flag_k8s), today)
        return written, found

    def printed(self):
        """The assessment as `jsk tailor match` prints it: no gaps.md is written any more
        (Ruling 24 of the graph-native plan), so the text the person reads is the build's."""
        self.assertFalse((self.app() / "gaps.md").exists())
        return self.shown

    def fails(self, found):
        return [t for sev, t, _ in found if sev == "FAIL"]

    def read(self, name, posting="contoso"):
        return (self.app(posting) / name).read_text(encoding="utf-8")

    # --- the agent-free path -----------------------------------------------------------

    def test_with_no_gaps_txt_the_derived_assessment_is_written_and_loads_clean(self):
        written, found = self.build()
        self.assertEqual(([check_gaps.shown(w) for w in written], found),
                         ([self.gaps()], []))
        self.assertFalse((self.app() / "gaps.ttl").exists())
        s = self.load()
        name = self.gaps()
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual([f.text() for f in s.findings if f.file == name], [])
        # SPARQL reaches it: one verdict per contoso requirement.
        self.assertEqual(len(s.select(queries.PRE + "SELECT ?v WHERE { ?x j:verdict ?v }")), 10)

    def test_the_printed_assessment_has_every_section_in_order_and_no_slot(self):
        self.build()
        md = self.printed()
        at = [md.find(s) for s in SECTIONS]
        self.assertNotIn(-1, at)
        self.assertEqual(at, sorted(at))
        self.assertNotIn(overlay.MARK, md)
        self.assertIn(check_gaps.HEADER, md)
        self.assertTrue(md.startswith("---\ntype: Gap Assessment"))
        self.assertIn("fit: partial", md)
        self.assertIn("Not judged", md)
        # With no analyst, where it falls short is still said: the required rows left short.
        self.assertIn("- **.NET** (required): unevidenced - carried by prj_events (tag), "
                      "prj_identity (tag) only", md)

    def test_a_rebuild_is_identical_and_keeps_its_day(self):
        self.build()
        ttl, md = appkit.facts(self.root, self.gaps()), self.printed()
        self.build(today=TODAY + datetime.timedelta(days=3))
        self.assertEqual((appkit.facts(self.root, self.gaps()), self.printed()), (ttl, md))

    # --- the overlay folded in ---------------------------------------------------------

    def test_a_lowered_verdict_stands_with_its_reason(self):
        written, found = self.build("fit: poor\neligibility: meets it - based in Pune\n"
                                    "k8s | partial | one AKS cluster | never on call\n"
                                    "short: no on-call ownership\nask: Who ran it?\n")
        self.assertEqual(found, [])
        ttl, md = self.ttl(), self.printed()
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
        # One: the gaps graph. No gaps.md is written beside it.
        self.assertEqual((len(written), found), (1, []))
        self.assertIn("| satisfied | prj_events | flagged, not yet reviewed: names Nomad; the "
                      "evidence never does |", self.printed())

    def test_a_flagged_row_must_be_answered_and_keep_is_marked(self):
        _, found = self.build("", flag_k8s=True)
        self.assertEqual(self.fails(found), [
            "k8s is flagged (names Nomad; the evidence never does) and gaps.txt has no row "
            "for it"])
        self.assertFalse(self.assessed())
        written, found = self.build("k8s | keep\n", flag_k8s=True)
        self.assertEqual(found, [])
        self.assertIn("| satisfied | prj_events | kept after review: names Nomad; the evidence "
                      "never does |", self.printed())
        self.assertIn("j:flag j:listed-names", self.ttl())

    # --- what FAILs, and writes nothing ------------------------------------------------

    def assert_fails(self, txt, *expected, posting="contoso"):
        written, found = self.build(txt, posting=posting)
        self.assertEqual(written, [])
        self.assertFalse(self.assessed(posting))
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

    def test_keep_on_a_row_no_flag_asks_about_warns_and_the_match_stands(self):
        """Finding 4 of the 2026-09-28 review: this FAILed, so a flag the career had since
        cleared blocked the build. `keep` is the match's verdict, which is what is written."""
        written, found = self.build("k8s | keep\n")
        self.assertEqual(len(written), 1)               # the gaps graph; no gaps.md
        self.assertEqual([(s, t) for s, t, _ in found],
                         [("WARN", "gaps.txt line 1: `keep` on k8s, which no flag asks about "
                                   "now")])
        self.assertIn("j:matched j:satisfied ; j:verdict j:satisfied", self.ttl())

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

    def test_a_row_that_repeats_the_match_with_no_reason_only_warns(self):
        """Finding 5: this FAILed "no reason" beside the WARN telling it to delete the row."""
        written, found = self.build("dotnet | unevidenced\n")
        self.assertEqual(len(written), 1)               # the gaps graph; no gaps.md
        self.assertEqual([(s, t) for s, t, _ in found],
                         [("WARN", "gaps.txt line 1: dotnet says unevidenced, which is the "
                                   "match's verdict already")])

    def test_when_the_match_moves_the_row_is_named(self):
        s = self.load()
        d = derive(self.result(s), s)
        # The match used to say satisfied for .NET, the analyst lowered it to partial, and the
        # career has since lost the evidence: the match's unevidenced stands.
        o = overlay.parse("dotnet | partial | only one service\n")
        found = fold.check(d, o, "", {"dotnet": "satisfied"})
        self.assertEqual([(sev, t) for sev, t, _ in found],
                         [("WARN", "gaps.txt line 1: the match now says unevidenced; the row "
                                   "lowers nothing - delete it")])
        self.assertEqual(next(v.verdict for v in fold.fold(d, o, {"dotnet": "satisfied"}).verdicts
                              if v.row.slug == "dotnet"), "unevidenced")
        # The match rose from unsatisfied to satisfied under a lowering to partial.
        o = overlay.parse("k8s | partial | one cluster\n")
        found = fold.check(d, o, "", {"k8s": "unsatisfied"})
        self.assertEqual([(sev, t) for sev, t, _ in found],
                         [("WARN", "gaps.txt line 1: the match now says satisfied; you lowered "
                                   "it to partial because one cluster - still true?")])

    # --- files that are not UTF-8 -------------------------------------------------------

    # A Windows editor's cp1252 save: `\x93` is its opening curly quote, and not UTF-8.
    CP1252 = b"# the \x93overlay\x94, saved in a Windows editor\n"

    def match_gaps(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = M_match.main([str(self.app()), "--today", "2026-09-24",
                           "--gaps", str(self.app() / "gaps.txt")])
        return code, out.getvalue()

    def assert_fails_naming(self, name):
        code, out = self.match_gaps()
        self.assertEqual(code, 1, out)
        self.assertIn(f"FAIL  {name}", out)
        self.assertIn("UTF-8", out)
        self.assertNotIn("Traceback", out)
        self.assertFalse(self.assessed())

    def test_a_gaps_txt_that_is_not_utf8_fails_naming_it(self):
        (self.app() / "gaps.txt").write_bytes(b"fit: partial\n" + self.CP1252)
        self.assert_fails_naming("gaps.txt")

    def test_a_decisions_txt_that_is_not_utf8_fails_naming_it(self):
        (self.app() / "gaps.txt").write_bytes(b"fit: partial\n")
        (self.app() / "decisions.txt").write_bytes(b"company: Contoso\n" + self.CP1252)
        self.assert_fails_naming("decisions.txt")

    def test_a_posting_md_that_is_not_utf8_fails_naming_it(self):
        advert = self.app() / "posting.md"
        advert.write_bytes(advert.read_bytes() + self.CP1252)
        written, found = self.build()
        self.assertEqual(written, [])
        self.assertEqual([t[:len("posting.md: not UTF-8")] for t in self.fails(found)],
                         ["posting.md: not UTF-8"])

    # --- frozen at submission ----------------------------------------------------------

    def test_a_sent_application_is_frozen(self):
        self.build()
        before = appkit.facts(self.root, self.gaps())
        appkit.put(self.root, "applications/contoso/application",
                   'k:app_contoso j:posting k:post_contoso ; j:submitted "2026-09-20"^^xsd:date .\n')
        written, found = self.build("k8s | partial | changed my mind\n")
        self.assertEqual(written, [])
        self.assertEqual(self.fails(found), ["applications/contoso: sent on 2026-09-20 - "
                                             "its assessment and gaps.md are frozen"])
        self.assertEqual(appkit.facts(self.root, self.gaps()), before)


if __name__ == "__main__":
    unittest.main()
