"""The plugin's own manifest surface: frontmatter, versions, revision constants.

None of this is exercised by running a script, which is exactly why it drifts. Four of
the seven command files shipped with YAML that does not parse - an unquoted `Optional:`
in `argument-hint` - and nothing caught it, because nothing looked.
"""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "career-okf"
SKILL = PLUGIN / "skills" / "career-okf"
SCRIPTS = SKILL / "scripts"

try:
    import yaml
except ImportError:                                     # pragma: no cover
    yaml = None


def frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    return yaml.safe_load(m.group(1)) if m else None


@unittest.skipIf(yaml is None, "pyyaml not installed")
class CommandFrontmatter(unittest.TestCase):
    """A command whose frontmatter does not parse loses its description AND its
    allowed-tools list - silently, because the file still looks fine."""

    def commands(self):
        return sorted(PLUGIN.joinpath("commands").glob("*.md"))

    def test_every_command_has_parseable_frontmatter(self):
        for path in self.commands():
            with self.subTest(command=path.name):
                try:
                    fm = frontmatter(path)
                except yaml.YAMLError as exc:
                    self.fail(f"{path.name}: frontmatter does not parse - {exc}")
                self.assertIsInstance(fm, dict, f"{path.name}: no frontmatter")

    def test_every_command_declares_a_description_and_its_tools(self):
        for path in self.commands():
            with self.subTest(command=path.name):
                fm = frontmatter(path)
                self.assertTrue(fm.get("description"), f"{path.name}: no description")
                self.assertTrue(fm.get("allowed-tools"), f"{path.name}: no allowed-tools")

    def test_an_argument_hint_with_a_colon_is_quoted(self):
        """Regression: `argument-hint: Optional: a bundle path` is a YAML mapping error
        that takes the whole block down with it."""
        for path in self.commands():
            raw = re.search(r"^argument-hint: (.+)$", path.read_text(encoding="utf-8"), re.M)
            if not raw:
                continue
            value = raw.group(1).strip()
            with self.subTest(command=path.name):
                if ":" in value:
                    self.assertRegex(value, r"^['\"].*['\"]$",
                                     f"{path.name}: a colon in argument-hint needs quoting")

    def test_every_command_maps_to_a_mode(self):
        modes = {p.stem.replace("mode-", "")
                 for p in SKILL.joinpath("references").glob("mode-*.md")}
        for path in self.commands():
            with self.subTest(command=path.name):
                self.assertIn(path.stem, modes)


@unittest.skipIf(yaml is None, "pyyaml not installed")
class AgentFrontmatter(unittest.TestCase):
    def agents(self):
        return sorted(PLUGIN.joinpath("agents").glob("*.md"))

    def test_every_agent_parses_and_names_itself_after_its_file(self):
        for path in self.agents():
            with self.subTest(agent=path.name):
                fm = frontmatter(path)
                self.assertIsInstance(fm, dict)
                self.assertEqual(fm.get("name"), path.stem)

    def test_every_agent_declares_a_description_and_a_tool_list(self):
        for path in self.agents():
            with self.subTest(agent=path.name):
                fm = frontmatter(path)
                self.assertTrue(fm.get("description"))
                self.assertTrue(fm.get("tools"))
                self.assertLess(len(fm["description"]), 1024)

    def test_the_read_only_agents_cannot_write(self):
        """Both are deliberately denied Write and Edit: a defect is repaired in the
        record, and a provenance status flips only when the person says so."""
        for name in ("career-okf-verifier", "career-okf-bundle-auditor"):
            tools = frontmatter(PLUGIN / "agents" / f"{name}.md")["tools"]
            with self.subTest(agent=name):
                self.assertNotIn("Write", tools)
                self.assertNotIn("Edit", tools)


class Manifests(unittest.TestCase):
    def test_the_two_versions_agree(self):
        plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(plugin["version"], entry["version"])


class RevisionConstants(unittest.TestCase):
    """Three files carry the bundle layout revision. A bundle that lies about its own
    shape is worse than one carrying no stamp at all."""

    def constant(self, script, name):
        text = (SCRIPTS / script).read_text(encoding="utf-8")
        return int(re.search(rf"^{name} = (\d+)", text, re.M).group(1))

    def test_all_three_agree(self):
        self.assertEqual(
            self.constant("init_bundle.py", "BUNDLE_REVISION"),
            self.constant("migrate_bundle.py", "CURRENT_REVISION"))
        self.assertEqual(
            self.constant("migrate_bundle.py", "CURRENT_REVISION"),
            self.constant("validate_bundle.py", "CURRENT_BUNDLE_REVISION"))

    def test_every_migration_step_is_bounded_by_the_target(self):
        """Regression: the steps were guarded on `revision < N` alone, so capping
        CURRENT_REVISION still ran the later step and then stamped the lower number
        over the result."""
        text = (SCRIPTS / "migrate_bundle.py").read_text(encoding="utf-8")
        guards = re.findall(r"if revision < (\d+)( <= CURRENT_REVISION)?:", text)
        self.assertTrue(guards, "no migration step guards found")
        for step, bounded in guards:
            with self.subTest(step=step):
                self.assertTrue(bounded, f"step r{step} is not bounded by CURRENT_REVISION")

    def test_every_revision_has_a_description(self):
        text = (SCRIPTS / "migrate_bundle.py").read_text(encoding="utf-8")
        current = int(re.search(r"^CURRENT_REVISION = (\d+)", text, re.M).group(1))
        described = set(int(n) for n in re.findall(r"^    (\d+): \"", text, re.M))
        self.assertEqual(described, set(range(1, current + 1)))


if __name__ == "__main__":
    unittest.main()
