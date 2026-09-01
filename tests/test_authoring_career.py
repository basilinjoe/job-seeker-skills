"""The career concepts: project, role, org and education - add, set, retire, rm.

Sixteen verbs over one generic implementation, so the tests are shaped to catch the
failure that a table-driven layer actually has: a rule that holds for the type it was
written against and silently does not hold for the other three. Every behavioural
class therefore runs over all four nouns with `subTest` wherever the rule is meant to
be generic, and names the type explicitly where it is not.

Two classes are the load-bearing ones. `WrittenEntirelyThroughTheVerbs` builds a
bundle with nothing but these commands and asserts both gates accept it and the
compiled record holds what was written - the claim the whole write layer rests on.
`SetPreservesEverythingElse` hand-edits a concept and asserts a `set` moves exactly
the bytes it was asked to, which is the promise that makes a CLI safe to point at
somebody's own files.

`ProjectAddBehaviourIsUnchanged` restates a few of the assertions `class ProjectAdd`
in tests/test_authoring.py makes, because `project add` moved out of commands.py into
the generic implementation here. Those 38 tests are the definition of the verb and
they pass; this class exists so that a change to the table shows up in this file too,
and it is not a substitute for them.
"""
import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixtures import (CLI, INIT_BUNDLE, OKF_COMPILE, VALIDATE_BUNDLE,
                      authoring_module, load_script, run)

career = authoring_module("authoring.career")
common = authoring_module("authoring.common")
concept = authoring_module("authoring.concept")
schema = authoring_module("authoring.schema")
stage = authoring_module("authoring.stage")


def build_parser():
    """The parser commands.py builds, with only this module's nouns on it.

    The same three-line path `commands.main` runs - parse, build, commit - against
    the same `register(nouns)` contract, and deliberately not `commands.main`
    itself: that imports five verb modules, so a behavioural test of these sixteen
    verbs driven through it would go red when a sibling module was mid-edit.
    `ThroughTheRealCli` below covers the wiring, in-process and as a subprocess.
    """
    parser = argparse.ArgumentParser(prog="okf")
    nouns = parser.add_subparsers(dest="noun", metavar="<noun>")
    career.register(nouns)
    return parser


def okf(*argv):
    """Run one command end to end. Returns (exit code, everything printed).

    Mirrors commands.main's own reporting, including its exit codes: 0 did it, 1
    refused, 2 was called wrong.
    """
    parser = build_parser()
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
        try:
            args = parser.parse_args([str(item) for item in argv])
        except SystemExit as exc:
            return int(exc.code or 0), printed.getvalue()
        if not getattr(args, "build", None):
            (getattr(args, "parser", None) or parser).print_help()
            return 2, printed.getvalue()
        try:
            payload = stage.commit(args.build(args), dry_run=args.dry_run)
        except (stage.Refused, concept.Unsplicable) as exc:
            print(f"FAIL  {exc}")
            return 1, printed.getvalue()
        if args.json:
            print(json.dumps(payload, indent=2))
            return 0, printed.getvalue()
        verb = "would write" if payload["dry_run"] else "wrote"
        for path in payload["changed"]:
            print(f"{verb}  {path}")
        for path in payload.get("removed", ()):
            print(f"{'would remove' if payload['dry_run'] else 'removed'}  {path}")
        for name, value in sorted(payload["ids"].items()):
            print(f"{name}: {value}")
        if payload["dry_run"]:
            print("dry run - nothing was written")
        return 0, printed.getvalue()


PROJECT_STEM = "acme-care-coordination-platform"
ROLE_STEM = "lead-engineer-acme"
ORG_STEM = "acme-health"
EDUCATION_STEM = "btech-computer-science"

# Which stem each noun's happy path writes, so a generic test can address the
# concept it just created without a branch per type.
STEM_FOR = {"project": PROJECT_STEM, "role": ROLE_STEM, "org": ORG_STEM,
            "education": EDUCATION_STEM}
NOUNS = ("project", "role", "org", "education")


