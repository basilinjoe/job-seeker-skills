"""What a resume for one posting selects, decided from the match: the projects, the bullets
under each and their order, the order of the skills, and the gaps the selection cannot close.

docs/superpowers/specs/2026-09-25-export-from-match-design.md. These are the rules the resume
author applied by hand from `jsk match` and a table in its prose; here the same posting always
selects the same evidence, and the author is left the words.

A tag is not evidence, and here that decides the cover too: a project carries a requirement
only when a live, confirmed bullet shows it. `jsk match` still reports tags - they are leads
for the conversation - so the filtering happens here, on a copy of its matches.
"""
import copy
from dataclasses import dataclass

from . import ontology as O
from . import queries as Q
from .scoring import WEIGHTS
from .shapes import curie

MOST = 8
KINDS = ("tag-only", "unconfirmed", "uncovered", "unresolved")
NEEDS = ("required", "preferred")


@dataclass(frozen=True)
class Gap:
    kind: str
    requirement: str             # the label as the posting wrote it
    necessity: str
    detail: str
    iri: str                     # the requirement, for the order

    def line(self):
        return f"GAP   {self.kind:<11} {self.requirement} ({self.necessity}): {self.detail}"


@dataclass
class Selection:
    projects: list               # iris, in position order, additions last
    bullets: dict                # project iri -> bullet iris, in render order
    skills: list                 # skill iris, the posting's first
    gaps: list                   # Gap, sorted


def band(position):
    """(cap, floor) for a project at this 1-based position among the selected."""
    if position <= 2:
        return 5, 3
    if position <= 5:
        return 2, 1
    return 1, 1


def pick(candidates, assigned, cap, floor):
    """The bullets a project shows, from `candidates` - (bullet, score, requirements shown),
    best first. First, greedily, until every requirement in `assigned` is shown (the cover
    beats the cap); then scoring bullets up to `cap`; then any, up to `floor`. Returned in
    the candidates' order."""
    chosen, unshown = set(), set(assigned)
    while unshown:
        best = None
        for i, (b, _, reqs) in enumerate(candidates):
            gain = len(reqs & unshown)
            if b not in chosen and gain and (best is None or gain > best[0]):
                best = (gain, i)
        if best is None:
            break
        b, _, reqs = candidates[best[1]]
        chosen.add(b)
        unshown -= reqs
    for b, score, _ in candidates:
        if len(chosen) >= cap:
            break
        if score > 0:
            chosen.add(b)
    for b, _, _ in candidates:
        if len(chosen) >= floor:
            break
        chosen.add(b)
    return [b for b, _, _ in candidates if b in chosen]


def bullets(store):
    """{bullet: (project, rank, provenance)} for every live bullet."""
    rows = store.select(Q.PRE + """
        SELECT ?b ?p ?rank ?pv WHERE { ?b j:project ?p ; j:rank ?rank ; j:provenance ?pv .
                                       FILTER NOT EXISTS { ?b j:retired ?x } }""")
    return {r["b"].value: (r["p"].value, int(r["rank"].value), Q.local(r["pv"].value))
            for r in rows}


def shows(store):
    """{bullet: the concepts it shows or counts as, without an implies edge}."""
    rows = store.select(Q.PRE + """
        SELECT ?b ?to WHERE { ?b j:project ?p ; j:shows ?m .
          GRAPH j:derived { ?x j:from ?m ; j:to ?to ; j:implied false } }""")
    out = {}
    for r in rows:
        out.setdefault(r["b"].value, set()).add(r["to"].value)
    return out


def cites_current(store):
    """Bullets citing a metric that has a current version - the ones export keeps a number
    for."""
    rows = store.select(Q.PRE + """
        SELECT DISTINCT ?b WHERE { ?b j:project ?p ; j:cites ?m . ?v j:of ?m .
                                   FILTER NOT EXISTS { ?v j:validUntil ?u } }""")
    return {r["b"].value for r in rows}


