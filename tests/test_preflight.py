"""preflight.py tells someone whether this machine can produce a verified resume.

A setup check that reports success it has not established is worse than no check,
because it converts an unknown into a false belief. So these tests pin the two
things that matter: the verdict is earned, and a gap is described by what it
costs rather than by the name of a missing package.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import PLUGIN, PREFLIGHT, load_script, run

preflight = load_script(PREFLIGHT)


class KnowledgeBaseDiscovery(unittest.TestCase):
    """The career is one file, so finding it is finding that file.

    A bundle used to be recognised by the directories inside it, which meant a
    half-created one was invisible here and reported as "no bundle" while the person
    was looking straight at it. A filename cannot be half-present.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_kb(self, parent, name="career"):
        root = parent / name
        root.mkdir(parents=True)
        path = root / "user-knowledgebase.md"
        path.write_text("# Career knowledge base", encoding="utf-8")
        return path

    def test_finds_the_knowledge_base_by_name(self):
        path = self.make_kb(self.tmp)
        self.assertEqual(Path(preflight.find_kb(self.tmp)), path)

    def test_a_directory_with_no_knowledge_base_is_not_one(self):
        (self.tmp / "notacareer" / "projects").mkdir(parents=True)
        self.assertIsNone(preflight.find_kb(self.tmp))

    def test_a_differently_named_markdown_file_is_not_one(self):
        """Every other .md in a career folder - a posting, a log, a draft - would
        otherwise be reported as the knowledge base by whichever one os.walk saw
        first."""
        (self.tmp / "career").mkdir()
        (self.tmp / "career" / "resume.md").write_text("draft", encoding="utf-8")
        self.assertIsNone(preflight.find_kb(self.tmp))

    def test_dot_directories_are_not_searched(self):
        self.make_kb(self.tmp / ".hidden")
        self.assertIsNone(preflight.find_kb(self.tmp))

    def test_search_does_not_descend_forever(self):
        deep = self.tmp / "a" / "b" / "c" / "d" / "e"
        self.make_kb(deep)
        self.assertIsNone(preflight.find_kb(self.tmp))


class GapsAreDescribedByWhatTheyCost(unittest.TestCase):
    def test_every_optional_gap_says_what_it_disables(self):
        checks, _ = preflight.gather()
        for check in checks:
            if check.ok:
                continue
            self.assertTrue(
                check.disables,
                f"{check.name} reports a gap without saying what it costs")

    def test_the_tex_gap_names_the_unverified_consequence(self):
        checks, _ = preflight.gather()
        tex = next(c for c in checks if c.name.startswith("TeX engine"))
        if tex.ok:
            self.skipTest("a TeX engine is installed here")
        self.assertIn("UNVERIFIED", tex.disables)

    def test_install_hints_are_platform_specific(self):
        line, note = preflight.hint("tex")
        self.assertTrue(line)
        self.assertTrue(note)
        if sys.platform == "win32":
            self.assertIn("winget", line)

    def test_pip_hints_use_the_running_interpreter(self):
        line, _ = preflight.hint("pymupdf")
        self.assertIn("-m pip install pymupdf", line)


class RequiredVersusOptional(unittest.TestCase):
    def test_the_shipped_toolchain_is_required(self):
        checks, _ = preflight.gather()
        required = [c.name for c in checks if preflight.is_required(c)]
        # "modules (4/4)" since these became a package: preflight asks whether each
        # one can be imported, not whether a file of that name is on disk.
        self.assertTrue(any(n.startswith("modules") for n in required))
        self.assertTrue(any(n.startswith("urs renderer") for n in required))
        self.assertTrue(any(n.startswith("URS schema") for n in required))

    def test_the_pdf_toolchain_is_required(self):
        """A TeX engine and pymupdf were survivable while the .docx was the
        portal artefact. The PDF is now the only rendered deliverable, so a
        machine without them cannot produce a resume at all - reporting that as
        a degraded install would say the toolchain works when it does not."""
        checks, _ = preflight.gather()
        for name in ("TeX engine", "pymupdf"):
            check = next(c for c in checks if c.name.startswith(name))
            self.assertTrue(preflight.is_required(check),
                            f"{name} must block: without it there is no deliverable")

    def test_the_retired_convenience_libraries_are_no_longer_probed(self):
        """pyyaml went with the bundle format; jsonschema went with a URS schema that
        never existed - nothing imported it, so it bought a line in this report and
        nothing else. Probing for either would teach people to install it."""
        checks, _ = preflight.gather()
        for name in ("pyyaml", "jsonschema"):
            self.assertFalse([c for c in checks if c.name.startswith(name)],
                             f"{name} is not a dependency of anything any more")

    def test_libreoffice_is_no_longer_probed(self):
        """It rendered the .docx for page measurement. With the .docx gone it has
        no job left, and probing for it would teach people to install it."""
        checks, _ = preflight.gather()
        self.assertFalse([c for c in checks if "ibre" in c.name or "offic" in c.name.lower()])

    def test_an_absent_knowledge_base_does_not_block(self):
        checks, _ = preflight.gather()
        kb = next(c for c in checks if c.name.startswith("knowledge base"))
        self.assertFalse(preflight.is_required(kb))

    def test_the_shipped_install_is_intact(self):
        # If this fails the plugin is broken, not the machine it is running on.
        checks, _ = preflight.gather()
        for check in checks:
            if preflight.is_required(check):
                self.assertTrue(check.ok, f"{check.name}: {check.disables}")


