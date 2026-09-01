"""score_projects.py makes the tailoring formula reproducible. mode-tailor.md
specified it precisely and shipped no implementation, so every session hand-wrote
a throwaway scorer and re-decided the two terms the formula never defined.

These tests pin the formula and pin both of those decisions. They also pin the
inputs: requirements come from the posting's own `requirements[]` and projects
from the record's `projects[]`, so the ranking is computed over exactly the
document a gap analysis assesses. When the scorer read the bundle and the
assessor read the record, the two could disagree about what the record held and
nothing would have said so.
"""
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import SCRIPTS, load_script, run

SCORE_PROJECTS = "jsk_okf.score_projects"
sp = load_script(SCORE_PROJECTS)


def requirement(rid, kind, value, necessity="required"):
    return {"id": rid, "kind": kind, "necessity": necessity, "value": value,
            "provenance": {"status": "confirmed", "source": {"kind": "posting-text"}}}


POSTING = {
    "ujd": "1.0.0",
    "meta": {"id": "ujd:test"},
    "posting": {"id": "pst_test", "title": "Solution Architect"},
    "organization": {"name": "Acme Corp"},
    "role": {"seniority": "architecture-ownership", "domains": ["healthcare"]},
    "requirements": [
        requirement("req_int", "capability", "integration-architecture"),
        requirement("req_sov", "capability", "data-sovereignty"),
        requirement("req_stk", "capability", "stakeholder-management"),
        requirement("req_azure", "technology", "azure"),
        requirement("req_tf", "technology", "terraform", "preferred"),
    ],
}

PROJECT = {
    "id": "prj_test",
    "title": "integration",
    "strength": 5,
    "seniority": "architecture-ownership",
    "domains": ["healthcare"],
    "capabilities": ["integration-architecture", "data-sovereignty"],
    "technologies": ["azure", "bicep"],
    "period": {"start": {"value": "2024"}, "end": {"value": "2026"}, "state": "ended"},
}


def want_from(posting=None, include_implicit=False):
    return sp.requirements({**POSTING, **(posting or {})}, include_implicit)


class Formula(unittest.TestCase):
    """score = cap x3 + tech x2 + domain x2 + seniority x2 + strength + recency"""

    def score(self, project=None, posting=None, as_of=2026, technologies=None):
        want = want_from(posting)
        techs = want["technologies"] if technologies is None else sp.as_set(technologies)
        return sp.score_one({**PROJECT, **(project or {})}, want, as_of, techs)

    def test_every_term_is_weighted_as_documented(self):
        # 2 caps x3 + 1 tech x2 + domain x2 + seniority 1.0 x2 + strength 5 + recency 2
        self.assertAlmostEqual(self.score()["score"], 6 + 2 + 2 + 2 + 5 + 2)

    def test_capability_overlap_is_a_count(self):
        base = self.score()["score"]
        more = self.score({"capabilities": ["integration-architecture",
                                            "data-sovereignty",
                                            "stakeholder-management"]})["score"]
        self.assertAlmostEqual(more - base, 3.0)

    def test_technology_overlap_is_a_count(self):
        base = self.score()["score"]
        more = self.score({"technologies": ["azure", "terraform"]})["score"]
        self.assertAlmostEqual(more - base, 2.0)

    def test_capability_matching_is_exact_string(self):
        # A near-synonym must score zero: that is the whole reason the vocabulary exists.
        self.assertEqual(self.score({"capabilities": ["integration-architectures"]})
                         ["matched"], [])

    def test_unmatched_lists_what_the_project_lacks(self):
        self.assertEqual(self.score()["unmatched"], ["stakeholder-management"])


