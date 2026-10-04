"""The named queries the career_query tool (jsk mcp) runs: questions an agent asks the record by name.

Each returns (columns, rows), rows as dicts, so the same answer prints as a table or as
JSON. A query is here because an agent would otherwise work it out by reading the whole
file - which is the reading the graph exists to save. `experience` and `pipeline` came
with the claims gate and the app_event tool (jsk mcp) (P5); the roadmap's `inconsistent` is not here yet.
`demand`, `shortfalls`, `drops`, `outcomes`, `repeated` and `absences` read what a
graph-native application puts in the store (docs/superpowers/plans/
2026-10-01-graph-native-applications-mcp.md, P3): questions across applications that no
file could answer; they live in insights.py. `evidence` and `person` replaced the tailor
analyst's grep of kb.ttl: on the Taskrabbit run it spent five of its seven minutes on some forty greps and reads for terms
and a location that two queries answer in half a second.

The SPARQL stays here, over Store.select: the query text is the verb (Ruling 3 of the onion
design). `@query` registers each verb in QUERIES, the kb's read vocabulary; the few that
resolve a term through the vocabulary are registered as `reads` and take the record's
feature reads (ports.queries.RecordQueries) as `queries`, and the few that count to a day
as `dated`, taking the day the command read from the clock as `today`. The rows go out as
data: the career_query tool returns them as they are.
"""
import datetime

from ...domain import ontology as O
from ...domain.matching import resolve as matching
from ...domain.matching.model import local
from ...domain.ontology import SPARQL_PREFIX as PRE
from ...domain.record.writer import curie
from ...domain.timeline.events import pipeline_rank
from . import likeness
from .holdings import experience_of

QUERIES = {}


def query(name, args="", doc="", reads=False, dated=False):
    """Register the function it decorates as the career_query tool's query `name`.

    Args:
        name: the verb.
        args: its arguments as the usage shows them; `...` at the end for one or more.
        doc: the line the verb's list gives it.
        reads: the verb takes the record's feature reads as `queries`.
        dated: the verb takes the day the command runs on as `today`.

    Returns:
        The decorator, which records (args, doc, fn, reads, dated) in QUERIES and returns
        fn.
    """
    def register(fn):
        QUERIES[name] = (args, doc, fn, reads, dated)
        return fn
    return register


@query("open", doc="open questions, oldest first")
def open_questions(store):
    """The questions nobody has answered yet, oldest first.

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows): one row per question, every entry it is about joined.
    """
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
    """Every live entry not yet confirmed, with an open question about it if there is one.

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows), by entry.
    """
    rows = store.select(PRE + """SELECT ?s ?pv (SAMPLE(?q) AS ?open) WHERE {
        ?s j:provenance ?pv FILTER(?pv != j:confirmed) FILTER NOT EXISTS { ?s j:retired ?r }
        OPTIONAL { ?q j:about ?s FILTER NOT EXISTS { ?q j:answered ?d } } }
        GROUP BY ?s ?pv ORDER BY ?s""")
    return (("entry", "provenance", "open question"),
            [{"entry": curie(r["s"].value), "provenance": local(r["pv"].value),
              "open question": curie(r["open"].value) if "open" in r else ""} for r in rows])


@query("holds", "<concept>", "live projects holding a concept, or one that counts as it",
       reads=True)
def holds(store, concept, *, queries):
    """The live projects holding `concept`, or something that counts as it, nearest first.

    Args:
        store: a loaded workspace.
        concept: a concept's iri, `c:` curie or bare id.
        queries: the record's feature reads over `store`.

    Returns:
        (columns, rows): one row per project - what it holds, how many hops away, whether
        through an implies edge, and the evidence behind it.
    """
    iri = concept if concept.startswith(O.C) else \
        O.C + concept[2:] if concept.startswith("c:") else O.C + concept
    rows = sorted(queries.paths_to(iri), key=lambda r: (r[2], r[0], r[1]))
    seen, out = set(), []
    for proj, held, hops, implied in rows:
        if proj in seen:
            continue
        seen.add(proj)
        out.append({"project": curie(proj), "holds": curie(held), "hops": hops,
                    "implied": implied, "evidence": matching.evidence(queries, proj, iri)})
    return (("project", "holds", "hops", "implied", "evidence"), out)


@query("stale", doc="applications that sent a metric version since replaced")
def stale(store):
    """The applications that sent a metric version which has since been replaced.

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows): the application, the version it sent, when that was replaced, and
        the version current now.
    """
    rows = store.select(PRE + """SELECT ?app ?v ?until ?now WHERE {
        ?app j:carriedVersion ?v . ?v j:validUntil ?until ; j:of ?m .
        OPTIONAL { ?now j:of ?m FILTER NOT EXISTS { ?now j:validUntil ?u } } }
        ORDER BY ?app ?v""")
    return (("application", "sent", "replaced", "current"),
            [{"application": curie(r["app"].value), "sent": curie(r["v"].value),
              "replaced": r["until"].value,
              "current": curie(r["now"].value) if "now" in r else ""} for r in rows])


