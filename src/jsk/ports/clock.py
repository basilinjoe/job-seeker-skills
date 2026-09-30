"""Today, read once at the edge (Ruling 9) and passed down as a value."""
import datetime
from typing import Protocol


class Clock(Protocol):
    """The one place a command learns the date."""

    def today(self) -> datetime.date:
        """The current local date."""
        ...
