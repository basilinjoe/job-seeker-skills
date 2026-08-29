"""The compiler, and the guarantee that replaced the schema.

A schema used to assert that the record had the right shape. Nothing hand-writes the
record any more, so the question worth asking is not "does it match a description of
itself" but "does the thing that consumes it work". These tests compile a bundle and
then render it, which is the only claim that matters.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import SCRIPTS, run

COMPILE = SCRIPTS / "okf_compile.py"
RENDER = SCRIPTS / "render_resume.py"
VALIDATE_URS = SCRIPTS / "validate_urs.py"

PERSON = """---
type: Person
title: "Ada Vance"
description: "Platform architect, eleven years, Melbourne."
status: confirmed
---

# Contact

| Field | Value |
|---|---|
| Name | Ada Vance |
| Location | Melbourne, VIC, Australia |
| Email | ada@example.com |
| Phone | +61 400 000 000 |

**Home address (private - never render on a resume):** 12 Somewhere St.
"""

ORG = """---
type: Organisation
relationship: employer
title: "Meridian Health"
description: "Aged-care provider."
status: confirmed
---
"""

ROLE_ONE = """---
type: Role
title: "Senior Engineer"
organisation: meridian-health
start: 2019-04
end: 2021-12
state: ended
seniority: technical-ownership
change: hire
status: confirmed
---
"""

ROLE_TWO = """---
type: Role
title: "Principal Engineer"
organisation: meridian-health
start: 2022-01
state: ongoing
seniority: architecture-ownership
change: promotion
status: confirmed
---
"""

PROJECT = """---
type: Project
title: "Care coordination platform"
description: "Multi-tenant platform for aged-care providers."
role: senior-engineer
status: confirmed
strength: 5
recency: 2021
seniority: architecture-ownership
domains: [healthcare]
capabilities: [ai-platform-architecture]
technologies: [azure]
---

# The problem

The legacy scheduler could not express care-plan constraints.

# Bullets

- Cut event propagation from 5 minutes to under 1 second across the integrated estate.
  metric: Event propagation latency
  status: confirmed
"""

METRICS = """---
type: Metric Set
title: "Verified metrics"
status: confirmed
---

# Confirmed numbers

| Metric | Value | Project | Source | Notes |
|---|---|---|---|---|
| Event propagation latency | **5 min to under 1 s** | [Care](../projects/care.md) | interview | |
"""

POSITIONING = """---
type: Positioning
title: "How the resume frames her"
status: confirmed
---

# Summary variant A - positioning-led (default)

> Platform architect who builds what other teams build on.

Use for: direct applications.
"""

SKILLS = """---
type: Skill Set
title: "Core competencies"
status: confirmed
---

# Skills

- C# / .NET
  id: skill_dotnet
  category: language
  aliases: C#, .NET, ASP.NET Core
