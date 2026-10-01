"""`jsk kb` itself: its verb table and the flags it does not know."""
import contextlib
import io
import os
import re
import unittest

from storekit import Workspace
from test_kb_write import BRAINDUMP

from jsk import cli


class Dispatch(Workspace):
    def test_help_lists_the_verbs_and_exits_0(self):
        code, out = self.kb("--help")
        self.assertEqual(code, 0)
        self.assertIn("apply <changeset.trig>", out)
        verbs = re.findall(r"^  (\w+)", out, re.M)
        self.assertEqual(verbs, ["new", "apply", "confirm", "show", "view", "query", "pack",
                                 "merge", "export", "check", "path", "load", "dump", "log"])
        from jsk.adapters.cli import kb as kbcli
        self.assertEqual(sorted([*kbcli.VERBS, "new"]), sorted(verbs))

    def test_a_verb_s_help(self):
        code, out = self.kb("apply", "--help")
        self.assertEqual(code, 0)
        self.assertIn("--dry-run prints the diff", out)

    def test_an_unknown_verb(self):
        code, out = self.kb("aply")
        self.assertEqual(code, 2)
        self.assertIn("unknown verb: aply", out)

    def test_the_workspace_is_found_from_inside_it(self):
        self.seed()
        here = os.getcwd()
        os.chdir(self.path("applications"))
        self.addCleanup(os.chdir, here)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "apply", self.changeset(BRAINDUMP), "--dry-run"])
        self.assertEqual(code, 0, out.getvalue())


class UnknownFlags(Workspace):
    """A flag a verb does not take is refused by name. Every verb used to lift its own
    flags out by name and leave the rest as arguments, so a mistyped one was caught only
    when the count came out wrong - and then as "takes one changeset", not as the typo."""

    CALLS = [("apply", "changes.trig"), ("path",), ("load", "x.trig"), ("dump",), ("log",),
             ("confirm", "k:prj_identity", "--answer", "It shipped in March."),
             ("pack", "capabilities"), ("merge", "c:kafka", "--into", "c:python"),
             ("show", "k:prj_identity"), ("view",), ("export", "--select", "prj_identity"),
             ("query", "open"), ("check",)]

    def test_a_quote_may_start_with_a_dash(self):
        # A value is whatever follows its flag, as it was when each verb lifted its own.
        code, out = self.kb("confirm", "k:prj_identity", "--source", "notes.md",
                            "--quote", "-40% in a quarter")
        self.assertEqual(code, 1, out)          # it got as far as looking for the file
        self.assertIn("REFUSED  notes.md", out)

    def test_each_verb_names_the_flag(self):
        for call in self.CALLS:
            with self.subTest(verb=call[0]):
                code, out = self.kb(*call, "--no-such-flag")
                self.assertEqual(code, 2, out)
                self.assertIn("unknown flag: --no-such-flag", out)


if __name__ == "__main__":
    unittest.main()
