"""The match and the selection, bound to a loaded Store: each question asked of the engine's
feature reads (infra.oxigraph.queries.OxigraphQueries).

The rules are domain/matching's and domain/selection's, the match application/tailor/
match_posting.py's. Each function keeps the signature its callers use - a Store first - and
asks the engine's queries over it. `select` is looked up here at each call to `result` and
`record_faults`, because a test patches it here.
"""


def labels(store):
    """{normalised label: {concept iris}} (domain.matching.resolve.labels).

    Args:
        store: a loaded workspace.
    """
    from ...domain.matching.resolve import labels as of
    from ...infra.oxigraph.queries import OxigraphQueries

    return of(OxigraphQueries(store))


def concepts(store):
    """Every concept iri the workspace states something about.

    Args:
        store: a loaded workspace.
    """
    from ...infra.oxigraph.queries import OxigraphQueries

    return OxigraphQueries(store).concepts()


def match(store, post):
    """{requirement iri: Match} for one posting (domain.matching.resolve.match).

    Args:
        store: a loaded workspace.
        post: the posting's iri.
    """
    from ...domain.matching.resolve import match as matched
    from ...infra.oxigraph.queries import OxigraphQueries

    return matched(OxigraphQueries(store), post)


def evidence(store, project, concepts):
    """confirmed, unconfirmed or tag for a project (domain.matching.resolve.evidence).

    Args:
        store: a loaded workspace.
        project: the project's iri.
        concepts: the concepts any one of which it must show.
    """
    from ...domain.matching.resolve import evidence as of
    from ...infra.oxigraph.queries import OxigraphQueries

    return of(OxigraphQueries(store), project, concepts)


def confirmed_texts(store, project, concepts):
    """The sorted words of the live, confirmed bullets showing one of the concepts.

    Args:
        store: a loaded workspace.
        project: the project's iri.
        concepts: the concepts.
    """
    from ...infra.oxigraph.queries import OxigraphQueries

    return OxigraphQueries(store).confirmed_texts(project, concepts)


def rank(store, post, matches, today):
    """[Row] for every live project, best first (domain.matching.rank.rank).

    Args:
        store: a loaded workspace.
        post: the posting's iri.
        matches: {requirement iri: Match}.
        today: the date recency is counted from.
    """
    from ...domain.matching.rank import rank as ranked
    from ...infra.oxigraph.queries import OxigraphQueries

    return ranked(OxigraphQueries(store), post, matches, today)


def nearest(store, limit=3, post=None):
    """near(label) -> the concepts closest to it (domain.matching.nearest.nearest).

    Args:
        store: a loaded workspace.
        limit: how many concepts near() returns.
        post: a posting whose own answers are left out, or None.
    """
    from ...domain.matching.nearest import nearest as near
    from ...infra.oxigraph.queries import OxigraphQueries

    return near(OxigraphQueries(store), limit, post)


def labels_in(store):
    """named(line) -> the concepts whose whole label it holds (domain.matching.nearest.labels_in).

    Args:
        store: a loaded workspace.
    """
    from ...domain.matching.nearest import labels_in as named
    from ...infra.oxigraph.queries import OxigraphQueries

    return named(OxigraphQueries(store))


def questions(store, matches):
    """[Question] a tailoring round should ask (domain.matching.questions.questions).

    Args:
        store: a loaded workspace.
        matches: {requirement iri: Match}.
    """
    from ...domain.matching.questions import questions as asked
    from ...infra.oxigraph.queries import OxigraphQueries

    return asked(OxigraphQueries(store), matches)


def skill_order(store, matches):
    """Every live skill in the posting's order (domain.selection.select.skill_order).

    The skills' order reads the career graph and the projects' holdings (a named query),
    so it is gathered here and passed in.

    Args:
        store: a loaded workspace.
        matches: {requirement iri: Match}.

    Returns:
        The skill iris, those matching a required requirement first.
    """
    from ...application.record.holdings import holdings
    from ...domain.matching.resolve import labels as by_labels
    from ...domain.record.career import Career
    from ...domain.record.state import KB
    from ...domain.selection.select import skill_order as ordered
    from ...infra.oxigraph.queries import OxigraphQueries

    by_label = by_labels(OxigraphQueries(store))
    held = set().union(*holdings(store).values())
    return ordered(Career(store.graph(KB)), by_label, held, matches)


def ranked(store, today, extra=()):
    """The Selection with no posting (`--ranked`), over a loaded workspace.

    Args:
        store: a loaded workspace.
        today: the date recency is counted from.
        extra: iris to add, in order (`--select`).

    Returns:
        domain.selection.select.ranked's Selection.
    """
    from ...domain.selection.select import ranked as by_rank
    from ...infra.oxigraph.queries import OxigraphQueries

    return by_rank(OxigraphQueries(store), today, extra)


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
    from ...domain.selection.select import select as selected
    from ...infra.oxigraph.queries import OxigraphQueries

    return selected(OxigraphQueries(store), post, today, budget, extra,
                    lambda kept: skill_order(store, kept))


def posting_in(store, app):
    """The one Posting the application `app` (its directory) holds, or None
    (application.tailor.match_posting.posting_in).

    Args:
        store: a loaded workspace.
        app: the application directory.
    """
    from ...application.tailor.match_posting import posting_in as posting_of
    from ...infra.files import file_name

    return posting_of(store, file_name(app, store.root))


def record_faults(store, post, today, budget, ranked=None):
    """The bullets this posting's draft would carry whose numbers the record cannot back,
    as questions for round 1 (application.tailor.match_posting.record_faults over the
    engine's queries and this module's select).

    Args:
        store: a loaded workspace.
        post: the posting's iri.
        today: the date the check runs on.
        budget: the most projects the cover may use.
        ranked: the ranked rows already made, or None.
    """
    from ...application.tailor.match_posting import record_faults as faults
    from ...infra.oxigraph.queries import OxigraphQueries

    return faults(store, OxigraphQueries(store), post, today, budget, ranked, select)


def result(store, post, today, budget, elsewhere=0):
    """Everything the match reports, as plain data
    (application.tailor.match_posting.result over the engine's queries and this module's
    select).

    Args:
        store: a loaded workspace.
        post: the posting's iri.
        today: the date recency is counted from.
        budget: the most projects the cover may use.
        elsewhere: the FAILs elsewhere in the workspace, which do not block this match.
    """
    from ...application.tailor.match_posting import result as matched
    from ...infra.oxigraph.queries import OxigraphQueries

    return matched(store, OxigraphQueries(store), post, today, budget, elsewhere, select)
