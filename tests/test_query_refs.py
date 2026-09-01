"""`okf refs` - everything that still points at one thing.

The command's whole value is one sentence: "nothing references it, so a delete would be
permitted". A wrong *narrow* answer here - a reference this layer cannot see - is worse
than no command at all, because somebody acts on it and loses a reference the compile
then refuses on. So these tests are shaped around two failures rather than around the
happy path.

**Agreement with the refusal.** `AgreesWithTheRefusal` drives `okf project rm
--dry-run` and asserts `refs` reports exactly the references that refusal names. That
is the load-bearing test of the module: `refs` for a career concept is
`authoring.career.references()` called unchanged, and this is what proves it was not
quietly forked.

**The archive.** `refs` reads `tailoring/applications/` by default, alone among the read
verbs, because a sent application is where most references to a posting or a view live.
`TheArchiveIsRead` pins that, and pins that a row from a *frozen companion* says FROZEN
while the application's own `<stem>.md` does not - the decision is only safe while the
unwritable rows carry that warning, and only honest while the writable one does not.

The fixture is `fixtures.query_bundle`, so the references asserted below are the ones a
real bundle has: two roles naming an organisation, a project naming a role, a metrics
table linking to a project, a view selecting an engagement, a bullet and a skill, and
one filed application naming a frozen posting, a frozen view and a company's concept.
"""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixtures import CLI, OKF_COMPILE, load_script, query_bundle, query_module, run

refs = query_module("refs")
commands = query_module("commands")
okf_compile = load_script(OKF_COMPILE)

# A second view in tailoring/targets/, well formed. `references/view-format.md` is
# explicit that `include[].ref` names an **owner** - an engagement or a project - and
# that claim ids sit in `achievements` and in the view's own `skills`. So this file
# exercises both readers at once: `career.references()` sees the `ref` as a reference to
# the project, and `claims._selected` sees the `achievements` list as a reference to the
# bullet.
OWNER_VIEW = """---
type: View
id: view_extra
format_profile: ats-maximal
region_profile: urs:profile:au/1
include:
  - ref: prj_care_platform
    order: 1
    achievements: [ach_projects_care_platform_md_1]
---
"""

# The malformed spelling: a claim id where an owner id belongs. `urs/resolve.py` keys
# its selection by owner id, so this view selects nothing and renders nothing, and no
# gate says which id was wrong. `refs` reports it anyway, with its position, because it
# is still a mention of the id a delete would strand - and because the position is what
# somebody needs in order to move it into `achievements`.
MALFORMED_VIEW = """---
type: View
id: view_wrong
format_profile: ats-maximal
include:
  - ref: ach_projects_care_platform_md_1
---
"""

# The view an application froze at submission, selecting what it actually rendered. A
# frozen companion beside the sent application, so it may not be edited - and the whole
# reason this command reads the archive by default: the claims it names cannot be cut,
# and a `refs` that could not see it would say they could.
SENT_VIEW = """---
type: View
title: "Kestrel - staff engineer (as sent)"
frozen: true
frozen_date: "2025-11-03"
id: view_kestrel_staff
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
include:
  - ref: eng_meridian_health
    order: 1
    achievements: [ach_projects_care_platform_md_1]
skills: [skill_dotnet]
---
"""

APPLICATION = "tailoring/applications/2025/2025-11-03-kestrel-staff.md"
SENT_VIEW_FILE = "tailoring/applications/2025/2025-11-03-kestrel-staff.view.md"
WORKING_VIEW = "tailoring/targets/meridian-principal.view.md"

# The same link twice, in a file with no frontmatter at all. Two identical references
# in one file are one reference, and an untyped file is still text somebody wrote.
TWO_LINKS = """# Notes from the retro

- [the posting](../tailoring/targets/meridian-principal.posting.md)
- [the posting again](../tailoring/targets/meridian-principal.posting.md)
"""

# A link nothing would ever report. validate_bundle.py strips fenced blocks and inline
# code before looking for a broken link, so an answer that counted one would send
# somebody to remove a reference that is not one.
FENCED_LINK = """# How a target is linked

```
- [example](../tailoring/targets/meridian-principal.posting.md)
```

See `[x](../tailoring/targets/meridian-principal.posting.md)` for the shape.
"""

