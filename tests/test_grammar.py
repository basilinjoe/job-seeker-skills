"""The CLI is `jsk <noun> <verb>` (Ruling 10 of the onion design) for what stays on the command
line (doctor, kb new|load|dump, mcp), and the old names are retired with a pointer rather than
kept as aliases. Each old top-level name (`validate`, `check`, `gates`, `render`, `preview`,
`fit`, `ship`) exits 2 naming the TOOL of `jsk mcp` that does its work now (2026-10-04,
docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 4); `jsk new` names `jsk kb new`.

Every remaining noun-verb pair answers --help from a process of its own, the way an agent
first meets it. What `resume_check` does with each kind of target, and which flags it refuses,
is pinned here through the entry point the tool calls.
"""
import ast
import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import (CLEAN_RESUME, REPO_ROOT, SCRIPTS, build_text, child_env,
                      example_short, tool_entry)

from jsk.adapters.cli import main as M

# (the old call, the new call it names): the one old name whose replacement is still a command.
MAPPING = [
    (["new", "my-career", "--name", "Priya"], ["kb", "new", "my-career", "--name", "Priya"]),
]

# The old calls whose work is a tool: (the old call, what it is called in the message, the tool
# its fix names). Not a `jsk <noun> <verb>` any more, so no new call runs. The first seven
# went on 2026-10-04 with the resume noun (docs/superpowers/plans/2026-10-04-mcp-first.md,
# Ruling 4); the rest in the plan before it (2026-10-04-retire-duplicated-cli.md, Ruling 2).
TOOLS = [
    (["validate", "resume.json"], "jsk validate", "resume_check"),
    (["check", "resume.pdf", "--strict", "--only", "parse"], "jsk check", "resume_check"),
    (["gates", "out", "--record", "resume.json", "--pages", "2", "--json"], "jsk gates",
     "resume_check"),
    (["render", "resume.json", "--out", "out"], "jsk render", "resume_render"),
    (["preview", "resume.json", "--out", "looks"], "jsk preview", "resume_preview"),
    (["fit", "resume.tex", "--target-pages", "2"], "jsk fit", "resume_fit"),
    (["ship", "resume.json", "--out", "out"], "jsk ship", "resume_ship"),
    (["check", "letter.txt", "--only", "letter", "--record", "resume.json"],
     "jsk check --only letter", "letter_check"),
    (["event", "applications/acme", "offer", "--date", "2026-10-01"], "jsk event", "app_event"),
    (["freeze", "applications/acme", "--submitted", "false"], "jsk freeze", "app_freeze"),
]

# The commands Ruling 10 leaves as they were.
UNCHANGED = [["kb", "load"], ["kb", "dump"], ["doctor"]]


