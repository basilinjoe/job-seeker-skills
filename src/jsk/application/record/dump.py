"""`jsk kb dump`: the whole record - the career, its log, every application's graphs - as
TriG, the text `jsk kb load` reads back."""


def dump(root, *, db):
    """The record of the workspace at `root` as TriG.

    Args:
        root: the workspace.
        db: the store on disk (infra.oxigraph.db): read, and dump_text.

    Returns:
        The TriG text. Reads career/store/ under shared access.

    Raises:
        StoreError: the store could not be read (db.StoreError, with its fix).
    """
    return db.dump_text(db.read(root))
