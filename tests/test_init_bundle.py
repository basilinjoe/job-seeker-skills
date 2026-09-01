"""A scaffold must produce a bundle that validates, and must not document paths
it never creates.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import (INIT_BUNDLE, MIGRATE_BUNDLE, SCRIPTS, VALIDATE_BUNDLE, load_script, run,
                      write_concept)

CURRENT = load_script(MIGRATE_BUNDLE).CURRENT_REVISION


class InitBundleCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.root = self.tmp / "my-career"
        code, out = run(INIT_BUNDLE, self.root, "--name", "Test Person")
        self.assertEqual(code, 0, out)

    def validate(self):
        return run(VALIDATE_BUNDLE, self.root)


class Scaffold(InitBundleCase):
    def test_fresh_bundle_validates(self):
        code, out = self.validate()
        self.assertEqual(code, 0, out)

    def test_bundle_with_one_project_still_validates(self):
        write_concept(self.root)
        code, out = self.validate()
        self.assertEqual(code, 0, out)

    def test_refuses_to_overwrite_a_non_empty_directory(self):
        code, out = run(INIT_BUNDLE, self.root, "--name", "Someone Else")
        self.assertEqual(code, 1)
        self.assertIn("refusing to overwrite", out)

    def test_name_with_quotes_does_not_break_frontmatter(self):
        root = self.tmp / "quoted"
        code, out = run(INIT_BUNDLE, root, "--name", 'John "Jack" Smith')
        self.assertEqual(code, 0, out)
        code, out = run(VALIDATE_BUNDLE, root)
        self.assertEqual(code, 0, out)


class GeneratedDocs(InitBundleCase):
    """getting-started.md told users to run `framework/validate_bundle.py`,
    a path init_bundle.py never creates.
    """

    def test_getting_started_does_not_reference_paths_that_do_not_exist(self):
        text = (self.root / "getting-started.md").read_text(encoding="utf-8")
        for claimed in ("framework/validate_bundle.py", "framework/check_ats.py",
                        "framework/init_bundle.py"):
            self.assertNotIn(claimed, text,
                             f"getting-started.md points at {claimed}, which is never created")

    def test_every_local_path_named_in_generated_docs_exists(self):
        for doc in ("index.md", "getting-started.md", "log.md"):
            text = (self.root / doc).read_text(encoding="utf-8")
            for token in text.split():
                if token.endswith(".py"):
                    candidate = self.root / token.strip("`(),")
                    self.assertFalse(
                        token.startswith(("framework/", "scripts/")) and not candidate.exists(),
                        f"{doc} names {token}, which does not exist in the bundle")


class ScaffoldedConcepts(InitBundleCase):
    """The two files without which a bundle compiles to nothing.

    A fresh bundle validated clean and compiled to an empty record, so somebody could
    get all the way to a render before finding out there had never been anything to
    render. Both are scaffolded `needs-verification` and empty: setup mode then has
    something to fill in rather than something to invent.
    """

    def compiled(self):
        okf = load_script(
            SCRIPTS / "okf_compile.py")      # read-only; owned elsewhere
        return okf, okf.load(str(self.root))

    def test_the_person_concept_exists_and_compiles(self):
        identity = self.root / "profile" / "identity.md"
        self.assertTrue(identity.exists(), "profile/identity.md - the Person concept")
        self.assertIn("type: Person", identity.read_text(encoding="utf-8"))
        _, doc = self.compiled()
        self.assertEqual(doc["person"]["name"]["full"], "Test Person")

    def test_the_person_stub_is_empty_not_invented(self):
        """A placeholder headline would compile onto a resume as if someone wrote it."""
        _, doc = self.compiled()
        self.assertEqual(doc["person"]["contacts"], [])
        self.assertNotIn("headline", doc["person"])
        self.assertIn("status: needs-verification",
                      (self.root / "profile" / "identity.md").read_text(encoding="utf-8"))

    def test_the_metrics_table_exists_and_reads_as_empty(self):
        metrics = self.root / "achievements" / "metrics.md"
        self.assertTrue(metrics.exists(), "achievements/metrics.md")
        okf, _ = self.compiled()
        self.assertEqual(okf.metrics_table(str(self.root)), {})

    def test_a_fresh_bundle_is_born_at_the_current_revision(self):
        self.assertIn(f"okf_bundle: {CURRENT}",
                      (self.root / "index.md").read_text(encoding="utf-8"))
        code, out = run(MIGRATE_BUNDLE, self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to do", out)

    def test_the_archive_index_describes_the_year_partition(self):
        text = (self.root / "tailoring/applications/index.md").read_text(encoding="utf-8")
        self.assertIn("One directory per submission year", text)


if __name__ == "__main__":
    unittest.main()
