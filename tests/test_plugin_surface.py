"""The plugin's own manifest surface: frontmatter, versions, revision constants.

None of this is exercised by running a script, which is exactly why it drifts. Four of
the seven command files shipped with YAML that does not parse - an unquoted `Optional:`
in `argument-hint` - and nothing caught it, because nothing looked.
"""
import json
import re
import unittest
from pathlib import Path

from fixtures import source_path
from test_agent_grants import MCP, granted

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

        The graph record has a write tool again, `career_apply`, and it cannot
        confirm anything. While the analyst held Bash it could run `jsk kb apply` (retired in
        6.0 for the tool); since 5.0.0 it
        works through the `jsk mcp` tools and holds none that writes the career, so the
        sentence is also true by construction (AgentGrants pins the grant). The sentence
        stays asserted: a grant widened later must still meet the rule in writing.
        """
        body = (PLUGIN / "agents" / "jsk-tailor-analyst.md").read_text(encoding="utf-8")
        self.assertIn("**Never touch the career**", " ".join(body.split()))

    def test_the_author_is_told_in_writing_that_everything_it_writes_is_inferred(self):
        """The author's boundary is different from the analyst's, because it does write
        into the career - bullets belong in the project they are about, so the next
        application can reuse them. What holds it is the status: a bullet it adds
        through `career_apply` arrives `j:inferred` whatever the changeset says (apply
        refuses one that says confirmed), and the short file's `floor`, `confirmed` by
        default, means the render withholds it. The short file holds ids, never a
        bullet's words, so there is no copy for a confirmation to be raised in - the
        claims gate that watched for one went with the URS record.

        That is enforcement rather than instruction, which is why the author may run
        apply and the analyst's rule has to be a sentence. Since 5.0.0 it applies through
        `career_apply`, and the body names it (6.0 retired the `jsk kb apply` form).
        """
        body = (PLUGIN / "agents" / "jsk-resume-author.md").read_text(encoding="utf-8")
        self.assertIn("`j:inferred`", body)
        self.assertIn("`career_apply`", body)
        self.assertIn("Leave `floor` at its default, `confirmed`", " ".join(body.split()))
        self.assertNotIn("provenance_floor", body)

    def test_the_extractor_stops_at_the_preview(self):
        """The extractor turns a person's own account into a changeset - the riskiest
        writing in the skill, so it runs pinned to a model rather than on whatever the
        session has. It may preview and nothing more: the person must see what lands
        before it lands, and the agent never talks to them.

        Changed on purpose in 5.0.0: it held Write for one changeset file under changes/
        and Bash for `jsk kb apply <file> --dry-run` (retired in 6.0). It passes the changeset's text to
        `career_preview` now and returns it whole, so it holds neither - and no
        `career_apply`, which is the stop made a grant. The stop is still a sentence,
        asserted."""
        fm = frontmatter(PLUGIN / "agents" / "jsk-extractor.md")
        self.assertEqual(fm["model"], "sonnet")
        tools = granted(fm)
        for denied in ("Write", "Edit", "Bash", MCP + "career_apply", MCP + "career_confirm"):
            with self.subTest(denied=denied):
                self.assertNotIn(denied, tools)
        self.assertIn(MCP + "career_preview", tools)
        body = " ".join((PLUGIN / "agents" / "jsk-extractor.md").read_text(
            encoding="utf-8").split())
        self.assertIn("You run `career_preview` and nothing that writes.", body)
        self.assertIn("Leave provenance out.", body)
        self.assertIn("Never invent a number.", body)

    def test_the_mode_that_extracts_sends_the_extractor(self):
        """Intake keeps the person's words as a file - the agent needs a source, and
        `career_confirm`'s `source` and `quote` can then check a confirmation against what
        they actually said. It applies only after showing the diff. Setup no longer extracts
        (2026-10-04, six commands): it creates the workspace and reads intake."""
        refs = SKILL / "references"
        intake = " ".join((refs / "mode-intake.md").read_text(encoding="utf-8").split())
        setup = " ".join((refs / "mode-setup.md").read_text(encoding="utf-8").split())
        self.assertIn("`<workspace>/sources/<yyyy-mm-dd>-braindump.md`", intake)
        self.assertIn('source="sources/<that file>", quote=', intake)
        self.assertIn("jsk-extractor", intake)
        self.assertIn("No agents", intake)
        self.assertIn("`mode-intake.md`", setup)

    def test_every_agent_is_in_the_skill_table_and_pinned(self):
        """SKILL.md's Agents table is how a session learns an agent exists; one missing
        from it is never sent, and a row naming no file sends the session at nothing.
        Every agent runs pinned, with a colour of its own to tell them apart."""
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        table = skill.split("## Agents")[1].split("\n## ")[0]
        named = set(re.findall(r"^\| `(jsk-[a-z-]+)` \|", table, re.M))
        files = {p.stem for p in self.agents()}
        self.assertEqual(named, files)
        colours = [frontmatter(p).get("color") for p in self.agents()]
        self.assertEqual(len(colours), len(set(colours)), colours)
        for path in self.agents():
            with self.subTest(agent=path.name):
                self.assertEqual(frontmatter(path).get("model"), "sonnet")


class TheSectionsAndTheFormatAgree(unittest.TestCase):
    """`career_view` prints the sections; `kb-format.md` lists them for a model.

    This used to check that `jsk new`'s Markdown headings and `kb-spec.md` named the
    same sections, then that the writer's `# == <Section>` banners in kb.ttl matched
    the format reference. The career is in a store now and has no file layout, but the
    sections survive one level up: `ontology.SECTIONS["kb"]` is the order `career_view`
    prints the career in and the names its `section` argument takes. A section missing from the
    format reference, or listed in another order, sends a model to a `section` that
    is not there - or has it look for one the view never prints.
    """

    def format_text(self):
        return (SKILL / "references" / "kb-format.md").read_text(encoding="utf-8")

    def sections(self):
        """The names kb-format.md's Sections part lists, in its code block."""
        part = self.format_text().split("## Sections", 1)[1].split("\n## ", 1)[0]
        block = part.split("```", 2)[1]
        return [line.strip() for line in block.splitlines() if line.strip()]

    def test_the_format_lists_every_section_in_the_views_order(self):
        from jsk.domain.ontology import SECTIONS

        self.assertEqual(self.sections(), list(SECTIONS["kb"]))

    def test_the_view_prints_the_sections_as_the_format_shows_them(self):
        """The shape, not only the names: an empty career rendered by `career_view`
        carries exactly the section headings kb-format.md lists."""
        from jsk.domain.record import view

        text = view.render([])
        self.assertEqual(re.findall(r"^## (.+)$", text, re.M), self.sections())

    def test_the_format_names_every_predicate_a_model_may_draft(self):
        """A predicate kb-format.md does not name is one a model drafting a changeset
        cannot know exists - it reaches for `j:note`, or invents a name that apply
        refuses. So every predicate of every class the career or a posting holds is
        named in it, backticked."""
        from jsk.domain.ontology import CLASSES

        named = set(re.findall(r"`(?:j:)?([A-Za-z]+)`", self.format_text()))
        missing = sorted({f"{c.name}.{p}" for c in CLASSES
                          if set(c.kinds) & {"kb", "posting"}
                          for p in c.preds if p not in named})
        self.assertEqual(missing, [], f"kb-format.md does not name: {missing}")