def jsk(*argv):
    """(exit code, stdout) of `jsk argv...` run in this interpreter."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = M.main(["jsk", *map(str, argv)])
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

    def test_a_row_naming_a_tool_names_one_the_server_registers(self):
        """A fix that names a tool the server lacks would send the reader to a third failure."""
        from test_mcp_server import TOOLS as REGISTERED

        for _, _, tool in TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, REGISTERED)

    def test_a_name_whose_work_is_a_tool_now_names_the_tool(self):
        for old, said, tool in TOOLS:
            with self.subTest(old=" ".join(old)):
                code, out = jsk(*old)
                self.assertEqual(code, 2, out)
                self.assertIn(f"{said} was retired", out)
                self.assertIn(f"fix:  the {tool} tool (jsk mcp)", out)

    def test_the_letter_noun_is_retired_whole(self):
        code, out = jsk("letter")
        self.assertEqual(code, 2, out)
        self.assertIn("jsk letter was retired", out)
        self.assertIn("the letter_check tool (jsk mcp)", out)
        self.assertNotIn("letter", M.NOUNS)

    def test_a_retired_name_with_no_arguments_shows_what_to_pass(self):
        code, out = jsk("validate")
        self.assertEqual(code, 2, out)
        self.assertIn("fix:  the resume_check tool (jsk mcp): resume_check(target)", out)

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
        code, out = jsk("kb")
        self.assertEqual(code, 2, out)
        self.assertIn("Usage: jsk kb", out)

    def test_an_unknown_verb_names_the_real_ones(self):
        code, out = jsk("kb", "frobnicate")
        self.assertEqual(code, 2, out)
        self.assertIn("unknown verb: frobnicate", out)
        self.assertIn("load, dump", out)

    def test_the_kb_verbs_are_the_kb_adapter_s(self):
        """The adapter still has check, pack and merge, which the career_* tools call; the
        command line dispatches only the verbs in KB_VERBS, plus `new`."""
        from jsk.adapters.entry import kb

        self.assertEqual(set(M.KB_VERBS) | {"check", "pack", "merge"}, set(kb.VERBS))
        self.assertEqual(set(M.NOUNS["kb"]), set(M.KB_VERBS) | {"new"})


class ResumeCheckByTarget(unittest.TestCase):
    """The resume_check tool's entry point picks its gates from what it is given, and refuses
    a flag that does not fit that kind of target."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.txt = build_text(self.tmp / "resume.txt", CLEAN_RESUME)
        self.json = self.tmp / "resume.json"
        self.json.write_text("{}", encoding="utf-8")

    def test_a_target_gets_the_record_gate(self):
        code, out = tool_entry("resume_check", example_short())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)
        self.assertNotIn("parse gate", out)

    def test_a_render_gets_the_parse_and_prose_gates(self):
        code, out = tool_entry("resume_check", self.txt)
        self.assertEqual(code, 0, out)
        self.assertIn("--- parse gate", out)
        self.assertIn("--- prose gate", out)
        self.assertNotIn("record gate", out)

    def test_a_directory_gets_all_four(self):
        (self.tmp / "out").mkdir()
        code, out = tool_entry("resume_check", self.tmp / "out")
        self.assertEqual(code, 1, out)
        for gate in ("record", "parse", "prose", "layout"):
            self.assertIn(f"--- {gate} gate", out)
        self.assertIn("=== summary", out)

    def test_each_flag_that_does_not_fit_is_a_usage_error_naming_the_kind(self):
        cases = [(example_short(), flag, "a target") for flag in
                 (["--pages", "2"], ["--record", "x.json"], ["--json"], ["--only", "parse"])]
        cases += [(self.txt, flag, "a render") for flag in
                  (["--pages", "2"], ["--record", "x.json"], ["--json"],
                   ["--max-findings", "3"])]
        cases += [(self.tmp, flag, "a render's directory") for flag in
                  (["--strict"], ["--only", "parse"])]
        for target, flag, kind in cases:
            with self.subTest(target=Path(target).name, flag=flag[0]):
                code, out = tool_entry("resume_check", target, *flag)
                self.assertEqual(code, 2, out)
                self.assertIn(f"{flag[0]} does not fit {kind}", out)
                self.assertIn("fix:  resume_check(", out)

    def test_the_layout_gate_keeps_its_own_flags(self):
        code, out = tool_entry("resume_check", self.tmp / "resume.pdf", "--only", "layout",
                        "--record", self.json, "--region", "AU")
        self.assertNotIn("does not fit", out)

    def test_only_letter_points_at_letter_check(self):
        code, out = tool_entry("resume_check", self.txt, "--only", "letter", "--record", self.json)
        self.assertEqual(code, 2, out)
        self.assertIn("fix:  the letter_check tool (jsk mcp)", out)

    def test_the_rerun_hint_for_the_letter_gate_names_the_tools_real_arguments(self):
        # The hint read letter_check(<stem>), which has no such argument: the letter is the
        # first argument and the stem is `record` (the review, 2026-10-04).
        import inspect

        from jsk.adapters.entry.gates.check import COMMANDS
        from jsk.adapters.mcp import server, session

        self.assertEqual(COMMANDS["letter.py"], "letter_check(<letter>, record=<stem>)")
        tool = server.build(session.Session(root=str(self.tmp)))._tool_manager.get_tool(
            "letter_check")
        self.assertEqual(list(inspect.signature(tool.fn).parameters)[:2], ["letter", "record"])

    def test_no_target_is_the_usage_of_all_three(self):
        code, out = tool_entry("resume_check")
        self.assertEqual(code, 2, out)
        self.assertEqual(out.count("resume_check(<"), 3, out)