class CareerCase(unittest.TestCase):
    """A scaffolded bundle, and one complete `add` per noun.

    The four adds run in dependency order - an organisation before the role that
    names it, a role before the project done under it - because two of the four
    carry a relational refusal and building the bundle any other way would be
    testing the refusal rather than the verb.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)
        self.log = self.root / "log.md"
        self.vocabulary = self.root / "framework" / "capability-vocabulary.md"

    # --- the bundle's own files -------------------------------------------------

    def concept_path(self, noun, stem=None):
        type_name = common.NOUNS[noun]
        return Path(common.path_of(self.root, type_name,
                                   stem or STEM_FOR[noun]))

    def index_path(self, noun):
        return self.root / common.directory_of(common.NOUNS[noun]) / "index.md"

    def read(self, noun, stem=None):
        return self.concept_path(noun, stem).read_text(encoding="utf-8")

    def populate(self, *terms):
        """List `terms` under the scaffolder's first theme heading.

        init_bundle.py puts its example values inside a fence, so a fresh bundle's
        vocabulary is empty and validate_bundle.py's `if vocab and ...` switches the
        capability check off. A test about an unlisted capability that skips this
        step proves nothing.
        """
        text = self.vocabulary.read_text(encoding="utf-8")
        rows = "".join(f"- `{term}`\n" for term in terms)
        text = text.replace("# Architecture & design\n",
                            "# Architecture & design\n\n" + rows)
        self.vocabulary.write_text(text, encoding="utf-8")

    # --- one complete add per noun ----------------------------------------------

    def flags(self, noun, **over):
        """A complete set of `add` flags for one noun. `None` drops a flag."""
        values = dict(FLAGS[noun])
        values.update(over)
        out = []
        for key, value in values.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    out += [f"--{key.replace('_', '-')}", str(item)]
            else:
                out += [f"--{key.replace('_', '-')}", str(value)]
        return out

    def add(self, noun, *extra, body=None, **over):
        return okf(noun, "add", "--bundle", self.root, *self.flags(noun, **over),
                   *extra, "--body", body or f"# Notes\n\nWhat happened.\n")

    def org(self, **over):
        code, out = self.add("org", **over)
        self.assertEqual(code, 0, out)
        return out

    def role(self, **over):
        self.org()
        code, out = self.add("role", **over)
        self.assertEqual(code, 0, out)
        return out

    def project(self, **over):
        self.role()
        code, out = self.add("project", **over)
        self.assertEqual(code, 0, out)
        return out

    def education(self, **over):
        code, out = self.add("education", **over)
        self.assertEqual(code, 0, out)
        return out

    def whole_bundle(self):
        """One of everything, written through the verbs."""
        self.project()
        self.education()

    def build(self, noun):
        """One concept of `noun`, plus whatever it depends on."""
        {"project": self.project, "role": self.role, "org": self.org,
         "education": self.education}[noun]()


# The flags a complete `add` takes, per noun. Kept as data rather than four
# methods so `flags(noun, key=None)` can drop exactly one of them and ask what the
# command does without it.
FLAGS = {
    "org": {
        "title": "Acme Health",
        "description": "Aged-care provider.",
        "relationship": "employer",
        "industry": ["healthcare", "aged-care"],
        "sector": "private",
        "size": "400 staff",
        "employment": "employment",
        "url": "https://example.invalid",
    },
    "role": {
        "title": "Lead Engineer - Acme",
        "slug": ROLE_STEM,
        "description": "Owned the platform.",
        "organisation": ORG_STEM,
        "start": "2019-04",
        "end": "2021-12",
        "state": "ended",
        "seniority": "team-leadership",
        "change": "hire",
        "functional_title": "Platform Engineer",
    },
    "project": {
        "title": "Acme - care coordination platform",
        "description": "Multi-tenant platform for aged-care providers.",
        "role": ROLE_STEM,
        "strength": "5",
        "recency": "2026",
        "seniority": "architecture-ownership",
        "domain": ["healthcare", "aged-care"],
        "capability": ["ai-platform-architecture"],
        "technology": ["bicep"],
        "headline_metric": "event latency 5 min to under 1 s",
        "url": "https://example.invalid/care",
    },
    "education": {
        "title": "BTech Computer Science",
        "description": "Four-year degree.",
        "level": "bachelor",
        "field": "Computer Science",
        "location": "Kerala, India",
        "institute": "Mahatma Gandhi University",
        "period": "July 2011 - April 2014",
    },
}


class ConceptAdd(CareerCase):
    """`add` writes the concept, its index entry and its log row, per noun."""

    def test_each_noun_writes_its_concept_into_its_own_directory(self):
        for noun in NOUNS:
            with self.subTest(noun=noun):
                case = self.__class__(self._testMethodName)
                case.setUp()
                case.build(noun)
                text = case.read(noun)
                self.assertTrue(
                    text.startswith(f"---\ntype: {common.NOUNS[noun]}\n"), text)
                self.assertIn("status: confirmed", text)
                self.assertTrue(text.endswith("What happened.\n"), text)
                case._tmp.cleanup()

    def test_the_index_and_the_log_are_updated_in_the_same_run(self):
        for noun in NOUNS:
            with self.subTest(noun=noun):
                case = self.__class__(self._testMethodName)
                case.setUp()
                case.build(noun)
                index = case.index_path(noun).read_text(encoding="utf-8")
                self.assertIn(f"]({STEM_FOR[noun]}.md)", index)
                self.assertNotIn("Empty. Add concepts here.", index)
                directory = common.directory_of(common.NOUNS[noun])
                self.assertIn(f"Added {directory}/{STEM_FOR[noun]}.md",
                              case.log.read_text(encoding="utf-8"))
                case._tmp.cleanup()

    def test_status_defaults_to_confirmed_because_a_person_just_said_it(self):
        self.education()
        self.assertIn("status: confirmed", self.read("education"))

    def test_a_project_carries_every_selection_key(self):
        self.project()
        text = self.read("project")
        self.assertIn("strength: 5", text)
        self.assertIn("recency: 2026", text)
        self.assertIn("seniority: architecture-ownership", text)
        self.assertIn("domains: [healthcare, aged-care]", text)
        self.assertIn("capabilities: [ai-platform-architecture]", text)
        self.assertIn("technologies: [bicep]", text)
        self.assertIn("role: lead-engineer-acme", text)

    def test_a_role_carries_its_period_and_its_organisation(self):
        self.role()
        text = self.read("role")
        self.assertIn("organisation: acme-health", text)
        self.assertIn("start: 2019-04", text)
        self.assertIn("end: 2021-12", text)
        self.assertIn("state: ended", text)
        self.assertIn("change: hire", text)
        self.assertIn('functional_title: "Platform Engineer"', text)

    def test_an_organisation_carries_industry_as_a_list(self):
        # build_organizations passes `industry` straight through to URS, where the
        # record writes it as an array - a bare string reached the record as a
        # string where every consumer expects one.
        self.org()
        text = self.read("org")
        self.assertIn("industry: [healthcare, aged-care]", text)
        self.assertIn("relationship: employer", text)
        self.assertIn("employment: employment", text)

    def test_education_keeps_institute_and_period_in_the_body(self):
        # okf_compile.build_education reads both out of the body as a labelled
        # list. A key named in frontmatter that the compile never reads is a value
        # somebody wrote and no resume shows.
        self.education()
        text = self.read("education")
        self.assertNotIn("institute:", text)
        self.assertNotIn("period:", text)
        self.assertIn("- **Institute:** Mahatma Gandhi University\n", text)
        self.assertIn("- **Period:** July 2011 - April 2014\n", text)
        self.assertIn("# Notes", text)
        # The rows come above the prose, so the first thing under the frontmatter
        # is the two facts the compile is looking for.
        self.assertLess(text.index("**Institute:**"), text.index("# Notes"))

    def test_the_labelled_rows_are_what_okf_compile_reads(self):
        self.education()
        body = self.read("education").split("---\n", 2)[2]
        self.assertEqual(career.labelled_rows(body),
                         {"institute": "Mahatma Gandhi University",
                          "period": "July 2011 - April 2014"})

    def test_the_body_arrives_on_stdin(self):
        with mock.patch("sys.stdin",
                                 io.StringIO("# The problem\n\nFrom stdin.\n")):
            code, out = okf("education", "add", "--bundle", self.root,
                            *self.flags("education"))
        self.assertEqual(code, 0, out)
        self.assertTrue(self.read("education").endswith("From stdin.\n"))

    def test_an_explicit_slug_names_the_file(self):
        code, out = self.add("education", "--slug", "mg-university-btech")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / "education" / "mg-university-btech.md")
                        .exists())

    def test_a_slug_is_derived_from_the_title(self):
        self.education(title="Café résumé studies")
        self.assertTrue((self.root / "education" / "cafe-resume-studies.md")
                        .exists())

    def test_an_extension_key_is_written_and_keeps_its_string(self):
        self.education()
        code, out = okf("education", "add", "--bundle", self.root,
                        *self.flags("education", title="Diploma", slug="diploma"),
                        "--set", "awarding_body=MGU", "--set", "cohort=007",
                        "--body", "x\n")
        self.assertEqual(code, 0, out)
        text = self.read("education", "diploma")
        self.assertIn("awarding_body: MGU", text)
        self.assertIn('cohort: "007"', text)

    def test_every_repeatable_flag_dedupes_and_keeps_the_order_given(self):
        self.role()
        code, out = okf("project", "add", "--bundle", self.root,
                        *self.flags("project", domain=None, capability=None,
                                    technology=None),
                        "--domain", "healthcare", "--domain", "aged-care",
                        "--domain", "healthcare",
                        "--capability", "one", "--capability", "one",
                        "--technology", "bicep", "--technology", "bicep",
                        "--body", "x\n")
        self.assertEqual(code, 0, out)
        text = self.read("project")
        self.assertIn("domains: [healthcare, aged-care]", text)
        self.assertIn("capabilities: [one]", text)
        self.assertIn("technologies: [bicep]", text)

    def test_json_reports_the_stem_as_the_nouns_own_id(self):
        for noun in NOUNS:
            with self.subTest(noun=noun):
                case = self.__class__(self._testMethodName)
                case.setUp()
                if noun == "project":
                    case.role()
                elif noun == "role":
                    case.org()
                code, out = case.add(noun, "--json")
                self.assertEqual(code, 0, out)
                payload = json.loads(out)
                self.assertEqual(payload["ids"], {noun: STEM_FOR[noun]})
                self.assertIn(str(case.concept_path(noun)), payload["changed"])
                self.assertFalse(payload["dry_run"])
                case._tmp.cleanup()

    def test_the_concept_publishes_before_its_companions(self):
        self.role()
        code, out = self.add("project", "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["changed"][0],
                         str(self.concept_path("project")))

    def test_dry_run_decides_everything_and_writes_nothing(self):
        self.role()
        before = {path: path.stat().st_mtime_ns
                  for path in self.root.rglob("*.md")}
        code, out = self.add("project", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.concept_path("project").exists())
        self.assertEqual({path: path.stat().st_mtime_ns
                          for path in self.root.rglob("*.md")}, before)
        self.assertIn(str(self.concept_path("project")), out)
        self.assertIn("dry run", out)

    def test_a_new_capability_lands_in_the_vocabulary_in_the_same_changeset(self):
        self.populate("data-sovereignty")
        self.role()
        code, out = self.add("project", "--new-capability", "care-plan-modelling",
                             "--theme", "Architecture & design", capability=None)
        self.assertEqual(code, 0, out)
        vocabulary = self.vocabulary.read_text(encoding="utf-8")
        self.assertIn("- `data-sovereignty`\n- `care-plan-modelling`\n", vocabulary)
        self.assertIn("capabilities: [care-plan-modelling]", self.read("project"))
        self.assertIn(str(self.vocabulary), out)

    def test_a_bundle_scaffolded_as_crlf_gets_a_crlf_concept(self):
        for path in self.root.rglob("*.md"):
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            path.write_bytes(raw.replace(b"\n", b"\r\n"))
        self.education()
        raw = self.concept_path("education").read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))


class AddRefusals(CareerCase):
    """Every row of the refusals table that `add` owns, per noun where it is
    generic. Each asserts exit code 1, the named cause, a `fix:` line, and that
    nothing was written."""

    def assert_refused(self, code, out, *expected):
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("fix:", out)
        for fragment in expected:
            self.assertIn(fragment, out)

    def test_a_concept_that_is_already_there_is_refused(self):
        for noun in NOUNS:
            with self.subTest(noun=noun):
                case = self.__class__(self._testMethodName)
                case.setUp()
                case.build(noun)
                before = case.concept_path(noun).read_bytes()
                code, out = case.add(noun)
                self.assert_refused(code, out, f"okf {noun} set")
                self.assertEqual(case.concept_path(noun).read_bytes(), before)
                case._tmp.cleanup()

    def test_a_project_naming_a_role_that_is_not_there_is_refused(self):
        """The load-bearing refusal. validate_bundle.py does not check this at all;
        okf_compile.py refuses on it, and `okf score` calls okf_compile.load() - so a
        dangling role written today surfaces as a crash mid-tailoring-run."""
        self.role()
        before = self.index_path("project").read_bytes()
        code, out = self.add("project", role="no-such-role")
        self.assert_refused(code, out, os.path.join("roles", "no-such-role.md"),
                            "okf_compile.py refuses on it")
        self.assertFalse(self.concept_path("project").exists())
        self.assertEqual(self.index_path("project").read_bytes(), before)

    def test_a_role_naming_an_organisation_that_is_not_there_is_refused(self):
        # The same class and the same reason - which is why one helper enforces
        # both rather than two copies that can drift.
        code, out = self.add("role", organisation="no-such-org")
        self.assert_refused(code, out,
                            os.path.join("organisations", "no-such-org.md"))
        self.assertFalse(self.concept_path("role").exists())

    def test_a_project_with_no_capability_at_all_is_refused(self):
        self.role()
        code, out = self.add("project", capability=None)
        self.assert_refused(code, out, "--capability", "at least one capability")
        self.assertFalse(self.concept_path("project").exists())

    def test_capabilities_are_required_on_a_project_and_on_nothing_else(self):
        # The one type-specific rule in the table, asserted as type-specific: an
        # Education with no capabilities is an ordinary Education, and the flag is
        # not even offered on the three types that do not take the key.
        self.education()
        self.assertNotIn("capabilities:", self.read("education"))
        for spec in career.SPECS:
            with self.subTest(type_name=spec.name):
                self.assertEqual(spec.capabilities, spec.name == "Project")
                self.assertEqual("capabilities" in {flag.key
                                                    for flag in spec.flags},
                                 spec.name == "Project")

    def test_a_capability_outside_a_populated_vocabulary_is_refused(self):
        self.populate("ai-platform-architecture", "data-sovereignty")
        self.role()
        code, out = self.add("project", capability=["totally-made-up"])
        self.assert_refused(code, out, "totally-made-up",
                            os.path.join("framework", "capability-vocabulary.md"),
                            "--new-capability")
        self.assertFalse(self.concept_path("project").exists())

    def test_an_empty_vocabulary_leaves_capabilities_unchecked(self):
        """A fresh bundle's vocabulary holds nothing, because the scaffolder's
        examples sit inside a fence. validate_bundle.py switches its own check off
        there and this layer must switch off with it - rejecting every value on a
        fresh bundle is the other half of the same bug."""
        self.role()
        code, out = self.add("project", capability=["whatever-they-called-it"])
        self.assertEqual(code, 0, out)
        self.assertIn("capabilities: [whatever-they-called-it]",
                      self.read("project"))

    def test_a_new_capability_needs_a_theme(self):
        self.role()
        code, out = self.add("project", capability=None,
                             new_capability="care-plan-modelling")
        self.assert_refused(code, out, "--theme")
        self.assertFalse(self.concept_path("project").exists())

    def test_a_theme_naming_no_heading_is_refused_with_the_ones_that_do(self):
        self.role()
        code, out = self.add("project", capability=None,
                             new_capability="care-plan-modelling", theme="Data")
        self.assert_refused(code, out, "Architecture & design")
        self.assertFalse(self.concept_path("project").exists())

    def test_a_theme_with_no_new_capability_is_refused(self):
        self.role()
        code, out = self.add("project", theme="Architecture & design")
        self.assert_refused(code, out, "--theme", "--new-capability")

    def test_a_missing_required_flag_is_refused_by_the_parser(self):
        # Required is read off schema.TYPES, so this asserts the join rather than a
        # restated list: `strength` is required in the schema, so argparse demands
        # the flag.
        self.role()
        code, out = self.add("project", strength=None)
        self.assertEqual(code, 2, out)
        self.assertIn("--strength", out)
        self.assertFalse(self.concept_path("project").exists())

    def test_a_required_flag_is_required_for_exactly_the_schemas_keys(self):
        for noun in NOUNS:
            type_name = common.NOUNS[noun]
            wanted = {key.name for key in schema.TYPES[type_name] if key.required}
            table = {flag.key: flag for flag in career.BY_NAME[type_name].flags}
            for key in wanted:
                with self.subTest(noun=noun, key=key):
                    # `capabilities` is written from two flags, so argparse cannot
                    # demand it and common.resolve_capabilities does instead.
                    self.assertIn(key, table)

    def test_a_bad_value_is_refused_with_the_schemas_own_sentence(self):
        self.role()
        code, out = self.add("project", strength="6")
        self.assert_refused(code, out,
                            "`strength` must be a whole number from 1 to 5")
        self.assertFalse(self.concept_path("project").exists())

    def test_a_value_outside_a_closed_vocabulary_is_refused(self):
        code, out = self.add("org", relationship="sort-of")
        self.assert_refused(code, out, "`relationship` must be one of")

    def test_a_stem_that_is_a_path_is_refused(self):
        code, out = self.add("education", slug="../elsewhere")
        self.assert_refused(code, out, "not a path")

    def test_a_title_with_nothing_to_derive_a_stem_from_is_refused(self):
        code, out = self.add("education", title="項目再構築")
        self.assert_refused(code, out, "--slug")

    def test_a_set_naming_a_key_with_its_own_flag_is_refused(self):
        for noun, pair, flag in (("project", "title=Other", "--title"),
                                 ("role", "organisation=x", "--organisation"),
                                 ("org", "industry=x", "--industry"),
                                 ("education", "level=x", "--level")):
            with self.subTest(noun=noun):
                case = self.__class__(self._testMethodName)
                case.setUp()
                if noun in ("project", "role"):
                    case.org()
                if noun == "project":
                    code, out = case.add("role")
                    self.assertEqual(code, 0, out)
                code, out = case.add(noun, "--set", pair)
                self.assert_refused(code, out, flag,
                                    "two sources for one key")
                case._tmp.cleanup()

    def test_no_flag_offers_a_key_this_layer_cannot_write(self):
        """`location` on an Organisation is a URS mapping validate_urs.py checks
        nowhere, so writing one would be the wrong shape with nothing to catch it.
        No flag offers it, and `--set` cannot loosen it either."""
        self.assertNotIn("--location",
                         {flag.flag
                          for flag in career.BY_NAME["Organisation"].flags})
        code, out = self.add("org", "--set", "location=Brisbane")
        self.assert_refused(code, out, "a mapping this layer cannot write")

    def test_a_set_naming_the_key_the_command_stamps_is_told_so(self):
        code, out = self.add("education", "--set", "timestamp=whenever")
        self.assert_refused(code, out, "this command stamps it itself")

    def test_a_set_pair_with_no_equals_is_refused(self):
        code, out = self.add("education", "--set", "justakey")
        self.assert_refused(code, out, "key=value")

    def test_a_near_miss_extension_key_is_refused_with_the_suggestion(self):
        self.role()
        code, out = self.add("project", "--set", "recency_year=2026")
        self.assert_refused(code, out, "did you mean `recency`?")
        self.assertFalse(self.concept_path("project").exists())

    def test_a_bundle_that_is_not_one_is_refused(self):
        code, out = okf("education", "add", "--bundle", self.root / "log.md",
                        *self.flags("education"), "--body", "x\n")
        self.assert_refused(code, out, "--bundle")


class ConceptSet(CareerCase):
    """`set` amends one concept and re-stamps its provenance."""

    def test_one_key_is_changed_and_the_rest_of_the_frontmatter_is_not(self):
        self.project()
        before = self.read("project")
        code, out = okf("project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM, "--strength", "3")
        self.assertEqual(code, 0, out)
        after = self.read("project")
        self.assertIn("strength: 3", after)
        changed = [(old, new) for old, new
                   in zip(before.split("\n"), after.split("\n")) if old != new]
        self.assertEqual(sorted(new for _, new in changed),
                         ["status: inferred", "strength: 3"])

    def test_set_restamps_inferred_because_confirmation_must_be_asked_for(self):
        """Rule 2. Change half a claim and a `confirmed` status now asserts that a
        person signed off on text that no longer exists."""
        for noun in NOUNS:
            with self.subTest(noun=noun):
                case = self.__class__(self._testMethodName)
                case.setUp()
                case.build(noun)
                self.assertIn("status: confirmed", case.read(noun))
                code, out = okf(noun, "set", "--bundle", case.root,
                                "--slug", STEM_FOR[noun],
                                "--description", "Rewritten.")
                self.assertEqual(code, 0, out)
                self.assertIn("status: inferred", case.read(noun))
                case._tmp.cleanup()

    def test_an_explicit_status_is_honoured(self):
        self.education()
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--field", "Computing",
                        "--status", "confirmed")
        self.assertEqual(code, 0, out)
        self.assertIn("status: confirmed", self.read("education"))

    def test_a_list_key_is_written_whole(self):
        # There is no --add-domain: half a list is not a value, and a partial edit
        # of one is not expressible.
        self.project()
        code, out = okf("project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM, "--domain", "government")
        self.assertEqual(code, 0, out)
        self.assertIn("domains: [government]", self.read("project"))

    def test_a_new_capability_can_be_minted_by_a_set(self):
        self.populate("data-sovereignty")
        self.project(capability=["data-sovereignty"])
        code, out = okf("project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM,
                        "--capability", "data-sovereignty",
                        "--new-capability", "care-plan-modelling",
                        "--theme", "Architecture & design")
        self.assertEqual(code, 0, out)
        self.assertIn("capabilities: [data-sovereignty, care-plan-modelling]",
                      self.read("project"))
        self.assertIn("- `care-plan-modelling`",
                      self.vocabulary.read_text(encoding="utf-8"))

    def test_a_set_that_says_nothing_about_capabilities_leaves_them_alone(self):
        self.project()
        code, out = okf("project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM, "--strength", "3")
        self.assertEqual(code, 0, out)
        self.assertIn("capabilities: [ai-platform-architecture]",
                      self.read("project"))

    def test_a_key_is_unset(self):
        self.project()
        code, out = okf("project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM, "--unset", "headline_metric")
        self.assertEqual(code, 0, out)
        self.assertNotIn("headline_metric", self.read("project"))

    def test_a_prose_section_is_replaced(self):
        self.education()
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--section", "Notes",
                        "--body", "Rewritten prose.\n")
        self.assertEqual(code, 0, out)
        text = self.read("education")
        self.assertIn("Rewritten prose.", text)
        self.assertNotIn("What happened.", text)
        # The labelled rows above it are prose nobody named, so they stay.
        self.assertIn("- **Institute:** Mahatma Gandhi University", text)

    def test_a_new_prose_section_is_written(self):
        self.education()
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM,
                        "--new-section", "What I decided",
                        "--body", "Kept the degree.\n")
        self.assertEqual(code, 0, out)
        text = self.read("education")
        self.assertIn("# What I decided\n\nKept the degree.\n", text)
        self.assertIn("What happened.", text)

    def test_a_labelled_row_is_updated_in_place(self):
        self.education()
        before = self.read("education")
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM,
                        "--institute", "Kerala University")
        self.assertEqual(code, 0, out)
        after = self.read("education")
        self.assertIn("- **Institute:** Kerala University\n", after)
        self.assertIn("- **Period:** July 2011 - April 2014\n", after)
        changed = [new for old, new in zip(before.split("\n"), after.split("\n"))
                   if old != new]
        self.assertEqual(sorted(changed),
                         ["- **Institute:** Kerala University", "status: inferred"])

    def test_a_labelled_row_that_is_not_there_is_added(self):
        code, out = self.add("education", institute=None, period=None)
        self.assertEqual(code, 0, out)
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM,
                        "--institute", "Kerala University")
        self.assertEqual(code, 0, out)
        text = self.read("education")
        self.assertIn("- **Institute:** Kerala University\n", text)
        self.assertIn("# Notes", text)

    def test_the_log_row_says_what_changed(self):
        self.project()
        code, out = okf("project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM, "--strength", "3",
                        "--unset", "headline_metric")
        self.assertEqual(code, 0, out)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn(f"Set projects/{PROJECT_STEM}.md - ", log)
        self.assertIn("strength", log)
        self.assertIn("headline_metric deleted", log)

    def test_the_index_row_is_not_rewritten_when_the_title_changes(self):
        # bookkeeping.index_entry leaves an existing row exactly as written,
        # because the row is the author's - it may have been retitled or reordered
        # on purpose. Asserted so nobody reads this as an oversight.
        self.education()
        before = self.index_path("education").read_bytes()
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--title", "BTech CS")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.index_path("education").read_bytes(), before)

    def test_dry_run_writes_nothing(self):
        self.education()
        before = {path: path.stat().st_mtime_ns
                  for path in self.root.rglob("*.md")}
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--field", "Computing",
                        "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual({path: path.stat().st_mtime_ns
                          for path in self.root.rglob("*.md")}, before)

    def test_json_reports_the_stem(self):
        self.education()
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--field", "Computing",
                        "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["ids"], {"education": EDUCATION_STEM})


# A concept somebody has been in with an editor: a comment, an aligned value, a
# blank line inside the block, a title quoted the other way round, and two trailing
# blank lines in the body. Every one of those is a byte a `set` must leave alone.
HAND_EDITED = """---
type: Education
title: 'BTech Computer Science'      # their own quoting, and a comment
description: "Four-year degree."

