"""`okf list unconfirmed`, `okf list orphans` and `okf stats` replace a whole-bundle read.

That is what makes them worth this many tests. `jsk-bundle-auditor.md` and
`mode-gaps.md` both specify "reads every concept" to find what `unconfirmed` prints, so
a session will act on these rows instead of opening the files - and a row that is wrong,
or a row that is missing, is now invisible rather than obvious.

Three defects are pinned harder than the rest:

  - **A claim's provenance is not always the field it looks like.** A status-less bullet
    is `inferred`; a held certification's `status: active` is validity and not
    provenance. Getting either wrong means an inferred bullet reaching a resume, or a
    permanent row nobody can clear. `ProvenanceComesFromTheIdIndex` has one case per
    rule and pins the agreement with `ids.claim_status`, which is where they live.
  - **`orphans` must not report a capability missing from the vocabulary.**
    `validate_bundle.py` errors on that, and a query that repeated the finding would
    teach people the gate is optional. `MissingCapabilityIsTheGatesFinding` is the most
    important case in this file.
  - **Nothing here compiles.** `NothingCompiles` breaks `okf_compile.load` and asks all
    three anyway. A query that quietly started compiling would still pass every other
    test here and would cost a second per call, which is the whole reason the layer
    exists.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import (CLI, Q_METRICS, Q_POSTING, Q_PROJECT, Q_SKILLS, Q_VIEW,
                      QUERY_FILES, load_script, query_bundle, query_module, run)


# Every module under test is resolved per call rather than bound here - see `live()`.


def audit_module():
    return query_module("audit")


def ids_module():
    return query_module("ids")


def compiler():
    return load_script("okf_compile.py")


# --- helpers --------------------------------------------------------------------


def live():
    """The audit and its CLI, resolved now rather than at import time.

    `test_okf_write_surface.py` deletes every `jsk_okf` module from `sys.modules` - to
    prove that importing the dispatcher does not drag in the write layer - and does not
    put them back. A reference captured before that runs is a *different object* from
    the one the CLI's own lazy `from . import audit` then loads, so `filters.Bad`
    raised by one is not the class the other catches: a refusal that must exit 2
    escapes as a traceback instead, and only when the whole suite runs in one process.

    Resolving both together here means these tests always drive one generation of the
    layer. Which is also the honest reading of what they are for - they assert about
    the code on disk, not about whatever was imported first.
    """
    return audit_module(), query_module("commands")


def listed(bundle, noun, *flags):
    """One audit's Result, reached through the real parser.

    Through `build_parser` rather than a hand-built namespace, so a flag that changes
    name or gains a default cannot leave these tests asserting against a shape the CLI
    no longer produces.
    """
    module, cli = live()
    args = cli.build_parser().parse_args(["list", str(bundle), noun] + list(flags))
    return getattr(module, noun)(bundle, args)


def counted(bundle, *flags):
    module, cli = live()
    args = cli.build_parser().parse_args(["stats", str(bundle)] + list(flags))
    return module.stats(bundle, args)


def printed(*argv):
    """(exit code, output) from the query CLI in this process."""
    _, cli = live()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue()


def survey(bundle, **kwargs):
    return live()[0].Survey(bundle, **kwargs)


def write(bundle, folder, name, text):
    directory = Path(bundle) / folder if folder else Path(bundle)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")
    return directory / name


def ids_in(result):
    return [row.get("id") or row.get("name") for row in result.rows]


PROJECT = """---
type: Project
title: "{title}"
description: "A project."
{role}status: {status}
strength: {strength}
recency: {recency}
seniority: architecture-ownership
domains: [healthcare]
capabilities: [{capabilities}]
technologies: [python]
---

# The problem

Something was slow.
{bullets}"""


def project(title, status="confirmed", strength=3, recency=2024, role="principal-engineer",
            capabilities="event-driven-architecture", bullets=""):
    return PROJECT.format(title=title, status=status, strength=strength,
                          recency=recency, capabilities=capabilities,
                          role=f"role: {role}\n" if role else "",
                          bullets=bullets)


BULLETS_NO_STATUS = """
# Bullets

- Rebuilt the telemetry path end to end.
"""

# The fixture's one view, with an `include` block the case states for itself.
VIEW_WITH = """---
type: View
id: view_meridian_principal
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
budget:
  pages: 2
include:
{include}
---
"""


# A bundle with nothing wrong in it, so that "exits 0" is not being demonstrated only
# on an answer that happens to be empty for want of content.
CLEAN_FILES = (
    ("projects", "ledger.md", """---
type: Project
title: "Ledger rebuild"
description: "Reconciliation, rebuilt."
role: staff-engineer
status: confirmed
strength: 4
recency: 2025
seniority: architecture-ownership
domains: [finance]
capabilities: [event-driven-architecture]
technologies: [python]
---

# The problem

Ledger entries disagreed and nobody could say by how much.

# Bullets

- Cut reconciliation from a day to an hour across every ledger.
  metric: Reconciliation time
  status: confirmed
"""),
    ("roles", "staff-engineer.md", """---
type: Role
title: "Staff Engineer"
description: "The only role."
organisation: northbridge
start: 2021-01
state: ongoing
seniority: architecture-ownership
change: hire
status: confirmed
---
"""),
    ("organisations", "northbridge.md", """---
type: Organisation
relationship: employer
title: "Northbridge"
description: "Payments."
status: confirmed
---
"""),
    ("achievements", "metrics.md", """---
