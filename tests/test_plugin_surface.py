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
# The code left the skill: it is a package at the repo root now, installed as
# jsk-resume. This file reads both - the skill for its markdown, the package for the
# dispatch tables the markdown has to agree with.
SCRIPTS = REPO / "src" / "jsk"

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
        """Regression: `argument-hint: Optional: a path` is a YAML mapping error
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

    def test_every_command_is_a_shim_into_its_mode(self):
        """A command loads its mode and says what `$ARGUMENTS` may hold - nothing more.

        Each one used to restate its mode's rules, which loaded them twice on every
        slash-command run and let the two copies drift: three still pointed at
        bundle-era paths after the mode files had moved on. A rule belongs in the
        mode file, so a command that grows past a shim is growing a second copy.
        """
        for path in self.commands():
            with self.subTest(command=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(f'Skill(skill="jsk:jsk", args="{path.stem}")', text)
                self.assertLess(len(text.encode("utf-8")), 800,
                                f"{path.name} restates its mode - move the rule there")


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
        for name in ("jsk-kb-auditor",):
            tools = frontmatter(PLUGIN / "agents" / f"{name}.md")["tools"]
            with self.subTest(agent=name):
                self.assertIn("Write", tools)
                self.assertNotIn("Edit", tools)

    def test_the_analyst_is_told_in_writing_to_leave_the_knowledge_base_alone(self):
        """The anti-invention guarantee, back in prose - and this test is the reason
        that is worth noticing rather than glossing.

        It used to be a tool grant: both authoring agents held neither Write nor Edit,
        because every change they made went through a write command that checked its
        shape. There is no write layer over one Markdown file, so both now hold Edit,
        and the guarantee is only as good as the sentence stating it. So the sentence
        is asserted.

        The analyst's boundary is absolute: it writes the posting and the assessment
        and never the knowledge base, because a claim that becomes `confirmed` without
        the person saying so is the defect this framework exists to prevent.
        """
        body = (PLUGIN / "agents" / "jsk-tailor-analyst.md").read_text(encoding="utf-8")
        self.assertIn("Never touch `user-knowledgebase.md`", body)

    def test_the_author_is_told_in_writing_that_everything_it_writes_is_inferred(self):
        """The author's boundary is different from the analyst's, because it does write
        into the knowledge base - bullets belong in the project they are about, so the
        next application can reuse them. What holds it is the status: everything it
        authors arrives `inferred`, and `provenance_floor: confirmed` on the view means
        the record gate refuses to render it until a person has confirmed each clause.

        That is enforcement rather than instruction, which is why the author may hold
        Edit and the analyst's rule has to be a sentence.
        """
        body = (PLUGIN / "agents" / "jsk-resume-author.md").read_text(encoding="utf-8")
        self.assertIn("status: inferred", body)
        self.assertIn("provenance_floor", body)

    def test_both_authoring_agents_keep_bash(self):
        """Bash is how the record gate is run at all, and both are told to run it."""
        for name in ("jsk-tailor-analyst", "jsk-resume-author"):
            tools = frontmatter(PLUGIN / "agents" / f"{name}.md")["tools"]
            with self.subTest(agent=name):
                self.assertIn("Bash", tools)


class TheTemplateAndTheSpecAgree(unittest.TestCase):
    """`jsk new` writes the headings; `kb-spec.md` says what goes under each.

    They are one rule in two languages and in two repositories' worth of distance from
    each other - the template is Python in `src/`, the spec is Markdown in `plugins/`.
    A heading in one and not the other is the whole failure: the skill writes a section
    the file does not have, or the file carries one nothing is ever written into.

    The headings are also the contract with every knowledge base already on disk.
    `kb-spec.md` says never to rename or reorder one, and this is what makes that
    enforceable rather than merely stated.
    """

    def headings(self, text):
        return re.findall(r"^## (.+)$", text, re.M)

    def test_the_scaffold_writes_every_heading_the_spec_documents(self):
        from jsk.kb import TEMPLATE

        spec = (SKILL / "references" / "kb-spec.md").read_text(encoding="utf-8")
        written = self.headings(TEMPLATE)
        self.assertTrue(written, "the template has no headings")
        # The spec names each one in its section table as `## Identity` and friends.
        documented = set(re.findall(r"`## ([A-Za-z ]+)`", spec))
        missing = sorted(h for h in written if h not in documented)
        self.assertEqual(missing, [],
                         f"jsk new writes headings kb-spec.md does not document: {missing}")

    def test_the_scaffold_leaves_no_heading_empty_of_guidance(self):
        """Every section a person opens to an empty file has to say what goes in it.

        Guidance in a template somebody is looking at gets read; guidance in a
        specification they have to go and find does not - and this file is the one
        thing between a blank document and an abandoned one.
        """
        from jsk.kb import TEMPLATE

        sections = re.split(r"^## ", TEMPLATE, flags=re.M)[1:]
        for section in sections:
            name = section.split("\n", 1)[0]
            with self.subTest(heading=name):
                self.assertTrue(
                    "<!--" in section or "```" in section or "|" in section,
                    f"## {name} offers neither guidance, a block, nor a table")


class TheLogIsItsOwnFile(unittest.TestCase):
    """The history moved out of the knowledge base into `log.md` beside it.

    Nothing that tailors or authors a resume reads the history, and three agents
    read the knowledge base whole on every tailoring run - 14k characters of log,
    three times, for nothing. The failure this guards is the section drifting back:
    one mode file still saying "append a row to `## Log`" puts it back in the file.
    """

    def test_the_template_has_no_log_section(self):
        from jsk.kb import LOG_TEMPLATE, TEMPLATE

        self.assertNotIn("## Log", TEMPLATE)
        self.assertIn("| date | what changed |", LOG_TEMPLATE)

    def test_jsk_new_writes_the_log_and_force_never_overwrites_it(self):
        import tempfile

        from jsk.kb import LOG_FILENAME, scaffold

        with tempfile.TemporaryDirectory() as root:
            code, _ = scaffold(root, "Test Person")
            self.assertEqual(code, 0)
            log = Path(root) / LOG_FILENAME
            self.assertIn("Knowledge base created.", log.read_text(encoding="utf-8"))
            with log.open("a", encoding="utf-8") as fh:
                fh.write("| 2026-09-24 | a row somebody wrote |\n")
            before = log.read_bytes()
            code, _ = scaffold(root, "Test Person", force=True)
            self.assertEqual(code, 0)
            self.assertEqual(log.read_bytes(), before)

    def test_no_instruction_writes_to_a_log_section(self):
        """Only kb-spec's migration note may still name the old section."""
        for path in sorted(PLUGIN.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            if path.name == "kb-spec.md":
                text = text.replace("**A `kb: 1` file still has `## Log` as its last section.**", "")
            with self.subTest(file=path.name):
                self.assertNotIn("## Log", text)


class Manifests(unittest.TestCase):
    def test_the_two_versions_agree(self):
        plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(plugin["version"], entry["version"])


class DocumentedSurface(unittest.TestCase):
    """What the prose promises, against what is installed.

    Nothing here is exercised by running a command, which is exactly why it drifts. A
    row naming a subcommand that does not exist sends an agent at something that cannot
    run, and the failure surfaces as a broken install rather than as a stale table.
    """

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
        """jsk-resume-author writes the view, so view-format.md is the half it cannot
        do without. It reads urs-spec.md too now that the record is hand-written, but
        losing the pointer to the view format would be the expensive one."""
        author = (PLUGIN / "agents" / "jsk-resume-author.md").read_text(encoding="utf-8")
        self.assertIn("view-format.md", author)

    def test_every_command_SKILL_md_names_is_a_real_subcommand(self):
        """The command table is how an agent decides what it may run. A row naming a
        subcommand that does not exist sends it to a command that cannot work, and the
        failure surfaces as a broken install rather than as a stale table.

        This checked for installed *files* until the scripts became one CLI. Same
        guarantee, one level up: what SKILL.md names has to be something `jsk`
        dispatches.
        """
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        named = set(re.findall(r"`jsk ([a-z]+)", text))
        self.assertTrue(named, "SKILL.md names no jsk subcommands")
        known = self.subcommands() | {"doctor", "new"}
        unknown = sorted(n for n in named if n not in known)
        self.assertEqual(unknown, [],
                         f"SKILL.md names subcommands jsk does not dispatch: {unknown}")

    # ---- the jsk subcommand menu ----------------------------------------------
    #
    # The check above runs one way only - named, therefore installed - and the other
    # direction is the one that drifted. A command that exists and appears in no
    # document is a command nobody reaches for, and a missing row does not read as out
    # of date: it reads as though the command does not exist.

    def subcommands(self):
        """Every subcommand `jsk` answers to, read off its two dispatch tables."""
        text = (SCRIPTS / "cli.py").read_text(encoding="utf-8")
        found = set()
        for table in ("SIMPLE", "HANDLERS"):
            block = re.search(rf"^{table} = \{{(.*?)^\}}", text, re.M | re.S)
            self.assertIsNotNone(block, f"cli.py: no {table} table found")
            found |= set(re.findall(r'^    "([a-z]+)":', block.group(1), re.M))
        self.assertTrue(found, "cli.py declares no subcommands")
        return found

    def test_the_help_text_lists_every_subcommand(self):
        """`jsk --help` prints the module docstring, so a subcommand absent from it is
        invisible to anyone who asks the command itself what it can do.

        A line may name several subcommands sharing a verb set, pipe-separated. Each
        alternative counts as listed; what is being checked is that nothing is absent,
        not how densely the menu is packed.
        """
        listed = set()
        for group in re.findall(r"^    jsk ([a-z|]+)", (SCRIPTS / "cli.py").read_text(
                encoding="utf-8"), re.M):
            listed |= set(group.split("|"))
        missing = sorted(self.subcommands() - listed)
        self.assertEqual(missing, [],
                         f"cli.py's own help text does not list: {missing}")

    def test_the_scripts_page_lists_every_subcommand(self):
        """docs/SCRIPTS.md opens with the whole menu, for a person running these by
        hand. It is the one page that promises to be exhaustive."""
        text = (REPO / "docs" / "SCRIPTS.md").read_text(encoding="utf-8")
        listed = set(re.findall(r"\bjsk ([a-z]+)", text))
        missing = sorted(self.subcommands() - listed)
        self.assertEqual(missing, [], f"docs/SCRIPTS.md does not list: {missing}")

    def test_SKILL_md_names_every_subcommand(self):
        """A command an agent does not know about is a command it does not run - and
        for `validate` that is not a slower route to the same answer, it is a resume
        rendered from a record nobody checked.

        This was a hand-maintained list of the eighteen subcommands that wrote into a
        bundle, kept separate so that adding a write forced a decision about the
        skill's own table. There are eight subcommands now and none of them writes
        anything a person owns, so the weaker statement is also the complete one:
        SKILL.md names all of them."""
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        missing = sorted(sub for sub in self.subcommands()
                         if not re.search(rf"`jsk {sub}\b", text))
        self.assertEqual(missing, [], f"SKILL.md does not name: {missing}")


if __name__ == "__main__":
    unittest.main()
