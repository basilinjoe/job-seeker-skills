"""`jsk doctor` on a workspace, and the refusal every noun gives one with no store."""
import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path

from jsk import cli
from jsk.adapters.cli.doctor import store_report
from jsk.application.guards import unloaded_refusal


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

    def test_kb_dump_is_refused_with_kb_load(self):
        # resume_check and app_drop were commands that gave this refusal until 2026-10-04;
        # test_mcp_rendering and test_mcp_upkeep pin it for each tool. Of the kb verbs only
        # dump still reads a career, so only it can be refused here (check, pack and merge
        # exit 2 naming their tools, which tests/test_retired.py pins).
        code, out = self.jsk("kb", "dump", "--root", self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("the career is still career/kb.ttl", out)
        self.assertIn("fix:  jsk kb load .", out)
        self.assertFalse((self.root / "career" / "store").exists(), "nothing was imported")

    def test_a_command_run_inside_it_is_refused(self):
        here = os.getcwd()
        try:
            os.chdir(self.root / "applications")
            code, out = self.jsk("kb", "dump")
        finally:
            os.chdir(here)
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb load .", out)

    def test_a_loaded_workspace_is_not(self):
        from appkit import seed
        seed(self.root)
        (self.root / "career" / "kb.ttl").write_text("# left by kb load\n", encoding="utf-8")
        code, out = self.jsk("kb", "dump", "--root", self.root)
        # What matters is that the workspace was let in, not what dump wrote.
        self.assertNotIn("the career is still career/kb.ttl", out)
        self.assertEqual(code, 0, out)

    def test_the_helper_the_kb_verbs_call(self):
        self.assertIsNotNone(unloaded_refusal(str(self.root)))
        self.assertIsNone(unloaded_refusal(None))
        from jsk import paths
        # The shipped example too: whatever reads it imports it first, as doctor does.
        self.assertIsNotNone(unloaded_refusal(paths.EXAMPLE_WORKSPACE))


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
        lines, broken = store_report(str(self.root))
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
        lines, broken = store_report(str(self.root))
        self.assertFalse(broken)
        self.assertIn("no .jsk/backup.trig yet", "\n".join(lines))

    def test_a_workspace_not_yet_loaded_fails_with_kb_load(self):
        lines, broken = store_report(str(self.root))
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
