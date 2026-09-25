"""jsk.kbindex: the Markdown knowledge base reader, and the ranking it used to do.

Retired as `jsk index`; the module stays one release because `jsk migrate` reads the
Markdown with it, and release N+1 deletes it and this file.

The scores below are worked by hand from the table in jsk-tailor-analyst.md, not read
back from the code - a test that recites the implementation's output proves only that
it ran.
"""
import datetime
import tempfile
import unittest
from pathlib import Path

from fixtures import PACKAGE, run

from jsk import kbindex

KBINDEX = f"{PACKAGE}.kbindex"

TODAY = datetime.date(2026, 9, 23)

FENCE = "```"

KB = f"""---
kb: 2
name: Test Person
updated: 2026-09-23
---

# Career knowledge base - Test Person

## Identity

{FENCE}yaml
full_name: Test Person
{FENCE}

## Vocabulary

### Capabilities

- `team-leadership`
- `mentoring`

## Roles

### Engineer - Acme `role_one`

{FENCE}yaml
id: role_one
start: 2015-08
end: 2016-04
state: ended
{FENCE}

### Senior Engineer - Acme `role_two`

{FENCE}yaml
id: role_two
start: 2016-03
end: 2017-02
state: ended
{FENCE}

### Architect - Beta `role_three`

{FENCE}yaml
id: role_three
start: 2026-01
state: ongoing
{FENCE}

## Projects

### Alpha `proj_alpha`

{FENCE}yaml
id: proj_alpha
role: role_three
strength: 5            # flagship
recency: 2025
seniority: architecture-ownership
capabilities: [team-leadership, mentoring]
technologies: [dotnet, kubernetes]
headline_metric: none-quantified
status: confirmed
{FENCE}

**The problem.** A fenced example inside a project must not read as a heading:

{FENCE}text
### Not a project
{FENCE}

### Beta `proj_beta`

{FENCE}yaml
id: proj_beta
role: role_two
strength: 3
recency: 2021
seniority: hands-on
capabilities: []
technologies: [dotnet, terraform]
status: confirmed
{FENCE}

### Gamma `proj_gamma`

{FENCE}yaml
id: proj_gamma
role: role_one
strength: 4
recency: 2018
seniority: platform-design
capabilities: []
technologies: [python]
status: confirmed
{FENCE}

### Old `proj_old`

{FENCE}yaml
id: proj_old
role: role_one
strength: 5
recency: 2025
seniority: architecture-ownership
capabilities: [team-leadership]
technologies: [dotnet, terraform]
status: confirmed
retired: true
{FENCE}

## Metrics

| id | subject | baseline | value | unit | direction | confidence | source | status |
|---|---|---|---|---|---|---|---|---|
| metric_latency | p95 latency | 5 | 1 | s | decrease | measured | Grafana | confirmed |

## Open questions

| id | question | about | asked | answered |
|---|---|---|---|---|
| q_open | Still open? | proj_alpha | 2026-09-01 | |
| q_done | Answered? | proj_beta | 2026-09-01 | 2026-09-02 |
"""

POSTING = """---
company: Acme
title: "Platform Engineer: Core"
url: https://example.com/jobs/1
seniority: platform-design
captured: 2026-09-23
requirements:
  - value: dotnet            # a technology
    kind: technology
    necessity: required
    label: ".NET: the whole stack"
  - value: terraform
    kind: technology
    necessity: required
    label: Terraform
  - value: kubernetes
    kind: technology
    necessity: preferred
    label: Kubernetes
  - value: mentoring
    kind: capability
    necessity: implicit
    label: grows people
  - value: team-leadership
    kind: capability
    necessity: required
    label: leads a team
  - value: quantum-annealing
    kind: capability
    necessity: preferred
    label: quantum
---

The advertisement.
"""


def ranking(kb=KB, posting=POSTING):
    _, sections, _ = kbindex.read_kb(kb)
    return {r["id"]: r for r in kbindex.rank(kbindex.projects_of(sections),
                                             kbindex.read_posting(posting), TODAY)}


