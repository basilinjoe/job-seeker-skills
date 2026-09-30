"""The files a render writes, and the scratch directories it stages them in."""
from typing import Any, Protocol


class RenderOutputs(Protocol):
    """Where a render, a preview and a fit put what they produce."""

    def write_text(self, path: str, text: str, encoding: str = "utf-8",
                   errors: str = "strict") -> None:
        """Write `text` to `path`, replacing it, with the platform's line endings.

        Args:
            path: the file.
            text: its whole content.
            encoding: how it is encoded.
            errors: what an unencodable character becomes, as open() takes it.
        """
        ...

    def scratch(self) -> Any:
        """A context manager holding a fresh directory, removed with what is in it on exit."""
        ...

    def replace(self, src: str, dst: str) -> None:
        """Move `src` over `dst`."""
        ...
