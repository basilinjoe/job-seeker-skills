"""An application's folder and its record graphs, as the timeline's rules read and write them."""
from typing import Any, Protocol


class ApplicationRecords(Protocol):
    """Where an application lives: its folder on disk, and its graphs in the workspace's store."""

    def workspace_of_app(self, app_dir: str) -> tuple[str | None, str | None]:
        """Where `app_dir` sits.

        Returns:
            (workspace root, `applications/<dir>`) as the disk spells them, else (None, None).
        """
        ...

    def has_store(self, root: str) -> bool:
        """Whether the workspace at `root` has a store."""
        ...

    def read_store(self, root: str) -> dict[str, list[Any]]:
        """{graph name: triples} of every graph the store at `root` holds, as it holds them.

        Raises:
            StoreError: the store will not open.
        """
        ...

    def write_graphs(self, root: str, graphs: dict[str, Any]) -> None:
        """Replace `graphs` ({name: triples, or None to drop}) in one update, then the backup.

        Raises:
            RecordError: nothing was changed. Written: the update landed and what followed
                failed.
        """
        ...

    def file_name(self, path: str, root: str) -> str:
        """How a finding names `path`: relative to the workspace, as the disk spells it."""
        ...

    def is_file(self, path: str) -> bool:
        """Whether `path` is a file there is."""
        ...

    def read_text(self, path: str, what: str) -> str:
        """An authored file's text.

        Raises:
            Missing, Unreadable: with the fix.
        """
        ...

    def write_document(self, path: str, text: str) -> str:
        """Write a document in an application's folder, whole or not at all.

        Returns:
            The path written.

        Raises:
            Unwritable: the file is locked, or the disk refused.
        """
        ...

    def remove_document(self, path: str) -> bool:
        """Remove `path` if it is there.

        Returns:
            True when a file was removed.

        Raises:
            Unwritable: it is there and could not be removed.
        """
        ...
