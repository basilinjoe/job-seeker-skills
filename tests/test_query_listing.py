"""`okf list <noun>` - twelve inventories, and the guarantees each one is worth having.

Most of these run `listing.run()` directly and read its rows, which is what `render.py`
exists to make possible: a listing tested through its printed table is a listing whose
tests break when somebody changes a column width. The CLI tests below cover what only
the CLI can get wrong - the exit code, the truncation, and whether `--json` honours
`--top` (it must not).

The load-bearing one is `BulletIdsAreWhatTheWriteLayerAccepts`. `okf view include`
names a bullet id, `authoring.common.item_ids(bundle, "bullet")` is the set it
validates against, and nothing exposed those ids before this noun existed - so an id
this module derived one character differently would be an id `okf list` prints and
`okf view include` then refuses, with nothing to say which of the two was wrong.
"""
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import (CLI, OKF_COMPILE, authoring_module, load_script, query_bundle,
                      query_module, run)

listing = query_module("listing")
filters = query_module("filters")
commands = query_module("commands")
common = authoring_module("authoring.common")
okf_compile = load_script(OKF_COMPILE)

PARSER = commands.build_parser()

# The nouns the CLI routes to listing.py, taken from the CLI rather than restated, so
# that a thirteenth added there is covered by every guarantee in EveryNounAnswers
# without anybody remembering to add it here.
NOUNS = tuple(noun for noun in commands.NOUNS if noun not in commands.AUDITS)

# A project carrying one capability and nothing else, for the counts that need a third
# and fourth project to exist.
PROJECT = """---
type: Project
title: "{title}"
status: confirmed
strength: 3
recency: 2022
capabilities: [{capability}]
---

# The problem

Something needed doing.
"""

# The one bullet shape the fixture does not have: no `status:` field at all, inside a
# `status: confirmed` project. The compile reads it as `inferred`.
BULLETS = """---
type: Project
title: "Care coordination platform"
status: confirmed
strength: 5
recency: 2024
capabilities: [ai-platform-architecture, event-driven-architecture]
---

# The problem

Event propagation took five minutes.

# Bullets

- Cut event propagation from 5 minutes to under 1 second.
  metric: Event propagation latency
  status: confirmed
- Onboarded every tenant in the first quarter.
  metric: Tenants onboarded
  status: confirmed
- Wrote the runbook nobody has confirmed yet.
"""

NONE_HELD = """---
type: Certification Status
title: "Certifications - none held"
status: confirmed
---

# Status

Nothing earned yet. Two are being considered.
"""

# The second shape `build_credentials` counts: no `# Held` block at all, and one
# `- **Issuer:**` line. A `# Held` heading here would make it the first shape and the
# compile would name the credential after the line.
SINGLE_CERT = """---
type: Certification Status
title: "Terraform Associate"
status: confirmed
---

# The certification

- **Issuer:** HashiCorp
"""

LIST_QUESTIONS = """---
type: Open Questions
title: "Open questions"
status: needs-verification
tags:
  - gaps
  - verify
---

# Blocking

- What was p95 before the rewrite?
- Did the sovereignty design ship? - [care](../projects/care-platform.md)

# Missing metrics

- How many tenants by the end of 2024?

# Resolved

- What was the team size? - six
"""

FENCED_QUESTIONS = """---
type: Open Questions
title: "Open questions"
---

# Blocking

- A real question.

# Not yet explored

Write one like this:

```
- This is an example, not a question.
```
"""


def written(bundle, rel, text):
    """One file of the fixture bundle, replaced or added."""
    path = Path(bundle) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return bundle


