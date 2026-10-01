"""What each live project holds, and the months of experience behind a concept.

Two reads of the record the named queries, the selection and the claims gates share: a
bullet's words are checked against what its project holds, and "N years of X" against the
roles behind the projects holding X. The SPARQL is over Store.select, as the named queries'
is (application/record/queries.py).
"""
import datetime

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


def experience_of(store, concept, today=None, held=None):
    """The months the roles behind the projects holding `concept` cover, overlaps counted
    once - scoring.experience over the graph. A project with no role has no dates, so it
    counts for nothing, and says so.

    Args:
        store: a loaded workspace.
        concept: the concept's iri.
        today: the day an ongoing role runs to; today when None.
        held: holdings(store), when the caller has it already.

    Returns:
        (months, [(project, position, start, end)], notes).
    """
    from ...domain.matching.scoring import experience

    today = today or datetime.date.today()
    held = holdings(store) if held is None else held
    projects = sorted(p for p, cs in held.items() if concept in cs)
    rows = store.select(PRE + """SELECT ?proj ?pos ?start ?end ?state WHERE {
        ?proj j:position ?pos . ?pos j:start ?start ; j:state ?state
        OPTIONAL { ?pos j:end ?end } }""")
    at = {r["proj"].value: r for r in rows}
    roles, spans, notes = {}, [], []
    for p in projects:
        r = at.get(p)
        if r is None:
            notes.append(f"{curie(p)} has no role, so no dates, and is not counted")
            continue
        pos = r["pos"].value
        roles[pos] = {"block": {"id": curie(pos), "start": r["start"].value,
                                "end": r["end"].value if "end" in r else None,
                                "state": local(r["state"].value)}, "start": 0}
        spans.append((p, pos, r["start"].value, r["end"].value if "end" in r else ""))
    months, more = experience(list(roles.values()), today)
    return months, spans, notes + more