# A bullet citing the same metric the flagship cites, spelt differently. The compile
# matches a `metric:` field to a table row through `okf_compile.slug`, so these are one
# number to the record and have to be one here.
LOUD_METRIC = """
# Bullets

- Reconciled the ledger against the invoice run every night.
  metric: EVENT   propagation Latency
  status: confirmed
"""


class RefsCase(unittest.TestCase):
    """The read layer's fixture bundle, and two ways in.

    `rows()` reads the `Result` directly, because that is the contract every query
    module has and reading rows beats parsing a table. `okf()` goes through
    `commands.main` in this interpreter, for the exit code, the printed answer and so
    that a `mock.patch` in a test is actually in force.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = query_bundle(Path(self._tmp.name) / "bundle")

    def write(self, rel, text):
        path = Path(self.root, *rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def result(self, target):
        args = argparse.Namespace(archive=False, as_json=False, top=0)
        return refs.run(str(self.root), target, args)

    def rows(self, target):
        """(file, reference) for every row, which is what a caller reads."""
        return [(row["file"], row["reference"]) for row in self.result(target).rows]

    def okf(self, *argv):
        """`okf <verb> ...` in this interpreter. Returns (exit code, everything printed)."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
            code = commands.main([str(item) for item in argv])
        return code, printed.getvalue()


class TheFourKindsCareReferencesFinds(RefsCase):
    """A relational key, a markdown link, a view's include and an archived path.

    `write-commands.md`'s own list, and the four `okf project rm` refuses over. `refs`
    must report each of them, because the question it answers is the same question.
    """

    def test_the_roles_that_name_an_organisation_are_reported_with_the_key(self):
        self.assertEqual(self.rows("meridian-health"), [
            ("roles/principal-engineer.md", "organisation: meridian-health"),
            ("roles/senior-engineer.md", "organisation: meridian-health"),
            # Real, and not a role: the fixture's view selects the engagement the two
            # roles under this organisation compile to - see the test below.
            (WORKING_VIEW, "include[1].ref: eng_meridian_health"),
        ])

    def test_the_project_that_names_a_role_is_reported(self):
        self.assertEqual(self.rows("principal-engineer"),
                         [("projects/care-platform.md", "role: principal-engineer")])

    def test_the_metrics_table_linking_to_a_project_is_reported_as_a_link(self):
        self.assertEqual(
            self.rows("care-platform"),
            [("achievements/metrics.md",
              "a markdown link to ../projects/care-platform.md")])

    def test_the_metrics_table_links_twice_and_counts_once(self):
        """Both rows of achievements/metrics.md link to the same project. An answer
        that counted two reads as two things to remove before a delete."""
        table = Path(self.root, "achievements", "metrics.md").read_text(encoding="utf-8")
        self.assertEqual(table.count("../projects/care-platform.md"), 2)
        self.assertEqual(len(self.rows("care-platform")), 1)

    def test_a_view_that_includes_the_project_is_reported_with_its_position(self):
        self.write("tailoring/targets/extra.view.md", OWNER_VIEW)
        self.assertIn(("tailoring/targets/extra.view.md",
                       "include[1].ref: prj_care_platform"),
                      self.rows("care-platform"))

    def test_a_view_that_includes_the_engagement_blocks_the_organisation(self):
        """An engagement's id is derived from the organisation's stem, so a view that
        selected an employer names `eng_<stem>` and never the filename.
        `career.references()` looks for both prefixes and this is the row that proves
        `refs` reports the second one - the fixture's view selects the engagement."""
        self.assertIn((WORKING_VIEW, "include[1].ref: eng_meridian_health"),
                      self.rows("meridian-health"))

    def test_an_archived_application_naming_a_company_is_reported_by_its_path_key(self):
        """`company_ref` is a relative path in frontmatter, not a markdown link, so
        nothing but a resolve of that key can see it."""
        self.assertEqual(
            self.rows("kestrel-systems"),
            [(APPLICATION, "company_ref: ../../../organisations/kestrel-systems.md")])