# the year is from the transcript, not from memory
level: bachelor
field:    Computer Science
location: "Kerala, India"
timestamp: 2026-01-01T00:00:00Z
status: confirmed
---

- **Institute:** Mahatma Gandhi University
- **Period:** July 2011 - April 2014

# Notes

What happened.


"""


class SetPreservesEverythingElse(CareerCase):
    """A write must not reflow somebody's file.

    The design's own test row: write a concept, hand-edit whitespace and comments
    into it, `set` one key, assert every other byte is unchanged. A tool that
    mangles a file once is a tool nobody runs again, and this layer has bound
    people to nothing.
    """

    def setUp(self):
        super().setUp()
        self.path = self.root / "education" / f"{EDUCATION_STEM}.md"
        self.path.write_text(HAND_EDITED, encoding="utf-8", newline="")

    def test_every_byte_but_the_two_that_changed_is_where_it_was(self):
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--field", "Computing")
        self.assertEqual(code, 0, out)
        after = self.path.read_text(encoding="utf-8")
        before_lines = HAND_EDITED.split("\n")
        after_lines = after.split("\n")
        self.assertEqual(len(before_lines), len(after_lines), after)
        differences = [(old, new) for old, new
                       in zip(before_lines, after_lines) if old != new]
        self.assertEqual(differences,
                         [("field:    Computer Science", "field:    Computing"),
                          ("status: confirmed", "status: inferred")])

    def test_a_comment_beside_a_key_that_changed_is_kept(self):
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--title", "BTech CS")
        self.assertEqual(code, 0, out)
        after = self.path.read_text(encoding="utf-8")
        self.assertIn('title: "BTech CS"      # their own quoting, and a comment',
                      after)

    def test_a_crlf_concept_keeps_its_line_endings(self):
        self.path.write_bytes(HAND_EDITED.encode("utf-8").replace(b"\n", b"\r\n"))
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--field", "Computing")
        self.assertEqual(code, 0, out)
        raw = self.path.read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertIn(b"field:    Computing\r\n", raw)

    def test_a_body_edit_leaves_the_frontmatter_untouched(self):
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--section", "Notes",
                        "--body", "Rewritten.\n", "--status", "confirmed")
        self.assertEqual(code, 0, out)
        after = self.path.read_text(encoding="utf-8")
        self.assertEqual(after.split("---\n")[1], HAND_EDITED.split("---\n")[1])

    def test_a_key_this_layer_does_not_model_does_not_block_an_amendment(self):
        """Measured, and the reason `set` reports only new problems.

        A real bundle carries hand-written keys - `organization` on a role written
        before the spelling settled is the one that occurs. Checking the merged
        result flatly would make every future `set` on that file refuse over a line
        the command did not touch, and a person cannot fix somebody else's key by
        way of amending their own.
        """
        text = HAND_EDITED.replace("level: bachelor",
                                  "level: bachelor\nawarding_body: MGU")
        self.path.write_text(text, encoding="utf-8", newline="")
        self.assertTrue(schema.check("Education", {"awarding_body": "MGU"}))
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM, "--field", "Computing")
        self.assertEqual(code, 0, out)
        self.assertIn("awarding_body: MGU",
                      self.path.read_text(encoding="utf-8"))


class SetRefusals(CareerCase):
    """`set`'s own refusals. Each names its cause and ends in a `fix:` line."""

    def assert_refused(self, code, out, *expected):
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("fix:", out)
        for fragment in expected:
            self.assertIn(fragment, out)

    def amend(self, *extra, noun="education", stem=EDUCATION_STEM):
        return okf(noun, "set", "--bundle", self.root, "--slug", stem, *extra)

    def test_a_concept_that_is_not_there_is_refused_by_its_path(self):
        for noun in NOUNS:
            with self.subTest(noun=noun):
                code, out = okf(noun, "set", "--bundle", self.root,
                                "--slug", "no-such-thing", "--title", "X")
                self.assert_refused(
                    code, out,
                    os.path.join(common.directory_of(common.NOUNS[noun]),
                                 "no-such-thing.md"))

    def test_a_set_that_names_no_change_is_refused(self):
        self.education()
        code, out = self.amend()
        self.assert_refused(code, out, "was given nothing to change")
        self.assertIn("status: confirmed", self.read("education"))

    def test_a_section_with_no_body_is_refused(self):
        self.education()
        code, out = self.amend("--section", "Notes")
        self.assert_refused(code, out, "--body", "the floor")

    def test_a_body_with_no_section_is_refused(self):
        self.education()
        code, out = self.amend("--body", "Rewritten.\n")
        self.assert_refused(code, out, "--section",
                            "not a whole-body replacement")

    def test_a_section_and_a_new_section_together_are_refused(self):
        self.education()
        code, out = self.amend("--section", "Notes", "--new-section", "Other",
                               "--body", "x\n")
        self.assert_refused(code, out, "--section and --new-section")

    def test_a_section_that_is_not_there_is_refused_with_the_ones_that_are(self):
        self.education()
        code, out = self.amend("--section", "What I decided", "--body", "x\n")
        self.assertEqual(code, 1, out)
        self.assertIn("'Notes'", out)
        self.assertIn("--new-section", out)

    def test_a_new_section_that_is_already_there_is_refused(self):
        self.education()
        code, out = self.amend("--new-section", "Notes", "--body", "x\n")
        self.assertEqual(code, 1, out)
        self.assertIn("already there", out)

    def test_unsetting_a_required_key_is_refused_with_the_schemas_reason(self):
        self.education()
        code, out = self.amend("--unset", "title")
        self.assert_refused(code, out, "required on an Education",
                            "renders on a resume as its own stem")
        self.assertIn('title: "BTech Computer Science"', self.read("education"))

    def test_unsetting_a_key_that_is_not_there_is_refused(self):
        self.education()
        code, out = self.amend("--unset", "resource")
        self.assert_refused(code, out, "nothing to")

    def test_unsetting_and_setting_one_key_at_once_is_refused(self):
        self.education()
        code, out = self.amend("--unset", "field", "--field", "Computing")
        self.assert_refused(code, out, "--unset field")

    def test_a_bad_value_is_refused(self):
        self.project()
        code, out = self.amend("--strength", "9", noun="project",
                               stem=PROJECT_STEM)
        self.assert_refused(code, out, "`strength` must be a whole number")

    def test_a_key_written_twice_is_refused_rather_than_reflowed(self):
        """write-commands.md's promise: where a key cannot be spliced
        unambiguously the command names the file and the line rather than
        rewriting somebody's block. Which of the two is right is not something a
        command can know."""
        self.education()
        path = self.concept_path("education")
        path.write_text(path.read_text(encoding="utf-8")
                        .replace("level: bachelor",
                                 "level: bachelor\nlevel: masters"),
                        encoding="utf-8")
        before = path.read_bytes()
        code, out = self.amend("--level", "diploma")
        self.assertEqual(code, 1, out)
        self.assertIn("`level` appears twice", out)
        self.assertIn("fix:", out)
        self.assertEqual(path.read_bytes(), before)

    def test_a_dangling_relation_is_refused_on_a_set_too(self):
        self.project()
        code, out = self.amend("--role", "no-such-role", noun="project",
                               stem=PROJECT_STEM)
        self.assert_refused(code, out, os.path.join("roles", "no-such-role.md"))
        self.assertIn(f"role: {ROLE_STEM}", self.read("project"))


