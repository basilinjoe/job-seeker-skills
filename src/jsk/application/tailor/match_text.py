"""The match as markdown: what `jsk tailor match` prints, and the sections the gaps draft shares."""


def number(x):
    """`x` as a score prints: a whole number without its `.0`, anything else as it is."""
    return str(int(x)) if float(x).is_integer() else str(x)


def ranking_lines(r):
    """The Ranking as markdown prints it - shared with the gaps draft, so the two never differ."""
    out = ["Required ×3 · preferred ×1 · strength ×2 · recency +1 within 3 years, +0.5 at 4-6 · "
           "seniority +1 at or above the posting's.", "",
           "| Project | Score | Required | Preferred |", "|---|---|---|---|"]
    for row in r["ranking"]:
        out.append(f"| {row['project']} | {number(row['score'])} | {', '.join(row['required'])} | "
                   f"{', '.join(row['preferred'])} |")
    return out


def cover_lines(r):
    """The Cover as markdown prints it - shared with the gaps draft, so the two never differ."""
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
    """One of the match's questions as a list item - shared with the gaps draft."""
    if q["kind"] == "missing-metric":
        return f"- **missing-metric** {q['bullet']}: {q['ask']}"
    if q["kind"] == "unknown-term" and q["detail"]:
        return (f"- **unknown-term** {q['requirement']}: no concept has this label - "
                f"nearest {', '.join(q['detail'])}; name the one meant with j:concept, "
                f"or add it to the vocabulary?")
    return (f"- **{q['kind']}** {q['requirement']}: "
            + ASK[q["kind"]].format(" or ".join(q["detail"]) if q["kind"] == "ambiguous"
                                    else ", ".join(q["detail"])))


def markdown(r):
    """What `jsk tailor match` prints: the match `r` as markdown.

    Args:
        r: match_posting.result's plain data.

    Returns:
        The requirements table, the Ranking, the Cover and the Questions, one string.
    """
    reqs = r["requirements"]
    count = {s: sum(q["state"] == s for q in reqs) for s in
             ("matched", "near", "missing", "ambiguous", "candidate", "implicit")}
    need = {n: sum(q["necessity"] == n for q in reqs) for n in ("required", "preferred", "implicit")}
    out = [f"# Match - {r['title']} at {r['company']} ({r['posting']})", "",
           f"{need['required']} required, {need['preferred']} preferred, {need['implicit']} implicit. "
           + ", ".join(f"{n} {s}" for s, n in count.items() if n) + "."]
    n = r["warnings"]["count"]
    if n:
        # Named, not waved away: a label-clash or a necessity-wording warning can be exactly
        # what makes a row below wrong.
        out.append(f"The workspace has {n} warning{'s' if n > 1 else ''} "
                   f"({', '.join(r['warnings']['rules'])}); the validator's report lists "
                   f"{'them' if n > 1 else 'it'}.")
    if r["failures_elsewhere"]:
        m = r["failures_elsewhere"]
        out.append(f"{m} failure{'s' if m > 1 else ''} elsewhere in the workspace: matching those "
                   f"postings refuses until they are fixed.")
    out += ["", "## Requirements", "",
            "Verdict is the most the record supports: gaps.txt may lower it, never raise it.", "",
            "| Requirement | Need | State | Verdict | Carried by | Evidence |",
            "|---|---|---|---|---|---|"]
    for q in reqs:
        if q["carriers"]:
            carried = "; ".join(c["project"] + ("" if c["hops"] == 0 else
                                                f" (via {c['held']}, {c['hops']} hop"
                                                f"{'s' if c['hops'] > 1 else ''}"
                                                f"{', implied' if c['implied'] else ''})")
                                for c in q["carriers"])
            ev = "; ".join(c["evidence"] for c in q["carriers"])
        elif q["near"]:
            carried, ev = "; ".join(f"{n['project']}: {n['why']}" for n in q["near"]), ""
        elif q["state"] == "ambiguous":
            carried, ev = " or ".join(q["concepts"]) + "?", ""
        else:
            carried, ev = "", ""
        out.append(f"| {q['asked']} | {q['necessity']} | {q['state']} | {q['verdict'] or '-'} | "
                   f"{carried} | {ev} |")
    out += ["", "## Ranking", "", *ranking_lines(r), "", "## Cover", "", *cover_lines(r),
            "", "## Questions", ""]
    out += [question_line(q) for q in r["questions"]]
    if not r["questions"]:
        out.append("None: every requirement is matched with confirmed evidence, or missing.")
    return "\n".join(out) + "\n"