class RequirementsComeFromThePosting(unittest.TestCase):
    """`value` is what the score runs on, never `label`.

    The resume mirrors the posting's wording; the ranking matches the vocabulary
    term. Conflating them scores a synonym as absent evidence.
    """

    def test_capabilities_and_technologies_are_split_by_kind(self):
        want = want_from()
        self.assertEqual(want["capabilities"], {"integration-architecture",
                                                "data-sovereignty",
                                                "stakeholder-management"})
        self.assertEqual(want["technologies"], {"azure", "terraform"})

    def test_preferred_requirements_are_scored(self):
        self.assertIn("terraform", want_from()["technologies"])

    def test_label_is_never_matched_on(self):
        posting = {"requirements": [
            {**requirement("req_x", "capability", "integration-architecture"),
             "label": "designing enterprise integration platforms"}]}
        self.assertEqual(want_from(posting)["capabilities"],
                         {"integration-architecture"})

    def test_domains_and_seniority_come_from_role(self):
        want = want_from()
        self.assertEqual(want["domains"], {"healthcare"})
        self.assertEqual(want["seniority"], "architecture-ownership")


class ImplicitRequirementsAreExcluded(unittest.TestCase):
    """An inference that moves a x3 term is an invented requirement."""

    IMPLICIT = {"requirements": POSTING["requirements"] + [
        {"id": "req_imp", "kind": "capability", "necessity": "implicit",
         "value": "vendor-management",
         "provenance": {"status": "inferred", "source": {"kind": "inferred"}}}]}

    def test_implicit_is_dropped_by_default(self):
        want = want_from(self.IMPLICIT)
        self.assertNotIn("vendor-management", want["capabilities"])
        self.assertEqual(want["dropped_implicit"], 1)

    def test_include_implicit_scores_it(self):
        want = want_from(self.IMPLICIT, include_implicit=True)
        self.assertIn("vendor-management", want["capabilities"])

    def test_dropping_one_changes_the_ranking(self):
        vendor = {**PROJECT, "capabilities": ["vendor-management"]}
        without = sp.score_one(vendor, want_from(self.IMPLICIT), 2026, set())
        with_it = sp.score_one(vendor, want_from(self.IMPLICIT, True), 2026, set())
        self.assertEqual(with_it["score"] - without["score"], 3.0)


class NecessityVocabulary(unittest.TestCase):
    """`required` is what a posting is written with. `must-have` is what UJD said.

    Both have to score, and anything else has to be reported rather than quietly
    treated as an inference - an unrecognised word falling through to `implicit`
    drops the entire primary axis without saying so.
    """

    def scored(self, necessity):
        return want_from({"requirements": [
            requirement("req_one", "capability", "integration-architecture", necessity)]})

    def test_required_is_scored(self):
        self.assertEqual(self.scored("required")["capabilities"],
                         {"integration-architecture"})

    def test_the_ujd_word_still_scores(self):
        """A posting migrated out of an archived UJD document carries it."""
        self.assertEqual(self.scored("must-have")["capabilities"],
                         {"integration-architecture"})
        self.assertEqual(self.scored("nice-to-have")["capabilities"],
                         {"integration-architecture"})

    def test_preferred_is_scored(self):
        self.assertEqual(self.scored("preferred")["capabilities"],
                         {"integration-architecture"})

    def test_implicit_is_dropped_and_is_not_reported_as_unknown(self):
        want = self.scored("implicit")
        self.assertEqual(want["capabilities"], set())
        self.assertEqual(want["dropped_implicit"], 1)
        self.assertEqual(want["unknown_necessity"], [])

    def test_a_word_nobody_knows_is_named(self):
        want = self.scored("mandatory")
        self.assertEqual(want["capabilities"], set())
        self.assertEqual(want["unknown_necessity"], ["mandatory"])

    def test_a_missing_necessity_is_named_too(self):
        want = want_from({"requirements": [
            {"id": "req_one", "kind": "capability", "value": "integration-architecture"}]})
        self.assertEqual(want["unknown_necessity"], ["None"])