"""


def build_bundle(root):
    root = Path(root)
    for folder, name, text in (
        ("profile", "identity.md", PERSON),
        ("profile", "positioning.md", POSITIONING),
        ("organisations", "meridian-health.md", ORG),
        ("roles", "senior-engineer.md", ROLE_ONE),
        ("roles", "principal-engineer.md", ROLE_TWO),
        ("projects", "care.md", PROJECT),
        ("achievements", "metrics.md", METRICS),
        ("skills", "competencies.md", SKILLS),
    ):
        directory = root / folder
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text, encoding="utf-8")
    (root / "index.md").write_text(
        "---\ntype: Index\ntitle: \"Bundle\"\nokf_bundle: 5\n---\n", encoding="utf-8")
    return root


class CompileCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bundle = build_bundle(self.tmp / "bundle")

    def compile(self):
        out = self.tmp / "record.json"
        code, text = run(COMPILE, self.bundle, "--dump-record", out, "--quiet")
        self.assertEqual(code, 0, text)
        return json.loads(out.read_text(encoding="utf-8"))


class Relations(CompileCase):
    def test_roles_at_one_employer_become_one_engagement(self):
        doc = self.compile()
        self.assertEqual(len(doc["engagements"]), 1)
        positions = doc["engagements"][0]["positions"]
        self.assertEqual([p["title"] for p in positions],
                         ["Senior Engineer", "Principal Engineer"])
        self.assertEqual([p["change"] for p in positions], ["hire", "promotion"])

    def test_the_engagement_spans_its_positions(self):
        period = self.compile()["engagements"][0]["period"]
        self.assertEqual(period["start"]["value"], "2019-04")
        self.assertEqual(period["state"], "ongoing")
        self.assertNotIn("end", period)

    def test_a_role_with_no_organisation_names_the_file(self):
        (self.bundle / "roles" / "orphan.md").write_text(
            "---\ntype: Role\ntitle: \"Orphan\"\nstart: 2020-01\nstate: ongoing\n---\n",
            encoding="utf-8")
        code, out = run(COMPILE, self.bundle)
        self.assertEqual(code, 1)
        self.assertIn("orphan.md", out)
        self.assertIn("organisation", out)

    def test_an_unknown_organisation_is_refused_not_invented(self):
        """The failure this whole design exists to stop: a record entity with no
        concept behind it, which is how two employers appeared on a resume that the
        bundle had never heard of."""
        (self.bundle / "roles" / "elsewhere.md").write_text(
            "---\ntype: Role\ntitle: \"Elsewhere\"\norganisation: nowhere-inc\n"
            "start: 2020-01\nstate: ongoing\n---\n", encoding="utf-8")
        code, out = run(COMPILE, self.bundle)
        self.assertEqual(code, 1)
        self.assertIn("nowhere-inc", out)


class AuthoredContent(CompileCase):
    def test_a_bullet_carries_its_metric_and_its_status(self):
        project = self.compile()["projects"][0]
        achievement = project["achievements"][0]
        self.assertEqual(achievement["provenance"]["status"], "confirmed")
        self.assertEqual(achievement["metrics"][0]["value"], "5 min to under 1 s")

    def test_a_bullet_naming_an_unknown_metric_fails(self):
        path = self.bundle / "projects" / "care.md"
        path.write_text(path.read_text(encoding="utf-8")
                        .replace("metric: Event propagation latency",
                                 "metric: A number nobody recorded"), encoding="utf-8")
        code, out = run(COMPILE, self.bundle)
        self.assertEqual(code, 1)
        self.assertIn("metrics.md", out)

    def test_only_the_quoted_summary_becomes_a_narrative(self):
        narratives = self.compile()["narratives"]
        self.assertEqual(len(narratives), 1)
        self.assertIn("Platform architect", narratives[0]["text"])
        self.assertNotIn("direct applications", narratives[0]["text"])

    def test_skills_are_read_from_their_block(self):
        skills = self.compile()["skills"]
        self.assertEqual(skills[0]["id"], "skill_dotnet")
        self.assertIn("ASP.NET Core", skills[0]["aliases"])


class Privacy(CompileCase):
    def test_the_private_address_never_reaches_the_record(self):
        """identity.md marks it 'never render on a resume'. A compile that swept up
        every line in the file would put it one careless view away from printing."""
        self.assertNotIn("Somewhere St", json.dumps(self.compile()))


class Inflation(CompileCase):
    def test_a_number_no_metric_backs_stops_the_render(self):
        """The check that survives the schema's removal, and the one that matters:
        a rewritten clause that inflates a number is caught before it renders."""
        path = self.bundle / "projects" / "care.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "across the integrated estate", "across 15 integrated applications"),
            encoding="utf-8")
        code, out = run(VALIDATE_URS, self.bundle)
        self.assertEqual(code, 1, out)
        self.assertIn("'15' appears in the text but in no metric", out)


class Consumers(CompileCase):
    def test_the_compiled_bundle_validates(self):
        code, out = run(VALIDATE_URS, self.bundle)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_the_compiled_bundle_renders(self):
        """The guarantee that replaced the schema: the consumer works."""
        out_dir = self.tmp / "out"
        code, out = run(RENDER, self.bundle, "--out", out_dir, "--format", "txt")
        self.assertEqual(code, 0, out)
        rendered = list(Path(out_dir).glob("*.txt"))
        self.assertTrue(rendered, out)
        text = rendered[0].read_text(encoding="utf-8", errors="replace")
        self.assertIn("Ada Vance", text)
        self.assertIn("Platform architect", text)
        self.assertNotIn("Somewhere St", text)


if __name__ == "__main__":
    unittest.main()
