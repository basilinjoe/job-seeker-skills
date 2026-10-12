"""A requirement that states a minimum in years is measured against the record's dates.

The rule pinned (2026-10-06, docs/ONTOLOGY.md `j:years`): "7+ years of Engineering
experience" names no concept, so posting_decide recorded it with none and assessment_derive
left it indeterminate for ever, until a run asked the person "how many years?" of a record
whose role dates answered it. With `years` the derive totals the months of the roles behind
the requirement's concepts (every role when it has none), overlaps once, and says satisfied
at years x 12 months, partial within a year under it, unsatisfied further under. The match's
own verdict is a ceiling; a requirement without `years` is derived as before.

The claims fixture's roles cover 131 months with overlaps counted once (2014-03 to 2016-10,
2018-01 to 2022-12 and 2023-01 to 2026-06), about 10.9 years.
"""
import datetime
import tempfile
import unittest
from pathlib import Path

import careerkit
from jsk.adapters.compose import native
from jsk.domain import ontology as O
from jsk.domain.assessment import derive as D

ADVERT = """https://acme.example/jobs/42

# Platform Engineer
Acme Health · Melbourne

## What you'll bring

- 7+ years of Engineering experience.
- Kafka and event-driven systems.
"""
YEARS_LINE, KAFKA_LINE = 2, 3
STEM = "acme-platform"
TODAY = datetime.date(2026, 10, 6)
ALL_ROLES_MONTHS = 131


def fails(findings):
    return [text for severity, text, _ in findings if severity == "FAIL"]


