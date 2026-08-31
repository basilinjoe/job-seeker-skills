"""Tranche 2: the posting, the assessment and the view a tailoring run writes.

Every test pins a rule from the write-CLI design, `references/bundle-spec.md`
("Postings on disk"), `references/view-format.md` or `agents/jsk-tailor-analyst.md`.
The rules worth most are the ones about the three files' relationship - a `.gaps.md`
or a `.view.md` with no `.posting.md` beside it is a hard error in
`validate_bundle.py` - and the ones about a view's keys, because
`validate_urs.py` fails a key it does not know and a view is the one concept whose
frontmatter *is* the document it compiles to.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import (INIT_BUNDLE, OKF_COMPILE, SCRIPTS, VALIDATE_BUNDLE,
                      VALIDATE_URS, authoring_module, run)

commands = authoring_module("authoring.commands")
tailoring = authoring_module("authoring.tailoring")
body = authoring_module("authoring.body")
concept = authoring_module("authoring.concept")
schema = authoring_module("authoring.schema")

OKF = SCRIPTS / "okf.py"

ORGANISATION = """---
type: Organisation
title: "Acme Health"
description: "Aged-care provider."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
employment: employment
location: "Melbourne"
---

# What they do

Aged care across Victoria.
"""

ROLE = """---
type: Role
title: "Lead Engineer"
description: "Platform lead."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
organisation: acme-health
start: 2021-02
state: ongoing
seniority: architecture-ownership
---

# What the role was

Platform ownership.
"""

PROJECT = """---
type: Project
title: "Care coordination platform"
description: "Multi-tenant platform for aged-care providers."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
role: lead-engineer-acme
strength: 5
recency: 2026
seniority: architecture-ownership
domains: [healthcare]
capabilities: [ai-platform-architecture]
technologies: [azure]
---

# The problem

The legacy scheduler could not express care-plan constraints.

# Bullets

- Rebuilt the scheduler so care-plan constraints were expressible.
  id: ach_scheduler
  status: confirmed
- Owned the platform across every site in the network.
  id: ach_platform
  status: confirmed
"""

# A second project whose bullets write no id down, so the ids `view include` has
# to accept are the ones okf_compile derives from position.
UNNUMBERED = """---
type: Project
title: "Rostering service"
description: "Shift allocation for care staff."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
role: lead-engineer-acme
strength: 4
recency: 2025
seniority: technical-ownership
domains: [healthcare]
capabilities: [ai-platform-architecture]
---

# The problem

Rosters were built by hand.

# Bullets

- Replaced the manual roster with an allocation service.
  status: confirmed
"""

SKILL_SET = """---
type: Skill Set
title: "Competencies"
description: "What they can do."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
---

# Skills

- Azure
  id: skill_azure
  category: cloud-platform
"""

ADVERTISEMENT = ("We are hiring a Staff Software Engineer to own features end to "
                 "end,\nfrom schema to pixel. TypeScript and Postgres throughout.\n")

ASSESSMENT = """# Eligibility

Pass. The record holds Australian permanent residence.

# Requirements

| Requirement | Need | Verdict | Evidence | Shortfall |
|---|---|---|---|---|
| ai-platform-architecture | required | satisfied | prj_care_platform | |

# Where this falls short

- **Terraform.** Named throughout the posting; the record's IaC is Bicep.
"""


class TargetsCase(unittest.TestCase):
    """A scaffolded bundle with an organisation, a role, two projects and a skill.

    Written directly rather than through `okf project add`: this file is about
    tranche 2, and a fixture built out of tranche 1's commands would fail for
    reasons that have nothing to do with what is being tested.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)
        self.targets = self.root / "tailoring" / "targets"
        self.log = self.root / "log.md"
        self.index = self.targets / "index.md"
        for rel, text in (("organisations/acme-health.md", ORGANISATION),
                          ("roles/lead-engineer-acme.md", ROLE),
                          ("projects/care-platform.md", PROJECT),
                          ("projects/rostering.md", UNNUMBERED),
                          ("skills/competencies.md", SKILL_SET)):
            (self.root / rel).write_text(text, encoding="utf-8")
        self.populate("ai-platform-architecture", "data-sovereignty")

    def populate(self, *terms):
        """List `terms` under the scaffolder's first theme heading.

        init_bundle.py puts its only example values INSIDE a fence, so a fresh
        bundle's vocabulary is empty and both gates' `if vocab and ...` switch the
        capability check off. A test about an unlisted capability that skips this
        step proves nothing.
        """
        path = self.root / "framework" / "capability-vocabulary.md"
        rows = "".join(f"- `{term}`\n" for term in terms)
        text = path.read_text(encoding="utf-8").replace(
            "# Architecture & design\n", "# Architecture & design\n\n" + rows)
        path.write_text(text, encoding="utf-8")

    # -- driving the commands ---------------------------------------------------

    def okf(self, *args, stdin=None):
        """One command as the CLI runs it, in this interpreter.

        In process rather than as a subprocess: `commands.main` is the whole of
        what okf.py's write nouns do, and a test that spawned an interpreter per
        verb would spend most of its time on the interpreter. One test drives the
        real okf.py as well, to prove the wiring.
        """
        out = io.StringIO()
        # `--bundle` last, not first: the noun and the verb are positional, and
        # argparse reads the first token as the noun whatever it is.
        argv = [str(a) for a in args] + ["--bundle", str(self.root)]
        original = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out):
                code = commands.main(argv)
        except SystemExit as exit_code:            # argparse's own refusals
            code = exit_code.code
        finally:
            sys.stdin = original
        return code, out.getvalue()

    def posting(self, *extra, stdin=ADVERTISEMENT, **over):
        """`posting add` with everything a complete one takes. None drops a flag."""
        values = {"company": "Ashby", "title": "Staff Software Engineer",
                  "slug": "ashby-staff-engineer",
                  "description": "Staff engineer, product engineering."}
        values.update(over)
        args = ["posting", "add"]
        for key, value in values.items():
            if value is not None:
                args += ["--" + key.replace("_", "-"), str(value)]
        return self.okf(*args, "--body", "-", *extra, stdin=stdin)

    def gaps(self, *extra, stem="ashby-staff-engineer", stdin=ASSESSMENT):
        return self.okf("gaps", "write", "--posting", stem, "--fit", "partial",
                        "--body", "-", *extra, stdin=stdin)

    def view(self, *extra, stem="ashby-staff-engineer", profile="ats-maximal"):
        args = ["view", "create", "--posting", stem]
        if profile is not None:
            args += ["--format-profile", profile]
        return self.okf(*args, *extra)

    def target(self, kind, stem="ashby-staff-engineer"):
        return self.targets / f"{stem}.{kind}.md"

    def frontmatter(self, kind, stem="ashby-staff-engineer"):
        return concept.read(str(self.target(kind, stem))).meta

    def text(self, kind, stem="ashby-staff-engineer"):
        return self.target(kind, stem).read_text(encoding="utf-8")


