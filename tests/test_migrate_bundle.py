"""migrate_bundle.py must move an old bundle forward without inventing anything.

The migration writes into somebody's career record, so the tests here care less about
"did it change the file" than about two narrower promises: it never fabricates a posting
it could not find, and it never claims a late snapshot was taken at submission.
"""
import re
import tempfile
import unittest
from pathlib import Path

from fixtures import INIT_BUNDLE, MIGRATE_BUNDLE, VALIDATE_BUNDLE, load_script, run

CURRENT = load_script(MIGRATE_BUNDLE).CURRENT_REVISION

TARGET = """---
type: Job Target
title: "Kestrel Health - Principal Platform Architect"
description: "Own the clinical integration platform."
timestamp: 2026-08-26T00:00:00Z
status: confirmed
company: "Kestrel Health"
role: "Principal Platform Architect"
required_capabilities: [integration-architecture]
required_technologies: [azure]
domains: [healthcare]
seniority_sought: architecture-ownership
---

# Posting

Own the clinical integration platform across 60 sites.
"""

APPLICATION = """---
type: Application
title: "Kestrel Health - Principal Platform Architect"
description: "Submitted via Workday."
timestamp: 2026-08-26T00:00:00Z
status: confirmed
company: "Kestrel Health"
role: "Principal Platform Architect"
target: "../targets/kestrel.md"
record: "kestrel.resume.json"
submitted: 2020-03-04
outcome: pending
---

# What was sent

The ATS variant.
"""

ORPHAN = """---
type: Application
title: "Vanished Co - Staff Architect"
description: "No target file was ever written."
timestamp: 2026-05-02T00:00:00Z
status: confirmed
company: "Vanished Co"
role: "Staff Architect"
submitted: 2026-05-02
outcome: rejected-at-screen
---

# Outcome

Rejected at screen.
"""


class MigrateCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_bundle(self):
        root = self.tmp / "my-career"
        code, out = run(INIT_BUNDLE, root, "--name", "Test Person")
        self.assertEqual(code, 0, out)
        return root

    def make_r1(self, with_target=True, with_orphan=False):
        """A bundle in the pre-stamp shape: no okf_bundle, applications carry `target:`."""
        root = self.make_bundle()
        index = root / "index.md"
        index.write_text(
            re.sub(r"okf_bundle: \d+\n", "", index.read_text(encoding="utf-8")),
            encoding="utf-8")
        if with_target:
            (root / "tailoring/targets/kestrel.md").write_text(TARGET, encoding="utf-8")
        (root / "tailoring/applications/kestrel.md").write_text(APPLICATION, encoding="utf-8")
        if with_orphan:
            (root / "tailoring/applications/vanished-co.md").write_text(ORPHAN, encoding="utf-8")
        return root

    def archived(self, root, name):
        """One file in the archive, wherever revision 7 filed it.

        The tests below are about what the earlier revision steps write, not about
        which year directory it ends up in - that has its own case. Looking it up
        keeps them saying the one thing each was written to say.
        """
        found = sorted((root / "tailoring/applications").rglob(name))
        self.assertEqual(len(found), 1, f"{name}: {found}")
        return found[0]

    def frozen(self, root):
        return self.archived(root, "kestrel.target.md")

    # ------------------------------------------------------------------ shape

    def test_new_bundle_is_born_current(self):
        root = self.make_bundle()
        code, out = run(MIGRATE_BUNDLE, root)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to do", out)

    def test_unstamped_bundle_reads_as_revision_1(self):
        root = self.make_r1()
        code, out = run(MIGRATE_BUNDLE, root)
        self.assertEqual(code, 1, out)
        self.assertIn("bundle revision: 1", out)

    def test_not_a_bundle_is_a_usage_error(self):
        code, out = run(MIGRATE_BUNDLE, self.tmp / "nowhere")
        self.assertEqual(code, 2, out)

    # -------------------------------------------------------------- dry run

    def test_dry_run_writes_nothing(self):
        root = self.make_r1()
        before = (root / "tailoring/applications/kestrel.md").read_text(encoding="utf-8")
        code, out = run(MIGRATE_BUNDLE, root)
        self.assertEqual(code, 1, out)
        self.assertIn("DRY RUN", out)
        self.assertEqual(list((root / "tailoring/applications").rglob("*.target.md")), [])
        self.assertEqual((root / "tailoring/applications/kestrel.md")
                         .read_text(encoding="utf-8"), before)

    # ---------------------------------------------------------------- apply

    def test_apply_freezes_the_posting_beside_the_application(self):
        root = self.make_r1()
        code, out = run(MIGRATE_BUNDLE, root, "--apply")
        self.assertIn("MIGRATED to revision", out)
        self.assertTrue(self.frozen(root).exists())
        frozen = self.frozen(root).read_text(encoding="utf-8")
        self.assertIn("type: Source Document", frozen)
        self.assertIn("Own the clinical integration platform across 60 sites.", frozen)

    def test_a_late_snapshot_says_so(self):
        """The whole point. A copy taken today is not a copy taken at submission."""
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        frozen = self.frozen(root).read_text(encoding="utf-8")
        # The banner tells the reader how to promote it later, so it mentions
        # `status: confirmed` in prose. Only the frontmatter settles what it IS.
        head = frozen.split("\n---\n", 1)[0]
        self.assertIn("snapshot_late: true", head)
        self.assertIn("status: needs-verification", head)
        self.assertNotIn("status: confirmed", head)
        self.assertIn("not captured at submission", frozen)
        self.assertIn("submitted on 2020-03-04", frozen)

    def test_pointers_name_which_copy_they_mean(self):
        """`posting:` is the frozen companion beside it; `target_working_copy:` is the
        live posting, which r6 moved onto `.posting.md` and r7 put two levels up."""
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        app = self.archived(root, "kestrel.md").read_text(encoding="utf-8")
        self.assertIn('posting: "kestrel.target.md"', app)
        self.assertIn('target_working_copy: "../../targets/kestrel.posting.md"', app)
        self.assertNotRegex(app, r"(?m)^target:")

    def test_the_working_copy_survives(self):
        """Nothing is deleted - the next application to this company starts from it.

        r6 marks it superseded and touches nothing else: the advertisement is still
        there word for word, which is the whole reason it was not removed.
        """
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        working = root / "tailoring/targets/kestrel.md"
        self.assertTrue(working.exists())
        text = working.read_text(encoding="utf-8")
        self.assertIn("superseded_by: kestrel.posting.md", text)
        self.assertEqual(text.replace("superseded_by: kestrel.posting.md\n", ""), TARGET)

    def test_index_is_stamped(self):
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        self.assertIn(f"okf_bundle: {CURRENT}", (root / "index.md").read_text(encoding="utf-8"))

    def test_running_twice_changes_nothing(self):
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        after = self.frozen(root).read_text(encoding="utf-8")
        code, out = run(MIGRATE_BUNDLE, root, "--apply")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to do", out)
        self.assertEqual(self.frozen(root).read_text(encoding="utf-8"), after)

    # -------------------------------------------------- what it must not do

    def test_a_missing_posting_is_reported_not_invented(self):
        root = self.make_r1(with_orphan=True)
        code, out = run(MIGRATE_BUNDLE, root, "--apply")
        self.assertEqual(code, 1, out)
        self.assertIn("cannot invent one", out)
        self.assertIn("vanished-co.md", out)
        self.assertFalse((root / "tailoring/applications/vanished-co.target.md").exists())

    def test_no_dangling_posting_pointer_is_written(self):
        """A `posting:` naming a file the migration just said it could not create would
        read as if the freeze had resolved. Regression: it used to write one."""
        root = self.make_r1(with_orphan=True)
        run(MIGRATE_BUNDLE, root, "--apply")
        orphan = self.archived(root, "vanished-co.md").read_text(encoding="utf-8")
        self.assertNotIn("posting:", orphan)

    def test_migrated_bundle_still_validates(self):
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        code, out = run(VALIDATE_BUNDLE, root)
        self.assertEqual(code, 0, out)
        self.assertIn("VALID", out)

    # --------------------------------------------------------------- r2 -> r3

    def test_a_closed_application_gets_a_terminal_row(self):
        root = self.make_r1()
        app = root / "tailoring/applications/kestrel.md"
        app.write_text(
            APPLICATION.replace("outcome: pending", "outcome: rejected-after-interview")
            + "\n# Outcome\n\nRejected after first interview, 2026-07-02.\n",
            encoding="utf-8")
        run(MIGRATE_BUNDLE, root, "--apply")
        text = self.archived(root, "kestrel.md").read_text(encoding="utf-8")
        self.assertIn("# Timeline", text)
        self.assertIn("| 2020-03-04 | submitted |", text)
        self.assertIn("| 2026-07-02 | rejected |", text)

    def test_an_outcome_with_no_date_is_written_unknown(self):
        """A plausible date is indistinguishable from a recorded one. That is the bug."""
        root = self.make_r1()
        app = root / "tailoring/applications/kestrel.md"
        app.write_text(
            APPLICATION.replace("outcome: pending", "outcome: rejected-at-screen"),
            encoding="utf-8")
        run(MIGRATE_BUNDLE, root, "--apply")
        text = self.archived(root, "kestrel.md").read_text(encoding="utf-8")
        self.assertIn("| unknown | rejected |", text)
        self.assertIn("[reconstructed at migration", text)

    def test_a_date_outside_the_outcome_section_is_not_borrowed(self):
        root = self.make_r1()
        app = root / "tailoring/applications/kestrel.md"
        app.write_text(
            APPLICATION.replace("outcome: pending", "outcome: withdrawn")
            + "\n# Selection\n\nRanked on 2026-04-01.\n\n# Outcome\n\nWithdrawn.\n",
            encoding="utf-8")
        run(MIGRATE_BUNDLE, root, "--apply")
        text = self.archived(root, "kestrel.md").read_text(encoding="utf-8")
        self.assertIn("| unknown | withdrawn |", text)
        self.assertNotIn("| 2026-04-01 | withdrawn |", text)

    def test_outcome_is_deprecated_not_deleted(self):
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        text = self.archived(root, "kestrel.md").read_text(encoding="utf-8")
        self.assertIn("outcome: pending", text)
        self.assertIn("DEPRECATED at r3", text)

    def test_live_applications_are_listed_for_a_person(self):
        root = self.make_r1()
        code, out = run(MIGRATE_BUNDLE, root, "--apply")
        self.assertEqual(code, 1, out)
        self.assertIn("live application(s) have no history beyond submission", out)

    def test_the_pipeline_vocabulary_is_seeded(self):
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        vocab = root / "framework/pipeline-vocabulary.md"
        self.assertTrue(vocab.exists())
        text = vocab.read_text(encoding="utf-8")
        self.assertIn("`submitted`", text)
        self.assertIn("`follow-up-sent`", text)

    def test_organisations_are_labelled_employer(self):
        root = self.make_r1()
        (root / "organisations/meridian.md").write_text("""---
type: Organisation
title: "Meridian Health"
description: "Aged care provider."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
---

# About
""", encoding="utf-8")
        run(MIGRATE_BUNDLE, root, "--apply")
        text = (root / "organisations/meridian.md").read_text(encoding="utf-8")
        self.assertIn("relationship: employer", text)

    def test_an_old_bundle_is_warned_about_never_failed(self):
        """Failing r1 would break every bundle already in existence."""
        root = self.make_r1()
        code, out = run(VALIDATE_BUNDLE, root)
        self.assertEqual(code, 0, out)
        self.assertIn("VALID", out)
        self.assertIn("bundle revision 1", out)
        self.assertIn("migrate_bundle.py", out)


