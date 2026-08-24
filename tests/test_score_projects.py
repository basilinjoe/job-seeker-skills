"""score_projects.py makes the tailoring formula reproducible. mode-tailor.md
specified it precisely and shipped no implementation, so every session hand-wrote
a throwaway scorer and re-decided the two terms the formula never defined.

These tests pin the formula, pin both of those decisions, and pin that the
requirement sets come from the target's frontmatter rather than from anywhere else.
"""
import tempfile
import textwrap
import unittest
from pathlib import Path

from fixtures import SCRIPTS, load_script, run

SCORE_PROJECTS = SCRIPTS / "score_projects.py"
sp = load_script(SCORE_PROJECTS)

TARGET = {
    "type": "Job Target",
    "company": "Acme Corp",
    "role": "Solution Architect",
    "required_capabilities": ["integration-architecture", "data-sovereignty",
                              "stakeholder-management"],
    "required_technologies": ["azure", "terraform"],
    "domains": ["healthcare"],
    "seniority_sought": "architecture-ownership",
}

PROJECT = {
    "type": "Project",
    "strength": 5,
    "recency": 2026,
    "seniority": "architecture-ownership",
    "domains": ["healthcare"],
    "capabilities": ["integration-architecture", "data-sovereignty"],
    "technologies": ["azure", "bicep"],
}


def yaml_block(meta):
    lines = []
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif isinstance(value, str):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    return "---\n" + "\n".join(lines) + "\n---\n\n# Body\n"


class Formula(unittest.TestCase):
    """score = cap x3 + tech x2 + domain x2 + seniority x2 + strength + recency"""

    def score(self, project=None, target=None, as_of=2026, technologies=None):
        target = {**TARGET, **(target or {})}
        techs = sp.as_set(target.get("required_technologies")
                          if technologies is None else technologies)
        return sp.score_one({**PROJECT, **(project or {})}, target, as_of, techs)

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
        r = self.score({"capabilities": ["integration-architectures"]})
        self.assertEqual(r["matched"], [])

    def test_unmatched_lists_what_the_project_lacks(self):
        self.assertEqual(self.score()["unmatched"], ["stakeholder-management"])


class DomainMatch(unittest.TestCase):
    """Settled as binary. Multiplying a count rewards concepts that happen to carry
    more domain tags, which is a tagging artefact rather than a signal."""

    def score(self, domains):
        return sp.score_one({**PROJECT, "domains": domains}, TARGET, 2026, set())

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


class RecencyBonus(unittest.TestCase):
    def test_within_three_years_earns_two(self):
        self.assertEqual(sp.recency_bonus(2024, 2026), 2)

    def test_within_six_years_earns_one(self):
        self.assertEqual(sp.recency_bonus(2021, 2026), 1)

    def test_older_earns_nothing(self):
        self.assertEqual(sp.recency_bonus(2015, 2026), 0)

    def test_missing_or_unparseable_recency_earns_nothing(self):
        self.assertEqual(sp.recency_bonus(None, 2026), 0)
        self.assertEqual(sp.recency_bonus("recently", 2026), 0)


class BundleCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.bundle = self.tmp / "bundle"
        (self.bundle / "projects").mkdir(parents=True)
        (self.bundle / "framework").mkdir(parents=True)
        (self.bundle / "tailoring" / "targets").mkdir(parents=True)

    def project(self, name, **overrides):
        path = self.bundle / "projects" / f"{name}.md"
        path.write_text(yaml_block({**PROJECT, **overrides}), encoding="utf-8")
        return path

    def target(self, **overrides):
        path = self.bundle / "tailoring" / "targets" / "acme.md"
        path.write_text(yaml_block({**TARGET, **overrides}), encoding="utf-8")
        return path

    def vocabulary(self, values):
        (self.bundle / "framework" / "capability-vocabulary.md").write_text(
            textwrap.dedent("""\
                # Architecture & design

                """) + "\n".join(f"- `{v}`" for v in values), encoding="utf-8")

    def score(self, *args):
        return run(SCORE_PROJECTS, self.bundle, self.target(), "--as-of", "2026", *args)


class ReadsFromTargetFrontmatter(BundleCase):
    """'The reviewed document is the one that drives the ranking.'"""

    def test_ranking_follows_the_targets_capabilities(self):
        self.project("integration", capabilities=["integration-architecture",
                                                  "data-sovereignty"])
        self.project("ai-platform", capabilities=["ai-platform-architecture"])
        code, out = self.score()
        self.assertEqual(code, 0, out)
        self.assertLess(out.index("integration"), out.index("ai-platform"))

    def test_changing_the_target_reshuffles_the_ranking(self):
        self.project("integration", capabilities=["integration-architecture"])
        self.project("ai-platform", capabilities=["ai-platform-architecture"])
        self.target(required_capabilities=["ai-platform-architecture"])
        code, out = run(SCORE_PROJECTS, self.bundle,
                        self.bundle / "tailoring" / "targets" / "acme.md",
                        "--as-of", "2026")
        self.assertEqual(code, 0, out)
        self.assertLess(out.index("ai-platform"), out.index("integration"))

    def test_index_files_are_not_scored(self):
        self.project("integration")
        (self.bundle / "projects" / "index.md").write_text(
            yaml_block({"type": "Index"}), encoding="utf-8")
        _, out = self.score()
        self.assertIn("projects scored: 1", out)

    def test_non_project_concepts_are_not_scored(self):
        self.project("integration")
        (self.bundle / "projects" / "note.md").write_text(
            yaml_block({"type": "Guide"}), encoding="utf-8")
        _, out = self.score()
        self.assertIn("projects scored: 1", out)


