"""A graph-native application's use cases, bound: capture, decide, complete, derive, review,
show and list over career/store/ and the engine (docs/superpowers/plans/
2026-10-01-graph-native-applications-mcp.md, P3).

Each writing function takes the workspace's turn before it reads (Ruling 14): what it
validates is what it writes over, and nothing is held between calls. The reads take none.
The clock is not read here: every function takes `today`, which the caller read once at
the edge (Ruling 17). `fetch_json` is looked up in compose.posting at each capture, because
a test patches it there.
"""
from ....infra.oxigraph import record as R


class Ports:
    """What the graph-native use cases ask of the world (application/posting/native.py)."""

    def has_store(self, root):
        """Whether the workspace at `root` has a store (db.exists)."""
        from ....infra.oxigraph import db

        return db.exists(root)

    def load(self, root, graphs=None):
        """The workspace, loaded; `graphs` stand in for the store's (compose.record.load)."""
        from .record import load

        return load(root, graphs=graphs)

    def write(self, app_dir, graphs, store):
        """Replace the application's graphs in one update (compose.timeline.write_app_graphs).

        Raises:
            Unwritable: nothing was written; Frozen when the application is sent.
        """
        from .timeline import write_app_graphs

        return write_app_graphs(app_dir, graphs, store)

    def sent_day(self, app_dir, store):
        """The day the application was sent, or None (compose.timeline.sent_day).

        Raises:
            GraphError: whether it was sent cannot be read.
        """
        from .timeline import sent_day

        return sent_day(app_dir, store)

    def is_file(self, path):
        """Whether `path` is a file there is."""
        import os

        return os.path.isfile(path)

    def queries(self, store):
        """The feature reads over `store` (infra.oxigraph.queries.OxigraphQueries)."""
        from ....infra.oxigraph.queries import OxigraphQueries

        return OxigraphQueries(store)

    def labels_in(self, store):
        """named(line) -> the concepts whose whole label it holds (compose.match.labels_in)."""
        from .match import labels_in

        return labels_in(store)

    def match(self, store, post, today, budget, elsewhere):
        """match_posting.result's plain data for `post` (compose.match.result)."""
        from .match import result

        return result(store, post, today, budget, elsewhere)

    def derive(self, r, store, today):
        """The Derived assessment, with the absences standing on `today` (compose.tailor.derive)."""
        from .tailor import derive

        return derive(r, store, today)

    def folder(self):
        """The application's folder and record as check_gaps.build writes them (compose.tailor.Folder)."""
        from .tailor import Folder

        return Folder()


def capture(root, stem, *, url=None, text=None, company=None, title=None, captured=None,
            replace=False, today, get=None):
    """The advert stored as a draft posting (application.posting.capture.capture), in the turn.

    Args:
        root: the workspace root.
        stem: the application's name, `applications/<stem>`.
        url, text: the advert's URL or file, or its pasted text - one of them.
        company, title: the header, when the advert does not give it.
        captured: the day it was saved, ISO; `today` when None.
        replace: capture it again, dropping its requirements, review and assessment.
        today: the day the caller read from the clock.
        get: api url -> the board's JSON answer; compose.posting.fetch_json by default.

    Returns:
        The Captured.

    Raises:
        Refused: with every reason; nothing written.
    """
    from ....application.posting.capture import capture as captured_
    from ....infra.posting_sources import read_file
    from . import posting

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return captured_(root, stem, url=url, text=text, company=company, title=title,
                         captured=captured, replace=replace, today=today,
                         get=get or posting.fetch_json, read_file=read_file, ports=Ports())


def decide(root, stem, header=None, rows=(), drops=(), remove=(), *, today):
    """A batch of decisions merged into the posting (application.posting.decide.decide).

    Returns:
        The Decided.

    Raises:
        Refused: a legacy application, no posting, or a sent one.
    """
    from ....application.posting.decide import decide as decided

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return decided(root, stem, header, rows, drops, remove, today=today, ports=Ports())


def complete_posting(root, stem, *, today):
    """The posting settled (application.posting.decide.complete).

    Returns:
        The Decided.

    Raises:
        Refused: a legacy application, no posting, or a sent one.
    """
    from ....application.posting.decide import complete

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return complete(root, stem, today=today, ports=Ports())


def derive_assessment(root, stem, *, today):
    """The assessment derived and written (application.tailor.assessment.derive_assessment).

    Returns:
        The Assessed.

    Raises:
        Refused: as derive_assessment does.
    """
    from ....application.tailor.assessment import derive_assessment as derived

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return derived(root, stem, today=today, ports=Ports())


def review(root, stem, *, fit=None, eligibility=None, verdicts=(), short=None, surplus=None,
           asks=None, today):
    """A batch upserted into the review (application.tailor.review.review).

    Returns:
        The Reviewed.

    Raises:
        Refused: as review does.
    """
    from ....application.tailor.review import review as reviewed

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return reviewed(root, stem, fit=fit, eligibility=eligibility, verdicts=verdicts,
                        short=short, surplus=surplus, asks=asks, today=today, ports=Ports())


def complete_review(root, stem, *, today):
    """The review settled (application.tailor.review.complete).

    Returns:
        The Reviewed.

    Raises:
        Refused: as complete does.
    """
    from ....application.tailor.review import complete

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return complete(root, stem, today=today, ports=Ports())


def show(root, stem, part, *, today, ports=None):
    """One part of an application as plain data (application.tailor.show.show); no turn.

    `ports` stands in for Ports(): the MCP server passes one whose load is its cached read
    (adapters/mcp/session.py), since a read takes no turn and nothing here writes.

    Raises:
        Refused: as show does.
    """
    from ....application.tailor.show import show as shown

    return shown(root, stem, part, today=today, ports=ports or Ports())


def list_apps(root, *, today, ports=None):
    """Every application and resume (application.tailor.show.list_apps); no turn. `ports`
    as show takes it.

    Raises:
        Refused: there is no store.
    """
    from ....application.tailor.show import list_apps as listed

    return listed(root, today=today, ports=ports or Ports())