class Retire(CareerCase):
    """`retire` stops a claim and keeps the file, which is the whole difference."""

    def retire(self, noun, *extra, stem=None):
        return okf(noun, "retire", "--bundle", self.root,
                   "--slug", stem or STEM_FOR[noun],
                   "--reason", "superseded by the rebuild", *extra)

    def test_every_noun_can_be_retired_and_keeps_its_file(self):
        for noun in NOUNS:
            with self.subTest(noun=noun):
                case = self.__class__(self._testMethodName)
                case.setUp()
                case.build(noun)
                code, out = case.retire(noun)
                self.assertEqual(code, 0, out)
                text = case.read(noun)
                self.assertIn(f"retired: {common.today()}", text)
                self.assertIn('retired_reason: "superseded by the rebuild"', text)
                self.assertTrue(case.concept_path(noun).exists())
                # The index row stays, so every link to it keeps resolving.
                self.assertIn(f"]({STEM_FOR[noun]}.md)",
                              case.index_path(noun).read_text(encoding="utf-8"))
                case._tmp.cleanup()

    def test_a_retired_organisation_can_still_be_amended(self):
        """A retirement must not leave a concept the next `set` refuses to touch.

        `schema.TYPES["Organisation"]` used to omit `retired`/`retired_reason` where
        the other three types had them, so the two keys were declared as extensions
        for this type alone. The schema now carries them - see
        `TheFourCareerTypesAgreeWithEachOther` in tests/test_authoring_schema.py -
        and this keeps asserting the behaviour that gap was found through, which is
        the half that matters and the half that outlives the workaround.
        """
        self.org()
        code, out = self.retire("org")
        self.assertEqual(code, 0, out)
        code, out = okf("org", "set", "--bundle", self.root, "--slug", ORG_STEM,
                        "--sector", "public")
        self.assertEqual(code, 0, out)
        self.assertIn("sector: public", self.read("org"))

    def test_the_status_is_not_restamped(self):
        # `status` says how well the bundle knows a claim and `retired` says
        # whether the claim is still made. A retirement changes the second and
        # nothing in the prose has moved.
        self.education()
        code, out = self.retire("education")
        self.assertEqual(code, 0, out)
        self.assertIn("status: confirmed", self.read("education"))

    def test_an_explicit_date_is_written(self):
        self.education()
        code, out = self.retire("education", "--date", "2024-06-01")
        self.assertEqual(code, 0, out)
        self.assertIn("retired: 2024-06-01", self.read("education"))

    def test_a_bad_date_is_refused(self):
        self.education()
        code, out = self.retire("education", "--date", "last summer")
        self.assertEqual(code, 1, out)
        self.assertIn("`retired` must be a date", out)

    def test_retiring_twice_is_refused_and_says_when(self):
        self.education()
        code, out = self.retire("education", "--date", "2024-06-01")
        self.assertEqual(code, 0, out)
        code, out = self.retire("education")
        self.assertEqual(code, 1, out)
        self.assertIn("already retired on 2024-06-01", out)
        self.assertIn("fix:", out)

    def test_a_concept_that_is_not_there_is_refused_by_its_path(self):
        code, out = self.retire("education", stem="no-such-thing")
        self.assertEqual(code, 1, out)
        self.assertIn(os.path.join("education", "no-such-thing.md"), out)

    def test_the_reason_is_required(self):
        self.education()
        code, out = okf("education", "retire", "--bundle", self.root,
                        "--slug", EDUCATION_STEM)
        self.assertEqual(code, 2, out)
        self.assertIn("--reason", out)

    def test_the_retirement_is_logged(self):
        self.education()
        code, out = self.retire("education")
        self.assertEqual(code, 0, out)
        self.assertIn(f"Retired education/{EDUCATION_STEM}.md - superseded",
                      self.log.read_text(encoding="utf-8"))

    def test_dry_run_writes_nothing(self):
        self.education()
        before = self.read("education")
        code, out = self.retire("education", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("education"), before)


