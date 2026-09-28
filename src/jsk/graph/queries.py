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

from . import ontology as O
from .scoring import SENIORITY, WEIGHTS, recency_points
from .shapes import curie

PRE = (f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
       f"PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")


@dataclass(frozen=True)
class Requirement:
    iri: str
    asked: str
    quote: str
    necessity: str
    concepts: tuple = ()         # the analyst's answer: the concepts meant, any one satisfies


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
        """The first concept meant, for display; `concepts` is what matching reads."""
        return self.resolution.concepts[0] if self.resolution.state == "resolved" else None

    @property
    def concepts(self):
        """Every concept meant - any one satisfies - when resolved; () otherwise."""
        return self.resolution.concepts if self.resolution.state == "resolved" else ()


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
    # One row per j:concept: an advert listing alternatives names several.
    found = {}
    for r in rows:
        key = r["r"].value
        if key not in found:
            found[key] = (r["asked"].value, r["quote"].value, local(r["need"].value), set())
        if "concept" in r:
            found[key][3].add(r["concept"].value)
    return [Requirement(iri, asked, quote, need, tuple(sorted(cs)))
            for iri, (asked, quote, need, cs) in found.items()]


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
    """The concepts a requirement asks for: the analyst's choice, then an id, then labels."""
    if req.concepts:
        return Resolution("resolved", tuple(sorted(req.concepts)), "concept")
    key = O.norm(req.asked)
    named = set(index.get(key, ()))
    # An id wins only when no other concept goes by the same word. A person's own slug
    # meets free advert text here: were their board game c:go, "Go" would otherwise mean
    # it silently, and the language would never be asked about.
    if O.C + key in known and not named - {O.C + key}:
        return Resolution("resolved", (O.C + key,), "id")
    if O.C + key in known:
        named.add(O.C + key)
    found = tuple(sorted(named))
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
        # Any concept meant satisfies: a project carries the requirement through whichever
        # it holds by the shortest path.
        for want in m.concepts:
            for proj, held, hops, implied in paths_to(store, want):
                if implied and req.necessity == "required":
                    m.near.setdefault(proj, f"implied by {curie(held)}; confirm")
                    continue
                best = m.carriers.get(proj)
                if best is None or (hops, implied, held) < (best[1], best[2], best[0]):
                    m.carriers[proj] = (held, hops, implied)
        for want in m.concepts:
            for proj, held in broader_held(store, want):
                if proj not in m.carriers:
                    m.near.setdefault(proj, f"holds broader {curie(held)}")
        for proj in m.carriers:
            m.near.pop(proj, None)
        m.state = "matched" if m.carriers else "near" if m.near else "missing"
    return out


def evidence(store, project, concepts):
    """confirmed: a live, confirmed bullet shows one of the concepts, or something that
    counts as one without an implies edge. unconfirmed: only an inferred or unverified
    bullet does. tag: only the project's `uses` does - which is a claim, not evidence. A
    disputed bullet is evidence of nothing. `concepts` is one iri or several, any of which
    will do."""
    wanted = " ".join(f"<{c}>" for c in ((concepts,) if isinstance(concepts, str) else concepts))
    rows = store.select(PRE + f"""
        SELECT DISTINCT ?pv WHERE {{
          VALUES ?want {{ {wanted} }}
          ?b j:project <{project}> ; j:shows ?m ; j:provenance ?pv .
          GRAPH j:derived {{ ?p j:from ?m ; j:to ?want ; j:implied false }}
          FILTER(?pv != j:disputed)
          FILTER NOT EXISTS {{ ?b j:retired ?x }} }}""")
    levels = {local(r["pv"].value) for r in rows}
    return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "tag"


def confirmed_texts(store, project, concepts):
    """The words of the bullets that make `evidence` say confirmed: live, confirmed, and
    showing one of the concepts without an implies edge. Sorted, so a caller is stable."""
    wanted = " ".join(f"<{c}>" for c in ((concepts,) if isinstance(concepts, str) else concepts))
    rows = store.select(PRE + f"""
        SELECT DISTINCT ?t WHERE {{
          VALUES ?want {{ {wanted} }}
          ?b j:project <{project}> ; j:shows ?m ; j:provenance j:confirmed ; j:text ?t .
          GRAPH j:derived {{ ?p j:from ?m ; j:to ?want ; j:implied false }}
          FILTER NOT EXISTS {{ ?b j:retired ?x }} }}""")
    return sorted(r["t"].value for r in rows)


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
    """Every live project scored over the graph's matches: scoring.WEIGHTS per
    requirement carried (required x3, preferred x1), strength x2, recency, and a
    seniority point at or above the posting's. SENIORITY runs from most senior to least,
    so a lower index is higher."""
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
    # The tie-break: strength, then recency, then id.
    return sorted(rows, key=lambda r: (-r.score, -live[r.project][0], -live[r.project][1],
                                       r.project))