class TheKindsRmCannotAsk(RefsCase):
    """A claim, a metric, a posting, a view, a narrative.

    None of these has a `rm` that walks the tree, so before this command nothing in
    the codebase could answer "is anything still pointing at it".
    """

    def test_a_bullet_a_view_selects_is_reported_the_way_bullet_rm_sees_it(self):
        """`okf bullet rm` refuses on `claims._selected`, which reads
        `include[].achievements`, `include[].skills` and the view's own `skills` - and
        deliberately not `include[].ref`, which names an owner. A `refs` reading any
        other set would call a bullet safe to cut that `rm` will not cut, which was the
        whole argument for asking that function rather than the frontmatter."""
        self.assertEqual(
            self.rows("ach_projects_care_platform_md_1"),
            [(WORKING_VIEW, "selected: ach_projects_care_platform_md_1")])

    def test_a_skill_a_view_selects_through_its_own_skills_list_is_reported(self):
        """The third place `_selected` looks is the view's top-level `skills:`, which
        is where the fixture's view names this one - not inside an `include` entry."""
        self.assertEqual(self.rows("skill_dotnet"),
                         [(WORKING_VIEW, "selected: skill_dotnet")])

    def test_a_second_views_include_achievements_is_seen_too(self):
        self.write("tailoring/targets/extra.view.md", OWNER_VIEW)
        self.assertIn(("tailoring/targets/extra.view.md",
                       "selected: ach_projects_care_platform_md_1"),
                      self.rows("ach_projects_care_platform_md_1"))

    def test_a_claim_id_written_where_an_owner_id_belongs_is_still_reported(self):
        """`include[].ref` names an engagement or a project, so a claim id there
        selects nothing and renders nothing - `urs/resolve.py` keys its selection by
        owner id. It is still a mention of the id a delete would strand, and reporting
        it with its position is what lets somebody move it into `achievements` where it
        belongs. A view nobody can see is wrong about is a view nobody fixes."""
        self.write("tailoring/targets/wrong.view.md", MALFORMED_VIEW)
        self.assertIn(("tailoring/targets/wrong.view.md",
                       "include[1].ref: ach_projects_care_platform_md_1"),
                      self.rows("ach_projects_care_platform_md_1"))

    def test_the_bullet_that_cites_a_metric_is_reported_with_its_id_and_line(self):
        rows = self.result("met_event_propagation_latency").rows
        self.assertEqual(
            [(row["file"], row["line"], row["reference"]) for row in rows],
            [("projects/care-platform.md", 23,
              "ach_projects_care_platform_md_1: metric: Event propagation latency")])

    def test_a_metric_cited_in_another_spelling_is_still_one_citation(self):
        """`okf_compile.bullets()` matches a `metric:` field to a table row through
        `okf_compile.slug`, so case and spacing do not make a second number. Re-slugging
        either half here is how `refs` and the compile disagree about which bullet
        rests on which figure."""
        path = Path(self.root, "projects", "billing-reconciliation.md")
        path.write_text(path.read_text(encoding="utf-8") + LOUD_METRIC, encoding="utf-8")
        self.assertEqual(
            [row[0] for row in self.rows("met_event_propagation_latency")],
            ["projects/billing-reconciliation.md", "projects/care-platform.md"])

    def test_a_metric_no_bullet_cites_says_a_delete_is_safe(self):
        """The second row of the fixture's table is cited by nothing, which is a
        legitimate state and not a finding - see query/__init__.py."""
        code, out = self.okf("refs", self.root, "met_tenants_onboarded")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing in the bundle points at met_tenants_onboarded", out)

    def test_the_application_that_answered_a_posting_is_found_by_the_postings_stem(self):
        self.assertEqual(
            self.rows("2025-11-03-kestrel-staff.posting"),
            [(APPLICATION, "posting: 2025-11-03-kestrel-staff.posting.md")])

    def test_a_view_is_found_by_the_path_that_names_it_and_by_the_id_that_names_it(self):
        """An application names its view twice - `view_file:` is the frozen copy beside
        it and `view:` is the id inside that copy. Both are references, and reporting
        one of them would understate what a delete would break."""
        self.assertEqual(self.rows("view_kestrel_staff"), [
            (APPLICATION, "view_file: 2025-11-03-kestrel-staff.view.md"),
            (APPLICATION, "view: view_kestrel_staff"),
        ])

    def test_the_view_that_prints_a_narrative_is_reported(self):
        self.assertEqual(
            self.rows("nar_a_positioning_led_default"),
            [(WORKING_VIEW, "narrative: nar_a_positioning_led_default")])

    def test_a_link_to_a_posting_is_a_reference_and_counts_once(self):
        self.write("sources/notes-real.md", TWO_LINKS)
        self.assertEqual(
            self.rows("meridian-principal.posting"),
            [("sources/notes-real.md",
              "a markdown link to ../tailoring/targets/meridian-principal.posting.md")])

    def test_a_link_inside_a_fence_or_backticks_is_not_a_reference(self):
        """The same rule `validate_bundle.py` reads links by, reached through
        `career._link_targets` rather than restated - an example link in a template is
        not a reference, and reporting one would send somebody to remove nothing."""
        self.write("sources/notes-fenced.md", FENCED_LINK)
        self.assertEqual(self.rows("meridian-principal.posting"), [])


