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
PLUGIN = REPO / "plugins" / "jsk"
SKILL = PLUGIN / "skills" / "jsk"
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

    def test_the_verifier_cannot_touch_a_document(self):
        """Denied Write and Edit both: a defect is repaired in the record and
        re-rendered, never patched into the document the checker just read."""
        tools = frontmatter(PLUGIN / "agents" / "jsk-verifier.md")["tools"]
        self.assertNotIn("Write", tools)
        self.assertNotIn("Edit", tools)

    def test_no_agent_that_reports_on_the_record_can_edit_it(self):
        """The auditor and the gap analyst write their own analysis and nothing else.

        Both hold Write, because a UGS document is their output. Neither holds Edit,
        which is the tool that would let one change a concept - and a provenance
        status that flips without the person saying so is the defect this whole
        framework exists to prevent.
        """
        for name in ("jsk-bundle-auditor",):
            tools = frontmatter(PLUGIN / "agents" / f"{name}.md")["tools"]
            with self.subTest(agent=name):
                self.assertIn("Write", tools)
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


class DocumentedSurface(unittest.TestCase):
    """What the prose promises, against what is installed.

    The constants above agree with each other and say nothing about the two revision
    tables a person actually reads. Revision 7 had to be added to both by hand, and a
    table that stops at 6 does not read as out of date - it reads as though 7 does not
    exist, which is worse than no table.
    """

    REVISION_TABLES = (
        SKILL / "references" / "bundle-spec.md",
        REPO / "docs" / "SCRIPTS.md",
    )

    def current(self):
        text = (SCRIPTS / "validate_bundle.py").read_text(encoding="utf-8")
        return int(re.search(r"^CURRENT_BUNDLE_REVISION = (\d+)", text, re.M).group(1))

    def test_every_revision_table_reaches_the_current_revision(self):
        current = self.current()
        for path in self.REVISION_TABLES:
            with self.subTest(doc=path.name):
                rows = re.findall(r"^\| (\d+) \|", path.read_text(encoding="utf-8"), re.M)
                self.assertTrue(rows, f"{path.name}: no revision table found")
                described = set(int(n) for n in rows)
                self.assertEqual(
                    described, set(range(1, current + 1)),
                    f"{path.name} documents {sorted(described)}, "
                    f"current revision is {current}")

    # ---- the URS specification is in two halves -------------------------------

    REFS = SKILL / "references"

    def test_the_view_format_lives_in_exactly_one_file(self):
        """`urs-spec.md` defines what a view points at; `view-format.md` defines what a
        view may carry. The split exists so jsk-resume-author reads 968 tokens instead
        of 4,127, and it is only safe while it stays a split rather than a copy.

        This cannot be checked key by key: `id`, `label`, `skills`, `target` and
        `include` are legitimately both view keys and record keys, so "appears in both
        files" is not evidence of anything. What is checkable is that the normative
        view example lives in one file, and that neither half has quietly regrown a
        Views section of its own."""
        spec = (self.REFS / "urs-spec.md").read_text(encoding="utf-8")
        view = (self.REFS / "view-format.md").read_text(encoding="utf-8")
        self.assertIn('"provenance_floor"', view,
                      "view-format.md no longer holds the normative view example")
        self.assertNotIn('"provenance_floor"', spec,
                         "urs-spec.md has regrown a view example - it was moved, not copied")

    def test_each_half_says_where_the_other_one_is(self):
        """A reader who lands in the wrong half has to be able to get to the right one.
        The pointers are the whole mechanism holding the split together, so losing one
        silently is the failure this guards."""
        spec = (self.REFS / "urs-spec.md").read_text(encoding="utf-8")
        view = (self.REFS / "view-format.md").read_text(encoding="utf-8")
        self.assertIn("view-format.md", spec, "urs-spec.md does not point at its other half")
        self.assertIn("urs-spec.md", view, "view-format.md does not point at its other half")

    def test_the_author_is_pointed_at_the_half_it_needs(self):
        """jsk-resume-author writes a view and reads the compiled record, so the record
        schema is the half it does not need. Pointing it back at urs-spec.md would undo
        the saving without anything failing."""
        author = (PLUGIN / "agents" / "jsk-resume-author.md").read_text(encoding="utf-8")
        self.assertIn("view-format.md", author)

    def test_every_script_SKILL_md_names_is_installed(self):
        """The script table is how an agent decides what it may run. A row naming a
        file that is not there sends it to a command that cannot exist, and the
        failure surfaces as a broken install rather than as a stale table."""
        named = set(re.findall(r"`([a-z_]+\.py)", (SKILL / "SKILL.md").read_text(encoding="utf-8")))
        self.assertTrue(named, "SKILL.md names no scripts")
        missing = sorted(n for n in named if not (SCRIPTS / n).exists())
        self.assertEqual(missing, [], f"SKILL.md names scripts that are not installed: {missing}")


if __name__ == "__main__":
    unittest.main()
