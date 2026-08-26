"""migrate_bundle.py must move an old bundle forward without inventing anything.

The migration writes into somebody's career record, so the tests here care less about
"did it change the file" than about two narrower promises: it never fabricates a posting
it could not find, and it never claims a late snapshot was taken at submission.
"""
import re
import tempfile
import unittest
from pathlib import Path

from fixtures import INIT_BUNDLE, MIGRATE_BUNDLE, VALIDATE_BUNDLE, run

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
        self.assertEqual(code, 0, out)
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
        self.assertIn("okf_bundle: 2", (root / "index.md").read_text(encoding="utf-8"))

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
        self.assertIn("NEEDS A PERSON 1", out)
        self.assertIn("cannot invent one", out)
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
