"""The compiler, and the guarantee that replaced the schema.

A schema used to assert that the record had the right shape. Nothing hand-writes the
record any more, so the question worth asking is not "does it match a description of
itself" but "does the thing that consumes it work". These tests compile a bundle and
then render it, which is the only claim that matters.
"""
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import RENDER_RESUME, load_script, run

COMPILE = "jsk_okf.okf_compile"
RENDER = RENDER_RESUME
SCORE = "jsk_okf.score_projects"
VALIDATE_URS = "jsk_okf.validate_urs"

okf_compile = load_script(COMPILE)

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


# The working copy: the view being edited for a target that has not been sent yet.
# `budget.pages` is the tell in these tests - it is a value only this file sets.
VIEW_WORKING = """---
type: View
id: view_meridian_principal
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
budget:
  pages: 99
---
"""

# What mode-ship.md freezes beside a sent application: the same view, the same id,
# the settings as they were on the day it went out - plus the concept bookkeeping
# every OKF file carries.
VIEW_FROZEN = """---
type: View
title: "Meridian - principal engineer (as sent)"
frozen: true
frozen_date: "2026-01-14"
id: view_meridian_principal
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
budget:
  pages: 2
---
"""

# The two concepts that sit beside a working view and that the record has never read
# a field of. Both carry `type:`, so before the walk was narrowed they were opened,
# YAML-parsed and bucketed by type on every compile.
POSTING = """---
type: Job Posting
title: "Principal Engineer"
company: "Meridian Health"
seniority: architecture-ownership
domains: [healthcare]
requirements:
  - value: ai-platform-architecture
    kind: capability
    necessity: required
    label: "platform architecture"
  - value: azure
    kind: technology
    necessity: preferred
    label: "Azure"
---

# Advertisement

Meridian Health is hiring a principal engineer for its care platform.
"""

GAPS = """---
type: Gap Assessment
title: "Meridian - what is missing"
status: confirmed
---

# Verdict

Strong fit.
"""