def evidenced(store, matches, held, shown):
    """(matches with carriers cut to confirmed evidence, the gaps the cut left)."""
    kept, gaps = {}, []
    for iri, m in matches.items():
        req = m.requirement
        if req.necessity not in NEEDS:
            kept[iri] = m
            continue
        if m.state in ("ambiguous", "candidate"):
            detail = (f"ambiguous - {' or '.join(curie(c) for c in m.resolution.concepts)}"
                      if m.state == "ambiguous" else "no concept has this label")
            gaps.append(Gap("unresolved", req.asked, req.necessity, detail, iri))
            kept[iri] = m
            continue
        if m.state != "matched":
            kept[iri] = m
            continue
        n = copy.copy(m)
        n.carriers, tags, loose = {}, [], []
        for proj, (h, hops, imp) in sorted(m.carriers.items()):
            level = Q.evidence(store, proj, m.concept)
            if level == "confirmed":
                n.carriers[proj] = (h, hops, imp)
            elif level == "unconfirmed":
                loose += sorted(b for b, (p, _, pv) in held.items() if p == proj
                                and pv not in ("confirmed", "disputed")
                                and m.concept in shown.get(b, ()))
            else:
                # A bullet showing the held concept, when it only implies the one asked
                # for, is not evidence - but "no bullet shows it" would send the person
                # to write one that exists.
                near = sorted(b for b, (p, _, pv) in held.items()
                              if p == proj and h in shown.get(b, ()))
                tags.append(f"{curie(near[0])} shows {curie(h)}, which only implies "
                            f"{curie(m.concept)}" if near and h != m.concept
                            else f"{curie(proj)} tags {curie(h)}, and no bullet shows it")
        if not n.carriers:
            n.state = "missing"
            if tags:
                gaps.append(Gap("tag-only", req.asked, req.necessity, "; ".join(tags), iri))
            if loose:
                named = ", ".join(f"{curie(b)} ({held[b][2]})" for b in loose)
                gaps.append(Gap("unconfirmed", req.asked, req.necessity,
                                f"{named} shows it - confirm it" if len(loose) == 1
                                else f"{named} show it - confirm one", iri))
        kept[iri] = n
    return kept, gaps


def skill_order(store, matches):
    """Every live skill: those matching a required requirement, then a preferred one, then
    the rest; within each by the first requirement matched, then export's own order.
    Skills are display entries, not concepts, so they match by label."""
    from ..gates import claims
    from . import record as R
    from .export import Career, skills

    names = {}
    for label, concepts in Q.labels(store).items():
        for c in concepts:
            names.setdefault(c, set()).add(label)
    wanted = []                  # (group, requirement index, normalised labels)
    for i, m in enumerate(matches.values()):
        need = m.requirement.necessity
        if need not in NEEDS:
            continue
        labels = {O.norm(m.requirement.asked)}
        if m.concept:
            labels |= names.get(m.concept, set())
        wanted.append((NEEDS.index(need), i, labels))
    order = []
    # The aliases as export writes them: one it leaves out cannot rank its skill.
    for at, item in enumerate(skills(Career(store.graph(R.KB)), claims.Career(store))):
        own = {O.norm(item["name"])} | {O.norm(a) for a in item.get("aliases", [])}
        key = min(((g, i) for g, i, labels in wanted if own & labels), default=(2, 0))
        order.append((key, at, O.K + item["id"]))
    return [iri for *_, iri in sorted(order)]


