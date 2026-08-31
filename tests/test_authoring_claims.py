"""The claim verbs: bullet, skill, credential and metric.

The load-bearing class here is `TheIdDefectIsClosed`. Bullet and credential ids
are positional in `okf_compile.py` where a concept wrote none, so inserting an
item above one renumbered every id below it and a view naming `..._1` silently
started rendering a different sentence. It compiles both sides of an insertion
and asserts the recorded id still resolves to the same text - which is the whole
reason these verbs materialise ids before they mutate anything.

Everything else pins one rule each: a refusal and its named cause, an untouched
item keeping its bytes, a dry run writing nothing, and a bundle written entirely
through these verbs passing validate_bundle.py and compiling with what it wrote.
"""
import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from fixtures import (INIT_BUNDLE, OKF_COMPILE, VALIDATE_BUNDLE,
                      authoring_module, load_script, run)

claims = authoring_module("authoring.claims")
body = authoring_module("authoring.body")
common = authoring_module("authoring.common")
concept = authoring_module("authoring.concept")
schema = authoring_module("authoring.schema")
stage = authoring_module("authoring.stage")
okf_compile = load_script(OKF_COMPILE)

try:
    commands = authoring_module("authoring.commands")
except ImportError:                                      # pragma: no cover
    # The CLI imports five verb modules and only some of them exist while the
    # catalogue is being landed. `_replica` below is commands.main()'s own body
    # over a parser holding this module's nouns alone, so these tests exercise
    # the same path either way and switch to the real CLI the moment it imports.
    commands = None


def _replica(argv):
    parser = argparse.ArgumentParser(prog="okf")
    nouns = parser.add_subparsers(dest="noun", metavar="<noun>")
    claims.register(nouns)
    args = parser.parse_args(argv)
    if not getattr(args, "build", None):
        args.parser.print_help()
        return 2
    try:
        payload = stage.commit(args.build(args), dry_run=args.dry_run)
    except (stage.Refused, concept.Unsplicable) as exc:
        print(f"FAIL  {exc}")
        return 1
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    verb = "would write" if payload["dry_run"] else "wrote"
    for path in payload["changed"]:
        print(f"{verb}  {path}")
    for name, value in sorted(payload["ids"].items()):
        print(f"{name}: {value}")
    if payload["dry_run"]:
        print("dry run - nothing was written")
    return 0


def okf(*argv):
    """(exit code, everything printed) for one command, in this interpreter."""
    argv = [str(item) for item in argv]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = commands.main(argv) if commands else _replica(argv)
    return code, out.getvalue()


PROJECT = """---
type: Project
title: "Acme - care coordination platform"
description: "Multi-tenant platform for aged-care providers."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
strength: 5
recency: 2026
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture]
---

# The problem

The legacy scheduler could not express care-plan constraints.
"""

# Two bullets and no ids at all - the shape every bundle written before this
# module existed is in, and the one the materialisation is about.
IMPLICIT = """
# Bullets

- Cut event propagation from 5 minutes to under 1 second.
  status: confirmed
- Ran the delivery team through two platform rewrites.
  status: confirmed
"""

HELD = """---
type: Certification Status
title: "Certifications"
description: "What has been earned."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
---

# Held

- Azure Solutions Architect Expert
  issuer: Microsoft
  issued: 2024-05
- Certified Kubernetes Administrator
  issuer: CNCF
  issued: 2023-01
"""

COMPETENCIES = """---
type: Skill Set
title: "Competencies"
description: "The keyword block."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
---

# Skills

- C# / .NET
  category: language
- Azure
  category: cloud-platform
  id: skill_azure_platform
"""

VIEW = """---
type: View
title: "Acme architect"
format_profile: presentation
provenance_floor: inferred
timestamp: 2026-01-01T00:00:00Z
include:
  - ref: prj_care_platform
    achievements:
      - ach_projects_care_platform_md_1
skills:
  - skill_azure_platform
---

# Why

Because.
"""


class BundleCase(unittest.TestCase):
    """A scaffolded bundle, and the concepts these verbs write into."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)
        self.project = self.root / "projects" / "care-platform.md"
        self.metrics = self.root / "achievements" / "metrics.md"
        self.log = self.root / "log.md"

    # -- fixtures --------------------------------------------------------

    def write_project(self, bullets=""):
        self.project.write_text(PROJECT + bullets, encoding="utf-8")
        return self.project

    def write_held(self, text=HELD):
        path = self.root / "education" / "certifications.md"
        path.write_text(text, encoding="utf-8")
        return path

    def write_skills(self, text=COMPETENCIES):
        path = self.root / "skills" / "competencies.md"
        path.write_text(text, encoding="utf-8")
        return path

    def write_view(self, name="acme.view.md", text=VIEW, directory=None):
        path = (Path(directory) if directory
                else self.root / "tailoring" / "targets") / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def add_metric(self, name="Event propagation latency",
                   value="5 min to under 1 s", *extra):
        return okf("metric", "add", "--bundle", self.root, "--name", name,
                   "--value", value, *extra)

    # -- helpers ---------------------------------------------------------

    def read(self, path):
        return Path(path).read_text(encoding="utf-8")

    def without_timestamp(self, text):
        """A file's lines bar the one line every write is meant to move."""
        return [line for line in text.split("\n")
                if not line.startswith("timestamp:")]

    def items(self, path, kind="bullet"):
        spec = body.KINDS[kind]
        doc = concept.read(str(path))
        block = body.parse(doc.body, spec["heading"], spec["keys"])
        return [] if block is None else block.items

    def ids(self, path, kind="bullet"):
        return [item.id for item in self.items(path, kind)]

    def texts(self, path, kind="bullet"):
        return [item.text for item in self.items(path, kind)]

    def snapshot(self):
        """Every file in the bundle, by path, with its bytes and mtime."""
        out = {}
        for dirpath, _, filenames in os.walk(self.root):
            for name in filenames:
                path = os.path.join(dirpath, name)
                out[path] = (os.stat(path).st_mtime_ns,
                             open(path, "rb").read())
        return out

    def achievements(self):
        """The compiled record's achievements for the one project, by id."""
        record = okf_compile.load(str(self.root))
        return {item["id"]: item["text"]
                for item in record["projects"][0]["achievements"]}

    def validates(self):
        return run(VALIDATE_BUNDLE, self.root)


# --- the defect this module exists to close --------------------------------------

class TheIdDefectIsClosed(BundleCase):
    """A view's id keeps pointing at the sentence it was chosen for.

    `okf_compile.bullets()` numbers an id-less bullet positionally, so before
    this the id `ach_projects_care_platform_md_1` meant "whatever is first" -
    and an insertion above it moved every claim below by one, silently. The
    assertion is on the compiled record either side of an insertion, because
    that is what a view resolves against.
    """

    def test_a_recorded_id_still_resolves_to_the_same_text_after_an_insert(self):
        self.write_project(IMPLICIT)
        before = self.achievements()
        recorded = "ach_projects_care_platform_md_1"
        self.assertIn(recorded, before)

        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "Rebuilt ingestion.",
                        "--at", "1")
        self.assertEqual(code, 0, out)

        after = self.achievements()
        self.assertEqual(after[recorded], before[recorded])
        # And the second one too - the whole block shifted, not only the first.
        second = "ach_projects_care_platform_md_2"
        self.assertEqual(after[second], before[second])

    def test_the_new_bullet_takes_a_content_derived_id_not_a_position(self):
        self.write_project(IMPLICIT)
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "Rebuilt the ingestion pipeline.",
            "--at", "1")
        self.assertEqual(self.ids(self.project)[0],
                         "ach_rebuilt_ingestion_pipeline")

    def test_a_credentials_positional_id_survives_an_insert(self):
        path = self.write_held()
        first = "cred_certifications_1"
        before = {item["id"]: item["name"]
                  for item in okf_compile.load(str(self.root))["credentials"]}
        self.assertIn(first, before)
        code, out = okf("credential", "add", "--bundle", self.root, "--concept",
                        "certifications", "--text", "Terraform Associate",
                        "--issuer", "HashiCorp", "--at", "1")
        self.assertEqual(code, 0, out)
        after = {item["id"]: item["name"]
                 for item in okf_compile.load(str(self.root))["credentials"]}
        self.assertEqual(after[first], before[first])
        self.assertEqual(self.ids(path, "credential")[0],
                         "cred_terraform_associate")

    def test_a_skills_derived_id_is_written_down_too(self):
        # A skill's id is derived from its name rather than its position, so
        # nothing moves - but it is materialised anyway, because renaming a
        # competency would otherwise silently repoint a view that selected it.
        path = self.write_skills()
        okf("skill", "add", "--bundle", self.root, "--text", "Terraform")
        self.assertEqual(self.ids(path, "skill"),
                         ["skill_c_net", "skill_azure_platform",
                          "skill_terraform"])


