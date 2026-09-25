"""The named queries `jsk kb query` runs: questions an agent asks the record by name.

Each returns (columns, rows), rows as dicts, so the same answer prints as a table or as
JSON. A query is here because an agent would otherwise work it out by reading the whole
file - which is the reading the graph exists to save. `experience` and `pipeline` came
with the claims gate and `jsk event` (P5); the roadmap's `inconsistent` and `demand` are
not here yet.
"""
import datetime

from . import ontology as O
from .queries import PRE, evidence, paths_to
from .writer import curie

QUERIES = {}


def query(name, args="", doc=""):
    def register(fn):
        QUERIES[name] = (args, doc, fn)
        return fn
    return register


def local(iri):
    return iri[len(O.J):] if iri.startswith(O.J) else iri


@query("open", doc="open questions, oldest first")
def open_questions(store):
    rows = store.select(PRE + """SELECT ?q ?about ?text ?asked WHERE {
        ?q j:about ?about ; j:question ?text ; j:asked ?asked
        FILTER NOT EXISTS { ?q j:answered ?d } } ORDER BY ?asked ?q""")
    return (("question", "about", "asked", "ask"),
            [{"question": curie(r["q"].value), "about": curie(r["about"].value),
              "asked": r["asked"].value, "ask": r["text"].value} for r in rows])


@query("unconfirmed", doc="live entries not yet confirmed, with the question open about each")
def unconfirmed(store):
    rows = store.select(PRE + """SELECT ?s ?pv (SAMPLE(?q) AS ?open) WHERE {
        ?s j:provenance ?pv FILTER(?pv != j:confirmed) FILTER NOT EXISTS { ?s j:retired ?r }
        OPTIONAL { ?q j:about ?s FILTER NOT EXISTS { ?q j:answered ?d } } }
        GROUP BY ?s ?pv ORDER BY ?s""")
    return (("entry", "provenance", "open question"),
            [{"entry": curie(r["s"].value), "provenance": local(r["pv"].value),
              "open question": curie(r["open"].value) if "open" in r else ""} for r in rows])


@query("holds", "<concept>", "live projects holding a concept, or one that counts as it")
def holds(store, concept):
    iri = O.C + concept[2:] if concept.startswith("c:") else O.C + concept
    rows = sorted(paths_to(store, iri), key=lambda r: (r[2], r[0], r[1]))
    seen, out = set(), []
    for proj, held, hops, implied in rows:
        if proj in seen:
            continue
        seen.add(proj)
        out.append({"project": curie(proj), "holds": curie(held), "hops": hops,
                    "implied": implied, "evidence": evidence(store, proj, iri)})
    return (("project", "holds", "hops", "implied", "evidence"), out)


@query("stale", doc="applications that sent a metric version since replaced")
def stale(store):
    rows = store.select(PRE + """SELECT ?app ?v ?until ?now WHERE {
        ?app j:carriedVersion ?v . ?v j:validUntil ?until ; j:of ?m .
        OPTIONAL { ?now j:of ?m FILTER NOT EXISTS { ?now j:validUntil ?u } } }
        ORDER BY ?app ?v""")
    return (("application", "sent", "replaced", "current"),
            [{"application": curie(r["app"].value), "sent": curie(r["v"].value),
              "replaced": r["until"].value,
              "current": curie(r["now"].value) if "now" in r else ""} for r in rows])


def holdings(store):
    """{project iri: {concept iris it holds}} for every live project - what it is tagged
    with, its domains, and what its live bullets show (a disputed one shows nothing), each
    closed upward through the counts-as paths that carry a requirement: no implies edge.

    What the claims gate asks of a bullet's words: does its project hold what they name?
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
    """(months, [(project, position, start, end)], notes): the months the roles behind the
    projects holding `concept` cover, overlaps counted once - kbindex.experience over the
    graph. A project with no role has no dates, so it counts for nothing, and says so."""
    from ..kbindex import experience

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


@query("experience", "<concept>", "months the roles behind the projects holding a concept cover")
def experience_query(store, concept):
    iri = O.C + concept[2:] if concept.startswith("c:") else O.C + concept
    months, spans, _ = experience_of(store, iri)
    rows = [{"project": curie(p), "role": curie(pos), "from": start, "to": end or "ongoing",
             "months": ""} for p, pos, start, end in spans]
    rows.append({"project": "total, overlaps once", "role": "", "from": "", "to": "",
                 "months": months})
    return (("project", "role", "from", "to", "months"), rows)


@query("pipeline", doc="each application's stage: its latest event, and how long ago")
def pipeline(store, today=None):
    """The stage is a query, never a stored field: the latest dated event of each
    application. An event dated `unknown` is the stage only when nothing is dated."""
    today = today or datetime.date.today()
    apps = store.select(PRE + """SELECT ?app ?sub WHERE { ?app a j:Application ;
                                                                j:submitted ?sub }""")
    events = store.select(PRE + """SELECT ?app ?e ?date ?kind ?due WHERE {
        ?e j:application ?app ; j:date ?date ; j:kind ?kind OPTIONAL { ?e j:due ?due } }""")
    by = {}
    for r in events:
        by.setdefault(r["app"].value, []).append(r)
    out = []
    for a in sorted(apps, key=lambda r: r["app"].value):
        app = a["app"].value
        evs = sorted(by.get(app, []), key=lambda r: (r["date"].value != "unknown",
                                                     r["date"].value, r["e"].value))
        last = evs[-1] if evs else None
        date = last["date"].value if last else ""
        days = ""
        if date and date != "unknown":
            days = (today - datetime.date.fromisoformat(date)).days
        stage = local(last["kind"].value) if last else (
            "held back" if a["sub"].value == "false" else "")
        out.append({"application": curie(app), "submitted": a["sub"].value, "stage": stage,
                    "since": date, "days": days,
                    "due": last["due"].value if last and "due" in last else "",
                    "events": len(evs)})
    return (("application", "submitted", "stage", "since", "days", "due", "events"), out)


def table(columns, rows):
    """A Markdown table; `|` in a value is escaped so the row keeps its cells."""
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    out += ["| " + " | ".join(cell(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join(out)