class Case(unittest.TestCase):
    """The fixture bundle, and the two ways of asking it a question."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.bundle = str(query_bundle(self.tmp / "bundle"))

    def empty(self):
        """A bundle holding only what makes a path a bundle: projects/ and roles/."""
        root = self.tmp / "empty"
        for name in ("projects", "roles"):
            (root / name).mkdir(parents=True)
        return str(root)

    def result(self, noun, *flags, bundle=None):
        bundle = str(bundle or self.bundle)
        args = PARSER.parse_args(["list", bundle, noun] + [str(f) for f in flags])
        return listing.run(bundle, noun, args)

    def rows(self, noun, *flags, bundle=None):
        return self.result(noun, *flags, bundle=bundle).rows

    def row(self, noun, key, value, *flags):
        """The one row whose `key` is `value`, so a test names what it is about."""
        found = [r for r in self.rows(noun, *flags) if r.get(key) == value]
        self.assertEqual(len(found), 1, f"{noun}: {key}={value!r} in {self.rows(noun)}")
        return found[0]


class BulletIdsAreWhatTheWriteLayerAccepts(Case):
    """The blocker this noun was written for.

    `view include --ref` validates against `common.item_ids(bundle, "bullet")`. A
    printed id outside that set is an id somebody copies out of a listing and gets
    refused by the next command, and the two derivations are far enough apart in the
    tree that nothing else would notice them diverging.
    """

    def test_every_printed_bullet_id_is_one_view_include_accepts(self):
        printed = {row["id"] for row in self.rows("bullets")}
        self.assertEqual(printed, set(common.item_ids(self.bundle, "bullet")))

    def test_every_bullet_the_write_layer_accepts_is_printed(self):
        """The other direction. A listing that showed a subset would hide a claim
        from the person choosing evidence, which is the failure that does not
        announce itself."""
        printed = {row["id"] for row in self.rows("bullets")}
        self.assertTrue(printed)
        self.assertEqual(set(common.item_ids(self.bundle, "bullet")) - printed, set())

    def test_skill_and_credential_ids_agree_with_the_write_layer_too(self):
        for kind, noun in (("skill", "skills"), ("credential", "credentials")):
            printed = {row["id"] for row in self.rows(noun)}
            self.assertEqual(printed, set(common.item_ids(self.bundle, kind)),
                             f"{noun} disagrees with item_ids({kind!r})")

    def test_the_inferred_bullet_shows_inferred_not_the_concepts_status(self):
        """projects/care-platform.md is `status: confirmed` and its second bullet is
        `status: inferred`. Reporting the concept's status would say a claim nobody
        has signed off on is confirmed - and `provenance_floor` is what stops it
        rendering, so the row would contradict the document."""
        row = self.row("bullets", "id", "ach_projects_care_platform_md_2")
        self.assertEqual(row["status"], "inferred")

    def test_a_bullet_with_no_status_reads_inferred(self):
        """`okf_compile.bullets` defaults an absent `status:` to `inferred`;
        `ids.Located.status` defaults it to the *concept's* status. The compile's
        rule is the one the renderer applies, so it is the one printed."""
        written(self.bundle, "projects/care-platform.md", BULLETS)
        row = self.row("bullets", "id", "ach_projects_care_platform_md_3")
        self.assertEqual(row["status"], "inferred")

    def test_the_sentence_is_the_last_column_and_is_not_truncated(self):
        """The sentence is the claim. A truncated claim is one somebody reads the
        wrong half of, so its column declares no width."""
        columns = listing.NOUNS["bullets"].columns
        self.assertEqual(columns[-1].key, "text")
        self.assertIsNone(columns[-1].width)

    def test_a_bullet_row_says_which_file_and_line_it_came_from(self):
        row = self.row("bullets", "id", "ach_projects_care_platform_md_1")
        self.assertEqual(row["file"], "projects/care-platform.md")
        self.assertGreater(row["line"], 1)


class MetricsAreCounted(Case):
    """A number nothing rests on is either a missing bullet or a stale row, and
    neither was visible before this counted."""

    def test_the_cited_metric_counts_one(self):
        self.assertEqual(self.row("metrics", "name",
                                  "Event propagation latency")["cited"], 1)

    def test_the_uncited_metric_counts_zero(self):
        """`Tenants onboarded` is in the table and no bullet names it."""
        self.assertEqual(self.row("metrics", "name", "Tenants onboarded")["cited"], 0)

    def test_two_bullets_naming_one_metric_count_two(self):
        written(self.bundle, "projects/care-platform.md",
                BULLETS.replace("Tenants onboarded", "Event propagation latency"))
        self.assertEqual(self.row("metrics", "name",
                                  "Event propagation latency")["cited"], 2)

    def test_the_summary_says_how_many_are_cited_by_nothing(self):
        self.assertIn("1 cited by nothing", self.result("metrics").summary)

    def test_the_id_is_the_one_the_compile_mints(self):
        """`metrics_table` is reused whole rather than re-parsed, so the key a
        bullet's `metric:` field is matched against cannot differ from the id."""
        table = okf_compile.metrics_table(self.bundle)
        self.assertEqual({row["id"] for row in self.rows("metrics")},
                         {row["id"] for row in table.values()})

    def test_a_bundle_with_no_metrics_file_says_so_rather_than_matching_nothing(self):
        result = self.result("metrics", bundle=self.empty())
        self.assertEqual(result.rows, [])
        self.assertTrue(any("achievements/metrics.md" in note
                            for note in result.notes), result.notes)