class Postings(MigrateCase):
    """A working posting becomes `<stem>.posting.md`, and the one unrecoverable
    fact is said.

    A Job Target file held a single list of requirements with no required-versus-
    preferred modifier. Promoting all of them to `required` is the only reading that
    does not silently discard a distinction - but it is still a promotion, so it is
    reported rather than performed quietly.
    """

    OUT = "tailoring/targets/kestrel.posting.md"

    def migrate(self, root):
        return run(MIGRATE_BUNDLE, root, "--apply")

    def make_r1_migrated(self):
        root = self.make_r1()
        self.migrate(root)
        return root

    def posting(self, root, rel=None):
        path = root / (rel or self.OUT)
        self.assertTrue(path.exists(), f"{rel or self.OUT} was not written")
        return path.read_text(encoding="utf-8")

    def frontmatter(self, root, rel=None):
        text = self.posting(root, rel)
        self.assertTrue(text.startswith("---"), text[:40])
        return text.split("---", 2)[1]

    def requirements(self, root, rel=None):
        """The `requirements:` blocks as dicts, without a YAML parser.

        Everything above the first `- ` is a scalar key, so it lands nowhere.
        """
        out = []
        for line in self.frontmatter(root, rel).splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                out.append({})
                stripped = stripped[2:]
            if out and ": " in stripped:
                key, value = stripped.split(": ", 1)
                out[-1][key] = value.split("#")[0].strip().strip('"')
        return out

    def test_a_target_becomes_a_markdown_posting(self):
        fm = self.frontmatter(self.make_r1_migrated())
        self.assertIn("type: Job Posting", fm)
        self.assertIn("title: Principal Platform Architect", fm)
        self.assertIn("company: Kestrel Health", fm)

    def test_requirements_carry_their_kind_and_value(self):
        reqs = self.requirements(self.make_r1_migrated())
        self.assertEqual({(r["value"], r["kind"]) for r in reqs},
                         {("integration-architecture", "capability"),
                          ("azure", "technology")})

    def test_role_axes_carry_over(self):
        fm = self.frontmatter(self.make_r1_migrated())
        self.assertIn("domains: [healthcare]", fm)
        self.assertIn("seniority: architecture-ownership", fm)

    def test_necessity_is_promoted_and_the_promotion_is_reported(self):
        root = self.make_r1()
        _, out = self.migrate(root)
        fm = self.frontmatter(root)
        self.assertEqual(fm.count("necessity: required"), 2)
        self.assertIn("status: needs-verification", fm)
        self.assertIn("no required-versus-preferred modifier", out)

    def test_the_advertisement_is_kept_and_nothing_else_is(self):
        """Only the `# Posting` section. The ranking below it was our own output,
        and carrying it over would leave someone re-reading this framework's guesses
        as though the employer had written them."""
        root = self.make_r1()
        (root / "tailoring/targets/kestrel.md").write_text(
            TARGET + "\n# Evidence ranking\n\n| rank | score |\n|---|---|\n| 1 | 19 |\n"
            "\n# Gaps\n\nNo Terraform evidence.\n", encoding="utf-8")
        self.migrate(root)
        body = self.posting(root).split("---", 2)[2]
        self.assertIn("Own the clinical integration platform across 60 sites.", body)
        self.assertNotIn("Evidence ranking", body)
        self.assertNotIn("Terraform", body)

    def test_the_frozen_application_target_is_left_alone(self):
        """It is already Markdown, and it is already frozen. Rewriting it to match a
        convention that postdates the application is what an archive exists to
        prevent."""
        root = self.make_r1_migrated()
        self.assertTrue(self.archived(root, "kestrel.target.md").exists())
        self.assertEqual(
            list((root / "tailoring/applications").rglob("*.posting.md")), [])

    def test_the_application_log_is_not_mistaken_for_a_posting(self):
        root = self.make_r1_migrated()
        self.assertTrue(self.archived(root, "kestrel.md").exists())

    def test_the_markdown_source_is_left_in_place(self):
        root = self.make_r1_migrated()
        self.assertTrue((root / "tailoring/targets/kestrel.md").exists())

    def test_it_does_not_overwrite_a_posting_that_already_exists(self):
        root = self.make_r1_migrated()
        target = root / self.OUT
        target.write_text("---\ntype: Job Posting\nmine: true\n---\n",
                          encoding="utf-8")
        run(MIGRATE_BUNDLE, root, "--apply")
        self.assertIn("mine", target.read_text(encoding="utf-8"))

    def test_a_ujd_posting_is_converted_too(self):
        """A bundle stopped at revision 4 has JSON postings and no reader for them."""
        import json
        root = self.make_r1()
        (root / "tailoring/targets/heron.posting.json").write_text(json.dumps({
            "ujd": "1.0.0",
            "posting": {"title": "Staff Engineer", "url": "https://example.com/j/1"},
            "organization": {"name": "Heron Labs"},
            "role": {"domains": ["fintech"], "seniority": "platform-design"},
            "requirements": [
                {"kind": "technology", "value": "kubernetes", "necessity": "must-have",
                 "provenance": {"source": {"text": "deep Kubernetes experience"}}},
                {"kind": "capability", "value": "observability",
                 "necessity": "nice-to-have"},
            ],
            "source": {"raw_text": "Run the platform team."},
        }), encoding="utf-8")
        self.migrate(root)
        text = self.posting(root, "tailoring/targets/heron.posting.md")
        fm, body = text.split("---", 2)[1], text.split("---", 2)[2]
        self.assertIn("title: Staff Engineer", fm)
        self.assertIn("company: Heron Labs", fm)
        # A URL holds a colon, which is the one thing bare YAML cannot carry.
        self.assertIn('url: "https://example.com/j/1"', fm)
        self.assertIn("domains: [fintech]", fm)
        self.assertIn("Run the platform team.", body)
        reqs = self.requirements(root, "tailoring/targets/heron.posting.md")
        self.assertEqual(reqs, [
            {"value": "kubernetes", "kind": "technology", "necessity": "required",
             "label": "deep Kubernetes experience"},
            {"value": "observability", "kind": "capability",
             "necessity": "preferred"},
        ])

    def test_a_target_with_no_frontmatter_is_reported_not_guessed(self):
        root = self.make_r1()
        (root / "tailoring/targets/bare.md").write_text(
            "# Just a posting\n\nSome text.\n", encoding="utf-8")
        _, out = self.migrate(root)
        self.assertIn("no readable frontmatter", out)
        self.assertFalse((root / "tailoring/targets/bare.posting.md").exists())

    def test_a_dry_run_writes_nothing(self):
        root = self.make_r1()
        code, out = run(MIGRATE_BUNDLE, root)
        self.assertEqual(code, 1)
        self.assertIn("would create", out)
        self.assertFalse((root / self.OUT).exists())