VIEW_ARCHIVED_ONLY = """---
type: View
id: view_kestrel_staff
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
budget:
  pages: 2
---
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


class TheArchiveIsNotTheRecord(CompileCase):
    """tailoring/applications/ holds what has already been sent, and the compiler
    does not read it. Every one of these failed before it stopped."""

    def write(self, rel, text):
        path = self.bundle / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_frozen_view_does_not_shadow_the_working_copy(self):
        """The defect: `applications` sorts before `targets`, so the copy frozen at
        submission won the de-duplication in build_views() and the view being edited
        was discarded. Its own comment claimed the opposite."""
        self.write("tailoring/targets/meridian-principal.view.md", VIEW_WORKING)
        self.write("tailoring/applications/2026-01-14-meridian-principal.view.md",
                   VIEW_FROZEN)
        views = self.compile()["views"]
        self.assertEqual([v["id"] for v in views], ["view_meridian_principal"])
        self.assertEqual(views[0]["budget"]["pages"], 99)

    def test_the_archive_contributes_nothing_to_the_record(self):
        """A hundred sent applications put a hundred frozen views into a record that
        several agents read on every run - 59% of record.json by volume, none of it
        career evidence."""
        self.write("tailoring/applications/2025-11-03-kestrel-staff.view.md",
                   VIEW_ARCHIVED_ONLY)
        doc = self.compile()
        self.assertEqual(doc["views"], [])
        self.assertNotIn("view_kestrel_staff", json.dumps(doc))

    def test_a_directory_called_applications_elsewhere_is_still_read(self):
        """Pruned by path from the bundle root, not by name: a person's own
        projects/applications/ is filing, not the tailoring archive."""
        self.write("projects/applications/intake.md",
                   "---\ntype: Project\ntitle: \"Intake rewrite\"\n"
                   "status: confirmed\n---\n")
        titles = [p["title"] for p in self.compile()["projects"]]
        self.assertIn("Intake rewrite", titles)


class OnlyTheViewsAskedFor(CompileCase):
    """Nothing retires a working view, so a bundle carries one per target forever.

    At a hundred applications that is half of record.json by volume, handed whole to
    every agent that reads it, ninety-nine of them irrelevant to the one application
    being worked on. Narrowing is the caller's to ask for, never the default: the
    record gate compiles the bundle to check every view on disk.
    """

    def setUp(self):
        super().setUp()
        for slug, pages in (("meridian-principal", 99), ("kestrel-staff", 2)):
            path = self.bundle / "tailoring" / "targets" / f"{slug}.view.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"---\ntype: View\nid: view_{slug.replace('-', '_')}\n"
                f"format_profile: presentation\nregion_profile: urs:profile:au/1\n"
                f"provenance_floor: confirmed\nbudget:\n  pages: {pages}\n---\n",
                encoding="utf-8")

    def ids(self, *args):
        out = self.tmp / "record.json"
        code, text = run(COMPILE, self.bundle, "--dump-record", out, "--quiet", *args)
        self.assertEqual(code, 0, text)
        return [v["id"] for v in json.loads(out.read_text(encoding="utf-8"))["views"]]

    def test_the_default_is_still_every_view_on_disk(self):
        """A view with a misspelt key is broken whether or not anyone is rendering
        it this week, and validate_urs.py is what says so."""
        self.assertEqual(sorted(self.ids()),
                         ["view_kestrel_staff", "view_meridian_principal"])

    def test_a_named_view_is_the_only_one_emitted(self):
        self.assertEqual(self.ids("--view", "view_kestrel_staff"),
                         ["view_kestrel_staff"])

    def test_view_is_repeatable_and_keeps_the_order_asked_for(self):
        """Named in the reverse of the order they sit on disk, so a compile that
        ignored the flag and emitted everything could not pass this."""
        self.assertEqual(
            self.ids("--view", "view_meridian_principal", "--view", "view_kestrel_staff"),
            ["view_meridian_principal", "view_kestrel_staff"])

    def test_no_views_emits_none(self):
        self.assertEqual(self.ids("--no-views"), [])

    def test_an_unknown_view_fails_and_says_what_is_on_disk(self):
        """Emitting nothing for a name nobody recognises would look like a clean
        compile, and then render an empty selection."""
        code, out = run(COMPILE, self.bundle, "--view", "view_kestrel_stafff")
        self.assertEqual(code, 1, out)
        self.assertIn("view_kestrel_stafff", out)
        self.assertIn("view_meridian_principal", out)
        self.assertIn("fix:", out)

    def test_the_flag_value_is_not_mistaken_for_the_bundle(self):
        """`--view ID` before the path used to leave ID sitting at args[0]."""
        out = self.tmp / "record.json"
        code, text = run(COMPILE, "--view", "view_kestrel_staff", "--quiet",
                         "--dump-record", out, self.bundle)
        self.assertEqual(code, 0, text)

    def test_narrowing_changes_nothing_else_in_the_record(self):
        full = self.tmp / "full.json"
        one = self.tmp / "one.json"
        run(COMPILE, self.bundle, "--dump-record", full, "--quiet")
        run(COMPILE, self.bundle, "--dump-record", one, "--quiet", "--no-views")
        a = json.loads(full.read_text(encoding="utf-8"))
        b = json.loads(one.read_text(encoding="utf-8"))
        a.pop("views"), b.pop("views")
        self.assertEqual(a, b)


class ViewsCarryTheirOwnBookkeeping(CompileCase):
    """A View on disk is an OKF concept; the View that reaches URS is pure URS.

    Two validators disagreed about this. validate_bundle.py recommends title,
    description and timestamp on every concept and mode-ship.md instructs `frozen:
    true`; validate_urs.py's VIEW_KEYS rejects all four, so following the bundle's own
    advice broke the record gate permanently.
    """

    def write_view(self, text):
        path = self.bundle / "tailoring" / "targets" / "meridian-principal.view.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    BOOKKEEPING = """---