class VocabularyWarning(BundleCase):
    """'A typo silently scores zero and is invisible today.'"""

    def test_capability_absent_from_the_vocabulary_warns(self):
        self.project("integration")
        self.vocabulary(["integration-architecture", "data-sovereignty",
                         "stakeholder-management"])
        self.target(required_capabilities=["integration-architectrue"])
        code, out = run(SCORE_PROJECTS, self.bundle,
                        self.bundle / "tailoring" / "targets" / "acme.md")
        self.assertEqual(code, 0, out)
        self.assertIn("WARN", out)
        self.assertIn("integration-architectrue", out)

    def test_known_capabilities_do_not_warn(self):
        self.project("integration")
        self.vocabulary(["integration-architecture", "data-sovereignty",
                         "stakeholder-management"])
        _, out = self.score()
        self.assertNotIn("is not in", out)

    def test_an_empty_vocabulary_leaves_checking_off(self):
        # Matching validate_bundle.py: while the file holds no values, do not reject
        # every genuine capability.
        self.project("integration")
        self.vocabulary([])
        _, out = self.score()
        self.assertNotIn("is not in", out)

    def test_a_target_with_no_capabilities_says_so(self):
        self.project("integration")
        self.target(required_capabilities=[])
        code, out = run(SCORE_PROJECTS, self.bundle,
                        self.bundle / "tailoring" / "targets" / "acme.md")
        self.assertIn("primary axis is empty", out)


class NoTechnologiesNamed(BundleCase):
    """The case mode-tailor.md left undefined, on a x2 term."""

    def test_an_empty_technology_list_is_reported_as_inert(self):
        self.project("integration")
        self.target(required_technologies=[])
        code, out = run(SCORE_PROJECTS, self.bundle,
                        self.bundle / "tailoring" / "targets" / "acme.md")
        self.assertEqual(code, 0, out)
        self.assertIn("names no technologies", out)

    def test_an_inert_term_cannot_change_the_ranking(self):
        self.project("wide-stack", technologies=["azure", "terraform", "aws"])
        self.project("narrow-stack", technologies=[])
        self.target(required_technologies=[])
        _, out = run(SCORE_PROJECTS, self.bundle,
                     self.bundle / "tailoring" / "targets" / "acme.md",
                     "--as-of", "2026", "--markdown")
        scores = {line.split("|")[2].strip()
                  for line in out.splitlines() if "stack" in line and "|" in line}
        self.assertEqual(len(scores), 1, f"scores should be equal:\n{out}")

    def test_assumed_technologies_are_labelled_as_an_inference(self):
        self.project("integration")
        self.target(required_technologies=[])
        code, out = run(SCORE_PROJECTS, self.bundle,
                        self.bundle / "tailoring" / "targets" / "acme.md",
                        "--assume-technologies", "azure,bicep")
        self.assertEqual(code, 0, out)
        self.assertIn("ASSUMED", out)

    def test_assumption_is_refused_when_the_posting_named_a_stack(self):
        self.project("integration")
        code, out = self.score("--assume-technologies", "aws")
        self.assertIn("ignored", out)


class Output(BundleCase):
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


class BadInput(BundleCase):
    def test_missing_bundle_is_a_usage_error(self):
        code, out = run(SCORE_PROJECTS, self.tmp / "absent", self.target())
        self.assertEqual(code, 2)
        self.assertIn("bundle not found", out)

    def test_missing_target_is_a_usage_error(self):
        code, out = run(SCORE_PROJECTS, self.bundle, self.tmp / "absent.md")
        self.assertEqual(code, 2)
        self.assertIn("target not found", out)

    def test_target_without_frontmatter_is_a_usage_error(self):
        path = self.bundle / "tailoring" / "targets" / "bare.md"
        path.write_text("# Just a posting\n", encoding="utf-8")
        code, out = run(SCORE_PROJECTS, self.bundle, path)
        self.assertEqual(code, 2)
        self.assertIn("target-template.md", out)

    def test_a_bundle_with_no_projects_exits_non_zero(self):
        code, out = run(SCORE_PROJECTS, self.bundle, self.target())
        self.assertEqual(code, 1)
        self.assertIn("nothing to score", out)

    def test_an_unparseable_project_is_skipped_not_fatal(self):
        self.project("integration")
        (self.bundle / "projects" / "broken.md").write_text(
            "---\ntype: Project\ncapabilities: [unclosed\n---\n", encoding="utf-8")
        code, out = self.score()
        self.assertEqual(code, 0, out)
        self.assertIn("broken.md", out)


if __name__ == "__main__":
    unittest.main()
