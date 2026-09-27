"""The gaps.md draft `jsk match --draft-gaps` writes: code fills every part the match already
knows, and leaves a `<!-- jsk: ... -->` slot wherever the analyst's judgement is needed.

On the JumpCloud run the analyst spent 11.8k output tokens rewriting what `jsk match` had
printed - the requirements with their verdicts and ids, the Ranking, the questions - and then
fixed the rows `--gaps` could not tie back to a requirement. Here the rows come from the
requirement ids, so they cannot drift, and `--gaps` FAILs on any slot left unfilled.
"""
import os

MARK = "<!-- jsk:"
IMPLICIT = "implicit — the match does not assess it"
CUT = 80


def slot(text):
    return f"{MARK} {text} -->"


def bare(curie):
    """`prj_x` for `k:prj_x`: what the analyst's template cites, and what cites_id reads."""
    return curie[2:] if curie.startswith("k:") else curie


def cell(text):
    return text.replace("|", "/")          # a pipe would split the table's cell


def advert(path):
    """posting.md's lines, as advert_lines numbers them; none when there is no posting.md."""
    from .io import normalise
    from .rules import advert_lines

    try:
        with open(path, encoding="utf-8") as fh:
            return advert_lines(normalise(fh.read()))
    except OSError:
        return []


def drops(post_dir):
    """decisions.txt's drops, or none for a posting written before decisions.txt existed.
    DecisionsError propagates: a file `jsk posting build` would refuse is not guessed at."""
    from . import decisions as D

    path = os.path.join(post_dir, "decisions.txt")
    return D.read(path).drops if os.path.isfile(path) else []


def cut(text):
    if len(text) <= CUT:
        return text
    return text[:CUT].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def eligibility(store, lines):
    from .named import person

    _, rows = person(store)
    facts = [f"  {r['fact']}: {r['value']}" + (f" ({r['provenance']})" if r["provenance"] else "")
             for r in rows]
    elig = [f'  advert: "{x.text}"' for x in lines if x.elig] or \
        ["  advert: nothing it says is about eligibility"]
    return [f"{MARK} judge eligibility against these facts, then write the verdict in place of "
            f"this comment", *facts, *elig, "-->"]


def evidence(q):
    if q["verdict"] == "satisfied":
        return ", ".join(bare(c["project"]) for c in q["carriers"] if c["evidence"] == "confirmed")
    if q["verdict"] == "unevidenced":
        return ", ".join(f"{bare(c['project'])} ({c['evidence']})" for c in q["carriers"])
    if q["verdict"] == "partial":
        return ", ".join(bare(n["project"]) for n in q["near"])
    return ""


def requirement_rows(reqs):
    out = ["| Requirement | Need | Verdict | Evidence | Shortfall |", "|---|---|---|---|---|"]
    for q in reqs:
        verdict = q["verdict"] or "indeterminate"            # Ruling 9: implicit rows
        short = ("" if q["verdict"] == "satisfied" else IMPLICIT if q["verdict"] is None
                 else slot("shortfall"))
        out.append(f"| {cell(q['asked'])} | {q['necessity']} | {verdict} | {evidence(q)} | "
                   f"{short} |".replace("|  |", "| |"))
    return out


def new_terms(reqs, dropped, lines):
    by_n = {x.n: x.text for x in lines}
    out = [f"- **{q['asked']}** — candidate: no concept holds it."
           for q in reqs if q["state"] == "candidate"]
    # An eligibility drop is judged under # Eligibility, not offered as a term (Ruling 8).
    out += [f"- **{cut(by_n.get(d.n, f'advert line {d.n}'))}** — dropped: {d.reason}"
            for d in dropped if not d.reason.lower().startswith("elig")]
    return out or ["None."]


# The analyst's order: blocking, unmet, unconfirmed, missing metric, unexplored.
ORDER = {"implied": 1, "broader-held": 1, "tag-only": 2, "missing-metric": 3,
         "ambiguous": 4, "unknown-term": 4}


def questions(r):
    from .match import question_line

    unmet = [(1, f"- **unsatisfied** {q['asked']}: required, and nothing in the record "
                 f"carries it - is there work that shows it?")
             for q in r["requirements"]
             if q["necessity"] == "required" and q["verdict"] == "unsatisfied"]
    asked = [(ORDER[q["kind"]], question_line(q)) for q in r["questions"]]
    ordered = [line for _, line in sorted(unmet + asked, key=lambda x: x[0])]
    return [f"- {slot('blocking: an eligibility question, or delete this line')}", *ordered,
            "", slot("reword each to be said aloud; add from jsk kb query unconfirmed")]


def draft_gaps(r, store, post, today, advert_path):
    """gaps.md for the match `r` of `post`, with a slot wherever judgement is needed."""
    from .match import cover_lines, ranking_lines

    lines = advert(advert_path)
    reqs = r["requirements"]
    out = ["---", "type: Gap Assessment", "posting: posting.ttl", f"assessed: {today.isoformat()}",
           f"fit: {slot('strong | partial | poor')}", "---", "",
           "# Eligibility", "", *eligibility(store, lines), "",
           "# Requirements", "", *requirement_rows(reqs), "",
           "# Ranking", "", *ranking_lines(r), "", *cover_lines(r), "",
           "# Where this falls short", "",
           slot("the unmet and partial requirements that matter, most load-bearing first"), "",
           "# Surplus worth knowing about", "",
           slot("optional - delete this line if there is none"), "",
           "# New terms", "", *new_terms(reqs, drops(os.path.dirname(os.path.abspath(advert_path))),
                                         lines), "",
           "# Questions", "", *questions(r)]
    return "\n".join(out) + "\n"
