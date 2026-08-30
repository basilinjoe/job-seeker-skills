"""validate_bundle.py must never report VALID when it has not actually looked."""
import tempfile
import unittest
from pathlib import Path

from fixtures import INIT_BUNDLE, VALIDATE_BUNDLE, CONCEPT, run, write_concept

VOCAB_HEADER = """---
type: Vocabulary
title: "Capability vocabulary"
description: "Canonical capability values."
timestamp: 2026-01-01T00:00:00Z
---

`capabilities` is the primary axis for matching a job description to evidence.

# Architecture & design
"""


class BundleCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_bundle(self, parent=None):
        root = (parent or self.tmp) / "my-career"
        code, out = run(INIT_BUNDLE, root, "--name", "Test Person")
        self.assertEqual(code, 0, out)
        return root

    def validate(self, root):
        return run(VALIDATE_BUNDLE, root)

    def assertValid(self, root):
        code, out = self.validate(root)
        self.assertEqual(code, 0, f"expected VALID, got:\n{out}")
        self.assertIn("VALID", out)
        return out

    def assertInvalid(self, root, needle=None):
        code, out = self.validate(root)
        self.assertEqual(code, 1, f"expected FAILED, got exit {code}:\n{out}")
        self.assertIn("FAILED", out)
        if needle:
            self.assertIn(needle, out.lower())
        return out


class SilentPass(BundleCase):
    def test_bundle_under_a_dot_directory_is_still_checked(self):
        """A bundle at ...\\.claude\\my-career reported `files 0 ... VALID`."""
        hidden = self.tmp / ".claude"
        hidden.mkdir()
        root = self.make_bundle(parent=hidden)
        (root / "projects" / "broken.md").write_text("no frontmatter here\n", encoding="utf-8")

        out = self.assertInvalid(root.resolve(), "frontmatter")
        self.assertNotIn("files 0", out)

    def test_hidden_subdirectories_are_still_skipped(self):
        root = self.make_bundle()
        git = root / ".git"
        git.mkdir()
        (git / "COMMIT_EDITMSG.md").write_text("not a concept\n", encoding="utf-8")
        self.assertValid(root)

    def test_empty_directory_is_not_valid(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        self.assertInvalid(empty, "no markdown files")

    def test_nonexistent_directory_is_not_valid(self):
        self.assertInvalid(self.tmp / "does-not-exist")


class CapabilityVocabulary(BundleCase):
    """The seeded vocabulary's own prose made `vocab` non-empty, which defeated
    the "empty vocabulary disables the check" escape hatch at validate_bundle.py:80.
    """

    def test_seeded_vocabulary_does_not_reject_real_capabilities(self):
        root = self.make_bundle()
        write_concept(root)
        self.assertValid(root)

    def test_populated_vocabulary_rejects_an_unlisted_capability(self):
        root = self.make_bundle()
        vocab = root / "framework" / "capability-vocabulary.md"
        vocab.write_text(VOCAB_HEADER + "\n- `ai-platform-architecture`\n", encoding="utf-8")
        write_concept(root)
        out = self.assertInvalid(root, "data-sovereignty")
        self.assertNotIn("'ai-platform-architecture' is not", out)

    def test_populated_vocabulary_accepts_listed_capabilities(self):
        root = self.make_bundle()
        vocab = root / "framework" / "capability-vocabulary.md"
        vocab.write_text(
            VOCAB_HEADER + "\n- `ai-platform-architecture`\n- `data-sovereignty`\n",
            encoding="utf-8")
        write_concept(root)
        self.assertValid(root)

    def test_fenced_example_is_not_treated_as_vocabulary(self):
        """The seed file shows the list-item format in a fence. That example must
        not become vocabulary, or an unpopulated file rejects every real value."""
        root = self.make_bundle()
        vocab = root / "framework" / "capability-vocabulary.md"
        vocab.write_text(
            VOCAB_HEADER + "\n```\n- `example-capability`\n```\n", encoding="utf-8")
        write_concept(root)
        self.assertValid(root)

    def test_prose_backticks_are_not_treated_as_vocabulary(self):
        root = self.make_bundle()
        vocab = root / "framework" / "capability-vocabulary.md"
        vocab.write_text(
            VOCAB_HEADER + "\nCompare `capabilities` as exact strings.\n\n"
            "- `ai-platform-architecture`\n- `data-sovereignty`\n", encoding="utf-8")
        write_concept(root, text=CONCEPT.replace(
            "capabilities: [ai-platform-architecture, data-sovereignty]",
            "capabilities: [capabilities]"))
        self.assertInvalid(root, "capabilities")


class ConceptRules(BundleCase):
    def test_project_missing_selection_keys_fails(self):
        root = self.make_bundle()
        write_concept(root, text=CONCEPT.replace("strength: 5\n", ""))
        self.assertInvalid(root, "selection key")

    def test_bad_status_fails(self):
        root = self.make_bundle()
        write_concept(root, text=CONCEPT.replace("status: confirmed", "status: probably-true"))
        self.assertInvalid(root, "status")

    def test_bad_seniority_fails(self):
        root = self.make_bundle()
        write_concept(root, text=CONCEPT.replace("seniority: architecture-ownership",
                                                 "seniority: very-senior"))
        self.assertInvalid(root, "seniority")

    def test_strength_out_of_range_fails(self):
        root = self.make_bundle()
        write_concept(root, text=CONCEPT.replace("strength: 5", "strength: 9"))
        self.assertInvalid(root, "strength")

    def test_broken_relative_link_fails(self):
        root = self.make_bundle()
        write_concept(root, text=CONCEPT + "\nSee [the role](../roles/absent.md).\n")
        self.assertInvalid(root, "broken link")

    def test_capabilities_as_a_string_is_a_type_error(self):
        """A scalar where a list was meant must not be iterated character by character."""
        root = self.make_bundle()
        write_concept(root, text=CONCEPT.replace(
            "capabilities: [ai-platform-architecture, data-sovereignty]",
            "capabilities: ai-platform-architecture"))
        out = self.assertInvalid(root, "must be a list")
        self.assertNotIn("capability 'a' is not", out)


if __name__ == "__main__":
    unittest.main()