class CapabilitiesAreCounted(Case):
    """`capabilities` compares as exact strings and is the primary matching axis, so
    the question worth answering is how much evidence each term actually has."""

    def test_a_vocabulary_term_no_project_carries_counts_zero(self):
        row = self.row("capabilities", "term", "data-sovereignty")
        self.assertEqual(row["projects"], 0)
        self.assertFalse(row["through_line"])

    def test_a_term_two_projects_carry_is_not_yet_a_through_line(self):
        """bundle-spec.md draws the line at three. Two is evidence, not a claim."""
        row = self.row("capabilities", "term", "event-driven-architecture")
        self.assertEqual(row["projects"], 2)
        self.assertFalse(row["through_line"])

    def test_a_term_three_projects_carry_is_a_through_line(self):
        written(self.bundle, "projects/third.md",
                PROJECT.format(title="Third", capability="event-driven-architecture"))
        row = self.row("capabilities", "term", "event-driven-architecture")
        self.assertEqual(row["projects"], 3)
        self.assertTrue(row["through_line"])
        self.assertIn("3 or more", self.result("capabilities").summary)

    def test_the_theme_each_term_is_listed_under_is_shown(self):
        self.assertEqual(self.row("capabilities", "term",
                                  "ai-platform-architecture")["theme"], "Platform")

    def test_a_term_a_project_carries_and_the_vocabulary_omits_is_still_listed(self):
        """It is a validation error - `validate_bundle.py` reports it - and hiding it
        here would make this listing disagree with the projects it is counting."""
        written(self.bundle, "projects/third.md",
                PROJECT.format(title="Third", capability="invented-term"))
        row = self.row("capabilities", "term", "invented-term")
        self.assertEqual(row["projects"], 1)
        self.assertIsNone(row["theme"])
        self.assertFalse(row["in_vocabulary"])

    def test_a_fenced_example_is_not_vocabulary(self):
        """`init_bundle` scaffolds this file with its examples inside a fence, so a
        fresh bundle yields nothing. Admitting them would report a dozen terms
        nobody wrote and call every one unused."""
        written(self.bundle, "framework/capability-vocabulary.md",
                "---\ntype: Vocabulary\n---\n\n# Platform\n\n```\n- `example-term`\n"
                "```\n")
        self.assertNotIn("example-term",
                         {row["term"] for row in self.rows("capabilities")})

    def test_the_summary_counts_the_terms_nothing_carries(self):
        self.assertIn("1 on no project", self.result("capabilities").summary)