type: Metric Set
title: "Verified metrics"
status: confirmed
---

# Confirmed numbers

| Metric | Value | Project | Source | Notes |
|---|---|---|---|---|
| Reconciliation time | **a day to an hour** | [Ledger](../projects/ledger.md) | dashboard | |
"""),
    ("framework", "capability-vocabulary.md", """---
type: Vocabulary
title: "Capability vocabulary"
status: confirmed
---

# Platform

- `event-driven-architecture`
"""),
    ("tailoring/targets", "northbridge-staff.view.md", """---
type: View
id: view_northbridge_staff
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
budget:
  pages: 2
include:
  - ref: ach_projects_ledger_md_1
---
"""),
)


class Bundle(unittest.TestCase):
    """The read layer's fixture bundle, which is deliberately imperfect."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bundle = query_bundle(Path(self._tmp.name) / "bundle")

    def empty(self):
        """A bundle with the two directories that make it one, and nothing in them."""
        root = Path(self._tmp.name) / "empty"
        (root / "projects").mkdir(parents=True)
        (root / "roles").mkdir(parents=True)
        return root

    def clean(self):
        return query_bundle(Path(self._tmp.name) / "clean", files=CLEAN_FILES)


# --- okf list unconfirmed -------------------------------------------------------


class UnconfirmedClaims(Bundle):
    """Every claim that is not confirmed, and nothing that is.

    A confirmed bullet appearing here would make the queue unclearable, and an
    unconfirmed one missing would put inferred prose on a resume with nothing having
    said so - which is the failure the whole framework is built around.
    """

    def test_the_inferred_bullet_appears_with_its_own_status(self):
        rows = listed(self.bundle, "unconfirmed").rows
        found = [r for r in rows if r["id"] == "ach_projects_care_platform_md_2"]
        self.assertEqual(len(found), 1, rows)
        self.assertEqual(found[0]["status"], "inferred")
        self.assertEqual(found[0]["kind"], "bullet")
        self.assertIn("data-sovereignty", found[0]["says"])

    def test_the_confirmed_bullet_in_the_same_concept_does_not(self):
        """The claim is the atom. A concept-level answer would report both or neither."""
        self.assertNotIn("ach_projects_care_platform_md_1",
                         ids_in(listed(self.bundle, "unconfirmed")))

    def test_a_row_points_at_the_line_the_claim_is_on(self):
        """`file` is pasted into an editor. A concept-level line would open the
        frontmatter of a file whose problem is forty lines down."""
        row = [r for r in listed(self.bundle, "unconfirmed").rows
               if r["id"] == "ach_projects_care_platform_md_2"][0]
        self.assertRegex(row["file"], r"^projects/care-platform\.md:\d+$")
        line = int(row["file"].split(":")[1])
        text = (Path(self.bundle) / "projects" / "care-platform.md").read_text(
            encoding="utf-8").splitlines()
        self.assertIn("data-sovereignty", text[line - 1])

    def test_a_needs_verification_concept_appears(self):
        rows = listed(self.bundle, "unconfirmed").rows
        found = [r for r in rows if r["id"] == "prj_billing_reconciliation"]
        self.assertEqual(len(found), 1, rows)
        self.assertEqual(found[0]["status"], "needs-verification")

    def test_inferred_sorts_above_needs_verification(self):
        """mode-gaps.md's order. Inferred reads as a fact and is the dangerous kind, so
        a queue that put a known gap first would have somebody working the safe half."""
        statuses = [row["status"] for row in listed(self.bundle, "unconfirmed").rows]
        self.assertEqual(statuses, sorted(statuses, key=audit_module().UNCONFIRMED.index))
        self.assertEqual(statuses[0], "inferred")

    def test_a_skill_wears_its_concepts_provenance(self):
        """`body.SKILL_KEYS` has no `status` key, so a skill cannot carry its own. The
        Skill Set is what has to be confirmed, and every skill in it follows."""
        write(self.bundle, "skills", "competencies.md",
              Q_SKILLS.replace("status: confirmed", "status: needs-verification"))
        rows = {r["id"]: r for r in listed(self.bundle, "unconfirmed").rows}
        self.assertIn("skill_dotnet", rows)
        self.assertIn("skill_azure", rows)
        self.assertEqual(rows["skill_dotnet"]["status"], "needs-verification")

    def test_the_strongest_project_leads_its_band(self):
        """mode-gaps.md orders the band below inferred "highest-strength projects
        first", and that is the tie-break here rather than filename order."""
        write(self.bundle, "projects", "atlas.md",
              project("Atlas migration", status="needs-verification", strength=5))
        rows = [r for r in listed(self.bundle, "unconfirmed").rows
                if r["status"] == "needs-verification"]
        self.assertEqual([r["id"] for r in rows][:2],
                         ["prj_atlas", "prj_billing_reconciliation"])

    def test_a_view_is_not_a_claim(self):
        """A view makes its claim with `provenance_floor`. Reporting its own `status:`
        would put every working view in a tailoring-heavy bundle in the queue."""
        self.assertNotIn("view_meridian_principal",
                         ids_in(listed(self.bundle, "unconfirmed")))

    def test_an_engagement_is_not_a_second_row_for_its_organisation(self):
        """`eng_x` and `org_x` are one file. Two rows for it reads as two findings."""
        write(self.bundle, "organisations", "meridian-health.md",
              (Path(self.bundle) / "organisations" / "meridian-health.md")
              .read_text(encoding="utf-8").replace("status: confirmed",
                                                   "status: needs-verification"))
        rows = ids_in(listed(self.bundle, "unconfirmed"))
        self.assertIn("org_meridian_health", rows)
        self.assertNotIn("eng_meridian_health", rows)

    def test_a_metric_row_is_never_unconfirmed(self):
        """The table has no status column; a row in it is a verified number."""
        self.assertNotIn("met_tenants_onboarded",
                         ids_in(listed(self.bundle, "unconfirmed")))

    def test_status_narrows_on_the_claims_own_provenance(self):
        """`--status inferred` on any other listing means "in an inferred concept". Here
        it has to mean the claim, or it hides every inferred bullet in a confirmed
        project - the exact rows this command exists for."""
        rows = listed(self.bundle, "unconfirmed", "--status", "inferred").rows
        self.assertEqual([r["id"] for r in rows], ["ach_projects_care_platform_md_2"])

    def test_a_metadata_filter_narrows_to_the_concept_it_sits_in(self):
        rows = listed(self.bundle, "unconfirmed", "--strength", "4+").rows
        self.assertEqual([r["id"] for r in rows], ["ach_projects_care_platform_md_2"])

    def test_a_status_the_record_does_not_recognise_is_reported_not_dropped(self):
        """`validate_bundle.py` is what refuses `status: verified`. A query that
        silently omitted the claim wearing it would hide the one file most in need of
        attention - and the summary has to read as a finding about the bundle rather
        than as a bug in the command."""
        write(self.bundle, "projects", "atlas.md",
              project("Atlas migration", status="verified"))
        result = listed(self.bundle, "unconfirmed")
        rows = {r["id"]: r for r in result.rows}
        self.assertEqual(rows["prj_atlas"]["status"], "verified")
        self.assertNotIn("- ,", result.summary)
        self.assertIn("does not recognise", result.summary)

    def test_an_unrecognised_status_sorts_below_the_two_that_are(self):
        write(self.bundle, "projects", "atlas.md",
              project("Atlas migration", status="verified", strength=5))
        statuses = [r["status"] for r in listed(self.bundle, "unconfirmed").rows]
        self.assertEqual(statuses[-1], "verified")

    def test_nothing_unconfirmed_says_so_rather_than_nothing(self):
        result = listed(self.clean(), "unconfirmed")
        self.assertEqual(result.rows, [])
        self.assertIn("confirmed", result.summary)

    def test_the_answer_says_the_archive_was_not_read(self):
        """An empty answer with an invisible boundary reads as "there is nothing there"."""
        self.assertTrue(any("archive" in note
                            for note in listed(self.bundle, "unconfirmed").notes))
        self.assertFalse(any("archive was not read" in note for note in
                             listed(self.bundle, "unconfirmed", "--archive").notes))


