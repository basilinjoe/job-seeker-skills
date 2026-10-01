"""`jsk posting extract` and `jsk posting build`'s old path, and their binding: code extracts
the advert's lines, the model decides in decisions.txt, code writes the posting - the
application's posting graph in career/store/.

The decisions as data are domain/posting/decide.py's and the two use cases
application/posting/extract.py's and build.py's. This module keeps every name its callers
and tests use, `extract` and `build` with today's signatures - each defaulting the day to
today for a caller that has not read the clock - and the application's folder on disk
(PostingFolder). `triples` is looked up here at each build, because a test patches it.
"""
import datetime

from ..application.posting.extract import dir_stem as dir_stem
from ..domain.posting.decide import DATED as DATED
from ..domain.posting.decide import DECISIONS as DECISIONS
from ..domain.posting.decide import SENIORITY_HINTS as SENIORITY_HINTS
from ..domain.posting.decide import SHORT as SHORT
from ..domain.posting.decide import SOFT_CAP as SOFT_CAP
from ..domain.posting.decide import advert_header as advert_header
from ..domain.posting.decide import default_need as default_need
from ..domain.posting.decide import seniority_hint as seniority_hint
from ..domain.posting.decide import triples as triples
from ..domain.posting.errors import POSTING as POSTING
from ..domain.posting.errors import Refused as Refused


class PostingFolder:
    """An application's folder and its workspace, as extract and build read and write them:
    the files on disk, the store loaded and written through application/timeline/records.py."""

    def read_text(self, path, what=None):
        """An authored file's text (infra.files.read_text).

        Raises:
            Missing, Unreadable: with the fix.
        """
        from ..infra.files import read_text

        return read_text(path, what)

    def read_decisions(self, path):
        """decisions.txt at `path`, parsed (graph.decisions.read).

        Raises:
            Missing, Unreadable, DecisionsError.
        """
        from . import decisions as D

        return D.read(path)

    def is_file(self, path):
        """Whether `path` is a file there is."""
        import os

        return os.path.isfile(path)

    def find_root(self, start):
        """The workspace at or above `start`, or None (infra.files.find_root)."""
        from ..infra.files import find_root

        return find_root(start)

    def load(self, root, vocabulary):
        """The workspace at `root`, loaded with `vocabulary`, or the shipped one when None."""
        from . import store as S

        return S.load(root) if vocabulary is None else S.load(root, vocabulary=vocabulary)

    def file_name(self, path, root):
        """`path` as findings name it (infra.files.file_name)."""
        from ..infra.files import file_name

        return file_name(path, root)

    def labels_in(self, store):
        """named(line) -> the concepts whose whole label it holds (graph.queries.labels_in)."""
        from .queries import labels_in

        return labels_in(store)

    def queries(self, store):
        """The feature reads over `store` (infra.oxigraph.queries.OxigraphQueries)."""
        from ..infra.oxigraph.queries import OxigraphQueries

        return OxigraphQueries(store)

    def numbers_as_kept(self, quads, refuse):
        """Refuse each number the store would rewrite (graph.changeset.numbers_as_kept)."""
        from .changeset import numbers_as_kept

        numbers_as_kept(quads, refuse)

    def posting_of(self, store, rel):
        """(posting iri, stem) in the application `rel`, or (None, None)."""
        from ..application.timeline.records import posting_of

        return posting_of(store, rel)

    def workspace_of_app(self, app_dir):
        """(workspace root, `applications/<dir>`), or (None, None)."""
        from ..infra.files import workspace_of_app

        return workspace_of_app(app_dir)

    def refuse_if_sent(self, app_dir, name):
        """Raise Frozen when the graph `name` must not change: the application was sent."""
        from ..application.timeline.records import refuse_if_sent
        from ..infra.oxigraph.applications import StoredApplications

        refuse_if_sent(app_dir, name, graph=True, records=StoredApplications())

    def has_record(self, app_dir, kind):
        """Whether the application holds its `kind` graph."""
        from ..application.timeline.records import has_record
        from ..infra.oxigraph.applications import StoredApplications

        return has_record(app_dir, kind, records=StoredApplications())

    def app_graphs(self, app_dir, store):
        """{kind: triples} of the graphs the application holds."""
        from ..application.timeline.records import app_graphs
        from ..infra.oxigraph.applications import StoredApplications

        return app_graphs(app_dir, store, records=StoredApplications())

    def write_graphs(self, app_dir, graphs, store):
        """Replace the application's graphs in one update (records.write_app_graphs).

        Raises:
            Unwritable: nothing was written.
        """
        from ..application.timeline.records import write_app_graphs
        from ..infra.oxigraph.applications import StoredApplications

        return write_app_graphs(app_dir, graphs, store, records=StoredApplications())

    def remove_file(self, app_dir, name, store):
        """Remove `name` from the folder if it is there; True when one was removed.

        Raises:
            Unwritable: it is there and could not be removed.
        """
        from ..application.timeline.records import remove_app_file
        from ..infra.oxigraph.applications import StoredApplications

        return remove_app_file(app_dir, name, store, records=StoredApplications())


def read_advert(app_dir):
    """posting.md's text. Raises Refused when there is none, or it is not UTF-8."""
    from ..application.posting.extract import read_advert as read

    return read(app_dir, folder=PostingFolder())


def workspace(app_dir, vocabulary):
    """(root, store) for the workspace above the application, or (None, None)."""
    from ..application.posting.extract import workspace as found

    return found(app_dir, vocabulary, folder=PostingFolder())


def posting_stem(app_dir, root, store):
    """The stem of the Posting already in the posting graph, else the directory's."""
    from ..application.posting.extract import posting_stem as stem

    return stem(app_dir, root, store, folder=PostingFolder())


def extract(app_dir, vocabulary=None, today=None):
    """The decisions.txt header, ready to copy, then every advert line numbered with its
    section, its flag and the concepts its labels name (application.posting.extract).
    Raises Refused."""
    from ..application.posting.extract import extract as extracted

    return extracted(app_dir, vocabulary, today or datetime.date.today(),
                     folder=PostingFolder())


def build(app_dir, decisions_path=None, replace=False, vocabulary=None, today=None):
    """(what was written, requirements, warnings): the posting graph's name. Raises
    Refused, and then writes nothing. Runs inside the workspace's turn, taken before
    anything is read (application.posting.build, with this module's triples)."""
    from ..application.posting.build import build as built
    from ..infra.files import find_root
    from ..infra.oxigraph import record as R

    root = find_root(app_dir)
    with R.turn(root, dry_run=root is None):
        done = built(app_dir, decisions_path, replace, vocabulary,
                     today or datetime.date.today(), folder=PostingFolder(), triples=triples)
    return done.target, done.count, done.warnings


def existing_captured(store, post):
    """The day the posting already says it was saved: a rebuild is not a new capture."""
    from ..infra.oxigraph.queries import OxigraphQueries

    return OxigraphQueries(store).posting_captured(post)
