"""A posting matched against the career, through the vocabulary: what `jsk tailor match` prints.

Ported from the graph simulation (docs/superpowers/experiments/2026-09-24-graph-simulation/),
where every rule here was proven by a scenario and then by a mutation that broke it. The
rules, from docs/superpowers/specs/2026-09-24-graph-match-design.md:

- counts-as runs one way, from what a project holds up to what the posting asks for;
- within the closure P1 builds - 0, 1 or 2 hops, never more;
- a path through `implies` never carries a required requirement;
- a label that names two concepts is asked about, never guessed;
- a tag is not evidence: only a bullet that shows the concept is.

A RecordQueries finds the paths; this assembles the answer, because the answer is a
decision over several rows (the best path, the evidence level), not a row.
"""
from .. import ontology as O
from ..record.shapes import curie
from .model import Match, Resolution


def labels(queries):
    """{normalised label: {concept iris}} over labels and former labels, shipped and the
    person's own - after the career's unlabels, which the loader has already applied.

    Args:
        queries: a RecordQueries over a loaded workspace.

    Returns:
        Each label as O.norm keeps it, mapped to the concepts it names.
    """
    out = {}
    for c, label in queries.label_pairs():
        out.setdefault(O.norm(label), set()).add(c)
    return out


def resolve(req, index, known):
    """The concepts a requirement asks for: the analyst's choice, then an id, then labels.

    Args:
        req: a Requirement.
        index: `labels`' {normalised label: {concepts}}.
        known: every concept iri in the workspace.

    Returns:
        A Resolution: resolved, ambiguous (several named) or candidate (none).
    """
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


def match(queries, post):
    """{requirement iri: Match} for one posting.

    Args:
        queries: a RecordQueries over a loaded workspace.
        post: the posting's iri.

    Returns:
        Each requirement's Match, in the posting's requirement order.
    """
    index, known = labels(queries), queries.concepts()
    out = {}
    for req in queries.requirements(post):
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
            for proj, held, hops, implied in queries.paths_to(want):
                if implied and req.necessity == "required":
                    m.near.setdefault(proj, f"implied by {curie(held)}; confirm")
                    continue
                best = m.carriers.get(proj)
                if best is None or (hops, implied, held) < (best[1], best[2], best[0]):
                    m.carriers[proj] = (held, hops, implied)
        for want in m.concepts:
            for proj, held in queries.broader_held(want):
                if proj not in m.carriers:
                    m.near.setdefault(proj, f"holds broader {curie(held)}")
        for proj in m.carriers:
            m.near.pop(proj, None)
        m.state = "matched" if m.carriers else "near" if m.near else "missing"
    return out


def evidence(queries, project, concepts):
    """confirmed: a live, confirmed bullet shows one of the concepts, or something that
    counts as one without an implies edge. unconfirmed: only an inferred or unverified
    bullet does. tag: only the project's `uses` does - which is a claim, not evidence. A
    disputed bullet is evidence of nothing.

    Args:
        queries: a RecordQueries over a loaded workspace.
        project: the project's iri.
        concepts: one iri or several, any of which will do.

    Returns:
        "confirmed", "unconfirmed" or "tag".
    """
    levels = queries.evidence_levels(project, concepts)
    return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "tag"