class Remove(CareerCase):
    """`rm` deletes, and refuses while anything still references the concept.

    The load-bearing refusal of the verb. Without it a delete leaves a dangling
    reference the compile refuses on - and `okf score` compiles, so it surfaces as
    a crash mid-tailoring rather than as a red line at ship time.
    """

    def remove(self, noun, *extra, stem=None):
        return okf(noun, "rm", "--bundle", self.root,
                   "--slug", stem or STEM_FOR[noun], *extra)

    def test_a_concept_nothing_references_is_deleted_with_its_index_row(self):
        self.education()
        code, out = self.remove("education")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.concept_path("education").exists())
        self.assertNotIn(f"({EDUCATION_STEM}.md)",
                         self.index_path("education").read_text(encoding="utf-8"))
        self.assertIn(f"Removed education/{EDUCATION_STEM}.md - BTech",
                      self.log.read_text(encoding="utf-8"))

    def test_json_names_the_file_that_went(self):
        self.education()
        code, out = self.remove("education", "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(payload["removed"],
                         [str(self.concept_path("education"))])
        self.assertEqual(payload["ids"], {"education": EDUCATION_STEM})

    def test_the_concept_is_removed_after_every_write_has_landed(self):
        # stage.py's contract: a `rm` whose index rewrite fails must leave the
        # concept on disk, so the removal is published last.
        self.education()
        code, out = self.remove("education", "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertTrue(payload["changed"])
        self.assertEqual(payload["removed"],
                         [str(self.concept_path("education"))])

    def test_dry_run_leaves_the_file_on_disk(self):
        self.education()
        code, out = self.remove("education", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.concept_path("education").exists())
        self.assertIn("would remove", out)

    def test_a_role_a_project_still_names_is_refused(self):
        self.project()
        code, out = self.remove("role")
        self.assertEqual(code, 1, out)
        self.assertIn(f"projects/{PROJECT_STEM}.md: role: {ROLE_STEM}", out)
        self.assertIn(f"okf role retire --slug {ROLE_STEM}", out)
        self.assertIn("Git is this command's only undo", out)
        self.assertTrue(self.concept_path("role").exists())

    def test_an_organisation_a_role_still_names_is_refused(self):
        self.role()
        code, out = self.remove("org")
        self.assertEqual(code, 1, out)
        self.assertIn(f"roles/{ROLE_STEM}.md: organisation: {ORG_STEM}", out)
        self.assertTrue(self.concept_path("org").exists())

    def test_the_older_spelling_of_organisation_is_seen_too(self):
        # okf_compile.py reads `organization` for bundles written before the
        # spelling settled. A reference this layer could not see is a link `rm`
        # would break.
        self.role()
        path = self.concept_path("role")
        path.write_text(path.read_text(encoding="utf-8")
                        .replace("organisation:", "organization:"),
                        encoding="utf-8")
        code, out = self.remove("org")
        self.assertEqual(code, 1, out)
        self.assertIn("organization: " + ORG_STEM, out)

    def test_a_markdown_link_from_anywhere_in_the_bundle_is_refused(self):
        """mode-braindump.md instructs a link from the role concept to the project,
        so this is the ordinary case rather than an exotic one. Deleting the target
        would make validate_bundle.py report a BROKEN LINK."""
        self.project()
        role = self.concept_path("role")
        role.write_text(role.read_text(encoding="utf-8")
                        + f"\n- [The platform](../projects/{PROJECT_STEM}.md)\n",
                        encoding="utf-8")
        code, out = self.remove("project")
        self.assertEqual(code, 1, out)
        self.assertIn(f"roles/{ROLE_STEM}.md: a markdown link", out)
        self.assertTrue(self.concept_path("project").exists())

    def test_a_link_inside_a_fence_or_backticks_is_not_a_reference(self):
        """validate_bundle.py strips fenced blocks and inline code before looking
        for a broken link, so a delete that refused over one would refuse over a
        reference nothing would ever report."""
        self.project()
        role = self.concept_path("role")
        role.write_text(
            role.read_text(encoding="utf-8")
            + f"\n```\n- [example](../projects/{PROJECT_STEM}.md)\n```\n"
            + f"\nSee `[x](../projects/{PROJECT_STEM}.md)` for the shape.\n",
            encoding="utf-8")
        code, out = self.remove("project")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.concept_path("project").exists())

    def test_the_concepts_own_index_row_does_not_block_its_removal(self):
        # The row is dropped in this same changeset, so counting it would make
        # every `rm` refuse itself.
        self.education()
        self.assertIn(f"({EDUCATION_STEM}.md)",
                      self.index_path("education").read_text(encoding="utf-8"))
        code, out = self.remove("education")
        self.assertEqual(code, 0, out)

    def test_a_view_naming_the_compiled_id_is_refused(self):
        self.project()
        view = self.root / "tailoring" / "targets" / "ashby-staff.view.md"
        view.write_text(
            "---\ntype: View\nid: view_ashby\nformat_profile: ats-maximal\n"
            "include:\n  - ref: prj_acme_care_coordination_platform\n"
            "    order: 1\n---\n\n# Notes\n\nSelected.\n", encoding="utf-8")
        code, out = self.remove("project")
        self.assertEqual(code, 1, out)
        self.assertIn("ashby-staff.view.md: include[1].ref: "
                      "prj_acme_care_coordination_platform", out)

    def test_a_view_naming_an_engagement_blocks_its_organisation(self):
        # An engagement's id is derived from the organisation's stem, so a view
        # that selected an employer names `eng_<stem>` and never the filename.
        self.org()
        view = self.root / "tailoring" / "targets" / "ashby-staff.view.md"
        view.write_text(
            "---\ntype: View\nid: view_ashby\nformat_profile: ats-maximal\n"
            "include:\n  - ref: eng_acme_health\n    order: 1\n---\n\n"
            "# Notes\n\nSelected.\n", encoding="utf-8")
        code, out = self.remove("org")
        self.assertEqual(code, 1, out)
        self.assertIn("include[1].ref: eng_acme_health", out)

    def test_a_declared_id_is_the_one_a_view_names(self):
        # okf_compile.ident() prefers a declared `id:`, so a bundle that published
        # one is named by it rather than by the derived form.
        self.education()
        path = self.concept_path("education")
        path.write_text(path.read_text(encoding="utf-8")
                        .replace("status: confirmed",
                                 "status: confirmed\nid: edu_published"),
                        encoding="utf-8")
        view = self.root / "tailoring" / "targets" / "ashby-staff.view.md"
        view.write_text(
            "---\ntype: View\nid: view_ashby\nformat_profile: ats-maximal\n"
            "include:\n  - ref: edu_published\n    order: 1\n---\n\n"
            "# Notes\n\nSelected.\n", encoding="utf-8")
        code, out = self.remove("education")
        self.assertEqual(code, 1, out)
        self.assertIn("include[1].ref: edu_published", out)

    def test_an_archived_application_naming_the_organisation_is_refused(self):
        """`company_ref: "../../../organisations/<company>.md"` is a relative path
        in frontmatter, not a markdown link, so nothing but a resolve of that key
        can see it."""
        self.org()
        year = self.root / "tailoring" / "applications" / "2026"
        year.mkdir(parents=True, exist_ok=True)
        (year / "2026-08-26-acme-engineer.md").write_text(
            "---\ntype: Application\ntitle: \"Acme - engineer\"\n"
            f"company_ref: \"../../../organisations/{ORG_STEM}.md\"\n"
            "submitted: 2026-08-26\n---\n\n# Timeline\n\n- 2026-08-26 submitted\n",
            encoding="utf-8")
        code, out = self.remove("org")
        self.assertEqual(code, 1, out)
        self.assertIn("company_ref", out)
        self.assertTrue(self.concept_path("org").exists())

    def test_the_refusal_counts_and_lists_every_reference(self):
        self.project()
        role = self.concept_path("role")
        role.write_text(role.read_text(encoding="utf-8")
                        + f"\n- [One](../projects/{PROJECT_STEM}.md)\n",
                        encoding="utf-8")
        view = self.root / "tailoring" / "targets" / "ashby-staff.view.md"
        view.write_text(
            "---\ntype: View\nid: view_ashby\nformat_profile: ats-maximal\n"
            "include:\n  - ref: prj_acme_care_coordination_platform\n"
            "    order: 1\n---\n\n# Notes\n\nSelected.\n", encoding="utf-8")
        code, out = self.remove("project")
        self.assertEqual(code, 1, out)
        self.assertIn("2 things still reference it", out)

    def test_a_set_on_an_rm_is_refused(self):
        self.education()
        code, out = self.remove("education", "--set", "note=whatever")
        self.assertEqual(code, 1, out)
        self.assertIn("a delete writes no keys", out)
        self.assertTrue(self.concept_path("education").exists())

    def test_a_concept_that_is_not_there_is_refused_by_its_path(self):
        code, out = self.remove("education", stem="no-such-thing")
        self.assertEqual(code, 1, out)
        self.assertIn(os.path.join("education", "no-such-thing.md"), out)

    def test_a_dry_run_still_makes_every_decision(self):
        # A dry run that skipped the reference walk would be a dry run of half the
        # command, and the half it skipped is the one worth knowing about.
        self.project()
        code, out = self.remove("role", "--dry-run")
        self.assertEqual(code, 1, out)
        self.assertIn(f"projects/{PROJECT_STEM}.md: role: {ROLE_STEM}", out)

    def test_the_dependency_order_can_be_unwound(self):
        # project, then role, then org: each becomes removable once the thing that
        # pointed at it is gone, which is the property that makes the refusal
        # useful rather than merely obstructive.
        self.project()
        for noun in ("project", "role", "org"):
            with self.subTest(noun=noun):
                code, out = self.remove(noun)
                self.assertEqual(code, 0, out)
                self.assertFalse(self.concept_path(noun).exists())


