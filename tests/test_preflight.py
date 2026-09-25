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

from fixtures import PLUGIN, PREFLIGHT, load_script, run, urs_module

preflight = load_script(PREFLIGHT)
tex = urs_module("urs.tex")

# Without a TeX engine preflight is BLOCKED by design - the PDF is the deliverable - so a
# test that expects a passing verdict needs one. These ran nowhere without an engine
# until the no-engine CI jobs stopped failing at their preflight step (graph core, P1).
NEEDS_TEX = unittest.skipUnless(tex.available_engine(), "needs a TeX engine: preflight blocks without one")
# The exit code a plain preflight earns on this machine: 1 is BLOCKED, which is what a
# machine with no engine is.
VERDICT = 0 if tex.available_engine() else 1


class KnowledgeBaseDiscovery(unittest.TestCase):
    """The career is one file, `career/kb.ttl`, so finding it is finding that file.

    A bundle used to be recognised by the directories inside it, which meant a
    half-created one was invisible here and reported as "no bundle" while the person
    was looking straight at it. A filename cannot be half-present.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_kb(self, parent, name="my-career"):
        root = parent / name / "career"
        root.mkdir(parents=True)
        path = root / "kb.ttl"
        path.write_text("k:kb j:format 3 .", encoding="utf-8")
        return path

    def make_markdown(self, parent, name="my-career"):
        root = parent / name
        root.mkdir(parents=True, exist_ok=True)
        path = root / "user-knowledgebase.md"
        path.write_text("# Career knowledge base", encoding="utf-8")
        return path

    def test_finds_the_graph_record_by_name(self):
        path = self.make_kb(self.tmp)
        self.assertEqual(Path(preflight.find_kb(self.tmp)), path)

    def test_a_kb_ttl_outside_a_career_folder_is_not_one(self):
        (self.tmp / "notes").mkdir()
        (self.tmp / "notes" / "kb.ttl").write_text("", encoding="utf-8")
        self.assertIsNone(preflight.find_kb(self.tmp))

    def test_a_markdown_knowledge_base_is_not_the_record(self):
        """It is still found - to be pointed at `jsk migrate` - but never as the record."""
        path = self.make_markdown(self.tmp)
        self.assertIsNone(preflight.find_kb(self.tmp))
        self.assertEqual(Path(preflight.find_markdown_kb(self.tmp)), path)

    def test_a_migrated_workspace_is_its_graph_record(self):
        self.make_markdown(self.tmp)
        path = self.make_kb(self.tmp)
        self.assertEqual(preflight.resolve_kb(str(self.tmp / "my-career")),
                         (str(path), None, None))
        md = self.tmp / "my-career" / "user-knowledgebase.md"
        self.assertEqual(preflight.resolve_kb(str(md)), (str(path), None, None))

    def test_kb_names_only_a_career_record(self):
        """`--kb pyproject.toml` reported "ok knowledge base", `--kb README.md` called it
        a Markdown knowledge base not yet migrated, and a path that does not exist said
        there was nothing to render from yet. Each is refused for what it is."""
        (self.tmp / "pyproject.toml").write_text("[project]", encoding="utf-8")
        (self.tmp / "README.md").write_text("# readme", encoding="utf-8")
        (self.tmp / "empty").mkdir()
        for name, words in (("pyproject.toml", "is not a career record"),
                            ("README.md", "is not a career record"),
                            ("nonexistent", "does not exist"),
                            ("empty", "not a career workspace")):
            with self.subTest(name=name):
                checks, found = preflight.gather(str(self.tmp / name))
                kb = next(c for c in checks if c.name.startswith("knowledge base"))
                self.assertFalse(kb.ok)
                self.assertIsNone(found)
                self.assertIn(words, kb.disables)
                self.assertNotIn("nothing to render from", kb.disables)

    def test_the_record_path_is_printed_once(self):
        path = self.make_kb(self.tmp)
        code, out = run(PREFLIGHT, "--kb", path)
        self.assertEqual(out.count(str(path)), 1, out)

    def test_a_directory_with_no_knowledge_base_is_not_one(self):
        (self.tmp / "notacareer" / "projects").mkdir(parents=True)
        self.assertIsNone(preflight.find_kb(self.tmp))
        self.assertIsNone(preflight.find_markdown_kb(self.tmp))

    def test_a_differently_named_markdown_file_is_not_one(self):
        """Every other .md in a career folder - a posting, a log, a draft - would
        otherwise be reported as the knowledge base by whichever one os.walk saw
        first."""
        (self.tmp / "career").mkdir()
        (self.tmp / "career" / "resume.md").write_text("draft", encoding="utf-8")
        self.assertIsNone(preflight.find_markdown_kb(self.tmp))

    def test_dot_directories_are_not_searched(self):
        """`.jsk/kb.last.ttl` is a cache, and a .git folder holds old copies."""
        self.make_kb(self.tmp / ".hidden")
        self.assertIsNone(preflight.find_kb(self.tmp))

    def test_search_does_not_descend_forever(self):
        deep = self.tmp / "a" / "b" / "c" / "d"
        self.make_kb(deep)
        self.assertIsNone(preflight.find_kb(self.tmp))


class AMarkdownKnowledgeBaseIsPointedAtMigrate(unittest.TestCase):
    """A user-knowledgebase.md with no kb.ttl beside it is a gap, never a FAIL: the
    render path starts at resume.json and still works, and blocking on it would hide
    every other finding behind one migration."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.md = self.tmp / "user-knowledgebase.md"
        self.md.write_text("# Career knowledge base", encoding="utf-8")

    def test_it_is_a_gap_naming_migrate(self):
        checks, found = preflight.gather(str(self.md))
        kb = next(c for c in checks if c.name.startswith("knowledge base"))
        self.assertFalse(kb.ok)
        self.assertFalse(preflight.is_required(kb))
        self.assertIn(f"jsk migrate {self.md}", kb.disables)
        self.assertEqual(found, str(self.md))

    def test_json_reports_it_apart_from_the_record(self):
        code, out = run(PREFLIGHT, "--kb", self.md, "--json")
        self.assertEqual(code, VERDICT, out)
        payload = json.loads(out)
        self.assertIsNone(payload["knowledge_base"])
        self.assertEqual(Path(payload["markdown_knowledge_base"]), self.md)


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
        self.assertTrue(any(n.startswith("profile schema") for n in required))

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
        # A TeX engine is the machine's, not the plugin's - it is installed beside jsk.
        checks, _ = preflight.gather()
        for check in checks:
            if preflight.is_required(check) and not check.name.startswith("TeX engine"):
                self.assertTrue(check.ok, f"{check.name}: {check.disables}")


