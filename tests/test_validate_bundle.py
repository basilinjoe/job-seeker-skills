"""validate_bundle.py must never report VALID when it has not actually looked."""
import re
import tempfile
import unittest
from pathlib import Path

from fixtures import INIT_BUNDLE, VALIDATE_BUNDLE, CONCEPT, run, write_concept


def set_revision(root, n):
    """Stamp the bundle root at a layout revision.

    Every revision-gated rule is asserted at the revision that has it and the one
    below, so these tests must not inherit whatever init_bundle.py stamps today.
    """
    index = Path(root) / "index.md"
    text = index.read_text(encoding="utf-8")
    text, count = re.subn(r"^okf_bundle: \d+$", f"okf_bundle: {n}", text, count=1, flags=re.M)
    assert count == 1, "bundle root index.md no longer carries okf_bundle"
    index.write_text(text, encoding="utf-8")


APPLICATION = """---
type: Application
title: "Kestrel Health - Principal Architect"
description: "Submitted."
timestamp: 2026-01-01T00:00:00Z
status: confirmed
company: "Kestrel Health"
role: "Principal Architect"
submitted: 2026-09-01
{extra}---

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-09-01 | submitted | portal |  |  |
"""

FROZEN_VIEW = """---
type: View
title: "Kestrel Health - Principal Architect"
description: "Frozen at submission."
timestamp: 2026-01-01T00:00:00Z
---

{body}
"""

NOTE = """---
type: Note
title: "A note"
description: "Something written down."
timestamp: 2026-01-01T00:00:00Z
---

Body.
"""

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

    def validate(self, root, *args):
        return run(VALIDATE_BUNDLE, root, *args)

    def application(self, root, subdir="", stem="2026-09-01-kestrel-architect", extra=""):
        """Write an application into the archive, flat or inside a year directory."""
        where = Path(root) / "tailoring" / "applications"
        if subdir:
            where = where / subdir
            where.mkdir(parents=True, exist_ok=True)
        path = where / f"{stem}.md"
        path.write_text(APPLICATION.format(extra=extra), encoding="utf-8")
        return path

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


class YearPartitionedArchive(BundleCase):
    """Revision 7 partitions tailoring/applications/ by submission year. Every rule
    here has to be silent at revision 6, where the flat shape is the correct one."""

    def test_a_flat_application_at_r7_is_an_error(self):
        root = self.make_bundle()
        set_revision(root, 7)
        self.application(root)
        self.assertInvalid(root, "partitions the archive by year")

    def test_the_same_flat_application_at_r6_is_correct(self):
        root = self.make_bundle()
        set_revision(root, 6)
        self.application(root)
        self.assertValid(root)

    def test_a_year_directory_is_the_r7_shape(self):
        root = self.make_bundle()
        set_revision(root, 7)
        self.application(root, subdir="2026")
        self.assertValid(root)

    def test_undated_is_a_year_directory(self):
        """Where no year could be established the migration reports it rather than
        guessing, and the directory it lands in must not then read as an error."""
        root = self.make_bundle()
        set_revision(root, 7)
        self.application(root, subdir="undated")
        self.assertValid(root)

    def test_a_directory_that_is_not_a_year_at_r7_is_an_error(self):
        root = self.make_bundle()
        set_revision(root, 7)
        self.application(root, subdir="closed")
        self.assertInvalid(root, "not a year directory")

    def test_a_directory_that_is_not_a_year_at_r6_is_not(self):
        root = self.make_bundle()
        set_revision(root, 6)
        self.application(root, subdir="closed")
        self.assertValid(root)

    def test_a_declared_companion_missing_inside_a_year_directory_is_caught(self):
        """The layout checks listed tailoring/applications/ flat. At r7 that is a
        directory of year folders, so every one of them reported nothing at all -
        the quietest way for a gate to stop working."""
        root = self.make_bundle()
        set_revision(root, 7)
        self.application(root, subdir="2026",
                         extra='posting: "2026-09-01-kestrel-architect.posting.md"\n')
        self.assertInvalid(root, "does not exist")

    def test_a_companion_beside_it_in_a_year_directory_satisfies_the_check(self):
        root = self.make_bundle()
        set_revision(root, 7)
        app = self.application(root, subdir="2026",
                               extra='posting: "2026-09-01-kestrel-architect.posting.md"\n')
        (app.parent / "2026-09-01-kestrel-architect.posting.md").write_text(
            FROZEN_VIEW.format(body="The advertisement, verbatim."), encoding="utf-8")
        out = self.assertValid(root)
        self.assertNotIn("does not exist", out)

    def test_a_companion_in_a_different_year_does_not_count(self):
        """A companion is a file beside the application, not one anywhere under the
        archive. A recursive name set would have made this pass."""
        root = self.make_bundle()
        set_revision(root, 7)
        self.application(root, subdir="2026",
                         extra='posting: "2026-09-01-kestrel-architect.posting.md"\n')
        elsewhere = Path(root) / "tailoring" / "applications" / "2025"
        elsewhere.mkdir()
        (elsewhere / "2026-09-01-kestrel-architect.posting.md").write_text(
            FROZEN_VIEW.format(body="The advertisement, verbatim."), encoding="utf-8")
        self.assertInvalid(root, "does not exist")