class TailoringIsReadWhole(RefsCase):
    """`walk()` reads only `*.view.md` under tailoring/targets/ by default; this scan
    asks for all of it.

    That default is right for a listing - a posting and a gap assessment are 200 files
    per hundred targets the record never reads - and wrong for this command, which is
    not asking what the record reads but what a delete would break. A posting names
    another posting through `snapshot_of:` and `superseded_by:`; a gap assessment links
    to the evidence it weighed. `career.references()` reads both through its own walk,
    so narrowing here would leave one command with two breadths: the career half
    seeing a reference the posting half cannot.
    """

    def test_a_link_written_in_a_gap_assessment_is_seen(self):
        gaps = Path(self.root, "tailoring", "targets", "meridian-principal.gaps.md")
        gaps.write_text(gaps.read_text(encoding="utf-8")
                        + "\n- [the advertisement](meridian-principal.posting.md)\n",
                        encoding="utf-8")
        self.assertEqual(
            self.rows("meridian-principal.posting"),
            [("tailoring/targets/meridian-principal.gaps.md",
              "a markdown link to meridian-principal.posting.md")])

    def test_a_posting_that_snapshots_another_posting_is_a_reference(self):
        self.write("tailoring/targets/meridian-principal-v2.posting.md",
                   "---\ntype: Job Posting\n"
                   "title: \"Principal Engineer - second round\"\n"
                   "company: \"Meridian Health\"\n"
                   "snapshot_of: \"meridian-principal.posting.md\"\n---\n")
        self.assertEqual(
            self.rows("meridian-principal.posting"),
            [("tailoring/targets/meridian-principal-v2.posting.md",
              "snapshot_of: meridian-principal.posting.md")])

    def test_the_archived_application_concept_is_still_walked(self):
        """`views`-narrowing must not reach the archive. An `Application` is
        `<stem>.md` and not a `.view.md`, so a narrowing that applied there would
        honour `archive=True` by walking into the directory and then skipping every
        file the flag was for - and this command, which reads the archive by default,
        would find no application at all and report a sent application's references as
        nothing."""
        self.assertEqual([row[0] for row in self.rows("kestrel-systems")],
                         [APPLICATION])
        self.assertEqual([row[0] for row in self.rows("view_kestrel_staff")],
                         [APPLICATION] * 2)


