"""jsk.kbindex: the Markdown knowledge base reader `jsk migrate` runs.

Retired as `jsk index`, and its report and ranking with it; the reader stays one release
because `jsk migrate` reads the Markdown with it, and release N+1 deletes it and this
file. The ranking is graph.queries.rank now, tested with `jsk match`.
"""
import datetime
import unittest

from jsk import kbindex

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

    def test_a_date_that_is_not_one_is_refused_with_its_fix(self):
        """The count moved to graph.scoring, which raises ValueError; the reader still
        refuses it the way it refuses every other field, naming the entry."""
        _, sections, _ = kbindex.read_kb(KB.replace("start: 2016-03", "start: spring"))
        roles = kbindex.entries_with_blocks(sections["Roles"], "role")
        with self.assertRaises(kbindex.KBError) as caught:
            kbindex.experience(roles, TODAY)
        self.assertIn("role_two", str(caught.exception))
        self.assertIn("YYYY-MM", caught.exception.fix)


def read(kb):
    """Everything `jsk migrate` asks of the reader: the entries, the projects' fields,
    and the roles' dates."""
    _, sections, _ = kbindex.read_kb(kb)
    kbindex.projects_of(sections)
    kbindex.experience(kbindex.entries_with_blocks(sections["Roles"], "role"), TODAY)


class ItRefusesRatherThanGuesses(unittest.TestCase):
    """A project that quietly fails to parse would migrate as absent evidence. Each of
    these has to stop the run and name the entry."""

    def refuses(self, kb, *words):
        with self.assertRaises(kbindex.KBError) as caught:
            read(kb)
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


if __name__ == "__main__":
    unittest.main()
