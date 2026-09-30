"""A workspace as loading it needs it: the record's stored graphs, and the files beside it."""
from typing import Any, Protocol


class WorkspaceSource(Protocol):
    """Where a load reads from: career/store/ for the record, the disk for everything else."""

    def absolute(self, root: str) -> str:
        """`root` as an absolute path, the form every finding's graph name is made from."""
        ...

    def record_graphs(self, root: str) -> dict[str, list[Any]]:
        """{graph name: triples} out of career/store/; {} in a workspace with no record.

        Raises:
            GraphError: the career is still laid out as files, or the store will not open.
        """
        ...

    def is_file(self, path: str) -> bool:
        """Whether `path` is a file there is."""
        ...

    def graph_name(self, path: str, root: str) -> str:
        """The record graph a file holds, by the name findings use for it."""
        ...

    def file_name(self, path: str, root: str) -> str:
        """How a finding names a file: relative to the workspace, as the disk spells it."""
        ...

    def parse(self, path: str) -> Any:
        """A file on disk, parsed.

        Returns:
            A domain.record.parsed.Parsed.

        Raises:
            GraphError: a syntax error, which the load reports as a finding. Unreadable:
                the file could not be read at all.
        """
        ...
