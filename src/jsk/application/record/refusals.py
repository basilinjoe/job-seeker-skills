"""How a use case over the record refuses: nothing was written, and each error says why.

The CLI adapter prints them (adapters/cli/presenters.py); nothing here prints.
"""


class Refused(Exception):
    """A refusal: what is wrong, a line each, and the one fix for all of them."""

    def __init__(self, lines, fix=None):
        super().__init__("; ".join(lines))
        self.lines = list(lines)
        self.fix = fix


class Problems(Exception):
    """A refusal of several things at once, each with its own fix: [(detail, fix)]."""

    def __init__(self, problems):
        super().__init__("; ".join(detail for detail, _ in problems))
        self.problems = list(problems)


class Failing(Exception):
    """A record whose FAIL findings stop the command.

    `findings` are the domain.record.shapes.Finding that stop it, `title` the line said
    above them, and `written` whether "nothing was written" follows: a command that never
    writes does not say so.
    """

    def __init__(self, findings, title, written=True):
        super().__init__(title)
        self.findings = list(findings)
        self.title = title
        self.written = written


class Unclean(Exception):
    """A record in a state no command may write over or answer from: `state` says which
    (domain.record.state.State), and the adapter says the fix."""

    def __init__(self, state):
        super().__init__(state.kind)
        self.state = state
