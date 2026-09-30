"""A changeset read from its text: the parse and the store's form of a number from the
engine's codec, bound into the reading and refusing in domain/record/changeset.py."""
from ..domain.record.changeset import GRAPHS as GRAPHS
from ..domain.record.changeset import OP as OP
from ..domain.record.changeset import WRITTEN_BY_JSK as WRITTEN_BY_JSK
from ..domain.record.changeset import Changeset as Changeset
from ..domain.record.changeset import Refusal as Refusal
from ..domain.record.changeset import Refused as Refused
from ..domain.record.changeset import article as article
from ..domain.record.changeset import bullets_named as bullets_named
from ..domain.record.changeset import check as check
from ..domain.record.changeset import curie as curie
from ..domain.record.changeset import header as header
from ..domain.record.changeset import name as name
from ..domain.record.changeset import predicate as predicate
from ..domain.record.changeset import read_parsed as read_parsed
from ..domain.record import changeset as _domain
from ..infra.oxigraph.codec import canonical_numbers, parse_text


def read(text, file="changeset.trig"):
    """The changeset in `text`.

    Args:
        text: the changeset's TriG text.
        file: the name its syntax errors are reported under.

    Returns:
        the Changeset.

    Raises:
        GraphError: on a syntax error.
        Refused: on anything else wrong with it, every refusal at once.
    """
    return read_parsed(parse_text(text, file, kind="changeset").quads, canonical_numbers)


def numbers_as_kept(quads, refuse):
    """Refuse each number in `quads` the store would rewrite (`8.40`, `007`).

    Args:
        quads: the quads to check.
        refuse: called as refuse(focus, detail, fix) once per number the store rewrites.

    Returns:
        None; its only effect is the calls to `refuse`.
    """
    _domain.numbers_as_kept(quads, refuse, canonical_numbers)