class OpenQuestions(Case):
    """The file two mode files read as their agenda, in both shapes real bundles
    write it."""

    def test_the_two_open_questions_are_listed(self):
        asked = {row["question"] for row in self.rows("questions")}
        self.assertEqual(asked, {"How many tenants by the end of 2024?",
                                 "Did the sovereignty design ship?"})

    def test_the_resolved_one_is_not(self):
        """A resolved question in a listing of open ones is a to-do somebody does
        again."""
        asked = " ".join(row["question"] for row in self.rows("questions"))
        self.assertNotIn("team size", asked)

    def test_a_row_whose_resolved_cell_is_filled_in_is_not_open(self):
        text = Path(self.bundle, "resume-generation", "open-questions.md").read_text(
            encoding="utf-8")
        written(self.bundle, "resume-generation/open-questions.md",
                text.replace("| sizes the platform claim | 2026-02-01 | |",
                             "| sizes the platform claim | 2026-02-01 | 2026-03-01 |"))
        asked = {row["question"] for row in self.rows("questions")}
        self.assertEqual(asked, {"Did the sovereignty design ship?"})

    def test_the_list_shape_question_add_writes_is_read(self):
        """`okf question add` appends `- <text>` under `# Blocking`, not a table row.
        A reader that only knew the table would report no questions in every bundle
        the write layer has touched."""
        written(self.bundle, "resume-generation/open-questions.md", LIST_QUESTIONS)
        rows = self.rows("questions")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["section"], "Blocking")
        self.assertEqual(rows[0]["question"], "What was p95 before the rewrite?")

    def test_a_list_row_keeps_the_text_question_resolve_matches_on(self):
        """The row's own text, link and all, is the only handle this file gives a
        question - `question resolve --match` takes a substring of exactly it."""
        written(self.bundle, "resume-generation/open-questions.md", LIST_QUESTIONS)
        rows = self.rows("questions")
        self.assertIn("Did the sovereignty design ship? - [care]", rows[1]["question"])

    def test_a_resolved_section_is_excluded_in_the_list_shape_too(self):
        written(self.bundle, "resume-generation/open-questions.md", LIST_QUESTIONS)
        self.assertNotIn("team size",
                         " ".join(row["question"] for row in self.rows("questions")))

    def test_a_fenced_example_is_not_a_question(self):
        written(self.bundle, "resume-generation/open-questions.md", FENCED_QUESTIONS)
        rows = self.rows("questions")
        self.assertEqual([row["question"] for row in rows], ["A real question."])

    def test_a_frontmatter_sequence_is_not_a_question(self):
        """`tags:` written as two `- ` entries is a Markdown list item to anything
        that does not know where the body starts."""
        written(self.bundle, "resume-generation/open-questions.md", LIST_QUESTIONS)
        asked = " ".join(row["question"] for row in self.rows("questions"))
        self.assertNotIn("verify", asked)
        self.assertNotIn("gaps", asked)

    def test_the_reported_line_is_the_file_line_not_the_body_line(self):
        row = self.row("questions", "question", "Did the sovereignty design ship?")
        text = Path(self.bundle, "resume-generation",
                    "open-questions.md").read_text(encoding="utf-8").split("\n")
        self.assertIn("sovereignty", text[row["line"] - 1])

    def test_the_archive_flag_says_it_changed_nothing(self):
        """One file, and the archive holds no copy of it. A flag that appeared to run
        and did not is a boundary the caller believes they crossed."""
        notes = " ".join(self.result("questions", "--archive").notes)
        self.assertIn("--archive changes nothing here", notes)


class Postings(Case):
    """A posting compiles to nothing, so its row is about what has been done with
    it: the two companions it acquires on the way to an application."""

    def test_the_companions_beside_a_worked_posting_are_reported(self):
        row = self.row("postings", "stem", "meridian-principal")
        self.assertTrue(row["gaps"])
        self.assertTrue(row["view"])

    def test_a_posting_with_no_companions_reports_neither(self):
        written(self.bundle, "tailoring/targets/acme-staff.posting.md",
                "---\ntype: Job Posting\ntitle: \"Staff Engineer\"\n"
                "company: \"Acme\"\n---\n\n# Advertisement\n\nHiring.\n")
        row = self.row("postings", "stem", "acme-staff")
        self.assertFalse(row["gaps"])
        self.assertFalse(row["view"])
        self.assertEqual(row["requirements"], 0)

    def test_the_requirements_are_counted(self):
        self.assertEqual(self.row("postings", "stem",
                                  "meridian-principal")["requirements"], 2)

    def test_the_first_column_is_the_stem_because_there_is_no_compiled_id(self):
        self.assertEqual(listing.NOUNS["postings"].columns[0].key, "stem")

    def test_the_archive_is_not_read_by_default(self):
        stems = {row["stem"] for row in self.rows("postings")}
        self.assertEqual(stems, {"meridian-principal"})

    def test_an_archived_posting_is_read_with_archive_and_says_it_is_frozen(self):
        result = self.result("postings", "--archive")
        row = [r for r in result.rows if r["stem"] == "2025-11-03-kestrel-staff"][0]
        self.assertTrue(row["frozen"])
        self.assertTrue(any("may not be edited" in note for note in result.notes))