class DomainMatch(unittest.TestCase):
    """Settled as binary. Multiplying a count rewards projects that happen to carry
    more domain tags, which is a tagging artefact rather than a signal."""

    def score(self, domains):
        return sp.score_one({**PROJECT, "domains": domains}, want_from(), 2026, set())

    def test_one_shared_domain_scores_the_same_as_several(self):
        self.assertEqual(self.score(["healthcare"])["score"],
                         self.score(["healthcare", "aged-care", "government"])["score"])

    def test_no_shared_domain_scores_zero_for_the_term(self):
        self.assertEqual(self.score(["healthcare"])["score"]
                         - self.score(["retail"])["score"], 2)


class SeniorityScale(unittest.TestCase):
    """Settled as a graded scale: 1.0 at or above the level sought, decaying to 0.0
    at junior. The formula left this to the reader and every session re-decided it."""

    def test_exact_match_is_full_credit(self):
        self.assertEqual(sp.seniority_match("architecture-ownership",
                                            "architecture-ownership"), 1.0)

    def test_junior_against_architecture_ownership_is_zero(self):
        self.assertEqual(sp.seniority_match("junior", "architecture-ownership"), 0.0)

    def test_partial_credit_between_the_ends(self):
        value = sp.seniority_match("hands-on-senior", "architecture-ownership")
        self.assertGreater(value, 0.0)
        self.assertLess(value, 1.0)

    def test_the_scale_is_monotonic(self):
        values = [sp.seniority_match(level, "architecture-ownership")
                  for level in sp.SENIORITY]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_overshooting_is_not_penalised(self):
        # Evidence from a more senior engagement than the posting asks for is not
        # worth less; the penalty is for falling short.
        self.assertEqual(sp.seniority_match("architecture-ownership", "hands-on"), 1.0)

    def test_unspecified_seniority_is_neutral(self):
        self.assertEqual(sp.seniority_match("junior", None), 1.0)
        self.assertEqual(sp.seniority_match("junior", "not-a-level"), 1.0)


class RecencyFromPeriod(unittest.TestCase):
    """URS carries a Period, not the bundle's bare `recency:` year."""

    def ended(self, year):
        return {"period": {"end": {"value": str(year)}, "state": "ended"}}

    def test_within_three_years_earns_two(self):
        self.assertEqual(sp.recency_bonus(self.ended(2024), 2026), 2)

    def test_within_six_years_earns_one(self):
        self.assertEqual(sp.recency_bonus(self.ended(2021), 2026), 1)

    def test_older_earns_nothing(self):
        self.assertEqual(sp.recency_bonus(self.ended(2015), 2026), 0)

    def test_a_month_precision_end_still_yields_its_year(self):
        self.assertEqual(sp.project_year(
            {"period": {"end": {"value": "2024-07"}, "state": "ended"}}), 2024)

    def test_ongoing_earns_the_full_bonus(self):
        project = {"period": {"start": {"value": "2019"}, "state": "ongoing"}}
        self.assertEqual(sp.recency_bonus(project, 2026), 2)

    def test_an_undated_project_earns_nothing(self):
        self.assertEqual(sp.recency_bonus({}, 2026), 0)

    def test_no_end_falls_back_to_the_start(self):
        self.assertEqual(sp.project_year({"period": {"start": {"value": "2011"}}}), 2011)


class RecordCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._projects = []
        self._posting = dict(POSTING)

    def project(self, title, **overrides):
        self._projects.append({**PROJECT, "id": f"prj_{title}", "title": title,
                               **overrides})

    def posting(self, **overrides):
        self._posting = {**POSTING, **overrides}

    def paths(self):
        record = self.tmp / "record.json"
        record.write_text(json.dumps({
            "urs": "1.0.0", "meta": {}, "person": {"name": {"full": "T"}},
            "projects": self._projects}), encoding="utf-8")
        posting = self.tmp / "acme.posting.json"
        posting.write_text(json.dumps(self._posting), encoding="utf-8")
        return record, posting

    def score(self, *args):
        record, posting = self.paths()
        return run(SCORE_PROJECTS, record, posting, "--as-of", "2026", *args)