class CliBehaviour(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    @NEEDS_TEX
    def test_plain_run_reports_a_verdict(self):
        code, out = run(PREFLIGHT)
        self.assertEqual(code, 0, out)
        self.assertTrue(any(v in out for v in ("READY", "READY, with gaps")), out)

    @NEEDS_TEX
    def test_verify_runs_the_pipeline_and_every_gate(self):
        code, out = run(PREFLIGHT, "--verify")
        self.assertEqual(code, 0, out)
        for step in ("validate the example resume", "render the example to a PDF",
                     "parse gate, rendered PDF",
                     "parse gate, plain text (strict)", "prose gate"):
            self.assertIn(step, out)
        self.assertNotIn("FAIL", out)

    def test_verify_renders_the_example_workspace_s_short_file(self):
        """doctor renders the resume the way a person's is rendered: a short resume.json
        built from a career, not a record copied out of one."""
        from unittest import mock

        from jsk import paths, preflight
        calls = []

        def fake(args, **_):
            calls.append(args)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(preflight.subprocess, "run", fake):
            preflight.verify(str(self.tmp))
        render = next(c for c in calls if any("render_resume" in a for a in c))
        self.assertIn(paths.EXAMPLE_SHORT, render)
        self.assertNotIn("--view", render)

    def test_verify_validates_the_short_file_not_the_legacy_record(self):
        """The validate step read example.resume.json - a URS record nothing renders any
        more - so doctor passed a check on a file the render never touched."""
        from unittest import mock

        from jsk import paths, preflight
        calls = []

        def fake(args, **_):
            calls.append(args)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(preflight.subprocess, "run", fake):
            steps = preflight.verify(str(self.tmp))
        check = next(c for c in calls if any("gates.record" in a for a in c))
        self.assertIn(paths.EXAMPLE_SHORT, check)
        self.assertFalse(any("validate_urs" in a for c in calls for a in c))
        self.assertEqual(steps[0][0], "validate the example resume")
        self.assertEqual(len(steps), 5)

    def test_json_output_is_machine_readable(self):
        code, out = run(PREFLIGHT, "--json")
        self.assertEqual(code, VERDICT, out)
        payload = json.loads(out)
        self.assertIn("checks", payload)
        self.assertTrue(all({"name", "ok", "required", "disables"} <= set(c)
                            for c in payload["checks"]))

    @NEEDS_TEX
    def test_json_verify_reports_each_step(self):
        code, out = run(PREFLIGHT, "--json", "--verify")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["verify"]), 5)

    def test_kb_override_is_honoured(self):
        path = self.tmp / "mine" / "career" / "kb.ttl"
        path.parent.mkdir(parents=True)
        path.write_text("k:kb j:format 3 .", encoding="utf-8")
        code, out = run(PREFLIGHT, "--kb", path, "--json")
        self.assertEqual(code, VERDICT, out)
        self.assertEqual(Path(json.loads(out)["knowledge_base"]), path)

    def test_help_prints_usage_and_checks_nothing(self):
        """`jsk doctor --help` ran the whole preflight - with --verify, a real render -
        and exited 1 wherever there was no TeX engine, so reading the documentation
        looked like a failure. Help is the usage, and nothing is checked."""
        for flag in ("--help", "-h"):
            code, out = run(PREFLIGHT, flag)
            self.assertEqual(code, 0, out)
            self.assertIn("Usage:", out)
            self.assertNotIn("jsk preflight", out)      # the report's header

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