class ProvenanceComesFromTheIdIndex(Bundle):
    """A claim's status is not always the field it looks like, and `ids.claim_status`
    is where the three rules live.

    This module used to apply them itself, from `Located.detail` and the owning
    concept, because `ids` applied one fallback to every kind. The copy is gone and
    these are what is left: one case per rule, asserted against a row of this command's
    own output, plus the agreement in both directions. A change to either module fails
    here rather than quietly moving what the queue reports - and the value it decides
    is the one `provenance_floor` gates a resume on.
    """

    def bullet_with_no_status(self):
        write(self.bundle, "projects", "telemetry.md",
              project("Telemetry rebuild", status="confirmed", strength=4,
                      bullets=BULLETS_NO_STATUS))
        return "ach_projects_telemetry_md_1"

    def test_a_bullet_with_no_status_of_its_own_is_inferred(self):
        """`okf_compile.bullets()` defaults it that way. Reading it as its concept's
        status would call a claim signed off that the renderer then withholds under
        `provenance_floor: confirmed` - the one direction that must never be wrong."""
        wanted = self.bullet_with_no_status()
        rows = listed(self.bundle, "unconfirmed").rows
        found = [r for r in rows if r["id"] == wanted]
        self.assertEqual(len(found), 1, rows)
        self.assertEqual(found[0]["status"], "inferred")

    def test_the_id_index_says_the_same(self):
        wanted = self.bullet_with_no_status()
        self.assertEqual(ids_module().index(self.bundle)[wanted].status, "inferred")

    def test_an_active_certification_is_not_an_unconfirmed_claim(self):
        """A `# Held` item's `status:` is `active`/`expired` - whether the certification
        is current, not whether anybody signed off on the claim. Reading it as
        provenance puts a row in this queue that confirming cannot clear."""
        self.assertNotIn("cred_cloud_certifications_1",
                         ids_in(listed(self.bundle, "unconfirmed")))

    def test_the_id_index_does_not_read_validity_as_provenance(self):
        located = ids_module().index(self.bundle)["cred_cloud_certifications_1"]
        self.assertEqual(located.status, "confirmed")
        self.assertEqual(located.detail.get("status"), "active")

    def test_every_claims_provenance_is_the_id_indexs(self):
        """The agreement itself, over the whole fixture. `Survey.provenance` is now
        `Located.status` and this is what keeps it honest if anyone re-derives it."""
        self.bullet_with_no_status()
        found = survey(self.bundle)
        for located, status, _ in found.claims():
            with self.subTest(id=located.id):
                self.assertEqual(status, located.status)

    def test_a_provenance_word_the_record_uses_is_what_is_reported(self):
        """Every row's status is one of the three the record recognises, or a value
        somebody actually wrote. `active` reaching this column would mean validity had
        been read as provenance somewhere upstream."""
        self.bullet_with_no_status()
        for row in listed(self.bundle, "unconfirmed").rows:
            self.assertNotEqual(row["status"], "active")


