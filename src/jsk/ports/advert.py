"""An application's own texts the record's rules read beside its graphs: the advert and the
analyst's decisions."""
from typing import Any, Protocol


class AdvertSource(Protocol):
    """The files beside an application's graphs, by the folder the graphs name."""

    def advert(self, root: str, folder: str) -> str:
        """The advert an application answers: the posting.md in its folder, normalised.

        Args:
            root: the workspace root.
            folder: the application's folder, relative to `root`, as its graph names it
                (`applications/acme`).

        Returns:
            posting.md's text.

        Raises:
            Missing, NotUtf8, Unreadable: posting.md could not be read, its path in the
                message.
        """
        ...

    def legacy_frozen(self, root: str, folder: str) -> bool:
        """Whether the application in `folder` was frozen as an application.md, the record
        a frozen application kept before the career was a graph.

        Args:
            root: the workspace root.
            folder: the application's folder, relative to `root`.

        Returns:
            True when application.md is there.
        """
        ...

    def decisions(self, root: str, folder: str) -> Any:
        """The decisions.txt in an application's folder, parsed.

        Args:
            root: the workspace root.
            folder: the application's folder, relative to `root`.

        Returns:
            A domain.record.decisions.Decisions.

        Raises:
            Unreadable: decisions.txt could not be read (Missing when there is none).
            DecisionsError: on its first bad line.
        """
        ...
