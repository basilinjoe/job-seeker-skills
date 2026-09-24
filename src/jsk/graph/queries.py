"""A posting matched against the career, through the vocabulary: what `jsk match` prints.

Ported from the graph simulation (docs/superpowers/experiments/2026-09-24-graph-simulation/),
where every rule here was proven by a scenario and then by a mutation that broke it. The
rules, from docs/superpowers/specs/2026-09-24-graph-match-design.md:

- counts-as runs one way, from what a project holds up to what the posting asks for;
- within the closure P1 builds - 0, 1 or 2 hops, never more;
- a path through `implies` never carries a required requirement;
- a label that names two concepts is asked about, never guessed;
- a tag is not evidence: only a bullet that shows the concept is.

SPARQL finds the paths; Python assembles the answer, because the answer is a decision
over several rows (the best path, the evidence level), not a row.
"""
import itertools
from dataclasses import dataclass, field

from ..kbindex import SENIORITY, WEIGHTS, recency_points
from . import ontology as O
from .shapes import curie

PRE = (f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
       f"PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")


@dataclass(frozen=True)
class Requirement:
    iri: str
    asked: str
    quote: str
    necessity: str
    concept: str = None          # the analyst's answer to an ambiguity


@dataclass(frozen=True)
class Resolution:
    state: str                   # resolved | ambiguous | candidate
    concepts: tuple              # iris, sorted
    via: str = None              # concept | id | label


@dataclass
class Match:
    requirement: Requirement
    resolution: Resolution
    state: str = None            # matched | near | missing | ambiguous | candidate | implicit
    carriers: dict = field(default_factory=dict)   # project -> (held, hops, implied)
    near: dict = field(default_factory=dict)       # project -> why

    @property
    def concept(self):
        return self.resolution.concepts[0] if self.resolution.state == "resolved" else None


@dataclass(frozen=True)
class Row:
    project: str
    score: float
    required: tuple
    preferred: tuple


@dataclass(frozen=True)
class Question:
    kind: str                    # ambiguous | unknown-term | implied | broader-held | tag-only
    requirement: str             # the label as the posting wrote it
    detail: tuple


def local(iri):
    return iri[len(O.J):] if iri.startswith(O.J) else iri


def requirements(store, post):
    rows = store.select(PRE + f"""
        SELECT ?r ?asked ?quote ?need ?concept WHERE {{
          ?r j:posting <{post}> ; j:asked ?asked ; j:quote ?quote ; j:necessity ?need .
          OPTIONAL {{ ?r j:concept ?concept }} }} ORDER BY ?r""")
    return [Requirement(r["r"].value, r["asked"].value, r["quote"].value, local(r["need"].value),
                        r["concept"].value if "concept" in r else None) for r in rows]


def labels(store):
    """{normalised label: {concept iris}} over labels and former labels, shipped and the
    person's own - after kb.ttl's unlabels, which the loader has already applied."""
    out = {}
    for r in store.select(PRE + """SELECT ?c ?l WHERE { ?c j:label|j:former ?l }"""):
        out.setdefault(O.norm(r["l"].value), set()).add(r["c"].value)
    return out


def concepts(store):
    return {r["c"].value for r in store.select(PRE + """
        SELECT DISTINCT ?c WHERE { GRAPH ?g { ?c ?p ?o }
                                   FILTER(STRSTARTS(STR(?c), STR(c:))) }""")}


def resolve(req, index, known):
    """The concept a requirement asks for: the analyst's choice, then an id, then labels."""
    if req.concept:
        return Resolution("resolved", (req.concept,), "concept")
    key = O.norm(req.asked)
    if O.C + key in known:
        return Resolution("resolved", (O.C + key,), "id")
    found = tuple(sorted(index.get(key, ())))
    if len(found) == 1:
        return Resolution("resolved", found, "label")
    return Resolution("ambiguous" if found else "candidate", found, "label" if found else None)


def paths_to(store, concept):
    """(project, held, hops, implied) for every live project holding something that counts
    as `concept` - the closure's paths run from the held concept up to the asked one."""
    rows = store.select(PRE + f"""
        SELECT ?proj ?held ?hops ?implied WHERE {{
          ?proj j:uses ?held .
          GRAPH j:derived {{ ?p j:from ?held ; j:to <{concept}> ; j:hops ?hops ;
                                j:implied ?implied }}
          FILTER NOT EXISTS {{ ?proj j:retired ?x }} }}""")
    return [(r["proj"].value, r["held"].value, int(r["hops"].value), r["implied"].value == "true")
            for r in rows]


def broader_held(store, concept):
    """(project, held) where the project holds only something `concept` counts as - the
    reverse direction, which never matches: Kubernetes work is not EKS work."""
    rows = store.select(PRE + f"""
        SELECT ?proj ?held WHERE {{
          ?proj j:uses ?held .
          GRAPH j:derived {{ ?p j:from <{concept}> ; j:to ?held ; j:hops ?h ; j:implied false }}
          FILTER(?h > 0) FILTER NOT EXISTS {{ ?proj j:retired ?x }} }}""")
    return [(r["proj"].value, r["held"].value) for r in rows]