type: View
title: "Meridian - principal engineer"
description: "What this application leads with."
timestamp: 2026-08-30
status: confirmed
id: view_meridian_principal
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
---
"""

    def test_a_bare_yaml_date_does_not_end_the_compile_in_a_traceback(self):
        """`timestamp: 2026-08-30` unquoted is a datetime.date to YAML and nothing
        at all to json.dumps, which raised TypeError from inside the encoder. Every
        path that serialises the record hit it - `okf.py score` included."""
        self.write_view(self.BOOKKEEPING)
        code, out = run(COMPILE, self.bundle, "--dump-record", "-")
        self.assertEqual(code, 0, out)
        self.assertNotIn("Traceback", out)

    def test_concept_keys_are_stripped_before_the_view_is_emitted(self):
        self.write_view(self.BOOKKEEPING)
        view = self.compile()["views"][0]
        for key in ("type", "title", "description", "timestamp", "status"):
            self.assertNotIn(key, view)
        self.assertEqual(view["provenance_floor"], "confirmed")

    def test_the_record_gate_accepts_the_compiled_view(self):
        self.write_view(self.BOOKKEEPING)
        code, out = run(VALIDATE_URS, self.bundle)
        self.assertEqual(code, 0, out)


class ABundleWithNothingInIt(unittest.TestCase):
    """A compile that reports success on an empty bundle teaches every gate after
    it that an empty document is a passing one."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bundle = self.tmp / "bundle"
        (self.bundle / "projects").mkdir(parents=True)
        (self.bundle / "index.md").write_text(
            "---\ntype: Index\ntitle: \"Bundle\"\nokf_bundle: 6\n---\n", encoding="utf-8")

    def test_a_scaffolded_bundle_does_not_compile_to_a_record(self):
        code, out = run(COMPILE, self.bundle)
        self.assertEqual(code, 1, out)
        self.assertIn("Person", out)
        self.assertIn("fix:", out)

    def test_a_person_alone_is_not_a_record_either(self):
        (self.bundle / "profile").mkdir()
        (self.bundle / "profile" / "identity.md").write_text(PERSON, encoding="utf-8")
        code, out = run(COMPILE, self.bundle)
        self.assertEqual(code, 1, out)
        self.assertIn("no Role and no Project", out)

    def test_a_sparse_but_real_bundle_still_compiles(self):
        """The floor is a person and one thing to say about them. A bundle of
        projects and no employment history is a legitimate one."""
        (self.bundle / "profile").mkdir()
        (self.bundle / "profile" / "identity.md").write_text(PERSON, encoding="utf-8")
        (self.bundle / "projects" / "intake.md").write_text(
            "---\ntype: Project\ntitle: \"Intake rewrite\"\nstatus: confirmed\n---\n",
            encoding="utf-8")
        code, out = run(COMPILE, self.bundle)
        self.assertEqual(code, 0, out)


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


class TailoredCase(CompileCase):
    """A bundle with one answered target: a posting, its assessment, and a view."""

    def setUp(self):
        super().setUp()
        targets = self.bundle / "tailoring" / "targets"
        targets.mkdir(parents=True, exist_ok=True)
        for name, text in (("meridian-principal.posting.md", POSTING),
                           ("meridian-principal.gaps.md", GAPS),
                           ("meridian-principal.view.md", VIEW_WORKING)):
            (targets / name).write_text(text, encoding="utf-8")

    def under_tailoring(self, *args, **kwargs):
        """The stems concepts() read out of tailoring/, in whatever mode."""
        return sorted(
            stem for stem, _, _, _ in okf_compile.concepts(self.bundle, *args, **kwargs)
            if stem.startswith("meridian-principal."))


class TailoringIsNotCareerRecord(TailoredCase):
    """A View is the only thing the record takes from tailoring/.

    The posting and the gap assessment beside it were parsed on every compile and
    then never read again: at a hundred answered targets that is 300 of the 341
    concepts a compile walked to build a record out of 41, and 408ms of a 946ms run.
    """

    def test_only_a_view_is_read_under_tailoring(self):
        self.assertEqual(self.under_tailoring(), ["meridian-principal.view"])

    def test_asking_for_no_views_does_not_enter_the_directory(self):
        self.assertEqual(self.under_tailoring(tailoring="none"), [])

    def test_the_view_still_reaches_the_record(self):
        """The narrowing is a walk that reads less, not a record that says less."""
        self.assertEqual([v["id"] for v in self.compile()["views"]],
                         ["view_meridian_principal"])

    def test_a_narrowing_nobody_asked_for_is_refused(self):
        """A typo in this argument reads less and says nothing - every check written
        about what the walk found still passes on what it did not find."""
        with self.assertRaises(ValueError):
            okf_compile.concepts(self.bundle, tailoring="veiws")


class TheCensusKeepsItsOwnEyes(TailoredCase):
    """census() walks everything, including what the record stopped reading.

    check_conservation in validate_urs.py is the only check that can see a whole
    concept type go missing - every other one iterates a record key, and an empty list
    satisfies each of them, which is how `views: []` passed for months. It compares
    what census() found on disk against what the record emitted, so a census sharing
    load()'s narrowed walk would read no views for a bundle full of them and agree
    that nothing had been dropped.
    """

    def test_the_census_counts_what_the_record_never_reads(self):
        counts = okf_compile.census(self.bundle)
        self.assertEqual(counts.get("Job Posting"), 1)
        self.assertEqual(counts.get("Gap Assessment"), 1)
        self.assertEqual(counts.get("View"), 1)

    def test_the_census_sees_views_the_compile_was_told_to_skip(self):
        doc = okf_compile.load(self.bundle, views=[])
        self.assertEqual(doc["views"], [])
        self.assertEqual(okf_compile.census(self.bundle).get("View"), 1)

    def test_a_type_that_compiles_to_nothing_still_fails_the_record_gate(self):
        """The regression this gate exists for, run end to end: the bundle holds a
        Skill Set, the record holds no skills, and nothing else in validate_urs.py can
        tell that apart from a bundle that never had one."""
        (self.bundle / "skills" / "competencies.md").write_text(
            "---\ntype: Skill Set\ntitle: \"Core competencies\"\nstatus: confirmed\n"
            "---\n\nNothing under a `# Skills` heading, so nothing compiles.\n",
            encoding="utf-8")
        self.assertEqual(self.compile()["skills"], [])
        code, out = run(VALIDATE_URS, self.bundle)
        self.assertEqual(code, 1, out)
        self.assertIn("'Skill Set'", out)
        self.assertIn("skills", out)