class TheLogIsWrittenByJskAlone(unittest.TestCase):
    """The history is the store's `log` graph, written by jsk and read with the `career_log` tool.

    It moved out of the knowledge base into `log.md` because nothing that tailors or
    authors a resume reads the history, then became `log.ttl` when every change started
    going through `jsk kb apply`, which logs it, then a graph in career/store/ written in
    the same update as the change. The failure this guards is an instruction drifting
    back: a mode file still saying "append a row to `## Log`", or to `log.md`, has a
    model hand-writing a log that apply owns; one saying to read `log.ttl` sends it at a
    file that is no longer the record.
    """

    def test_no_instruction_writes_a_log_by_hand(self):
        for path in sorted(PLUGIN.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotIn("## Log", text)
                self.assertNotIn("log.md", text)
                self.assertNotIn("log.ttl", text)

    def test_the_agents_that_date_a_pass_read_the_log_through_jsk(self):
        """The auditor and the review mode read the history to date the last pass; with
        no file to open, `career_log` is the only way, so each names it."""
        self.assertIn("career_log", (PLUGIN / "agents" / "jsk-kb-auditor.md").read_text(
            encoding="utf-8"))
        self.assertIn("career_log", (SKILL / "references" / "mode-review.md").read_text(
            encoding="utf-8"))


class AgentsNeverReadRecordFiles(unittest.TestCase):
    """The record is career/store/, and only jsk opens it.

    The agents used to be told to run `jsk kb path` and read or grep `kb.ttl`, `log.ttl`
    and `posting.ttl` at the paths it printed. Those files are not the record any more -
    a workspace imported with `jsk kb load .` still has them, stale, which makes a read
    of one worse than none: it looks right and is out of date. So no plugin file names a
    record file, except SKILL.md and mode-setup.md naming `career/kb.ttl` once, as the
    sign of a workspace to import; and nothing tells a model to read what `jsk kb path`
    prints.
    """

    RECORD_FILES = ("kb.ttl", "log.ttl", "posting.ttl", "application.ttl", "gaps.ttl")
    # Where `career/kb.ttl` may appear: the sign of a workspace from before the store.
    IMPORT_HINT = {"SKILL.md", "mode-setup.md"}

    def test_no_plugin_file_names_a_record_file(self):
        for path in sorted(PLUGIN.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            for name in self.RECORD_FILES:
                found = text.count(name)
                if name == "kb.ttl" and path.name in self.IMPORT_HINT:
                    found -= text.count("`career/kb.ttl`")
                with self.subTest(file=path.name, record=name):
                    self.assertEqual(found, 0, f"{path.name} names {name}")

    def test_the_import_hint_names_the_import(self):
        for name in self.IMPORT_HINT:
            path = next(PLUGIN.rglob(name))
            with self.subTest(file=name):
                self.assertIn("jsk kb load .", path.read_text(encoding="utf-8"))

    def test_no_agent_is_told_to_read_the_paths_kb_path_prints(self):
        for path in sorted(PLUGIN.joinpath("agents").glob("*.md")):
            body = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(agent=path.name):
                self.assertNotIn("read the files at", body)
                self.assertNotIn("read and grep", body)
                self.assertNotIn("grep `kb", body)


class ChangesetsRouteThroughApply(unittest.TestCase):
    """The P6 rule, asserted where it can be: the career changes through `career_apply`,
    and no mode or agent tells a model to grep, sed or Edit it by hand.

    With the record in career/store/ there is no hand edit to make, and `jsk kb adopt`
    and `jsk kb fmt`, which answered one, are gone. An instruction naming either is the
    okf failure again: a verb the prose promises that the CLI does not have.
    """

    RETIRED = ("jsk kb adopt", "jsk kb fmt", "`adopt`", "`fmt`")

    def test_no_file_names_a_retired_verb(self):
        for name, text in self.plugin_texts().items():
            for verb in self.RETIRED:
                with self.subTest(file=name, verb=verb):
                    self.assertNotIn(verb, text)

    def test_every_kb_verb_the_plugin_names_is_one_jsk_kb_has(self):
        """`jsk kb <verb>` named anywhere in the plugin is a verb `jsk kb` dispatches."""
        from jsk.adapters.cli.main import NOUNS

        for name, text in self.plugin_texts().items():
            for verb in set(re.findall(r"jsk kb ([a-z]+)", text)):
                with self.subTest(file=name, verb=verb):
                    self.assertIn(verb, NOUNS["kb"])

    def test_the_skill_names_the_read_verbs_and_the_load(self):
        """The kb row of SKILL.md's table, and the reads its one rule names: what an
        agent reads with is the whole of how it reads."""
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        row = re.search(r"^\| `jsk kb ([a-z\\|]+)` \|", text, re.M)
        self.assertIsNotNone(row, "SKILL.md has no `jsk kb` row")
        listed = row.group(1).replace("\\", "").split("|")
        self.assertEqual(sorted(listed), sorted(["load", "dump"]))
        self.assertIn("`jsk kb new <path>", text)
        self.assertIn("jsk kb load .", text)

    def plugin_texts(self):
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(PLUGIN.rglob("*.md"))}

    def test_nothing_names_the_markdown_knowledge_base(self):
        """jsk no longer reads it, and `jsk migrate` went with it."""
        for name, text in self.plugin_texts().items():
            with self.subTest(file=name):
                self.assertNotIn("user-knowledgebase.md", text)
                self.assertNotIn("jsk migrate", text)

    def test_no_file_names_the_index_command(self):
        """`jsk index` leaves with the Markdown reader; `jsk match` replaced it."""
        for name, text in self.plugin_texts().items():
            with self.subTest(file=name):
                self.assertNotIn("jsk index", text)
                self.assertNotIn("kb-spec.md", text)

    def test_SKILL_md_states_the_one_rule(self):
        text = " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())
        self.assertIn("change it with `career_apply(changeset)`", text)
        self.assertIn("Confirm only through `career_confirm`, with the person's own answer", text)
        self.assertIn("Never open anything under `career/`", text)
        self.assertNotIn("## Editing the knowledge base", text)

    def test_every_changeset_the_plugin_shows_is_one_apply_accepts(self):
        """A worked example a model copies is code, and unverified code in a document
        reads as checked. Every TriG block with a changeset graph in it must get past
        apply's own reader - the refusals that need no career in front of them."""
        from jsk.adapters.compose import record
        from jsk.domain.record import changeset

        seen = 0
        for name, text in self.plugin_texts().items():
            for block in re.findall(r"```turtle\n(.*?)```", text, re.S):
                if "op:add" not in block and "op:set" not in block:
                    continue
                seen += 1
                with self.subTest(file=name, block=block[:60]):
                    try:
                        record.read_changeset(block.replace("…", "x"), name)
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
        """`career_confirm` of an id confirms the career's text. A bullet retuned only in the
        record and then confirmed by id sends words nobody confirmed, at `confirmed`."""
        author = self.agent("jsk-resume-author.md")
        self.assertNotIn("Retune from what is there", author)
        self.assertIn("`op:set` its `j:text`", author)
        for name in ("mode-tailor.md", "mode-ship.md"):
            with self.subTest(file=name):
                self.assertIn("never on the strength of the old text", self.ref(name))
        # WHY.md said a reworded bullet kept its id and got a `text-changed` WARN. With
        # no copy to reword, it says where the rewording happens instead.
        self.assertNotIn("`text-changed`", self.doc("docs/WHY.md"))
        self.assertIn("one reworded for a posting is reworded in the career", self.doc("docs/WHY.md"))
        self.assertIn("not a proof", self.doc("docs/WHY.md"))
        self.assertNotIn("every claim to your career at the confidence", self.doc("README.md"))

    def test_a_file_outside_the_workspace_is_refused_not_passed(self):
        """The claims gate walked up from resume.json for career/kb.ttl, and a record
        saved elsewhere - an outputs folder - got NOT RUN while ship exited 0; the plugin
        had to say never to freeze over one. The short file was then built from the career,
        so outside a workspace there was nothing to build, and SKILL.md said to keep it
        inside one. Changed on purpose in 6.0 (docs/superpowers/plans/
        2026-10-03-retire-file-pipeline.md, P2): no command reads a resume.json, a selection
        lives in its workspace's store and is never outside one, so SKILL.md no longer
        names the file and ARCHITECTURE.md says the record gate and the render refuse one,
        naming the target form. No file may promise a NOT RUN that no longer exists."""
        ship = self.ref("mode-ship.md")
        for gone in ("NOT RUN", "claims gate", "Move `resume.json` into", "--view",
                     "<resume.json>"):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, ship)
        skill = self.text(SKILL / "SKILL.md")
        self.assertNotIn("Keep `resume.json` inside the workspace", skill)
        self.assertNotIn("<resume.json>", skill)
        self.assertNotIn("`NOT RUN`", skill)
        self.assertNotIn("**Claims**", skill)
        self.assertIn("a `resume.json` is read nowhere since 6.0, so the record gate and the "
                      "render both refuse one (exit 2), naming the target form",
                      self.doc("docs/ARCHITECTURE.md").split("## Releasing")[0][-1500:])

    def test_a_bundle_keeps_its_statuses(self):
        """A changeset cannot write `confirmed`, so a bundle written as changesets alone
        loses every status. The plugin ships no shape for the old Markdown file, so
        mode-intake.md (which setup reads, since 2026-10-04) builds the record with changesets
        and then raises what the bundle held confirmed through `career_confirm`, quoting the
        bundle file - an --answer that only named it was checked by nothing."""
        setup = " ".join(self.ref("mode-intake.md").split())
        arch = self.doc("docs/ARCHITECTURE.md")
        self.assertNotIn("carrying every status across unchanged", setup)
        self.assertNotIn("write a `user-knowledgebase.md`", setup)
        self.assertIn("A changeset cannot confirm", setup)
        self.assertIn("`career_confirm(ids=[every id the bundle held confirmed], "
                      "source=\"<bundle file>\", quote=", " ".join(setup.split()))
        self.assertNotIn("--answer` naming", setup)
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

    # ---- the short resume.json has one reference ------------------------------

    REFS = SKILL / "references"

    def test_the_format_names_every_key_the_short_file_accepts(self):
        """`resume-format.md` replaced `urs-spec.md` and `view-format.md` - an 11KB
        specification of a copy of the career, and the half of it an author read. The
        short file refuses an unknown key, so a key the reference does not name is one
        an author cannot know it may set, and one it names that `short.KEYS` lacks fails
        every file that uses it."""
        from jsk.domain.resume import short

        text = (self.REFS / "resume-format.md").read_text(encoding="utf-8")
        table = set(re.findall(r"^\| `([a-z_]+)`", text, re.M))
        table |= set(re.findall(r"^\| `[a-z_]+`, `([a-z_]+)`", text, re.M))
        self.assertEqual(table, set(short.KEYS))

    def test_no_file_points_at_the_retired_specification(self):
        """The URS spec, the view format and the URS guide were deleted with the record
        (2026-09-25). A pointer left behind sends a reader to a file that is not there -
        or, read by an agent, to a search for one."""
        texts = {p.relative_to(REPO).as_posix(): p.read_text(encoding="utf-8")
                 for p in [*PLUGIN.rglob("*.md"), REPO / "README.md", *(REPO / "docs").glob("*.md")]}
        for name in ("urs-spec.md", "view-format.md", "urs-guide.md"):
            self.assertFalse((self.REFS / name).exists() or (REPO / "docs" / name).exists(), name)
            for path, text in texts.items():
                with self.subTest(file=path, pointer=name):
                    self.assertNotIn(name, text)

    def test_the_author_is_pointed_at_the_format_it_needs(self):
        """jsk-resume-author exports the short file and edits its order, summary and page
        settings, so resume-format.md is the one format reference it reads."""
        author = (PLUGIN / "agents" / "jsk-resume-author.md").read_text(encoding="utf-8")
        self.assertIn("references/resume-format.md", author)

    def test_no_example_passes_a_view(self):
        """A short resume.json is one resume, so `--view` left render, preview, gates,
        ship and freeze. An example still passing it is a usage error copied into a
        shell by whoever trusts the page."""
        texts = {p.relative_to(REPO).as_posix(): p.read_text(encoding="utf-8")
                 for p in [*PLUGIN.rglob("*.md"), REPO / "README.md", *(REPO / "docs").glob("*.md")]}
        for path, text in texts.items():
            for line in text.splitlines():
                if re.search(r"jsk (ship|render|preview|gates|freeze)\b.*--view", line):
                    with self.subTest(file=path):
                        self.fail(f"{path}: {line.strip()}")

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
        """Every noun `jsk` answers to, read off its noun table."""
        text = (SCRIPTS / "adapters" / "cli" / "main.py").read_text(encoding="utf-8")
        block = re.search(r"^NOUNS = \{(.*?)^\}", text, re.M | re.S)
        self.assertIsNotNone(block, "adapters/cli/main.py: no NOUNS table found")
        found = set(re.findall(r'^    "([a-z]+)":', block.group(1), re.M))
        self.assertTrue(found, "adapters/cli/main.py declares no nouns")
        return found

    def test_the_help_text_lists_every_subcommand(self):
        """`jsk --help` prints the module docstring, so a subcommand absent from it is
        invisible to anyone who asks the command itself what it can do.

        A line may name several subcommands sharing a verb set, pipe-separated. Each
        alternative counts as listed; what is being checked is that nothing is absent,
        not how densely the menu is packed.
        """
        listed = set()
        for group in re.findall(r"^    jsk ([a-z|]+)", (SCRIPTS / "adapters" / "cli" /
                                                       "main.py").read_text(encoding="utf-8"),
                                re.M):
            listed |= set(group.split("|"))
        missing = sorted(self.subcommands() - listed)
        self.assertEqual(missing, [],
                         f"adapters/cli/main.py's own help text does not list: {missing}")

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


