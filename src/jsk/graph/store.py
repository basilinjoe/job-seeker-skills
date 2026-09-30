"""Loading a workspace, bound to the store on disk and the in-memory engine.

The record comes out of career/store/ (infra/oxigraph/db.py) into an engine, graph by
graph; the shipped vocabulary is read from its file each time. What a load does is
application/record/load.py's, and the Store it returns is domain/record/store.py's; this
module supplies the real workspace and engine, and keeps every name its callers use.

A workspace still laid out as files (career/kb.ttl, applications/*/*.ttl) is read only
by the one-time import (legacy.py, `jsk kb load`), which names its files; loaded any other
way it is refused, with that import as the fix.
"""
import glob
import os

from ..domain.naming import app_graph as app_graph
from ..domain.naming import graph_iri as graph_iri
from ..domain.naming import short_name as short_name
from ..domain.record.parsed import GraphError
from ..domain.record.store import NARROWS as NARROWS
from ..domain.record.store import ORDER as ORDER
from ..domain.record.store import Store as Store
from ..domain.record.store import derive_types as derive_types
from ..domain.record.store import load_order as load_order
from ..domain.record.store import materialise_paths as materialise_paths
from ..domain.record.store import narrow as narrow
from ..domain.record.store import parsed_graph as parsed_graph
from ..infra.files import file_name, graph_name, parse
from ..infra.files import inside as inside
from ..infra.files import rel as rel
from ..infra.files import spelled as spelled

SHIPPED_VOCABULARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "vocabulary.ttl")


def workspace_files(root, vocabulary=SHIPPED_VOCABULARY):
    """The record files under a workspace root still laid out as files, in a fixed order -
    what the import reads. Missing ones are absent."""
    found = [os.path.join(root, "career", "kb.ttl"), os.path.join(root, "career", "log.ttl")]
    for pattern in ("posting.ttl", "application.ttl", "gaps.ttl"):
        # Escaped: a root named "jobs [2026]" is a glob character class, and would
        # silently match no application at all.
        found += sorted(glob.glob(os.path.join(glob.escape(str(root)), "applications", "*",
                                               pattern)))
    found = [f for f in found if os.path.isfile(f)]
    if vocabulary and os.path.isfile(vocabulary):
        found.append(vocabulary)
    return found


def record_graphs(root):
    """{name: [Triple]} of the workspace's record, from career/store/ - {} in a folder with
    no record yet (before `jsk new`, or a --root that is not one). A career still laid out
    as files is a GraphError: jsk no longer reads or writes those files, and answering from
    them would answer from a record nothing keeps up to date. So is a store that will not
    open - never a traceback."""
    from ..infra.oxigraph import db
    from . import legacy

    if not db.exists(root):
        if legacy.has_files(root):
            raise GraphError("the career is still career/kb.ttl, and jsk reads it from "
                             "career/store/ now", "`jsk kb load .` imports the files, once",
                             "career/kb.ttl")
        return {}
    try:
        return db.read(root)
    except db.StoreError as e:
        raise GraphError(str(e), e.fix, "career/store/") from None


class Workspace:
    """The workspace a load reads: career/store/ for the record, the disk for the rest.

    It implements ports.workspace.WorkspaceSource.
    """

    def absolute(self, root):
        """`root` as an absolute path."""
        return os.path.abspath(root)

    def record_graphs(self, root):
        """{graph name: triples} out of career/store/, as record_graphs reads them."""
        return record_graphs(root)

    def is_file(self, path):
        """Whether `path` is a file there is."""
        return os.path.isfile(path)

    def graph_name(self, path, root):
        """The record graph a file holds, as infra.files.graph_name names it."""
        return graph_name(path, root)

    def file_name(self, path, root):
        """How a finding names a file, as infra.files.file_name spells it."""
        return file_name(path, root)

    def parse(self, path):
        """A file on disk, parsed through the engine's codec."""
        return parse(path)


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
    from ..infra.oxigraph.engine import OxigraphEngine

    return load_workspace(root, vocabulary, files, graphs, source=Workspace(),
                          new_engine=OxigraphEngine)