class Materialisation(BundleCase):
    """Every mutation writes down the ids the compile was deriving, first."""

    def test_add_materialises_the_items_already_there(self):
        self.write_project(IMPLICIT)
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A third.")
        self.assertEqual(self.ids(self.project)[:2],
                         ["ach_projects_care_platform_md_1",
                          "ach_projects_care_platform_md_2"])

    def test_set_materialises_the_items_it_did_not_touch(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "set", "--bundle", self.root, "--project",
                        "care-platform", "--id",
                        "ach_projects_care_platform_md_1", "--text", "Restated.")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(self.project),
                         ["ach_projects_care_platform_md_1",
                          "ach_projects_care_platform_md_2"])

    def test_rm_materialises_before_it_removes(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "rm", "--bundle", self.root, "--project",
                        "care-platform", "--id",
                        "ach_projects_care_platform_md_1")
        self.assertEqual(code, 0, out)
        # The survivor keeps the id it had, rather than becoming _1.
        self.assertEqual(self.ids(self.project),
                         ["ach_projects_care_platform_md_2"])

    def test_mv_materialises_and_the_ids_stay_with_their_sentences(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "mv", "--bundle", self.root, "--project",
                        "care-platform", "--id",
                        "ach_projects_care_platform_md_1", "--to", "2")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(self.project),
                         ["ach_projects_care_platform_md_2",
                          "ach_projects_care_platform_md_1"])
        self.assertEqual(self.texts(self.project)[1],
                         "Cut event propagation from 5 minutes to under 1 "
                         "second.")

    def test_an_item_that_already_has_an_id_keeps_its_own_bytes(self):
        # Its field order is not the canonical one and its indent is four
        # spaces, so a restatement would be visible.
        self.write_project("\n# Bullets\n\n-   Left exactly as written.\n"
                           "    status: confirmed\n    id: ach_kept\n"
                           "- Second, with no id.\n")
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A third.")
        self.assertIn("-   Left exactly as written.\n"
                      "    status: confirmed\n    id: ach_kept\n",
                      self.read(self.project))

    def test_the_log_records_how_many_ids_were_written_down(self):
        self.write_project(IMPLICIT)
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A third.")
        self.assertIn("wrote down 2 implicit ids", self.read(self.log))

    def test_a_second_write_materialises_nothing_because_nothing_is_implicit(self):
        self.write_project(IMPLICIT)
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A third.")
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A fourth.")
        rows = [line for line in self.read(self.log).split("\n")
                if "A fourth" in line]
        self.assertEqual(len(rows), 1)
        self.assertNotIn("implicit id", rows[0])


# --- bullet ----------------------------------------------------------------------

class BulletAdd(BundleCase):
    """The block is created where it is absent, and appended to where it is."""

    def test_the_block_is_created_with_the_first_bullet(self):
        self.write_project()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "Cut latency.")
        self.assertEqual(code, 0, out)
        text = self.read(self.project)
        self.assertIn("# Bullets\n\n- Cut latency.\n  id: ach_cut_latency\n"
                      "  status: inferred\n", text)
        # The prose that was already there is untouched.
        self.assertIn("The legacy scheduler could not express care-plan "
                      "constraints.", text)

    def test_a_bullet_arrives_inferred(self):
        # Anything authored during tailoring is inferred until a person
        # confirms it: `provenance_floor: confirmed` is what stops it rendering.
        self.write_project()
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "Cut latency.")
        self.assertEqual(self.items(self.project)[0].fields["status"],
                         "inferred")

    def test_status_confirmed_is_written_when_it_is_asked_for(self):
        self.write_project()
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "Cut latency.", "--status", "confirmed")
        self.assertEqual(self.items(self.project)[0].fields["status"],
                         "confirmed")

    def test_an_empty_block_is_filled_rather_than_duplicated(self):
        self.write_project("\n# Bullets\n\n# What I decided\n\nProse.\n")
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "The first one.")
        self.assertEqual(code, 0, out)
        text = self.read(self.project)
        self.assertEqual(text.count("# Bullets"), 1)
        self.assertEqual(self.texts(self.project), ["The first one."])
        self.assertIn("# What I decided\n\nProse.\n", text)

    def test_the_frontmatter_keeps_every_key_but_the_timestamp(self):
        self.write_project(IMPLICIT)
        before = concept.read(str(self.project)).meta
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A third.")
        after = concept.read(str(self.project)).meta
        self.assertEqual({k: v for k, v in after.items() if k != "timestamp"},
                         {k: v for k, v in before.items() if k != "timestamp"})

    def test_a_second_bullet_appends(self):
        self.write_project(IMPLICIT)
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A third one.")
        self.assertEqual(self.texts(self.project)[-1], "A third one.")

    def test_at_inserts_at_a_one_based_position(self):
        self.write_project(IMPLICIT)
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "A new first.", "--at", "2")
        self.assertEqual(self.texts(self.project)[1], "A new first.")

    def test_for_records_the_posting_the_sentence_was_written_for(self):
        self.write_project()
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "Cut latency.", "--for",
            "acme-architect")
        self.assertEqual(self.items(self.project)[0].fields["for"],
                         "acme-architect")

    def test_a_newline_in_the_text_is_collapsed(self):
        # A newline inside an item would end it, so body.item() collapses one.
        self.write_project()
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "One sentence.\nAnd another.")
        self.assertEqual(self.texts(self.project),
                         ["One sentence. And another."])

    def test_an_explicit_id_is_used_as_given(self):
        self.write_project()
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "Cut latency.", "--id", "ach_latency")
        self.assertEqual(self.ids(self.project), ["ach_latency"])

    def test_the_metric_a_bullet_names_is_written_to_the_field(self):
        self.write_project()
        self.add_metric()
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "Cut latency.", "--metric",
            "Event propagation latency")
        self.assertEqual(self.items(self.project)[0].fields["metric"],
                         "Event propagation latency")

    def test_the_metric_reaches_the_compiled_record(self):
        self.write_project()
        self.add_metric()
        okf("bullet", "add", "--bundle", self.root, "--project",
            "care-platform", "--text", "Cut latency.", "--metric",
            "Event propagation latency")
        record = okf_compile.load(str(self.root))
        metrics = record["projects"][0]["achievements"][0]["metrics"]
        self.assertEqual(metrics[0]["value"], "5 min to under 1 s")


