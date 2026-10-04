"""Matching an application's posting against the career, through the vocabulary.

The application's one posting is found and its requirements joined with the career into
`result`'s plain data, the dict the tests pin (Ruling 5 of the onion design keeps it a dict).
It prints nothing: application/tailor/assessment.py derives an assessment from it, which the
assessment_derive tool (jsk mcp) returns. `jsk tailor match --json` printed it until 6.0
retired the file-made pipeline.
"""
from ...domain.matching import questions as _questions
from ...domain.matching import rank as _rank
from ...domain.matching import resolve as _resolve
from ...domain.matching.cover import cover, unresolved
from ...domain.matching.report import fault_question, verdict
from ...domain.naming import app_graph
from ...domain.record.shapes import curie
from ...domain.record.state import KB

# The top of the Ranking whose bullets are asked about as well as the selection's.
TOP = 6


def posting_in(store, rel):
    """The one Posting the application holds, or None.

    Args:
        store: the loaded workspace.
        rel: the application's folder relative to the workspace (`applications/<dir>`).

    Returns:
        The posting's iri, or None when the application holds none, or more than one.
    """
    from ...domain import ontology as O

    name = app_graph(rel, "posting")
    posts = [iri for iri in store.homes if O.class_of(iri) == "Posting"
             and store.file_of(iri) == name]
    return posts[0] if len(posts) == 1 else None


def record_faults(store, queries, post, today, budget, ranked, select):
    """The bullets this posting's draft would carry whose numbers the record cannot back -
    one entry per bullet, in the draft's order - as questions for round 1.

    On the ElevenLabs run kb.ttl held six such bullets ("a 300-400 candidate drive" citing
    nothing). the resume_select tool (jsk mcp) found them only mid-authoring, and the author "fixed"
    one by moving 300-400 to 300-800 to fit an unrelated metric: a factual change the
    person had to undo. The number is the person's to give, so it is asked here, before
    anyone writes.

    The draft is the one the resume_select tool (jsk mcp) writes for this posting - select.py's
    projects (the cover, then the ranked projects that carry a requirement) and the
    bullets it picks under each - because those are exactly the bullets the author starts
    from. The whole Ranking would be every live project, and a fault in a bullet no draft
    selects is a question nobody needs answered for this posting; `jsk kb check` asks
    those across the career. numbers.untraced is called on the bullets themselves: this
    used to export a URS record and read the numerals back out of the record and claims
    gates' lines with three regexes, which broke whenever a gate reworded a line.

    The selection is not enough on its own. It picks from confirmed evidence, and on the
    ElevenLabs career as it stood before the run - nine requirements unresolved terms, the
    rest carried by tags - it picked nothing, so this asked nothing while `jsk kb check`
    named six faults. The author then read the top of the Ranking and exported those by
    hand. So every live bullet of the top-ranked projects that carry a requirement is
    asked about too, by rank: the ones the assessment cites and the author reads (`ranked`, `TOP`).

    Args:
        store: the loaded workspace.
        queries: the feature reads over it (ports.queries.RecordQueries).
        post: the posting's iri.
        today: the date recency is measured from.
        budget: the most projects the cover may use.
        ranked: the Ranking's rows, best first, or None.
        select: (store, post, today, budget) -> the posting's Selection.

    Returns:
        faults_in's entries; empty when the workspace has no career: the match stands alone.
    """
    from ...domain.record.career import Career

    if KB not in store.parsed:
        return []
    selection = select(store, post, today, budget)
    bullets = [b for p in selection.projects for b in selection.bullets.get(p, [])]
    career = Career(store.graph(KB))
    live = career.live("Achievement")
    for project in [r.project for r in ranked or () if r.required or r.preferred][:TOP]:
        bullets += sorted((a for a in live if career.get(a, "project") == project),
                          key=lambda a: (int(career.get(a, "rank", 0)), a))
    return faults_in(queries, list(dict.fromkeys(bullets)))


def faults_in(queries, bullets):
    """record_faults' entries for `bullets`, in their order: numbers.untraced's Faults as
    the question's data.

    Args:
        queries: the feature reads over the workspace (ports.queries.RecordQueries).
        bullets: the bullets' iris.

    Returns:
        [{bullet, numbers, superseded, cites}], ids as curies.
    """
    from ..gates import numbers

    return [{"bullet": curie(f.bullet), "numbers": f.numbers,
             "superseded": [{"number": s["number"], "version": curie(s["version"]),
                             "until": s["until"]} for s in f.superseded],
             "cites": [curie(m) for m in f.cites]}
            for f in numbers.untraced(queries, bullets)]


def result(store, queries, post, today, budget, elsewhere, select):
    """Everything the match reports, as plain data.

    Args:
        store: the loaded workspace.
        queries: the feature reads over it (ports.queries.RecordQueries).
        post: the posting's iri.
        today: the date recency is measured from.
        budget: the most projects the cover may use.
        elsewhere: the FAILs elsewhere in the workspace, which do not block this match.
        select: (store, post, today, budget) -> the posting's Selection.

    Returns:
        {posting, company, title, requirements, ranking, cover, questions, warnings,
        failures_elsewhere}: the dict --json prints.
    """
    matches = _resolve.match(queries, post)
    ranked = _rank.rank(queries, post, matches, today)
    chosen, uncovered = cover(matches, budget, ranked)
    company, title = queries.posting_head(post)
    reqs = []
    for m in matches.values():
        carriers = [{"project": curie(p), "held": curie(h), "hops": hops, "implied": imp,
                     "evidence": _resolve.evidence(queries, p, m.concepts)}
                    for p, (h, hops, imp) in sorted(m.carriers.items())]
        reqs.append({
            "id": curie(m.requirement.iri), "asked": m.requirement.asked,
            "necessity": m.requirement.necessity, "state": m.state,
            "verdict": verdict(m.state, carriers),
            "concepts": [curie(c) for c in m.resolution.concepts],
            "carriers": carriers,
            "near": [{"project": curie(p), "why": why} for p, why in sorted(m.near.items())],
        })
    return {
        "posting": curie(post), "company": company, "title": title,
        "requirements": reqs,
        "ranking": [{"project": curie(r.project), "score": r.score, "required": list(r.required),
                     "preferred": list(r.preferred)} for r in ranked],
        "cover": {"budget": budget, "projects": None if chosen is None else
                  [curie(p) for p in chosen], "uncovered": uncovered,
                  "unresolved": unresolved(matches)},
        "questions": [{"kind": q.kind, "requirement": q.requirement,
                       "detail": [curie(d) for d in q.detail]}
                      for q in _questions.questions(queries, matches)]
        # After the requirements' questions: the analyst's order puts a missing metric
        # after the unmet and the unconfirmed, and every one is asked before authoring.
        + [{"kind": "missing-metric", "requirement": None, "detail": [f["bullet"]], **f,
            "ask": fault_question(f)} for f in record_faults(store, queries, post, today,
                                                             budget, ranked, select)],
        "warnings": {"count": len(store.warns()),
                     "rules": sorted({f.rule for f in store.warns()})},
        "failures_elsewhere": elsewhere,
    }


