"""`jsk kb` itself: its verb table and the flags it does not know."""
import contextlib
import io
import os
import re
import unittest

from storekit import Workspace

from jsk import cli


class Dispatch(Workspace):
    def test_help_lists_the_verbs_and_exits_0(self):
        code, out = self.kb("--help")
        self.assertEqual(code, 0)
        # The retired verbs are named in the closing paragraph, not listed as verbs.
        self.assertIn("`jsk kb apply|confirm|show|view|query|log|export|path` were retired", out)
        self.assertIn("pack capabilities [--out FILE]", out)
        verbs = re.findall(r"^  (\w+)", out, re.M)
        self.assertEqual(verbs, ["new", "pack", "merge", "check", "load", "dump"])
        from jsk.adapters.cli import kb as kbcli
        self.assertEqual(sorted([*kbcli.VERBS, "new"]), sorted(verbs))

    def test_an_unknown_verb(self):
        code, out = self.kb("chek")
        self.assertEqual(code, 2)
        self.assertIn("unknown verb: chek", out)

    def test_the_workspace_is_found_from_inside_it(self):
        self.seed()
        here = os.getcwd()
        os.chdir(self.path("applications"))
        self.addCleanup(os.chdir, here)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "check"])
        self.assertEqual(code, 0, out.getvalue())


class UnknownFlags(Workspace):
    """A flag a verb does not take is refused by name. Every verb used to lift its own
    flags out by name and leave the rest as arguments, so a mistyped one was caught only
    when the count came out wrong - and then as "takes one changeset", not as the typo."""

    CALLS = [("load", "x.trig"), ("dump",), ("pack", "capabilities"),
             ("merge", "c:kafka", "--into", "c:python"), ("check",)]

    def test_each_verb_names_the_flag(self):
        for call in self.CALLS:
            with self.subTest(verb=call[0]):
                code, out = self.kb(*call, "--no-such-flag")
                self.assertEqual(code, 2, out)
                self.assertIn("unknown flag: --no-such-flag", out)


if __name__ == "__main__":
    unittest.main()
