"""An application's posting.md and decisions.txt, read from its folder on disk."""
import os

from .files import read_text


class Adverts:
    """The files beside an application's graphs, read through infra.files.read_text.

    It implements ports.advert.AdvertSource.
    """

    def advert(self, root, folder):
        """posting.md in `folder` under `root`.

        Args:
            root: the workspace root.
            folder: the application's folder, relative to `root`.

        Returns:
            The advert's text, normalised.

        Raises:
            Missing, NotUtf8, Unreadable: from read_text, naming the file by its path.
        """
        return read_text(os.path.join(root, folder, "posting.md"))

    def decisions(self, root, folder):
        """decisions.txt in `folder` under `root`, parsed.

        Args:
            root: the workspace root.
            folder: the application's folder, relative to `root`.

        Returns:
            A domain.record.decisions.Decisions.

        Raises:
            Unreadable: the file could not be read (Missing when there is none).
            DecisionsError: on its first bad line.
        """
        from ..domain.record.decisions import parse

        return parse(read_text(os.path.join(root, folder, "decisions.txt")))