# --- okf list orphans -----------------------------------------------------------


class MissingCapabilityIsTheGatesFinding(Bundle):
    """The boundary, and the most important case in this file.

    A capability a project carries that the vocabulary does not list is an **error**
    from `okf validate`, because the scorer compares exact strings and an unlisted term
    silently matches nothing. If `orphans` reported it too, the command that exits 0
    would become the one people read and the gate would look optional.
    """

    def setUp(self):
        super().setUp()
        write(self.bundle, "projects", "care-platform.md", Q_PROJECT.replace(
            "capabilities: [ai-platform-architecture, event-driven-architecture]",
            "capabilities: [ai-platform-architecture, event-driven-architecture, "
            "quantum-teleportation]"))

    def test_the_gate_reports_it(self):
        code, out = run(CLI, "validate", str(self.bundle))
        self.assertEqual(code, 1, out)
        self.assertIn("quantum-teleportation", out)
        self.assertIn("capability-vocabulary.md", out)

    def test_orphans_does_not(self):
        result = listed(self.bundle, "orphans")
        self.assertNotIn("quantum-teleportation", ids_in(result))
        for row in result.rows:
            self.assertNotIn("quantum-teleportation", row["nothing"])

    def test_orphans_still_reports_the_other_direction(self):
        """The half nothing else covers stays reported - the boundary is a boundary,
        not a switch that turned the check off."""
        self.assertIn("data-sovereignty", ids_in(listed(self.bundle, "orphans")))


class Orphans(Bundle):
    """What nothing points at. Every check here is one no gate makes."""

    def test_an_uncited_metric_is_reported(self):
        rows = {r["name"]: r for r in listed(self.bundle, "orphans").rows}
        self.assertIn("met_tenants_onboarded", rows)
        self.assertEqual(rows["met_tenants_onboarded"]["kind"], "metric")
        self.assertIn("Tenants onboarded", rows["met_tenants_onboarded"]["nothing"])

    def test_a_cited_metric_is_not(self):
        self.assertNotIn("met_event_propagation_latency",
                         ids_in(listed(self.bundle, "orphans")))

    def test_an_unused_vocabulary_term_is_reported(self):
        rows = {r["name"]: r for r in listed(self.bundle, "orphans").rows}
        self.assertIn("data-sovereignty", rows)
        self.assertEqual(rows["data-sovereignty"]["kind"], "capability")
        self.assertEqual(rows["data-sovereignty"]["file"],
                         "framework/capability-vocabulary.md")

    def test_the_underscored_vocabulary_spelling_is_read_and_named(self):
        """`validate_bundle.py` falls back to `capability_vocabulary.md`, so a bundle
        written against it must be read - and the row has to name the file that is
        actually there. A `file` column naming a file the bundle does not have is worse
        than no row."""
        framework = Path(self.bundle) / "framework"
        (framework / "capability-vocabulary.md").rename(
            framework / "capability_vocabulary.md")
        rows = {r["name"]: r for r in listed(self.bundle, "orphans").rows}
        self.assertIn("data-sovereignty", rows)
        self.assertEqual(rows["data-sovereignty"]["file"],
                         "framework/capability_vocabulary.md")

    def test_no_vocabulary_file_reports_no_capability_at_all(self):
        """The fallback both gates make: a bundle scaffolded with its examples inside a
        fence yields no vocabulary, and a fresh bundle is not a bundle full of
        orphans."""
        (Path(self.bundle) / "framework" / "capability-vocabulary.md").unlink()
        self.assertEqual([r for r in listed(self.bundle, "orphans").rows
                          if r["kind"] == "capability"], [])

    def test_a_carried_vocabulary_term_is_not(self):
        self.assertNotIn("event-driven-architecture", ids_in(listed(self.bundle, "orphans")))

    def bullets_reported(self, include):
        """The bullets `orphans` reports, with the bundle's one view rewritten.

        The view is written whole rather than patched, so these cases assert about a
        selection shape they state themselves. A test that string-replaced a line of
        the shared fixture asserted nothing the moment the fixture's view changed
        shape - which is how the narrowing bug below survived its first review.
        """
        write(self.bundle, "tailoring/targets", "meridian-principal.view.md",
              VIEW_WITH.format(include=include))
        return [r["name"] for r in listed(self.bundle, "orphans").rows
                if r["kind"] == "bullet"]

    def test_a_bullet_no_view_names_is_reported(self):
        rows = {r["name"]: r for r in listed(self.bundle, "orphans").rows}
        self.assertIn("ach_projects_care_platform_md_2", rows)
        self.assertEqual(rows["ach_projects_care_platform_md_2"]["kind"], "bullet")

    def test_a_bullet_a_view_names_is_not(self):
        self.assertNotIn("ach_projects_care_platform_md_1",
                         ids_in(listed(self.bundle, "orphans")))

    def test_an_owner_included_whole_covers_every_bullet_under_it(self):
        """`resolve.achievements_of` renders every achievement of an included owner
        when that owner's entry does not narrow them, so a view including `eng_x` puts
        them all on the page. Reporting them would be a page of false findings against
        exactly the claims somebody just tailored."""
        self.assertEqual(self.bullets_reported("  - ref: eng_meridian_health"), [])

    def test_the_project_id_covers_them_too(self):
        self.assertEqual(self.bullets_reported("  - ref: prj_care_platform"), [])

    def test_an_owner_that_chooses_between_bullets_covers_only_those(self):
        """The other direction, and the one that matters more: an `achievements` list
        is how a tailored view says "this bullet and not that one". Treating the owner
        include as wholesale would hide the bullet nothing renders, which is the whole
        finding."""
        reported = self.bullets_reported(
            "  - ref: eng_meridian_health\n"
            "    achievements: [ach_projects_care_platform_md_1]")
        self.assertEqual(reported, ["ach_projects_care_platform_md_2"])

    def test_a_bullet_named_inside_an_engagements_achievements_is_not(self):
        reported = self.bullets_reported(
            "  - ref: eng_meridian_health\n"
            "    achievements: [ach_projects_care_platform_md_2]")
        self.assertNotIn("ach_projects_care_platform_md_2", reported)

    def test_a_bare_string_ref_is_an_owner_included_whole(self):
        """`resolve` builds its selection only from mappings, so a bare string reaches
        `achievements_of` as no selection at all."""
        self.assertEqual(self.bullets_reported("  - eng_meridian_health"), [])

    def test_no_views_at_all_checks_no_bullet(self):
        """Before a bundle's first tailoring run "no view includes it" is true of every
        bullet, and a page of those rows says only that nobody has tailored yet."""
        (Path(self.bundle) / "tailoring" / "targets"
         / "meridian-principal.view.md").unlink()
        result = listed(self.bundle, "orphans")
        self.assertEqual([r for r in result.rows if r["kind"] == "bullet"], [])
        self.assertTrue(any("no views" in note for note in result.notes), result.notes)

    def test_a_project_with_no_role_is_reported(self):
        rows = {r["name"]: r for r in listed(self.bundle, "orphans").rows}
        self.assertIn("prj_billing_reconciliation", rows)
        self.assertEqual(rows["prj_billing_reconciliation"]["kind"], "project")
        self.assertIn("role:", rows["prj_billing_reconciliation"]["nothing"])

    def test_a_project_with_a_role_is_not(self):
        self.assertNotIn("prj_care_platform", ids_in(listed(self.bundle, "orphans")))

    def test_rows_are_grouped_by_kind(self):
        kinds = [audit_module().ORPHAN_KINDS.index(row["kind"])
                 for row in listed(self.bundle, "orphans").rows]
        self.assertEqual(kinds, sorted(kinds))

    def test_a_clean_bundle_is_reported_clean(self):
        result = listed(self.clean(), "orphans")
        self.assertEqual(result.rows, [], result.rows)
        self.assertIn("nothing orphaned", result.summary)

    def test_a_selection_filter_is_refused_by_name(self):
        """Silently ignoring it would make a narrowed question answer "nothing is
        orphaned" when the answer is "you did not ask about it"."""
        code, out = printed("list", self.bundle, "orphans", "--capability", "x")
        self.assertEqual(code, 2, out)
        self.assertIn("--capability", out)
        self.assertIn("no selection filters", out)


