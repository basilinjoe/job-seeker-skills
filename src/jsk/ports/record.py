"""Where the career record is kept: its graphs read, the writer's turn, and one write."""
from typing import Any, ContextManager, Protocol


class RecordRepository(Protocol):
    """The record on disk - career/store/ - behind the one gate every write goes through."""

    def exists(self, root: str) -> bool:
        """Whether the workspace at `root` has a store."""
        ...

    def record_graphs(self, root: str) -> dict[str, list[Any]]:
        """Every record graph of the workspace, by name.

        Args:
            root: the workspace root.

        Returns:
            {graph name: triples}; {} in a workspace with no store. Takes shared access for
            the read.
        """
        ...

    def turn(self, root: str, dry_run: bool = False) -> ContextManager[None]:
        """The context a writing command runs in, taken before it reads the record.

        Args:
            root: the workspace root.
            dry_run: no turn is taken for a dry run.

        Returns:
            A context manager holding this process's turn to write, blocking until it is.
        """
        ...

    def write_graphs(self, root: str, graphs: dict[str, Any], create: bool = False) -> None:
        """Replace `graphs` ({name: triples, or None to drop}) in one update, then the backup.

        Raises:
            RecordError: nothing was changed. Written: the update landed and what followed
                failed.
        """
        ...