class PostingAdd(TargetsCase):
    """`tailoring/targets/<slug>.posting.md` - the advertisement, verbatim."""

    def test_a_posting_is_written_with_the_advertisement_in_its_body(self):
        code, out = self.posting()
        self.assertEqual(code, 0, out)
        text = self.text("posting")
        meta = self.frontmatter("posting")
        self.assertEqual(meta["type"], "Job Posting")
        self.assertEqual(meta["company"], "Ashby")
        self.assertEqual(meta["title"], "Staff Software Engineer")
        # Verbatim, and in the body. jsk-tailor-analyst.md: "Do not put the
        # advertisement in the frontmatter. It is already in the body, verbatim,
        # which is what the archive keeps and what a person re-reads."
        self.assertIn(ADVERTISEMENT, text)
        self.assertNotIn("schema to pixel", text.split("---\n")[1])

    def test_requirements_is_written_empty_so_the_compiler_finds_the_key(self):
        self.assertEqual(self.posting()[0], 0)
        self.assertIn("requirements: []", self.text("posting"))
        self.assertEqual(self.frontmatter("posting")["requirements"], [])

    def test_the_slug_defaults_to_the_company_and_the_title(self):
        code, out = self.posting(slug=None)
        self.assertEqual(code, 0, out)
        self.assertTrue(
            (self.targets / "ashby-staff-software-engineer.posting.md").exists(),
            sorted(p.name for p in self.targets.iterdir()))

    def test_repeated_domains_are_dropped(self):
        code, out = self.posting("--domain", "saas", "--domain", "saas",
                                 "--domain", "hr-tech")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("posting")["domains"],
                         ["saas", "hr-tech"])

    def test_the_index_and_the_log_are_written(self):
        self.assertEqual(self.posting()[0], 0)
        self.assertIn("(ashby-staff-engineer.posting.md)",
                      self.index.read_text(encoding="utf-8"))
        self.assertIn("Added tailoring/targets/ashby-staff-engineer.posting.md",
                      self.log.read_text(encoding="utf-8"))

    def test_an_empty_advertisement_is_refused(self):
        code, out = self.posting(stdin="   \n")
        self.assertEqual(code, 1)
        self.assertIn("--body is empty", out)
        self.assertIn("fix:", out)
        self.assertFalse(self.target("posting").exists())

    def test_a_posting_that_is_already_there_is_not_overwritten(self):
        self.assertEqual(self.posting()[0], 0)
        code, out = self.posting()
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)

    def test_a_missing_company_is_refused_with_the_reason_it_is_required(self):
        code, out = self.posting(company=None)
        self.assertEqual(code, 1)
        self.assertIn("company is required on a Job Posting", out)
        # The stem is derived FROM company and title, so a check that ran after the
        # derivation would refuse a filename rather than the missing flag.
        self.assertNotIn("no filename can be derived", out)

    def test_an_unmarked_predecessor_is_refused(self):
        # validate_bundle.py:301-310 turns this into an error the moment the
        # posting lands beside it, and not before - so no gate can warn about it
        # and this layer is the only thing that can refuse.
        (self.targets / "ashby-staff-engineer.md").write_text(
            "---\ntype: Job Posting\ntitle: \"Old\"\n---\n\nThe old copy.\n",
            encoding="utf-8")
        code, out = self.posting()
        self.assertEqual(code, 1)
        self.assertIn("says nothing about which document is live", out)
        self.assertIn("superseded_by: ashby-staff-engineer.posting.md", out)

    def test_a_marked_predecessor_is_accepted(self):
        (self.targets / "ashby-staff-engineer.md").write_text(
            "---\ntype: Job Posting\ntitle: \"Old\"\n"
            "superseded_by: ashby-staff-engineer.posting.md\n---\n\nOld.\n",
            encoding="utf-8")
        code, out = self.posting()
        self.assertEqual(code, 0, out)

    def test_a_set_naming_a_key_with_a_flag_is_refused(self):
        code, out = self.posting("--set", "company=Elsewhere")
        self.assertEqual(code, 1)
        self.assertIn("`company` is not an extension key", out)
        self.assertIn("--company", out)

    def test_a_set_naming_requirements_points_at_the_verb_that_writes_them(self):
        code, out = self.posting("--set", "requirements=[]")
        self.assertEqual(code, 1)
        self.assertIn("okf posting requirement add", out)

    def test_an_extension_key_is_written(self):
        code, out = self.posting("--set", "recruiter=Ada")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("posting")["recruiter"], "Ada")

    def test_a_dry_run_writes_nothing(self):
        before = self.log.read_text(encoding="utf-8")
        code, out = self.posting("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("dry run - nothing was written", out)
        self.assertFalse(self.target("posting").exists())
        self.assertEqual(self.log.read_text(encoding="utf-8"), before)

    def test_a_dry_run_still_makes_every_decision(self):
        # A dry run that skipped a derivation would be a dry run of half the
        # command: the refusals are the product, so they have to run.
        code, out = self.posting("--dry-run", company=None)
        self.assertEqual(code, 1)
        self.assertIn("company is required", out)

    def test_json_names_the_files_and_the_stem(self):
        code, out = self.posting("--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(payload["ids"], {"posting": "ashby-staff-engineer"})
        self.assertIn(str(self.target("posting")), payload["changed"])

    def test_the_real_cli_runs_the_verb(self):
        # The one subprocess in this file: proof that okf.py's WRITE_NOUNS and
        # commands.py's parser agree about `posting`, which no in-process call can
        # show.
        proc = run(OKF, "posting", "add", "--bundle", self.root,
                   "--company", "Ashby", "--title", "Staff Engineer",
                   "--slug", "cli-posting", "--body", "An advertisement.")
        self.assertEqual(proc[0], 0, proc[1])
        self.assertTrue((self.targets / "cli-posting.posting.md").exists())


class PostingRequirementAdd(TargetsCase):
    """One entry in a posting's `requirements[]`, and the checks that earn it."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.posting()[0], 0)

    def requirement(self, *extra, **over):
        values = {"posting": "ashby-staff-engineer",
                  "value": "ai-platform-architecture",
                  "kind": "capability", "necessity": "required"}
        values.update(over)
        args = ["posting", "requirement", "add"]
        for key, value in values.items():
            if value is not None:
                args += ["--" + key.replace("_", "-"), str(value)]
        return self.okf(*args, *extra)

    def test_one_requirement_is_appended(self):
        code, out = self.requirement("--label", "own features end to end")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("posting")["requirements"], [{
            "value": "ai-platform-architecture", "kind": "capability",
            "necessity": "required", "label": "own features end to end"}])

    def test_a_second_call_appends_beside_the_first(self):
        self.assertEqual(self.requirement()[0], 0)
        code, out = self.requirement(value="typescript", kind="technology",
                                     necessity="preferred")
        self.assertEqual(code, 0, out)
        self.assertEqual(
            [entry["value"] for entry in
             self.frontmatter("posting")["requirements"]],
            ["ai-platform-architecture", "typescript"])

    def test_several_values_share_one_kind_and_one_necessity(self):
        code, out = self.requirement("--value", "postgres", value="typescript",
                                     kind="technology", necessity="preferred")
        self.assertEqual(code, 0, out)
        entries = self.frontmatter("posting")["requirements"]
        self.assertEqual([entry["value"] for entry in entries],
                         ["typescript", "postgres"])
        for entry in entries:
            self.assertEqual(entry["necessity"], "preferred")

    def test_repeated_values_are_dropped(self):
        code, out = self.requirement("--value", "typescript", value="typescript",
                                     kind="technology", necessity="preferred")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.frontmatter("posting")["requirements"]), 1)

    def test_the_advertisement_is_left_exactly_where_it_was(self):
        self.assertEqual(self.requirement()[0], 0)
        self.assertIn(ADVERTISEMENT, self.text("posting"))

    def test_a_capability_outside_the_vocabulary_is_refused(self):
        code, out = self.requirement(value="totally-made-up")
        self.assertEqual(code, 1)
        self.assertIn("capability 'totally-made-up' is not in", out)
        self.assertIn("--new-capability totally-made-up", out)

    def test_a_new_capability_is_added_to_the_vocabulary_in_the_same_change(self):
        code, out = self.requirement(
            "--new-capability", "event-driven-integration",
            "--theme", "Architecture & design", value=None)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            [entry["value"] for entry in
             self.frontmatter("posting")["requirements"]],
            ["event-driven-integration"])
        vocabulary = (self.root / "framework" / "capability-vocabulary.md"
                      ).read_text(encoding="utf-8")
        self.assertIn("- `event-driven-integration`", vocabulary)

    def test_a_technology_is_not_checked_against_the_capability_vocabulary(self):
        code, out = self.requirement(value="postgres", kind="technology",
                                     necessity="preferred")
        self.assertEqual(code, 0, out)

    def test_new_capability_with_kind_technology_is_refused(self):
        code, out = self.requirement("--new-capability", "postgres",
                                     "--theme", "Architecture & design",
                                     kind="technology", necessity="preferred",
                                     value="postgres")
        self.assertEqual(code, 1)
        self.assertIn("--kind technology with --new-capability", out)

    def test_a_duplicate_value_is_refused(self):
        self.assertEqual(self.requirement()[0], 0)
        code, out = self.requirement(necessity="preferred")
        self.assertEqual(code, 1)
        self.assertIn("already asks for 'ai-platform-architecture'", out)
        self.assertIn("counted twice", out)

    def test_a_requirement_with_no_value_is_refused(self):
        code, out = self.requirement(value=None)
        self.assertEqual(code, 1)
        self.assertIn("no requirement was named", out)
        self.assertIn("--new-capability", out)

    def test_a_missing_necessity_is_refused_and_says_why_it_has_no_default(self):
        # jsk-tailor-analyst.md: the scorer excludes implicit requirements by
        # default, so a requirement invented as `required` makes a good fit look
        # like a bad one - which is why neither value can be a default.
        code, out = self.requirement(necessity=None)
        self.assertEqual(code, 1)
        self.assertIn("--necessity is not optional and has no default", out)
        self.assertIn("implicit", out)
        self.assertEqual(self.frontmatter("posting")["requirements"], [])

    def test_a_label_with_two_values_is_refused(self):
        code, out = self.requirement("--value", "postgres", "--label", "either",
                                     value="typescript", kind="technology",
                                     necessity="preferred")
        self.assertEqual(code, 1)
        self.assertIn("--label with 2 values", out)

    def test_a_posting_that_is_not_there_is_refused(self):
        code, out = self.requirement(posting="no-such-posting")
        self.assertEqual(code, 1)
        self.assertIn("no such posting", out)
        self.assertIn("okf posting add", out)

    def test_an_unknown_necessity_is_refused_by_the_vocabulary(self):
        code, out = self.requirement(necessity="essential")
        self.assertEqual(code, 1)
        self.assertIn("must be one of required, preferred, implicit", out)

    def test_a_dry_run_writes_nothing(self):
        before = self.text("posting")
        code, out = self.requirement("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.text("posting"), before)

    def test_an_extension_key_is_spliced_onto_the_posting(self):
        # There is no `posting set`, so this is the only way an extension key
        # reaches a posting that is already on disk.
        code, out = self.requirement("--set", "recruiter=Ada")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("posting")["recruiter"], "Ada")

    def test_a_posting_with_no_requirements_key_gains_one(self):
        # A hand-written posting, or one from a bundle written before this layer
        # existed: `requirements` has no extent to replace, so it is appended.
        path = self.targets / "handwritten.posting.md"
        path.write_text("---\ntype: Job Posting\ntitle: \"By hand\"\n"
                        "company: Elsewhere\n---\n\nAn advertisement.\n",
                        encoding="utf-8")
        code, out = self.requirement(posting="handwritten")
        self.assertEqual(code, 0, out)
        self.assertEqual(
            [entry["value"] for entry in
             self.frontmatter("posting", "handwritten")["requirements"]],
            ["ai-platform-architecture"])

    def test_the_written_requirements_are_what_the_compiler_reads(self):
        self.assertEqual(self.requirement("--label", "end to end")[0], 0)
        okf_compile = _okf_compile()
        read = okf_compile.posting(str(self.target("posting")))
        self.assertEqual(read["requirements"][0]["necessity"], "required")
        self.assertEqual(read["source"]["raw_text"], ADVERTISEMENT.strip())


class GapsWrite(TargetsCase):
    """`tailoring/targets/<stem>.gaps.md` - and it may not exist alone."""

    def test_an_assessment_is_written_beside_its_posting(self):
        self.assertEqual(self.posting()[0], 0)
        code, out = self.gaps()
        self.assertEqual(code, 0, out)
        meta = self.frontmatter("gaps")
        self.assertEqual(meta["type"], "Gap Assessment")
        self.assertEqual(meta["posting"], "ashby-staff-engineer")
        self.assertEqual(meta["fit"], "partial")
        self.assertIn("# Where this falls short", self.text("gaps"))

    def test_assessed_defaults_to_today(self):
        self.assertEqual(self.posting()[0], 0)
        self.assertEqual(self.gaps()[0], 0)
        common = authoring_module("authoring.common")
        self.assertEqual(str(self.frontmatter("gaps")["assessed"]),
                         common.today())

    def test_an_assessment_with_no_posting_beside_it_is_refused(self):
        # validate_bundle.py:311 makes this a hard error, so writing the file
        # would leave a bundle that fails its own gate.
        code, out = self.gaps()
        self.assertEqual(code, 1)
        self.assertIn("no such posting", out)
        self.assertIn("validate_bundle.py", out)
        self.assertFalse(self.target("gaps").exists())

    def test_overwriting_needs_replace(self):
        self.assertEqual(self.posting()[0], 0)
        self.assertEqual(self.gaps()[0], 0)
        code, out = self.gaps()
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)
        self.assertIn("--replace", out)

    def test_replace_rewrites_the_assessment(self):
        self.assertEqual(self.posting()[0], 0)
        self.assertEqual(self.gaps()[0], 0)
        code, out = self.gaps("--replace", "--fit", "strong",
                              stdin="# Requirements\n\nAll satisfied.\n")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("gaps")["fit"], "strong")
        self.assertIn("All satisfied.", self.text("gaps"))
        self.assertIn("Replaced tailoring/targets/ashby-staff-engineer.gaps.md",
                      self.log.read_text(encoding="utf-8"))

    def test_an_empty_assessment_is_refused(self):
        self.assertEqual(self.posting()[0], 0)
        code, out = self.gaps(stdin="\n\n")
        self.assertEqual(code, 1)
        self.assertIn("--body is empty", out)

    def test_json_names_the_stem_and_an_extension_key_is_written(self):
        self.assertEqual(self.posting()[0], 0)
        code, out = self.gaps("--set", "round=1", "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["ids"],
                         {"gaps": "ashby-staff-engineer"})
        # A string, and quoted, so it reads back as the string it was typed as.
        self.assertEqual(self.frontmatter("gaps")["round"], "1")

    def test_an_extension_key_that_is_a_near_miss_of_a_real_one_is_refused(self):
        self.assertEqual(self.posting()[0], 0)
        code, out = self.gaps("--set", "assessor=analyst")
        self.assertEqual(code, 1)
        self.assertIn("did you mean `assessed`?", out)

    def test_an_unknown_fit_is_refused(self):
        self.assertEqual(self.posting()[0], 0)
        code, out = self.okf("gaps", "write", "--posting", "ashby-staff-engineer",
                             "--fit", "adequate", "--body", "An assessment.")
        self.assertEqual(code, 1)
        self.assertIn("must be one of strong, partial, poor", out)


class ViewCreate(TargetsCase):
    """A `.view.md` is a concept whose frontmatter is a URS view."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.posting()[0], 0)

    def test_a_view_is_written_beside_its_posting(self):
        code, out = self.view()
        self.assertEqual(code, 0, out)
        meta = self.frontmatter("view")
        self.assertEqual(meta["type"], "View")
        self.assertEqual(meta["format_profile"], "ats-maximal")
        self.assertEqual(meta["include"], [])

    def test_the_id_is_materialised_rather_than_left_to_be_derived(self):
        # okf_compile.concepts() hands build_views the filename stem, which for
        # `x.view.md` is `x.view` - so a view with no id compiles to `view_x_view`.
        self.assertEqual(self.view()[0], 0)
        self.assertEqual(self.frontmatter("view")["id"],
                         "view_ashby_staff_engineer")

    def test_target_ref_is_the_sibling_filename_with_no_traversal(self):
        self.assertEqual(self.view()[0], 0)
        target = self.frontmatter("view")["target"]
        self.assertEqual(target["ref"], "ashby-staff-engineer.posting.md")
        self.assertEqual(target["title"], "Staff Software Engineer")
        self.assertNotIn("..", target["ref"])
        # And it resolves from the view's own directory, which is the thing a
        # wrong value would break silently.
        self.assertTrue((self.target("view").parent / target["ref"]).exists())

    def test_the_body_repeats_target_ref_as_a_link_the_gate_can_check(self):
        # Nothing checks a frontmatter path. validate_bundle.py's link checker
        # reads Markdown links, so the same string goes in the body too.
        self.assertEqual(self.view()[0], 0)
        self.assertIn("[ashby-staff-engineer.posting.md]"
                      "(ashby-staff-engineer.posting.md)", self.text("view"))
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        self.assertNotIn("BROKEN LINK", out)

    def test_the_label_is_read_off_the_posting(self):
        self.assertEqual(self.view()[0], 0)
        self.assertEqual(self.frontmatter("view")["label"],
                         "Staff Software Engineer @ Ashby")

    def test_the_provenance_floor_defaults_to_confirmed(self):
        self.assertEqual(self.view()[0], 0)
        self.assertEqual(self.frontmatter("view")["provenance_floor"],
                         "confirmed")

    def test_both_page_budgets_are_written(self):
        code, out = self.view("--pages", "2", "--ats-max-pages", "3")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["budget"],
                         {"pages": 2, "ats_maximal_pages": 3})

    def test_redact_is_a_list_of_dotted_paths(self):
        code, out = self.view("--redact", "person.phone", "--redact",
                              "person.phone", "--redact", "person.address.city")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["redact"],
                         ["person.phone", "person.address.city"])

    def test_a_view_with_no_format_profile_is_refused_with_the_gate_named(self):
        code, out = self.view(profile=None)
        self.assertEqual(code, 1)
        self.assertIn("format_profile is required on a View", out)
        self.assertIn("validate_urs.py", out)

    def test_an_unknown_format_profile_is_refused(self):
        code, out = self.view(profile="ats")
        self.assertEqual(code, 1)
        self.assertIn("presentation, ats-maximal, plaintext, web", out)

    def test_a_view_with_no_posting_beside_it_is_refused(self):
        code, out = self.view(stem="no-such-posting")
        self.assertEqual(code, 1)
        self.assertIn("no such posting", out)
        self.assertIn("target.ref", out)

    def test_a_view_that_is_already_there_is_not_overwritten(self):
        self.assertEqual(self.view()[0], 0)
        code, out = self.view()
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)
        self.assertIn("okf view set", out)

    def test_a_set_lands_under_x(self):
        # validate_urs.py names `x` as where a view's extensions belong and fails
        # any other unknown key, permanently.
        code, out = self.view("--set", "board=ashby")
        self.assertEqual(code, 0, out)
        meta = self.frontmatter("view")
        self.assertEqual(meta["x"], {"board": "ashby"})
        self.assertNotIn("board", set(meta) - {"x"})

    def test_a_set_holding_prose_is_refused(self):
        code, out = self.view(
            "--set", "note=They want somebody who can own the whole feature, "
                     "from the schema to the pixel, without hand-holding.")
        self.assertEqual(code, 1)
        self.assertIn("a view MUST NOT contain content text", out)

    def test_a_long_value_with_no_whitespace_is_not_prose(self):
        code, out = self.view(
            "--set", "advert=https://jobs.example.invalid/ashby/staff-engineer"
                     "-product-engineering")
        self.assertEqual(code, 0, out)

    def test_a_set_naming_a_view_key_with_a_flag_is_refused(self):
        code, out = self.view("--set", "format_profile=web")
        self.assertEqual(code, 1)
        self.assertIn("`format_profile` is not an extension key", out)

    def test_a_set_naming_a_view_key_with_no_flag_is_refused(self):
        for key in sorted(tailoring.VIEW_KEYS_WITHOUT_A_FLAG):
            with self.subTest(key=key):
                code, out = self.view("--set", f"{key}=x")
                self.assertEqual(code, 1, out)
                self.assertIn("is a view's own key, not an extension", out)

    def test_json_names_the_view_id(self):
        code, out = self.view("--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["ids"],
                         {"view": "view_ashby_staff_engineer"})

    def test_a_dry_run_writes_nothing(self):
        code, out = self.view("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.target("view").exists())


class ViewSet(TargetsCase):
    """Amending a view, and what that costs its status."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.posting()[0], 0)
        self.assertEqual(self.view("--pages", "2", "--ats-max-pages", "3",
                                   "--status", "confirmed")[0], 0)

    def amend(self, *extra):
        return self.okf("view", "set", "--view", "ashby-staff-engineer", *extra)

    def test_one_key_is_changed_and_the_rest_are_left_alone(self):
        before = self.text("view")
        code, out = self.amend("--locale", "en-AU")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["locale"], "en-AU")
        for line in before.split("\n"):
            if line.startswith(("format_profile:", "id:", "label:", "target:")):
                self.assertIn(line, self.text("view"))

    def test_the_status_goes_back_to_inferred(self):
        # "Confirmation is then something the agent had to ask for, rather than
        # something it inherits by not touching a line."
        self.assertEqual(self.frontmatter("view")["status"], "confirmed")
        self.assertEqual(self.amend("--locale", "en-AU")[0], 0)
        self.assertEqual(self.frontmatter("view")["status"], "inferred")

    def test_status_confirmed_is_honoured_when_it_is_asked_for(self):
        self.assertEqual(self.amend("--locale", "en-AU",
                                    "--status", "confirmed")[0], 0)
        self.assertEqual(self.frontmatter("view")["status"], "confirmed")

    def test_setting_one_page_budget_keeps_the_other(self):
        # urs/resolve.py falls back to `pages` only when `ats_maximal_pages` is
        # absent, so dropping one would change the length of a document nobody
        # asked about.
        self.assertEqual(self.amend("--pages", "1")[0], 0)
        self.assertEqual(self.frontmatter("view")["budget"],
                         {"pages": 1, "ats_maximal_pages": 3})

    def test_a_set_with_nothing_to_change_is_refused(self):
        code, out = self.amend()
        self.assertEqual(code, 1)
        self.assertIn("nothing to set", out)
        self.assertEqual(self.frontmatter("view")["status"], "confirmed")

    def test_extensions_accumulate_under_x(self):
        self.assertEqual(self.amend("--set", "board=ashby")[0], 0)
        self.assertEqual(self.amend("--set", "recruiter=Ada")[0], 0)
        self.assertEqual(self.frontmatter("view")["x"],
                         {"board": "ashby", "recruiter": "Ada"})

    def test_a_hand_edited_comment_survives(self):
        path = self.target("view")
        text = path.read_text(encoding="utf-8").replace(
            "locale:", "locale:", 1).replace(
            "format_profile: ats-maximal",
            "format_profile: ats-maximal   # chosen for the ATS portal")
        path.write_text(text, encoding="utf-8")
        self.assertEqual(self.amend("--locale", "en-AU")[0], 0)
        self.assertIn("# chosen for the ATS portal", self.text("view"))

    def test_a_view_that_is_not_there_is_refused(self):
        code, out = self.okf("view", "set", "--view", "nope", "--locale", "en-AU")
        self.assertEqual(code, 1)
        self.assertIn("no such view", out)

    def test_the_log_says_what_changed(self):
        self.assertEqual(self.amend("--locale", "en-AU", "--pages", "1")[0], 0)
        self.assertIn("- Set tailoring/targets/ashby-staff-engineer.view.md - "
                      "budget, locale", self.log.read_text(encoding="utf-8"))

    def test_a_dry_run_writes_nothing(self):
        before = self.text("view")
        code, out = self.amend("--locale", "en-AU", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.text("view"), before)


class ViewInclude(TargetsCase):
    """The verb that selects the evidence, and the ids it refuses."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.posting()[0], 0)
        self.assertEqual(self.view("--status", "confirmed")[0], 0)

    def include(self, *extra, ref="eng_acme_health"):
        return self.okf("view", "include", "--view", "ashby-staff-engineer",
                        "--ref", ref, *extra)

    def test_an_entry_is_appended(self):
        code, out = self.include("--order", "1", "--skill", "skill_azure")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["include"],
                         [{"ref": "eng_acme_health", "order": 1,
                           "skills": ["skill_azure"]}])

    def test_the_achievement_order_is_the_order_it_was_passed(self):
        # view-format.md: "Within an include entry, the achievements list is
        # rendered in the order written - that is how a bullet earns the top of a
        # role." Sorting them would silently reorder somebody's evidence.
        code, out = self.include("--achievement", "ach_platform",
                                 "--achievement", "ach_scheduler")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["include"][0]["achievements"],
                         ["ach_platform", "ach_scheduler"])

    def test_a_second_call_for_the_same_ref_amends_that_entry(self):
        self.assertEqual(self.include("--achievement", "ach_platform")[0], 0)
        self.assertEqual(self.include("--order", "2")[0], 0)
        entries = self.frontmatter("view")["include"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["order"], 2)
        # A flag that was not passed leaves its key alone.
        self.assertEqual(entries[0]["achievements"], ["ach_platform"])

    def test_a_second_ref_is_a_second_entry(self):
        self.assertEqual(self.include()[0], 0)
        self.assertEqual(self.include(ref="prj_care_platform")[0], 0)
        self.assertEqual([entry["ref"] for entry in
                          self.frontmatter("view")["include"]],
                         ["eng_acme_health", "prj_care_platform"])

    def test_a_project_id_resolves(self):
        code, out = self.include(ref="prj_rostering")
        self.assertEqual(code, 0, out)

    def test_a_project_that_declares_its_own_id_is_honoured(self):
        path = self.root / "projects" / "rostering.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "type: Project\n", "type: Project\nid: prj_chosen\n"), encoding="utf-8")
        self.assertEqual(self.include(ref="prj_chosen")[0], 0)
        code, out = self.include(ref="prj_rostering")
        self.assertEqual(code, 1)
        self.assertIn("prj_chosen", out)

    def test_a_ref_that_resolves_to_nothing_is_refused_with_a_few_that_do(self):
        code, out = self.include(ref="eng_nope")
        self.assertEqual(code, 1)
        self.assertIn("no engagement or project in the bundle has that id", out)
        self.assertIn("eng_acme_health", out)
        self.assertIn("prj_care_platform", out)
        # Silently falling back to every engagement is the failure this prevents.
        self.assertIn("falls back to selecting every engagement", out)

    def test_an_organisations_own_id_does_not_rename_its_engagement(self):
        # okf_compile.build_engagements writes `eng_{slug(org)}` off the role's
        # `organisation:` and never ident(), so an organisation's id renames the
        # organization it compiles to and nothing else.
        path = self.root / "organisations" / "acme-health.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "type: Organisation\n", "type: Organisation\nid: org_chosen\n"),
            encoding="utf-8")
        self.assertEqual(self.include(ref="eng_acme_health")[0], 0)

    def test_an_achievement_that_resolves_to_nothing_is_refused(self):
        code, out = self.include("--achievement", "ach_invented")
        self.assertEqual(code, 1)
        self.assertIn("no bullet in the bundle has that id", out)
        self.assertIn("ach_platform", out)
        self.assertEqual(self.frontmatter("view")["include"], [])

    def test_a_derived_bullet_id_resolves(self):
        # common.item_ids includes the ids the compile derives from position,
        # because those are the ids a view can name today.
        derived = body.derived_bullet_id("rostering", 1)
        code, out = self.include("--achievement", derived, ref="prj_rostering")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["include"][0]["achievements"],
                         [derived])

    def test_a_skill_that_resolves_to_nothing_is_refused(self):
        code, out = self.include("--skill", "skill_invented")
        self.assertEqual(code, 1)
        self.assertIn("no skill in the bundle has that id", out)
        self.assertIn("skill_azure", out)

    def test_repeated_achievements_are_dropped(self):
        code, out = self.include("--achievement", "ach_platform",
                                 "--achievement", "ach_platform")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["include"][0]["achievements"],
                         ["ach_platform"])

    def test_the_status_goes_back_to_inferred(self):
        self.assertEqual(self.frontmatter("view")["status"], "confirmed")
        self.assertEqual(self.include()[0], 0)
        self.assertEqual(self.frontmatter("view")["status"], "inferred")

    def test_an_order_past_five_is_accepted(self):
        """`order` was kind `rank`, which is 1-5 - so a view selecting eight
        engagements could not number the sixth, and the refusal it met talked
        about flagship evidence, which is `strength`'s subject. It has its own
        kind now; see `StructuredKeysMatchTheirReaders` in
        tests/test_authoring_schema.py. Reported from this module.
        """
        code, out = self.include("--order", "9")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["include"][0]["order"], 9)

    def test_an_order_below_one_is_still_refused(self):
        code, out = self.include("--order", "0")
        self.assertEqual(code, 1)
        self.assertIn("whole number from 1 up", out)

    def test_a_view_that_is_not_there_is_refused(self):
        code, out = self.okf("view", "include", "--view", "nope",
                             "--ref", "eng_acme_health")
        self.assertEqual(code, 1)
        self.assertIn("no such view", out)

    def test_json_names_the_view_and_the_ref(self):
        code, out = self.include("--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["ids"],
                         {"view": "view_ashby_staff_engineer",
                          "include": "eng_acme_health"})

    def test_a_dry_run_writes_nothing(self):
        before = self.text("view")
        code, out = self.include("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.text("view"), before)

    def test_a_view_with_no_include_key_gains_one(self):
        # A view written by hand, or written against jsk-resume-author.md's own
        # example: `include` has no extent to replace, so it is appended.
        path = self.targets / "ashby-staff-engineer.view.md"
        path.write_text("---\ntype: View\ntitle: \"By hand\"\n"
                        "id: view_by_hand\nformat_profile: presentation\n"
                        "---\n\nA view.\n", encoding="utf-8")
        code, out = self.include("--order", "1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["include"],
                         [{"ref": "eng_acme_health", "order": 1}])
        self.assertEqual(json.loads(self.include("--json")[1])["ids"]["view"],
                         "view_by_hand")

    def test_an_include_of_the_wrong_shape_is_refused_rather_than_crashed_on(self):
        # These files are hand-editable by design, so what is already there has to
        # be met with a sentence rather than a TypeError from list().
        path = self.targets / "ashby-staff-engineer.view.md"
        path.write_text("---\ntype: View\nid: view_by_hand\n"
                        "format_profile: presentation\ninclude: acme\n"
                        "---\n\nA view.\n", encoding="utf-8")
        code, out = self.include()
        self.assertEqual(code, 1)
        self.assertIn("`include` is a str, and this command adds to it", out)

    def test_a_treatment_key_already_in_an_entry_is_kept(self):
        # jsk-resume-author.md's example view carries it and nothing reads it, so
        # a `view include` that refused it would refuse every view a real run has
        # produced.
        path = self.targets / "ashby-staff-engineer.view.md"
        path.write_text("---\ntype: View\nid: view_by_hand\n"
                        "format_profile: presentation\ninclude:\n"
                        "  - ref: eng_acme_health\n    treatment: brief\n"
                        "---\n\nA view.\n", encoding="utf-8")
        code, out = self.include("--order", "2")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.frontmatter("view")["include"],
                         [{"ref": "eng_acme_health", "treatment": "brief",
                           "order": 2}])


