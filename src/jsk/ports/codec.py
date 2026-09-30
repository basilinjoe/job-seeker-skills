"""Turtle and TriG in and out of the engine's own terms."""
from typing import Any, Protocol


class GraphCodec(Protocol):
    """Parsing a text into quads, and asking the engine how it keeps a number."""

    def parse_text(self, text: str, file: str, kind: str | None = None) -> Any:
        """Parse one file's text.

        Args:
            text: the Turtle, or TriG for a changeset.
            file: the name findings report it by.
            kind: the record kind; by default the one `file` is named like.

        Returns:
            A domain.record.parsed.Parsed.

        Raises:
            GraphError: a syntax error, with its line.
        """
        ...

    def canonical_numbers(self, quads: list[Any]) -> tuple[list[Any], list[Any]]:
        """Every number in `quads` as the engine keeps it.

        Returns:
            (the quads with each number canonical, [(quad, canonical literal)] for each one
            that changed).
        """
        ...