class SpellingsAgree(RefsCase):
    """A caller must not have to know which spelling of a thing the command wants.

    `okf refs` takes a compiled id or a bare file stem, and an organisation has three
    spellings - the stem, `org_<stem>` and the `eng_<stem>` a view would name. All of
    them are the same question and any difference between the answers is a difference
    somebody would act on.
    """

    def test_a_stem_and_its_compiled_id_answer_identically(self):
        stem, ident = self.result("care-platform"), self.result("prj_care_platform")
        self.assertEqual(stem.rows, ident.rows)
        self.assertEqual(stem.summary, ident.summary)

    def test_an_organisation_answers_the_same_by_stem_id_and_engagement_id(self):
        by_stem = self.rows("meridian-health")
        self.assertEqual(self.rows("org_meridian_health"), by_stem)
        self.assertEqual(self.rows("eng_meridian_health"), by_stem)

    def test_a_view_answers_the_same_by_stem_and_by_id(self):
        self.assertEqual(self.rows("2025-11-03-kestrel-staff.view"),
                         self.rows("view_kestrel_staff"))

    def test_a_stem_two_files_share_is_refused_rather_than_answered_about_one(self):
        """Answering about one of them would be this command's worst failure: "nothing
        points at this, the delete is permitted", about a file the caller did not
        mean."""
        for directory, type_name in (("projects", "Project"), ("roles", "Role")):
            self.write(f"{directory}/ambiguous.md",
                       f"---\ntype: {type_name}\ntitle: \"Ambiguous\"\n---\n")
        code, out = self.okf("refs", self.root, "ambiguous")
        self.assertEqual(code, 2, out)
        self.assertIn("projects/ambiguous.md", out)
        self.assertIn("roles/ambiguous.md", out)


class NothingPointsAtIt(RefsCase):
    """The answer the command exists for, and the one it is easiest to get wrong.

    Exit 0, because a query has no findings - `query/__init__.py` has the argument -
    and a sentence naming the delete that would therefore be permitted. Somebody acts
    on that sentence, so it has to name the command rather than implying it.
    """

    def test_a_concept_nothing_points_at_exits_zero_and_names_the_delete(self):
        code, out = self.okf("refs", self.root, "billing-reconciliation")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing in the bundle points at prj_billing_reconciliation", out)
        self.assertIn("`okf project rm --slug billing-reconciliation` would permit "
                      "the delete", out)

    def test_a_referenced_concept_still_exits_zero(self):
        """Nothing in this layer exits 1. Grep's convention - 1 means no match - is
        the tempting one and the wrong one: a reference found is not a finding."""
        code, out = self.okf("refs", self.root, "meridian-health")
        self.assertEqual(code, 0, out)
        self.assertIn("3 things still point at org_meridian_health", out)

    def test_the_summary_names_the_claim_delete_where_there_is_one(self):
        code, out = self.okf("refs", self.root, "skill_dotnet")
        self.assertEqual(code, 0, out)
        self.assertIn("`okf skill rm --concept competencies --id skill_dotnet`", out)

    def test_a_single_reference_reads_as_one_thing(self):
        code, out = self.okf("refs", self.root, "principal-engineer")
        self.assertIn("1 thing still points at pos_principal_engineer", out)


class TheArchiveIsRead(RefsCase):
    """Alone among the read verbs, and only safe while a frozen row says FROZEN.

    A sent application names the posting it answered, the view it rendered from and the
    company's concept, and the view it froze still selects the bullets it rendered.
    `refs` skipping that by default would answer "nothing points at this" about a claim
    a sent application does point at - a wrong answer, not a narrow one - and would
    disagree with the `rm` refusals it exists to predict.

    `sent()` puts a real selection into the frozen view beside the fixture's
    application, because the fixture's own copy selects nothing and a FROZEN assertion
    needs an archived file that actually holds a reference.
    """

    def sent(self):
        self.write(SENT_VIEW_FILE, SENT_VIEW)

    def test_a_claim_a_sent_application_still_selects_is_reported(self):
        """The case that pays for the whole decision: this bullet was rendered into a
        resume somebody posted, so it may not be cut, and only the archive says so."""
        self.sent()
        self.assertIn((SENT_VIEW_FILE, "selected: ach_projects_care_platform_md_1"),
                      self.rows("ach_projects_care_platform_md_1"))

    def test_the_frozen_row_is_marked_frozen(self):
        self.sent()
        row, = [r for r in self.result("skill_dotnet").rows
                if r["file"] == SENT_VIEW_FILE]
        self.assertTrue(row["frozen"])

    def test_the_printed_frozen_row_says_it_may_not_be_edited(self):
        self.sent()
        code, out = self.okf("refs", self.root, "skill_dotnet")
        self.assertEqual(code, 0, out)
        self.assertIn("FROZEN - an archived copy beside a sent application; "
                      "do not edit it", out)

    def test_a_working_copy_is_not_marked_frozen(self):
        row, = self.result("principal-engineer").rows
        self.assertFalse(row["frozen"])

    def test_the_applications_own_file_is_not_marked_frozen(self):
        """`bundle-spec.md` draws the line at the companions, not at the directory:
        `<stem>.posting.md`, `<stem>.gaps.md` and `<stem>.view.md` may not be edited,
        but the application's own `<stem>.md` has its `# Timeline` appended to for as
        long as the process is live. Marking it FROZEN told somebody the one file in
        there they are supposed to write to was off limits."""
        row, = self.result("kestrel-systems").rows
        self.assertEqual(row["file"], APPLICATION)
        self.assertFalse(row["frozen"])

    def test_the_note_says_the_archive_was_read(self):
        code, out = self.okf("refs", self.root, "kestrel-systems")
        self.assertIn("the frozen archive is read here", out)
        self.assertIn("--archive is accepted", out)

    def test_the_archive_flag_changes_nothing(self):
        plain = self.okf("refs", self.root, "view_kestrel_staff")
        asked = self.okf("refs", self.root, "view_kestrel_staff", "--archive")
        self.assertEqual(plain, asked)

    def test_an_id_that_only_the_archive_mints_still_resolves(self):
        """`view_kestrel_staff` exists only in tailoring/applications/. A resolve that
        skipped the archive would refuse the target rather than answer about it."""
        code, out = self.okf("refs", self.root, "view_kestrel_staff")
        self.assertEqual(code, 0, out)