class ReadsBothSidesAsJson(RecordCase):
    def test_ranking_follows_the_postings_capabilities(self):
        self.project("integration", capabilities=["integration-architecture",
                                                  "data-sovereignty"])
        self.project("ai-platform", capabilities=["ai-platform-architecture"])
        code, out = self.score()
        self.assertEqual(code, 0, out)
        self.assertLess(out.index("integration"), out.index("ai-platform"))

    def test_changing_the_posting_reshuffles_the_ranking(self):
        self.project("integration", capabilities=["integration-architecture"])
        self.project("ai-platform", capabilities=["ai-platform-architecture"])
        self.posting(requirements=[
            requirement("req_ai", "capability", "ai-platform-architecture")])
        code, out = self.score()
        self.assertEqual(code, 0, out)
        self.assertLess(out.index("ai-platform"), out.index("integration"))

    def test_the_posting_title_and_organization_are_reported(self):
        self.project("integration")
        _, out = self.score()
        self.assertIn("Acme Corp - Solution Architect", out)

    def test_projects_are_counted_from_the_record(self):
        self.project("one")
        self.project("two")
        _, out = self.score()
        self.assertIn("projects scored: 2", out)


class CapabilityThatMatchesNothing(RecordCase):
    """Absent evidence and an under-tagged project need opposite responses."""

    def test_a_capability_on_no_project_warns(self):
        self.project("integration", capabilities=["integration-architecture"])
        code, out = self.score()
        self.assertEqual(code, 0, out)
        self.assertIn("appears on no project in the record", out)
        self.assertIn("data-sovereignty", out)

    def test_a_capability_some_project_carries_does_not_warn(self):
        self.project("integration", capabilities=["integration-architecture"])
        self.project("other", capabilities=["data-sovereignty",
                                            "stakeholder-management"])
        _, out = self.score()
        self.assertNotIn("appears on no project", out)

    def test_a_posting_with_no_capabilities_says_so(self):
        self.project("integration")
        self.posting(requirements=[requirement("req_azure", "technology", "azure")])
        _, out = self.score()
        self.assertIn("primary axis is empty", out)

    def test_a_near_miss_names_the_term_the_record_actually_carries(self):
        """The analyst mints a requirement's term fresh while the project carries
        the bundle's own word for the same thing, and the two never meet. Both
        halves scored zero and the warning could not say which had happened."""
        self.project("streams", capabilities=["event-driven-architecture"])
        self.posting(requirements=[
            requirement("req_evt", "capability", "event-streaming-architecture")])
        _, out = self.score()
        self.assertIn("event-driven-architecture", out)
        self.assertIn("tag the project", out)

    def test_a_genuine_absence_suggests_nothing(self):
        """A suggestion here reads as "tag this project with that capability", so a
        wrong one invites exactly the invented evidence the exact-match rule exists
        to stop. 'engineer-mentoring' and 'data-engineering' score 0.65 on
        SequenceMatcher and share no whole word."""
        self.project("pipelines", capabilities=["data-engineering"])
        self.posting(requirements=[
            requirement("req_men", "capability", "engineer-mentoring")])
        _, out = self.score()
        self.assertIn("appears on no project in the record", out)
        self.assertNotIn("tag the project", out)

    def test_a_ranking_no_capability_reached_says_it_decided_nothing(self):
        """Every requirement missing its term leaves the order decided by strength
        and recency alone. The column of zeroes looks like a verdict on the
        evidence when it is a verdict on the vocabulary."""
        self.project("pipelines", capabilities=["data-engineering"])
        self.posting(requirements=[
            requirement("req_men", "capability", "engineer-mentoring")])
        _, out = self.score()
        self.assertIn("contributed nothing to this ranking", out)


