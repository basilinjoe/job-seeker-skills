"""The one outcome fold.check gives each row of the analyst's overlay against the match, over
every combination a row can meet (Ruling 7 of the 2026-09-28 review), and what fold.fold then
does with it.

The overlay was read from gaps.txt until 6.0 retired `jsk tailor match --gaps`
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2); its parser's tests went
with it, and what `assessment_review` refuses of a row it is sent is
tests/test_graph_native_apps.py's (Review). A graph-native review is folded by the same
check, its rows built here as review.overlay_of builds them; the messages still name a row
by its line, which domain/assessment/review.py restates by verdict.
"""
import itertools
import unittest

from jsk.domain.assessment import fold, overlay
from jsk.application.tailor import check_gaps
from jsk.domain.assessment.derive import Derived, Row


def overlaid(slug, said, reason=""):
    """An Overlay holding the one row `slug | said | reason`, as line 1."""
    return overlay.Overlay(rows=[overlay.Row(1, slug, said, reason)])


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
        return None if flagged else RESTATED           # on a flag it answers, as keep does
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
    """fold.check gives each overlay row exactly one outcome, whatever it meets. Before
    the review, `keep` on a row whose flag had cleared FAILed (finding 4), and a row
    restating the match with no reason FAILed "no reason" beside its "delete the row" WARN
    (finding 5): the order of a chain of `if`s decided, and two could fire."""

    CASES = list(itertools.product(("keep", *VERDICTS), (*VERDICTS, None), (False, True),
                                   (False, True), (None, *VERDICTS)))

    def outcome(self, said, matched, flagged, reason, was):
        d = derived(matched, flagged)
        o = overlaid("r", said, "because" if reason else "")
        found = fold.check(d, o, "", {} if was is None else {"r": was})
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
            v = fold.fold(d, o, {} if case[4] is None else {"r": case[4]}).verdicts[0]
            with self.subTest(case=case):
                honoured = want in (None, MOVED_ABOVE) and said != "keep"
                self.assertEqual(v.verdict, said if honoured else (matched or "indeterminate"))

    def test_only_an_answered_flag_is_kept_after_review(self):
        """A kept verdict renders "kept after review: <the flag>". On an unflagged row that
        read "kept after review: None"; on a flagged row restating the match it was left
        "flagged, not yet reviewed", and deleting the row as told then FAILed."""
        for case in self.CASES:
            want = expected(*case)
            if want is not None and want[0] == "FAIL":
                continue
            said, matched, flagged, reason = case[:4]
            d, o, _ = self.outcome(*case)
            v = fold.fold(d, o, {} if case[4] is None else {"r": case[4]}).verdicts[0]
            with self.subTest(case=case):
                self.assertEqual(v.kept, flagged and (
                    said == "keep" or (said == (matched or "indeterminate") and not reason)))
                shortfall = check_gaps.requirement_rows(fold.Assessment(d, "partial", None, (v,), (), (), ()))
                self.assertNotIn("None", shortfall[2])
                if want != MOVED_BELOW:     # a raise the career undid asks the flag again
                    self.assertNotIn(check_gaps.UNREVIEWED, shortfall[2])

    def test_no_advice_on_a_flagged_row_is_to_delete_it(self):
        """Deleting a flagged row FAILs "flagged and gaps.txt has no row for it"."""
        for case in self.CASES:
            if not case[2]:
                continue
            d = derived(case[1], True)
            o = overlaid("r", case[0], "because" if case[3] else "")
            found = fold.check(d, o, "", {} if case[4] is None else {"r": case[4]})
            with self.subTest(case=case):
                self.assertFalse([f for f in found if "delete" in f[2]], found)

    def test_finding_4_keep_on_a_row_whose_flag_has_cleared_warns(self):
        _, _, found = self.outcome("keep", "satisfied", False, False, None)
        self.assertEqual(found, [("WARN", "gaps.txt line 1: `keep` on r, which no flag asks "
                                          "about now")])

    def test_finding_5_a_restated_verdict_with_no_reason_only_warns(self):
        _, _, found = self.outcome("unevidenced", "unevidenced", False, False, None)
        self.assertEqual(found, [("WARN", "gaps.txt line 1: r says unevidenced, which is the "
                                          "match's verdict already")])

    def test_an_unknown_slug_is_its_one_fail(self):
        found = fold.check(derived("satisfied", False), overlaid("kotlin", "partial"))
        self.assertEqual([(s, t) for s, t, _ in found],
                         [("FAIL", "gaps.txt line 1: 'kotlin' is not a requirement of this "
                                   "posting")])

    def test_an_unfilled_slot_is_named_once_by_the_slot_fail(self):
        text = f"r | {overlay.MARK} keep, or lower -->\n"
        found = fold.check(derived("satisfied", True), overlaid("r", text.split(" | ")[1]),
                           text)
        self.assertEqual([(s, t) for s, t, _ in found],
                         [("FAIL", "gaps.txt line 1: unfilled slot")])


if __name__ == "__main__":
    unittest.main()
