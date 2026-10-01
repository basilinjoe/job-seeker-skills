"""The named queries across applications: what the postings ask for, where the person
falls short, why advert lines were left out, whether fit predicts the outcome, which
questions keep coming back, and each "no" the person gave.

They read what a graph-native application puts in the store (docs/superpowers/plans/
2026-10-01-graph-native-applications-mcp.md, P3) - questions no file could answer - and
register into application/record/queries.py's QUERIES with its `@query`, as `jsk kb query`
verbs. Split from queries.py (2026-10-02), which they would have taken past its size.
"""
from ...domain import ontology as O
from ...domain.matching.model import local
from ...domain.ontology import SPARQL_PREFIX as PRE
from ...domain.record.writer import curie
from .queries import pipeline, query


def counted(values):
    """"satisfied 2, partial 1": each value with how often it comes, most first."""
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return ", ".join(f"{v} {n}" for v, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])))



@query("demand", doc="each concept the postings ask for: how many postings, how many require it, my verdicts")
def demand(store):
    """What the postings ask for across every application: a concept, the postings asking
    for it, how many of those require it, and the verdicts the assessments gave it - the
    first of the insights the graph-native plan promised (docs/superpowers/plans/
    2026-10-01-graph-native-applications-mcp.md, P3).

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows), the most asked first.
    """
    rows = store.select(PRE + """SELECT ?c ?p ?r ?need ?v WHERE {
        ?r a j:Requirement ; j:posting ?p ; j:concept ?c ; j:necessity ?need
        OPTIONAL { ?vd a j:Verdict ; j:requirement ?r ; j:verdict ?v } }""")
    by = {}
    for r in rows:
        row = by.setdefault(r["c"].value, {"postings": set(), "required": set(), "verdicts": {}})
        row["postings"].add(r["p"].value)
        if r["need"].value == O.J + "required":
            row["required"].add(r["r"].value)
        if "v" in r:
            row["verdicts"][r["r"].value] = local(r["v"].value)
    out = [{"concept": curie(c), "postings": len(x["postings"]), "required": len(x["required"]),
            "verdicts": counted(x["verdicts"].values())} for c, x in by.items()]
    out.sort(key=lambda x: (-x["postings"], -x["required"], x["concept"]))
    return (("concept", "postings", "required", "verdicts"), out)


def absence_status(absences, today):
    """{concept iri: live, due or unconfirmed} for the career's unretired absences - the
    most standing one when a concept has several."""
    from ...domain.record.absence import live

    rank = {"live": 0, "due": 1, "unconfirmed": 2}
    out = {}
    for a in absences:
        if a.retired:
            continue
        status = ("unconfirmed" if a.provenance != "confirmed"
                  else "live" if live(a.said, today) else "due")
        if a.concept not in out or rank[status] < rank[out[a.concept]]:
            out[a.concept] = status
    return out


def career_absences(store):
    """The career's j:Absence entries (domain.record.absence.of_triples), none without a career."""
    from ...domain.record.absence import of_triples
    from ...domain.record.state import KB

    return of_triples(store.graph(KB)) if KB in store.parsed else []


@query("shortfalls", doc="concepts the assessments leave short (unsatisfied, partial, unevidenced), with any absence",
       dated=True)
def shortfalls(store, *, today):
    """Where the person keeps falling short: each concept a requirement names whose
    verdict is unsatisfied, partial or unevidenced, across every application, and whether a
    "no" the person gave stands for it (Ruling 8: live, due once lapsed, or unconfirmed).

    Args:
        store: a loaded workspace.
        today: the day an absence's lapse is measured against.

    Returns:
        (columns, rows), the most applications first.
    """
    # Short: lacked (unsatisfied), had in part (partial), or held with nothing confirmed
    # behind it (unevidenced) - the plan's "missing/partial", in the verdicts' own names.
    rows = store.select(PRE + """SELECT ?c ?p ?r ?v WHERE {
        ?vd a j:Verdict ; j:requirement ?r ; j:verdict ?v . ?r j:concept ?c ; j:posting ?p
        FILTER(?v IN (j:unsatisfied, j:partial, j:unevidenced)) }""")
    said = absence_status(career_absences(store), today)
    by = {}
    for r in rows:
        row = by.setdefault(r["c"].value, {"postings": set(), "verdicts": {}})
        row["postings"].add(r["p"].value)
        row["verdicts"][r["r"].value] = local(r["v"].value)
    out = [{"concept": curie(c), "applications": len(x["postings"]),
            "verdicts": counted(x["verdicts"].values()),
            "postings": ", ".join(sorted(curie(p) for p in x["postings"])),
            "absence": said.get(c, "")} for c, x in by.items()]
    out.sort(key=lambda x: (-x["applications"], x["concept"]))
    return (("concept", "applications", "verdicts", "postings", "absence"), out)