class TheModulePathsAreRetired(unittest.TestCase):
    """`jsk` is the only door. A module path left importable but silent would exit 0, which
    a script reads as success, so each one names its command and exits 2."""

    PATHS = {
        "jsk.preflight": "jsk doctor",
    }

    def test_each_names_its_command_and_exits_2(self):
        for module, command in self.PATHS.items():
            with self.subTest(module=module):
                proc = subprocess.run([sys.executable, "-m", module, "--help"],
                                      capture_output=True, text=True, encoding="utf-8",
                                      env=child_env(), timeout=300)
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertEqual(proc.stdout.count("\n"), 1, proc.stdout)
                self.assertIn(f"python -m {module} was retired: it is {command}", proc.stdout)

    def test_doctor_runs_without_pyoxigraph(self):
        """`python -m jsk doctor` replaced `python -m jsk.preflight`, which ran on a bare
        machine; with the engine hidden it reports it missing rather than crashing."""
        script = ("import runpy, sys; sys.modules['pyoxigraph'] = None; "
                  "sys.argv = ['jsk', 'doctor', '--quick']; "
                  "runpy.run_module('jsk', run_name='__main__')")
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                  text=True, encoding="utf-8", env=child_env(), cwd=tmp,
                                  timeout=300)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, out)
        self.assertIn("FAIL  pyoxigraph", out)
        self.assertNotIn("Traceback", out)


RETIRED_NAME = re.compile(
    r"\bjsk (new|match|validate|check|gates|render|preview|fit|ship|freeze|event)\b"
    r"|python -m jsk\.\w")

# The commands that became tools on 2026-10-04 (docs/superpowers/plans/2026-10-04-mcp-first.md,
# Ruling 4). Held to what is PRINTED or taught, not to a docstring: a docstring may say that
# `jsk resume check` was retired, and where it went, which names it.
RETIRED_TO_TOOL = re.compile(
    r"\bjsk (resume (check|render|preview|fit|ship)|app drop|kb (check|pack|merge))\b")

# A documented script's name opening an advice line in a printed string: "  check_ats.py X.pdf"
# told the reader to run a program that is no longer a command (2026-10-04, the review of the
# MCP-first change; the tools are resume_check, resume_fit and the rest). Held like
# RETIRED_TO_TOOL: a docstring may name the script it replaced. Indented only: advice was
# printed indented under what it followed, while a step's heading opens its line with the
# script it ran as (application/gates/run_gates.text_step), which is no advice.
SCRIPT_ADVICE = re.compile(
    r"^ {2,}(check_ats|check_prose|render_resume|fit_pages|preview_templates)\.py\s", re.M)

# Where the prose teaches commands: an agent runs what the skill tells it to, and a retired
# name there is a step that exits 2.
DOC_ROOTS = ("plugins", "README.md", "docs/*.md")