def select(store, post, today, budget, extra=()):
    """The Selection for one posting; `extra` is iris to add, in order (`--select`)."""
    matches = Q.match(store, post)
    held, shown, citing = bullets(store), shows(store), cites_current(store)
    kept, gaps = evidenced(store, matches, held, shown)
    ranked = Q.rank(store, post, kept, today)
    cover = Q.cover(kept, budget, ranked)[0] or []
    position = {r.project: i for i, r in enumerate(ranked)}
    carrying = {p for m in kept.values() if m.requirement.necessity in NEEDS
                for p in m.carriers}
    projects = list(cover)
    for row in ranked:
        if len(projects) >= max(MOST, len(cover)):
            break
        if row.project in carrying and row.project not in projects:
            projects.append(row.project)
    projects.sort(key=position.get)

    # What a bullet is worth: the requirements it shows, then a number it can stand on.
    reqs = [(iri, m) for iri, m in kept.items() if m.requirement.necessity in NEEDS and m.concept]

    def worth(b):
        mine = {iri for iri, m in reqs if m.concept in shown.get(b, ())}
        return mine, sum(WEIGHTS[kept[i].requirement.necessity] for i in mine) + (b in citing)

    def order(b):
        return -worth(b)[1], held[b][1], b

    def candidates(proj):
        rows = sorted((b for b, (p, _, pv) in held.items() if p == proj and pv == "confirmed"),
                      key=order)
        return [(b, worth(b)[1], worth(b)[0]) for b in rows]

    # Each required requirement to the highest-placed project that carries it: the cover's
    # when one fits, else any selected - so no carried requirement loses its bullet to a cap.
    anchors = cover or projects
    owner = {}
    for iri, m in kept.items():
        mine = [p for p in anchors if p in m.carriers]
        if m.requirement.necessity == "required" and mine:
            owner[iri] = min(mine, key=position.get)
    chosen = {}
    for n, proj in enumerate(projects, 1):
        cap, floor = band(n)
        chosen[proj] = pick(candidates(proj), {i for i, p in owner.items() if p == proj},
                            cap, floor)

    for iri in extra:
        cls = O.class_of(iri)
        if cls == "Project" and iri not in chosen:
            first = sorted((rank, b) for b, (p, rank, pv) in held.items()
                           if p == iri and pv == "confirmed")
            projects.append(iri)
            chosen[iri] = [b for _, b in first[:1]]
        elif cls == "Achievement" and iri in held:
            proj = held[iri][0]
            if proj not in chosen:
                projects.append(proj)
                chosen[proj] = []
            if iri not in chosen[proj]:
                # Placed by what it shows, whatever its provenance: a reworded bullet is
                # inferred until confirmed, and must not fall to the bottom for it.
                chosen[proj] = sorted(chosen[proj] + [iri], key=order)

    # What the picked bullets show decides the gaps: a requirement a picked confirmed
    # bullet shows has none; one only a picked unconfirmed bullet shows needs confirming.
    picked = [b for bs in chosen.values() for b in bs]
    firm = set().union(*(shown.get(b, set()) for b in picked if held[b][2] == "confirmed"))
    soft = {}
    for b in picked:
        if held[b][2] != "confirmed":
            for c in shown.get(b, ()):
                soft.setdefault(c, []).append(b)
    concept = {iri: m.concept for iri, m in kept.items()}
    gaps = [g for g in gaps if g.kind == "unresolved" or not (
        concept[g.iri] in firm or (g.kind == "tag-only" and concept[g.iri] in soft))]
    for at, g in enumerate(gaps):
        if g.kind == "unconfirmed" and concept[g.iri] in soft:
            named = ", ".join(f"{curie(b)} ({held[b][2]})" for b in sorted(soft[concept[g.iri]]))
            gaps[at] = Gap(g.kind, g.requirement, g.necessity,
                           f"{named} is selected - confirm it before it renders", g.iri)
    said = {g.iri for g in gaps}
    for iri, m in kept.items():
        req = m.requirement
        if req.necessity not in NEEDS or iri in said or not m.concept or m.concept in firm:
            continue
        if m.concept in soft:
            named = ", ".join(f"{curie(b)} ({held[b][2]})" for b in sorted(soft[m.concept]))
            gaps.append(Gap("unconfirmed", req.asked, req.necessity,
                            f"{named} is selected - confirm it before it renders", iri))
            continue
        if req.necessity != "required":
            continue
        if m.carriers:
            detail = "its carriers were not selected: " + ", ".join(
                curie(p) for p in sorted(m.carriers))
        elif m.near:
            detail = "only near - " + "; ".join(f"{curie(p)} {why}"
                                                for p, why in sorted(m.near.items()))
        else:
            detail = "nothing carries it"
        gaps.append(Gap("uncovered", req.asked, req.necessity, detail, iri))
    gaps.sort(key=lambda g: (NEEDS.index(g.necessity), KINDS.index(g.kind), g.iri))
    return Selection(projects, chosen, skill_order(store, kept), gaps)