class FrozenArchive(BundleCase):
    """bundle-spec.md: the copies beside an application are the archive and do not
    stay editable. An error inside one is a red nobody is permitted to clear, and a
    gate that cannot go green is a gate people stop running."""

    def test_a_broken_link_in_a_frozen_copy_is_a_warning(self):
        root = self.make_bundle()
        set_revision(root, 6)
        self.application(root)
        (Path(root) / "tailoring" / "applications"
         / "2026-09-01-kestrel-architect.view.md").write_text(
            FROZEN_VIEW.format(body="See [the record](../../resume-generation/gone.md)."),
            encoding="utf-8")
        out = self.assertValid(root)
        self.assertIn("BROKEN LINK", out)
        self.assertIn("! ", out)

    def test_the_same_break_in_the_application_file_is_still_an_error(self):
        """The application file is not frozen - its timeline is appended to for as
        long as the process is live, so anything wrong in it can be fixed."""
        root = self.make_bundle()
        set_revision(root, 6)
        app = self.application(root)
        app.write_text(app.read_text(encoding="utf-8")
                       + "\nSee [the record](../../resume-generation/gone.md).\n",
                       encoding="utf-8")
        self.assertInvalid(root, "broken link")

    def test_a_broken_link_in_a_working_target_is_still_an_error(self):
        """tailoring/targets/ stays editable, so nothing there is demoted."""
        root = self.make_bundle()
        set_revision(root, 6)
        targets = Path(root) / "tailoring" / "targets"
        (targets / "kestrel-architect.posting.md").write_text(
            FROZEN_VIEW.format(body="See [the record](../../resume-generation/gone.md)."),
            encoding="utf-8")
        self.assertInvalid(root, "broken link")


