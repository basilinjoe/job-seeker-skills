"""gaps.txt read from disk. The overlay's format and its parser are in
domain/assessment/overlay.py; this binds the file read to it."""
from ..domain.assessment.overlay import KEYED as KEYED
from ..domain.assessment.overlay import ONCE as ONCE
from ..domain.assessment.overlay import MARK as MARK
from ..domain.assessment.overlay import AssessmentError as AssessmentError
from ..domain.assessment.overlay import Row as Row
from ..domain.assessment.overlay import Overlay as Overlay
from ..domain.assessment.overlay import parse as parse


def read(path):
    """Read the gaps.txt at `path` and parse it.

    Args:
        path: the gaps file.

    Returns:
        Overlay: the analyst's overlay the file holds.

    Raises:
        Missing: when there is no file at `path`.
        Unreadable: when it is not UTF-8.
        AssessmentError: on the first bad line.
    """
    from ..infra.files import read_text

    return parse(read_text(path, "gaps.txt"))