class Views(Case):
    """A view is the selection a resume renders from, and the two things worth
    knowing about one are what it answers and what it will refuse to render."""

    def test_the_view_is_traced_to_the_posting_beside_it(self):
        """The fixture's view declares no `target:`. The posting shares its stem,
        which is bundle-spec.md's rule for tailoring/targets/, so the companion is
        looked for on disk rather than reported as unknown."""
        row = self.row("views", "id", "view_meridian_principal")
        self.assertEqual(row["target"], "meridian-principal")
        self.assertEqual(row["target_file"],
                         "tailoring/targets/meridian-principal.posting.md")

    def test_the_provenance_floor_and_include_count_are_shown(self):
        """`includes` is the length of the view's own `include:` list, read off the
        file rather than written down here - a view's shape is the fixture's to
        change and this guarantee is about the count being the list's."""
        path = Path(self.bundle, "tailoring", "targets", "meridian-principal.view.md")
        meta, _ = okf_compile.read_frontmatter(path.read_text(encoding="utf-8"))
        row = self.row("views", "id", "view_meridian_principal")
        self.assertEqual(row["provenance_floor"], "confirmed")
        self.assertEqual(row["includes"], len(meta["include"]))


class Credentials(Case):
    """`build_credentials` counts two shapes and refuses a third, and the third is
    the one that put "Certifications - none held" on a resume."""

    def test_the_held_block_entry_is_listed(self):
        row = self.row("credentials", "id", "cred_cloud_certifications_1")
        self.assertEqual(row["issuer"], "Microsoft")
        self.assertEqual(row["issued"], "2024-05")
        self.assertEqual(row["status"], "active")

    def test_a_concept_evidencing_nothing_yields_no_credential(self):
        """`ids.index()` mints `cred_<stem>` for any Certification Status with no
        `# Held` block, where the compile also requires an `- **Issuer:**` line. The
        compile's condition is the one applied here, so a "none held" concept prints
        no row - an id in this listing is one a view may include."""
        written(self.bundle, "education/none-held.md", NONE_HELD)
        self.assertNotIn("cred_none_held", {row["id"] for row in self.rows(
            "credentials")})

    def test_a_single_certification_concept_is_listed(self):
        written(self.bundle, "education/terraform.md", SINGLE_CERT)
        row = self.row("credentials", "id", "cred_terraform")
        self.assertEqual(row["issuer"], "HashiCorp")