class OrphanedPostings(Bundle):
    """A posting with nothing beside it is a posting nobody worked.

    `bundle-spec.md` puts the assessment and the view next to it, and `validate_bundle`
    checks the *archive's* companions rather than a working copy's - so this half is
    nobody else's.
    """

    def test_a_posting_with_both_companions_is_not_reported(self):
        self.assertNotIn("meridian-principal.posting",
                         ids_in(listed(self.bundle, "orphans")))

    def test_a_posting_with_neither_names_both(self):
        write(self.bundle, "tailoring/targets", "atlas-staff.posting.md", Q_POSTING)
        rows = {r["name"]: r for r in listed(self.bundle, "orphans").rows}
        self.assertIn("atlas-staff.posting", rows)
        self.assertEqual(rows["atlas-staff.posting"]["kind"], "posting")
        self.assertIn("atlas-staff.gaps.md", rows["atlas-staff.posting"]["nothing"])
        self.assertIn("atlas-staff.view.md", rows["atlas-staff.posting"]["nothing"])

    def test_a_posting_missing_one_companion_names_only_that_one(self):
        write(self.bundle, "tailoring/targets", "atlas-staff.posting.md", Q_POSTING)
        write(self.bundle, "tailoring/targets", "atlas-staff.gaps.md",
              "---\ntype: Gap Assessment\ntitle: \"Atlas\"\n---\n")
        row = {r["name"]: r for r in listed(self.bundle, "orphans").rows
               }["atlas-staff.posting"]
        self.assertNotIn("gaps.md", row["nothing"])
        self.assertIn("atlas-staff.view.md", row["nothing"])

    def test_a_frozen_posting_is_never_reported(self):
        """The archived copy beside a sent application has no `.gaps.md` in this
        fixture, and it may not be edited. A row directing somebody there directs them
        to edit the record of what was already posted."""
        names = ids_in(listed(self.bundle, "orphans", "--archive"))
        self.assertNotIn("2025-11-03-kestrel-staff.posting", names)


