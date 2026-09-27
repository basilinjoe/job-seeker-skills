"""gaps.txt, the analyst's overlay: what the parser reads, and what it refuses from the text
alone. The rules that need the match (a verdict above it, `keep` on an unflagged row) are
gapsbuild's, and tested there.
"""
import tempfile
import unittest
from pathlib import Path

from jsk.graph import assessment as A


class Parse(unittest.TestCase):
    def refuses(self, text, *needles):
        with self.assertRaises(A.AssessmentError) as cm:
            A.parse(text)
        for needle in needles:
            self.assertIn(needle, str(cm.exception))
        return str(cm.exception)

    def test_a_full_overlay(self):
        o = A.parse("# a comment\n\nfit: partial\neligibility: India-based, as the role is\n"
                    "vector_dbs | unevidenced | pgvector only\nmentoring | keep\n"
                    "short: vector databases\nsurplus: Rust\nask: Have you used Pinecone?\n")
        self.assertEqual((o.fit, o.eligibility), ("partial", "India-based, as the role is"))
        self.assertEqual(o.rows, [A.Row(5, "vector_dbs", "unevidenced", "pgvector only"),
                                  A.Row(6, "mentoring", "keep", "")])
        self.assertEqual((o.short, o.surplus, o.ask),
                         (["vector databases"], ["Rust"], ["Have you used Pinecone?"]))

    def test_an_empty_file_is_an_empty_overlay(self):
        self.assertEqual(A.parse(""), A.Overlay())

    def test_repeated_short_surplus_and_ask_keep_file_order(self):
        o = A.parse("short: b\nask: two?\nshort: a\nsurplus: y\nask: one?\nsurplus: x\n"
                    "short: c\n")
        self.assertEqual((o.short, o.surplus, o.ask), (["b", "a", "c"], ["y", "x"],
                                                       ["two?", "one?"]))

    def test_a_pipe_in_a_reason_stays_in_the_reason(self):
        o = A.parse("grpc | partial | one service | internal only\n")
        self.assertEqual(o.rows, [A.Row(1, "grpc", "partial", "one service | internal only")])

    def test_a_pipe_in_a_keyed_value_stays_keyed(self):
        o = A.parse("short: gRPC | one service\neligibility: yes | remote\n")
        self.assertEqual((o.short, o.eligibility, o.rows), (["gRPC | one service"],
                                                            "yes | remote", []))

    def test_an_empty_keyed_value_is_skipped(self):
        o = A.parse("fit:\neligibility:   \nsurplus:\nshort: \t\nask:\n")
        self.assertEqual(o, A.Overlay())

    def test_crlf_and_indentation(self):
        o = A.parse("  fit: strong\r\n\tgrpc | partial | one  \r\n")
        self.assertEqual((o.fit, o.rows), ("strong", [A.Row(2, "grpc", "partial", "one")]))

    def test_slots_are_text_here_and_checked_by_gapsbuild(self):
        o = A.parse("fit: <!-- jsk: strong / partial / poor -->\n"
                    "eligibility: <!-- jsk: judge eligibility -->\n"
                    "grpc | <!-- jsk: keep, or lower: partial / unevidenced / unsatisfied --> |\n"
                    "short: <!-- jsk: the unmet -->\n")
        self.assertEqual(o.fit, "<!-- jsk: strong / partial / poor -->")
        self.assertEqual(o.eligibility, "<!-- jsk: judge eligibility -->")
        self.assertEqual(o.rows[0].verdict,
                         "<!-- jsk: keep, or lower: partial / unevidenced / unsatisfied -->")
        self.assertEqual(o.short, ["<!-- jsk: the unmet -->"])

    def test_every_verdict_name_and_keep(self):
        names = ("keep", "satisfied", "partial", "unevidenced", "unsatisfied", "indeterminate")
        o = A.parse("".join(f"r{i} | {v} | why\n" for i, v in enumerate(names)))
        self.assertEqual(tuple(r.verdict for r in o.rows), names)

    # -- refusals, each naming the line

    def test_refuses_fit_twice(self):
        self.refuses("fit: strong\n\nfit: poor\n", "line 3", "`fit:` is given twice", "line 1")

    def test_refuses_fit_twice_even_when_the_first_was_empty(self):
        self.refuses("fit:\nfit: poor\n", "line 2", "twice")

    def test_refuses_eligibility_twice(self):
        self.refuses("eligibility: yes\neligibility: no\n", "line 2", "`eligibility:`")

    def test_refuses_a_repeated_slug(self):
        self.refuses("grpc | partial | a\n# x\ngrpc | unsatisfied | b\n",
                     "line 3", "`grpc`", "line 1")

    def test_refuses_a_row_of_one_field(self):
        self.refuses("fit: strong\ngrpc\n", "line 2", "slug | verdict | reason")

    def test_refuses_an_unknown_key_as_a_bad_row(self):
        self.refuses("title: Staff Engineer\n", "line 1")

    def test_refuses_a_fit_outside_the_enum(self):
        self.refuses("fit: excellent\n", "line 1", "'excellent'", "strong, partial, poor")

    def test_refuses_an_unknown_verdict(self):
        self.refuses("grpc | missing | nothing\n", "line 1", "'missing'", "keep")

    def test_refuses_an_empty_verdict(self):
        self.refuses("grpc |\n", "line 1", "verdict ''")

    def test_refuses_a_verdict_in_the_wrong_case(self):
        self.refuses("grpc | Partial | one service\n", "line 1", "'Partial'")

    def test_refuses_a_bad_slug(self):
        for slug in ("gRPC", "req_x-y", "req x", "_x", ""):
            with self.subTest(slug=slug):
                self.refuses(f"{slug} | partial | why\n", "line 1", "slug")

    def test_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gaps.txt"
            path.write_text("fit: poor\n", encoding="utf-8")
            self.assertEqual(A.read(path).fit, "poor")


if __name__ == "__main__":
    unittest.main()
