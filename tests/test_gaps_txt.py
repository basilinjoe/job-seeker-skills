"""gaps.txt, the analyst's overlay: what the parser reads, and what it refuses from the text
alone - then, in `Outcome`, the one outcome gapsbuild gives each row against the match, over
every combination a row can meet. The build around them is test_gaps_build's.
"""
import itertools
import tempfile
import unittest
from pathlib import Path

from jsk.graph import assessment as A
from jsk.graph import gapsbuild as B
from jsk.graph.gapsderive import Derived, Row


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

    def test_read_refuses_a_file_that_is_not_utf8(self):
        from jsk.graph import io

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gaps.txt"
            path.write_bytes(b"fit: poor\n# \x93curly\x94\n")
            with self.assertRaises(io.NotUtf8) as cm:
                A.read(path)
            self.assertIn("gaps.txt: not UTF-8", str(cm.exception))


# --- one outcome per row (Ruling 7 of the 2026-09-28 review) -------------------------------

VERDICTS = ("satisfied", "partial", "unevidenced", "unsatisfied", "indeterminate")
RANK = {"satisfied": 3, "partial": 2, "unevidenced": 1, "unsatisfied": 0}

# Each outcome, as (severity, words only its text holds).
KEEP_UNASKED = ("WARN", "which no flag asks about now")
RESTATED = ("WARN", "which is the match's verdict already")
MOVED_BELOW = ("WARN", "the row lowers nothing - delete it")
RAISED = ("FAIL", "above the match's")
NO_REASON = ("FAIL", "with no reason")
MOVED_ABOVE = ("WARN", "still true?")


def above(said, matched):
    """Does `said` claim more than `matched`? Written from gapsbuild.raises' docstring, not
    by calling it: against an implicit row nothing is a raise, `indeterminate` claims
    nothing, and against `indeterminate` a satisfied or a partial claims more."""
    if matched is None or said == "indeterminate":
        return False
    if matched == "indeterminate":
        return said in ("satisfied", "partial")
    return RANK[said] > RANK[matched]


def expected(said, matched, flagged, reason, was):
    """Ruling 7, one case per return, in its order. `was` is the match's verdict when
    gaps.ttl was last written, or None."""
    if said == "keep":
        return None if flagged else KEEP_UNASKED
    if said == (matched or "indeterminate"):
        return RESTATED
    if above(said, matched):
        return MOVED_BELOW if was is not None and not above(said, was) else RAISED
    if not reason:
        return NO_REASON
    if matched is not None and was is not None and above(matched, was):
        return MOVED_ABOVE
    return None


def derived(matched, flagged, slug="r"):
    return Derived("k:post_t", "t", (Row(
        f"k:req_t_{slug}", slug, "R", "implicit" if matched is None else "required", "matched",
        matched, (), "why the match says so", ("listed-names",) if flagged else (),
        "names Nomad; the evidence never does" if flagged else None),), "partial", ())


class Outcome(unittest.TestCase):
    """gapsbuild.check gives each gaps.txt row exactly one outcome, whatever it meets. Before
    the review, `keep` on a row whose flag had cleared FAILed (finding 4), and a row
    restating the match with no reason FAILed "no reason" beside its "delete the row" WARN
    (finding 5): the order of a chain of `if`s decided, and two could fire."""

    CASES = list(itertools.product(("keep", *VERDICTS), (*VERDICTS, None), (False, True),
                                   (False, True), (None, *VERDICTS)))

    def outcome(self, said, matched, flagged, reason, was):
        d = derived(matched, flagged)
        o = A.parse(f"r | {said} | because\n" if reason else f"r | {said}\n")
        found = B.check(d, o, "", {} if was is None else {"r": was})
        return d, o, [(sev, text) for sev, text, _ in found]

    def test_every_combination_has_exactly_the_one_outcome_ruling_7_gives_it(self):
        self.assertEqual(len(self.CASES), 864)
        for case in self.CASES:
            with self.subTest(said=case[0], matched=case[1], flagged=case[2], reason=case[3],
                              was=case[4]):
                _, _, found = self.outcome(*case)
                want = expected(*case)
                if want is None:
                    self.assertEqual(found, [])
                else:
                    self.assertEqual(len(found), 1, found)
                    self.assertEqual(found[0][0], want[0], found)
                    self.assertIn(want[1], found[0][1])

    def test_fold_honours_the_row_only_where_check_let_it_lower(self):
        """What check says of a row, fold does: a row check named as the match's verdict
        (keep, restated, moved below) folds to the match's; a lowering folds to the row."""
        for case in self.CASES:
            want = expected(*case)
            if want is not None and want[0] == "FAIL":
                continue                                # fold is not called past a FAIL
            said, matched = case[0], case[1]
            d, o, _ = self.outcome(*case)
            v = B.fold(d, o, {} if case[4] is None else {"r": case[4]}).verdicts[0]
            with self.subTest(case=case):
                honoured = want in (None, MOVED_ABOVE) and said != "keep"
                self.assertEqual(v.verdict, said if honoured else (matched or "indeterminate"))

    def test_finding_4_keep_on_a_row_whose_flag_has_cleared_warns(self):
        _, _, found = self.outcome("keep", "satisfied", False, False, None)
        self.assertEqual(found, [("WARN", "gaps.txt line 1: `keep` on r, which no flag asks "
                                          "about now")])

    def test_finding_5_a_restated_verdict_with_no_reason_only_warns(self):
        _, _, found = self.outcome("unevidenced", "unevidenced", False, False, None)
        self.assertEqual(found, [("WARN", "gaps.txt line 1: r says unevidenced, which is the "
                                          "match's verdict already")])

    def test_an_unknown_slug_is_its_one_fail(self):
        found = B.check(derived("satisfied", False), A.parse("kotlin | partial\n"))
        self.assertEqual([(s, t) for s, t, _ in found],
                         [("FAIL", "gaps.txt line 1: 'kotlin' is not a requirement of this "
                                   "posting")])

    def test_an_unfilled_slot_is_named_once_by_the_slot_fail(self):
        text = f"r | {A.MARK} keep, or lower -->\n"
        found = B.check(derived("satisfied", True), A.parse(text), text)
        self.assertEqual([(s, t) for s, t, _ in found],
                         [("FAIL", "gaps.txt line 1: unfilled slot")])


if __name__ == "__main__":
    unittest.main()