class BulletAddRefuses(BundleCase):
    """Every refusal exits 1 and names its cause."""

    def test_a_project_that_is_not_there(self):
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "nope", "--text", "x")
        self.assertEqual(code, 1)
        self.assertIn("projects/nope.md: no such concept", out)
        self.assertIn("fix:", out)

    def test_a_role_named_as_a_project(self):
        # A `# Bullets` block in a Role compiles to nothing, silently:
        # okf_compile calls bullets() from one place, inside build_projects.
        (self.root / "roles" / "lead-engineer.md").write_text(
            "---\ntype: Role\ntitle: \"Lead\"\n---\n\nx\n", encoding="utf-8")
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "lead-engineer", "--text", "x")
        self.assertEqual(code, 1)
        self.assertIn("roles/lead-engineer.md is there", out)
        self.assertIn("bullets are projects' alone", out)

    def test_a_concept_of_the_wrong_type(self):
        self.project.write_text("---\ntype: Education\ntitle: \"BSc\"\n---\n\nx\n",
                                encoding="utf-8")
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x")
        self.assertEqual(code, 1)
        self.assertIn("this is a 'Education' concept, not a 'Project'", out)

    def test_a_metric_that_is_not_a_row(self):
        # okf_compile.bullets() raises Problem on this mid-compile, which is on
        # `okf score`'s hot path during a tailoring run.
        self.write_project()
        self.add_metric()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--metric",
                        "Latency, sort of")
        self.assertEqual(code, 1)
        self.assertIn("not a row in achievements/metrics.md", out)
        self.assertIn("'Event propagation latency'", out)
        self.assertFalse(self.items(self.project))

    def test_a_spelling_that_slugs_the_same_is_accepted(self):
        # The check has to slug exactly as metrics_table keys its rows, or a
        # metric this accepts is one the compile does not find - and one it
        # refuses is a number a bullet cannot name.
        self.write_project()
        self.add_metric()
        for spelling in ("Event Propagation Latency", "event propagation latency",
                         "event-propagation-latency"):
            with self.subTest(spelling=spelling):
                code, out = okf("bullet", "add", "--bundle", self.root,
                                "--project", "care-platform", "--text",
                                f"About {spelling}.", "--metric", spelling)
                self.assertEqual(code, 0, out)

    def test_an_id_that_is_already_taken(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--id", "ach_kept")
        self.assertEqual(code, 0, out)
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "y", "--id", "ach_kept")
        self.assertEqual(code, 1)
        self.assertIn("already the id of item", out)

    def test_an_id_the_compile_only_derives_is_still_taken(self):
        # item_ids() includes the ids the compile derives, so a minted or
        # explicit id cannot collide with an implicit one either.
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--id",
                        "ach_projects_care_platform_md_1")
        self.assertEqual(code, 1)
        self.assertIn("already the id of item 1", out)

    def test_a_position_past_the_end_of_the_block(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--at", "9")
        self.assertEqual(code, 1)
        self.assertIn("--at 9: the block holds 2 items", out)

    def test_a_position_in_a_block_that_does_not_exist_yet(self):
        self.write_project()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--at", "2")
        self.assertEqual(code, 1)
        self.assertIn("a new block holds 0 items", out)

    def test_a_position_of_zero(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--at", "0")
        self.assertEqual(code, 1)
        self.assertIn("--at 0", out)

    def test_an_extension_key(self):
        # An item's keys are closed. A line blocks() does not recognise becomes
        # part of the sentence, so --set here would print on a resume.
        self.write_project()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--set",
                        "audience=recruiters")
        self.assertEqual(code, 1)
        self.assertIn("--set is not something an item takes", out)

    def test_a_status_outside_the_vocabulary(self):
        self.write_project()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--status", "probably")
        self.assertEqual(code, 1)
        self.assertIn("probably", out)

    def test_an_id_that_is_not_slug_shaped(self):
        self.write_project()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--id", "not a slug")
        self.assertEqual(code, 1)

    def test_text_that_is_only_whitespace(self):
        # A field-only item compiles to an empty achievement, which renders as
        # a blank line on a resume.
        self.write_project()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "   ")
        self.assertEqual(code, 1)
        self.assertIn("an item needs text", out)


class BulletSet(BundleCase):
    """One item restated, and provenance reset across it."""

    def test_the_text_is_replaced(self):
        self.write_project(IMPLICIT)
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1",
            "--text", "Cut event propagation to under a second.")
        self.assertEqual(self.texts(self.project)[0],
                         "Cut event propagation to under a second.")

    def test_a_changed_bullet_is_re_stamped_inferred(self):
        # A `confirmed` status over text that has been rewritten asserts that a
        # person signed off on a sentence that no longer exists.
        self.write_project(IMPLICIT)
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1",
            "--text", "Restated.")
        self.assertEqual(self.items(self.project)[0].fields["status"],
                         "inferred")

    def test_confirmation_survives_only_when_it_is_asked_for(self):
        self.write_project(IMPLICIT)
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1",
            "--text", "Restated.", "--status", "confirmed")
        self.assertEqual(self.items(self.project)[0].fields["status"],
                         "confirmed")

    def test_the_item_beside_it_keeps_its_bytes(self):
        self.write_project("\n# Bullets\n\n-   Untouched, oddly written.\n"
                           "    id: ach_kept\n    status: confirmed\n"
                           "- Second.\n  id: ach_second\n")
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_second", "--text", "Restated.")
        self.assertIn("-   Untouched, oddly written.\n    id: ach_kept\n"
                      "    status: confirmed\n", self.read(self.project))

    def test_a_field_is_amended_without_touching_the_sentence(self):
        self.write_project(IMPLICIT)
        self.add_metric()
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1",
            "--metric", "Event propagation latency")
        item = self.items(self.project)[0]
        self.assertEqual(item.fields["metric"], "Event propagation latency")
        self.assertEqual(item.text,
                         "Cut event propagation from 5 minutes to under 1 second.")

    def test_an_empty_value_clears_a_field(self):
        self.write_project("\n# Bullets\n\n- One.\n  id: ach_one\n"
                           "  for: acme-architect\n")
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_one", "--for", "")
        self.assertNotIn("for", self.items(self.project)[0].fields)

    def test_the_id_is_the_locator_and_never_changes(self):
        self.write_project(IMPLICIT)
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1",
            "--text", "Restated.")
        self.assertEqual(self.ids(self.project)[0],
                         "ach_projects_care_platform_md_1")

    def test_the_concepts_timestamp_moves(self):
        self.write_project(IMPLICIT)
        okf("bullet", "set", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1",
            "--text", "Restated.")
        self.assertNotIn("timestamp: 2026-01-01T00:00:00Z",
                         self.read(self.project))

    def test_an_id_that_is_not_in_the_block(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "set", "--bundle", self.root, "--project",
                        "care-platform", "--id", "ach_nope", "--text", "x")
        self.assertEqual(code, 1)
        self.assertIn("no bullet with id 'ach_nope'", out)
        self.assertIn("ach_projects_care_platform_md_1", out)

    def test_a_concept_with_no_block_at_all(self):
        self.write_project()
        code, out = okf("bullet", "set", "--bundle", self.root, "--project",
                        "care-platform", "--id", "ach_nope", "--text", "x")
        self.assertEqual(code, 1)
        self.assertIn("no `# Bullets` block", out)

    def test_a_set_that_changes_nothing(self):
        self.write_project(IMPLICIT)
        code, out = okf("bullet", "set", "--bundle", self.root, "--project",
                        "care-platform", "--id",
                        "ach_projects_care_platform_md_1")
        self.assertEqual(code, 1)
        self.assertIn("nothing to set", out)


