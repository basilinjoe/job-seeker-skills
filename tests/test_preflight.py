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


class BundleDiscovery(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_bundle(self, parent, name="career"):
        root = parent / name
        (root / "projects").mkdir(parents=True)
        (root / "resume-generation").mkdir(parents=True)
        return root

    def test_finds_a_bundle_by_its_two_marker_directories(self):
        root = self.make_bundle(self.tmp)
        self.assertEqual(Path(preflight.find_bundle(self.tmp)), root)

    def test_a_directory_with_only_one_marker_is_not_a_bundle(self):
        (self.tmp / "notabundle" / "projects").mkdir(parents=True)
        self.assertIsNone(preflight.find_bundle(self.tmp))

    def test_dot_directories_are_not_searched(self):
        self.make_bundle(self.tmp / ".hidden")
        self.assertIsNone(preflight.find_bundle(self.tmp))

    def test_search_does_not_descend_forever(self):
        deep = self.tmp / "a" / "b" / "c" / "d" / "e"
        self.make_bundle(deep)
        self.assertIsNone(preflight.find_bundle(self.tmp))


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
        line, _ = preflight.hint("jsonschema")
        self.assertIn("-m pip install jsonschema", line)


class RequiredVersusOptional(unittest.TestCase):
    def test_the_shipped_toolchain_is_required(self):
        checks, _ = preflight.gather()
        required = [c.name for c in checks if preflight.is_required(c)]
        # "modules (12/12)" since these became a package: preflight asks whether each
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

    def test_the_convenience_libraries_are_not_required(self):
        checks, _ = preflight.gather()
        for name in ("pyyaml", "jsonschema"):
            check = next(c for c in checks if c.name.startswith(name))
            self.assertFalse(preflight.is_required(check),
                             f"{name} must not block the core pipeline")

    def test_libreoffice_is_no_longer_probed(self):
        """It rendered the .docx for page measurement. With the .docx gone it has
        no job left, and probing for it would teach people to install it."""
        checks, _ = preflight.gather()
        self.assertFalse([c for c in checks if "ibre" in c.name or "offic" in c.name.lower()])

    def test_an_absent_bundle_does_not_block(self):
        checks, _ = preflight.gather()
        bundle = next(c for c in checks if c.name.startswith("career bundle"))
        self.assertFalse(preflight.is_required(bundle))

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

    def test_bundle_override_is_honoured(self):
        root = self.tmp / "mine"
        (root / "projects").mkdir(parents=True)
        (root / "resume-generation").mkdir(parents=True)
        code, out = run(PREFLIGHT, "--bundle", root, "--json")
        self.assertEqual(code, 0, out)
        self.assertEqual(Path(json.loads(out)["bundle"]), root)

    def test_bundle_flag_without_a_path_is_a_usage_error(self):
        code, out = run(PREFLIGHT, "--bundle")
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
        """`okf doctor` since preflight became a subcommand. Bare `okf doctor` is the
        verifying run - cmd_doctor adds --verify unless given --quick - so the flag
        that used to have to be present is now the one that must be absent."""
        body = self.command.read_text(encoding="utf-8")
        self.assertIn("okf doctor", body)
        self.assertNotIn("okf doctor --quick", body,
                         "setup must run the verifying preflight, not the quick one")
        self.assertLess(body.index("okf doctor"), body.index("mode-setup.md"))

    def test_every_command_it_invokes_is_real(self):
        """It checked that each `scripts/X.py` it named was on disk. The scripts are one
        CLI now, so the equivalent claim is that each `okf <verb>` it names is a verb
        `okf` dispatches - otherwise the command file sends setup at something that
        cannot run, and the failure reads as a broken install."""
        import re

        from jsk_okf import cli
        body = self.command.read_text(encoding="utf-8")
        named = set(re.findall(r"`?okf ([a-z]+)", body))
        self.assertTrue(named, "the setup command invokes no okf subcommand")
        known = set(cli.HANDLERS) | set(cli.SIMPLE)
        unknown = sorted(n for n in named if n not in known)
        self.assertEqual(unknown, [], f"setup.md names unknown subcommands: {unknown}")


if __name__ == "__main__":
    unittest.main()