class ProjectAddBehaviourIsUnchanged(CareerCase):
    """`project add` moved out of commands.py into the generic implementation, and
    `class ProjectAdd` in tests/test_authoring.py is the definition of the verb.

    Those tests drive `okf.py`, which cannot reach the new noun-level parser yet, so
    they cannot run. These are their assertions restated against this module so the
    move has evidence behind it now. They are not a replacement: when the catalogue
    is complete, the originals are the ones that matter.
    """

    def setUp(self):
        super().setUp()
        self.role()
        self.concept = self.concept_path("project")

    def project_add(self, *extra, **over):
        return self.add("project", *extra, body="# The problem\n\nWhat happened.\n",
                        **over)

    def test_a_project_is_written_with_its_frontmatter_and_body(self):
        code, out = self.project_add()
        self.assertEqual(code, 0, out)
        text = self.concept.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ntype: Project\n"), text)
        self.assertIn('title: "Acme - care coordination platform"', text)
        self.assertIn('description: "Multi-tenant platform for aged-care '
                      'providers."', text)
        self.assertIn("status: confirmed", text)
        self.assertIn("role: lead-engineer-acme", text)
        self.assertIn("strength: 5", text)
        self.assertIn("recency: 2026", text)
        self.assertIn("seniority: architecture-ownership", text)
        self.assertIn("domains: [healthcare, aged-care]", text)
        self.assertIn("capabilities: [ai-platform-architecture]", text)
        self.assertTrue(text.endswith("# The problem\n\nWhat happened.\n"), text)

    def test_the_concept_is_named_in_the_output_with_its_id(self):
        code, out = self.project_add()
        self.assertEqual(code, 0, out)
        self.assertIn(str(self.concept), out)
        self.assertIn(f"project: {PROJECT_STEM}", out)

    def test_flag_for_is_the_map_commands_py_imports(self):
        # commands.py does `FLAG_FOR = career.FLAG_FOR["Project"]`, and
        # common.extension_keys reads it to tell a `--set` which flag to pass
        # instead. `None` is the marker for a key the command stamps itself.
        flag_for = career.FLAG_FOR["Project"]
        self.assertEqual(flag_for["title"], "--title")
        self.assertEqual(flag_for["capabilities"], "--capability")
        self.assertEqual(flag_for["domains"], "--domain")
        self.assertEqual(flag_for["headline_metric"], "--headline-metric")
        self.assertIsNone(flag_for["timestamp"])
        for type_name in ("Project", "Role", "Organisation", "Education"):
            with self.subTest(type_name=type_name):
                # Every flagged key is a key the schema models, so no flag can
                # write a value nothing reads.
                modelled = {key.name for key in schema.TYPES[type_name]}
                self.assertLessEqual(set(career.FLAG_FOR[type_name]), modelled)

    def test_concept_add_is_the_name_commands_py_calls(self):
        self.assertTrue(callable(career.concept_add))


