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
    # Counted with LF line endings whatever the checkout wrote. A clone with
    # core.autocrlf=true adds a byte per line, which moved the resume author's
    # total across its ceiling on a fresh Windows checkout and nowhere else.
    return sum(len(p.read_bytes().replace(b"\r\n", b"\n")) for p in paths) // 4


class ResidentCost(unittest.TestCase):
    """SKILL.md loads whenever the skill triggers, for every mode, before anyone has
    said what they want. It is the only file here nobody can opt out of."""

    def test_the_always_loaded_file_stays_small(self):
        # 5200 -> 4400 when the career became one file. Measured: 5128 before,
        # 4246 after.
        #
        # Almost all of the fall is a surface that stopped existing. SKILL.md had
        # to NAME every write noun and every read verb - thirty-odd commands, plus
        # the fourteen `list` nouns - because an agent that does not know a verb
        # exists hand-authors the file instead, and the index entry, log row and
        # vocabulary term that a write implies were then left to be remembered.
        # There is one file now, so hand-authoring IS the interface: eight
        # subcommands, none of which writes anything a person owns.
        #
        # This ceiling is the one number in this file that should be defended
        # hardest, because SKILL.md loads for every mode before anyone has said
        # what they want.
        #
        # 4400 -> 2400 when SKILL.md became a router. Measured: 4,246 before, 2,202
        # after. What left was history (how the write layer and the compiler used to
        # work), gate and agent detail each mode file already carries, and rationale
        # paragraphs that rationale.md holds in long form.
        self.assertLess(tokens(SKILL / "SKILL.md"), 2400)


class AgentReadBudget(unittest.TestCase):
    """Each subagent's mandated static reads: its own definition plus the reference
    files it is told to open. The record it compiles is not counted - that scales with
    the person's career, not with anything in this repo - but which flags it compiles
    with are asserted below, because those are what stop it scaling with the job search.
    """

    def test_the_tailor_analyst_reads_only_what_it_ranks_from(self):
        # 3200 -> 2300: 2,841 -> 2,096 measured, history and rationale cut.
        self.assertLess(tokens(AGENTS / "jsk-tailor-analyst.md"), 2300)

    def test_the_resume_author_reads_both_halves_of_the_record_spec(self):
        """It writes the record by hand now, so `urs-spec.md` went from the half it
        did not need to the half it cannot do without.

        This ceiling went UP - 8,600 to 11,400 - and that is the cost of removing the
        compiler, stated rather than absorbed. A compiled record could not carry an
        unrecognised key, so the agent needed only the view format; a hand-written one
        can, and `experience:` written where `engagements:` belongs renders a resume
        with no jobs on it. 3,727 tokens of schema against a defect invisible in the
        PDF is the trade, and it is the right way round.
        """
        author = tokens(AGENTS / "jsk-resume-author.md")
        spec = tokens(REFS / "view-format.md", REFS / "urs-spec.md")
        rules = tokens(REFS / "ats-rules.md", REFS / "writing-rules.md")
        # 11400 -> 7600: 11,214 -> 7,138 measured. Every key, type and shape stayed;
        # the prose around them, and each half's account of why it was split, went.
        self.assertLess(author + spec + rules, 7600)

    def test_the_view_format_is_the_smaller_half(self):
        """If it ever grows past the file it was split out of, the split has stopped
        paying for itself and should be reconsidered rather than quietly kept."""
        self.assertLess(tokens(REFS / "view-format.md"),
                        tokens(REFS / "urs-spec.md"))