class NoTechnologiesNamed(RecordCase):
    """The case mode-tailor.md left undefined, on a x2 term."""

    CAPS_ONLY = [requirement("req_int", "capability", "integration-architecture")]

    def test_an_empty_technology_list_is_reported_as_inert(self):
        self.project("integration")
        self.posting(requirements=self.CAPS_ONLY)
        code, out = self.score()
        self.assertEqual(code, 0, out)
        self.assertIn("names no technologies", out)

    def test_an_inert_term_cannot_change_the_ranking(self):
        self.project("wide-stack", technologies=["azure", "terraform", "aws"])
        self.project("narrow-stack", technologies=[])
        self.posting(requirements=self.CAPS_ONLY)
        _, out = self.score("--markdown")
        scores = {line.split("|")[2].strip()
                  for line in out.splitlines() if "stack" in line and "|" in line}
        self.assertEqual(len(scores), 1, f"scores should be equal:\n{out}")

    def test_assumed_technologies_are_labelled_as_an_inference(self):
        self.project("integration")
        self.posting(requirements=self.CAPS_ONLY)
        code, out = self.score("--assume-technologies", "azure,bicep")
        self.assertEqual(code, 0, out)
        self.assertIn("ASSUMED", out)

    def test_assumption_is_refused_when_the_posting_named_a_stack(self):
        self.project("integration")
        _, out = self.score("--assume-technologies", "aws")
        self.assertIn("ignored", out)


class ImplicitIsReportedNotHidden(RecordCase):
    def test_excluding_implicit_requirements_is_stated(self):
        self.project("integration")
        self.posting(requirements=POSTING["requirements"] + [
            {"id": "req_imp", "kind": "capability", "necessity": "implicit",
             "value": "vendor-management",
             "provenance": {"status": "inferred", "source": {"kind": "inferred"}}}])
        _, out = self.score()
        self.assertIn("implicit requirement(s) excluded", out)

    def test_including_them_is_stated_too(self):
        self.project("integration")
        _, out = self.score("--include-implicit")
        self.assertIn("requirements the posting never stated are part of", out)


class Output(RecordCase):
    def test_markdown_table_is_pasteable(self):
        self.project("integration")
        _, out = self.score("--markdown")
        self.assertIn("| rank | score | project |", out)
        self.assertIn("|---|", out)

    def test_plain_table_is_the_default(self):
        self.project("integration")
        _, out = self.score()
        self.assertNotIn("| rank |", out)
        self.assertIn("rank", out)

    def test_matched_and_unmatched_are_shown_per_project(self):
        self.project("integration")
        _, out = self.score()
        self.assertIn("matched:", out)
        self.assertIn("unmatched:", out)
        self.assertIn("stakeholder-management", out)

    def test_ties_break_by_name_so_reruns_are_stable(self):
        self.project("bravo")
        self.project("alpha")
        _, first = self.score()
        _, second = self.score()
        self.assertEqual(first, second)
        self.assertLess(first.index("alpha"), first.index("bravo"))


class BadInput(RecordCase):
    def test_missing_record_is_a_usage_error(self):
        _, posting = self.paths()
        code, out = run(SCORE_PROJECTS, self.tmp / "absent.json", posting)
        self.assertEqual(code, 2)
        self.assertIn("record not found", out)

    def test_missing_posting_is_a_usage_error(self):
        record, _ = self.paths()
        code, out = run(SCORE_PROJECTS, record, self.tmp / "absent.json")
        self.assertEqual(code, 2)
        self.assertIn("posting not found", out)

    def test_a_record_that_is_not_json_is_a_usage_error(self):
        _, posting = self.paths()
        broken = self.tmp / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        code, out = run(SCORE_PROJECTS, broken, posting)
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", out)

    def test_a_record_with_no_projects_exits_non_zero(self):
        code, out = self.score()
        self.assertEqual(code, 1)
        self.assertIn("nothing to score", out)
        self.assertIn("selection keys", out)


class NoYamlDependency(unittest.TestCase):
    def test_the_scorer_does_not_import_yaml(self):
        """Both sides are JSON now, so pyyaml stopped being a requirement."""
        source = (SCRIPTS / "score_projects.py").read_text(encoding="utf-8")
        self.assertNotIn("import yaml", source)
        self.assertNotIn("pyyaml", source.lower())


if __name__ == "__main__":
    unittest.main()