@query("drops", doc="why advert lines were left out, grouped by reason, with the postings")
def drops(store):
    """The analyst's reasons for leaving advert lines out of graph-native postings, grouped:
    a reason that keeps coming is a kind of line the advert parser could skip itself.

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows), the most used reason first.
    """
    rows = store.select(PRE + """SELECT ?l ?p ?reason WHERE {
        ?l a j:AdvertLine ; j:posting ?p ; j:dropped ?reason }""")
    by = {}
    for r in rows:
        row = by.setdefault(r["reason"].value, {"lines": set(), "postings": set()})
        row["lines"].add(r["l"].value)
        row["postings"].add(r["p"].value)
    out = [{"reason": reason, "lines": len(x["lines"]),
            "postings": ", ".join(sorted(curie(p) for p in x["postings"]))}
           for reason, x in by.items()]
    out.sort(key=lambda x: (-x["lines"], x["reason"]))
    return (("reason", "lines", "postings"), out)


@query("outcomes", doc="applications by the fit they were assessed at and the stage they reached",
       dated=True)
def outcomes(store, *, today):
    """Whether fit predicts what happens: applications grouped by their assessment's fit
    and their stage (`pipeline`'s latest event).

    Args:
        store: a loaded workspace.
        today: the day the pipeline counts to.

    Returns:
        (columns, rows), by fit then stage.
    """
    fits = {r["app"].value: local(r["fit"].value) for r in store.select(PRE + """
        SELECT ?app ?fit WHERE { ?app a j:Application ; j:posting ?p .
                                 ?g a j:Assessment ; j:posting ?p ; j:fit ?fit }""")}
    by = {}
    for row in pipeline(store, today=today)[1]:
        app = O.K + row["application"].removeprefix("k:")
        key = (fits.get(app, "not assessed"), row["stage"] or "no event")
        by.setdefault(key, []).append(row["application"])
    order = {"strong": 0, "partial": 1, "poor": 2}
    out = [{"fit": fit, "stage": stage, "applications": len(apps),
            "which": ", ".join(sorted(apps))}
           for (fit, stage), apps in sorted(by.items(), key=lambda x: (order.get(x[0][0], 3),
                                                                        x[0][1]))]
    return (("fit", "stage", "applications", "which"), out)


@query("repeated", doc="concepts asked about in more than one application's questions")
def repeated(store):
    """The questions that keep coming back: each concept a graph-native assessment's j:Ask
    names in more than one application. One worth answering once, in the career - a
    project, or a "no" (Ruling 8).

    Args:
        store: a loaded workspace.

    Returns:
        (columns, rows), the most applications first.
    """
    rows = store.select(PRE + """SELECT ?c ?p WHERE {
        ?a a j:Ask ; j:concept ?c ; j:assessment ?g . ?g j:posting ?p }""")
    by = {}
    for r in rows:
        by.setdefault(r["c"].value, set()).add(r["p"].value)
    out = [{"concept": curie(c), "applications": len(ps),
            "postings": ", ".join(sorted(curie(p) for p in ps))}
           for c, ps in by.items() if len(ps) > 1]
    out.sort(key=lambda x: (-x["applications"], x["concept"]))
    return (("concept", "applications", "postings"), out)


@query("absences", doc="each \"no\" the person gave: live, due to ask again, or unconfirmed",
       dated=True)
def absences(store, *, today):
    """Every j:Absence in the career (Ruling 8): what the person said they have not done,
    when, in their words, and whether it stands - live, due once a year has passed (a
    refresh asks it again), or unconfirmed, which the match ignores.

    Args:
        store: a loaded workspace.
        today: the day lapses are measured against.

    Returns:
        (columns, rows), due first, then live, then unconfirmed, each oldest first.
    """
    import datetime as dt

    from ...domain.record.absence import LAPSE_DAYS, live

    out = []
    for a in career_absences(store):
        if a.retired:
            continue
        status = ("unconfirmed" if a.provenance != "confirmed"
                  else "live" if live(a.said, today) else "due")
        out.append({"absence": curie(a.iri), "concept": curie(a.concept),
                    "said": a.said.isoformat(),
                    "lapses": (a.said + dt.timedelta(days=LAPSE_DAYS)).isoformat(),
                    "status": status, "answer": a.answer})
    order = {"due": 0, "live": 1, "unconfirmed": 2}
    out.sort(key=lambda x: (order[x["status"]], x["said"], x["absence"]))
    return (("absence", "concept", "said", "lapses", "status", "answer"), out)