class Scoping(BundleCase):
    """A whole-bundle run is the only run there was, and a bundle grows without limit."""

    def test_scope_reads_only_that_subtree(self):
        root = self.make_bundle()
        (root / "projects" / "broken.md").write_text("no frontmatter here\n", encoding="utf-8")
        self.assertInvalid(root, "frontmatter")
        code, out = run(VALIDATE_BUNDLE, root, "--scope", "organisations")
        self.assertEqual(code, 0, out)
        self.assertIn("VALID", out)

    def test_scope_still_checks_what_is_inside_it(self):
        root = self.make_bundle()
        (root / "projects" / "broken.md").write_text("no frontmatter here\n", encoding="utf-8")
        code, out = run(VALIDATE_BUNDLE, root, "--scope", "projects")
        self.assertEqual(code, 1, out)
        self.assertIn("frontmatter", out)

    def test_scope_says_which_checks_it_could_not_cover(self):
        """A check that silently did not run is worse than one that failed."""
        root = self.make_bundle()
        _, out = run(VALIDATE_BUNDLE, root, "--scope", "projects")
        self.assertIn("only projects/ was read", out)
        self.assertIn("capability vocabulary cross-checked against projects/ only", out)
        self.assertIn("bundle revision read from the bundle root", out)
        self.assertIn("through-line counts suppressed", out)

    def test_scope_outside_the_bundle_is_a_usage_error(self):
        root = self.make_bundle()
        for bad in ("..", "../elsewhere", "no-such-directory"):
            code, out = run(VALIDATE_BUNDLE, root, "--scope", bad)
            self.assertEqual(code, 2, f"--scope {bad}:\n{out}")
            self.assertIn("fix:", out)

    def test_exclude_archive_skips_the_archive_and_says_so(self):
        root = self.make_bundle()
        set_revision(root, 6)
        app = self.application(root)
        app.write_text(app.read_text(encoding="utf-8")
                       + "\nSee [the record](../../resume-generation/gone.md).\n",
                       encoding="utf-8")
        self.assertInvalid(root, "broken link")
        code, out = run(VALIDATE_BUNDLE, root, "--exclude-archive")
        self.assertEqual(code, 0, out)
        self.assertIn("tailoring/applications/ not read (--exclude-archive)", out)


class FindingVolume(BundleCase):
    """Warnings truncated at 15; errors printed unbounded, which is how one vocabulary
    change put a hundred lines into a reader's context."""

    def bad_projects(self, root, n):
        for i in range(n):
            (root / "projects" / f"bad{i}.md").write_text("no frontmatter\n", encoding="utf-8")

    def test_errors_are_capped_the_way_warnings_are(self):
        root = self.make_bundle()
        self.bad_projects(root, 8)
        code, out = run(VALIDATE_BUNDLE, root, "--max-findings", "3")
        self.assertEqual(code, 1, out)
        self.assertIn("ERRORS 8", out)
        self.assertEqual(out.count("no YAML frontmatter"), 3)
        self.assertIn("x ... and 5 more", out)

    def test_the_cap_is_the_default(self):
        root = self.make_bundle()
        self.bad_projects(root, 40)
        code, out = run(VALIDATE_BUNDLE, root)
        self.assertEqual(code, 1, out)
        self.assertIn("ERRORS 40", out)
        self.assertIn("x ... and 15 more", out)

    def test_zero_prints_every_one(self):
        root = self.make_bundle()
        self.bad_projects(root, 40)
        _, out = run(VALIDATE_BUNDLE, root, "--max-findings", "0")
        self.assertEqual(out.count("no YAML frontmatter"), 40)
        self.assertNotIn("... and", out)


class DirectoryIndex(BundleCase):
    """bundle-spec.md gives every directory an index.md and SKILL.md has every session
    read it first. Only init_bundle.py has ever written one."""

    def test_a_directory_with_no_index_warns(self):
        root = self.make_bundle()
        notes = root / "notes"
        notes.mkdir()
        (notes / "thought.md").write_text(NOTE, encoding="utf-8")
        out = self.assertValid(root)
        self.assertIn("notes/index.md: absent", out)

    def test_a_seeded_bundle_is_not_nagged(self):
        root = self.make_bundle()
        write_concept(root)
        out = self.assertValid(root)
        self.assertNotIn("index.md: absent", out)

    def test_a_year_directory_without_an_index_warns(self):
        root = self.make_bundle()
        set_revision(root, 7)
        self.application(root, subdir="2026")
        out = self.assertValid(root)
        self.assertIn("tailoring/applications/2026/index.md: absent", out)


if __name__ == "__main__":
    unittest.main()