class Ordering(Case):
    """A listing whose order is arbitrary is one people read a ranking into."""

    def test_projects_are_strongest_first(self):
        self.assertEqual([row["strength"] for row in self.rows("projects")], [5, 2])

    def test_a_project_with_no_strength_sorts_last(self):
        written(self.bundle, "projects/unscored.md",
                "---\ntype: Project\ntitle: \"Unscored\"\nstatus: confirmed\n---\n\n"
                "# The problem\n\nNobody scored it.\n")
        self.assertEqual(self.rows("projects")[-1]["title"], "Unscored")

    def test_roles_are_most_recent_first(self):
        self.assertEqual([row["start"] for row in self.rows("roles")],
                         ["2022-01", "2019-04"])

    def test_orgs_are_employers_before_prospects(self):
        self.assertEqual([row["relationship"] for row in self.rows("orgs")],
                         ["employer", "prospect"])

    def test_metrics_are_most_cited_first(self):
        self.assertEqual([row["cited"] for row in self.rows("metrics")], [1, 0])

    def test_capabilities_are_most_evidenced_first(self):
        self.assertEqual([row["projects"] for row in self.rows("capabilities")],
                         [2, 1, 0])

    def test_bullets_keep_the_order_the_file_lists_them_in(self):
        """Which is the order they render in and the order their ids number in.
        Sorting by status would make this read as the audit `list unconfirmed` is."""
        self.assertEqual([row["id"] for row in self.rows("bullets")],
                         ["ach_projects_care_platform_md_1",
                          "ach_projects_care_platform_md_2"])

    def test_every_listing_is_stable_across_two_runs(self):
        for noun in NOUNS:
            self.assertEqual(self.rows(noun), self.rows(noun), noun)


class FiltersApplyOrAreRefused(Case):
    """A filter accepted and ignored hands back every row and reads as though it
    ran. That is worse than an empty answer: nobody can tell."""

    def test_strength_narrows_projects(self):
        rows = self.rows("projects", "--strength", "4+")
        self.assertEqual([row["id"] for row in rows], ["prj_care_platform"])

    def test_capability_narrows_projects_exactly(self):
        rows = self.rows("projects", "--capability", "event-driven-architecture")
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.rows("projects", "--capability", "event-driven"), [])

    def test_status_narrows_bullets_by_the_claims_own_provenance(self):
        rows = self.rows("bullets", "--status", "inferred")
        self.assertEqual([row["id"] for row in rows],
                         ["ach_projects_care_platform_md_2"])

    def test_status_narrows_concept_nouns(self):
        self.assertEqual(len(self.rows("projects", "--status", "confirmed")), 1)

    def test_seniority_narrows_roles(self):
        rows = self.rows("roles", "--seniority", "architecture-ownership")
        self.assertEqual([row["id"] for row in rows], ["pos_principal_engineer"])

    def test_a_filter_the_noun_cannot_apply_is_refused_by_name(self):
        with self.assertRaises(filters.Bad) as caught:
            self.rows("metrics", "--strength", "4+")
        message = str(caught.exception)
        self.assertIn("--strength", message)
        self.assertIn("metrics", message)
        self.assertIn("fix:", message)

    def test_a_refusal_names_the_filters_the_noun_does_take(self):
        with self.assertRaises(filters.Bad) as caught:
            self.rows("roles", "--strength", "4")
        self.assertIn("--seniority", str(caught.exception))

    def test_type_is_refused_on_every_noun_because_the_noun_is_the_type(self):
        for noun in NOUNS:
            with self.assertRaises(filters.Bad, msg=noun):
                self.rows(noun, "--type", "Project")

    def test_status_is_refused_on_credentials_because_it_would_mean_currency(self):
        """A `# Held` entry's `status:` is `active`/`expired` and `--status` selects
        provenance. One flag with two meanings across two nouns is the drift
        filters.py exists to prevent, so the refusal explains rather than guesses."""
        with self.assertRaises(filters.Bad) as caught:
            self.rows("credentials", "--status", "active")
        self.assertIn("currency", str(caught.exception))

    def test_a_malformed_bound_is_still_refused_where_the_flag_applies(self):
        with self.assertRaises(filters.Bad) as caught:
            self.rows("projects", "--strength", "high")
        self.assertIn("takes a number", str(caught.exception))

    def test_every_declared_axis_is_a_real_filter_flag(self):
        """A typo in a noun's `axes` would silently refuse a flag that works."""
        for name, spec in listing.NOUNS.items():
            for axis in spec.axes:
                self.assertIn(axis, listing.AXES, f"{name} declares {axis!r}")
            for axis in spec.refusals:
                self.assertIn(axis, listing.AXES, f"{name} refuses {axis!r}")