class BulletRm(BundleCase):
    """Removal, and the refusal that pays for it."""

    def test_the_item_goes_and_its_neighbour_stays(self):
        self.write_project(IMPLICIT)
        okf("bullet", "rm", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1")
        self.assertEqual(self.texts(self.project),
                         ["Ran the delivery team through two platform rewrites."])

    def test_the_last_item_can_go_and_the_heading_stays(self):
        self.write_project("\n# Bullets\n\n- Only one.\n  id: ach_only\n")
        code, out = okf("bullet", "rm", "--bundle", self.root, "--project",
                        "care-platform", "--id", "ach_only")
        self.assertEqual(code, 0, out)
        self.assertIn("# Bullets", self.read(self.project))
        self.assertEqual(self.items(self.project), [])

    def test_a_view_that_still_selects_it(self):
        # urs/resolve.py keeps only the ids a view names and drops the rest, so
        # this fails nowhere - the resume renders one bullet fewer.
        self.write_project(IMPLICIT)
        self.write_view()
        code, out = okf("bullet", "rm", "--bundle", self.root, "--project",
                        "care-platform", "--id",
                        "ach_projects_care_platform_md_1")
        self.assertEqual(code, 1)
        self.assertIn("still selected by tailoring/targets/acme.view.md", out)
        self.assertEqual(len(self.items(self.project)), 2)

    def test_a_frozen_view_in_the_archive_counts_too(self):
        self.write_project(IMPLICIT)
        self.write_view(name="2026-03-04-acme.view.md",
                        directory=self.root / "tailoring" / "applications" / "2026")
        code, out = okf("bullet", "rm", "--bundle", self.root, "--project",
                        "care-platform", "--id",
                        "ach_projects_care_platform_md_1")
        self.assertEqual(code, 1)
        self.assertIn("tailoring/applications/2026/2026-03-04-acme.view.md", out)

    def test_a_view_selecting_a_different_id_does_not_block_it(self):
        self.write_project(IMPLICIT)
        self.write_view()
        code, out = okf("bullet", "rm", "--bundle", self.root, "--project",
                        "care-platform", "--id",
                        "ach_projects_care_platform_md_2")
        self.assertEqual(code, 0, out)

    def test_the_log_records_the_sentence_that_went(self):
        self.write_project(IMPLICIT)
        okf("bullet", "rm", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_1")
        self.assertIn("Removed bullet ach_projects_care_platform_md_1 from "
                      "projects/care-platform.md", self.read(self.log))


class BulletMv(BundleCase):
    """Reordering, which is the one place a position is addressable."""

    def test_an_item_moves_to_a_one_based_position(self):
        self.write_project("\n# Bullets\n\n- One.\n  id: ach_one\n"
                           "- Two.\n  id: ach_two\n- Three.\n  id: ach_three\n")
        okf("bullet", "mv", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_three", "--to", "1")
        self.assertEqual(self.ids(self.project),
                         ["ach_three", "ach_one", "ach_two"])

    def test_a_position_outside_the_list(self):
        self.write_project(IMPLICIT)
        for position in ("0", "3"):
            with self.subTest(position=position):
                code, out = okf("bullet", "mv", "--bundle", self.root,
                                "--project", "care-platform", "--id",
                                "ach_projects_care_platform_md_1", "--to",
                                position)
                self.assertEqual(code, 1)
                self.assertIn("the block holds 2 items", out)

    def test_moving_changes_no_text(self):
        self.write_project(IMPLICIT)
        before = sorted(self.texts(self.project))
        okf("bullet", "mv", "--bundle", self.root, "--project",
            "care-platform", "--id", "ach_projects_care_platform_md_2",
            "--to", "1")
        self.assertEqual(sorted(self.texts(self.project)), before)


# --- skill -----------------------------------------------------------------------

class SkillVerbs(BundleCase):
    """The concept is created where there is none, because nothing else creates it."""

    def test_skill_add_is_a_working_first_command_on_a_fresh_bundle(self):
        # init_bundle.py scaffolds no skills/competencies.md and the catalogue
        # has no verb that writes a Skill Set, so a claim addressed at one would
        # have nowhere to live.
        code, out = okf("skill", "add", "--bundle", self.root, "--text",
                        "C# / .NET", "--category", "language")
        self.assertEqual(code, 0, out)
        path = self.root / "skills" / "competencies.md"
        text = self.read(path)
        self.assertIn("type: Skill Set", text)
        self.assertIn("title: Competencies", text)
        self.assertIn("# Skills\n\n- C# / .NET\n  id: skill_c_net\n"
                      "  category: language\n", text)

    def test_the_new_concept_gets_its_index_row(self):
        okf("skill", "add", "--bundle", self.root, "--text", "Azure")
        self.assertIn("(competencies.md)",
                      self.read(self.root / "skills" / "index.md"))

    def test_the_bundle_still_validates_after_the_first_skill(self):
        code, out = okf("skill", "add", "--bundle", self.root, "--text",
                        "Azure")
        self.assertEqual(code, 0, out)
        code, out = self.validates()
        self.assertEqual(code, 0, out)

    def test_the_new_concept_arrives_inferred(self):
        okf("skill", "add", "--bundle", self.root, "--text", "Azure")
        doc = concept.read(str(self.root / "skills" / "competencies.md"))
        self.assertEqual(doc.meta["status"], "inferred")

    def test_a_title_can_be_given(self):
        okf("skill", "add", "--bundle", self.root, "--concept", "cloud",
            "--concept-title", "Cloud competencies", "--text", "Azure")
        self.assertIn("title: \"Cloud competencies\"",
                      self.read(self.root / "skills" / "cloud.md"))

    def test_aliases_are_a_comma_separated_string(self):
        # build_skills splits on commas itself, so a YAML list here would reach
        # the record as one alias containing brackets.
        okf("skill", "add", "--bundle", self.root, "--text", "C# / .NET",
            "--aliases", "C#, .NET, ASP.NET Core")
        record = okf_compile.load(str(self.root))
        self.assertEqual(record["skills"][0]["aliases"],
                         ["C#", ".NET", "ASP.NET Core"])

    def test_last_used_reaches_the_record_as_a_date(self):
        okf("skill", "add", "--bundle", self.root, "--text", "Azure",
            "--last-used", "2026-06")
        record = okf_compile.load(str(self.root))
        self.assertEqual(record["skills"][0]["last_used"],
                         {"value": "2026-06", "precision": "month"})

    def test_a_second_skill_appends_to_the_block(self):
        okf("skill", "add", "--bundle", self.root, "--text", "Azure")
        okf("skill", "add", "--bundle", self.root, "--text", "Terraform")
        self.assertEqual(
            self.texts(self.root / "skills" / "competencies.md", "skill"),
            ["Azure", "Terraform"])

    def test_a_skill_is_set_rm_and_mv(self):
        path = self.write_skills()
        okf("skill", "set", "--bundle", self.root, "--id",
            "skill_azure_platform", "--category", "cloud")
        self.assertEqual(self.items(path, "skill")[1].fields["category"],
                         "cloud")
        code, out = okf("skill", "mv", "--bundle", self.root, "--id",
                        "skill_azure_platform", "--to", "1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(path, "skill")[0], "skill_azure_platform")
        code, out = okf("skill", "rm", "--bundle", self.root, "--id",
                        "skill_c_net")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(path, "skill"), ["skill_azure_platform"])

    def test_a_skill_set_does_not_re_stamp_the_shared_provenance(self):
        # A skill has no provenance of its own and the concept's status is
        # shared with every sibling, so demoting it would withhold entries
        # nobody touched from any view with a confirmed floor.
        path = self.write_skills()
        okf("skill", "set", "--bundle", self.root, "--id",
            "skill_azure_platform", "--category", "cloud")
        self.assertEqual(concept.read(str(path)).meta["status"], "confirmed")

    def test_a_view_selecting_a_skill_blocks_its_removal(self):
        self.write_skills()
        self.write_view()
        code, out = okf("skill", "rm", "--bundle", self.root, "--id",
                        "skill_azure_platform")
        self.assertEqual(code, 1)
        self.assertIn("still selected by", out)

    def test_a_concept_of_the_wrong_type(self):
        (self.root / "skills" / "competencies.md").write_text(
            "---\ntype: Project\ntitle: \"x\"\n---\n\nx\n", encoding="utf-8")
        code, out = okf("skill", "add", "--bundle", self.root, "--text", "x")
        self.assertEqual(code, 1)
        self.assertIn("not a 'Skill Set'", out)

    def test_a_missing_concept_is_refused_rather_than_created_by_set(self):
        code, out = okf("skill", "set", "--bundle", self.root, "--id",
                        "skill_x", "--category", "y")
        self.assertEqual(code, 1)
        self.assertIn("skills/competencies.md: no such concept", out)


# --- credential ------------------------------------------------------------------

class CredentialVerbs(BundleCase):
    """The `# Held` block: nothing outside it becomes a credential."""

    def test_credential_add_creates_the_concept_where_there_is_none(self):
        code, out = okf("credential", "add", "--bundle", self.root, "--concept",
                        "certifications", "--text",
                        "Azure Solutions Architect Expert", "--issuer",
                        "Microsoft", "--issued", "2024-05", "--status",
                        "active")
        self.assertEqual(code, 0, out)
        text = self.read(self.root / "education" / "certifications.md")
        self.assertIn("type: Certification Status", text)
        self.assertIn("# Held\n\n- Azure Solutions Architect Expert\n", text)
        self.assertIn("issuer: Microsoft", text)
        code, out = self.validates()
        self.assertEqual(code, 0, out)

    def test_it_reaches_the_record_as_a_credential(self):
        okf("credential", "add", "--bundle", self.root, "--concept",
            "certifications", "--text", "Azure Solutions Architect Expert",
            "--issuer", "Microsoft", "--issued", "2024-05")
        record = okf_compile.load(str(self.root))
        held = record["credentials"][0]
        self.assertEqual(held["name"], "Azure Solutions Architect Expert")
        self.assertEqual(held["issuer"], "Microsoft")
        self.assertEqual(held["kind"], "certification")

    def test_the_concept_flag_is_required_because_there_is_nothing_to_guess(self):
        # A bundle holds one Skill Set and any number of Certification Status
        # concepts, so there is no default file for this one.
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                okf("credential", "add", "--bundle", self.root, "--text", "x")

    def test_the_certifications_own_status_is_its_currency(self):
        path = self.write_held()
        okf("credential", "set", "--bundle", self.root, "--concept",
            "certifications", "--id", "cred_certifications_2", "--status",
            "expired")
        self.assertEqual(self.items(path, "credential")[1].fields["status"],
                         "expired")

    def test_a_status_outside_the_credential_vocabulary(self):
        self.write_held()
        code, out = okf("credential", "set", "--bundle", self.root, "--concept",
                        "certifications", "--id", "cred_certifications_1",
                        "--status", "inferred")
        self.assertEqual(code, 1)
        self.assertIn("inferred", out)

    def test_a_credential_is_set_rm_and_mv(self):
        path = self.write_held()
        okf("credential", "set", "--bundle", self.root, "--concept",
            "certifications", "--id", "cred_certifications_1", "--expires",
            "2027-05")
        self.assertEqual(self.items(path, "credential")[0].fields["expires"],
                         "2027-05")
        code, out = okf("credential", "mv", "--bundle", self.root, "--concept",
                        "certifications", "--id", "cred_certifications_2",
                        "--to", "1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(path, "credential")[0],
                         "cred_certifications_2")
        code, out = okf("credential", "rm", "--bundle", self.root, "--concept",
                        "certifications", "--id", "cred_certifications_1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(path, "credential"),
                         ["cred_certifications_2"])

    def test_an_education_concept_is_not_a_certification_status(self):
        # build_credentials reads a `# Held` block out of Certification Status
        # and nothing else, so one written into a degree compiles to nothing.
        (self.root / "education" / "beng.md").write_text(
            "---\ntype: Education\ntitle: \"BEng\"\n---\n\nx\n",
            encoding="utf-8")
        code, out = okf("credential", "add", "--bundle", self.root, "--concept",
                        "beng", "--text", "x")
        self.assertEqual(code, 1)
        self.assertIn("not a 'Certification Status'", out)


# --- metric ----------------------------------------------------------------------

class ContainerProvenance(BundleCase):
    """`--concept-status`: the one thing a claim verb otherwise cannot reach.

    A skill and a held credential have no provenance of their own -
    `build_credentials` takes it from the concept's frontmatter and
    `build_skills` attaches none - so without this flag a credential written by
    command was stuck at whatever the concept said and could never clear a
    view's `provenance_floor: confirmed`. It is a flag rather than a default
    because the marker is shared: demoting it automatically would withhold
    entries nobody touched.
    """

    def test_a_credential_added_confirmed_compiles_as_confirmed(self):
        # The assertion that closes the gap: on a bundle with no education
        # concept at all, one command produces a credential that would survive
        # a view carrying `provenance_floor: confirmed`.
        code, out = okf("credential", "add", "--bundle", self.root, "--concept",
                        "certifications", "--text",
                        "Azure Solutions Architect Expert", "--issuer",
                        "Microsoft", "--issued", "2024-05", "--status",
                        "active", "--concept-status", "confirmed")
        self.assertEqual(code, 0, out)
        record = okf_compile.load(str(self.root))
        held = record["credentials"][0]
        self.assertEqual(held["provenance"]["status"], "confirmed")
        # And the certification's own currency is untouched by it: two `status`
        # words, kept apart by name.
        self.assertEqual(held["status"], "active")
        code, out = self.validates()
        self.assertEqual(code, 0, out)

    def test_without_the_flag_a_new_container_is_inferred(self):
        okf("credential", "add", "--bundle", self.root, "--concept",
            "certifications", "--text", "Azure Solutions Architect Expert")
        record = okf_compile.load(str(self.root))
        self.assertEqual(record["credentials"][0]["provenance"]["status"],
                         "inferred")

    def test_it_is_spliced_into_a_container_that_already_exists(self):
        path = self.write_held()
        code, out = okf("credential", "add", "--bundle", self.root, "--concept",
                        "certifications", "--text", "Terraform Associate",
                        "--concept-status", "needs-verification")
        self.assertEqual(code, 0, out)
        self.assertEqual(concept.read(str(path)).meta["status"],
                         "needs-verification")

    def test_a_set_can_confirm_the_concept(self):
        path = self.write_skills()
        okf("skill", "set", "--bundle", self.root, "--id",
            "skill_azure_platform", "--category", "cloud",
            "--concept-status", "needs-verification")
        self.assertEqual(concept.read(str(path)).meta["status"],
                         "needs-verification")

    def test_it_is_enough_on_its_own_and_the_claim_keeps_its_bytes(self):
        # Amending the concept's provenance has not touched the claim, so the
        # claim is not restated - the same rule materialisation follows.
        self.write_held(
            "---\ntype: Certification Status\ntitle: \"Certifications\"\n"
            "timestamp: 2026-01-01T00:00:00Z\nstatus: inferred\n---\n\n"
            "# Held\n\n-   Azure Solutions Architect Expert\n"
            "    id: cred_azure\n    issuer: Microsoft\n")
        path = self.root / "education" / "certifications.md"
        code, out = okf("credential", "set", "--bundle", self.root, "--concept",
                        "certifications", "--id", "cred_azure",
                        "--concept-status", "confirmed")
        self.assertEqual(code, 0, out)
        text = self.read(path)
        self.assertIn("-   Azure Solutions Architect Expert\n"
                      "    id: cred_azure\n    issuer: Microsoft\n", text)
        self.assertEqual(concept.read(str(path)).meta["status"], "confirmed")

    def test_a_value_outside_the_status_vocabulary(self):
        self.write_held()
        code, out = okf("credential", "set", "--bundle", self.root, "--concept",
                        "certifications", "--id", "cred_certifications_1",
                        "--concept-status", "probably")
        self.assertEqual(code, 1)
        self.assertIn("probably", out)
        for value in schema.VOCABULARIES["status"]:
            self.assertIn(value, out)

    def test_a_bad_value_on_a_new_container_is_refused_before_anything_lands(self):
        code, out = okf("credential", "add", "--bundle", self.root, "--concept",
                        "certifications", "--text", "x", "--concept-status",
                        "probably")
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "education" / "certifications.md").exists())

    def test_a_bullet_does_not_carry_the_flag(self):
        # A Project's own status is `okf project set --status`'s, and a bullet
        # carries its own provenance - so there is nothing here for it to reach.
        self.write_project(IMPLICIT)
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                okf("bullet", "add", "--bundle", self.root, "--project",
                    "care-platform", "--text", "x", "--concept-status",
                    "confirmed")

    def test_the_log_says_what_the_concepts_status_became(self):
        self.write_held()
        okf("credential", "set", "--bundle", self.root, "--concept",
            "certifications", "--id", "cred_certifications_1",
            "--concept-status", "confirmed")
        self.assertIn("concept status: confirmed", self.read(self.log))

    def test_a_created_containers_status_is_in_its_log_row(self):
        okf("skill", "add", "--bundle", self.root, "--text", "Azure",
            "--concept-status", "confirmed")
        self.assertIn("status confirmed", self.read(self.log))


class MetricAdd(BundleCase):
    """A row in achievements/metrics.md - the number recorded once."""

    def test_the_row_is_what_metrics_table_reads(self):
        self.write_project()
        code, out = self.add_metric("Event propagation latency",
                                    "5 min to under 1 s", "--evidence",
                                    "care-platform", "--source",
                                    "Azure dashboard")
        self.assertEqual(code, 0, out)
        rows = okf_compile.metrics_table(str(self.root))
        row = rows["event_propagation_latency"]
        self.assertEqual(row["value"], "5 min to under 1 s")
        self.assertEqual(row["project"], "care-platform")
        self.assertEqual(row["source"], "Azure dashboard")
        self.assertEqual(row["id"], "met_event_propagation_latency")

    def test_the_evidence_is_a_link_the_gate_resolves(self):
        self.write_project()
        self.add_metric("Latency", "1 s", "--evidence", "care-platform")
        self.assertIn("[care-platform](../projects/care-platform.md)",
                      self.read(self.metrics))
        code, out = self.validates()
        self.assertEqual(code, 0, out)

    def test_the_rest_of_the_table_keeps_its_bytes(self):
        # The scaffolded prose above the table, the header and the separator
        # are all somebody's, and a row is the only thing this adds.
        before = self.without_timestamp(self.read(self.metrics))
        self.add_metric("Latency", "1 s")
        after = self.without_timestamp(self.read(self.metrics))
        added = [line for line in after if line not in before]
        self.assertEqual(added, ["| Latency | 1 s |  |  |"])
        self.assertEqual([line for line in after if line != added[0]], before)

    def test_a_second_row_lands_under_the_first(self):
        self.add_metric("Latency", "1 s")
        self.add_metric("Throughput", "20k/s")
        rows = [line for line in self.read(self.metrics).split("\n")
                if line.startswith("| ")]
        self.assertEqual(rows[-2:], ["| Latency | 1 s |  |  |",
                                     "| Throughput | 20k/s |  |  |"])

    def test_a_duplicate_name(self):
        # Two rows slugging the same are one row to metrics_table, which keys
        # them by slug - so the second silently replaces the first.
        self.add_metric("Latency", "1 s")
        code, out = self.add_metric("latency", "2 s")
        self.assertEqual(code, 1)
        self.assertIn("already a row", out)

    def test_evidence_naming_no_project(self):
        code, out = self.add_metric("Latency", "1 s", "--evidence", "nope")
        self.assertEqual(code, 1)
        self.assertIn("no such project", out)
        self.assertIn("BROKEN LINK", out)

    def test_a_pipe_in_a_value(self):
        # metrics_table splits the row on `|` and honours no escape.
        code, out = self.add_metric("Latency", "5 min | 1 s")
        self.assertEqual(code, 1)
        self.assertIn("a `|` ends a cell", out)

    def test_a_newline_in_a_value_is_collapsed(self):
        # A markdown table row is one line and has no escape for a newline, so
        # the only repair available is to not have one.
        code, out = self.add_metric("Latency", "5 min\nto under 1 s")
        self.assertEqual(code, 0, out)
        self.assertIn("| Latency | 5 min to under 1 s |  |  |",
                      self.read(self.metrics))

    def test_an_empty_name_or_value(self):
        for flag, argv in (("--name", ("", "1 s")), ("--value", ("Latency", ""))):
            with self.subTest(flag=flag):
                code, out = self.add_metric(*argv)
                self.assertEqual(code, 1)
                self.assertIn(f"{flag}: empty", out)

    def test_a_source_with_nowhere_to_go(self):
        self.metrics.write_text(
            "---\ntype: Metric Set\ntitle: \"Numbers\"\n---\n\n"
            "| Metric | Value | Evidence |\n|---|---|---|\n", encoding="utf-8")
        code, out = self.add_metric("Latency", "1 s", "--source", "Recall")
        self.assertEqual(code, 1)
        self.assertIn("this table has 3 columns", out)

    def test_a_three_column_table_gets_a_three_cell_row(self):
        self.metrics.write_text(
            "---\ntype: Metric Set\ntitle: \"Numbers\"\n---\n\n"
            "| Metric | Value | Evidence |\n|---|---|---|\n", encoding="utf-8")
        code, out = self.add_metric("Latency", "1 s")
        self.assertEqual(code, 0, out)
        self.assertIn("| Latency | 1 s |  |\n", self.read(self.metrics))

    def test_an_extension_key(self):
        code, out = self.add_metric("Latency", "1 s", "--set", "x=y")
        self.assertEqual(code, 1)
        self.assertIn("--set is not something a metric row takes", out)

    def test_a_file_with_no_header(self):
        self.metrics.write_text(
            "---\ntype: Metric Set\ntitle: \"Numbers\"\n---\n\nNo table.\n",
            encoding="utf-8")
        code, out = self.add_metric("Latency", "1 s")
        self.assertEqual(code, 1)
        self.assertIn("no `| Metric | ... |` header", out)

    def test_a_bundle_with_no_metrics_file(self):
        self.metrics.unlink()
        code, out = self.add_metric("Latency", "1 s")
        self.assertEqual(code, 1)
        self.assertIn("no such metrics file", out)


class MetricSet(BundleCase):
    """One row amended, the rest of the table byte for byte."""

    def setUp(self):
        super().setUp()
        self.write_project()
        self.add_metric("Latency", "5 min to 1 s", "--source", "Recall")
        self.add_metric("Throughput", "20k/s", "--source", "Dashboard")
        self.before = self.read(self.metrics)

    def test_the_value_is_replaced(self):
        code, out = okf("metric", "set", "--bundle", self.root, "--name",
                        "Latency", "--value", "5 min to under 1 s")
        self.assertEqual(code, 0, out)
        rows = okf_compile.metrics_table(str(self.root))
        self.assertEqual(rows["latency"]["value"], "5 min to under 1 s")

    def test_the_row_beside_it_is_untouched(self):
        okf("metric", "set", "--bundle", self.root, "--name", "Latency",
            "--value", "2 s")
        self.assertIn("| Throughput | 20k/s |  | Dashboard |",
                      self.read(self.metrics))

    def test_the_cells_it_was_not_given_are_kept(self):
        okf("metric", "set", "--bundle", self.root, "--name", "Latency",
            "--value", "2 s")
        self.assertIn("| Latency | 2 s |  | Recall |", self.read(self.metrics))

    def test_one_line_changes_and_no_other(self):
        before = self.without_timestamp(self.before)
        okf("metric", "set", "--bundle", self.root, "--name", "Latency",
            "--value", "2 s")
        after = self.without_timestamp(self.read(self.metrics))
        self.assertEqual(len(after), len(before))
        differences = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(differences,
                         [("| Latency | 5 min to 1 s |  | Recall |",
                           "| Latency | 2 s |  | Recall |")])

    def test_evidence_and_source_are_amended(self):
        okf("metric", "set", "--bundle", self.root, "--name", "Latency",
            "--evidence", "care-platform", "--source", "Post-incident review")
        rows = okf_compile.metrics_table(str(self.root))
        self.assertEqual(rows["latency"]["project"], "care-platform")
        self.assertEqual(rows["latency"]["source"], "Post-incident review")

    def test_an_empty_evidence_or_source_empties_the_cell(self):
        okf("metric", "set", "--bundle", self.root, "--name", "Latency",
            "--evidence", "care-platform")
        code, out = okf("metric", "set", "--bundle", self.root, "--name",
                        "Latency", "--evidence", "", "--source", "")
        self.assertEqual(code, 0, out)
        self.assertIn("| Latency | 5 min to 1 s |  |  |",
                      self.read(self.metrics))

    def test_the_name_is_matched_on_the_compilers_own_slug(self):
        code, out = okf("metric", "set", "--bundle", self.root, "--name",
                        "LATENCY", "--value", "2 s")
        self.assertEqual(code, 0, out)

    def test_a_row_that_is_not_there(self):
        code, out = okf("metric", "set", "--bundle", self.root, "--name",
                        "Nope", "--value", "2 s")
        self.assertEqual(code, 1)
        self.assertIn("not a row in achievements/metrics.md", out)
        self.assertIn("'Latency'", out)

    def test_a_set_that_changes_nothing(self):
        code, out = okf("metric", "set", "--bundle", self.root, "--name",
                        "Latency")
        self.assertEqual(code, 1)
        self.assertIn("nothing to set", out)

    def test_the_bundle_still_validates(self):
        okf("metric", "set", "--bundle", self.root, "--name", "Latency",
            "--evidence", "care-platform")
        code, out = self.validates()
        self.assertEqual(code, 0, out)


# --- the flags every verb carries -------------------------------------------------

class DryRun(BundleCase):
    """A dry run decides everything and writes nothing."""

    def setUp(self):
        super().setUp()
        self.write_project(IMPLICIT)
        self.write_held()
        self.write_skills()
        self.add_metric("Latency", "1 s")

    def cases(self):
        return {
            "bullet add": ("bullet", "add", "--project", "care-platform",
                           "--text", "New."),
            "bullet set": ("bullet", "set", "--project", "care-platform",
                           "--id", "ach_projects_care_platform_md_1",
                           "--text", "New."),
            "bullet rm": ("bullet", "rm", "--project", "care-platform",
                          "--id", "ach_projects_care_platform_md_1"),
            "bullet mv": ("bullet", "mv", "--project", "care-platform",
                          "--id", "ach_projects_care_platform_md_1", "--to",
                          "2"),
            "skill add": ("skill", "add", "--text", "Terraform"),
            "skill set": ("skill", "set", "--id", "skill_azure_platform",
                          "--category", "cloud"),
            "skill rm": ("skill", "rm", "--id", "skill_azure_platform"),
            "skill mv": ("skill", "mv", "--id", "skill_azure_platform", "--to",
                         "1"),
            "credential add": ("credential", "add", "--concept",
                               "certifications", "--text", "Terraform Assoc."),
            "credential set": ("credential", "set", "--concept",
                               "certifications", "--id",
                               "cred_certifications_1", "--issuer", "MS"),
            "credential rm": ("credential", "rm", "--concept",
                              "certifications", "--id", "cred_certifications_1"),
            "credential mv": ("credential", "mv", "--concept",
                              "certifications", "--id", "cred_certifications_2",
                              "--to", "1"),
            "credential set --concept-status": (
                "credential", "set", "--concept", "certifications", "--id",
                "cred_certifications_1", "--concept-status", "confirmed"),
            "metric add": ("metric", "add", "--name", "Throughput", "--value",
                           "20k/s"),
            "metric set": ("metric", "set", "--name", "Latency", "--value",
                           "2 s"),
        }

    def test_nothing_on_disk_moves(self):
        for name, argv in self.cases().items():
            with self.subTest(verb=name):
                before = self.snapshot()
                code, out = okf(argv[0], argv[1], "--bundle", self.root,
                                *argv[2:], "--dry-run")
                self.assertEqual(code, 0, out)
                self.assertIn("dry run - nothing was written", out)
                self.assertEqual(before, self.snapshot())

    def test_a_dry_run_still_names_the_files_it_would_write(self):
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "New.", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("would write", out)
        self.assertIn("care-platform.md", out)

    def test_a_dry_run_still_refuses(self):
        # Every decision runs, so a dry run of a refused command refuses.
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text", "x", "--metric", "Nope",
                        "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("not a row in achievements/metrics.md", out)


class JsonPayload(BundleCase):
    """`--json` names every file touched and every id written or minted."""

    def test_a_bullet_add_reports_its_minted_id(self):
        self.write_project()
        code, out = okf("bullet", "add", "--bundle", self.root, "--project",
                        "care-platform", "--text",
                        "Cut event propagation latency.", "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(payload["ids"]["bullet"],
                         "ach_cut_event_propagation")
        self.assertEqual([Path(p).name for p in payload["changed"]],
                         ["care-platform.md", "log.md"])

    def test_a_created_concept_is_reported_as_well_as_the_item(self):
        code, out = okf("skill", "add", "--bundle", self.root, "--text",
                        "Azure", "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(payload["ids"]["concept"], "skills/competencies.md")
        self.assertEqual(payload["ids"]["skill"], "skill_azure")

    def test_a_metric_reports_the_id_the_compile_will_derive(self):
        code, out = okf("metric", "add", "--bundle", self.root, "--name",
                        "Event latency", "--value", "1 s", "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["ids"]["metric"], "met_event_latency")


class EveryVerbLogs(BundleCase):
    """A change with no log row is a change nobody can date."""

    def test_fourteen_verbs_each_append_a_row(self):
        self.write_project(IMPLICIT)
        self.write_held()
        self.write_skills()
        rows = [
            ("metric", "add", "--name", "Latency", "--value", "1 s"),
            ("metric", "set", "--name", "Latency", "--value", "2 s"),
            ("bullet", "add", "--project", "care-platform", "--text", "New."),
            ("bullet", "set", "--project", "care-platform", "--id", "ach_new",
             "--text", "Newer."),
            ("bullet", "mv", "--project", "care-platform", "--id", "ach_new",
             "--to", "1"),
            ("bullet", "rm", "--project", "care-platform", "--id", "ach_new"),
            ("skill", "add", "--text", "Terraform"),
            ("skill", "set", "--id", "skill_terraform", "--category", "iac"),
            ("skill", "mv", "--id", "skill_terraform", "--to", "1"),
            ("skill", "rm", "--id", "skill_terraform"),
            ("credential", "add", "--concept", "certifications", "--text",
             "Terraform Associate"),
            ("credential", "set", "--concept", "certifications", "--id",
             "cred_terraform_associate", "--issuer", "HashiCorp"),
            ("credential", "mv", "--concept", "certifications", "--id",
             "cred_terraform_associate", "--to", "1"),
            ("credential", "rm", "--concept", "certifications", "--id",
             "cred_terraform_associate"),
        ]
        for argv in rows:
            with self.subTest(verb=" ".join(argv[:2])):
                before = self.read(self.log).count("\n- ")
                code, out = okf(argv[0], argv[1], "--bundle", self.root,
                                *argv[2:])
                self.assertEqual(code, 0, out)
                self.assertEqual(self.read(self.log).count("\n- "), before + 1)


class WrittenThroughTheVerbs(BundleCase):
    """A bundle whose claims were all written by these commands holds up.

    The end-to-end assertion: the gate is green, the compile finds every claim,
    and the ids in the record are the ones `--json` reported.
    """

    def test_the_bundle_validates_and_compiles_with_what_was_written(self):
        self.write_project()
        steps = [
            ("metric", "add", "--name", "Event propagation latency", "--value",
             "5 min to under 1 s", "--evidence", "care-platform", "--source",
             "Azure dashboard"),
            ("bullet", "add", "--project", "care-platform", "--text",
             "Cut event propagation from 5 minutes to under 1 second.",
             "--metric", "Event propagation latency", "--status", "confirmed"),
            ("bullet", "add", "--project", "care-platform", "--text",
             "Ran the delivery team through two platform rewrites."),
            ("skill", "add", "--text", "C# / .NET", "--category", "language",
             "--aliases", "C#, .NET"),
            ("credential", "add", "--concept", "certifications", "--text",
             "Azure Solutions Architect Expert", "--issuer", "Microsoft",
             "--issued", "2024-05", "--status", "active"),
        ]
        minted = {}
        for argv in steps:
            code, out = okf(argv[0], argv[1], "--bundle", self.root,
                            *argv[2:], "--json")
            self.assertEqual(code, 0, out)
            minted.update(json.loads(out)["ids"])

        code, out = self.validates()
        self.assertEqual(code, 0, out)

        record = okf_compile.load(str(self.root))
        achievements = record["projects"][0]["achievements"]
        self.assertEqual([item["text"] for item in achievements],
                         ["Cut event propagation from 5 minutes to under 1 "
                          "second.",
                          "Ran the delivery team through two platform "
                          "rewrites."])
        self.assertEqual(achievements[0]["provenance"]["status"], "confirmed")
        self.assertEqual(achievements[1]["provenance"]["status"], "inferred")
        self.assertEqual(achievements[0]["metrics"][0]["label"],
                         "Event propagation latency")
        self.assertEqual([item["id"] for item in record["skills"]],
                         [minted["skill"]])
        self.assertEqual([item["id"] for item in record["credentials"]],
                         [minted["credential"]])
        self.assertIn(minted["bullet"], {item["id"] for item in achievements})

    def test_a_bundle_not_pointed_at_a_bundle(self):
        code, out = okf("bullet", "add", "--bundle", self.root / "log.md",
                        "--project", "x", "--text", "y")
        self.assertEqual(code, 1)
        self.assertIn("not a directory", out)


class AVerbFunctionDecidesAndDoesNotWrite(BundleCase):
    """Each verb takes `args` and returns a changeset, so a dry run is a real one.

    Called directly rather than through the parser, which is the shape
    `commands.main` relies on: it commits, and the function decides. A verb that
    wrote as it went could not be dry-run at all.
    """

    def args(self, **over):
        values = {"bundle": str(self.root), "project": "care-platform",
                  "text": "A new one.", "status": "inferred", "metric": None,
                  "for_": None, "id": None, "at": None, "set": [],
                  "dry_run": False, "json": False}
        values.update(over)
        return argparse.Namespace(**values)

    def test_it_returns_a_changeset_and_touches_nothing(self):
        self.write_project(IMPLICIT)
        before = self.snapshot()
        change = claims.item_add("bullet", self.args())
        self.assertIsInstance(change, stage.Changeset)
        self.assertEqual(before, self.snapshot())

    def test_the_changeset_names_the_concept_before_the_log(self):
        # The concept is the half that cannot be regenerated, so it publishes
        # first - see stage.py on the order.
        self.write_project(IMPLICIT)
        change = claims.item_add("bullet", self.args())
        self.assertEqual([Path(p).name for p in change.ordered()],
                         ["care-platform.md", "log.md"])

    def test_it_records_the_id_it_minted(self):
        # `a` is one of body.NOISE's words, so it is not part of the id: an id
        # is read by a person choosing evidence, and `ach_a_new` says nothing.
        self.write_project(IMPLICIT)
        change = claims.item_add("bullet", self.args())
        self.assertEqual(change.ids, {"bullet": "ach_new_one"})

    def test_a_refusal_carries_a_fix_line(self):
        self.write_project(IMPLICIT)
        with self.assertRaises(stage.Refused) as caught:
            claims.item_add("bullet", self.args(project="nope"))
        self.assertIn("\nfix:  ", str(caught.exception))


class LineEndings(BundleCase):
    """A file keeps its own line convention.

    Rewriting every line ending in somebody's concept in order to add one item
    is the defect `concept.read` carries `newline=""` to avoid, and the row
    splicer here has to leave it alone too.
    """

    def add_bullet(self):
        return okf("bullet", "add", "--bundle", self.root, "--project",
                   "care-platform", "--text", "A new one.")

    def test_an_lf_concept_stays_lf(self):
        self.project.write_bytes((PROJECT + IMPLICIT).encode("utf-8"))
        code, out = self.add_bullet()
        self.assertEqual(code, 0, out)
        self.assertNotIn(b"\r\n", self.project.read_bytes())

    def test_a_crlf_concept_stays_crlf(self):
        self.project.write_bytes(
            (PROJECT + IMPLICIT).replace("\n", "\r\n").encode("utf-8"))
        code, out = self.add_bullet()
        self.assertEqual(code, 0, out)
        raw = self.project.read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))

    def test_a_crlf_metrics_table_stays_crlf(self):
        raw = self.metrics.read_bytes().replace(b"\r\n", b"\n")
        self.metrics.write_bytes(raw.replace(b"\n", b"\r\n"))
        code, out = self.add_metric("Latency", "1 s")
        self.assertEqual(code, 0, out)
        raw = self.metrics.read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))

    def test_an_lf_metrics_table_stays_lf(self):
        self.metrics.write_bytes(
            self.metrics.read_bytes().replace(b"\r\n", b"\n"))
        code, out = self.add_metric("Latency", "1 s")
        self.assertEqual(code, 0, out)
        self.assertNotIn(b"\r\n", self.metrics.read_bytes())


