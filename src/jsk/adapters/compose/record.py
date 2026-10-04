"""The career record's ports, bound: a workspace loaded over career/store/ and the in-memory
engine, and a changeset read through the engine's codec.

What a load does is application/record/load.py's, the Store it returns is
domain/record/store.py's, and the workspace it reads is infra/workspace.py's; this module
hands the use case the real workspace and engine. Nothing is imported until a call.
"""
from ...infra.workspace import SHIPPED_VOCABULARY


def load(root, vocabulary=SHIPPED_VOCABULARY, files=None, graphs=None):
    """Load, derive, validate and close over a workspace (application/record/load.py).

    Args:
        root: the workspace root.
        vocabulary: the shipped vocabulary's file; by default the one that ships.
        files: None to read career/store/; else the files to read instead.
        graphs: {name: triples, or None to drop} standing in for the store's graphs.

    Returns:
        The loaded Store. Reads career/store/ under shared access, or the files.
    """
    from ...application.record.load import load as load_workspace
    from ...infra.adverts import Adverts
    from ...infra.oxigraph.engine import OxigraphEngine
    from ...infra.workspace import Workspace

    return load_workspace(root, vocabulary, files, graphs, source=Workspace(),
                          new_engine=OxigraphEngine, adverts=Adverts())


def read_changeset(text, file="changeset.trig"):
    """The changeset in `text` (domain.record.changeset.read_parsed over the engine's parse).

    Args:
        text: the changeset's TriG text.
        file: the name its syntax errors are reported under.

    Returns:
        the Changeset.

    Raises:
        GraphError: on a syntax error.
        Refused: on anything else wrong with it, every refusal at once.
    """
    from ...domain.record.changeset import read_parsed
    from ...infra.oxigraph.codec import canonical_numbers, parse_text

    return read_parsed(parse_text(text, file, kind="changeset").quads, canonical_numbers)


def numbers_as_kept(quads, refuse):
    """Refuse each number in `quads` the store would rewrite (`8.40`, `007`).

    Args:
        quads: the quads to check.
        refuse: called as refuse(focus, detail, fix) once per number the store rewrites.

    Returns:
        None; its only effect is the calls to `refuse`.
    """
    from ...domain.record import changeset
    from ...infra.oxigraph.codec import canonical_numbers

    changeset.numbers_as_kept(quads, refuse, canonical_numbers)
