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
        #
        # Ceiling kept at 2400 when the career became a graph record. Measured: 2,282
        # before, 2,169 after. "Editing the knowledge base" - three habits standing in
        # for a write command - became one rule naming the write command, `jsk kb
        # apply`, and `jsk index` left the table; the claims gate, `jsk migrate` and
        # `jsk event` came in. The okf lesson is the reason it fell rather than grew:
        # the subverbs live in `jsk kb --help` and in each refusal's fix line, not here.
        #
        # Held at 2400 when the URS record went (2026-09-25): 2,251 -> 2,191 measured. The
        # claims gate's row and its `NOT RUN` sentence, `--view` on two commands and the
        # two-halves spec pointer left; `resume-format.md` came in as one name.
        self.assertLess(tokens(SKILL / "SKILL.md"), 2400)


class AgentReadBudget(unittest.TestCase):
    """Each subagent's mandated static reads: its own definition plus the reference
    files it is told to open. The record it compiles is not counted - that scales with
    the person's career, not with anything in this repo - but which flags it compiles
    with are asserted below, because those are what stop it scaling with the job search.
    """

    def test_the_tailor_analyst_reads_only_what_it_ranks_from(self):
        # 3200 -> 2300: 2,841 -> 2,096 measured, history and rationale cut.
        # Ceiling kept when it moved to posting.ttl and `jsk match`: 2,188 -> 1,754. The
        # weights table it applied by hand left with the arithmetic; an inline
        # posting.ttl, so it never needs kb-format.md, came in.
        self.assertLess(tokens(AGENTS / "jsk-tailor-analyst.md"), 2300)

    def test_the_resume_author_reads_the_short_file_format_and_the_rules(self):
        """It wrote the record by hand, so `urs-spec.md` went from the half it did not
        need to the half it could not do without - and went back again when `jsk kb
        export` came to write every key but the view and the narrative. Then the record
        itself went: the author reads `resume-format.md`, the short file's every key.

        This ceiling once went UP - 8,600 to 11,400 - the cost of removing the compiler,
        stated rather than absorbed: a hand-written record could carry an unrecognised
        key, and `experience:` written where `engagements:` belongs rendered a resume
        with no jobs on it. The short file refuses an unknown key itself, so the schema
        the author reads is a table of ten keys.
        """
        author = tokens(AGENTS / "jsk-resume-author.md")
        spec = tokens(REFS / "resume-format.md")
        rules = tokens(REFS / "ats-rules.md", REFS / "writing-rules.md")
        # 11400 -> 7600: 11,214 -> 7,138 measured. Every key, type and shape stayed;
        # the prose around them, and each half's account of why it was split, went.
        #
        # 7600 -> 7200: 7,211 -> 7,124 measured, the author alone 1,842 -> 1,754. It
        # stopped reading user-knowledgebase.md whole: `jsk match` then `jsk kb show
        # <ids>` hands it only the entries the posting selects, and the Markdown bullet
        # shape it had to copy became a four-line changeset. The fall is small because
        # the changeset carries its own prefix block rather than sending the author to
        # kb-format.md for it - that read would have cost 1,788.
        #
        # Held at 7200: 7,169 -> 7,160 measured, the author 1,796 -> 1,787. `export
        # --from-match` took the choosing - the allocation table, ordering `include` and
        # the skills - but the author must now name its own inferred bullets with
        # --select and copy the GAP lines, which cost nearly what the table did.
        #
        # 7200 -> 5000: 7,160 -> 4,807 measured, the author 1,787 -> 2,105. On the
        # ElevenLabs run it read urs-spec.md and the 11.8KB example record to edit a
        # record the export had already written; both left, and a narrative's one
        # shape came in. The author grew by what the run cost: the order of career
        # changes before the export, `--refresh` over a delete and re-export, the
        # WARN that is a question rather than a number to change.
        #
        # 5000 -> 4800: 4,809 -> 4,607 measured, the author 2,105 -> 1,786 and the format
        # it reads 509 (view-format.md) -> 625 (resume-format.md). The URS record went
        # (2026-09-25): the view keys, `include`, `view_draft`, the narrative's JSON
        # shape, reading only the end of the record and `--refresh` all left with it -
        # there is no copy of the career to read the end of or to refresh. The format
        # grew by what the short file needs said once: a confirmed summary's one edit,
        # everything the record gate fails, and `jsk migrate` for a legacy record.
        self.assertLess(author + spec + rules, 4800)


