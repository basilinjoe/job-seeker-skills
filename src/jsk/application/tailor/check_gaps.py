"""The assessment: the derived assessment with the review folded in, checked, and rendered.

A graph-native application's overlay is its review graph (domain/assessment/review.py),
checked against the match (domain/assessment/fold.py) and folded in; its questions are
j:Ask nodes, and the assessment is the application's gaps graph - part of the record, so
SPARQL reaches it - rendered as text for the person (Ruling 24 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: no gaps.md). The
derivation takes the career's confirmed "no"s (Ruling 9). application/tailor/review.py,
assessment.py and show.py share what is here. It prints nothing.

Until 6.0 this also read an application's gaps.txt, decisions.txt and posting.md for
`jsk tailor match --gaps` and `jsk tailor prepare`, and wrote their assessment (`build`);
those verbs retired with the file-made pipeline (docs/superpowers/plans/
2026-10-03-retire-file-pipeline.md, P2). The match's Ranking, Cover and question lines,
which application/tailor/match_text.py printed for `jsk tailor match`, are here now: the
rendered assessment and the derivation are what still read them.
"""
from ...domain.assessment.fold import standing

# A graph-native assessment has no gaps.txt to edit: its overlay is the review graph,
# changed through the tool (Ruling 4 of the graph-native plan).
HEADER = ("<!-- rendered by jsk from the gaps graph - change the review with "
          "assessment_review, not this -->")
KEPT = "kept after review"
UNREVIEWED = "flagged, not yet reviewed"


def number(x):
    """`x` as a score prints: a whole number without its `.0`, anything else as it is."""
    return str(int(x)) if float(x).is_integer() else str(x)


def ranking_lines(r):
    """The Ranking, as the rendered assessment prints it."""
    out = ["Required ×3 · preferred ×1 · strength ×2 · recency +1 within 3 years, +0.5 at 4-6 · "
           "seniority +1 at or above the posting's.", "",
           "| Project | Score | Required | Preferred |", "|---|---|---|---|"]
    for row in r["ranking"]:
        out.append(f"| {row['project']} | {number(row['score'])} | {', '.join(row['required'])} | "
                   f"{', '.join(row['preferred'])} |")
    return out


def cover_lines(r):
    """The Cover, as the rendered assessment prints it."""
    cov, out = r["cover"], []
    if cov["projects"] is None:
        out.append(f"No {cov['budget']} projects carry every required requirement that can be "
                   f"carried; raise --cover or read the Ranking.")
    elif cov["projects"]:
        verb = "carries" if len(cov["projects"]) == 1 else "carry"
        out.append(f"{', '.join(cov['projects'])} {verb} every required requirement that can be "
                   f"carried.")
    if cov["uncovered"]:
        out.append(f"Nothing carries: {', '.join(cov['uncovered'])}.")
    if cov["unresolved"]:
        out.append(f"Unresolved, so not yet placed: {', '.join(cov['unresolved'])} - see Questions.")
    if not cov["projects"] and not cov["uncovered"] and not cov["unresolved"]:
        out.append("The posting has no required requirements.")
    return out


ASK = {"ambiguous": "which concept does it mean: {}?",
       "unknown-term": "no concept has this label - add it to the vocabulary?",
       "implied": "only implied, on {} - does the work really count?",
       "broader-held": "only something broader is held, on {} - is there narrower work?",
       "tag-only": "tagged on {}, but no confirmed bullet shows it"}


def question_line(q):
    """One of the match's questions as a list item: what the derivation asks with."""
    if q["kind"] == "missing-metric":
        return f"- **missing-metric** {q['bullet']}: {q['ask']}"
    if q["kind"] == "unknown-term" and q["detail"]:
        return (f"- **unknown-term** {q['requirement']}: no concept has this label - "
                f"nearest {', '.join(q['detail'])}; name the one meant with j:concept, "
                f"or add it to the vocabulary?")
    return (f"- **{q['kind']}** {q['requirement']}: "
            + ASK[q["kind"]].format(" or ".join(q["detail"]) if q["kind"] == "ambiguous"
                                    else ", ".join(q["detail"])))


def bare(curie):
    """`prj_x` for `k:prj_x`: the id as the analyst and the author cite it."""
    return curie.removeprefix("k:")


def cell(text):
    """`text` as one table cell: a `|` escaped, a newline a space."""
    return (text or "").replace("|", "\\|").replace("\n", " ")


def cut(text, n=80):
    """`text` cut at a word to at most `n` characters, an ellipsis marking the cut."""
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def falls_short(a):
    """The review's list, or - with none - the required requirements the verdicts leave
    short, in the match's order: an unreviewed assessment still says where it is weak."""
    if a.short:
        return [f"- {x}" for x in a.short]
    out = [f"- **{v.row.asked}** ({v.row.necessity}): {v.verdict} - {v.row.basis}"
           for v in a.verdicts if v.row.necessity == "required" and v.verdict != "satisfied"]
    return out or ["Nothing required falls short."]


