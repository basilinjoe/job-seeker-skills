"""A market's conventions, as the region profiles shipped under data/ state them."""
from typing import Any, Protocol


class Profiles(Protocol):
    """The region profiles a resume is built under."""

    def load(self, ref: str | None, base: str | None = None) -> dict[str, Any]:
        """A profile by id (`urs:profile:au/1`), region code (`AU`) or path.

        Args:
            ref: which profile; None, or one that does not ship, gives the default.
            base: the schema directory; by default the packaged one.

        Returns:
            The profile as a dict. Reads one JSON file.
        """
        ...