def cover(matches, budget, ranking=()):
    """(projects, uncovered): the smallest set of at most `budget` projects that carries
    every required requirement any project can carry - the top scores need not. Among
    sets of that size, the one whose projects score highest in `ranking` (the rows of
    `rank`), since the cover is what goes on the resume; then by id.

    `uncovered` is the required requirements nothing carries: missing or only near. An
    ambiguous or candidate one is not in it - it may well be carried, once someone says
    what it means. None for projects when no set within the budget does it."""
    required = [m for m in matches.values() if m.requirement.necessity == "required"
                and m.state == "matched"]
    carries = {}
    for m in required:
        for proj in m.carriers:
            carries.setdefault(proj, set()).add(m.requirement.iri)
    reachable = set().union(*carries.values()) if carries else set()
    uncovered = sorted(m.requirement.asked for m in matches.values()
                       if m.requirement.necessity == "required" and m.state in ("missing", "near"))
    score = {r.project: r.score for r in ranking}
    for size in range(0 if not reachable else 1, budget + 1):
        fits = [combo for combo in itertools.combinations(sorted(carries), size)
                if set().union(set(), *(carries[p] for p in combo)) >= reachable]
        if fits:
            best = max(fits, key=lambda combo: sum(score.get(p, 0) for p in combo))
            return list(best), uncovered
    return None, uncovered


def unresolved(matches):
    """Required requirements whose label names several concepts or none."""
    return sorted(m.requirement.asked for m in matches.values()
                  if m.requirement.necessity == "required" and m.state in ("ambiguous", "candidate"))


FILLER = {"a", "an", "and", "or", "the", "of", "in", "on", "with", "for", "to", "at", "as",
          "by", "experience", "skills", "strong", "knowledge", "years", "understanding"}


def words(text):
    """A phrase's content words, lowercased, a plural `s` dropped: "integration patterns"
    and c:integration-pattern share both."""
    import re
    out = set()
    for w in re.split(r"[^a-z0-9+#]+", text.lower()):
        if w and w not in FILLER:
            out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


COVER = 0.5   # the share of a label's weight a concept's words must carry to be offered


def posting(store, req):
    """The posting a requirement belongs to."""
    rows = store.select(PRE + f"SELECT ?p WHERE {{ <{req}> j:posting ?p }}")
    return rows[0]["p"].value if rows else None


def answered(store, post=None):
    """{(asked, concept): postings}: what the analyst named for each label on the other
    postings - the best guess at what this one means, since it was a person's answer. A
    retired concept is left out: a merge retires one an older posting still names."""
    out = {}
    for r in store.select(PRE + """SELECT DISTINCT ?p ?a ?c WHERE {
            ?r j:posting ?p ; j:asked ?a ; j:concept ?c
            FILTER NOT EXISTS { ?c j:retired ?x } }"""):
        if r["p"].value != post:
            out.setdefault((r["a"].value, r["c"].value), set()).add(r["p"].value)
    return out


