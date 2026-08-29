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

    def frozen(self, root):
        return root / "tailoring/applications/kestrel.target.md"

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
        self.assertFalse(self.frozen(root).exists())
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
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        app = (root / "tailoring/applications/kestrel.md").read_text(encoding="utf-8")
        self.assertIn('posting: "kestrel.target.md"', app)
        self.assertIn('target_working_copy: "../targets/kestrel.md"', app)
        self.assertNotRegex(app, r"(?m)^target:")

    def test_the_working_copy_survives(self):
        """Nothing is deleted - the next application to this company starts from it."""
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        working = root / "tailoring/targets/kestrel.md"
        self.assertTrue(working.exists())
        self.assertEqual(working.read_text(encoding="utf-8"), TARGET)

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
        orphan = (root / "tailoring/applications/vanished-co.md").read_text(encoding="utf-8")
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
        text = app.read_text(encoding="utf-8")
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
        text = app.read_text(encoding="utf-8")
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
        text = app.read_text(encoding="utf-8")
        self.assertIn("| unknown | withdrawn |", text)
        self.assertNotIn("| 2026-04-01 | withdrawn |", text)

    def test_outcome_is_deprecated_not_deleted(self):
        root = self.make_r1()
        run(MIGRATE_BUNDLE, root, "--apply")
        text = (root / "tailoring/applications/kestrel.md").read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()


class R3ToR4(MigrateCase):
    """The posting becomes a UJD document, and the one unrecoverable fact is said.

    A Job Target file held a single list of requirements with no required-versus-
    preferred modifier. Promoting all of them to must-have is the only reading that
    does not silently discard a distinction - but it is still a promotion, so it is
    reported rather than performed quietly.
    """

    def migrate(self, root):
        code, out = run(MIGRATE_BUNDLE, root, "--apply")
        return code, out

    def posting(self, root, rel="tailoring/targets/kestrel.posting.json"):
        import json
        path = root / rel
        self.assertTrue(path.exists(), f"{rel} was not written")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_a_target_becomes_a_ujd_document(self):
        root = self.make_r1()
        self.migrate(root)
        doc = self.posting(root)
        self.assertEqual(doc["ujd"], "1.0.0")
        self.assertEqual(doc["posting"]["title"], "Principal Platform Architect")
        self.assertEqual(doc["organization"]["name"], "Kestrel Health")

    def test_requirements_carry_their_kind_and_value(self):
        root = self.make_r1()
        self.migrate(root)
        doc = self.posting(root)
        pairs = {(r["kind"], r["value"]) for r in doc["requirements"]}
        self.assertEqual(pairs, {("capability", "integration-architecture"),
                                 ("technology", "azure")})

    def test_role_axes_carry_over(self):
        root = self.make_r1()
        self.migrate(root)
        doc = self.posting(root)
        self.assertEqual(doc["role"]["domains"], ["healthcare"])
        self.assertEqual(doc["role"]["seniority"], "architecture-ownership")

    def test_necessity_is_promoted_and_the_promotion_is_reported(self):
        root = self.make_r1()
        _, out = self.migrate(root)
        doc = self.posting(root)
        self.assertTrue(all(r["necessity"] == "must-have" for r in doc["requirements"]))
        self.assertTrue(all(r["provenance"]["status"] == "needs-verification"
                            for r in doc["requirements"]))
        self.assertIn("nothing here can tell which", out)

    def test_the_advertisement_is_kept_and_nothing_else_is(self):
        """Only the `# Posting` section. The ranking below it was our own output,
        and carrying it into raw_text would let a span check pass against text that
        was never in the advertisement."""
        root = self.make_r1()
        (root / "tailoring/targets/kestrel.md").write_text(
            TARGET + "\n# Evidence ranking\n\n| rank | score |\n|---|---|\n| 1 | 19 |\n"
            "\n# Gaps\n\nNo Terraform evidence.\n", encoding="utf-8")
        self.migrate(root)
        raw = self.posting(root)["source"]["raw_text"]
        self.assertIn("Own the clinical integration platform across 60 sites.", raw)
        self.assertNotIn("Evidence ranking", raw)
        self.assertNotIn("Terraform", raw)

    def test_the_frozen_application_target_is_converted_too(self):
        root = self.make_r1()
        self.migrate(root)
        doc = self.posting(root, "tailoring/applications/kestrel.posting.json")
        self.assertEqual(doc["organization"]["name"], "Kestrel Health")

    def test_the_application_log_is_not_mistaken_for_a_posting(self):
        """In applications/ only the frozen `.target.md` is a posting; the bare
        `<stem>.md` is the log, and converting it would invent a posting."""
        root = self.make_r1()
        self.migrate(root)
        self.assertTrue((root / "tailoring/applications/kestrel.md").exists())
        self.assertEqual(
            len(list((root / "tailoring/applications").glob("*.posting.json"))), 1)

    def test_the_markdown_is_left_in_place(self):
        root = self.make_r1()
        self.migrate(root)
        self.assertTrue((root / "tailoring/targets/kestrel.md").exists())

    def test_it_does_not_overwrite_a_posting_that_already_exists(self):
        root = self.make_r1()
        self.migrate(root)
        target = root / "tailoring/targets/kestrel.posting.json"
        target.write_text('{"ujd": "1.0.0", "mine": true}', encoding="utf-8")
        run(MIGRATE_BUNDLE, root, "--apply")
        self.assertIn("mine", target.read_text(encoding="utf-8"))

    def test_the_produced_document_validates_as_ujd(self):
        from fixtures import VALIDATE_UJD
        root = self.make_r1()
        self.migrate(root)
        code, out = run(VALIDATE_UJD, root / "tailoring/targets/kestrel.posting.json")
        self.assertEqual(code, 0, out)

    def test_the_missing_record_is_reported_rather_than_invented(self):
        """Transcribing prose into evidence is not a text substitution."""
        root = self.make_r1()
        _, out = self.migrate(root)
        self.assertIn("record.json does not exist yet", out)
        self.assertFalse((root / "resume-generation" / "record.json").exists())

    def test_a_target_with_no_frontmatter_is_reported_not_guessed(self):
        root = self.make_r1()
        (root / "tailoring/targets/bare.md").write_text(
            "# Just a posting\n\nSome text.\n", encoding="utf-8")
        _, out = self.migrate(root)
        self.assertIn("no readable frontmatter", out)
        self.assertFalse((root / "tailoring/targets/bare.posting.json").exists())

    def test_a_dry_run_writes_nothing(self):
        root = self.make_r1()
        code, out = run(MIGRATE_BUNDLE, root)
        self.assertEqual(code, 1)
        self.assertIn("would create", out)
        self.assertFalse((root / "tailoring/targets/kestrel.posting.json").exists())
