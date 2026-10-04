"""`jsk kb` itself: its verb table and the flags it does not know. The adapter still holds
check, pack and merge, which the career_check, career_pack and career_merge tools call, so the
flag rule is pinned on all five verbs, the three called as the tools call them."""
import os
import re
import unittest

from fixtures import gate
from storekit import Workspace


class Dispatch(Workspace):
    def test_help_lists_the_verbs_and_exits_0(self):
        code, out = self.kb("--help")
        self.assertEqual(code, 0)
        # The retired verbs are named in the closing paragraph, not listed as verbs.
        self.assertIn("`jsk kb apply|confirm|show|view|query|log|export|path` were retired", out)
        # What went to the tools is named by them, not listed as a verb of the command line.
        for tool in ("career_check", "career_pack", "career_merge"):
            self.assertIn(tool, out)
        verbs = re.findall(r"^  (\w+)", out, re.M)
        self.assertEqual(verbs, ["new", "load", "dump"])
        from jsk.adapters.cli import main as M
        self.assertEqual(sorted(M.NOUNS["kb"]), sorted(verbs))

    def test_an_unknown_verb(self):
        code, out = self.kb("chek")
        self.assertEqual(code, 2)
        self.assertIn("unknown verb: chek", out)

    def test_the_workspace_is_found_from_inside_it(self):
        self.seed()
        here = os.getcwd()
        os.chdir(self.path("applications"))
        self.addCleanup(os.chdir, here)
        # No --root: the entry point the career_check tool calls looks for the workspace
        # above the current directory, as `jsk kb check` did.
        code, out = gate("kbcli.py", "check")
        self.assertEqual(code, 0, out)


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
