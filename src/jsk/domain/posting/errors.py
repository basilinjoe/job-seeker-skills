"""The name of an application's advertisement, and how a posting step refuses."""

# The advertisement as fetched, beside the application's other files. Every posting step
# finds it by this name, so the name is said once.
POSTING = "posting.md"

# The fallback every fetch failure names: a posting jsk cannot read is still one a browser can.
BROWSER_FIX = ("fix:  fetch it with a browser tool and write posting.md with the Write "
               "tool - the advertisement verbatim, the URL on its first line")


class Refused(Exception):
    """A refusal: its message, then the fix line. `problems` is every (message, fix) it
    holds - several when `jsk posting build` found more than one, since a build that
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
