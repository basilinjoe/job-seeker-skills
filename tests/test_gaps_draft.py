"""`jsk match --draft-gaps`: code writes gaps.txt holding only what needs judgement.

The draft is only worth writing if it is the overlay the parser reads - otherwise the analyst
is back to fixing lines by hand - and if every open judgement is a slot `--gaps` FAILs on.
Everything the match already knows stays out: an unflagged requirement has no row.
"""
import tempfile
import unittest
from pathlib import Path

from jsk.graph import assessment as A
from jsk.graph import gapsdraft as G
from jsk.graph import store
from jsk.graph.gapsderive import Derived, Row

FIXTURES = Path(__file__).parent / "match_fixtures"
ADVERT = FIXTURES / "applications" / "contoso" / "posting.md"


def row(slug, matched="satisfied", flag_text=None, asked=None):
    return Row(id=f"k:req_contoso_{slug}", slug=slug, asked=asked or slug.upper(),
               necessity="required", state="matched", matched=matched,
               evidence=("k:prj_events",), basis="confirmed by prj_events",
               flags=("listed-names",) if flag_text else (), flag_text=flag_text)


DERIVED = Derived(
    posting="k:post_contoso", stem="contoso", fit="partial",
    rows=(row("k8s"),
          row("vector_dbs", flag_text="names Pinecone, Milvus; the evidence never does",
              asked="Vector databases (Pinecone, Weaviate, Milvus)"),
          row("terraform", matched="partial"),
          row("ai_tools", flag_text="names Cursor; the evidence never does",
              asked="Gemini, Cursor, and Claude"),
          row("mentoring", matched=None)),
    questions=("Is there work that shows .NET Framework?", "Did the K8s work run in production?"))


class Draft(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = store.load(FIXTURES, vocabulary=FIXTURES / "vocabulary.ttl")
        cls.text = G.draft_gaps(DERIVED, cls.s, str(ADVERT))
        cls.overlay = A.parse(cls.text)

    def test_the_draft_is_an_overlay_the_parser_reads(self):
        self.assertIsInstance(self.overlay, A.Overlay)

    def test_one_row_per_flagged_requirement_and_none_for_the_others(self):
        self.assertEqual([r.slug for r in self.overlay.rows], ["vector_dbs", "ai_tools"])
        for r in self.overlay.rows:
            self.assertTrue(r.verdict.startswith(G.MARK), r)
            self.assertEqual(r.reason, "")

    def test_each_row_has_its_flag_as_a_comment_above_it(self):
        lines = self.text.split("\n")
        for r in self.overlay.rows:
            self.assertTrue(lines[r.line - 2].startswith("# "), lines[r.line - 2])
        self.assertEqual(lines[self.overlay.rows[0].line - 2],
                         "# Vector databases (Pinecone, Weaviate, Milvus): names Pinecone, "
                         "Milvus; the evidence never does")

    def test_the_verdict_slot_holds_no_pipe(self):
        """A `|` in the slot would split the row into more fields than the slot."""
        for line in self.text.split("\n"):
            if line.startswith("vector_dbs"):
                self.assertEqual(line.count("|"), 2, line)

    def test_fit_holds_the_default_as_a_value(self):
        self.assertEqual(self.overlay.fit, "partial")
        self.assertIn("\nfit: partial\n", self.text)

    def test_the_slots_are_exactly_the_judgements(self):
        """eligibility, one per flagged row, short, surplus and the blocking ask."""
        self.assertEqual(self.text.count(G.MARK), 1 + 2 + 1 + 1 + 1)
        self.assertEqual(sum(G.MARK in line for line in self.text.split("\n")), 6)
        self.assertTrue(self.overlay.eligibility.startswith(G.MARK))
        self.assertEqual(len(self.overlay.short), 1)
        self.assertEqual(len(self.overlay.surplus), 1)

    def test_no_flagged_rows_leaves_four_slots_and_no_rows(self):
        quiet = Derived("k:post_contoso", "contoso", (row("k8s"),), "strong", ())
        text = G.draft_gaps(quiet, self.s, str(ADVERT))
        self.assertEqual(text.count(G.MARK), 4)
        o = A.parse(text)
        self.assertEqual((o.rows, o.fit, len(o.ask)), ([], "strong", 1))

    def test_the_derived_questions_are_asks_after_the_blocking_slot(self):
        self.assertEqual(self.overlay.ask[1:], list(DERIVED.questions))
        self.assertTrue(self.overlay.ask[0].startswith(G.MARK + " blocking"))
        self.assertIn("# reword each ask to be said aloud", self.text)

    def test_a_question_with_a_newline_stays_one_ask(self):
        d = Derived("k:post_contoso", "contoso", (), "partial", ("Two\nlines?",))
        self.assertEqual(A.parse(G.draft_gaps(d, self.s, str(ADVERT))).ask[1:], ["Two lines?"])

    def test_the_head_says_what_the_file_is(self):
        head = self.text.split("\n\n")[0]
        self.assertTrue(all(line.startswith("#") for line in head.split("\n")), head)
        self.assertIn("--gaps", head)
        self.assertIn("gaps.ttl and gaps.md", head)
        self.assertIn("never raises", head)

    def test_eligibility_facts_are_comments_above_the_slot(self):
        lines = self.text.split("\n")
        at = next(i for i, x in enumerate(lines) if x.startswith("eligibility:"))
        block = lines[lines.index("# eligibility is judged against:"):at]
        self.assertTrue(all(x.startswith("#") for x in block), block)
        self.assertIn("#   location: not recorded", block)
        self.assertIn("#   advert: nothing it says is about eligibility", block)
        self.assertEqual(lines[at],
                         "eligibility: <!-- jsk: judge eligibility against the facts above -->")

    def test_decisions_drops_and_advert_eligibility_lines_are_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            advert = Path(tmp) / "posting.md"
            advert.write_text("Senior Developer at Fabrikam\n\n## Requirements\n\n"
                              "- Years of .NET Framework.\n- Origin CI, Kargo and WoK, our "
                              "internal tooling, which you will learn on the job over your first "
                              "quarter.\n- Must hold a UK work visa.\n", encoding="utf-8")
            (Path(tmp) / "decisions.txt").write_text(
                "company: Fabrikam\n\n# n | slug | asked | concepts | need\n"
                "2 | dotnet_framework | .NET Framework | - |\n3 | - | internal tooling\n"
                "4 | - | eligibility: judged under eligibility\n", encoding="utf-8")
            text = G.draft_gaps(DERIVED, self.s, str(advert))
        lines = text.split("\n")
        drops = [x for x in lines if x.startswith("# dropped advert line")]
        self.assertEqual(len(drops), 2, drops)
        self.assertTrue(drops[0].startswith("# dropped advert line 3: Origin CI, Kargo and WoK"),
                        drops)
        self.assertTrue(drops[0].endswith("… - internal tooling"), drops)
        self.assertEqual(drops[1], "# dropped advert line 4: Must hold a UK work visa. - "
                                   "eligibility: judged under eligibility")
        self.assertIn('#   advert: "Must hold a UK work visa."', lines)
        self.assertEqual([(r.slug, r.verdict) for r in A.parse(text).rows],   # comments only
                         [(r.slug, r.verdict) for r in self.overlay.rows])

    def test_no_decisions_file_is_a_legacy_posting_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = G.draft_gaps(DERIVED, self.s, str(Path(tmp) / "posting.md"))
        self.assertNotIn("# dropped", text)
        self.assertEqual(A.parse(text).fit, "partial")


if __name__ == "__main__":
    unittest.main()