def _okf_compile():
    """okf_compile as a module, for a test that reads what it produced."""
    from fixtures import load_script
    return load_script(OKF_COMPILE)


class TheWholeRun(TargetsCase):
    """Six verbs, then the three gates and the scorer that read what they wrote.

    The one test in this file that is worth more than the sum of the others: every
    refusal above is a rule about one command, and this is the only assertion that
    the artefacts the six of them produce are a bundle the rest of the toolchain
    accepts. A view is the case that needs it - `validate_urs.py` fails a key it
    does not know, and nothing before the record gate would say so.
    """

    def setUp(self):
        super().setUp()
        self.assertEqual(self.posting()[0], 0)
        self.assertEqual(self.okf(
            "posting", "requirement", "add",
            "--posting", "ashby-staff-engineer",
            "--value", "ai-platform-architecture", "--kind", "capability",
            "--necessity", "required",
            "--label", "own features end to end, from schema to pixel")[0], 0)
        self.assertEqual(self.okf(
            "posting", "requirement", "add",
            "--posting", "ashby-staff-engineer", "--value", "typescript",
            "--kind", "technology", "--necessity", "preferred")[0], 0)
        self.assertEqual(self.gaps()[0], 0)
        self.assertEqual(self.view(
            "--region-profile", "urs:profile:au/1", "--locale", "en-AU",
            "--pages", "2", "--ats-max-pages", "3",
            "--redact", "person.phone",
            "--description", "The Ashby application's selection.")[0], 0)
        self.assertEqual(self.okf(
            "view", "include", "--view", "ashby-staff-engineer",
            "--ref", "eng_acme_health", "--order", "1",
            "--achievement", "ach_platform", "--achievement", "ach_scheduler",
            "--skill", "skill_azure")[0], 0)

    def test_the_bundle_gate_is_green(self):
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("ERRORS 0", out)

    def test_the_record_holds_the_view_and_its_include_entry(self):
        record = Path(self._tmp.name) / "record.json"
        code, out = run(OKF_COMPILE, self.root, "--dump-record", record,
                        "--quiet")
        self.assertEqual(code, 0, out)
        doc = json.loads(record.read_text(encoding="utf-8"))
        views = {view["id"]: view for view in doc["views"]}
        self.assertIn("view_ashby_staff_engineer", views)
        view = views["view_ashby_staff_engineer"]
        self.assertEqual(view["format_profile"], "ats-maximal")
        self.assertEqual(view["provenance_floor"], "confirmed")
        self.assertEqual(view["budget"], {"pages": 2, "ats_maximal_pages": 3})
        self.assertEqual(view["include"], [
            {"ref": "eng_acme_health", "order": 1,
             "achievements": ["ach_platform", "ach_scheduler"],
             "skills": ["skill_azure"]}])
        # The bundle's own bookkeeping is stripped rather than admitted into the
        # URS contract, which is why writing `title` and `status` on a view is safe.
        for key in ("type", "title", "description", "timestamp", "status"):
            self.assertNotIn(key, view)

    def test_the_record_gate_is_green(self):
        # The assertion the view exists for: validate_urs.py fails any view key it
        # does not know, so an unknown-key failure here would be permanent.
        code, out = run(VALIDATE_URS, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("FAIL 0", out)
        self.assertNotIn("unknown field", out)

    def test_the_scorer_runs_against_the_posting_that_was_written(self):
        code, out = run(OKF, "score", self.root,
                        self.target("posting"), "--markdown")
        self.assertEqual(code, 0, out)
        self.assertIn("ai-platform-architecture", out)
        self.assertIn("Care coordination platform", out)

    def test_the_three_files_share_a_stem(self):
        names = sorted(p.name for p in self.targets.iterdir()
                       if p.name != "index.md")
        self.assertEqual(names, ["ashby-staff-engineer.gaps.md",
                                 "ashby-staff-engineer.posting.md",
                                 "ashby-staff-engineer.view.md"])

    def test_every_verb_appended_a_log_row(self):
        rows = [line for line in self.log.read_text(encoding="utf-8").split("\n")
                if line.startswith("- ")]
        self.assertEqual(len(rows), 6, rows)


class Suffixes(unittest.TestCase):
    """The one fact this module and validate_bundle.py must agree about."""

    def test_the_suffixes_are_the_gates_own_companions(self):
        # Read as text rather than imported: validate_bundle.py runs its checks at
        # import and calls sys.exit, so there is no constant to import out of it.
        source = (SCRIPTS / "validate_bundle.py").read_text(encoding="utf-8")
        self.assertIn(
            'TARGET_COMPANIONS = (".posting.md", ".gaps.md", ".view.md")', source)
        self.assertEqual(set(tailoring.SUFFIXES.values()),
                         {".posting.md", ".gaps.md", ".view.md"})

    def test_the_nouns_registered_are_the_ones_common_py_names(self):
        # common.NOUNS is the noun-to-type map the rest of the layer reads, and
        # common.DIRECTORIES puts all three in tailoring/targets. A noun registered
        # here under a different spelling would be a verb nothing else could find.
        common = authoring_module("authoring.common")
        for noun, type_name in (("posting", "Job Posting"),
                                ("gaps", "Gap Assessment"),
                                ("view", "View")):
            with self.subTest(noun=noun):
                self.assertEqual(common.NOUNS[noun], type_name)
                self.assertEqual(common.DIRECTORIES[type_name],
                                 "tailoring/targets")
                self.assertIn(type_name, tailoring.SUFFIXES)

    def test_every_view_key_the_schema_models_is_writable_or_refused(self):
        # No third state: a key with a flag, or a key `--set` refuses by name.
        modelled = {key.name for key in schema.TYPES["View"]}
        self.assertEqual(
            modelled,
            set(tailoring.FLAG_FOR["View"]) | tailoring.VIEW_KEYS_WITHOUT_A_FLAG)


if __name__ == "__main__":                               # pragma: no cover
    unittest.main()
