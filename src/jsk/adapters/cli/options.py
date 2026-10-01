"""The flags the tailoring commands share: `--cover N` and `--today YYYY-MM-DD`, parsed once.

`jsk tailor match`, `jsk tailor prepare` and `jsk kb export --from-match` each parsed them, with
the same messages, three times over. The clock is read here, once, and only when no
--today was given (Ruling 9 of the onion design).
"""
import datetime
from dataclasses import dataclass

from ...application.tailor.match_posting import COVER


class BadOption(Exception):
    """A flag called wrong; its message is the line printed, and the exit is 2."""


@dataclass(frozen=True)
class TailorOptions:
    """What --cover and --today came to."""

    budget: int                 # the most projects the cover may use
    today: datetime.date        # the date recency is measured from


def take_values(argv, flags):
    """Take each of `flags` and the value after it out of `argv`.

    Args:
        argv: the arguments; the flags found and their values are removed from it.
        flags: the flags that take a value, in the order they are looked for.

    Returns:
        {flag: its value} for each flag present.

    Raises:
        BadOption: a flag is the last argument, with no value after it.
    """
    options = {}
    for flag in flags:
        if flag in argv:
            at = argv.index(flag)
            if at + 1 >= len(argv):
                raise BadOption(f"{flag} needs a value")
            options[flag] = argv[at + 1]
            del argv[at:at + 2]
    return options


def tailor_options(cover, today, clock=datetime.date.today):
    """The cover's budget and the day, from --cover's and --today's text.

    Args:
        cover: --cover's value, or None for the default (application.tailor.match_posting.COVER).
        today: --today's value, or None for the clock's date.
        clock: () -> today's date, called only when `today` is None.

    Returns:
        The TailorOptions.

    Raises:
        BadOption: --cover is not a whole number of at least 1, or --today not a date.
    """
    try:
        budget = int(COVER if cover is None else cover)
        day = datetime.date.fromisoformat(today) if today is not None else clock()
    except ValueError:
        raise BadOption("--cover takes a whole number and --today a YYYY-MM-DD date") from None
    if budget < 1:
        raise BadOption("--cover takes a whole number of at least 1")
    return TailorOptions(budget, day)