class Supersession(MigrateCase):
    """r5 -> r6 has to mark the working posting r5 itself replaced.

    It read only the filesystem, so on a bundle coming from r1 the `<stem>.posting.md`
    it was looking for had not been written yet - nothing looked superseded, nothing was
    marked, and `--apply` produced a bundle validate_bundle.py rejects on the very rule
    this step exists to satisfy. SKILL.md offers this migration to everyone arriving
    with an existing bundle, so that was the first thing the skill did to a real record.
    """

    def test_the_posting_it_created_supersedes_the_target_it_read(self):
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        self.assertIn("superseded_by: kestrel.posting.md",
                      (root / "tailoring/targets/kestrel.md").read_text(encoding="utf-8"))

    def test_a_posting_already_beside_an_unmarked_target_is_marked_too(self):
        """The other way in: r5 ran at some point, r6 never did."""
        root = self.make_r1()
        (root / "tailoring/targets/kestrel.posting.md").write_text(
            '---\ntype: Job Posting\ntitle: "Kestrel"\nstatus: confirmed\n---\n\n'
            "# Posting\n\nOwn the platform.\n", encoding="utf-8")
        run(MIGRATE_BUNDLE, root, "--apply")
        self.assertIn("superseded_by: kestrel.posting.md",
                      (root / "tailoring/targets/kestrel.md").read_text(encoding="utf-8"))


