"""The smallest set of projects that carries a posting's required requirements."""
import itertools


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
