"""What a gate returns: its failures and warnings, or why it stopped before judging.

Every gate's use case returns a GateResult (a subclass carrying what its heading prints)
and raises GateStopped for the calls it will not judge. The adapters print them; `jsk
gates` reads the counts off the result rather than off the text the gate printed.
"""
from dataclasses import dataclass


class GateStopped(Exception):
    """A gate that stopped before it judged anything.

    `kind` says why (each gate names its own: "no-pdf-library", "format", "skipped", ...),
    `detail` is what the adapter needs to say it, and `code` is the exit code.
    """

    def __init__(self, kind, detail, code):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
        self.code = code


@dataclass(frozen=True)
class GateResult:
    """A gate's findings over one document, each tuple in the order they were found."""

    fails: tuple
    warns: tuple

    @property
    def code(self):
        """1 when anything failed, else 0: every gate's exit code for a verdict."""
        return 1 if self.fails else 0


@dataclass(frozen=True)
class Unreadable(GateResult):
    """A document the gate could not open: one failure saying why, and no warnings."""

    name: str


def unreadable(name, reason):
    """The verdict on a document that would not open.

    Args:
        name: the document's file name, as the heading prints it.
        reason: the failure line, as the gate words it.

    Returns:
        An Unreadable holding that one failure.
    """
    return Unreadable(fails=(reason,), warns=(), name=name)
