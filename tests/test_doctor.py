"""`jsk doctor` on a workspace, and the refusal every noun gives one with no store."""
import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path

from jsk import cli


class UnloadedWorkspace(unittest.TestCase):
    """Plan P5: a workspace still laid out as files - career/kb.ttl, no career/store/ - is
    refused by every command, with the one fix that imports it."""

    def setUp(self):
        import shutil
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(Path(__file__).parent / "match_fixtures", self.root, dirs_exist_ok=True)

    def jsk(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["jsk", *map(str, args)])
        return code, buf.getvalue()

    def test_a_command_given_a_path_in_it_is_refused_with_kb_load(self):
        for args in (("resume", "check", self.root / "applications" / "contoso"),
                     ("app", "drop", self.root / "applications" / "contoso", "--dry-run")):
            with self.subTest(args=args[0]):
                code, out = self.jsk(*args)
                self.assertEqual(code, 1, out)
                self.assertIn("the career is still career/kb.ttl", out)
                self.assertIn("fix:  jsk kb load .", out)

    def test_every_kb_verb_but_load_and_path_is_refused_with_kb_load(self):
        from jsk.adapters.cli import kb as kbcli
        for verb in sorted(set(kbcli.VERBS) - {"load", "path"}):
            with self.subTest(verb=verb):
                code, out = self.jsk("kb", verb, "--root", self.root)
                self.assertEqual(code, 1, out)
                self.assertIn("the career is still career/kb.ttl", out)
                self.assertIn("fix:  jsk kb load .", out)
        self.assertFalse((self.root / "career" / "store").exists(), "nothing was imported")

    def test_a_command_run_inside_it_is_refused(self):
        here = os.getcwd()
        try:
            os.chdir(self.root / "applications")
            code, out = self.jsk("resume", "check", "resume.json")
        finally:
            os.chdir(here)
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb load .", out)

    def test_a_loaded_workspace_is_not(self):
        from appkit import seed
        seed(self.root)
        (self.root / "career" / "kb.ttl").write_text("# left by kb load\n", encoding="utf-8")
        code, out = self.jsk("resume", "check", self.root / "applications" / "contoso")
        # The gates find no render in it; what matters is that the workspace was let in.
        self.assertNotIn("the career is still career/kb.ttl", out)
        self.assertIn("--- record gate", out)

    def test_the_helper_the_kb_verbs_call(self):
        self.assertIsNotNone(cli.unloaded_refusal(str(self.root)))
        self.assertIsNone(cli.unloaded_refusal(None))
        from jsk import paths
        # The shipped example too: whatever reads it imports it first, as doctor does.
        self.assertIsNotNone(cli.unloaded_refusal(paths.EXAMPLE_WORKSPACE))


class DoctorStore(unittest.TestCase):
    """`jsk doctor`'s lines on the record: the store, its revision, the backup's."""

    def setUp(self):
        import shutil
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(Path(__file__).parent / "graph_fixtures", self.root, dirs_exist_ok=True)

    def test_a_store_its_revision_and_its_backup(self):
        from appkit import seed
        seed(self.root)
        lines, broken = cli.store_report(str(self.root))
        text = "\n".join(lines)
        self.assertFalse(broken, text)
        self.assertIn(f"ok    store    {self.root / 'career' / 'store'}", text)
        self.assertRegex(text, r"readable, at r\d+")
        self.assertIn("ok    backup", text)
        revision = re.search(r"readable, at (r\d+)", text).group(1)
        self.assertIn(f"at {revision}\n", text + "\n")

    def test_no_backup_is_a_gap(self):
        from appkit import seed
        seed(self.root)
        (self.root / ".jsk" / "backup.trig").unlink()
        lines, broken = cli.store_report(str(self.root))
        self.assertFalse(broken)
        self.assertIn("no .jsk/backup.trig yet", "\n".join(lines))

    def test_a_workspace_not_yet_loaded_fails_with_kb_load(self):
        lines, broken = cli.store_report(str(self.root))
        self.assertTrue(broken)
        self.assertIn("jsk kb load .", "\n".join(lines))

    def test_doctor_prints_them_after_the_preflight(self):
        from appkit import seed
        seed(self.root)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["jsk", "doctor", "--quick", "--kb", str(self.root)])
        out = buf.getvalue()
        self.assertIn("\nThe record:\n", out)
        self.assertIn("ok    store", out)


if __name__ == "__main__":
    unittest.main()