def new_terms(r, dropped, lines):
    """The New terms: each candidate requirement, and each advert line dropped for a reason
    other than eligibility.

    Args:
        r: the match's plain data.
        dropped: the posting's drops, each with its line's `n` and its `reason`.
        lines: the advert's numbered lines.

    Returns:
        The list items, or ["None."].
    """
    by_n = {x.n: x.text for x in lines}
    out = [f"- **{q['asked']}** — candidate: no concept holds it."
           for q in r["requirements"] if q["state"] == "candidate"]
    # An eligibility drop is judged under # Eligibility, not offered as a term.
    out += [f"- **{cut(by_n.get(d.n, f'advert line {d.n}'))}** — dropped: {d.reason}"
            for d in dropped if not d.reason.lower().startswith("elig")]
    return out or ["None."]


def requirement_rows(a):
    """The Requirements table for the Assessment `a`, one row a verdict."""
    out = ["| Requirement | Need | Verdict | Evidence | Shortfall |", "|---|---|---|---|---|"]
    for v in a.verdicts:
        row = v.row
        if v.shortfall:
            short = v.shortfall
        elif v.kept:
            short = f"{KEPT}: {row.flag_text}"
        elif row.flags:
            short = f"{UNREVIEWED}: {row.flag_text}"
        else:
            short = "" if v.verdict == "satisfied" else row.basis
        verdict = v.verdict if v.verdict == standing(row) else f"{v.verdict} (match: {standing(row)})"
        out.append(f"| {cell(row.asked)} | {row.necessity} | {verdict} | "
                   f"{cell(', '.join(bare(p) for p in row.evidence))} | {cell(short)} |")
    return out


def render(r, a, today, lines=(), dropped=()):
    """The assessment as the person reads it, from the assessment and the match - what
    `app_show` gives as the assessment's markdown, never written to a file.

    Args:
        r: the match's plain data.
        a: the Assessment.
        today: the day it is dated.
        lines: the advert's numbered lines.
        dropped: the posting's drops.

    Returns:
        The assessment's text.
    """
    out = ["---", "type: Gap Assessment", f"posting: {a.derived.posting}",
           f"assessed: {today.isoformat()}", f"fit: {a.fit}", "---", HEADER, "",
           "# Eligibility", "",
           a.eligibility or "Not judged: the review gives no eligibility (`assessment_review`).",
           "",
           "# Requirements", "", *requirement_rows(a), "",
           "# Ranking", "", *ranking_lines(r), "", *cover_lines(r), "",
           "# Where this falls short", "", *falls_short(a), ""]
    if a.surplus:
        out += ["# Surplus worth knowing about", "", *(f"- {x}" for x in a.surplus), ""]
    out += ["# New terms", "", *new_terms(r, dropped, lines), "",
            "# Questions", "", *([f"- {q}" for q in a.questions] or ["None."])]
    return "\n".join(out) + "\n"


def review_of(store, app_rel):
    """(the review graph's Overlay, whether the review is complete); an empty Overlay and
    False when there is no review yet."""
    from ...domain import ontology as O
    from ...domain.assessment.overlay import Overlay
    from ...domain.assessment.review import overlay_of
    from ...domain.naming import app_graph

    name = app_graph(app_rel, "review")
    if name not in store.parsed:
        return Overlay(), False
    quads = store.graph(name)
    return overlay_of(quads), any(q.predicate.value == O.J + "state"
                                  and q.object.value == O.J + "complete" for q in quads)


def native_assessed(store, app_rel, derived, overlay, reviewed):
    """(the Assessment, the findings), or (None, the findings) on a FAIL: the review's
    overlay checked against the match and folded in.

    Args:
        store: the loaded workspace.
        app_rel: the application, `applications/<dir>`.
        derived: the Derived assessment.
        overlay: the review's Overlay.
        reviewed: the review is complete, so a flag it has not answered FAILs; a draft's
            waits.
    """
    from ...domain.assessment.fold import check, fold, previous_verdicts
    from ...domain.assessment.review import restated

    previous = previous_verdicts(store, app_rel, derived.stem)
    found = restated(check(derived, overlay, "", previous, reviewed))
    if any(s == "FAIL" for s, _, _ in found):
        return None, found
    return fold(derived, overlay, previous), found


def native_triples(store, app_rel, a, today):
    """The gaps graph's triples for a graph-native Assessment `a`: its questions as j:Ask
    nodes, and the day it was first made kept while it has not changed."""
    from ...domain.assessment.fold import assessed, same_triples, triples
    from ...domain.naming import app_graph

    gaps = app_graph(app_rel, "gaps")
    before = assessed(store, app_rel)
    if before and gaps in store.parsed and same_triples(triples(a, before, native=True),
                                                        store.graph(gaps)):
        today = before
    return triples(a, today, native=True)