@query("experience", "<concept>", "months the roles behind the projects holding a concept cover",
       dated=True)
def experience_query(store, concept, *, today):
    """experience_of as a table: each role behind the concept's projects, then the total.

    Args:
        store: a loaded workspace.
        concept: a concept's `c:` curie or bare id.
        today: the day an ongoing role runs to.

    Returns:
        (columns, rows), the last row the months in all, overlaps counted once.
    """
    iri = O.C + concept[2:] if concept.startswith("c:") else O.C + concept
    months, spans, _ = experience_of(store, iri, today)
    rows = [{"project": curie(p), "role": curie(pos), "from": start, "to": end or "ongoing",
             "months": ""} for p, pos, start, end in spans]
    rows.append({"project": "total, overlaps once", "role": "", "from": "", "to": "",
                 "months": months})
    return (("project", "role", "from", "to", "months"), rows)


@query("pipeline", doc="each application's stage: its latest event, and how long ago",
       dated=True)
def pipeline(store, *, today):
    """Each application's stage. The stage is a query, never a stored field: the latest
    dated event of each application. An event dated `unknown` is the stage only when
    nothing is dated. Events of one day are ordered by the pipeline (events.pipeline_rank),
    and the store keeps no time of recording to order them further.

    Args:
        store: a loaded workspace.
        today: the day the days since are counted to.

    Returns:
        (columns, rows), by application.
    """
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
                                                     r["date"].value,
                                                     pipeline_rank(local(r["kind"].value)),
                                                     r["e"].value))
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
TEXT_HITS_RESOLVED = 5           # when the term names a concept, its holders already answer it


def snippet(text, at, end, width=60):
    """The match with `width` characters either side, whitespace collapsed.

    Args:
        text: the text the match is in.
        at, end: the match's span.
        width: how much context either side.

    Returns:
        The snippet, an ellipsis at each end that was cut.
    """
    lo, hi = max(0, at - width), min(len(text), end + width)
    body = " ".join(text[lo:hi].split())
    return ("…" if lo else "") + body + ("…" if hi < len(text) else "")


def text_pattern(term):
    """A whole-word match of `term`. An all-capitals term is an acronym and matches in
    capitals only - REST is not "the rest of", BFF is not "bff".

    Args:
        term: one or more words.

    Returns:
        The compiled pattern.
    """
    import re
    words = r"\s+".join(re.escape(w) for w in term.split())
    return re.compile(rf"(?<!\w){words}(?!\w)", 0 if term.isupper() else re.IGNORECASE)


def kb_text(store):
    """Every string in the career on a live entry - what a grep of the file would find,
    without the retired, and without the vocabulary's labels, which the concept match has
    already answered.

    Args:
        store: a loaded workspace.

    Returns:
        [(entry, predicate, text, provenance, project)], by entry and predicate.
    """
    from ...domain.naming import graph_iri
    from ...domain.record.state import KB
    rows = store.select(PRE + f"""SELECT ?s ?p ?o ?pv ?proj WHERE {{
        GRAPH <{graph_iri(KB)}> {{ ?s ?p ?o
          FILTER(isIRI(?s) && !STRSTARTS(STR(?s), STR(c:)) && isLiteral(?o)
                 && DATATYPE(?o) = <http://www.w3.org/2001/XMLSchema#string>) }}
        OPTIONAL {{ ?s j:provenance ?pv }} OPTIONAL {{ ?s j:project ?proj }}
        FILTER NOT EXISTS {{ ?s j:retired ?r }} }} ORDER BY ?s ?p""")
    return [(r["s"].value, r["p"].value, r["o"].value,
             local(r["pv"].value) if "pv" in r else "",
             r["proj"].value if "proj" in r else None) for r in rows]


@query("evidence", "<term>...", "per term: projects holding its concept, then the record's text naming it",
       reads=True)
def evidence_for(store, *terms, queries):
    """What the record holds for each term, in one call: the concept the term names and
    the live projects holding it (as `holds` reports them), then every live entry whose
    text names it as a whole word - the grep an agent would otherwise run once per term,
    over a file it would have to find first. A term the record says nothing about gets a
    row saying so, so an absence is an answer and not a reason to look again. A term that
    names a concept shows fewer text hits: its holders are the answer, the text is colour.

    Args:
        store: a loaded workspace.
        *terms: the terms, each one or more words.
        queries: the record's feature reads over `store`.

    Returns:
        (columns, rows), term by term.
    """
    from ...domain.matching.model import Requirement
    from ...domain.matching.resolve import resolve

    index, known, text = matching.labels(queries), queries.concepts(), kb_text(store)
    out = []
    for term in terms:
        start = len(out)
        res = resolve(Requirement("", term, "", ""), index, known)
        for concept in res.concepts:
            held = holds(store, concept, queries=queries)[1]
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
        cap = TEXT_HITS_RESOLVED if res.concepts else TEXT_HITS
        out += hits[:cap]
        if len(hits) > cap:
            out.append({"term": term, "found": "text", "entry": "",
                        "via": f"{len(hits) - cap} more - a narrower term finds them",
                        "evidence": "", "text": ""})
        if len(out) == start:
            out.append({"term": term, "found": "nothing", "entry": "",
                        "via": "no concept, and no text in the record names it",
                        "evidence": "", "text": ""})
    return (("term", "found", "entry", "via", "evidence", "text"), out)