# --- okf stats ------------------------------------------------------------------


class Stats(Bundle):
    """What the bundle holds, counted - and counted by the thing that can see a
    dropped type."""

    def test_the_type_counts_are_the_census(self):
        """**This assertion is the contract, not a sanity check.**

        `okf stats` counts types off its own walk rather than calling
        `okf_compile.census()`, because calling it beside the survey meant a second
        435-file walk for a number the survey already had - three times a full compile
        to produce it. What that bought was the wording of a docstring; this test is
        what buys the property, and it is now **the only thing holding the two
        together**.

        Why the property matters more than a count usually does: `census()` exists
        because a compiler that drops a whole type cannot be caught by any check
        written about the survivors - every one of them iterates a list that is empty,
        and passes. `views` was a hardcoded `[]` for months for exactly that reason.
        So if this fails, do not adjust the expectation: the walk's boundary has moved
        away from `concepts(root, tailoring="all")`' and the count has stopped being
        the thing that can see a type vanish.
        """
        self.assertEqual(counted(self.bundle).extra["census"],
                         compiler().census(str(self.bundle)))

    def test_the_concept_section_totals_the_census(self):
        result = counted(self.bundle)
        section = [r for r in result.rows if r["section"] == "concepts"][0]
        self.assertEqual(section["concepts"], sum(result.extra["census"].values()))
        self.assertEqual(section["types"], len(result.extra["census"]))

    def test_it_counts_what_the_bundle_holds(self):
        section = [r for r in counted(self.bundle).rows if r["section"] == "record"][0]
        self.assertEqual(section["projects"], 2)
        self.assertEqual(section["bullets"], 2)
        self.assertEqual(section["skills"], 2)
        self.assertEqual(section["metrics"], 2)
        self.assertEqual(section["views"], 1)
        self.assertEqual(section["postings"], 1)

    def test_applications_are_counted_even_though_the_archive_is_not_read(self):
        """"How many have I sent" is the one question whose answer lives entirely in
        the archive. Reporting 0 because the archive was skipped is a lie, not a
        boundary - the notes say the difference."""
        section = [r for r in counted(self.bundle).rows if r["section"] == "record"][0]
        self.assertEqual(section["applications"], 1)
        self.assertTrue(any("applications are counted" in note
                            for note in counted(self.bundle).notes))

    def test_the_provenance_mix_splits_concepts_from_claims(self):
        section = [r for r in counted(self.bundle).rows
                   if r["section"] == "provenance"][0]
        self.assertEqual(section["inferred"], 1)
        self.assertEqual(section["needs-verification"], 1)
        self.assertEqual(section["concepts"] + section["claims"],
                         section["confirmed"] + section["inferred"]
                         + section["needs-verification"])

    def test_the_mix_matches_what_unconfirmed_lists(self):
        """The reason all three live in one file. Two numbers that disagree about how
        much of a record is unconfirmed both look fine alone."""
        section = [r for r in counted(self.bundle).rows
                   if r["section"] == "provenance"][0]
        rows = listed(self.bundle, "unconfirmed").rows
        self.assertEqual(section["inferred"] + section["needs-verification"], len(rows))

    def test_the_span_runs_from_the_earliest_role_to_the_latest_project(self):
        section = [r for r in counted(self.bundle).rows if r["section"] == "span"][0]
        self.assertEqual(section["from"], "2019-04")
        self.assertEqual(section["to"], "2024")
        self.assertEqual(section["years"], 5)

    def test_a_capability_on_three_projects_is_a_through_line(self):
        """`bundle-spec.md`: values on three or more projects are the ones safe to claim
        as a through-line in a summary. That sentence is the only reason the histogram
        is worth printing."""
        write(self.bundle, "projects", "atlas.md",
              project("Atlas migration", capabilities="event-driven-architecture"))
        histogram = {e["term"]: e for e in counted(self.bundle).extra["capabilities"]}
        self.assertEqual(histogram["event-driven-architecture"]["projects"], 3)
        self.assertTrue(histogram["event-driven-architecture"]["through_line"])
        section = [r for r in counted(self.bundle).rows
                   if r["section"] == "capabilities"][0]
        self.assertIn("event-driven-architecture", section["through_lines"])

    def test_a_capability_on_two_projects_is_not(self):
        write(self.bundle, "projects", "atlas.md",
              project("Atlas migration", capabilities="ai-platform-architecture"))
        histogram = {e["term"]: e for e in counted(self.bundle).extra["capabilities"]}
        self.assertEqual(histogram["ai-platform-architecture"]["projects"], 2)
        self.assertFalse(histogram["ai-platform-architecture"]["through_line"])
        section = [r for r in counted(self.bundle).rows
                   if r["section"] == "capabilities"][0]
        self.assertNotIn("ai-platform-architecture", section["through_lines"])

    def test_the_histogram_counts_projects_and_not_postings(self):
        """A posting's requirements are what somebody *asked for*. Counting them would
        turn three advertisements into a through-line the record cannot support."""
        write(self.bundle, "tailoring/targets", "atlas-staff.posting.md", Q_POSTING)
        write(self.bundle, "tailoring/targets", "kestrel-staff.posting.md", Q_POSTING)
        histogram = {e["term"]: e for e in counted(self.bundle).extra["capabilities"]}
        self.assertEqual(histogram["ai-platform-architecture"]["projects"], 1)

    def test_json_carries_the_census_and_the_histogram_structured(self):
        code, out = printed("stats", self.bundle, "--json")
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertEqual(doc["census"], compiler().census(str(self.bundle)))
        terms = {entry["term"]: entry for entry in doc["capabilities"]}
        self.assertEqual(terms["event-driven-architecture"]["projects"], 2)
        self.assertIn("through_line", terms["event-driven-architecture"])

    def test_the_human_form_prints_a_stanza_per_section(self):
        code, out = printed("stats", self.bundle)
        self.assertEqual(code, 0, out)
        for heading in ("CONCEPTS", "PROVENANCE", "RECORD", "SPAN", "CAPABILITIES"):
            self.assertIn(heading, out)

    def test_the_counts_still_agree_with_a_broken_concept_in_the_bundle(self):
        """The equality has to hold on the bundles these commands are actually run on,
        which includes one mid-edit. Both sides drop a concept whose frontmatter will
        not parse; if only one of them did, the counts would differ by one and the
        difference would look like a dropped type."""
        write(self.bundle, "projects", "half-typed.md",
              "---\ntype: Project\ntitle: \"unclosed\nstrength: [\n---\n\n# The problem\n")
        self.assertEqual(counted(self.bundle).extra["census"],
                         compiler().census(str(self.bundle)))

    def test_the_counts_still_agree_with_the_archive_read(self):
        """`--archive` widens the provenance mix and must not widen the type counts:
        `concepts()` excludes `tailoring/applications/` and this is its number."""
        self.assertEqual(counted(self.bundle, "--archive").extra["census"],
                         compiler().census(str(self.bundle)))

    def test_a_narrow_survey_refuses_to_produce_type_counts(self):
        """`census()` walks `tailoring/`. A survey that did not would undercount by
        every posting and assessment in the bundle with nothing in the output to say
        so - the failure `walk.py`'s comment on that knob warns about - so it is
        refused rather than answered."""
        with self.assertRaises(ValueError):
            survey(self.bundle).census()


