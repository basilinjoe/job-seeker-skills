"""The workspace a load reads: career/store/ for the record, the disk for everything else.

The record comes out of career/store/ (infra/oxigraph/db.py) graph by graph; the shipped
vocabulary is read from its file each time. A workspace still laid out as files
(career/kb.ttl, applications/*/*.ttl) is read only by the one-time import
(infra/legacy_import.py, `jsk kb load`), which names its files; loaded any other way it is
refused, with that import as the fix.
"""
import os

from ..domain.record.parsed import GraphError
from .files import file_name, graph_name, parse

SHIPPED_VOCABULARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "vocabulary.ttl")


def record_graphs(root):
    """The workspace's record, out of career/store/.

    jsk no longer reads or writes a career laid out as files, and answering from them
    would answer from a record nothing keeps up to date, so such a career is refused.

    Args:
        root: the workspace root.

    Returns:
        {name: [Triple]}; {} in a folder with no record yet (before `jsk kb new`, or a
        --root that is not one). Reads career/store/ under shared access.

    Raises:
        GraphError: the career is still career/kb.ttl, or the store will not open -
            never a traceback.
    """
    from . import legacy_import
    from .oxigraph import db

    if not db.exists(root):
        if legacy_import.has_files(root):
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

    def record_state(self, store):
        """Where the career and its log stand, as infra.oxigraph.record.state finds it."""
        from .oxigraph.record import state

        return state(store)
