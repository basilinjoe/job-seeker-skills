"""Loading a workspace, bound to the store on disk and the in-memory engine.

What a load does is application/record/load.py's, the Store it returns is
domain/record/store.py's, and the workspace it reads is infra/workspace.py's; this module
supplies the real workspace and engine, and keeps every name its callers use.
"""
from ..domain.naming import app_graph as app_graph
from ..domain.naming import graph_iri as graph_iri
from ..domain.naming import short_name as short_name
from ..domain.record.store import NARROWS as NARROWS
from ..domain.record.store import ORDER as ORDER
from ..domain.record.store import Store as Store
from ..domain.record.store import derive_types as derive_types
from ..domain.record.store import load_order as load_order
from ..domain.record.store import materialise_paths as materialise_paths
from ..domain.record.store import narrow as narrow
from ..domain.record.store import parsed_graph as parsed_graph
from ..infra.files import file_name as file_name
from ..infra.files import graph_name as graph_name
from ..infra.files import inside as inside
from ..infra.files import rel as rel
from ..infra.files import spelled as spelled
from ..infra.workspace import SHIPPED_VOCABULARY


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
    from ..application.record.load import load as load_workspace
    from ..infra.adverts import Adverts
    from ..infra.oxigraph.engine import OxigraphEngine
    from ..infra.workspace import Workspace

    return load_workspace(root, vocabulary, files, graphs, source=Workspace(),
                          new_engine=OxigraphEngine, adverts=Adverts())
