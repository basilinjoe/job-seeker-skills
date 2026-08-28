"""okf.py is a convenience layer over the nine scripts, and its one job is to be
transparent: the same arguments, the same exit code, and the underlying script's own
output. These tests pin that transparency, because a dispatcher that quietly changes
a verdict is worse than no dispatcher at all.
"""
import tempfile
import unittest
from pathlib import Path

from fixtures import SCRIPTS, SKILL_DIR, CLEAN_RESUME, build_text, resume_with, run

OKF = SCRIPTS / "okf.py"
EXAMPLE = SKILL_DIR / "schema" / "example.resume.json"
BODY = "Cut order-processing latency 62 percent by decomposing a monolithic service."

SUBCOMMANDS = ["doctor", "new", "validate", "render", "check", "score", "fit"]


class Usage(unittest.TestCase):
    """Called with nothing useful, it must say what it can do - and exit 2, the
    documented code for "you called it wrong"."""

    def test_help_lists_every_subcommand(self):
        code, out = run(OKF, "--help")
        self.assertEqual(code, 2, out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)

    def test_bare_invocation_is_help(self):
        code, out = run(OKF)
        self.assertEqual(code, 2, out)
        self.assertIn("okf check", out)

    def test_unknown_subcommand_names_the_real_ones(self):
        code, out = run(OKF, "frobnicate")
        self.assertEqual(code, 2, out)
        self.assertIn("unknown command: frobnicate", out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)


class ValidateRouting(unittest.TestCase):
    """`okf validate` dispatches on what the target actually is, because a record and
    a bundle are checked by different scripts and people should not have to know
    which."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_json_routes_to_the_record_validator(self):
        code, out = run(OKF, "validate", EXAMPLE, "--level", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)

    def test_flags_are_forwarded_unchanged(self):
        """--level is the underlying script's flag; the dispatcher must not eat it."""
        code, out = run(OKF, "validate", EXAMPLE, "--level", "99")
        self.assertNotEqual(code, 0, out)

    def test_missing_target_is_a_usage_error(self):
        code, out = run(OKF, "validate", self.tmp / "nope.json")
        self.assertEqual(code, 2, out)
        self.assertIn("file not found", out)

    def test_unvalidatable_target_says_what_it_wanted(self):
        stray = self.tmp / "notes.txt"
        stray.write_text("not a record", encoding="utf-8")
        code, out = run(OKF, "validate", stray)
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_validate_with_no_target(self):
        code, out = run(OKF, "validate")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)


class Check(unittest.TestCase):
    """`okf check` runs both document gates on one file. It must run both even when
    the first fails - a document with parse problems can have prose problems too, and
    seeing them in one pass is the whole point."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def document(self, paragraphs=None, name="resume.txt"):
        """The .txt: the one artefact both gates read, so `okf check` can still
        run them in a single pass now that check_ats.py reads the PDF and
        check_prose.py reads the .tex."""
        return build_text(self.tmp / name,
                          CLEAN_RESUME if paragraphs is None else paragraphs)

    def test_clean_resume_passes_both_gates(self):
        code, out = run(OKF, "check", self.document())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to send", out)
        self.assertIn("PASS - prose rules satisfied", out)

    def test_both_gates_are_labelled(self):
        code, out = run(OKF, "check", self.document())
        del code
        self.assertIn("parse gate", out)
        self.assertIn("prose gate", out)

    def test_a_failing_gate_propagates_its_exit_code(self):
        bad = self.document(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = run(OKF, "check", bad)
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)

    def test_the_second_gate_still_runs_after_the_first_fails(self):
        bad = self.document(resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = run(OKF, "check", bad)
        del code
        self.assertIn("prose gate", out)

    def test_passing_both_does_not_imply_the_other_two_gates(self):
        """SKILL.md: "passing one says nothing about the others". A clean parse and
        prose result must not read as a finished resume."""
        code, out = run(OKF, "check", self.document())
        del code
        self.assertIn("okf validate", out)
        self.assertIn("PDF", out)

    def test_strict_reaches_the_parse_gate(self):
        code, out = run(OKF, "check", self.document(), "--strict")
        del code
        self.assertIn("--strict", out)

    def test_check_with_no_target(self):
        code, out = run(OKF, "check")
        self.assertEqual(code, 2, out)
        self.assertIn("usage:", out)


if __name__ == "__main__":
    unittest.main()