class SetupIsWiredUp(unittest.TestCase):
    """The slash command is the entry point and the mode file holds the procedure, so
    the wiring between them and the order inside the procedure are worth pinning."""

    def setUp(self):
        self.command = PLUGIN / "commands" / "setup.md"
        self.mode = PLUGIN / "skills" / "jsk" / "references" / "mode-setup.md"

    def fenced(self, path):
        import re
        body = path.read_text(encoding="utf-8")
        return "\n".join(re.findall(r"^```(?:bash)?\n(.*?)^```", body, re.M | re.S))

    def test_the_command_file_exists_where_plugins_look_for_it(self):
        self.assertTrue(self.command.exists(), self.command)

    def test_it_declares_a_description(self):
        head = self.command.read_text(encoding="utf-8").split("---")[1]
        self.assertIn("description:", head)

    def test_the_command_loads_setup_mode(self):
        self.assertIn('Skill(skill="jsk:jsk", args="setup")',
                      self.command.read_text(encoding="utf-8"))

    def test_it_runs_preflight_before_anything_else(self):
        """Bare `jsk doctor` is the verifying run - cmd_doctor adds --verify unless
        given --quick - so the first command the procedure runs must be exactly that.
        Prose may still mention `--quick`; what is pinned is what gets run first."""
        import re
        first = re.search(r"^jsk .*$", self.fenced(self.mode), re.M)
        self.assertIsNotNone(first, "mode-setup.md runs no jsk command")
        self.assertEqual(first.group(0).strip(), "jsk doctor",
                         "setup must run the verifying preflight first, not the quick one")

    def test_every_command_it_invokes_is_real(self):
        """Each `jsk <verb>` the procedure runs has to be a verb `jsk` dispatches -
        otherwise it sends setup at something that cannot run, and the failure reads
        as a broken install.

        Only fenced blocks are read: prose refers to the product as jsk too, and "Set up
        jsk end to end" would parse as an invocation of `jsk end`.
        """
        import re

        from jsk import cli
        fenced = self.fenced(self.mode)
        named = set(re.findall(r"^jsk ([a-z]+)", fenced, re.M))
        self.assertTrue(named, "the setup command invokes no jsk subcommand")
        known = set(cli.HANDLERS) | set(cli.SIMPLE)
        unknown = sorted(n for n in named if n not in known)
        self.assertEqual(unknown, [], f"setup.md names unknown subcommands: {unknown}")


class TheGraphRecord(unittest.TestCase):
    """P1 of the graph rewrite: a package of its own, and the engine it runs on."""

    def test_the_graph_package_is_required_like_the_other_packages(self):
        checks, _ = preflight.gather()
        graph = next(c for c in checks if c.name == "graph record package")
        self.assertTrue(preflight.is_required(graph))
        self.assertTrue(graph.ok, graph.disables)

    def test_the_engine_is_required(self):
        """The career is kb.ttl and `jsk ship` runs the record gate against it before
        it renders, so a machine without the engine cannot produce a resume from the
        career. It used to be reported as a gap."""
        checks, _ = preflight.gather()
        engine = next(c for c in checks if c.name == "pyoxigraph")
        self.assertTrue(preflight.is_required(engine))
        self.assertIn("kb.ttl", engine.disables)
        line, note = preflight.hint("pyoxigraph")
        self.assertIn("-m pip install pyoxigraph", line)
        self.assertTrue(note)

    def test_the_floor_is_python_3_10(self):
        self.assertEqual(preflight.MIN_PYTHON, (3, 10))


if __name__ == "__main__":
    unittest.main()