class EveryNounAnswers(Case):
    """Twelve nouns, one shape. These are the guarantees that hold for all of them,
    so that a thirteenth is one decision rather than twelve."""

    def test_the_twelve_nouns_the_cli_routes_here_are_the_twelve_answered(self):
        routed = [n for n in commands.NOUNS if n not in commands.AUDITS]
        self.assertEqual(set(routed), set(listing.NOUNS))
        self.assertEqual(len(routed), 12)

    def test_every_noun_answers_the_fixture(self):
        for noun in NOUNS:
            result = self.result(noun)
            self.assertTrue(result.rows, f"{noun} found nothing in the fixture")
            self.assertIsNotNone(result.summary, noun)

    def test_every_noun_answers_an_empty_bundle_with_nothing_matched(self):
        """`render.emit` prints "nothing matched" for an empty result with no
        summary, and exits 0. A query has no findings - see query/__init__.py."""
        empty = self.empty()
        for noun in NOUNS:
            result = self.result(noun, bundle=empty)
            self.assertEqual(result.rows, [], noun)
            self.assertIsNone(result.summary, noun)

    def test_no_noun_compiles_the_bundle(self):
        """The read layer's first rule. A compile costs what the thing this replaces
        costs, and refuses a bundle mid-edit - which is when the question gets
        asked."""
        def explode(*a, **k):
            raise AssertionError("a listing called okf_compile.load")

        original = okf_compile.load
        okf_compile.load = explode
        self.addCleanup(setattr, okf_compile, "load", original)
        for noun in NOUNS:
            self.assertTrue(self.rows(noun), noun)

    def test_every_noun_says_whether_it_read_the_archive(self):
        """Every noun for which the archive is a boundary. `questions` reads one file
        that the archive holds no copy of, and says so only when `--archive` is
        passed - see OpenQuestions."""
        for noun in NOUNS:
            if not listing.NOUNS[noun].archive:
                continue
            notes = " ".join(self.result(noun).notes)
            self.assertIn("archive", notes, noun)

    def test_every_row_carries_every_column_it_declares(self):
        """A column whose key nothing sets prints a column of dashes and reads as a
        bundle with nothing in it."""
        for noun in NOUNS:
            spec = listing.NOUNS[noun]
            for row in self.rows(noun):
                for column in spec.columns:
                    self.assertIn(column.key, row, f"{noun}.{column.key}")

    def test_no_column_is_narrower_than_its_own_header(self):
        """`render.table` pads to `min(want, width)` and never shortens a header, so
        a width below the header's length leaves every row under it out of line."""
        for noun, spec in listing.NOUNS.items():
            for column in spec.columns:
                if column.width is not None:
                    self.assertGreaterEqual(column.width, len(column.header),
                                            f"{noun}.{column.key}")

    def test_every_noun_renders_as_columns_not_blocks(self):
        for noun in NOUNS:
            result = self.result(noun)
            self.assertIsNotNone(result.columns, noun)
            self.assertIsNone(result.block, noun)

    def test_every_noun_declares_a_scope(self):
        """An unscoped walk answers correctly and slowly, so it is the one defect
        nobody would notice - `answers()` raises on import for a noun missing from
        `SCOPES` rather than letting it read the whole bundle."""
        self.assertEqual(set(listing.SCOPES), set(listing.NOUNS))

    def test_the_scopes_agree_with_where_the_write_layer_files_a_concept(self):
        """`SCOPES` is a deliberate copy of `authoring.common.DIRECTORIES` - imported
        here rather than there, because the read layer must not load the write layer
        to answer a question. This is what stops the copy drifting."""
        writes = {"projects": "Project", "roles": "Role", "orgs": "Organisation",
                  "education": "Education", "skills": "Skill Set",
                  "bullets": "Project", "credentials": "Certification Status",
                  "metrics": "Project", "capabilities": "Project"}
        for noun, ctype in writes.items():
            self.assertEqual(listing.SCOPES[noun],
                             (common.DIRECTORIES[ctype],), noun)
        for noun in ("views", "postings"):
            # `tailoring/`, not `tailoring/targets/`, because `--archive` widens
            # these two into `tailoring/applications/` and the archive is admitted by
            # `walk`'s own flag rather than by a second scope.
            self.assertEqual(listing.SCOPES[noun], ("tailoring",))
            self.assertTrue(
                common.DIRECTORIES[{"views": "View", "postings": "Job Posting"}[noun]]
                .startswith("tailoring/"))

    def test_a_noun_reads_only_the_directories_its_concepts_live_in(self):
        """The measurement behind `SCOPES`: unscoped, `list projects` opened every
        file in the bundle and cost more than the compile it replaces."""
        opened = []
        original = listing.walk.by_type

        def watched(root, *types, **kwargs):
            found = original(root, *types, **kwargs)
            opened.extend(concept.rel for concept in found)
            return found

        listing.walk.by_type = watched
        self.addCleanup(setattr, listing.walk, "by_type", original)
        self.rows("projects")
        self.assertTrue(opened)
        self.assertTrue(all(rel.startswith("projects/") for rel in opened), opened)

    def test_an_unknown_noun_names_the_ones_that_exist(self):
        args = PARSER.parse_args(["list", self.bundle, "projects"])
        with self.assertRaises(ValueError) as caught:
            listing.run(self.bundle, "frobnicate", args)
        self.assertIn("bullets", str(caught.exception))

    def test_nothing_is_written(self):
        """Every command in this package's read layer reads. A listing that touched
        a file would be a query somebody cannot run on a bundle mid-edit."""
        before = {path: path.stat().st_mtime_ns
                  for path in Path(self.bundle).rglob("*") if path.is_file()}
        for noun in NOUNS:
            self.rows(noun, "--archive")
        after = {path: path.stat().st_mtime_ns
                 for path in Path(self.bundle).rglob("*") if path.is_file()}
        self.assertEqual(before, after)


