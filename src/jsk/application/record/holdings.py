"""What each live project holds, and the months of experience behind a concept.

Two reads of the record the named queries, the selection and the claims gates share: a
bullet's words are checked against what its project holds, and "N years of X" against the
roles behind the projects holding X. The SPARQL is over Store.select, as the named queries'
is (application/record/queries.py).
"""
from ...domain.matching.model import local
from ...domain.ontology import SPARQL_PREFIX as PRE
from ...domain.record.writer import curie


def holdings(store):
    """What each live project holds: what it is tagged with, its domains, and what its
    live bullets show (a disputed one shows nothing), each closed upward through the
    counts-as paths that carry a requirement: no implies edge.

    What the record gate asks of a bullet's words (it was the claims gate's question): does
    its project hold what they name?

    Args:
        store: a loaded workspace.

    Returns:
        {project iri: {concept iris it holds}} for every live project.
    """
    rows = store.select(PRE + """SELECT DISTINCT ?proj ?to WHERE {
        ?proj a j:Project .
        { ?proj j:uses ?h } UNION { ?proj j:domain ?h }
        UNION { ?b j:project ?proj ; j:shows ?h
                FILTER NOT EXISTS { ?b j:retired ?r }
                FILTER NOT EXISTS { ?b j:provenance j:disputed } }
        GRAPH j:derived { ?p j:from ?h ; j:to ?to ; j:implied false }
        FILTER NOT EXISTS { ?proj j:retired ?x } }""")
    out = {}
    for r in rows:
        out.setdefault(r["proj"].value, set()).add(r["to"].value)
    return out


def experience_of(store, concept, today, held=None):
    """The months the roles behind the projects holding `concept` cover, overlaps counted
    once - scoring.experience over the graph. A project with no role has no dates, so it
    counts for nothing, and says so.

    Args:
        store: a loaded workspace.
        concept: the concept's iri.
        today: the day an ongoing role runs to.
        held: holdings(store), when the caller has it already.

    Returns:
        (months, [(project, position, start, end)], notes).
    """
    held = holdings(store) if held is None else held
    months, spans, notes, _ = _experience_over(
        store, sorted(p for p, cs in held.items() if concept in cs), today)
    return months, spans, notes


def experience_span(store, concepts, today, held=None):
    """The months of experience a requirement's years are measured against, and the span
    they cover: `concepts` empty counts every position, otherwise the roles behind the
    projects holding any one of them. Overlaps are counted once, as experience_of counts them.

    It is what `assessment_derive` reads for a requirement that states a minimum in years
    (docs/ONTOLOGY.md, `j:years`), bound in adapters/compose/tailor.py so the domain's derive
    stays free of the store.

    Args:
        store: a loaded workspace.
        concepts: the requirement's concept iris, any one satisfying; empty for all roles.
        today: the day an ongoing role runs to.
        held: holdings(store), when the caller has it already.

    Returns:
        (months, first, last): `first` is the earliest start of a counted role as the record
        writes it, `last` the latest end or "now" while one is ongoing; both None when no
        role counts.
    """
    projects = None
    if concepts:
        held = holdings(store) if held is None else held
        projects = sorted(p for p, cs in held.items() if cs & set(concepts))
    months, _, _, counted = _experience_over(store, projects, today)
    if not counted:
        return months, None, None
    ends = [b["end"] for b in counted]
    return months, min(b["start"] for b in counted), "now" if None in ends else max(ends)


def _experience_over(store, projects, today):
    """(months, [(project, position, start, end)], notes, counted) over `projects`' roles,
    or over every position when `projects` is None (a span's project is then None).

    `counted` holds the role blocks scoring.experience can count: a start, and an end or
    the state `ongoing`. The spans hold every role found, counted or not, as the
    `experience` query prints them with its notes.
    """
    from ...domain.matching.scoring import experience

    if projects is None:
        rows = store.select(PRE + """SELECT ?pos ?start ?end ?state WHERE {
            ?pos a j:Position ; j:start ?start ; j:state ?state
            FILTER NOT EXISTS { ?pos j:retired ?x }
            OPTIONAL { ?pos j:end ?end } }""")
        found = [(None, r) for r in rows]
    else:
        rows = store.select(PRE + """SELECT ?proj ?pos ?start ?end ?state WHERE {
            ?proj j:position ?pos . ?pos j:start ?start ; j:state ?state
            OPTIONAL { ?pos j:end ?end } }""")
        at = {r["proj"].value: r for r in rows}
        found = [(p, at.get(p)) for p in projects]
    roles, spans, notes = {}, [], []
    for p, r in found:
        if r is None:
            notes.append(f"{curie(p)} has no role, so no dates, and is not counted")
            continue
        pos = r["pos"].value
        end = r["end"].value if "end" in r else None
        roles[pos] = {"block": {"id": curie(pos), "start": r["start"].value, "end": end,
                                "state": local(r["state"].value)}, "start": 0}
        spans.append((p, pos, r["start"].value, end or ""))
    months, more = experience(list(roles.values()), today)
    counted = [x["block"] for x in roles.values()
               if x["block"]["end"] or x["block"]["state"] == "ongoing"]
    return months, spans, notes + more, counted