class TheRankingIsTheAnalystsTable(unittest.TestCase):
    """Required ×3, preferred ×1, implicit 0, strength ×2, recency +1 within three
    years and +0.5 at four to six, seniority +1 at or above the posting's."""

    def test_every_axis_scores_as_the_table_says(self):
        rows = ranking()
        # dotnet + team-leadership (6) + kubernetes (1) + strength 5 (10)
        # + one year old (1) + architecture-ownership >= platform-design (1).
        # mentoring is implicit and scores nothing.
        self.assertEqual(rows["proj_alpha"]["score"], 19)
        # dotnet + terraform (6) + strength 3 (6) + five years old (0.5); hands-on is
        # below platform-design.
        self.assertEqual(rows["proj_beta"]["score"], 12.5)
        # nothing matched; strength 4 (8); eight years old (0); platform-design equals
        # the posting's level, which counts.
        self.assertEqual(rows["proj_gamma"]["score"], 9)

    def test_a_retired_project_is_not_ranked(self):
        self.assertNotIn("proj_old", ranking())

    def test_the_order_is_by_score(self):
        _, sections, _ = kbindex.read_kb(KB)
        order = [r["id"] for r in kbindex.rank(kbindex.projects_of(sections),
                                               kbindex.read_posting(POSTING), TODAY)]
        self.assertEqual(order, ["proj_alpha", "proj_beta", "proj_gamma"])

    def test_the_row_shows_the_terms_behind_the_number(self):
        """Never a number you cannot show the terms behind."""
        alpha = ranking()["proj_alpha"]
        self.assertIn("kubernetes (preferred)", alpha["matched"])
        self.assertIn("seniority-match", alpha["matched"])
        self.assertNotIn("mentoring", alpha["matched"])
        self.assertEqual(alpha["missed"], ["terraform"])

    def test_a_synonym_scores_as_absent(self):
        """Exact strings: `.net` is not `dotnet`."""
        posting = POSTING.replace("value: dotnet", "value: .net")
        self.assertEqual(ranking(posting=posting)["proj_alpha"]["score"], 16)


class TheIndexPointsAtTheRightLines(unittest.TestCase):

    def test_a_heading_inside_a_fence_is_not_an_entry(self):
        _, sections, _ = kbindex.read_kb(KB)
        titles = [e["title"] for e in sections["Projects"]["entries"]]
        self.assertEqual(len(titles), 4)
        self.assertNotIn("Not a project", titles)

    def test_an_entry_range_covers_its_heading_to_its_last_line(self):
        _, sections, _ = kbindex.read_kb(KB)
        lines = KB.split("\n")
        alpha = sections["Projects"]["entries"][0]
        self.assertEqual(lines[alpha["start"] - 1], "### Alpha `proj_alpha`")
        self.assertEqual(lines[alpha["end"] - 1], FENCE)
        self.assertEqual(lines[alpha["end"]], "")
        self.assertTrue(lines[alpha["end"] + 1].startswith("### Beta"))

    def test_experience_counts_overlapping_months_once(self):
        """2015-08..2017-02 is nineteen months though the roles sum to twenty-one;
        the ongoing role adds 2026-01..2026-09."""
        _, sections, _ = kbindex.read_kb(KB)
        roles = kbindex.entries_with_blocks(sections["Roles"], "role")
        self.assertEqual(kbindex.experience(roles, TODAY)[0], 19 + 9)

    def test_a_role_of_unknown_state_is_not_run_to_today(self):
        """Only `ongoing` means still going. Counting `unknown` to today inflated the
        one number an eligibility gate compares."""
        _, sections, _ = kbindex.read_kb(KB.replace("state: ongoing", "state: unknown"))
        roles = kbindex.entries_with_blocks(sections["Roles"], "role")
        months, notes = kbindex.experience(roles, TODAY)
        self.assertEqual(months, 19)
        self.assertTrue(any("role_three" in n and "not counted" in n for n in notes), notes)

    def test_the_report_carries_what_an_agent_reads_it_for(self):
        report = kbindex.build(KB, POSTING, TODAY)
        self.assertIn("Experience: 2y 4m", report)
        self.assertIn("`proj_alpha` L", report)
        self.assertIn("capabilities: team-leadership, mentoring", report)
        self.assertIn("`metric_latency`", report)
        self.assertIn("`q_open`", report)
        self.assertNotIn("`q_done`", report)
        self.assertIn("| quantum-annealing | preferred | none | not in the vocabulary |", report)
        self.assertIn("| proj_beta | 12.5 |", report)