class WrittenEntirelyThroughTheVerbs(CareerCase):
    """The claim the whole write layer rests on: what these commands write, both
    gates accept and the compile reads back as what was written.

    A command that cheerfully writes a concept failing the bundle gate is not a
    convenience - the person finds out at ship time instead of at the keyboard.
    """

    def scaffold(self):
        self.populate("ai-platform-architecture", "data-sovereignty")
        self.org()
        code, out = self.add("role")
        self.assertEqual(code, 0, out)
        code, out = self.add("project", capability=["ai-platform-architecture"])
        self.assertEqual(code, 0, out)
        code, out = self.add("education")
        self.assertEqual(code, 0, out)

    def record(self):
        code, out = run(OKF_COMPILE, self.root, "--dump-record", "-")
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def assert_gates_are_clean(self):
        code, out = run(VALIDATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("VALID", out)
        self.assertIn("ERRORS 0", out)
        code, out = run(OKF_COMPILE, self.root)
        self.assertEqual(code, 0, out)

    def test_a_bundle_written_through_these_verbs_clears_both_gates(self):
        self.scaffold()
        self.assert_gates_are_clean()

    def test_the_compiled_record_holds_what_was_written(self):
        self.scaffold()
        record = self.record()

        project = record["projects"][0]
        self.assertEqual(project["id"], "prj_acme_care_coordination_platform")
        self.assertEqual(project["title"], "Acme - care coordination platform")
        self.assertEqual(project["capabilities"], ["ai-platform-architecture"])
        self.assertEqual(project["domains"], ["healthcare", "aged-care"])
        self.assertEqual(project["strength"], 5)
        self.assertEqual(project["provenance"]["status"], "confirmed")
        self.assertEqual(project["engagement"], "eng_acme_health")

        engagement = record["engagements"][0]
        self.assertEqual(engagement["id"], "eng_acme_health")
        self.assertEqual(engagement["kind"], "employment")
        # The employer is not stripped out of the role title here: the compile
        # only strips a suffix that matches the organisation's own title, and
        # "Acme" is not "Acme Health". A comparison against a known value, not a
        # guess at what a dash means.
        self.assertEqual(engagement["positions"][0]["title"],
                         "Lead Engineer - Acme")
        self.assertEqual(engagement["positions"][0]["functional_title"],
                         "Platform Engineer")
        self.assertEqual(engagement["period"]["start"]["value"], "2019-04")
        self.assertEqual(engagement["period"]["end"]["value"], "2021-12")

        education = record["education"][0]
        self.assertEqual(education["qualification"], "BTech Computer Science")
        # The two facts Education keeps in its body, read back out of it.
        self.assertEqual(education["institution"], "Mahatma Gandhi University")
        self.assertEqual(education["period"]["start"]["value"], "2011-07")
        self.assertEqual(education["period"]["end"]["value"], "2014-04")
        self.assertEqual(education["level"], "bachelor")

    def test_a_set_and_a_retire_leave_the_bundle_green(self):
        self.scaffold()
        code, out = okf("project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM, "--strength", "3",
                        "--capability", "data-sovereignty")
        self.assertEqual(code, 0, out)
        code, out = okf("education", "set", "--bundle", self.root,
                        "--slug", EDUCATION_STEM,
                        "--institute", "Kerala University",
                        "--period", "2011 - 2014")
        self.assertEqual(code, 0, out)
        code, out = okf("org", "retire", "--bundle", self.root,
                        "--slug", ORG_STEM, "--reason", "no longer claimed")
        self.assertEqual(code, 0, out)
        self.assert_gates_are_clean()
        record = self.record()
        self.assertEqual(record["projects"][0]["strength"], 3)
        self.assertEqual(record["projects"][0]["capabilities"],
                         ["data-sovereignty"])
        self.assertEqual(record["projects"][0]["provenance"]["status"], "inferred")
        self.assertEqual(record["education"][0]["institution"],
                         "Kerala University")
        self.assertEqual(record["education"][0]["period"]["start"]["value"],
                         "2011")

    def test_an_rm_leaves_the_bundle_green(self):
        # The project and the education go; the role and the organisation stay,
        # because okf_compile.py refuses a bundle with neither a Role nor a Project
        # - "the record has nothing to say" - which is its rule about empty bundles
        # rather than anything about this command.
        self.scaffold()
        for noun in ("project", "education"):
            with self.subTest(noun=noun):
                code, out = okf(noun, "rm", "--bundle", self.root,
                                "--slug", STEM_FOR[noun])
                self.assertEqual(code, 0, out)
        self.assert_gates_are_clean()
        record = self.record()
        self.assertEqual(record.get("projects", []), [])
        self.assertEqual(record.get("education", []), [])
        self.assertEqual(record["engagements"][0]["id"], "eng_acme_health")

    def test_the_log_records_every_change_in_order(self):
        self.scaffold()
        rows = [line for line in self.log.read_text(encoding="utf-8").split("\n")
                if line.startswith("- Added ")]
        self.assertEqual(
            rows,
            [f"- Added organisations/{ORG_STEM}.md - Acme Health",
             f"- Added roles/{ROLE_STEM}.md - Lead Engineer - Acme",
             f"- Added projects/{PROJECT_STEM}.md - "
             f"Acme - care coordination platform",
             f"- Added education/{EDUCATION_STEM}.md - BTech Computer Science"])


class ThroughTheRealCli(CareerCase):
    """The same verbs through `commands.main` and through `okf.py`.

    Everything above drives the parser this module registers into, which is the
    right seam for a behavioural test and says nothing about whether the CLI is
    wired to it. These four say that: one verb per noun, in-process and as a
    subprocess, so a `register` that never got called or an `okf <noun>` that never
    got dispatched fails here rather than in somebody's session.
    """

    def setUp(self):
        super().setUp()
        self.commands = authoring_module("authoring.commands")

    def main(self, *argv):
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = self.commands.main([str(item) for item in argv])
        return code, printed.getvalue()

    def test_every_noun_and_verb_is_reachable_through_commands_main(self):
        code, out = self.main("org", "add", "--bundle", self.root,
                             *self.flags("org"), "--body", "x\n")
        self.assertEqual(code, 0, out)
        code, out = self.main("role", "add", "--bundle", self.root,
                             *self.flags("role"), "--body", "x\n")
        self.assertEqual(code, 0, out)
        code, out = self.main("project", "add", "--bundle", self.root,
                             *self.flags("project"), "--body", "x\n")
        self.assertEqual(code, 0, out)
        code, out = self.main("education", "add", "--bundle", self.root,
                             *self.flags("education"), "--body", "x\n")
        self.assertEqual(code, 0, out)
        for noun, verb, extra in (
                ("project", "set", ("--strength", "3")),
                ("education", "retire", ("--reason", "no longer claimed")),
                ("education", "rm", ())):
            with self.subTest(noun=noun, verb=verb):
                code, out = self.main(noun, verb, "--bundle", self.root,
                                      "--slug", STEM_FOR[noun], *extra)
                self.assertEqual(code, 0, out)

    def test_commands_py_exports_the_two_names_it_imports_from_here(self):
        # commands.py does `FLAG_FOR = career.FLAG_FOR["Project"]`, and its
        # `project_add` delegates to `concept_add`. Both names are this module's
        # contract with the CLI: renaming either breaks the import there.
        self.assertIs(self.commands.FLAG_FOR, career.FLAG_FOR["Project"])
        self.assertTrue(callable(career.concept_add))
        self.assertTrue(callable(self.commands.project_add))

    def test_a_refusal_the_console_cannot_spell_is_still_a_refusal(self):
        # A Windows console is cp1252 and a title can carry a character it has no
        # byte for. The `FAIL` print used to raise UnicodeEncodeError from inside
        # the handler, so the one run with a refusal worth reading printed a
        # traceback instead of it.
        console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252",
                                   errors="strict")
        with contextlib.redirect_stdout(console):
            code = self.commands.main(
                ["education", "add", "--bundle", str(self.root),
                 "--title", "項目再構築", "--body", "x\n"])
        console.flush()
        printed = console.buffer.getvalue()
        self.assertEqual(code, 1, printed)
        self.assertIn(b"FAIL", printed)
        self.assertIn("項目再構築".encode("utf-8"), printed)

    def test_okf_py_dispatches_every_one_of_these_nouns(self):
        okf_py = CLI
        # In dependency order, because two of the four carry a relational refusal.
        for noun in ("org", "role", "project", "education"):
            with self.subTest(noun=noun):
                code, out = run(okf_py, noun, "add", "--bundle", self.root,
                                *self.flags(noun), "--body", "x\n")
                self.assertEqual(code, 0, out)
                self.assertTrue(self.concept_path(noun).exists(), out)
        code, out = run(okf_py, "project", "set", "--bundle", self.root,
                        "--slug", PROJECT_STEM, "--strength", "3")
        self.assertEqual(code, 0, out)
        self.assertIn("strength: 3", self.read("project"))