@query("concepts", doc="every concept: its labels, what it counts as, how many projects hold it",
       reads=True)
def concept_list(store, near=None, *, queries):
    """The vocabulary as one table, shipped and the person's own, to map a posting's
    phrases onto before the posting is written: "cloud-native architecture" is a label no
    concept has, and `j:concept` names the one it means. Read once, it replaces the grep
    for concept ids that followed every match full of `candidate`s.

    `near` (`--near <term>`): only the concepts the term names, then the few closest to
    it, closest first - a lookup for one term instead of reading 18 KB for it.

    Args:
        store: a loaded workspace.
        near: the term to look up, or None for every concept.
        queries: the record's feature reads over `store`.

    Returns:
        (columns, rows): each concept's labels, what it counts as, and how many live
        projects hold it.
    """
    from ...domain.matching.model import Requirement
    from ...domain.matching.nearest import nearest
    from ...domain.matching.resolve import resolve

    names, up, held = {}, {}, {}
    for r in store.select(PRE + "SELECT ?c ?l WHERE { ?c j:label ?l }"):
        names.setdefault(r["c"].value, set()).add(r["l"].value)
    for r in store.select(PRE + "SELECT ?c ?b WHERE { ?c j:isA|j:partOf ?b }"):
        up.setdefault(r["c"].value, set()).add(r["b"].value)
    for r in store.select(PRE + """SELECT ?c (COUNT(DISTINCT ?p) AS ?n) WHERE {
            ?p a j:Project ; j:uses|j:domain ?c FILTER NOT EXISTS { ?p j:retired ?x } }
            GROUP BY ?c"""):
        held[r["c"].value] = int(r["n"].value)
    known = queries.concepts()
    if near is None:
        shown = sorted(known)
    else:
        exact = resolve(Requirement("", near, "", ""), matching.labels(queries), known).concepts
        shown = list(dict.fromkeys((*exact, *nearest(queries, 5, None)(near))))
    return (("concept", "labels", "counts as", "held"),
            [{"concept": curie(c), "labels": ", ".join(sorted(names.get(c, ()))),
              "counts as": ", ".join(curie(b) for b in sorted(up.get(c, ()))),
              "held": held.get(c, "")} for c in shown])


@query("bare", doc="the career's capabilities with no label and no isA/partOf, most-held first")
def bare_list(store):
    """What `concepts-bare` counts, one row each: a capability nothing labels or places
    matches only its exact id, so a posting's "system design" misses c:systems-design.
    Most-held first - those are the ones a missed match costs most.

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows): each bare capability, how many projects hold it and bullets show it.
    """
    from ...domain.record.rules import bare_capabilities

    found = bare_capabilities(store)
    held, shown = {}, {}
    for r in store.select(PRE + """SELECT ?c (COUNT(DISTINCT ?p) AS ?n) WHERE {
            ?p a j:Project ; j:uses|j:domain ?c FILTER NOT EXISTS { ?p j:retired ?x } }
            GROUP BY ?c"""):
        held[r["c"].value] = int(r["n"].value)
    for r in store.select(PRE + """SELECT ?c (COUNT(DISTINCT ?b) AS ?n) WHERE {
            ?b j:shows ?c FILTER NOT EXISTS { ?b j:retired ?x } } GROUP BY ?c"""):
        shown[r["c"].value] = int(r["n"].value)
    order = sorted(found, key=lambda c: (-held.get(c, 0), -shown.get(c, 0), c))
    return (("concept", "held", "shown by"),
            [{"concept": curie(c), "held": held.get(c, 0), "shown by": shown.get(c, 0)}
             for c in order])


@query("person", doc="where they are, how they work, their rights to work, and the roles they hold now")
def person(store):
    """What eligibility and logistics are judged against: location and work mode, each
    work authorization, and every ongoing role - a second job is a constraint on the
    first. Anything not recorded says so. Willingness to relocate or keep other hours
    lives in prose: the career_query tool (jsk mcp) finds it.

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows): one row per fact, with the entry it is on and its provenance.
    """
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


query("similar", "<words>...", "live projects like what the words describe, best first",
      reads=True)(likeness.similar)
query("duplicates", doc="pairs of live projects that look like one project told twice")(
    likeness.duplicates)

# The insights across applications register themselves into QUERIES; imported last, as
# they use `query` and `pipeline` from here.
from . import insights  # noqa: E402, F401