ORG = """---
type: Organisation
title: "Acme Health"
description: "Aged care provider."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
relationship: employer
---

# About

Aged care.
"""

LIVE_POSTING = """---
type: Job Posting
title: "Staff Engineer"
description: "Run the platform team."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
company: "Acme Health"
---

# Posting

Run the platform team.
"""


def r6_application(stem, submitted, extra=""):
    """An application in the flat r6 archive, with a reference at every depth.

    `posting:` is a companion in the same directory, `target_working_copy:` is one
    level up and `company_ref:` is two - which is exactly the set r7 has to rebase.
    """
    return """---
type: Application
title: "Acme Health - Staff Engineer"
description: "Submitted via Workday."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
posting: "%(stem)s.posting.md"
view_file: "%(stem)s.view.md"
target_working_copy: "../targets/acme.posting.md"
company_ref: "../../organisations/acme.md"
%(extra)s---

# What was sent

Rendered from [the view](%(stem)s.view.md) against
[the live posting](../targets/acme.posting.md) for [Acme](../../organisations/acme.md).

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| %(submitted)s | submitted | workday |  |  |
""" % {"stem": stem, "submitted": submitted, "extra": extra}


FROZEN = """---
type: %s
title: "Acme Health - Staff Engineer"
description: "Frozen at submission."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
frozen: true
---

# Posting

Run the platform team.
"""