def match(store, post):
    """{requirement iri: Match} for one posting."""
    index, known = labels(store), concepts(store)
    out = {}
    for req in requirements(store, post):
        m = Match(req, resolve(req, index, known))
        out[req.iri] = m
        if req.necessity == "implicit":
            m.state = "implicit"
            continue
        if m.resolution.state != "resolved":
            m.state = m.resolution.state
            continue
        for proj, held, hops, implied in paths_to(store, m.concept):
            if implied and req.necessity == "required":
                m.near.setdefault(proj, f"implied by {curie(held)}; confirm")
                continue
            best = m.carriers.get(proj)
            if best is None or (hops, implied, held) < (best[1], best[2], best[0]):
                m.carriers[proj] = (held, hops, implied)
        for proj, held in broader_held(store, m.concept):
            if proj not in m.carriers:
                m.near.setdefault(proj, f"holds broader {curie(held)}")
        for proj in m.carriers:
            m.near.pop(proj, None)
        m.state = "matched" if m.carriers else "near" if m.near else "missing"
    return out


def evidence(store, project, concept):
    """confirmed: a live, confirmed bullet shows the concept or something that counts as it
    without an implies edge. unconfirmed: only an inferred or unverified bullet does.
    tag: only the project's `uses` does - which is a claim, not evidence."""
    rows = store.select(PRE + f"""
        SELECT DISTINCT ?pv WHERE {{
          ?b j:project <{project}> ; j:shows ?m ; j:provenance ?pv .
          GRAPH j:derived {{ ?p j:from ?m ; j:to <{concept}> ; j:implied false }}
          FILTER NOT EXISTS {{ ?b j:retired ?x }} }}""")
    levels = {local(r["pv"].value) for r in rows}
    return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "tag"


def projects(store):
    """{project: (strength, recency, seniority)} for every live project."""
    rows = store.select(PRE + """
        SELECT ?p ?s ?r ?sen WHERE { ?p a j:Project ; j:strength ?s ; j:recency ?r .
                                     OPTIONAL { ?p j:seniority ?sen }
                                     FILTER NOT EXISTS { ?p j:retired ?x } }""")
    return {r["p"].value: (int(r["s"].value), int(r["r"].value),
                           local(r["sen"].value) if "sen" in r else None) for r in rows}


def posting_seniority(store, post):
    rows = store.select(PRE + f"SELECT ?s WHERE {{ <{post}> j:seniority ?s }}")
    return local(rows[0]["s"].value) if rows else None


def rank(store, post, matches, today):
    """Every live project scored as `jsk index --rank` scores it, over the graph's matches:
    required x3, preferred x1, strength x2, recency, and a seniority point at or above the
    posting's. SENIORITY runs from most senior to least, so a lower index is higher."""
    level = posting_seniority(store, post)
    level_at = SENIORITY.index(level) if level in SENIORITY else None
    rows = []
    live = projects(store)
    for proj, (strength, recency, seniority) in live.items():
        req = tuple(m.requirement.asked for m in matches.values()
                    if proj in m.carriers and m.requirement.necessity == "required")
        pref = tuple(m.requirement.asked for m in matches.values()
                     if proj in m.carriers and m.requirement.necessity == "preferred")
        score = (WEIGHTS["required"] * len(req) + WEIGHTS["preferred"] * len(pref)
                 + 2 * strength + recency_points(recency, today))
        if level_at is not None and seniority in SENIORITY and SENIORITY.index(seniority) <= level_at:
            score += 1
        rows.append(Row(proj, score, req, pref))
    # kbindex.rank's tie-break: strength, then recency, then id.
    return sorted(rows, key=lambda r: (-r.score, -live[r.project][0], -live[r.project][1],
                                       r.project))


def cover(matches, budget):
    """(projects, uncovered): the smallest set of at most `budget` projects that carries
    every required requirement any project can carry - the top scores need not.
    `uncovered` is what nothing carries. None for projects when no set within the budget
    does it."""
    required = [m for m in matches.values() if m.requirement.necessity == "required"
                and m.state == "matched"]
    carries = {}
    for m in required:
        for proj in m.carriers:
            carries.setdefault(proj, set()).add(m.requirement.iri)
    reachable = set().union(*carries.values()) if carries else set()
    uncovered = sorted(m.requirement.asked for m in matches.values()
                       if m.requirement.necessity == "required" and m.state != "matched")
    for size in range(0 if not reachable else 1, budget + 1):
        for combo in itertools.combinations(sorted(carries), size):
            if set().union(set(), *(carries[p] for p in combo)) >= reachable:
                return list(combo), uncovered
    return None, uncovered


def questions(store, matches):
    """The questions a tailoring round should ask - each one a named gap in the join."""
    out = []
    for m in matches.values():
        asked = m.requirement.asked
        if m.state == "ambiguous":
            out.append(Question("ambiguous", asked, m.resolution.concepts))
        elif m.state == "candidate":
            out.append(Question("unknown-term", asked, ()))
        elif m.state == "near":
            kind = "implied" if any("implied" in why for why in m.near.values()) else "broader-held"
            out.append(Question(kind, asked, tuple(sorted(m.near))))
        elif m.state == "matched":
            levels = {p: evidence(store, p, m.concept) for p in m.carriers}
            if "confirmed" not in levels.values():
                out.append(Question("tag-only", asked, tuple(sorted(levels))))
    return sorted(out, key=lambda q: (q.requirement, q.kind))