class AgreesWithTheRefusal(RefsCase):
    """The load-bearing test: `refs` reports what `okf project rm` refuses over.

    `refs` for a career concept is `authoring.career.references()` called unchanged,
    and this is what proves that. Two implementations of "what points at this" is how
    `rm` comes to refuse a delete `refs` called safe - or, far worse, how `refs` comes
    to permit one `rm` would have stopped.
    """

    def refusal(self, stem):
        code, out = run(CLI, "project", "rm", "--bundle", self.root, "--slug", stem,
                        "--dry-run")
        self.assertEqual(code, 1, out)
        return out

    def test_every_reference_the_refusal_lists_is_a_row_refs_reports(self):
        self.write("tailoring/targets/extra.view.md", OWNER_VIEW)
        rows = self.rows("care-platform")
        self.assertEqual(len(rows), 2, rows)
        out = self.refusal("care-platform")
        self.assertIn("2 things still reference it", out)
        for rel, what in rows:
            self.assertIn(f"  {rel}: {what}", out)

    def test_a_concept_refs_calls_unreferenced_is_one_rm_deletes(self):
        self.assertEqual(self.rows("billing-reconciliation"), [])
        code, out = run(CLI, "project", "rm", "--bundle", self.root,
                        "--slug", "billing-reconciliation", "--dry-run")
        self.assertEqual(code, 0, out)

    def test_a_fenced_link_is_not_a_reference_to_either_of_them(self):
        """The two readers have to agree about what a link is, not only about how many
        there are. `career._link_targets` is the single one, reached from both."""
        role = Path(self.root, "roles", "senior-engineer.md")
        role.write_text(
            role.read_text(encoding="utf-8")
            + "\n```\n- [example](../projects/billing-reconciliation.md)\n```\n",
            encoding="utf-8")
        self.assertEqual(self.rows("billing-reconciliation"), [])
        code, out = run(CLI, "project", "rm", "--bundle", self.root,
                        "--slug", "billing-reconciliation", "--dry-run")
        self.assertEqual(code, 0, out)


