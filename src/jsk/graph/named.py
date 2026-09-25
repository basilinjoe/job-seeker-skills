"""The named queries `jsk kb query` runs: questions an agent asks the record by name.

Each returns (columns, rows), rows as dicts, so the same answer prints as a table or as
JSON. A query is here because an agent would otherwise work it out by reading the whole
file - which is the reading the graph exists to save. `experience` and `pipeline` came
with the claims gate and `jsk event` (P5); the roadmap's `inconsistent` and `demand` are
not here yet. `evidence` and `person` replaced the tailor analyst's grep of kb.ttl: on the
Taskrabbit run it spent five of its seven minutes on some forty greps and reads for terms
and a location that two queries answer in half a second.
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
    out = {}
    for r in rows:                     # one row per question, whatever it is about
        row = out.setdefault(r["q"].value, {"question": curie(r["q"].value), "about": [],
                                            "asked": r["asked"].value, "ask": r["text"].value})
        row["about"].append(curie(r["about"].value))
    for row in out.values():
        row["about"] = ", ".join(sorted(row["about"]))
    return (("question", "about", "asked", "ask"), list(out.values()))


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
    iri = concept if concept.startswith(O.C) else \
        O.C + concept[2:] if concept.startswith("c:") else O.C + concept
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
    projects holding `concept` cover, overlaps counted once - scoring.experience over the
    graph. A project with no role has no dates, so it counts for nothing, and says so."""
    from .scoring import experience

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


TEXT_HITS = 12                   # per term; past it, the term is too broad to read row by row


def snippet(text, at, end, width=60):
    """The match with `width` characters either side, whitespace collapsed."""
    lo, hi = max(0, at - width), min(len(text), end + width)
    body = " ".join(text[lo:hi].split())
    return ("…" if lo else "") + body + ("…" if hi < len(text) else "")


def text_pattern(term):
    """A whole-word match of `term`. An all-capitals term is an acronym and matches in
    capitals only - REST is not "the rest of", BFF is not "bff"."""
    import re
    words = r"\s+".join(re.escape(w) for w in term.split())
    return re.compile(rf"(?<!\w){words}(?!\w)", 0 if term.isupper() else re.IGNORECASE)


def kb_text(store):
    """(entry, predicate, text, provenance, project) for every string in career/kb.ttl
    on a live entry - what a grep of the file would find, without the retired, and
    without the vocabulary's labels, which the concept match has already answered."""
    from . import record as R
    from .store import graph_iri
    rows = store.select(PRE + f"""SELECT ?s ?p ?o ?pv ?proj WHERE {{
        GRAPH <{graph_iri(R.KB)}> {{ ?s ?p ?o
          FILTER(isIRI(?s) && !STRSTARTS(STR(?s), STR(c:)) && isLiteral(?o)
                 && DATATYPE(?o) = <http://www.w3.org/2001/XMLSchema#string>) }}
        OPTIONAL {{ ?s j:provenance ?pv }} OPTIONAL {{ ?s j:project ?proj }}
        FILTER NOT EXISTS {{ ?s j:retired ?r }} }} ORDER BY ?s ?p""")
    return [(r["s"].value, r["p"].value, r["o"].value,
             local(r["pv"].value) if "pv" in r else "",
             r["proj"].value if "proj" in r else None) for r in rows]