class ItRefusesRatherThanGuesses(unittest.TestCase):
    """A project that quietly fails to parse scores as absent evidence on every
    posting. Each of these has to stop the run and name the entry."""

    def refuses(self, kb, *words):
        with self.assertRaises(kbindex.KBError) as caught:
            kbindex.build(kb)
        for word in words:
            self.assertIn(word, str(caught.exception))

    def test_a_project_without_a_block(self):
        kb = KB.replace("### Gamma `proj_gamma`\n\n```yaml", "### Gamma `proj_gamma`\n\n```text")
        self.refuses(kb, "Gamma", "no ```yaml block")

    def test_a_nested_value_where_the_ranking_reads_a_number(self):
        kb = KB.replace("strength: 4\n", "strength:\n  value: 4\n")
        self.refuses(kb, "proj_gamma", "strength")

    def test_a_term_yaml_reads_as_a_boolean(self):
        """`no` unquoted is False to YAML; it would never match a requirement."""
        self.refuses(KB.replace("[python]", "[python, no]"), "proj_gamma", "technologies")

    def test_a_missing_library_is_a_reason_not_a_traceback(self):
        saved = kbindex.yaml
        kbindex.yaml = None
        try:
            with tempfile.TemporaryDirectory() as root:
                kb = Path(root) / "user-knowledgebase.md"
                kb.write_text(KB, encoding="utf-8")
                self.assertEqual(kbindex.main([str(kb)]), 1)
        finally:
            kbindex.yaml = saved

    def test_a_strength_outside_the_scale(self):
        self.refuses(KB.replace("strength: 4\n", "strength: 7\n"), "proj_gamma", "strength")

    def test_a_seniority_outside_the_eight(self):
        self.refuses(KB.replace("seniority: hands-on\n", "seniority: wizard\n"), "proj_beta")

    def test_a_list_that_does_not_close(self):
        self.refuses(KB.replace("[python]", "[python"), "Gamma", "not valid YAML", "line")

    def test_a_fence_that_never_closes(self):
        """Everything below it would vanish from the index, projects included."""
        self.refuses(KB.replace("### Not a project\n```\n", "### Not a project\n"), "never closes")

    def test_a_heading_in_an_html_comment_is_not_an_entry(self):
        kb = KB.replace("## Metrics", "<!--\n### Not a project either\n-->\n\n## Metrics")
        _, sections, _ = kbindex.read_kb(kb)
        self.assertEqual(len(sections["Projects"]["entries"]), 4)

    def test_a_posting_with_no_requirements(self):
        with self.assertRaises(kbindex.KBError):
            kbindex.read_posting("---\ntitle: x\nrequirements: []\n---\n")

    def test_a_retired_flag_that_is_not_a_boolean(self):
        """`retired: "true"` is a string, and ignoring it ranked a retired project."""
        self.refuses(KB.replace("retired: true", 'retired: "true"'), "proj_old", "retired")

    def test_a_bare_colon_in_a_posting_title_says_to_quote_it(self):
        posting = POSTING.replace('title: "Platform Engineer: Core"',
                                  "title: Platform Engineer: Core")
        with self.assertRaises(kbindex.KBError) as caught:
            kbindex.read_posting(posting)
        self.assertIn("line 3", str(caught.exception))
        self.assertIn("quote", caught.exception.fix)

    def test_a_posting_labels_keep_their_colons_and_quotes(self):
        reqs = kbindex.read_posting(POSTING)["requirements"]
        self.assertEqual(reqs[0]["label"], ".NET: the whole stack")
        self.assertEqual(reqs[0]["value"], "dotnet")


class TheCommand(unittest.TestCase):

    def test_the_module_ranks_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as root:
            kb, posting = Path(root) / "user-knowledgebase.md", Path(root) / "posting.md"
            kb.write_text(KB, encoding="utf-8")
            posting.write_text(POSTING, encoding="utf-8")
            code, out = run(KBINDEX, kb, "--rank", posting, "--today", "2026-09-23")
        self.assertEqual(code, 0, out)
        self.assertIn("# Ranking", out)
        self.assertIn("| proj_alpha | 19 |", out)

    def test_a_malformed_file_exits_one_with_a_fix(self):
        with tempfile.TemporaryDirectory() as root:
            kb = Path(root) / "user-knowledgebase.md"
            kb.write_text(KB.replace("strength: 4\n", "strength: many\n"), encoding="utf-8")
            code, out = run(KBINDEX, kb)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("fix:", out)


if __name__ == "__main__":
    unittest.main()