class Revision7(MigrateCase):
    """The archive is partitioned by submission year.

    A flat archive is four hundred files by the hundredth application, and the frozen
    `.view.md` copies in it collide with the live views they were taken from. The year
    is immutable and already in the stem, which is why it - and not the outcome - is
    what the layout partitions on.
    """

    ACME = "2025-11-03-acme-engineer"
    HERON = "2026-02-01-heron-architect"

    def make_r6(self):
        root = self.make_bundle()
        index = root / "index.md"
        index.write_text(
            re.sub(r"okf_bundle: \d+", "okf_bundle: 6", index.read_text(encoding="utf-8")),
            encoding="utf-8")
        (root / "organisations/acme.md").write_text(ORG, encoding="utf-8")
        (root / "tailoring/targets/acme.posting.md").write_text(LIVE_POSTING, encoding="utf-8")
        apps = root / "tailoring/applications"
        for stem, submitted in ((self.ACME, "2025-11-03"), (self.HERON, "2026-02-01")):
            (apps / f"{stem}.md").write_text(
                r6_application(stem, submitted, f"submitted: {submitted}\n"),
                encoding="utf-8")
            (apps / f"{stem}.posting.md").write_text(FROZEN % "Source Document",
                                                     encoding="utf-8")
            (apps / f"{stem}.view.md").write_text(FROZEN % "View", encoding="utf-8")
        # A stem from before the date convention, whose date is in frontmatter.
        (apps / "legacy.md").write_text(
            r6_application("legacy", "2019-06-04", "submitted: 2019-06-04\n"),
            encoding="utf-8")
        (apps / "legacy.posting.md").write_text(FROZEN % "Source Document", encoding="utf-8")
        (apps / "legacy.view.md").write_text(FROZEN % "View", encoding="utf-8")
        # And one where nothing records when it was sent.
        (apps / "kestrel.md").write_text(
            r6_application("kestrel", "unknown", "submitted: unknown\n"), encoding="utf-8")
        (apps / "kestrel.posting.md").write_text(FROZEN % "Source Document", encoding="utf-8")
        (apps / "kestrel.view.md").write_text(FROZEN % "View", encoding="utf-8")
        return root

    def migrate(self, root):
        return run(MIGRATE_BUNDLE, root, "--apply")

    # ------------------------------------------------------------- the layout

    def test_an_application_lands_in_the_year_its_stem_names(self):
        root = self.make_r6()
        self.migrate(root)
        apps = root / "tailoring/applications"
        self.assertTrue((apps / f"2025/{self.ACME}.md").exists())
        self.assertTrue((apps / f"2026/{self.HERON}.md").exists())
        self.assertFalse((apps / f"{self.ACME}.md").exists())

    def test_the_whole_file_set_moves_not_just_the_log(self):
        root = self.make_r6()
        self.migrate(root)
        year = root / "tailoring/applications/2025"
        for suffix in (".md", ".posting.md", ".view.md"):
            self.assertTrue((year / (self.ACME + suffix)).exists(), suffix)

    def test_a_stem_with_no_date_falls_back_to_the_frontmatter(self):
        """`kestrel.md` predates the dated stem. `submitted:` still knows the year."""
        root = self.make_r6()
        self.migrate(root)
        self.assertTrue((root / "tailoring/applications/2019/legacy.md").exists())

    def test_an_application_with_no_derivable_year_is_filed_undated_and_reported(self):
        root = self.make_r6()
        code, out = self.migrate(root)
        self.assertEqual(code, 1, out)
        self.assertTrue((root / "tailoring/applications/undated/kestrel.md").exists())
        self.assertIn("undated", out)
        self.assertIn("rather than into a guessed year", out)

    # -------------------------------------------------------------- the links

    def test_a_relative_link_out_of_a_moved_file_still_resolves(self):
        root = self.make_r6()
        self.migrate(root)
        moved = root / "tailoring/applications/2025" / (self.ACME + ".md")
        text = moved.read_text(encoding="utf-8")
        self.assertIn('target_working_copy: "../../targets/acme.posting.md"', text)
        self.assertIn('company_ref: "../../../organisations/acme.md"', text)
        self.assertIn("(../../targets/acme.posting.md)", text)
        self.assertIn("(../../../organisations/acme.md)", text)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            self.assertTrue((moved.parent / target).resolve().exists(), target)

    def test_a_companion_in_the_same_directory_is_left_alone(self):
        """It moved with the file that names it, so the path between them is unchanged."""
        root = self.make_r6()
        self.migrate(root)
        text = (root / "tailoring/applications/2025" / (self.ACME + ".md")).read_text(
            encoding="utf-8")
        self.assertIn('posting: "%s.posting.md"' % self.ACME, text)
        self.assertIn('view_file: "%s.view.md"' % self.ACME, text)

    def test_a_link_from_outside_the_archive_is_rebased(self):
        """r5 -> r6 leaves prose links alone because the file is still there. Here it
        is not, so a link nobody rebases is a broken link."""
        root = self.make_r6()
        log = root / "log.md"
        log.write_text(log.read_text(encoding="utf-8")
                       + f"\n# 2025-11-03 - Applied\n\nSee "
                         f"[the application](tailoring/applications/{self.ACME}.md).\n",
                       encoding="utf-8")
        self.migrate(root)
        self.assertIn(f"(tailoring/applications/2025/{self.ACME}.md)",
                      log.read_text(encoding="utf-8"))

    # ------------------------------------------------------------ the indexes

    def test_every_year_directory_gets_an_index(self):
        root = self.make_r6()
        self.migrate(root)
        apps = root / "tailoring/applications"
        for year in ("2019", "2025", "2026", "undated"):
            self.assertTrue((apps / year / "index.md").exists(), year)
        listing = (apps / "2025/index.md").read_text(encoding="utf-8")
        self.assertIn(f"({self.ACME}.md)", listing)

    def test_the_archive_index_lists_the_year_directories(self):
        root = self.make_r6()
        self.migrate(root)
        text = (root / "tailoring/applications/index.md").read_text(encoding="utf-8")
        for year in ("2019", "2025", "2026", "undated"):
            self.assertIn(f"({year}/index.md)", text)

    # ------------------------------------------------ what it must not do

    def test_the_dry_run_reports_the_moves_and_writes_nothing(self):
        root = self.make_r6()
        code, out = run(MIGRATE_BUNDLE, root)
        self.assertEqual(code, 1, out)
        self.assertIn("would move", out)
        self.assertIn("2025/", out)
        self.assertTrue((root / "tailoring/applications" / (self.ACME + ".md")).exists())
        self.assertFalse((root / "tailoring/applications/2025").exists())

    def test_it_refuses_to_write_over_a_file_already_in_the_year_directory(self):
        root = self.make_r6()
        year = root / "tailoring/applications/2025"
        year.mkdir()
        (year / (self.ACME + ".md")).write_text(
            '---\ntype: Application\ntitle: "Mine"\nsubmitted: false\n---\n\n'
            "# Timeline\n\n| Date | Event | Channel | Note | Due |\n|---|---|---|---|---|\n",
            encoding="utf-8")
        code, out = self.migrate(root)
        self.assertEqual(code, 1, out)
        self.assertIn("already exists", out)
        self.assertIn("Mine", (year / (self.ACME + ".md")).read_text(encoding="utf-8"))

    def test_a_migrated_r6_bundle_validates(self):
        root = self.make_r6()
        self.migrate(root)
        code, out = run(VALIDATE_BUNDLE, root)
        self.assertEqual(code, 0, out)

    def test_running_it_again_has_nothing_to_do(self):
        root = self.make_r6()
        self.migrate(root)
        code, out = run(MIGRATE_BUNDLE, root, "--apply")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to do", out)


    # ----------------------------------------------------------- loose files
    #
    # A sent resume is named after the person and the company, not the application, so
    # it cannot be grouped by its own filename - and filing it under the wrong
    # application is a worse record than leaving it where somebody can see it.

    def test_a_resume_the_application_links_moves_with_it(self):
        root = self.make_r6()
        apps = root / "tailoring/applications"
        (apps / "Test_Person_Acme_Resume.txt").write_text("Test Person\n", encoding="utf-8")
        app = apps / (self.ACME + ".md")
        app.write_text(app.read_text(encoding="utf-8")
                       + "\n# Sent\n\n[The resume](Test_Person_Acme_Resume.txt)\n",
                       encoding="utf-8")
        self.migrate(root)
        self.assertTrue((apps / "2025/Test_Person_Acme_Resume.txt").exists())

    def test_a_resume_named_after_the_stem_moves_with_it(self):
        root = self.make_r6()
        apps = root / "tailoring/applications"
        (apps / (self.ACME + "_Resume.txt")).write_text("Test Person\n", encoding="utf-8")
        self.migrate(root)
        self.assertTrue((apps / "2025" / (self.ACME + "_Resume.txt")).exists())

    def test_a_resume_nothing_claims_is_left_alone_and_reported(self):
        root = self.make_r6()
        apps = root / "tailoring/applications"
        (apps / "Test_Person_Vanished_Resume.txt").write_text("Test Person\n",
                                                              encoding="utf-8")
        code, out = self.migrate(root)
        self.assertEqual(code, 1, out)
        self.assertTrue((apps / "Test_Person_Vanished_Resume.txt").exists())
        self.assertIn("belongs to no application this migration can name", out)


if __name__ == "__main__":
    unittest.main()
