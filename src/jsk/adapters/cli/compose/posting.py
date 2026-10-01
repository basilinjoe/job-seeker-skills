"""`jsk posting extract` and `jsk posting build`'s ports, bound: code extracts the advert's
lines, the model decides in decisions.txt, code writes the posting - the application's
posting graph in career/store/.

The decisions as data are domain/posting/decide.py's and the two use cases
application/posting/extract.py's and build.py's. This module holds the application's
folder on disk (PostingFolder), and `extract` and `build` with their callers' signatures,
each defaulting the day to today for a caller that has not read the clock. `triples` is
looked up here at each build, because a test patches it here.
"""
import datetime

from ....domain.posting.decide import triples


def read_decisions(path, what=None):
    """Read the decisions.txt at `path` and parse it (domain.record.decisions.parse).

    Args:
        path: the decisions file.
        what: the name a refusal gives the file, or None for its path.

    Returns:
        Decisions: the file's header, rows and drops.

    Raises:
        Missing: when there is no file at `path`.
        Unreadable: when it is not UTF-8.
        DecisionsError: on the first bad line.
    """
    from ....domain.record.decisions import parse
    from ....infra.files import read_text

    return parse(read_text(path, what))


class PostingFolder:
    """An application's folder and its workspace, as extract and build read and write them:
    the files on disk, the store loaded and written through compose.timeline."""

    def read_text(self, path, what=None):
        """An authored file's text (infra.files.read_text).

        Raises:
            Missing, Unreadable: with the fix.
        """
        from ....infra.files import read_text

        return read_text(path, what)

    def read_decisions(self, path):
        """decisions.txt at `path`, parsed (this module's read_decisions).

        Raises:
            Missing, Unreadable, DecisionsError.
        """
        return read_decisions(path)

    def is_file(self, path):
        """Whether `path` is a file there is."""
        import os

        return os.path.isfile(path)

    def find_root(self, start):
        """The workspace at or above `start`, or None (infra.files.find_root)."""
        from ....infra.files import find_root

        return find_root(start)

    def load(self, root, vocabulary):
        """The workspace at `root`, loaded with `vocabulary`, or the shipped one when None."""
        from .record import load

        return load(root) if vocabulary is None else load(root, vocabulary=vocabulary)

    def file_name(self, path, root):
        """`path` as findings name it (infra.files.file_name)."""
        from ....infra.files import file_name

        return file_name(path, root)

    def labels_in(self, store):
        """named(line) -> the concepts whose whole label it holds (compose.match.labels_in)."""
        from .match import labels_in

        return labels_in(store)

    def queries(self, store):
        """The feature reads over `store` (infra.oxigraph.queries.OxigraphQueries)."""
        from ....infra.oxigraph.queries import OxigraphQueries

        return OxigraphQueries(store)

    def numbers_as_kept(self, quads, refuse):
        """Refuse each number the store would rewrite (compose.record.numbers_as_kept)."""
        from .record import numbers_as_kept

        numbers_as_kept(quads, refuse)

    def posting_of(self, store, rel):
        """(posting iri, stem) in the application `rel`, or (None, None)."""
        from ....application.timeline.records import posting_of

        return posting_of(store, rel)

    def workspace_of_app(self, app_dir):
        """(workspace root, `applications/<dir>`), or (None, None)."""
        from ....infra.files import workspace_of_app

        return workspace_of_app(app_dir)

    def refuse_if_sent(self, app_dir, name):
        """Raise Frozen when the graph `name` must not change: the application was sent."""
        from .timeline import refuse_if_sent

        refuse_if_sent(app_dir, name, graph=True)

    def has_record(self, app_dir, kind):
        """Whether the application holds its `kind` graph."""
        from .timeline import has_record

        return has_record(app_dir, kind)

    def app_graphs(self, app_dir, store):
        """{kind: triples} of the graphs the application holds."""
        from .timeline import app_graphs

        return app_graphs(app_dir, store)

    def write_graphs(self, app_dir, graphs, store):
        """Replace the application's graphs in one update (compose.timeline.write_app_graphs).

        Raises:
            Unwritable: nothing was written.
        """
        from .timeline import write_app_graphs

        return write_app_graphs(app_dir, graphs, store)

    def remove_file(self, app_dir, name, store):
        """Remove `name` from the folder if it is there; True when one was removed.

        Raises:
            Unwritable: it is there and could not be removed.
        """
        from .timeline import remove_app_file

        return remove_app_file(app_dir, name, store)


def extract(app_dir, vocabulary=None, today=None):
    """The decisions.txt header, ready to copy, then every advert line numbered with its
    section, its flag and the concepts its labels name (application.posting.extract).

    Args:
        app_dir: the application directory.
        vocabulary: the vocabulary's file, or None for the shipped one.
        today: the day the header is dated; today when None.

    Returns:
        The text to print.

    Raises:
        Refused: there is no readable posting.md.
    """
    from ....application.posting.extract import extract as extracted

    return extracted(app_dir, vocabulary, today or datetime.date.today(),
                     folder=PostingFolder())


def build(app_dir, decisions_path=None, replace=False, vocabulary=None, today=None):
    """The posting graph written from decisions.txt, inside the workspace's turn, taken
    before anything is read (application.posting.build, with this module's triples).

    Args:
        app_dir: the application directory.
        decisions_path: the decisions file, or None for the one in `app_dir`.
        replace: write over a posting graph that is there.
        vocabulary: the vocabulary's file, or None for the shipped one.
        today: the day the posting is captured; today when None.

    Returns:
        (what was written, requirements, warnings): the posting graph's name.

    Raises:
        Refused: every problem, and nothing written.
    """
    from ....application.posting.build import build as built
    from ....infra.files import find_root
    from ....infra.oxigraph import record as R

    root = find_root(app_dir)
    with R.turn(root, dry_run=root is None):
        done = built(app_dir, decisions_path, replace, vocabulary,
                     today or datetime.date.today(), folder=PostingFolder(), triples=triples)
    return done.target, done.count, done.warnings