class TheWritePathStaysCheap(unittest.TestCase):
    """Recording one project must not cost the whole format specification.

    This class used to assert the opposite thing by the same measure. `mode-braindump.md`
    opened its write section with "Follow references/bundle-spec.md. Read two existing
    project concepts first so you match house style" - 6,453 tokens of specification
    plus two files off the person's own disk, before writing a single frontmatter key.
    The write layer removed that read entirely: the command emitted house style, so the
    spec became something nobody on the write path opened.

    There is no write layer over one Markdown file. So the read is legitimate again -
    `kb-spec.md` is how anybody knows what a project block looks like - and what can
    still be asserted is the weaker, honest statement: it is not MANDATED, because the
    mode names the shape it needs inline, and the ordinary case of adding a project to
    a file that already has projects reads neither.
    """

    WRITE_MODES = ("mode-braindump.md", "mode-refresh.md", "mode-gaps.md",
                   "mode-tailor.md", "mode-ship.md", "mode-resume.md")

    # An instruction to read something, as these files write one: the imperative
    # at the start of a line or a bolded sentence. Deliberately narrow.
    #
    # A looser rule that matched "read" anywhere flagged mode-braindump.md's own
    # disclaimer - the sentence that replaced the instruction. Reading a negation as
    # the thing it negates is the one failure mode a check like this must not have,
    # because the fix a person would reach for is to delete the disclaimer.
    INSTRUCTION = ("Follow ", "Read ", "Open ", "**Follow ", "**Read ", "**Open ")

    def mandated(self, name):
        """The lines that tell a reader to open a file, not the ones about one."""
        return [line for line in (REFS / name).read_text(encoding="utf-8").splitlines()
                if line.strip().startswith(self.INSTRUCTION)]

    def test_no_write_mode_mandates_the_format_specification(self):
        for name in self.WRITE_MODES:
            for line in self.mandated(name):
                if "kb-spec.md" not in line:
                    continue
                with self.subTest(mode=name):
                    self.fail(f"{name} mandates reading kb-spec.md: {line.strip()!r}. "
                              f"Name the block shape inline instead - the spec is for "
                              f"the case the mode does not already cover.")

    def test_the_braindump_path_stays_small(self):
        """SKILL.md plus the mode file, which is the whole mandated read.

        Measured rather than estimated, because an estimate here was wrong by 450
        tokens on the first try:

            bundle era   SKILL 4,391 + braindump   956 + bundle-spec 6,453 = 11,800
            write layer  SKILL 5,128 + braindump 1,241                     =  6,369
            one file     SKILL 4,246 + braindump 1,414                     =  5,660

        The middle row was the write layer removing the specification read; the last
        is SKILL.md losing a command surface that no longer exists. The mode file grew
        both times, and both times that was the trade - it now carries the four
        sections a project touches and the ids that have to agree across them, which
        is what nothing checks any more.
        """
        #   router       SKILL 2,202 + braindump   890                     =  3,092
        self.assertLess(tokens(SKILL / "SKILL.md", REFS / "mode-braindump.md"), 3300)

    def test_the_format_specification_is_loaded_on_demand(self):
        """`kb-spec.md` is the reference, and its size is therefore free - but only
        while it stays off every mode's required path. The moment a mode mandates it,
        it becomes the read it replaced, and 3,121 tokens land on recording one
        project.
        """
        self.assertLess(tokens(REFS / "kb-spec.md"), 2400)


class TheAgentsReadTheFileWhole(unittest.TestCase):
    """How an agent gets the career into its context.

    This class used to assert three compile flags. `--no-views` kept a bundle that had
    answered eighty postings from handing eighty of them to an agent that needed none;
    `--for score` dropped the achievement prose for the one agent that ranks and never
    reads a bullet. Both were real, and both were solving a problem the folder created:
    a record assembled out of 345 concepts, most of which no verdict was computed from.

    One file has no such problem, so the flags went with the compiler. What replaced
    them is an instruction - read it once, as a file - and the failure it guards is the
    opposite of the old one: not too much read at once, but the same content read
    twenty times through greps, each one a round trip.
    """

    def body(self, name):
        return (AGENTS / name).read_text(encoding="utf-8")

    def test_neither_agent_is_sent_at_a_compile(self):
        """A stale instruction here sends an agent at a command that no longer exists,
        and the run stops on a `unknown command` before it has read anything."""
        for name in ("jsk-tailor-analyst.md", "jsk-resume-author.md"):
            with self.subTest(agent=name):
                self.assertNotIn("compile <", self.body(name))
                self.assertNotIn("--dump-record", self.body(name))
                self.assertNotIn("--for score", self.body(name))

    def test_both_agents_are_told_to_read_it_once_as_a_file(self):
        for name in ("jsk-tailor-analyst.md", "jsk-resume-author.md"):
            with self.subTest(agent=name):
                self.assertIn("whole", self.body(name))
                self.assertIn("user-knowledgebase.md", self.body(name))

    def test_the_author_is_warned_off_a_sibling_application(self):
        """The one read that got MORE dangerous. A record written for another posting
        is now a complete, valid, hand-written example of exactly the file this agent
        is about to write - which makes it a template to copy, and a tailored resume
        that copies one has stopped being tailored."""
        self.assertIn("Do not read a record written for a different posting",
                      self.body("jsk-resume-author.md"))


class TheMainThreadBudget(unittest.TestCase):
    """What the conversation itself reads on a tailoring run that goes all the way to
    a sent application. Documenting an interface costs tokens in exactly these files,
    so this is the ceiling most likely to be pushed by an honest change."""

    def test_a_tailoring_run_to_ship(self):
        # 10900 -> 10100 when the career became one file. Measured: 10,900 before,
        # 9,841 after.
        #
        # SKILL.md gave back 882 of it by losing a command surface. The two mode
        # files roughly held: mode-tailor.md lost the compile and the write commands
        # and gained the application directory; mode-ship.md lost `jsk application
        # file` - which performed the freeze - and gained the four edits that
        # replace it, because freezing a directory by hand is something somebody has
        # to be told how to do.
        #
        # That last one is the shape of this whole change in one file: a command
        # that did a thing correctly becomes a paragraph telling a model to do it
        # correctly. Cheaper to read, and one more thing nothing checks.
        #
        # 10100 -> 6000, and the freeze went back to being a command. Measured:
        # 9,841 -> 5,613. `jsk ship` replaced three gate steps and `jsk freeze` the
        # hand-written freeze, so the paragraph became an invocation that refuses
        # when a gate fails; the rest was history and rationale.
        self.assertLess(
            tokens(SKILL / "SKILL.md",
                   REFS / "mode-tailor.md",
                   REFS / "mode-ship.md"),
            6000)


if __name__ == "__main__":
    unittest.main()
