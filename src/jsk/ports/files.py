"""The workspace's own files: the texts people and agents write, and an application's."""
from typing import Protocol


class TextFiles(Protocol):
    """Every authored text read one way: UTF-8, no BOM, LF only."""

    def read_text(self, path: str, what: str | None = None) -> str:
        """The file's text, normalised.

        Args:
            path: the file.
            what: how the message names it; by default the path.

        Raises:
            Missing, NotUtf8, Unreadable: with the fix.
        """
        ...


class ApplicationFiles(Protocol):
    """An application directory's files, written so a reader never sees half of one."""

    def write_document(self, path: str, text: str) -> None:
        """Replace `path` with `text` atomically, retrying while another process holds it.

        Raises:
            OSError: the file could not be replaced after every retry.
        """
        ...
