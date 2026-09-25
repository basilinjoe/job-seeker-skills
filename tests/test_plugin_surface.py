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
        shape. Over one Markdown file both came to hold Edit, and the guarantee became
        only as good as the sentence stating it. So the sentence is asserted.

        The graph record has a write command again, `jsk kb apply`, and it cannot
        confirm anything - but the analyst still holds Bash, so it could run apply, and
        Write, so it could edit `career/kb.ttl` by hand. The analyst's boundary is
        absolute: it writes posting.ttl and the assessment and never the career.
        """
        body = (PLUGIN / "agents" / "jsk-tailor-analyst.md").read_text(encoding="utf-8")
        self.assertIn("Never touch `career/kb.ttl`", " ".join(body.split()))

    def test_the_author_is_told_in_writing_that_everything_it_writes_is_inferred(self):
        """The author's boundary is different from the analyst's, because it does write
        into the career - bullets belong in the project they are about, so the next
        application can reuse them. What holds it is the status: a bullet it adds
        through `jsk kb apply` arrives `j:inferred` whatever the changeset says (apply
        refuses one that says confirmed), `provenance_floor: confirmed` on the view means
        the record gate refuses to render it, and the claims gate refuses a record more
        confirmed than the career.

        That is enforcement rather than instruction, which is why the author may run
        apply and the analyst's rule has to be a sentence.
        """
        body = (PLUGIN / "agents" / "jsk-resume-author.md").read_text(encoding="utf-8")
        self.assertIn("`j:inferred`", body)
        self.assertIn("jsk kb apply", body)
        self.assertIn("provenance_floor", body)

    def test_both_authoring_agents_keep_bash(self):
        """Bash is how the record gate is run at all, and both are told to run it."""
        for name in ("jsk-tailor-analyst", "jsk-resume-author"):
            tools = frontmatter(PLUGIN / "agents" / f"{name}.md")["tools"]
            with self.subTest(agent=name):
                self.assertIn("Bash", tools)


class TheBannersAndTheFormatAgree(unittest.TestCase):
    """The writer prints the banners; `kb-format.md` shows them to a model.

    This used to check that `jsk new`'s Markdown headings and `kb-spec.md` named the
    same sections - one rule in two languages, Python in `src/` and Markdown in
    `plugins/`. The rule is the same with the graph record, one level down: the
    sections are `ontology.SECTIONS["kb"]`, which the writer prints as `# == <Section>`
    banners in that order, and a model reads kb.ttl by them. A banner missing from the
    format reference, or listed in another order, sends a model to the wrong place in
    the file - or has it add a section the writer would never print.
    """

    def format_text(self):
        return (SKILL / "references" / "kb-format.md").read_text(encoding="utf-8")

    def banners(self):
        """The banners kb-format.md lists for kb.ttl: its Layout section's, not the
        posting.ttl example's further down."""
        layout = self.format_text().split("## Layout", 1)[1].split("\n## ", 1)[0]
        return re.findall(r"^# == (.+)$", layout, re.M)

    def test_the_format_lists_every_banner_in_the_writers_order(self):
        from jsk.graph.ontology import SECTIONS

        self.assertEqual(self.banners(), list(SECTIONS["kb"]))

    def test_the_writer_prints_the_banners_as_the_format_shows_them(self):
        """The shape, not only the names: an empty record from the writer carries
        exactly the banner lines kb-format.md lists."""
        from jsk.graph import writer

        text = writer.write([], "kb")
        self.assertEqual(re.findall(r"^# == (.+)$", text, re.M),
                         self.banners())

    def test_the_format_names_every_predicate_a_model_may_draft(self):
        """A predicate kb-format.md does not name is one a model drafting a changeset
        cannot know exists - it reaches for `j:note`, or invents a name that apply
        refuses. So every predicate of every class that kb.ttl or posting.ttl holds is
        named in it, backticked."""
        from jsk.graph.ontology import CLASSES

        named = set(re.findall(r"`(?:j:)?([A-Za-z]+)`", self.format_text()))
        missing = sorted({f"{c.name}.{p}" for c in CLASSES
                          if set(c.kinds) & {"kb", "posting"}
                          for p in c.preds if p not in named})
        self.assertEqual(missing, [], f"kb-format.md does not name: {missing}")