class TheWritePathStaysCheap(unittest.TestCase):
    """Recording one project must not cost the whole format specification.

    This class used to assert the opposite thing by the same measure. `mode-braindump.md`
    opened its write section with "Follow references/bundle-spec.md. Read two existing
    project concepts first so you match house style" - 6,453 tokens of specification
    plus two files off the person's own disk, before writing a single frontmatter key.
    The write layer removed that read entirely: the command emitted house style, so the
    spec became something nobody on the write path opened.

    There was no write layer over one Markdown file, so the read became legitimate
    again - `kb-spec.md` was how anybody knew what a project block looked like.

    The graph record has one write command again, `jsk kb apply`, but its input is a
    changeset in the record's own format, so the reference - now `kb-format.md` - is
    still the thing that says what an entry looks like. What is asserted stays the
    honest statement: it is not MANDATED, because the mode shows the changeset it needs
    inline, and apply's refusals name the fix for anything the example did not cover.
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

    # The two agents that write a record file: the analyst writes posting.ttl, the
    # author a changeset. Each carries the shape it writes inline for the same reason.
    WRITE_AGENTS = ("jsk-tailor-analyst.md", "jsk-resume-author.md")

    def mandated(self, path):
        """The lines that tell a reader to open a file, not the ones about one."""
        return [line for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith(self.INSTRUCTION)]

    def test_no_write_path_mandates_the_format_specification(self):
        paths = [REFS / n for n in self.WRITE_MODES] + [AGENTS / n for n in self.WRITE_AGENTS]
        for path in paths:
            for line in self.mandated(path):
                if "kb-format.md" not in line:
                    continue
                with self.subTest(file=path.name):
                    self.fail(f"{path.name} mandates reading kb-format.md: {line.strip()!r}. "
                              f"Show the changeset inline instead - the reference is for "
                              f"the case the file does not already cover.")

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
        #   graph        SKILL 2,169 + braindump 1,041                     =  3,210
        #
        # The last row is the graph record: SKILL.md's hand-edit habits became one
        # rule, and the mode's four-sections-in-order paragraph became a worked
        # changeset with its prefix block - the one thing apply cannot infer.
        self.assertLess(tokens(SKILL / "SKILL.md", REFS / "mode-braindump.md"), 3300)

    def test_the_format_specification_is_loaded_on_demand(self):
        """`kb-format.md` is the reference, and its size is therefore free - but only
        while it stays off every write path. The moment a mode or a writing agent
        mandates it, it becomes the read it replaced, and its tokens land on recording
        one project.
        """
        # New file, new ceiling: 1,788 measured. It replaced kb-spec.md (2,315, under a
        # 2400 ceiling), which described thirteen Markdown headings and the block under
        # each. kb-format.md describes the Turtle file a model must read and draft: the
        # banners, one table row per class with every predicate, provenance, and a
        # changeset. Smaller because the predicates are a table, not an example per
        # section; `jsk kb apply`'s refusals carry what an example used to.
        self.assertLess(tokens(REFS / "kb-format.md"), 2000)


class TheAgentsReadTheFileWhole(unittest.TestCase):
    """How an agent gets the career into its context.

    This class used to assert three compile flags. `--no-views` kept a bundle that had
    answered eighty postings from handing eighty of them to an agent that needed none;
    `--for score` dropped the achievement prose for the one agent that ranks and never
    reads a bullet. Both were real, and both were solving a problem the folder created:
    a record assembled out of 345 concepts, most of which no verdict was computed from.

    One file had no such problem, so the flags went with the compiler. What replaced
    them was an instruction - read it once, as a file - guarding the opposite failure:
    the same content read twenty times through greps, each one a round trip.

    The graph record answers both with a query. `jsk match` does the selection a
    whole read was for, and `jsk kb show <ids>` reads exactly the entries it selected,
    so neither writing agent reads the career whole any more.
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

    def test_the_author_reads_the_assessment_then_only_the_entries_it_uses(self):
        """On the ElevenLabs run the author re-ran the `jsk match` the analyst had
        already copied into gaps.md, then showed the same six projects twice - once
        with --bullets, once without, 41.5KB of notes it read back from a spill file."""
        body = self.body("jsk-resume-author.md")
        self.assertIn("do not re-run `jsk match`", body)
        self.assertIn("jsk kb show <the prj_ ids gaps.md ranks> --bullets", body)
        self.assertIn("never the same ids twice", body)
        self.assertIn("not the whole career", body)

    def test_the_author_edits_ids_and_settings_and_the_career_first(self):
        """It read the 52KB export whole to edit the view and the summary - the last
        two keys - and after a re-export read it again; the ElevenLabs author then
        refreshed a record the career had moved under. The short file holds no copy to
        read the end of or to refresh: every word goes into the career before the export,
        and the author edits only the order, the summary and the page settings."""
        body = " ".join(self.body("jsk-resume-author.md").split())
        self.assertIn("Every new or reworded bullet goes into the career before the export", body)
        self.assertIn("jsk kb export --from-match", body)
        self.assertIn("**Then edit only** `bullets`", body)
        for gone in ("--refresh", "--urs", "view_draft", "include", "narrative",
                     "Read only the end of the record"):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, body)

    def test_the_analyst_runs_the_match_and_reads_what_it_cites(self):
        """The analyst stopped reading the file whole. On the ABB run it read 165k
        characters and then spent six and a half minutes in one reasoning turn,
        most of it 900 exact-string lookups and the arithmetic over them - which
        a command does in milliseconds and cannot miscount. That command was `jsk
        index --rank`; it is `jsk match` now, which matches through the vocabulary
        rather than by exact string. The analyst reads the entries it cites, and no
        more, and no index is named anywhere: it is leaving with the Markdown."""
        analyst = self.body("jsk-tailor-analyst.md")
        self.assertIn("jsk match applications/<stem>/posting.ttl", analyst)
        self.assertIn("Read a project before citing it as evidence", analyst)
        self.assertIn("Do not read the whole career", analyst)
        self.assertNotIn("jsk index", analyst)

    def test_the_author_is_warned_off_a_sibling_application(self):
        """The one read that got MORE dangerous. A record written for another posting
        is now a complete, valid, hand-written example of exactly the file this agent
        is about to write - which makes it a template to copy, and a tailored resume
        that copies one has stopped being tailored. A master record is the same
        template by another name, so the warning names it too."""
        body = self.body("jsk-resume-author.md")
        self.assertIn("Do not read any other `resume.json`", body)
        self.assertIn("master", body)

    def test_the_author_is_handed_its_paths_rather_than_searching(self):
        """Left to find its own rules and shape reference, the author spent its first
        fifty seconds on `find` and `ls` - and opened a sibling record and the master
        on the way. The caller resolves the paths; the agent reads only those."""
        self.assertIn("never search for rules, references or examples",
                      self.body("jsk-resume-author.md"))
        # The example record left with the hand-written record: an exported one is
        # already the shape, and 11.8KB of someone else's resume was a template to copy.
        # The URS specification followed it; the one format reference named is the
        # short file's.
        tailor = (REFS / "mode-tailor.md").read_text(encoding="utf-8")
        self.assertNotIn("EXAMPLE_RECORD", tailor)
        self.assertNotIn("urs-spec.md", tailor)
        self.assertIn("references/resume-format.md", self.body("jsk-resume-author.md"))

    def test_applications_live_beside_the_knowledge_base(self):
        """Written as a bare `applications/<stem>`, a session resolved it against its
        working directory and grew a second applications/ that the been-here-before
        check never looks in. SKILL.md anchors it once; the step that creates the
        directory names the anchor."""
        self.assertIn("`applications/` is the directory beside `career/`",
                      (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("<workspace>/applications/<stem>/",
                      (REFS / "mode-tailor.md").read_text(encoding="utf-8"))

    def test_a_second_round_is_a_patch_not_a_second_analyst(self):
        """On the ABB run a second analyst round took 193 seconds to rewrite a whole
        gaps.md whose changes were four verdicts and a struck question - and the main
        thread then patched a row itself in two. Row-local changes are the caller's;
        the analyst comes back only for the fit or a row that does not exist yet.

        The caller used to rescore a project by hand with the analyst's weights,
        restated in one line, and this test kept the two statements agreeing. `jsk
        match` prints the weights and the scores, so the caller re-runs it instead and
        neither file restates them - one statement cannot disagree with itself."""
        tailor = (REFS / "mode-tailor.md").read_text(encoding="utf-8")
        self.assertIn("Patch it yourself when every change is a row", tailor)
        self.assertIn("Re-run `jsk match`", tailor)
        self.assertNotIn("+3 a required term", tailor)
        self.assertNotIn("×3", self.body("jsk-tailor-analyst.md"))


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
        #
        # Ceiling kept at 6000 when the career became a graph record. Measured: 5,999
        # before, 5,105 after (SKILL 2,169, tailor 1,628, ship 1,306). mode-tailor.md
        # gave back 636: `jsk match` ranks, so the posting frontmatter, the weights and
        # the hand-rescoring left, and a round's answers became one changeset and one
        # confirm instead of a scripted find-and-replace. mode-ship.md lost the
        # hand-appended timeline rows to `jsk event` and gained the claims gate.
        #
        # Held at 6000 through the ElevenLabs run (2026-09-25). Measured: 5,995 before,
        # 5,998 after. Three commands replaced hand work and each cost its sentence:
        # `jsk posting fetch` (the posting had been fetched with hand-written curl),
        # ship's `=== summary` (`tail -60` had cut the record and claims gates off, so
        # it shipped twice) and `export --refresh` (the confirmed bullets had been
        # flipped in resume.json by an inline script). The prose they displaced paid
        # for them: the example record's path, and reasons restated beside rules.
        #
        # 6000 -> 5900 when the URS record went (2026-09-25). Measured: 5,998 -> 5,773
        # (SKILL 2,191, tailor 2,211, ship 1,370). mode-ship.md gave back 145: the claims
        # gate's paragraph and the `NOT RUN` one went with the gate, and a withheld line is
        # confirmed in the career and re-shipped rather than refreshed into the record.
        # mode-tailor.md lost the `--refresh` sentence: after a confirm nothing in
        # resume.json changes except a confirmed summary's status.
        self.assertLess(
            tokens(SKILL / "SKILL.md",
                   REFS / "mode-tailor.md",
                   REFS / "mode-ship.md"),
            5900)


if __name__ == "__main__":
    unittest.main()
