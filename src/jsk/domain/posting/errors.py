"""The name of an application's advertisement, and how a posting step refuses."""

# The advertisement of an application made from files, beside its other files: what marks
# one as file-made, and what a frozen one's quotes are still checked against (Ruling 2 of
# docs/superpowers/plans/2026-10-03-retire-file-pipeline.md). Said once.
POSTING = "posting.md"

# The fallback every fetch failure names: a posting jsk cannot read is still one a browser
# can. It said to write posting.md by hand until 6.0, when the file pipeline retired.
BROWSER_FIX = ("fix:  open it in a browser and capture the advertisement verbatim as text "
               "(`posting_capture` with text)")


class Refused(Exception):
    """A refusal: its message, then the fix line. `problems` is every (message, fix) it
    holds - several when a batch of decisions has more than one, since a build that
    stopped at the first cost Schneider's run six builds."""

    def __init__(self, message, fix, problems=None):
        """Hold one refusal, or several under a summary message.

        Args:
            message: what was wrong - the summary when `problems` holds several.
            fix: the fix line for `message`.
            problems: every (message, fix); by default just this one.
        """
        super().__init__(message)
        self.fix = fix
        self.problems = problems or [(message, fix)]

    @classmethod
    def every(cls, problems):
        """One refusal holding every (message, fix): the problem itself when there is one,
        else the count, each problem keeping its own fix."""
        if len(problems) == 1:
            return cls(*problems[0])
        return cls(f"{len(problems)} problems", "fix:  each problem above has its own fix",
                   problems)


class NotOnBoard(Exception):
    """The board answered, and this posting is not on it."""