def taught_in_strings(path):
    """[(line, the string)] for each string constant in a module that names a retired command.

    Args:
        path: a .py file.

    Returns:
        The offending strings, f-string parts included; comments are not strings, so they are
        not read. A docstring is held to RETIRED_NAME alone: it may name a command that
        became a tool, since saying so is how it records the change.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                       ast.ClassDef))
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)
                  and isinstance(node.body[0].value.value, str)}
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and (RETIRED_NAME.search(node.value)
                 or (id(node) not in docstrings
                     and (RETIRED_TO_TOOL.search(node.value)
                          or SCRIPT_ADVICE.search(node.value))))]


def taught_in_docs(root):
    """[(file, line)] for each line of the prose under `root` that names a retired command.

    Args:
        root: the repository root.

    Returns:
        The offending lines; docs/superpowers/ is history and is not read. RETIRED_TO_TOOL is
        held to plugins/ alone, the prose an agent runs: README.md's 6.0 notes and
        docs/SCRIPTS.md's retired tables name those commands to say where each one went, as
        they name `jsk kb apply` and the rest retired before them.
    """
    found = []
    for pattern in DOC_ROOTS:
        paths = root.glob(pattern) if "*" in pattern else [root / pattern]
        for path in (p for p in paths if p.exists()):
            files = path.rglob("*.md") if path.is_dir() else [path]
            for f in files:
                taught = f.relative_to(root).parts[0] == "plugins"
                for line in f.read_text(encoding="utf-8").splitlines():
                    if RETIRED_NAME.search(line) or (taught and RETIRED_TO_TOOL.search(line)):
                        found.append((f.relative_to(root).as_posix(), line.strip()))
    return found


class RetiredNamesAreNotTaught(unittest.TestCase):
    def test_no_string_in_src_names_a_retired_command(self):
        found = {}
        for path in sorted(SCRIPTS.rglob("*.py")):
            hits = taught_in_strings(path)
            if hits:
                found[path.relative_to(SCRIPTS).as_posix()] = hits
        self.assertEqual(found, {})

    def test_a_planted_one_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "planted.py"
            planted.write_text('HINT = "fix:  jsk validate resume.json"\n', encoding="utf-8")
            self.assertEqual(taught_in_strings(planted),
                             [(1, "fix:  jsk validate resume.json")])
            planted.write_text('HINT = "Rendered.\\n  check_prose.py X.tex"\n', encoding="utf-8")
            self.assertEqual(len(taught_in_strings(planted)), 1)
            # A docstring may name the script it replaced.
            planted.write_text('"""check_prose.py was the prose gate."""\n', encoding="utf-8")
            self.assertEqual(taught_in_strings(planted), [])
            # A step's heading names the script the gate ran as (dispatch.ADAPTERS), at the
            # start of the line: that is how it was called, not advice to run it.
            planted.write_text('HEAD = f"check_ats.py {name} --strict"\n', encoding="utf-8")
            self.assertEqual(taught_in_strings(planted), [])
            skill = Path(tmp) / "plugins" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text("Run `jsk validate` first.\n", encoding="utf-8")
            self.assertEqual(taught_in_docs(Path(tmp)),
                             [("plugins/SKILL.md", "Run `jsk validate` first.")])

    def test_a_plugin_teaching_a_command_that_became_a_tool_is_caught_and_its_history_is_not(self):
        # The skill is what an agent runs, so `jsk resume check` there is a step that exits 2;
        # the same words in a doc's retired table say where the command went.
        with tempfile.TemporaryDirectory() as tmp:
            mode = Path(tmp) / "plugins" / "mode-ship.md"
            mode.parent.mkdir()
            mode.write_text("Then run `jsk resume check out/`.\n", encoding="utf-8")
            notes = Path(tmp) / "docs" / "SCRIPTS.md"
            notes.parent.mkdir()
            notes.write_text("| `jsk resume check <dir>` | `resume_check(target)` |\n",
                             encoding="utf-8")
            self.assertEqual(taught_in_docs(Path(tmp)),
                             [("plugins/mode-ship.md", "Then run `jsk resume check out/`.")])

    def test_no_doc_names_a_retired_command(self):
        self.assertEqual(taught_in_docs(REPO_ROOT), [])


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
        self.assertIn("resume_check", proc.stdout)


if __name__ == "__main__":
    unittest.main()
