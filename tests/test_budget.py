"""What a tailoring run costs to read.

The 2.2.0 audit found a plugin whose costs nobody had measured: a compile that
parsed 345 concepts to build a record out of 41, and an agent handed 99 views for
postings it had nothing to do with. None of that was anybody's mistake - it was
simply never counted, and what is never counted drifts.

So it is counted here. These ceilings are the measured figures plus headroom, not
aspirations: a change that pushes a read over one is not necessarily wrong, but it
has to be seen and the ceiling moved deliberately.

Only *mandated* reads count - what SKILL.md, the mode files and the agent files
instruct. Model reasoning and the conversation are not measurable from the repo,
so the real cost of a run is higher than anything asserted here. That is fine: this
guards the part that is a property of the files, and it is the part that drifts.

Tokens are approximated as bytes/4. The absolute number matters less than that the
same approximation is applied on both sides of a change.
"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "jsk"
SKILL = PLUGIN / "skills" / "jsk"
REFS = SKILL / "references"
AGENTS = PLUGIN / "agents"


def tokens(*paths):
    return sum(p.stat().st_size for p in paths) // 4


class ResidentCost(unittest.TestCase):
    """SKILL.md loads whenever the skill triggers, for every mode, before anyone has
    said what they want. It is the only file here nobody can opt out of."""

    def test_the_always_loaded_file_stays_small(self):
        # 4800 -> 4900 when the write layer landed its catalogue. Moved
        # deliberately, which is what this file asks for, and the reasoning is
        # the one thing that makes it not a ratchet:
        #
        # SKILL.md has to NAME the write nouns. tests/test_plugin_surface.py
        # asserts that every mutating subcommand appears here, because an agent
        # that does not know a verb exists hand-authors the file instead - and
        # the index entry, log row and vocabulary term that a write implies are
        # then left to be remembered, which is the whole class of defect the
        # write layer removes. So this is a read that buys back a correctness
        # guarantee rather than one that merely explains something.
        #
        # Measured: 4391 before, 4825 after, having twice cut everything
        # redundant with references/write-commands.md - which is where the
        # explanation lives, loaded on demand. 4900 is that plus headroom.
        #
        # 4900 -> 5200 when the read layer landed - `okf search|list|show|refs|
        # stats`. Measured: 4789 before, 5128 after, the addition being five table
        # rows, the fourteen `list` nouns, and the four sentences that say to reach
        # for these before `Grep` or a record dump.
        #
        # This one is a *net saving* and that is the argument for it, rather than
        # the correctness argument the write nouns rest on. An agent that does not
        # know `okf list <bundle> bullets` exists gets a bullet id the only other
        # way there is: `okf compile --dump-record`, which docs/SCRIPTS.md measures
        # at 32,190 bytes on a hundred-target bundle - about 8,000 tokens, and
        # `--for score` cannot narrow it because that flag drops the achievements
        # the ids belong to. So 339 resident tokens replace roughly 8,000 per run,
        # the first time it is needed. `okf list unconfirmed` is the same trade
        # against jsk-bundle-auditor's whole-bundle read.
        #
        # It also buys a smaller correctness guarantee, which is worth naming
        # because it is not measurable: a `Grep` for a phrase cannot see that the
        # bullet it found is `inferred`, and an agent that reaches for `Grep`
        # because it does not know `okf search` exists gets an answer with the
        # provenance stripped off.
        self.assertLess(tokens(SKILL / "SKILL.md"), 5200)


class AgentReadBudget(unittest.TestCase):
    """Each subagent's mandated static reads: its own definition plus the reference
    files it is told to open. The record it compiles is not counted - that scales with
    the person's career, not with anything in this repo - but which flags it compiles
    with are asserted below, because those are what stop it scaling with the job search.
    """

    def test_the_tailor_analyst_reads_only_what_it_ranks_from(self):
        self.assertLess(tokens(AGENTS / "jsk-tailor-analyst.md"), 3200)

    def test_the_resume_author_stays_off_the_record_schema(self):
        """It authors a view and reads the compiled record, so `urs-spec.md` - the
        record's own schema - is the half it does not need. `view-format.md` is the
        half it does, and the split took that read from 4,127 tokens to 968."""
        author = tokens(AGENTS / "jsk-resume-author.md")
        spec = tokens(REFS / "view-format.md")
        rules = tokens(REFS / "ats-rules.md", REFS / "writing-rules.md")
        self.assertLess(author + spec + rules, 8600)

    def test_the_view_format_is_the_smaller_half(self):
        """If it ever grows past the file it was split out of, the split has stopped
        paying for itself and should be reconsidered rather than quietly kept."""
        self.assertLess(tokens(REFS / "view-format.md"),
                        tokens(REFS / "urs-spec.md"))


class TheWritePathReadsNoFormatSpecification(unittest.TestCase):
    """Authoring a concept must not require reading the format's prose.

    `mode-braindump.md` used to open its write section with "Follow
    references/bundle-spec.md. Read two existing project concepts first so you match
    house style" - about 5,330 tokens of specification plus two files off the person's
    own disk, before writing a single frontmatter key. House style is structural now:
    the command emits it, and refuses what it cannot emit correctly.

    So this asserts the read is actually gone rather than merely discouraged, which
    is the one measurement the write layer was sold on and the one most likely to
    creep back the next time somebody documents a key.
    """

    WRITE_MODES = ("mode-braindump.md", "mode-refresh.md", "mode-gaps.md",
                   "mode-tailor.md", "mode-ship.md", "mode-resume.md")

    # An instruction to read something, as these files write one: the imperative
    # at the start of a line or a bolded sentence. Deliberately narrow.
    #
    # A looser rule that matched "read" anywhere flagged mode-braindump.md's own
    # disclaimer - "You do not need to read `bundle-spec.md` to author a concept" -
    # which is the sentence that replaced the instruction. Reading a negation as
    # the thing it negates is the one failure mode a check like this must not have,
    # because the fix a person would reach for is to delete the disclaimer.
    INSTRUCTION = ("Follow ", "Read ", "Open ", "**Follow ", "**Read ", "**Open ")

    def mandated(self, name):
        """The lines that tell a reader to open a file, not the ones about one."""
        return [line for line in (REFS / name).read_text(encoding="utf-8").splitlines()
                if line.strip().startswith(self.INSTRUCTION)]

    def test_no_write_mode_tells_anyone_to_follow_the_bundle_spec(self):
        for name in self.WRITE_MODES:
            for line in self.mandated(name):
                if "bundle-spec.md" not in line:
                    continue
                with self.subTest(mode=name):
                    self.fail(f"{name} still sends a reader to bundle-spec.md to "
                              f"write: {line.strip()!r}. The commands emit house "
                              f"style; if a rule is missing from them, that is the "
                              f"defect rather than the read.")

    def test_the_braindump_path_stays_small(self):
        """SKILL.md plus the mode file, which is the whole mandated read now.

        Measured rather than estimated, because an estimate here was wrong by 450
        tokens on the first try:

            before  SKILL 4,391 + braindump 956 + bundle-spec 6,453 = 11,800
            after   SKILL 4,825 + braindump 1,241              =  6,066

        A 49% cut, and all of it is the specification no longer being read to write
        a concept. bundle-spec.md is 6,453 tokens on its own - larger than the
        design's own estimate of 5,330 - so it was more than half the cost of
        recording one project. The mode file grew by 285 tokens to hold the
        commands, which is the trade.

        6400 -> 6700 with the read layer. 6,050 before, 6,562 after: 339 of it is
        SKILL.md's five rows (see ResidentCost) and 173 is the `okf search` dedupe
        check this mode now opens its write section with.

        That 173 is the cheapest thing in this file. People re-tell the same work
        months apart in different words, and neither telling mentions the other; a
        second concept for one project splits its bullets across two files, so the
        ranking sees two weak projects where there was one strong one. One search
        before the first write costs 173 resident tokens and a command; finding it
        after a resume is written is a merge somebody does by hand.
        """
        self.assertLess(tokens(SKILL / "SKILL.md", REFS / "mode-braindump.md"), 6700)

    def test_the_write_reference_is_loaded_on_demand_and_not_by_a_mode(self):
        """`write-commands.md` is the reference, and it is deliberately NOT a
        mandated read: a mode names the commands it needs inline, and the reference
        is there for the flags. Its size is therefore free, and it must stay off
        every mode's required path or it becomes the read it replaced.
        """
        for name in self.WRITE_MODES:
            for line in self.mandated(name):
                if "write-commands.md" not in line:
                    continue
                with self.subTest(mode=name):
                    self.fail(f"{name} mandates reading write-commands.md: "
                              f"{line.strip()!r}. Name the command inline instead.")


class TheAgentsCompileNarrowly(unittest.TestCase):
    """The flags are the mechanism. A record compiled without them scales with the
    number of postings a person has answered, which is the defect this budget exists
    to prevent - and it is invisible until somebody has applied for eighty jobs.
    """

    def compile_command(self, name):
        """The `okf compile` line the agent is told to run - not the prose around it.

        Both files discuss the flags they do and do not pass, so searching the whole
        file finds an argument against a flag and reads it as the flag. The command
        used to be spelt `okf_compile.py`; it is a subcommand now.
        """
        for line in (AGENTS / name).read_text(encoding="utf-8").splitlines():
            if "okf compile" in line and "--dump-record" in line:
                return line
        self.fail(f"{name}: no `okf compile --dump-record` command found")

    def test_the_analyst_compiles_without_views_or_prose(self):
        """It ranks projects against requirements and never reads a bullet."""
        line = self.compile_command("jsk-tailor-analyst.md")
        for flag in ("--no-views", "--for score", "--compact"):
            with self.subTest(flag=flag):
                self.assertIn(flag, line)

    def test_the_author_compiles_without_views_but_keeps_the_prose(self):
        """`--for score` drops achievement text, which is the thing this agent
        retunes. A well-meaning future edit adding it here for symmetry with the
        analyst would leave the author with nothing to rewrite."""
        line = self.compile_command("jsk-resume-author.md")
        self.assertIn("--no-views", line)
        self.assertIn("--compact", line)
        self.assertNotIn("--for score", line)


class TheMainThreadBudget(unittest.TestCase):
    """What the conversation itself reads on a tailoring run that goes all the way to
    a sent application. Documenting an interface costs tokens in exactly these files,
    so this is the ceiling most likely to be pushed by an honest change."""

    def test_a_tailoring_run_to_ship(self):
        # 10400 -> 10700 with the write layer, and most of the rise is SKILL.md's
        # - see ResidentCost above for why that one is load-bearing.
        #
        # The two mode files rose least and gave the most back. mode-ship.md lost
        # its by-hand filing procedure entirely: `okf application file` performs
        # it, so what is left is why the freeze matters rather than how to
        # perform it, and bundle-spec.md holds the shape. That is the trade this
        # design predicted - "bundle-spec.md stops being a mandated read on the
        # write path" - and it is why the number moved by 300 rather than by the
        # 800 the commands themselves cost to document.
        #
        # 10700 -> 10900 with the read layer. The whole 339-token rise is
        # SKILL.md's; neither mode file here gained a line. `mode-tailor.md` was
        # deliberately left alone - `jsk-tailor-analyst` compiles with
        # `--no-views --for score --compact` because a ranking needs the whole
        # projection, and no query replaces that. A read command documented where
        # it would not be used is a resident cost with nothing behind it.
        self.assertLess(
            tokens(SKILL / "SKILL.md",
                   REFS / "mode-tailor.md",
                   REFS / "mode-ship.md"),
            10900)


if __name__ == "__main__":
    unittest.main()