class ArchitectureNamesTheCode(unittest.TestCase):
    """docs/ARCHITECTURE.md is where a contributor learns what each module is for.

    The review of 2026-09-28 found ten modules it never mentioned - the whole path from a
    posting to its assessment among them - and a subcommand count two behind. Neither was
    wrong when written; nothing looked when the code moved on. A module the page does not
    name is one a contributor has to find by reading the package."""

    TEXT = (REPO / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
             "fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()

    def test_every_module_is_named(self):
        for path in sorted(SCRIPTS.rglob("*.py")):
            if path.name == "__init__.py" and path.parent != SCRIPTS:
                continue                        # a subpackage's __init__ has nothing to say
            with self.subTest(module=path.relative_to(SCRIPTS).as_posix()):
                named = re.search(rf"(?<![\w.]){re.escape(path.name)}\b", self.TEXT)
                self.assertTrue(named, f"docs/ARCHITECTURE.md does not name {path.name}")

    def test_the_subcommand_count_is_the_dispatchers(self):
        count = len(DocumentedSurface.subcommands(self))
        said = re.search(r"cli/main\.py\s+the dispatcher: (\w+) nouns", self.TEXT)
        self.assertIsNotNone(said, "docs/ARCHITECTURE.md no longer counts the subcommands")
        self.assertEqual(said.group(1), self.WORDS[count],
                         f"adapters/cli/main.py dispatches {count} nouns")


class TextIsReadInOnePlace(unittest.TestCase):
    """Every text file jsk reads goes through graph.io.read_text.

    The review of 2026-09-28 found five defects that were one defect: about fifty readers,
    each choosing its own encoding and its own except clause, so a BOM, a CRLF or a cp1252
    save broke whichever reader had forgotten it. A byte read, a write and pymupdf are not
    text reads. A module here reads text itself, for the reason given."""

    ALLOWED = {
        "jsk.infra.files": "read_text itself",
        # Deliberately lenient: a gate reads a rendered document to judge it, and a stray
        # byte in what was rendered is a finding in its own right, not a reason to stop.
        "jsk.infra.documents": "reads a rendered .txt or .tex, or a cover letter, with "
                               "errors=replace",
    }

    def allowed_paths(self):
        return {source_path(name) for name in self.ALLOWED}

    @staticmethod
    def text_reads(path):
        """Line numbers of each builtin open() in text read mode."""
        import ast

        found = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "open"):
                continue
            mode = node.args[1] if len(node.args) > 1 else next(
                (k.value for k in node.keywords if k.arg == "mode"), None)
            text = mode.value if isinstance(mode, ast.Constant) else "r"
            if not set(text) & set("wxab"):
                found.append(node.lineno)
        return found

    def test_no_module_reads_text_itself(self):
        allowed = self.allowed_paths()
        for path in sorted(SCRIPTS.rglob("*.py")):
            name = path.relative_to(SCRIPTS).as_posix()
            with self.subTest(module=name):
                if name not in allowed:
                    self.assertEqual(self.text_reads(path), [],
                                     f"{name} opens a text file itself - use "
                                     "graph.io.read_text, which handles a BOM, CRLF and "
                                     "cp1252 once")

    def test_every_allowed_module_still_reads_text(self):
        for name in self.ALLOWED:
            with self.subTest(module=name):
                self.assertTrue(self.text_reads(SCRIPTS / source_path(name)),
                                f"{name} no longer reads text itself - take it off ALLOWED")


if __name__ == "__main__":
    unittest.main()
