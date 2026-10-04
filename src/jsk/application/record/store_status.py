"""Where a workspace's record is, and why it is not there when it is not: `jsk doctor`.

It needs nothing but the folders - no store is opened, and pyoxigraph is not imported.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Where:
    """The workspace's record, as absolute paths, and what is there instead of a store.

    `instead` is None when career/store/ is there; else "files" (a workspace still laid
    out as .ttl files), "career" (the folder given is career/ itself) or "nothing".
    """

    workspace: str
    store: str
    applications: str
    instead: str | None


def where(root, *, db, legacy):
    """Where the record of the workspace at `root` is.

    Args:
        root: the workspace, absolute.
        db: the store on disk (infra.oxigraph.db): its path and whether it exists.
        legacy: the workspace laid out as files (infra.legacy_import): whether it is one.

    Returns:
        Where. Looks at the folders only.
    """
    instead = None
    if not db.exists(root):
        if legacy.has_files(root):
            instead = "files"
        elif os.path.isdir(os.path.join(root, "store")) or \
                os.path.isfile(os.path.join(root, "kb.ttl")):
            instead = "career"
        else:
            instead = "nothing"
    return Where(root, db.path(root), os.path.join(root, "applications"), instead)
