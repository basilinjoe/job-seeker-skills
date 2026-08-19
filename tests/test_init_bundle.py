"""A scaffold must produce a bundle that validates, and must not document paths
it never creates.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import INIT_BUNDLE, VALIDATE_BUNDLE, run, write_concept


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


if __name__ == "__main__":
    unittest.main()
