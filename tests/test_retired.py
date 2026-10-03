"""6.0 retired the commands that served only applications made from files: P2 of
docs/superpowers/plans/2026-10-03-retire-file-pipeline.md.

Ruling 1: each retired command exits 2 through adapters/cli/main.py's retired table, names
the tool or the target form that replaces it, and writes nothing - never a silent shim and
never "unknown command", which reads as a broken install. A retired noun answers for every
verb it had, and for --help.
"""
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

import careerkit
from jsk import cli
from jsk.adapters.cli import main as M


def jsk(*argv):
    """(exit code, stdout and stderr) of `jsk argv...` run in this interpreter."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(["jsk", *map(str, argv)])
    return code, out.getvalue()


def tree(root):
    """{relative path: bytes} of every file under `root`: what a call must leave alone."""
    found = {}
    for d, _, names in os.walk(root):
        for name in names:
            path = os.path.join(d, name)
            with open(path, "rb") as fh:
                found[os.path.relpath(path, root)] = fh.read()
    return found


# (the retired call, `{app}` its application, what the fix must name).
RETIRED_CALLS = [
    (["posting", "fetch", "https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd",
      "{app}"], "posting_capture"),
    (["posting", "extract", "{app}"], "app_show"),
    (["posting", "build", "{app}"], "posting_decide"),
    (["posting", "build", "{app}", "decisions.txt", "--replace"], "posting_complete"),
    (["posting"], "posting_capture"),
    (["posting", "--help"], "posting_capture"),
    (["tailor", "match", "{app}"], "assessment_derive"),
    (["tailor", "match", "{app}", "--gaps", "{app}/gaps.txt"], "assessment_review"),
    (["tailor", "match", "{app}", "--draft-gaps", "{app}/gaps.txt"], "assessment_derive"),
    (["tailor", "prepare", "{app}", "--draft-gaps"], "assessment_derive"),
    (["tailor"], "assessment_complete"),
    # Ruling 10 of the onion design retired `jsk match` for `jsk tailor match`; 6.0 retired
    # that too, so the older name now names the tool as well.
    (["match", "{app}"], "assessment_derive"),
]


class Retired(unittest.TestCase):
    """Each call in the claims workspace, whose contoso-platform was made from files."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, _ = careerkit.workspace(Path(tmp.name) / "ws", short=careerkit.short())
        self.app = str(Path(self.root) / "applications" / "contoso-platform")
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)

    def test_each_exits_2_names_its_replacement_and_writes_nothing(self):
        for argv, names in RETIRED_CALLS:
            argv = [a.format(app=self.app) for a in argv]
            with self.subTest(call=" ".join(argv[:2])):
                before = tree(self.root)
                code, out = jsk(*argv)
                self.assertEqual(code, 2, out)
                self.assertIn(" was retired: in 6.0", out)
                self.assertIn("fix:  ", out)
                self.assertIn(names, out)
                self.assertNotIn("unknown command", out)
                self.assertEqual(tree(self.root), before, "a retired command writes nothing")

    def test_a_retired_noun_is_no_noun_and_every_verb_it_had_is_named(self):
        for noun in M.RETIRED_NOUNS:
            with self.subTest(noun=noun):
                self.assertNotIn(noun, M.NOUNS)
                self.assertIn(noun, M.RETIRED)
        for noun, verbs in (("posting", ("fetch", "extract", "build")),
                            ("tailor", ("match", "prepare"))):
            for verb in verbs:
                self.assertIn(f"{noun} {verb}", M.RETIRED)


if __name__ == "__main__":
    unittest.main()
