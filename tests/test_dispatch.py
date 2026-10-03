"""`jsk` itself: the noun table, its usage, the in-process dispatch and the flag
parsing every noun shares.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import careerkit
from fixtures import CLI, CLEAN_RESUME, SCRIPTS, build_pdf, build_text, resume_with, run
from test_resume_check import BODY, GOOD


JSK = CLI


SUBCOMMANDS = ["doctor", "kb", "tailor", "resume", "letter", "app"]


class Usage(unittest.TestCase):
    """Called with nothing useful, it must say what it can do.

    The exit code splits on whether the caller asked. `--help` is a question that
    got its answer, so it exits 0; a bare invocation is a call with nothing in it,
    so it stays 2, the documented code for "you called it wrong".

    Both used to return 2, so an agent or a script checking exit codes saw a failure
    for reading the documentation SKILL.md tells it to read.
    """

    def test_help_lists_every_subcommand(self):
        code, out = run(JSK, "--help")
        self.assertEqual(code, 0, out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)

    def test_help_stops_at_its_marker(self):
        """The cut was a literal buried in usage(); it is a named constant now, and the
        docstring is held to it so that rewording the last paragraph cannot silently
        print it as help."""
        from jsk.adapters.cli import main
        self.assertIn(main.HELP_ENDS_BEFORE, main.__doc__)
        code, out = run(JSK, "--help")
        self.assertEqual(code, 0, out)
        self.assertNotIn("markdown-it-py", out)
        self.assertIn("jsk resume check", out)

    def test_bare_invocation_is_help(self):
        code, out = run(JSK)
        self.assertEqual(code, 2, out)
        self.assertIn("jsk resume check", out)

    def test_every_subcommand_answers_help_the_same_way(self):
        """One contract across the surface, whichever kind of command you reached.

        The hand-rolled entry points printed their usage and returned 2, so an agent
        or script checking exit codes saw a failure for reading the documentation
        SKILL.md tells it to read.
        """
        for sub in SUBCOMMANDS:
            with self.subTest(subcommand=sub):
                code, out = run(JSK, sub, "--help")
                self.assertEqual(code, 0, f"jsk {sub} --help exited {code}: {out}")
                self.assertTrue(out.strip(), f"jsk {sub} --help printed nothing")

    def test_render_help_names_its_flags(self):
        """`jsk render --help` printed the two-line invocation and stopped, so the
        flags SKILL.md sends a reader here to look up were documented nowhere the
        command itself would show them."""
        code, out = run(JSK, "resume", "render", "--help")
        self.assertEqual(code, 0, out)
        for flag in ("--pdf", "--ats-max", "--template"):
            self.assertIn(flag, out)

    def test_jsk_index_is_retired_and_says_what_replaced_it(self):
        """It read user-knowledgebase.md. The career is career/kb.ttl now: `jsk match`
        ranks it against a posting, `jsk kb view` reads it. A bare "unknown command" would
        read as a broken install."""
        code, out = run(JSK, "index", "user-knowledgebase.md")
        self.assertEqual(code, 2, out)
        for pointer in ("jsk tailor match", "jsk kb view"):
            self.assertIn(pointer, out)
        from jsk import cli
        self.assertNotIn("index", cli.NOUNS)

    def test_jsk_migrate_is_retired_and_says_what_replaced_it(self):
        """It moved a user-knowledgebase.md to career/kb.ttl. The Markdown format is not
        read any more: `jsk new` starts a record, `jsk kb export` writes a resume.json."""
        code, out = run(JSK, "migrate", "user-knowledgebase.md")
        self.assertEqual(code, 2, out)
        self.assertIn("jsk migrate was retired", out)
        for pointer in ("jsk kb new", "jsk kb export"):
            self.assertIn(pointer, out)
        from jsk import cli
        self.assertNotIn("migrate", cli.NOUNS)

    def test_unknown_subcommand_names_the_real_ones(self):
        code, out = run(JSK, "frobnicate")
        self.assertEqual(code, 2, out)
        self.assertIn("unknown command: frobnicate", out)
        for sub in SUBCOMMANDS:
            self.assertIn(sub, out)


def in_process(*argv):
    """(exit code, stdout) of cli.main() called in this interpreter.

    The dispatch is in-process now, so the tests that pin it call it the same way -
    which is also the only way a patched compile_pdf can reach the renderer.
    """
    from jsk import cli
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(["jsk"] + [str(a) for a in argv])
    return code, buf.getvalue()


class InProcessDispatch(unittest.TestCase):
    """Every subcommand calls its script in this interpreter.

    Each one used to spawn a child, and `jsk check` spawned two: a Python start-up
    and a fresh import of the package per gate, for work that takes a fraction of
    that. What has to survive the change is what the child gave for free - the exit
    code, and every heading landing above the output it introduces.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_cli_spawns_nothing(self):
        """The one exception, preflight's end-to-end run, lives in preflight.py and
        says why there. cli.py itself has no reason left to import subprocess."""
        source = (SCRIPTS / "cli.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("def run(", source)

    def test_check_spawns_no_child(self):
        doc = build_text(self.tmp / "resume.txt", CLEAN_RESUME)
        with mock.patch("subprocess.Popen", side_effect=AssertionError("spawned")):
            code, out = in_process("resume", "check", doc)
        self.assertEqual(code, 0, out)

    def test_each_heading_is_above_the_output_it_introduces(self):
        """The ordering a child interpreter needed a flush for. A heading printed
        after its gate's output would put every verdict under the wrong section."""
        code, out = run(JSK, "resume", "check", build_text(self.tmp / "resume.txt", CLEAN_RESUME))
        self.assertEqual(code, 0, out)
        parse = out.index("--- parse gate")
        prose = out.index("--- prose gate")
        self.assertLess(parse, out.index("mode: presentation"))
        self.assertLess(out.index("mode: presentation"), prose)
        self.assertLess(prose, out.index("PASS - prose rules satisfied"))

    def test_a_failing_gate_keeps_its_exit_code_in_process(self):
        bad = build_text(self.tmp / "resume.txt",
                         resume_with((BODY, "Scaled the platform to [NUMBER] tenants.")))
        code, out = in_process("resume", "check", bad)
        self.assertEqual(code, 1, out)
        self.assertIn("DO NOT SEND", out)

    def test_a_bare_sys_exit_is_a_clean_exit(self):
        """argparse's --help exits by raising SystemExit(0), and a bare sys.exit()
        raises it with None. Both are exit 0 from a child interpreter, and reading
        None as a failure would turn `jsk fit --help` into one."""
        from jsk import cli
        fake = mock.Mock(main=mock.Mock(side_effect=SystemExit(None)))
        with mock.patch("importlib.import_module", return_value=fake):
            code, _ = cli.call_gate("kb.py", [])
        self.assertEqual(code, 0)

    def test_fit_help_still_names_its_own_program(self):
        """In process, sys.argv[0] is jsk's, and argparse would have printed that as
        the program name in fit_pages.py's usage line."""
        code, out = run(JSK, "resume", "fit", "--help")
        self.assertEqual(code, 0, out)
        self.assertIn("usage: jsk resume fit", out)

    def test_a_script_that_raises_is_reported_not_propagated(self):
        fake = mock.Mock(main=mock.Mock(side_effect=RuntimeError("boom")))
        with mock.patch("importlib.import_module", return_value=fake):
            code, out = in_process("resume", "render", "x.json")
        self.assertEqual(code, 2, out)
        self.assertIn("render_resume.py raised RuntimeError: boom", out)
        self.assertIn("jsk resume render x.json", out)


class PreviewInProcess(unittest.TestCase):
    """`jsk preview` renders every template in this interpreter and compiles them
    at once. The compile is faked here, so none of this needs a TeX engine: what is
    pinned is the plumbing - separate stages, and a report in template order however
    the compiles happen to finish."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _, self.record = careerkit.workspace(self.tmp / "ws", short=GOOD)
        self.out = self.tmp / "looks"

    def preview(self, compile_pdf):
        from jsk.adapters.cli.compose import preview
        with mock.patch.object(preview, "available_engine",
                               return_value="fake"), \
                mock.patch.object(preview, "compile_pdf", compile_pdf), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("spawned")):
            return in_process("resume", "preview", self.record, "--out", self.out)

    def test_the_report_is_in_template_order_whatever_finishes_first(self):
        """The first template is made the slowest to compile. A report that followed
        completion order would list it last."""
        import threading
        import time
        from jsk.infra import tex; from jsk.domain.render import themes
        names = themes.names()
        stages, lock = set(), threading.Lock()

        def slow_first(tex_path, out_dir):
            with lock:
                stages.add(out_dir)
            if os.path.basename(tex_path).startswith(names[0] + "_"):
                time.sleep(0.3)
            return build_pdf(tex.pdf_path_for(tex_path, out_dir), CLEAN_RESUME), "fake"

        code, out = self.preview(slow_first)
        self.assertEqual(code, 0, out)
        listed = [line.split()[0] for line in out.splitlines()
                  if line.startswith("  ") and line.split()[0] in names]
        self.assertEqual(listed, names, out)
        self.assertEqual(len(stages), len(names), "two templates shared a stage")
        for name in names:
            self.assertTrue((self.out / f"{name}.pdf").exists(), name)
            self.assertTrue((self.out / f"{name}.tex").exists(), name)

    def test_a_template_that_does_not_compile_fails_the_preview(self):
        from jsk.infra import tex; from jsk.domain.render import themes
        broken = themes.names()[1]

        def one_broken(tex_path, out_dir):
            if os.path.basename(tex_path).startswith(broken + "_"):
                return None, "UNVERIFIED - fake produced no PDF:\n    ! Missing $"
            return build_pdf(tex.pdf_path_for(tex_path, out_dir), CLEAN_RESUME), "fake"

        code, out = self.preview(one_broken)
        self.assertEqual(code, 1, out)
        self.assertIn(f"FAILED: {broken}", out)
        self.assertIn("! Missing $", out)

    def test_a_file_that_does_not_load_is_said_once_not_blamed_on_the_templates(self):
        """A legacy record fails the same way in every template; five FAILED blocks and
        "a template that does not build" sent the reader after the templates."""
        Path(self.record).write_text(json.dumps({"urs": "1.0"}), encoding="utf-8")

        def never(tex_path, out_dir):
            raise AssertionError("compiled a file that does not load")

        code, out = self.preview(never)
        self.assertEqual(code, 2, out)
        self.assertEqual(out.count("full URS record"), 1, out)
        self.assertIn("jsk kb export", out)
        self.assertNotIn("FAILED", out)
        self.assertNotIn("template that does not build", out)


class ParseFlags(unittest.TestCase):
    """The one argument parser every hand-written entry point shares."""

    def parse(self, *args, **kinds):
        from jsk.adapters.cli.cliutil import parse_flags
        return parse_flags(list(args), kinds.pop("values", ()), **kinds)

    def test_an_unknown_flag_is_refused_by_name(self):
        self.assertEqual(self.parse("x", "--nope"), (None, "unknown flag: --nope"))

    def test_a_value_may_start_with_a_dash(self):
        self.assertEqual(self.parse("--quote", "-40% cost", values=("--quote",)),
                         (([], {"--quote": "-40% cost"}), None))

    def test_a_lone_dash_is_positional_only_where_asked(self):
        """kb apply answers `-` (stdin is refused); jsk gates or ship reading `-` as a
        path would fail further in, on a file that is not there."""
        self.assertEqual(self.parse("-", dash=True), ((["-"], {}), None))
        self.assertEqual(self.parse("-"), (None, "unknown flag: -"))

    def test_a_value_flag_given_twice_is_refused(self):
        """Keeping the last dropped the first without a word: `--answer A --answer B`
        logged B as what the person said."""
        parsed, problem = self.parse("--answer", "A", "--answer", "B", values=("--answer",))
        self.assertIsNone(parsed)
        self.assertEqual((problem, problem.kind, problem.flag),
                         ("--answer given twice - pass it once", "repeated", "--answer"))

    def test_after_a_double_dash_everything_is_positional(self):
        """So `jsk kb query similar -- -40% cost cut` can say what it means."""
        self.assertEqual(self.parse("similar", "--", "-40%", "--json"),
                         ((["similar", "-40%", "--json"], {}), None))

    def test_a_problem_names_its_kind_and_flag(self):
        _, problem = self.parse("--out", values=("--out",))
        self.assertEqual((problem.kind, problem.flag), ("missing", "--out"))

    def test_a_list_runs_to_the_next_flag(self):
        self.assertEqual(self.parse("--select", "a", "b,c", "--out", "f", "d",
                                    values=("--out",), lists=("--select",)),
                         ((["d"], {"--select": ["a", "b,c"], "--out": "f"}), None))
        self.assertEqual(self.parse("--select", lists=("--select",)),
                         (([], {"--select": []}), None))


if __name__ == "__main__":
    unittest.main()