class Years(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws")

    def derived(self, years, concepts=(), line=YEARS_LINE, slug="experience", need=None):
        """The row for one requirement asking `years`, after the whole decide-and-derive."""
        native.capture(self.root, STEM, text=ADVERT, today=TODAY)
        row = {"n": line, "slug": slug, "asked": "Engineering experience" if line == YEARS_LINE
               else "Kafka", "concepts": list(concepts)}
        if years is not None:
            row["years"] = years
        if need:
            row["need"] = need
        done = native.decide(self.root, STEM, rows=[row], drops=[
            {"n": KAFKA_LINE if line == YEARS_LINE else YEARS_LINE, "reason": "not under test"}],
            today=TODAY)
        self.assertEqual(fails(done.findings), [], done.findings)
        done = native.complete_posting(self.root, STEM, today=TODAY)
        self.assertEqual(fails(done.findings), [], done.findings)
        a = native.derive_assessment(self.root, STEM, today=TODAY)
        return next(r for r in a.rows if r["slug"] == slug), a

    def test_enough_years_over_all_roles_is_satisfied_with_the_span_in_its_reason(self):
        row, a = self.derived(10)
        self.assertEqual(row["verdict"], "satisfied")
        self.assertIn("about 10.9 years in the record (2014-03 to 2026-06), 10 asked", row["basis"])
        # The record answered, so the person is not asked.
        self.assertEqual([q for q in a.questions if q["requirement"] == "experience"], [])

    def test_too_few_years_is_unsatisfied_and_not_asked_about(self):
        row, a = self.derived(15)
        self.assertEqual(row["verdict"], "unsatisfied")
        self.assertIn("about 10.9 years in the record", row["basis"])
        self.assertEqual([q for q in a.questions if q["requirement"] == "experience"], [])
        self.assertEqual(a.fit, "poor")

    def test_a_year_or_less_under_is_partial_and_a_month_over_is_not(self):
        self.assertEqual(self.derived(11)[0]["verdict"], "partial")     # 132 months asked

    def test_the_years_are_counted_over_the_requirements_concepts_alone(self):
        # Kafka sits on two projects in two roles (42 + 16 months), far under the 131 months
        # the whole record covers: ten years of it is unsatisfied though ten of anything is not.
        row, _ = self.derived(10, ["c:kafka"], line=KAFKA_LINE, slug="kafka")
        self.assertEqual(row["verdict"], "unsatisfied")
        self.assertIn("about 4.8 years in the record", row["basis"])

    def test_the_match_is_a_ceiling_the_years_never_raise(self):
        plain, _ = self.derived(None, ["c:kafka"], line=KAFKA_LINE, slug="kafka")
        row = self._rederived(3)
        # Three years of Kafka is met by its 58 months, so the verdict is the match's own.
        self.assertEqual(row["verdict"], plain["verdict"])
        self.assertIn("confirmed on" if plain["verdict"] == "satisfied" else "only",
                      row["basis"])

    def _rederived(self, years):
        """The kafka row once its years are decided into the posting already derived."""
        done = native.decide(self.root, STEM, today=TODAY, rows=[
            {"n": KAFKA_LINE, "slug": "kafka", "asked": "Kafka", "concepts": ["c:kafka"],
             "years": years}])
        self.assertEqual(fails(done.findings), [], done.findings)
        native.complete_posting(self.root, STEM, today=TODAY)
        a = native.derive_assessment(self.root, STEM, today=TODAY)
        return next(r for r in a.rows if r["slug"] == "kafka")

    def test_a_requirement_without_years_stays_indeterminate(self):
        row, a = self.derived(None)
        self.assertEqual(row["verdict"], "indeterminate")
        self.assertNotIn("years in the record", row["basis"])

    def test_years_are_stored_on_the_requirement_and_read_back(self):
        self.derived(7)
        graph = native.show(self.root, STEM, "requirements", today=TODAY)
        self.assertEqual(graph["requirements"][0]["years"], 7)

    def test_years_that_are_not_a_duration_fail_and_write_nothing(self):
        native.capture(self.root, STEM, text=ADVERT, today=TODAY)
        for bad in (0, 2018, True, "seven"):
            done = native.decide(self.root, STEM, today=TODAY, rows=[
                {"n": YEARS_LINE, "slug": "experience", "asked": "Engineering experience",
                 "years": bad}])
            self.assertTrue(any("years" in t for t in fails(done.findings)), (bad, done.findings))
            self.assertIsNone(done.target)


class Timed(unittest.TestCase):
    """domain.assessment.derive.timed over a hand-made match result."""

    @staticmethod
    def result(**q):
        base = {"id": "k:req_a_x", "asked": "x", "necessity": "required", "state": "candidate",
                "verdict": "indeterminate", "concepts": [], "carriers": [], "near": [],
                "years": 5}
        return {"requirements": [{**base, **q}], "questions": [
            {"kind": "unknown-term", "requirement": q.get("asked", "x"), "detail": []}]}

    def test_without_a_reader_of_the_record_nothing_is_measured(self):
        r = self.result()
        self.assertEqual(D.timed(r, None), (r, {}, set()))

    def test_an_implicit_requirement_is_left_alone(self):
        r = self.result(necessity="implicit", verdict=None, state="implicit")
        self.assertEqual(D.timed(r, lambda c: (999, "2000-01", "now"))[0], r)

    def test_a_tag_only_match_keeps_its_verdict_and_its_question(self):
        r = self.result(state="matched", verdict="unevidenced", concepts=["c:kafka"])
        out, basis, settled = D.timed(r, lambda c: (999, "2000-01", "now"))
        self.assertEqual(out["requirements"][0]["verdict"], "unevidenced")
        self.assertEqual(settled, set())
        self.assertEqual(len(out["questions"]), 1)
        self.assertIn("about 83.2 years in the record (2000-01 to now), 5 asked", basis["k:req_a_x"])

    def test_sixty_months_meet_five_years_and_forty_eight_are_a_year_under(self):
        for months, says in ((60, "satisfied"), (48, "partial"), (47, "unsatisfied")):
            out, _, _ = D.timed(self.result(), lambda c, m=months: (m, "2020-01", "now"))
            self.assertEqual(out["requirements"][0]["verdict"], says, months)

    def test_no_counted_role_says_so_without_a_span(self):
        _, basis, _ = D.timed(self.result(), lambda c: (0, None, None))
        self.assertEqual(basis["k:req_a_x"], "about 0.0 years in the record, 5 asked")


class Ontology(unittest.TestCase):
    def test_years_is_an_optional_integer_on_a_requirement(self):
        req = next(c for c in O.CLASSES if c.name == "Requirement")
        self.assertEqual(req.preds["years"].card, "?")


if __name__ == "__main__":
    unittest.main()
