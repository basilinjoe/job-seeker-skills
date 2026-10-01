"""`jsk kb pack`'s starter packs on disk: where each file is, and reading one. The pack's
logic is domain/record/pack.py's."""
import os

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
    from ..domain.record.pack import pack_of
    from .files import read_text
    from .oxigraph.codec import parse_text

    name = os.path.basename(path)
    return pack_of(parse_text(read_text(path, name), name, kind="vocabulary").quads)