# --- the two rules the whole layer holds ----------------------------------------


class ExitCodes(Bundle):
    """Always 0. An inferred claim is a legitimate state, not a finding, and a command
    that exited 1 on one would read as a failed check - which is how somebody comes to
    clear the queue by deleting rather than by asking."""

    def check(self, bundle):
        for argv in (("list", bundle, "unconfirmed"), ("list", bundle, "orphans"),
                     ("stats", bundle)):
            code, out = printed(*argv)
            self.assertEqual(code, 0, f"{argv}\n{out}")

    def test_a_bundle_with_findings_still_exits_zero(self):
        self.check(self.bundle)

    def test_a_bundle_with_nothing_wrong_exits_zero(self):
        self.check(self.clean())

    def test_an_empty_bundle_exits_zero(self):
        self.check(self.empty())

    def test_json_exits_zero_too(self):
        for argv in (("list", self.bundle, "unconfirmed", "--json"),
                     ("list", self.bundle, "orphans", "--json"),
                     ("stats", self.bundle, "--json")):
            code, out = printed(*argv)
            self.assertEqual(code, 0, out)
            json.loads(out)

    def test_the_real_cli_agrees(self):
        """In-process is what the rest of this file asserts against; once through the
        installed entry point, because that is what a session actually runs."""
        for argv in (("list", str(self.bundle), "unconfirmed"),
                     ("list", str(self.bundle), "orphans"),
                     ("stats", str(self.bundle))):
            code, out = run(CLI, *argv)
            self.assertEqual(code, 0, out)


class NothingCompiles(Bundle):
    """`okf_compile.load()` is what these commands exist not to pay for.

    A query that quietly started compiling would pass every other test in this file and
    cost a second and thirty kilobytes per call - and would refuse to answer about a
    bundle that is mid-edit, which is exactly when the question gets asked.
    """

    def setUp(self):
        super().setUp()
        compiled = compiler()
        original = compiled.load
        self.addCleanup(setattr, compiled, "load", original)

        def refuse(*args, **kwargs):
            raise AssertionError("a query compiled the bundle")

        compiled.load = refuse

    def test_unconfirmed_still_answers(self):
        self.assertTrue(listed(self.bundle, "unconfirmed").rows)

    def test_orphans_still_answers(self):
        self.assertTrue(listed(self.bundle, "orphans").rows)

    def test_stats_still_answers(self):
        self.assertTrue(counted(self.bundle).rows)

    def test_the_type_counts_still_agree_with_a_broken_compile(self):
        """The contract holds on a bundle `okf compile` would refuse, which is the
        practical point of the whole layer. `census()` builds no record and does not
        reach `load()`, so the comparison is still meaningful with `load` broken - and
        `okf stats` reaches neither."""
        self.assertEqual(counted(self.bundle).extra["census"],
                         compiler().census(str(self.bundle)))


class MidEdit(Bundle):
    """The question gets asked while a bundle is being edited, which is when a compile
    would refuse to answer it."""

    def test_a_concept_with_broken_yaml_does_not_take_the_answer_down(self):
        write(self.bundle, "projects", "half-typed.md",
              "---\ntype: Project\ntitle: \"unclosed\nstrength: [\n---\n\n# The problem\n")
        for argv in (("list", self.bundle, "unconfirmed"),
                     ("list", self.bundle, "orphans"), ("stats", self.bundle)):
            code, out = printed(*argv)
            self.assertEqual(code, 0, f"{argv}\n{out}")

    def test_a_project_naming_a_role_that_does_not_exist_still_answers(self):
        """`build_projects` raises on this. A query must not, because a half-finished
        edit is the state the query is for."""
        write(self.bundle, "projects", "atlas.md",
              project("Atlas migration", role="a-role-nobody-wrote"))
        self.assertNotIn("prj_atlas", ids_in(listed(self.bundle, "orphans")))
        code, out = printed("stats", self.bundle)
        self.assertEqual(code, 0, out)