class TheTableAndTheSchemaAgree(unittest.TestCase):
    """The table says which keys get a flag; schema.TYPES says what a value may be.
    Nothing joins them but this, so a drift is a flag writing a key nothing reads or
    a required key with no way to supply it."""

    def test_every_flagged_key_is_a_key_of_its_type(self):
        for spec in career.SPECS:
            modelled = {key.name for key in schema.TYPES[spec.name]}
            for flag in spec.flags:
                with self.subTest(type_name=spec.name, key=flag.key):
                    self.assertIn(flag.key, modelled)

    def test_every_required_key_has_a_flag(self):
        for spec in career.SPECS:
            keys = {flag.key for flag in spec.flags}
            for key in schema.TYPES[spec.name]:
                if key.required:
                    with self.subTest(type_name=spec.name, key=key.name):
                        self.assertIn(key.name, keys)

    def test_every_noun_carries_all_four_verbs(self):
        parser = build_parser()
        nouns = parser._subparsers._group_actions[0].choices
        for spec in career.SPECS:
            with self.subTest(noun=spec.noun):
                verbs = (nouns[spec.noun]._subparsers._group_actions[0].choices)
                self.assertEqual(sorted(verbs), ["add", "retire", "rm", "set"])

    def test_a_noun_with_no_verb_prints_its_own_help(self):
        # commands.main prints the help for whichever level the caller got wrong,
        # which is what `parser=` on both levels is for.
        code, out = okf("project")
        self.assertEqual(code, 2, out)
        self.assertIn("retire", out)
        self.assertIn("rm", out)

    def test_every_noun_is_the_one_common_py_names(self):
        for spec in career.SPECS:
            with self.subTest(type_name=spec.name):
                self.assertEqual(common.NOUNS[spec.noun], spec.name)

    def test_no_two_types_share_a_flag_name_for_different_keys(self):
        # A flag that meant `--location` on one type and something else on another
        # would be the table's one way to be quietly wrong.
        seen = {}
        for spec in career.SPECS:
            for flag in spec.flags:
                if flag.flag is None:
                    continue
                with self.subTest(flag=flag.flag):
                    self.assertEqual(seen.setdefault(flag.flag, flag.key),
                                     flag.key)

    def test_the_labelled_rows_read_the_same_as_the_compilers(self):
        """career.LABELLED is okf_compile.labelled()'s own pattern.

        Compared through what each *reads* rather than through the literal, which
        is the property that matters: a row this layer wrote that the compile read
        differently would be an institution nobody's resume shows. Asserted over
        the shapes the pattern is loose about - `*` bullets, the colon outside the
        stars, extra indentation - because those are where two copies of one regex
        drift apart first.
        """
        okf_compile = load_script(OKF_COMPILE)
        for body_text in (
                "- **Institute:** Mahatma Gandhi University\n",
                "-   **Period**: July 2011 - April 2014\n",
                "* **Level:** Bachelor\n",
                "  - **Institute:**  Kerala University  \n",
                "- **Institute:** One\n- **Period:** 2011 - 2014\n",
                "# Notes\n\nNo rows here at all.\n",
                "- a plain bullet, not a labelled one\n"):
            with self.subTest(body=body_text):
                self.assertEqual(career.labelled_rows(body_text),
                                 okf_compile.labelled(body_text))


if __name__ == "__main__":                               # pragma: no cover
    unittest.main()