class CliBehaviour(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_plain_run_reports_a_verdict(self):
        code, out = run(PREFLIGHT)
        self.assertEqual(code, 0, out)
        self.assertTrue(any(v in out for v in ("READY", "READY, with gaps")), out)

    def test_verify_runs_the_pipeline_and_every_gate(self):
        code, out = run(PREFLIGHT, "--verify")
        self.assertEqual(code, 0, out)
        for step in ("validate the example record", "render the example to a PDF",
                     "parse gate, rendered PDF",
                     "parse gate, plain text (strict)", "prose gate"):
            self.assertIn(step, out)
        self.assertNotIn("FAIL", out)

    def test_json_output_is_machine_readable(self):
        code, out = run(PREFLIGHT, "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertIn("checks", payload)
        self.assertTrue(all({"name", "ok", "required", "disables"} <= set(c)
                            for c in payload["checks"]))

    def test_json_verify_reports_each_step(self):
        code, out = run(PREFLIGHT, "--json", "--verify")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["verify"]), 5)

    def test_kb_override_is_honoured(self):
        path = self.tmp / "mine" / "user-knowledgebase.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Career knowledge base", encoding="utf-8")
        code, out = run(PREFLIGHT, "--kb", path, "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(Path(json.loads(out)["knowledge_base"]), path)

    def test_kb_flag_without_a_path_is_a_usage_error(self):
        code, out = run(PREFLIGHT, "--kb")
        self.assertEqual(code, 2)
        self.assertIn("needs a path", out)

    def test_no_deprecation_warnings_leak_into_the_report(self):
        # Probing the legacy `fitz` alias printed a PyMuPDF deprecation warning
        # into the middle of a setup report. The check asks about the module
        # fit_pages.py actually imports.
        code, out = run(PREFLIGHT)
        self.assertNotIn("deprecated", out.lower())


class CommandFileIsWiredUp(unittest.TestCase):
    """The slash command is the entry point, so its wiring is worth pinning."""

    def setUp(self):
        self.command = PLUGIN / "commands" / "setup.md"

    def test_the_command_file_exists_where_plugins_look_for_it(self):
        self.assertTrue(self.command.exists(), self.command)

    def test_it_declares_a_description(self):
        head = self.command.read_text(encoding="utf-8").split("---")[1]
        self.assertIn("description:", head)

    def test_it_runs_preflight_before_anything_else(self):
        """`jsk doctor` since preflight became a subcommand. Bare `jsk doctor` is the
        verifying run - cmd_doctor adds --verify unless given --quick - so the flag
        that used to have to be present is now the one that must be absent."""
        body = self.command.read_text(encoding="utf-8")
        self.assertIn("jsk doctor", body)
        self.assertNotIn("jsk doctor --quick", body,
                         "setup must run the verifying preflight, not the quick one")
        self.assertLess(body.index("jsk doctor"), body.index("mode-setup.md"))

    def test_every_command_it_invokes_is_real(self):
        """It checked that each `scripts/X.py` it named was on disk. The scripts are one
        CLI now, so the equivalent claim is that each `jsk <verb>` it names is a verb
        `jsk` dispatches - otherwise the command file sends setup at something that
        cannot run, and the failure reads as a broken install.

        Only fenced blocks are read. The command was renamed from `okf` to `jsk`, which
        is also how the file refers to the product - "Set up jsk end to end" parsed as
        an invocation of `jsk end`, and the fix a person would reach for is to reword
        the prose rather than the check.
        """
        import re

        from jsk import cli
        body = self.command.read_text(encoding="utf-8")
        fenced = "\n".join(re.findall(r"^```(?:bash)?\n(.*?)^```", body, re.M | re.S))
        named = set(re.findall(r"^jsk ([a-z]+)", fenced, re.M))
        self.assertTrue(named, "the setup command invokes no jsk subcommand")
        known = set(cli.HANDLERS) | set(cli.SIMPLE)
        unknown = sorted(n for n in named if n not in known)
        self.assertEqual(unknown, [], f"setup.md names unknown subcommands: {unknown}")


if __name__ == "__main__":
    unittest.main()
