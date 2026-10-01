"""The CLI is `jsk <noun> <verb>` (Ruling 10 of the onion design), and the old names are
retired with a pointer rather than kept as aliases.

Every row of the ruling's mapping table is a test here: the old command exits 2 and names
the new one, with the call's own arguments, and the new one runs. Every noun-verb pair
answers --help from a process of its own, the way an agent first meets it.
"""
import contextlib
import io
import subprocess
import sys
import unittest

from fixtures import child_env

from jsk.adapters.cli import main as M

# (the old call, the new call it names). Ruling 10's table, row by row.
MAPPING = [
    (["new", "my-career", "--name", "Priya"], ["kb", "new", "my-career", "--name", "Priya"]),
    (["match", "applications/acme"], ["tailor", "match", "applications/acme"]),
    (["validate", "resume.json"], ["resume", "check", "resume.json"]),
    (["check", "resume.pdf", "--strict", "--only", "parse"],
     ["resume", "check", "resume.pdf", "--strict", "--only", "parse"]),
    (["check", "letter.txt", "--only", "letter", "--record", "resume.json"],
     ["letter", "check", "letter.txt", "--record", "resume.json"]),
    (["gates", "out", "--record", "resume.json", "--pages", "2", "--json"],
     ["resume", "check", "out", "--record", "resume.json", "--pages", "2", "--json"]),
    (["render", "resume.json", "--out", "out"], ["resume", "render", "resume.json", "--out", "out"]),
    (["preview", "resume.json", "--out", "looks"],
     ["resume", "preview", "resume.json", "--out", "looks"]),
    (["fit", "resume.tex", "--target-pages", "2"],
     ["resume", "fit", "resume.tex", "--target-pages", "2"]),
    (["ship", "resume.json", "--out", "out"], ["resume", "ship", "resume.json", "--out", "out"]),
    (["event", "applications/acme", "offer", "--date", "2026-10-01"],
     ["app", "event", "applications/acme", "offer", "--date", "2026-10-01"]),
    (["freeze", "applications/acme", "--submitted", "false"],
     ["app", "freeze", "applications/acme", "--submitted", "false"]),
]

# The commands Ruling 10 leaves as they were.
UNCHANGED = [["kb", "view"], ["posting", "fetch"], ["tailor", "prepare"], ["doctor"]]


def jsk(*argv):
    """(exit code, stdout) of `jsk argv...` run in this interpreter."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = M.main(["jsk", *argv])
    return code, buf.getvalue()


def spawn(*argv):
    """(exit code, stdout and stderr) of `python -m jsk argv...` in a process of its own."""
    proc = subprocess.run([sys.executable, "-m", "jsk", *argv], capture_output=True,
                          text=True, encoding="utf-8", env=child_env(), timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


class EveryOldNameIsRetired(unittest.TestCase):
    def test_each_row_exits_2_and_names_the_new_call(self):
        for old, new in MAPPING:
            with self.subTest(old=" ".join(old)):
                code, out = jsk(*old)
                self.assertEqual(code, 2, out)
                self.assertIn(" was retired: it is jsk " + " ".join(new[:2]), out)
                self.assertIn("fix:  jsk " + " ".join(new), out)

    def test_a_retired_name_with_no_arguments_shows_what_to_pass(self):
        code, out = jsk("validate")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:  jsk resume check resume.json", out)

    def test_each_new_call_runs(self):
        for _, new in MAPPING:
            with self.subTest(new=" ".join(new[:2])):
                code, out = jsk(*new[:2], "--help")
                self.assertEqual(code, 0, out)
                self.assertTrue(out.strip(), out)

    def test_the_unchanged_ones_are_not_retired(self):
        for argv in UNCHANGED:
            with self.subTest(argv=" ".join(argv)):
                code, out = jsk(*argv, "--help")
                self.assertEqual(code, 0, out)
                self.assertNotIn("was retired", out)

    def test_no_retired_name_is_a_noun(self):
        self.assertFalse(set(M.RETIRED) & set(M.NOUNS))


class TheNouns(unittest.TestCase):
    def test_the_help_lists_the_nouns(self):
        code, out = jsk("--help")
        self.assertEqual(code, 0, out)
        for noun in M.NOUNS:
            self.assertIn(f"jsk {noun}", out)

    def test_each_noun_lists_its_verbs(self):
        for noun, verbs in M.NOUNS.items():
            if not verbs:
                continue
            with self.subTest(noun=noun):
                code, out = jsk(noun, "--help")
                self.assertEqual(code, 0, out)
                for verb in verbs:
                    self.assertIn(verb, out)

    def test_a_noun_with_no_verb_is_a_usage_error(self):
        for noun in ("tailor", "resume", "letter", "app"):
            with self.subTest(noun=noun):
                code, out = jsk(noun)
                self.assertEqual(code, 2, out)
                self.assertIn(f"usage: jsk {noun}", out)

    def test_an_unknown_verb_names_the_real_ones(self):
        code, out = jsk("resume", "validate")
        self.assertEqual(code, 2, out)
        self.assertIn("unknown verb: jsk resume validate", out)
        self.assertIn("check, render, preview, fit, ship", out)

    def test_the_kb_verbs_are_the_kb_adapter_s(self):
        from jsk.adapters.cli import kb

        self.assertEqual(set(M.KB_VERBS), set(kb.VERBS))
        self.assertEqual(set(M.NOUNS["kb"]), set(kb.VERBS) | {"new"})


class EveryVerbAnswersHelp(unittest.TestCase):
    """One spawn per noun-verb pair, plus `jsk.cli:main_console`'s module and the doctor."""

    def test_each_noun_verb_pair(self):
        for noun, verbs in M.NOUNS.items():
            for verb in verbs or [None]:
                argv = [noun] + ([verb] if verb else []) + ["--help"]
                with self.subTest(argv=" ".join(argv)):
                    code, out = spawn(*argv)
                    self.assertEqual(code, 0, out)
                    self.assertTrue(out.strip(), out)
                    self.assertNotIn("Traceback", out)

    def test_the_console_script_s_module(self):
        proc = subprocess.run([sys.executable, "-m", "jsk.cli", "--help"], capture_output=True,
                              text=True, encoding="utf-8", env=child_env(), timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("jsk resume check", proc.stdout)


if __name__ == "__main__":
    unittest.main()
