"""The gap assessment's old path, and its binding: domain.assessment.derive over a Store."""
from ..application.tailor.match_text import question_line
from ..domain.assessment import derive as _derive
from ..domain.assessment.derive import FLAG as FLAG
from ..domain.assessment.derive import IMPLICIT as IMPLICIT
from ..domain.assessment.derive import LIST_SPLIT as LIST_SPLIT
from ..domain.assessment.derive import ORDER as ORDER
from ..domain.assessment.derive import Derived as Derived
from ..domain.assessment.derive import Row as Row
from ..domain.assessment.derive import fit_default as fit_default
from ..domain.assessment.derive import listed_names as listed_names
from ..domain.assessment.derive import slug_of as slug_of
from ..infra.oxigraph.queries import OxigraphQueries


def derive(r, store):
    """Derived for the match result `r` (match.result) over `store`.

    Args:
        r: match.result's plain data for one posting.
        store: the loaded workspace the match ran on.

    Returns:
        domain.assessment.derive.derive's Derived. Reads the confirmed bullets' words.
    """
    return _derive.derive(r, OxigraphQueries(store), question_line)