class ThroughTheCli(Case):
    """What only the CLI can get wrong: the exit code, the cut, and `--json`."""

    def test_list_bullets_prints_every_id_the_write_layer_accepts(self):
        code, out = run(CLI, "list", self.bundle, "bullets")
        self.assertEqual(code, 0, out)
        for ident in common.item_ids(self.bundle, "bullet"):
            self.assertIn(ident, out)

    def test_every_noun_exits_zero_on_the_fixture(self):
        for noun in NOUNS:
            code, out = run(CLI, "list", self.bundle, noun)
            self.assertEqual(code, 0, f"{noun}: {out}")

    def test_every_noun_exits_zero_on_an_empty_bundle_and_says_nothing_matched(self):
        empty = self.empty()
        for noun in NOUNS:
            code, out = run(CLI, "list", empty, noun)
            self.assertEqual(code, 0, f"{noun}: {out}")
            self.assertIn("nothing matched", out, noun)

    def test_json_is_not_truncated_by_top(self):
        """`--top` is a reading aid and a parser does not read."""
        code, out = run(CLI, "list", self.bundle, "bullets", "--json", "--top", "1")
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertEqual(doc["count"], 2)
        self.assertEqual(len(doc["rows"]), 2)

    def test_a_cut_table_says_how_many_rows_it_did_not_show(self):
        code, out = run(CLI, "list", self.bundle, "projects", "--top", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("and 1 more", out)

    def test_a_refused_filter_exits_two(self):
        code, out = run(CLI, "list", self.bundle, "metrics", "--strength", "4+")
        self.assertEqual(code, 2, out)
        self.assertIn("--strength", out)

    def test_the_unread_archive_is_named(self):
        code, out = run(CLI, "list", self.bundle, "views")
        self.assertEqual(code, 0, out)
        self.assertIn("--archive", out)

    def test_json_carries_the_bundle_and_the_command(self):
        code, out = run(CLI, "list", self.bundle, "capabilities", "--json")
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertEqual(doc["command"], "list")
        self.assertEqual(doc["count"], 3)


if __name__ == "__main__":                                # pragma: no cover
    unittest.main()
