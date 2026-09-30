"""The selection's old path, and its binding: domain.selection.select over a loaded Store.

The rules are domain/selection/select.py's. The skills' order reads the career graph and
the projects' holdings (a named query), so it is gathered here and passed in.
"""
from ..domain.selection import select as _select
from ..domain.selection.select import KINDS as KINDS
from ..domain.selection.select import MOST as MOST
from ..domain.selection.select import NEEDS as NEEDS
from ..domain.selection.select import Gap as Gap
from ..domain.selection.select import Selection as Selection
from ..domain.selection.select import add as add
from ..domain.selection.select import band as band
from ..domain.selection.select import pick as pick
from ..infra.oxigraph.queries import OxigraphQueries


def bullets(store):
    """{bullet: (project, rank, provenance)} for every live bullet."""
    return OxigraphQueries(store).live_bullets()


def shows(store):
    """{bullet: the concepts it shows or counts as, without an implies edge}."""
    return OxigraphQueries(store).bullet_shows()


def cites_current(store):
    """Bullets citing a metric that has a current version - the ones export keeps a number
    for."""
    return OxigraphQueries(store).citing_current()


def evidenced(store, matches, held, shown):
    """(matches with carriers cut to confirmed evidence, the gaps the cut left)."""
    return _select.evidenced(OxigraphQueries(store), matches, held, shown)


def skill_order(store, matches):
    """Every live skill in the posting's order (domain.selection.select.skill_order).

    Args:
        store: a loaded workspace.
        matches: {requirement iri: Match}.

    Returns:
        The skill iris, those matching a required requirement first.
    """
    from ..domain.matching.resolve import labels
    from ..domain.record.career import Career
    from ..infra.oxigraph import record as R
    from .named import holdings

    by_label = labels(OxigraphQueries(store))
    held = set().union(*holdings(store).values())
    return _select.skill_order(Career(store.graph(R.KB)), by_label, held, matches)


def ranked(store, today, extra=()):
    """The Selection with no posting (`--ranked`), over a loaded workspace.

    Args:
        store: a loaded workspace.
        today: the date recency is counted from.
        extra: iris to add, in order (`--select`).

    Returns:
        domain.selection.select.ranked's Selection.
    """
    return _select.ranked(OxigraphQueries(store), today, extra)


def select(store, post, today, budget, extra=()):
    """The Selection for one posting; `extra` is iris to add, in order (`--select`).

    Args:
        store: a loaded workspace.
        post: the posting's iri.
        today: the date recency is counted from.
        budget: the most projects the cover may use.
        extra: iris to add, in order.

    Returns:
        domain.selection.select.select's Selection, its skills in skill_order.
    """
    return _select.select(OxigraphQueries(store), post, today, budget, extra,
                          lambda kept: skill_order(store, kept))
