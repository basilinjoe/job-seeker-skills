"""Where a posting's advertisement comes from: a job board's public API, or a file."""
from typing import Any, Protocol


class PostingSource(Protocol):
    """A board's API answered over the network; the one seam `posting_capture` crosses."""

    def get(self, api_url: str) -> Any:
        """The board's JSON answer for `api_url`, parsed.

        Raises:
            NotOnBoard: the board answered, and the posting is not on it.
            Refused: the network failed, with the fix.
        """
        ...