class TheRowSplicer(unittest.TestCase):
    """_rows() reads exactly what okf_compile.metrics_table reads.

    A row this module cannot see is a duplicate it would happily add, and a row
    it sees that the compile does not is a metric a bullet cannot name.
    """

    TABLES = [
        "| Metric | Value | Evidence | Source |\n|---|---|---|---|\n"
        "| Latency | 1 s | [x](../projects/x.md) | Dashboard |\n",
        # No source column.
        "| Metric | Value | Evidence |\n|---|---|---|\n| Latency | 1 s | x |\n",
        # Bold in the value, which metrics_table strips.
        "| Metric | Value | Evidence | Source |\n|---|---|---|---|\n"
        "| Latency | **1 s** | x | y |\n",
        # A two-cell row, which metrics_table does not read at all.
        "| Metric | Value | Evidence | Source |\n|---|---|---|---|\n"
        "| Latency | 1 s |\n",
        # An empty first cell.
        "| Metric | Value | Evidence | Source |\n|---|---|---|---|\n"
        "|  | 1 s | x | y |\n",
        # Prose either side of the table.
        "Before.\n\n| Metric | Value | Evidence | Source |\n|---|---|---|---|\n"
        "| Latency | 1 s | x | y |\n\nAfter.\n",
        # Two rows.
        "| Metric | Value | Evidence | Source |\n|---|---|---|---|\n"
        "| Latency | 1 s | x | y |\n| Throughput | 2/s | x | y |\n",
        # No table at all.
        "Nothing here.\n",
    ]

    def test_the_two_readers_see_the_same_rows(self):
        for table in self.TABLES:
            with self.subTest(table=table[:40]):
                with tempfile.TemporaryDirectory() as tmp:
                    directory = Path(tmp) / "achievements"
                    directory.mkdir()
                    (directory / "metrics.md").write_text(
                        "---\ntype: Metric Set\n---\n\n" + table,
                        encoding="utf-8")
                    theirs = set(okf_compile.metrics_table(tmp))
                mine = set(claims._rows(table))
                self.assertEqual(mine, theirs)

    def test_a_row_round_trips_through_the_renderer(self):
        cells = ["Latency", "5 min to under 1 s",
                 "[x](../projects/x.md)", "Dashboard"]
        line = claims._rendered(cells)
        self.assertEqual(claims._cells(line), cells)


if __name__ == "__main__":                               # pragma: no cover
    unittest.main()
