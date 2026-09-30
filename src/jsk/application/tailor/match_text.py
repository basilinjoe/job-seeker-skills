"""The match's sections as markdown lines, shared by `jsk match` and the gaps draft."""


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