class NothingCompiles(RefsCase):
    """`okf_compile.load()` is never called, by any query - query/__init__.py's rule.

    A query that compiled would cost what the thing it replaces costs, and would refuse
    to answer about a bundle that is mid-edit - which is exactly when somebody asks
    whether a concept is safe to delete.
    """

    def broken_compile(self):
        return mock.patch.object(
            okf_compile, "load",
            side_effect=AssertionError("a query must not compile the bundle"))

    def test_a_stem_still_answers(self):
        with self.broken_compile():
            self.assertEqual(
                self.rows("care-platform"),
                [("achievements/metrics.md",
                  "a markdown link to ../projects/care-platform.md")])

    def test_an_id_still_answers(self):
        with self.broken_compile():
            self.assertEqual(len(self.rows("ach_projects_care_platform_md_1")), 1)

    def test_a_metric_still_answers(self):
        with self.broken_compile():
            self.assertEqual(len(self.rows("met_event_propagation_latency")), 1)

    def test_an_unresolvable_target_still_refuses_by_name(self):
        with self.broken_compile():
            code, out = self.okf("refs", self.root, "prj_care_platfrom")
        self.assertEqual(code, 2, out)


class CalledWrong(RefsCase):
    """Exit 2, and a sentence saying what to type instead. Never a traceback."""

    def test_a_typo_exits_two_and_names_the_near_misses(self):
        code, out = self.okf("refs", self.root, "prj_care_platfrom")
        self.assertEqual(code, 2, out)
        self.assertIn("prj_care_platfrom", out)
        self.assertIn("did you mean prj_care_platform", out)

    def test_a_target_nothing_mints_is_refused_with_somewhere_to_look(self):
        code, out = self.okf("refs", self.root, "not-a-thing-at-all")
        self.assertEqual(code, 2, out)
        self.assertIn("okf search", out)

    def test_a_missing_target_says_both_spellings_are_accepted(self):
        code, out = self.okf("refs", self.root)
        self.assertEqual(code, 2, out)
        self.assertIn("okf refs needs an id or a file stem", out)

    def test_a_path_that_is_not_a_bundle_is_refused(self):
        code, out = self.okf("refs", Path(self.root, "projects"), "care-platform")
        self.assertEqual(code, 2, out)
        self.assertIn("not a bundle", out)

    def test_index_is_not_a_stem_this_command_resolves(self):
        """Every directory has one, so answering about a stem of `index` would be
        answering about whichever the walk reached first."""
        code, out = self.okf("refs", self.root, "index")
        self.assertEqual(code, 2, out)


class TheJsonEnvelope(RefsCase):
    """`--json` is what an agent reads, and it is never truncated."""

    def payload(self, *extra):
        code, out = self.okf("refs", self.root, *extra, "--json")
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def test_the_envelope_names_what_the_target_resolved_to(self):
        found = self.payload("care-platform")
        self.assertEqual(found["target"], "prj_care_platform")
        self.assertEqual(found["kind"], "project")
        self.assertEqual(found["target_file"], "projects/care-platform.md")

    def test_a_row_carries_the_file_the_reference_and_whether_it_is_frozen(self):
        row, = self.payload("kestrel-systems")["rows"]
        self.assertEqual(row["file"], APPLICATION)
        self.assertEqual(row["reference"],
                         "company_ref: ../../../organisations/kestrel-systems.md")
        # False on purpose: the application's own file is appended to for as long as
        # the process is live - `TheArchiveIsRead` has the argument. The key is here
        # either way, because a parser reading these rows has to be told.
        self.assertIs(row["frozen"], False)

    def test_a_frozen_row_carries_the_flag_as_a_boolean(self):
        self.write(SENT_VIEW_FILE, SENT_VIEW)
        row, = [r for r in self.payload("skill_dotnet")["rows"]
                if r["file"] == SENT_VIEW_FILE]
        self.assertIs(row["frozen"], True)

    def test_an_empty_answer_is_a_count_of_zero_rather_than_a_refusal(self):
        found = self.payload("billing-reconciliation")
        self.assertEqual(found["count"], 0)
        self.assertEqual(found["rows"], [])


class ThroughTheRealCli(RefsCase):
    """`okf refs` as a person types it, in its own interpreter."""

    def test_a_stem_answers_and_exits_zero(self):
        code, out = run(CLI, "refs", self.root, "care-platform")
        self.assertEqual(code, 0, out)
        self.assertIn("achievements/metrics.md", out)

    def test_an_unknown_id_exits_two(self):
        code, out = run(CLI, "refs", self.root, "prj_nope")
        self.assertEqual(code, 2, out)


if __name__ == "__main__":                                # pragma: no cover
    unittest.main()