class CompactRecords(TailoredCase):
    """`--compact` drops the indentation and nothing else.

    Every reader of a record parses it as JSON. On a hundred-target bundle the
    indentation is 34% of the file - a third of an agent's read spent on whitespace.
    """

    def record_text(self, *args):
        out = self.tmp / "record.json"
        code, text = run(COMPILE, self.bundle, "--dump-record", out, "--quiet", *args)
        self.assertEqual(code, 0, text)
        return out.read_text(encoding="utf-8")

    def test_compact_and_indented_records_parse_to_the_same_object(self):
        self.assertEqual(json.loads(self.record_text("--compact")),
                         json.loads(self.record_text()))

    def test_compact_is_smaller_and_carries_no_indentation(self):
        compact, indented = self.record_text("--compact"), self.record_text()
        self.assertNotIn('\n  "urs"', compact)
        self.assertIn('\n  "urs"', indented)
        self.assertLess(len(compact), len(indented))


class TheScorerProfile(TailoredCase):
    """`--for score` emits the keys the ranking runs on, and nothing else.

    projects[] is 80% of the record and the scorer slice is 39% of projects[], because
    the rest is achievement prose score_projects.py does not read a word of. The
    projection is computed here so there is one definition of what a scorer needs -
    a second list of keys elsewhere is the transcription that drifts.
    """

    def scored(self, *args):
        out = self.tmp / "score.json"
        code, text = run(COMPILE, self.bundle, "--dump-record", out, "--quiet",
                         "--for", "score", *args)
        self.assertEqual(code, 0, text)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_a_project_carries_only_what_the_ranking_reads(self):
        project = self.scored()["projects"][0]
        self.assertLessEqual(set(project), set(okf_compile.SCORE_PROJECT_KEYS))
        for key in ("capabilities", "technologies", "domains", "seniority",
                    "strength", "period", "title", "id"):
            self.assertIn(key, project)

    def test_no_achievement_prose_survives_the_projection(self):
        self.assertNotIn("care-plan", json.dumps(self.scored()))
        self.assertNotIn("Cut event propagation", json.dumps(self.scored()))

    def test_narratives_education_and_credentials_are_emitted_empty(self):
        doc = self.scored()
        for key in ("narratives", "education", "credentials"):
            self.assertEqual(doc[key], [], key)

    def test_the_ranking_is_the_same_one(self):
        """The claim that matters: a smaller record the scorer reads identically. If
        the projection dropped a key score_projects.py scores on, the table would
        still print - a term silently gone inert is what this test is here to catch."""
        posting = self.tmp / "posting.json"
        code, text = run(COMPILE,
                         self.bundle / "tailoring" / "targets"
                         / "meridian-principal.posting.md")
        self.assertEqual(code, 0, text)
        posting.write_text(text, encoding="utf-8")

        full = self.tmp / "full.json"
        run(COMPILE, self.bundle, "--dump-record", full, "--quiet", "--no-views")
        narrow = self.tmp / "score.json"
        run(COMPILE, self.bundle, "--dump-record", narrow, "--quiet", "--no-views",
            "--for", "score")
        self.assertEqual(run(SCORE, narrow, posting, "--as-of", "2026"),
                         run(SCORE, full, posting, "--as-of", "2026"))

    def test_the_projection_composes_with_compact(self):
        self.assertEqual(self.scored("--compact"), self.scored())

    def test_an_unknown_profile_is_refused_and_names_the_ones_there_are(self):
        code, out = run(COMPILE, self.bundle, "--for", "scores")
        self.assertEqual(code, 2, out)
        self.assertIn("score", out)

    def test_for_with_no_value_is_refused_rather_than_ignored(self):
        code, out = run(COMPILE, self.bundle, "--for")
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
