"""Ruling 6 of docs/superpowers/plans/2026-10-04-six-commands.md: each slash command's
`allowed-tools` matches the work its mode does, and no more.

Only `setup` runs a shell command; a command whose mode sends an agent holds `Task`; `Write`
and `Edit` belong to the modes that write a file. The review of 2026-10-04 found all eight old
commands holding Bash after the MCP-first change took every other shell call away, and the two
that sent the extractor holding no Task. Split from test_plugin_surface.py, which it took past
tests/test_sizes.py's limit.
"""
import re
import tempfile
import unittest
from pathlib import Path

from test_agent_grants import MCP
from test_plugin_surface import PLUGIN, SKILL, frontmatter, yaml

AGENT_NAMES = ("jsk-extractor", "jsk-kb-auditor", "jsk-tailor-analyst", "jsk-resume-author",
               "jsk-verifier")
# The commands whose mode writes a file itself: intake keeps the person's material under
# `sources/` (its text says "Write tool"), and setup seeds `rules/` overrides and keeps a
# document the same way. Every other mode changes the career through tools, or has an
# agent write the file (the auditor's `audit.gaps.md`), so its command needs no Write.
FILE_WRITERS = ("intake", "setup")


def mode_texts(command):
    """The text of the mode a command loads, and of every mode that text sends the
    session on to read: setup reads intake, which is where the extractor is sent."""
    refs = SKILL / "references"
    mode = re.search(r'args="([a-z]+)"', command.read_text(encoding="utf-8")).group(1)
    seen, todo, texts = set(), [mode], []
    while todo:
        name = todo.pop()
        path = refs / f"mode-{name}.md"
        if name in seen or not path.exists():
            continue
        seen.add(name)
        text = path.read_text(encoding="utf-8")
        texts.append(text)
        todo += re.findall(r"mode-([a-z]+)\.md", text)
    return texts


def grant_problems(name, grants, texts):
    """What a command's `allowed-tools` gets wrong about the work its mode does.

    Only `setup` runs a shell command (`jsk doctor`, `jsk kb new|load`); a mode that names an
    agent needs `Task` to send it; `Write` and `Edit` belong to the modes that write a file.
    """
    problems = []
    if "Bash" in grants and name != "setup":
        problems.append(f"{name} holds Bash but only setup runs a shell command")
    named = [a for a in AGENT_NAMES if any(a in text for text in texts)]
    if named and "Task" not in grants:
        problems.append(f"{name} names {named} but holds no Task")
    if {"Write", "Edit"} & grants and name not in FILE_WRITERS:
        problems.append(f"{name} holds Write or Edit but its mode writes no file")
    return problems


@unittest.skipIf(yaml is None, "pyyaml not installed")
class CommandGrants(unittest.TestCase):
    """Ruling 6 of docs/superpowers/plans/2026-10-04-six-commands.md: a command's grants
    match its mode's work, and no more."""

    def commands(self):
        return sorted(PLUGIN.joinpath("commands").glob("*.md"))

    def grants(self, path):
        return {g.strip() for g in str(frontmatter(path)["allowed-tools"]).split(",")}

    def test_the_six_commands_hold_the_grants_their_modes_need(self):
        self.assertEqual([p.stem for p in self.commands()],
                         ["intake", "resume", "review", "setup", "ship", "tailor"])
        for path in self.commands():
            with self.subTest(command=path.stem):
                self.assertEqual(
                    grant_problems(path.stem, self.grants(path), mode_texts(path)), [])
                self.assertIn(f"{MCP}*", self.grants(path))

    def test_only_setup_holds_bash_and_the_agent_senders_hold_task(self):
        for path in self.commands():
            grants = self.grants(path)
            with self.subTest(command=path.stem):
                self.assertEqual("Bash" in grants, path.stem == "setup")
                if any(a in t for a in AGENT_NAMES for t in mode_texts(path)):
                    self.assertIn("Task", grants)

    def test_the_commands_that_write_a_file_are_the_ones_whose_mode_says_so(self):
        for path in self.commands():
            with self.subTest(command=path.stem):
                holds = bool({"Write", "Edit"} & self.grants(path))
                self.assertEqual(holds, path.stem in FILE_WRITERS)
        intake = SKILL / "references" / "mode-intake.md"
        self.assertIn("(Write tool)", intake.read_text(encoding="utf-8"))

    def test_a_planted_grant_that_does_not_match_its_mode_fails(self):
        """The check above, with the violations planted: a shell grant on a command that
        runs none, a mode that names an agent with no Task, and a stray Write."""
        agent_mode = [f"Send `{AGENT_NAMES[0]}` the workspace."]
        self.assertTrue(grant_problems("review", {"Read", "Bash", "Task"}, agent_mode))
        self.assertTrue(grant_problems("review", {"Read", "Skill"}, agent_mode))
        self.assertTrue(grant_problems("review", {"Read", "Task", "Write"}, agent_mode))
        self.assertEqual(grant_problems("review", {"Read", "Task"}, agent_mode), [])
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "ship.md"
            planted.write_text("---\nallowed-tools: Bash, Read\n---\n"
                               'Skill(skill="jsk:jsk", args="ship")\n', encoding="utf-8")
            grants = self.grants(planted)
            self.assertIn("Bash", grants)
            self.assertTrue(grant_problems("ship", grants, mode_texts(planted)))