def nearest(store, limit=3, post=None):
    """A function from an unresolved label to the concepts closest to it. First what other
    postings' analysts named for the same label, or for one sharing most of its words;
    then the concepts whose whole id or label the phrase contains; then the concepts whose
    id and labels share its words, a rare word counting for more:
    "architecture" names forty concepts and says little, "integration" names five. A
    concept is offered only if the words it shares carry half the label's weight, so one
    shared word in three is not a suggestion: "clear technical documentation" is not
    c:clinical-documentation. `post` is the posting asking, whose own answers are not
    offered back to it. Only a suggestion - the analyst names the one meant with
    `j:concept`, or none."""
    past = answered(store, post)
    bags, names = {}, {}
    for c in concepts(store):
        bags[c] = words(c[len(O.C):].replace("-", " "))
        names[c] = [set(bags[c])]        # a copy: the bag grows by the labels below
    for r in store.select(PRE + """SELECT ?c ?l WHERE { ?c j:label|j:former ?l }"""):
        bags.setdefault(r["c"].value, set()).update(words(r["l"].value))
        names.setdefault(r["c"].value, []).append(words(r["l"].value))
    for r in store.select(PRE + """SELECT ?c WHERE { ?c j:retired ?x
                                    FILTER(STRSTARTS(STR(?c), STR(c:))) }"""):
        bags.pop(r["c"].value, None)         # no longer meant: never a suggestion
        names.pop(r["c"].value, None)
    df = {}
    for bag in bags.values():
        for w in bag:
            df[w] = df.get(w, 0) + 1
    unseen = max((1 / n for n in df.values()), default=1)   # a word no concept has: the rarest

    def near(label):
        mine = words(label)
        ranked = []
        for (asked, c), posts in past.items():
            if O.norm(asked) == O.norm(label):
                ranked.append((0, 0, -len(posts), c))
            elif mine and len(mine & words(asked)) * 2 > len(mine):
                ranked.append((1, -len(mine & words(asked)), -len(posts), c))
        # A concept whose whole name the phrase contains: "clear technical documentation"
        # holds c:technical-documentation, whatever "clear" weighs. The longest name first;
        # a one-word name of two letters ("go" in "go-to-market") is too short to count.
        for c, ns in names.items():
            held = [n for n in ns if n and n <= mine and (len(n) > 1 or len(next(iter(n))) > 2)]
            if held:
                n = max(held, key=len)
                ranked.append((2, -len(n), -sum(1 / df[w] for w in n), c))
        out = []
        for *_, c in sorted(ranked):
            if c not in out:
                out.append(c)
        weight = {w: 1 / df[w] if w in df else unseen for w in mine}
        total = sum(weight.values())
        scored = [(sum(weight[w] for w in mine & bag), c) for c, bag in bags.items()
                  if mine & bag]
        scored = [(s, c) for s, c in scored if s >= COVER * total]
        scored.sort(key=lambda s: (-s[0], len(s[1]), s[1]))
        for _, c in scored:
            if c not in out:
                out.append(c)
        return tuple(out[:limit])
    return near


def labels_in(store):
    """A function from an advert line to the concepts whose whole label it holds, in the
    order the line names them - what `jsk posting extract` proposes beside each line, so
    the analyst accepts or strikes instead of reading the whole vocabulary.

    A label matches as contiguous words, a space or a hyphen between them either way. The
    longest label at a place wins, so "Azure AI Foundry" is not also c:azure. A label of two
    characters or fewer matches only as written: "Go" is the language, "go" in "go live"
    is not. A retired concept is never proposed."""
    import re

    def key(text):
        return re.sub(r"[\s-]+", "-", text.strip().lower())

    retired = {r["c"].value for r in store.select(PRE + """SELECT ?c WHERE { ?c j:retired ?x
                                                 FILTER(STRSTARTS(STR(?c), STR(c:))) }""")}
    meant = {}
    for r in store.select(PRE + """SELECT ?c ?l WHERE { ?c j:label|j:former ?l }"""):
        label = r["l"].value.strip()
        if label and r["c"].value not in retired:
            meant.setdefault((label if len(label) <= 2 else key(label)), set()).add(r["c"].value)
    if not meant:
        return lambda line: ()

    def alternative(label):
        body = r"[\s-]+".join(re.escape(w) for w in re.split(r"[\s-]+", label))
        return body if len(label) <= 2 else f"(?i:{body})"

    found = re.compile(r"(?<![A-Za-z0-9+#])(?:"
                       + "|".join(alternative(k) for k in sorted(meant, key=lambda k: (-len(k), k)))
                       + r")(?![A-Za-z0-9+#])")

    def named(line):
        out = []
        for m in found.finditer(line):
            said = m.group(0)
            for c in sorted(meant.get(said if len(said) <= 2 else key(said), ())):
                if c not in out:
                    out.append(c)
        return tuple(out)
    return named


def questions(store, matches):
    """The questions a tailoring round should ask - each one a named gap in the join."""
    out = []
    near = None
    for m in matches.values():
        asked = m.requirement.asked
        if m.state == "ambiguous":
            out.append(Question("ambiguous", asked, m.resolution.concepts))
        elif m.state == "candidate":
            near = near or nearest(store, post=posting(store, m.requirement.iri))
            out.append(Question("unknown-term", asked, near(asked)))
        elif m.state == "near":
            kind = "implied" if any("implied" in why for why in m.near.values()) else "broader-held"
            out.append(Question(kind, asked, tuple(sorted(m.near))))
        elif m.state == "matched":
            levels = {p: evidence(store, p, m.concepts) for p in m.carriers}
            if "confirmed" not in levels.values():
                out.append(Question("tag-only", asked, tuple(sorted(levels))))
    return sorted(out, key=lambda q: (q.requirement, q.kind))