class TheLogIsItsOwnFile(unittest.TestCase):
    """The history is `career/log.ttl`, written by `jsk kb` and nothing else.

    It moved out of the knowledge base into `log.md` because nothing that tailors or
    authors a resume reads the history, then became `log.ttl` when every change started
    going through `jsk kb apply`, which logs it. The failure this guards is an
    instruction drifting back: a mode file still saying "append a row to `## Log`", or
    to `log.md`, has a model hand-writing a log that apply owns.
    """

    def test_no_instruction_writes_a_log_by_hand(self):
        for path in sorted(PLUGIN.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotIn("## Log", text)
                self.assertNotIn("log.md", text)


class ChangesetsRouteThroughApply(unittest.TestCase):
    """The P6 rule, asserted where it can be: the career changes through `jsk kb apply`,
    and no mode or agent tells a model to grep, sed or Edit it by hand.

    Hand edits are legal - `jsk kb adopt` logs them - but an instruction to make one is
    the okf failure again: the verb a model is not told about is the one it routes around.
    """

    def plugin_texts(self):
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(PLUGIN.rglob("*.md"))}

    def test_nothing_names_the_markdown_knowledge_base_except_its_migration(self):
        allowed = {"SKILL.md", "mode-setup.md", "setup.md"}
        for name, text in self.plugin_texts().items():
            if name in allowed:
                continue
            with self.subTest(file=name):
                self.assertNotIn("user-knowledgebase.md", text)

    def test_no_file_names_the_index_command(self):
        """`jsk index` leaves with the Markdown reader; `jsk match` replaced it."""
        for name, text in self.plugin_texts().items():
            with self.subTest(file=name):
                self.assertNotIn("jsk index", text)
                self.assertNotIn("kb-spec.md", text)

    def test_SKILL_md_states_the_one_rule(self):
        text = " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())
        self.assertIn("change it with `jsk kb apply <changeset.trig>`", text)
        self.assertIn("Confirm only with `jsk kb confirm <id> --answer", text)
        self.assertIn("then `jsk kb adopt`", text)
        self.assertIn("Never edit `career/kb.ttl` blind.", text)
        self.assertNotIn("## Editing the knowledge base", text)

    def test_every_changeset_the_plugin_shows_is_one_apply_accepts(self):
        """A worked example a model copies is code, and unverified code in a document
        reads as checked. Every TriG block with a changeset graph in it must get past
        apply's own reader - the refusals that need no career in front of them."""
        from jsk.graph import changeset

        seen = 0
        for name, text in self.plugin_texts().items():
            for block in re.findall(r"```turtle\n(.*?)```", text, re.S):
                if "op:add" not in block and "op:set" not in block:
                    continue
                seen += 1
                with self.subTest(file=name, block=block[:60]):
                    try:
                        changeset.read(block.replace("…", "x"), name)
                    except changeset.Refused as exc:
                        self.fail("\n".join(r.text() for r in exc.refusals))
        self.assertGreaterEqual(seen, 3)


class TheProseSaysWhatTheGatesDo(unittest.TestCase):
    """Four places the plugin and docs promised a gate would catch something it does not.

    Each was run on a copy by a reviewer. A promise like this is worse than silence: a
    model that believes the gate will fail stops looking, and ships what the gate let by.
    """

    def text(self, path):
        return " ".join(path.read_text(encoding="utf-8").split())

    def ref(self, name):
        return self.text(SKILL / "references" / name)

    def agent(self, name):
        return self.text(PLUGIN / "agents" / name)

    def doc(self, name):
        return self.text(REPO / name)

    def test_a_provenance_floor_withholds_rather_than_fails(self):
        """`provenance_floor: confirmed` makes the renderer drop below-floor content and
        print `withheld ...`; `jsk validate` passes and `jsk ship` exits 0. Told the gate
        would fail, a caller hands over a resume missing the bullets it was about."""
        texts = {"author": self.agent("jsk-resume-author.md"),
                 "ship": self.ref("mode-ship.md"), "tailor": self.ref("mode-tailor.md")}
        for name, text in texts.items():
            with self.subTest(file=name):
                self.assertIn("`withheld", text)
                self.assertIn("confirmed or cut before", text)
        self.assertNotIn("refuses to render your prose", texts["author"])
        self.assertNotIn("Expect the record gate to fail", texts["ship"])
        self.assertNotIn("fails until a person confirms", texts["tailor"])
        self.assertNotIn("record gate refuses to render it", self.doc("docs/ARCHITECTURE.md"))

    def test_reworded_text_is_confirmed_in_the_career_not_on_the_old_words(self):
        """`jsk kb confirm <id>` confirms the career's text. A bullet retuned only in the
        record and then confirmed by id sends words nobody confirmed, at `confirmed`."""
        author = self.agent("jsk-resume-author.md")
        self.assertNotIn("Retune from what is there", author)
        self.assertIn("`op:set` its `j:text`", author)
        for name in ("mode-tailor.md", "mode-ship.md"):
            with self.subTest(file=name):
                self.assertIn("never on the strength of the old text", self.ref(name))
        self.assertIn("`text-changed`", self.doc("docs/WHY.md"))
        self.assertIn("not a proof", self.doc("docs/WHY.md"))
        self.assertNotIn("every claim to your career at the confidence", self.doc("README.md"))

    def test_not_run_is_a_record_outside_the_workspace(self):
        """The claims gate walks up from resume.json for career/kb.ttl. A record saved
        elsewhere - an outputs folder - gets NOT RUN, and ship still exits 0."""
        ship = self.ref("mode-ship.md")
        self.assertNotIn("A `NOT RUN` means a Markdown workspace", ship)
        self.assertIn("Move `resume.json` into", ship)
        skill = self.text(SKILL / "SKILL.md")
        self.assertIn("Keep `resume.json` inside the workspace", skill)
        self.assertIn("`NOT RUN`", skill)
        self.assertIn("`NOT RUN`", self.doc("docs/ARCHITECTURE.md").split("## Releasing")[0][-1500:])

    def test_a_bundle_keeps_its_statuses(self):
        """A changeset cannot write `confirmed`, so a bundle written as changesets alone
        loses every status. The plugin ships no shape for the old Markdown file, so
        mode-setup.md builds the record with changesets and then raises what the bundle
        held confirmed through `jsk kb confirm`, naming the bundle as the source."""
        setup = self.ref("mode-setup.md")
        arch = self.doc("docs/ARCHITECTURE.md")
        self.assertNotIn("carrying every status across unchanged", setup)
        self.assertNotIn("write a `user-knowledgebase.md`", setup)
        self.assertIn("A changeset cannot confirm", setup)
        self.assertIn("`jsk kb confirm <every id the bundle held confirmed> --answer`", setup)
        self.assertIn("a changeset cannot confirm", arch)


class Manifests(unittest.TestCase):
    def test_the_two_versions_agree(self):
        plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(plugin["version"], entry["version"])

    def test_the_plugin_ships_the_package_it_describes(self):
        """The plugin runs `jsk`; a manifest a major version behind the package it
        drives advertises a surface the commands no longer have."""
        import jsk
        plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], jsk.__version__)


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