class SurveyReadsWhatTheFoundationHides(Bundle):
    """Two things `Survey` has to go and get, because a default hides them.

    Both were live defects caught by measurement rather than by reading, and both fail
    the same silent way - the check runs, finds nothing, and passes.
    """

    def test_the_walk_default_hides_every_posting(self):
        """`walk`'s `tailoring` defaults to "views", which skips `*.posting.md` under
        `tailoring/targets/` - where every posting lives. This is the defect that
        shipped: the companion check read the main walk, found nothing on every real
        bundle, and passed."""
        self.assertEqual(
            [c.rel for c in survey(self.bundle).by_type.get("Job Posting", ())], [])

    def test_a_narrow_survey_refuses_to_answer_about_postings(self):
        """So the guard is in `postings()` rather than in a comment: the lookup is only
        right on a `tailoring="all"` survey, and being wrong about it is silence."""
        with self.assertRaises(ValueError):
            survey(self.bundle).postings()

    def test_a_full_survey_finds_them(self):
        self.assertIn("tailoring/targets/meridian-principal.posting.md",
                      [c.rel for c in survey(self.bundle, tailoring="all").postings()])

    def test_an_engagement_id_comes_from_the_roles_that_name_a_company(self):
        """`ids.of()` mints no `eng_`: an engagement exists for an organisation a role
        points at and for no other. Deriving it from the Organisation instead would
        offer `eng_kestrel_systems` for a prospect the record has no engagement for -
        and would silently break the bullet-coverage check when it moved."""
        located = survey(self.bundle).located
        self.assertIn("eng_meridian_health", located)
        self.assertIn("org_kestrel_systems", located)
        self.assertNotIn("eng_kestrel_systems", located)

    def test_an_archived_row_says_it_may_not_be_edited(self):
        """One sentence, from `render.FROZEN_NOTE`, because it is the only thing between
        a caller and editing the record of what was already posted - and a person who
        learns it from one command has to recognise it in the next.

        The claim has to be a real one: the frozen `.view.md` beside a sent application
        mints a `view_` id, which is not a provenance kind, so a `# Bullets` block is
        written into the archive's own application file - which `walk.Scope.frozen` does
        *not* call frozen, since its timeline is appended to while the process is live.
        So the row that must carry the note is a bullet in a frozen companion.
        """
        render = query_module("render")
        write(self.bundle, "tailoring/applications/2025",
              "2025-11-03-kestrel-staff.gaps.md", project(
                  "Frozen work", status="inferred", role=None,
                  bullets="\n# Bullets\n\n- Something drafted and then sent.\n"))
        result = listed(self.bundle, "unconfirmed", "--archive")
        frozen = [r for r in result.rows if r.get("frozen")]
        self.assertTrue(frozen, result.rows)
        self.assertIn(render.FROZEN_NOTE, result.notes)

    def test_no_archived_row_means_no_such_note(self):
        self.assertNotIn(query_module("render").FROZEN_NOTE,
                         listed(self.bundle, "unconfirmed", "--archive").notes)

    def test_the_survey_agrees_with_the_index_it_does_not_call(self):
        """`Survey` assembles its ids from `ids.of` + `engagements_of` + `metrics`
        rather than calling `index()`, because it is already walking. This is what
        stops the two drifting apart."""
        self.assertEqual(set(survey(self.bundle).located),
                         set(ids_module().index(self.bundle)))


class FixtureGuards(unittest.TestCase):
    """The fixture is deliberately imperfect, and these tests read it as evidence.

    A fixture quietly cleaned up would make half of this file assert nothing while
    still passing, so the imperfections are pinned where they are declared.
    """

    def test_the_fixture_holds_one_confirmed_and_one_inferred_bullet(self):
        self.assertIn("status: confirmed", Q_PROJECT)
        self.assertIn("status: inferred", Q_PROJECT)

    def test_the_fixture_holds_a_metric_no_bullet_cites(self):
        self.assertIn("Tenants onboarded", Q_METRICS)
        self.assertNotIn("metric: Tenants onboarded", Q_PROJECT)

    def test_the_fixture_view_leaves_the_second_bullet_rendered_by_nothing(self):
        """The imperfection behind `test_a_bullet_no_view_names_is_reported`. If the
        fixture's view ever starts naming the second bullet - or including its owner
        without narrowing - that case passes while asserting nothing."""
        self.assertIn("ach_projects_care_platform_md_1", Q_VIEW)
        self.assertNotIn("ach_projects_care_platform_md_2", Q_VIEW)

    def test_the_fixture_gives_its_posting_both_companions(self):
        beside = {name for folder, name, _ in QUERY_FILES
                  if folder == "tailoring/targets"}
        self.assertIn("meridian-principal.gaps.md", beside)
        self.assertIn("meridian-principal.view.md", beside)


if __name__ == "__main__":                                 # pragma: no cover
    unittest.main()
