"""The named queries `jsk kb query` runs: questions an agent asks the record by name.

Each returns (columns, rows), rows as dicts, so the same answer prints as a table or as
JSON. A query is here because an agent would otherwise work it out by reading the whole
file - which is the reading the graph exists to save. The roadmap's `experience`,
`inconsistent`, `demand` and `pipeline` arrive with the phases that need them (P5).
"""
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


def table(columns, rows):
    """A Markdown table; `|` in a value is escaped so the row keeps its cells."""
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    out += ["| " + " | ".join(cell(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join(out)
