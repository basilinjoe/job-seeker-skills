"""Every live project scored for a posting, over the graph's matches."""
from .model import Row
from .scoring import SENIORITY, WEIGHTS, recency_points


def rank(queries, post, matches, today):
    """Every live project scored over the graph's matches: scoring.WEIGHTS per
    requirement carried (required x3, preferred x1), strength x2, recency, and a
    seniority point at or above the posting's. SENIORITY runs from most senior to least,
    so a lower index is higher.

    Args:
        queries: a RecordQueries over a loaded workspace.
        post: the posting's iri.
        matches: resolve.match's {requirement iri: Match}.
        today: the date recency is counted from.

    Returns:
        [Row], best first; ties by strength, then recency, then id.
    """
    level = queries.posting_seniority(post)
    level_at = SENIORITY.index(level) if level in SENIORITY else None
    rows = []
    live = queries.projects()
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
