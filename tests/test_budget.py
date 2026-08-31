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
        self.assertLess(tokens(SKILL / "SKILL.md"), 4800)


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


class TheAgentsCompileNarrowly(unittest.TestCase):
    """The flags are the mechanism. A record compiled without them scales with the
    number of postings a person has answered, which is the defect this budget exists
    to prevent - and it is invisible until somebody has applied for eighty jobs.
    """

    def compile_command(self, name):
        """The `okf_compile.py` line the agent is told to run - not the prose around
        it. Both files discuss the flags they do and do not pass, so searching the
        whole file finds an argument against a flag and reads it as the flag."""
        for line in (AGENTS / name).read_text(encoding="utf-8").splitlines():
            if "okf_compile.py" in line and "--dump-record" in line:
                return line
        self.fail(f"{name}: no okf_compile.py --dump-record command found")

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
        self.assertLess(
            tokens(SKILL / "SKILL.md",
                   REFS / "mode-tailor.md",
                   REFS / "mode-ship.md"),
            10400)


if __name__ == "__main__":
    unittest.main()