@query("evidence", "<term>...", "per term: projects holding its concept, then the record's text naming it")
def evidence_for(store, *terms):
    """What the record holds for each term, in one call: the concept the term names and
    the live projects holding it (as `holds` reports them), then every live entry whose
    text names it as a whole word - the grep an agent would otherwise run once per term,
    over a file it would have to find first. A term the record says nothing about gets a
    row saying so, so an absence is an answer and not a reason to look again."""
    from .queries import Requirement, concepts, labels, resolve

    index, known, text = labels(store), concepts(store), kb_text(store)
    out = []
    for term in terms:
        start = len(out)
        res = resolve(Requirement("", term, "", ""), index, known)
        for concept in res.concepts:
            held = holds(store, concept)[1]
            if not held:
                out.append({"term": term, "found": curie(concept), "entry": "",
                            "via": "no project holds it", "evidence": "", "text": ""})
            for h in held:
                via = f"holds {h['holds']}" + (f", {h['hops']} hop" if h["hops"] else "") + \
                      (", implies" if h["implied"] else "")
                out.append({"term": term, "found": curie(concept), "entry": h["project"],
                            "via": via, "evidence": h["evidence"], "text": ""})
        pattern, hits = text_pattern(term), []
        for entry, pred, body, pv, proj in text:
            m = pattern.search(body)
            if m:
                name = curie(entry) + (f" ({curie(proj)})" if proj else "")
                hits.append({"term": term, "found": "text", "entry": name, "via": curie(pred),
                             "evidence": pv, "text": snippet(body, m.start(), m.end())})
        out += hits[:TEXT_HITS]
        if len(hits) > TEXT_HITS:
            out.append({"term": term, "found": "text", "entry": "",
                        "via": f"{len(hits) - TEXT_HITS} more - a narrower term finds them",
                        "evidence": "", "text": ""})
        if len(out) == start:
            out.append({"term": term, "found": "nothing", "entry": "",
                        "via": "no concept, and no text in the record names it",
                        "evidence": "", "text": ""})
    return (("term", "found", "entry", "via", "evidence", "text"), out)


@query("person", doc="where they are, how they work, their rights to work, and the roles they hold now")
def person(store):
    """What eligibility and logistics are judged against: location and work mode, each
    work authorization, and every ongoing role - a second job is a constraint on the
    first. Anything not recorded says so. Willingness to relocate or keep other hours
    lives in prose: `jsk kb query evidence relocate remote` finds it."""
    out = []

    def row(fact, value, entry="", pv=""):
        out.append({"fact": fact, "value": value, "entry": entry, "provenance": pv})

    who = store.select(PRE + """SELECT ?city ?region ?country ?mode ?pv WHERE {
        k:person j:provenance ?pv
        OPTIONAL { k:person j:city ?city } OPTIONAL { k:person j:region ?region }
        OPTIONAL { k:person j:country ?country } OPTIONAL { k:person j:workMode ?mode } }""")
    w = who[0] if who else {}
    place = ", ".join(w[k].value for k in ("city", "region", "country") if k in w)
    pv = local(w["pv"].value) if "pv" in w else ""
    row("location", place or "not recorded", "k:person" if place else "", pv if place else "")
    row("work mode", local(w["mode"].value) if "mode" in w else "not recorded",
        "k:person" if "mode" in w else "", pv if "mode" in w else "")

    auths = store.select(PRE + """SELECT ?a ?where ?kind ?status ?until ?pv WHERE {
        ?a a j:WorkAuthorization ; j:jurisdiction ?where ; j:kind ?kind ;
           j:authorization ?status ; j:provenance ?pv
        OPTIONAL { ?a j:validUntil ?until } FILTER NOT EXISTS { ?a j:retired ?r } }
        ORDER BY ?where""")
    for a in auths:
        value = f"{a['where'].value}: {local(a['kind'].value)}, {local(a['status'].value)}" + \
                (f" until {a['until'].value}" if "until" in a else "")
        row("work authorization", value, curie(a["a"].value), local(a["pv"].value))
    if not auths:
        row("work authorization", "not recorded")

    roles = store.select(PRE + """SELECT ?pos ?title ?org ?start ?kind ?pv WHERE {
        ?pos a j:Position ; j:state j:ongoing ; j:title ?title ; j:start ?start ;
             j:provenance ?pv ; j:organisation ?o . ?o j:name ?org
        OPTIONAL { ?pos j:engagementKind ?kind } FILTER NOT EXISTS { ?pos j:retired ?r } }
        ORDER BY ?start""")
    for r in roles:
        kind = local(r["kind"].value) if "kind" in r else "employment"
        row("ongoing role", f"{r['title'].value} at {r['org'].value}, since {r['start'].value} ({kind})",
            curie(r["pos"].value), local(r["pv"].value))
    if not roles:
        row("ongoing role", "none recorded")
    return (("fact", "value", "entry", "provenance"), out)


def table(columns, rows):
    """A Markdown table; `|` in a value is escaped so the row keeps its cells."""
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    out += ["| " + " | ".join(cell(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join(out)
