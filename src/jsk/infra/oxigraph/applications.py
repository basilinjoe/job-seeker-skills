"""An application's folder on disk and its graphs in career/store/: ports.applications'
ApplicationRecords, which application/timeline/records.py reads and writes through."""


class StoredApplications:
    """ApplicationRecords over the store on disk (db, the write gate) and infra.files."""

    def workspace_of_app(self, app_dir):
        """(workspace root, `applications/<dir>`), or (None, None) (infra.files.workspace_of_app)."""
        from ..files import workspace_of_app

        return workspace_of_app(app_dir)

    def has_store(self, root):
        """Whether the workspace at `root` has a store (db.exists)."""
        from . import db

        return db.exists(root)

    def read_store(self, root):
        """{graph name: triples} the store holds (db.read).

        Raises:
            StoreError: the store will not open.
        """
        from . import db

        return db.read(root)

    def write_graphs(self, root, graphs):
        """Replace `graphs` in one update, then the backup (record.write_graphs).

        Raises:
            RecordError: nothing was changed. Written: the update landed and what followed
                failed.
        """
        from . import record as R

        R.write_graphs(root, graphs)

    def file_name(self, path, root):
        """`path` as findings name it (infra.files.file_name)."""
        from ..files import file_name

        return file_name(path, root)

    def is_file(self, path):
        """Whether `path` is a file there is."""
        import os

        return os.path.isfile(path)

    def read_text(self, path, what):
        """An authored file's text (infra.files.read_text).

        Raises:
            Missing, Unreadable: with the fix.
        """
        from ..files import read_text

        return read_text(path, what)

    def write_document(self, path, text):
        """Write the document at `path` whole, or not at all (infra.files.write_document).

        Returns:
            `path`.

        Raises:
            Unwritable: the file is locked, or the disk refused.
        """
        from ..files import write_document

        return write_document(path, text)

    def remove_document(self, path):
        """Remove `path` if it is there (infra.files.remove_document).

        Returns:
            True when a file was removed.

        Raises:
            Unwritable: it is there and could not be removed.
        """
        from ..files import remove_document

        return remove_document(path)
