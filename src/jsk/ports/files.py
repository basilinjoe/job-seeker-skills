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

    def write_document(self, path: str, text: str) -> str:
        """Replace `path` with `text` atomically, retrying while another process holds it.

        Returns:
            `path`.

        Raises:
            Unwritable: the file could not be replaced after every retry, or the disk
                refused; nothing was written.
        """
        ...

    def remove_document(self, path: str) -> bool:
        """Remove `path` if it is there.

        Returns:
            True when a file was removed, False when there was none.

        Raises:
            Unwritable: the file is there and could not be removed.
        """
        ...

    def rename_directory(self, old: str, new: str) -> None:
        """Rename the application directory `old` to `new`.

        Raises:
            OSError: the rename did not happen.
        """
        ...

    def is_dir(self, path: str) -> bool:
        """Whether `path` is a directory there is."""
        ...

    def free_directory(self, folder: str, stem: str) -> str:
        """The first of `stem`, `stem-2`, `stem-3`... that names nothing in `folder`."""
        ...

    def move_directory(self, old: str, new: str) -> None:
        """Move the directory `old` to `new`, creating the folder `new` goes in.

        Raises:
            OSError: the move did not happen; `new` was there, or the disk refused.
        """
        ...

    def write_new(self, folder: str, target: str, text: str) -> str:
        """Write a new document, creating its folder; never over a file there is.

        Returns:
            `target`.

        Raises:
            FileExistsError: `target` is there.
        """
        ...

    def restore_directory(self, moved: str, back: str) -> bool:
        """Undo rename_directory: rename `moved` back to `back`, never raising.

        Returns:
            True when it was renamed back, False when the disk refused.
        """
        ...
