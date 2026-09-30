"""`jsk kb pack`'s starter packs on disk: where each file is and reading it, bound into the
pack's logic in domain/record/pack.py."""
import os

from ..domain.record.pack import COUNTS_AS as COUNTS_AS
from ..domain.record.pack import EDGES as EDGES
from ..domain.record.pack import NAMES as NAMES
from ..domain.record.pack import Draft as Draft
from ..domain.record.pack import Walls as Walls
from ..domain.record.pack import classes as classes
from ..domain.record.pack import cur as cur
from ..domain.record.pack import draft as draft
from ..domain.record.pack import edges as edges
from ..domain.record.pack import names as names
from ..domain.record.pack import node as node
from ..domain.record.pack import pack_of as pack_of
from ..domain.record.pack import slug as slug
from ..domain.record.pack import trig as trig

PACKS = {"capabilities": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "data", "capabilities.ttl")}


def read_pack(path):
    """The starter pack in the file at `path`.

    Args:
        path: the pack's Turtle file, e.g. PACKS["capabilities"].

    Returns:
        {concept iri: {"class": name, "label": [(pred, text)], "edges": [(name, iri)]}}.

    Raises:
        GraphError: on a syntax error; the file read's own errors (Missing, NotUtf8,
            Unreadable) when it cannot be read. Reads the file.
    """
    from ..infra.files import read_text
    from ..infra.oxigraph.codec import parse_text

    name = os.path.basename(path)
    return pack_of(parse_text(read_text(path, name), name, kind="vocabulary").quads)
