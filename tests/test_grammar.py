"""The CLI is `jsk <noun> <verb>` (Ruling 10 of the onion design), and the old names are
retired with a pointer rather than kept as aliases.

Every row of the ruling's mapping table is a test here: the old command exits 2 and names
the new one, with the call's own arguments, and the new one runs. Every noun-verb pair
answers --help from a process of its own, the way an agent first meets it.
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
                      example_short)

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


class ResumeCheckByTarget(unittest.TestCase):
    """`jsk resume check` picks its gates from what it is given, and refuses a flag that
    does not fit that kind of target."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.txt = build_text(self.tmp / "resume.txt", CLEAN_RESUME)
        self.json = self.tmp / "resume.json"
        self.json.write_text("{}", encoding="utf-8")

    def test_a_resume_json_gets_the_record_gate(self):
        code, out = jsk("resume", "check", example_short())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)
        self.assertNotIn("parse gate", out)

    def test_a_render_gets_the_parse_and_prose_gates(self):
        code, out = jsk("resume", "check", self.txt)
        self.assertEqual(code, 0, out)
        self.assertIn("--- parse gate", out)
        self.assertIn("--- prose gate", out)
        self.assertNotIn("record gate", out)

    def test_a_directory_gets_all_four(self):
        (self.tmp / "out").mkdir()
        code, out = jsk("resume", "check", self.tmp / "out")
        self.assertEqual(code, 1, out)
        for gate in ("record", "parse", "prose", "layout"):
            self.assertIn(f"--- {gate} gate", out)
        self.assertIn("=== summary", out)

    def test_each_flag_that_does_not_fit_is_a_usage_error_naming_the_kind(self):
        cases = [(self.json, flag, "a resume.json") for flag in
                 (["--pages", "2"], ["--record", "x.json"], ["--json"], ["--only", "parse"])]
        cases += [(self.txt, flag, "a render") for flag in
                  (["--pages", "2"], ["--record", "x.json"], ["--json"],
                   ["--max-findings", "3"])]
        cases += [(self.tmp, flag, "a render's directory") for flag in
                  (["--strict"], ["--only", "parse"])]
        for target, flag, kind in cases:
            with self.subTest(target=Path(target).name, flag=flag[0]):
                code, out = jsk("resume", "check", target, *flag)
                self.assertEqual(code, 2, out)
                self.assertIn(f"{flag[0]} does not fit {kind}", out)
                self.assertIn("fix:  jsk resume check", out)

    def test_the_layout_gate_keeps_its_own_flags(self):
        code, out = jsk("resume", "check", self.tmp / "resume.pdf", "--only", "layout",
                        "--record", self.json, "--region", "AU")
        self.assertNotIn("does not fit", out)

    def test_only_letter_points_at_letter_check(self):
        code, out = jsk("resume", "check", self.txt, "--only", "letter", "--record", self.json)
        self.assertEqual(code, 2, out)
        self.assertIn(f"fix:  jsk letter check {self.txt} --record {self.json}", out)

    def test_no_target_is_the_usage_of_all_three(self):
        code, out = jsk("resume", "check")
        self.assertEqual(code, 2, out)
        self.assertEqual(out.count("jsk resume check <"), 3, out)


class TheModulePathsAreRetired(unittest.TestCase):
    """`jsk` is the only door. A module path left importable but silent would exit 0, which
    a script reads as success, so each one names its command and exits 2."""

    PATHS = {
        "jsk.kb": "jsk kb new",
        "jsk.posting": "jsk posting",
        "jsk.render.render_resume": "jsk resume render",
        "jsk.render.fit_pages": "jsk resume fit",
        "jsk.render.preview_templates": "jsk resume preview",
        "jsk.gates.check_ats": "jsk resume check RESUME.pdf --only parse",
        "jsk.gates.check_prose": "jsk resume check RESUME.tex --only prose",
        "jsk.gates.layout": "jsk resume check RESUME.pdf --only layout",
        "jsk.gates.letter": "jsk letter check",
        "jsk.gates.record": "jsk resume check RESUME.json",
        "jsk.resume.short": "jsk resume check RESUME.json",
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

# Where the prose teaches commands: an agent runs what the skill tells it to, and a retired
# name there is a step that exits 2.
DOC_ROOTS = ("plugins", "README.md", "docs/*.md")


def taught_in_strings(path):
    """[(line, the string)] for each string constant in a module that names a retired command.

    Args:
        path: a .py file.

    Returns:
        The offending strings, docstrings and f-string parts included; comments are not
        strings, so they are not read.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and RETIRED_NAME.search(node.value)]


def taught_in_docs(root):
    """[(file, line)] for each line of the prose under `root` that names a retired command.

    Args:
        root: the repository root.

    Returns:
        The offending lines; docs/superpowers/ is history and is not read.
    """
    found = []
    for pattern in DOC_ROOTS:
        paths = root.glob(pattern) if "*" in pattern else [root / pattern]
        for path in (p for p in paths if p.exists()):
            files = path.rglob("*.md") if path.is_dir() else [path]
            for f in files:
                for line in f.read_text(encoding="utf-8").splitlines():
                    if RETIRED_NAME.search(line):
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
            skill = Path(tmp) / "plugins" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text("Run `jsk validate` first.\n", encoding="utf-8")
            self.assertEqual(taught_in_docs(Path(tmp)),
                             [("plugins/SKILL.md", "Run `jsk validate` first.")])

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
        self.assertIn("jsk resume check", proc.stdout)


if __name__ == "__main__":
    unittest.main()
