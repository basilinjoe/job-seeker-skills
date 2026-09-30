"""decisions.txt read from disk. The format and its parser are in
domain/record/decisions.py; this binds the file read to it."""
from ..domain.record.decisions import HEADER_KEYS as HEADER_KEYS
from ..domain.record.decisions import NEEDS as NEEDS
from ..domain.record.decisions import ROW as ROW
from ..domain.record.decisions import DecisionsError as DecisionsError
from ..domain.record.decisions import Row as Row
from ..domain.record.decisions import Drop as Drop
from ..domain.record.decisions import Decisions as Decisions
from ..domain.record.decisions import parse as parse


def read(path, what=None):
    """Read the decisions.txt at `path` and parse it.

    Args:
        path: the decisions file.
        what: the name a refusal gives the file, or None for its path.

    Returns:
        Decisions: the file's header, rows and drops.

    Raises:
        Missing: when there is no file at `path`.
        Unreadable: when it is not UTF-8.
        DecisionsError: on the first bad line.
    """
    from ..infra.files import read_text

    return parse(read_text(path, what))
