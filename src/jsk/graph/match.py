"""jsk match - a posting's requirements joined with the career, through the vocabulary.

Usage: jsk match <applications/<dir>/posting.ttl> [--cover N] [--json] [--today YYYY-MM-DD]

  --cover N   the most projects the cover may use (default 3)
  --json      the same result, structured
  --today     the date recency is measured from (default: today)

Reads the whole graph workspace the posting belongs to - career/kb.ttl, the applications,
the shipped vocabulary - and validates it first: a record with a FAIL is not matched,
because a match over a broken record would be a guess.

Exit 0 matched (missing requirements included: this is an assessment, not a gate),
1 the workspace has FAIL findings, 2 called wrong.

Each requirement lands in one bucket. `matched`: a project holds the concept, or one that
counts as it. `near`: only through an implies edge, for a required requirement, or the
project holds something broader. `missing`, `ambiguous` (the label names more than one
concept - the analyst answers with j:concept), `candidate` (it names none), `implicit`.
"""
import datetime
import json
import os
import sys

from ..cliutil import docstring_usage, wants_help

COVER = 3


def workspace_of(posting):
    """The directory holding applications/, or None when the posting is not in that layout."""
    folder = os.path.dirname(os.path.abspath(posting))
    apps = os.path.dirname(folder)
    if os.path.basename(apps) != "applications" or os.path.basename(posting) != "posting.ttl":
        return None
    return os.path.dirname(apps)


def result(store, post, today, budget, elsewhere=0):
    """Everything `jsk match` reports, as plain data."""
    from . import queries as Q
    from .shapes import curie

    matches = Q.match(store, post)
    ranked = Q.rank(store, post, matches, today)
    chosen, uncovered = Q.cover(matches, budget, ranked)
    head = store.select(Q.PRE + f"""SELECT ?company ?title WHERE {{
        <{post}> j:company ?company ; j:title ?title }}""")[0]
    reqs = []
    for m in matches.values():
        reqs.append({
            "id": curie(m.requirement.iri), "asked": m.requirement.asked,
            "necessity": m.requirement.necessity, "state": m.state,
            "concepts": [curie(c) for c in m.resolution.concepts],
            "carriers": [{"project": curie(p), "held": curie(h), "hops": hops, "implied": imp,
                          "evidence": Q.evidence(store, p, m.concept)}
                         for p, (h, hops, imp) in sorted(m.carriers.items())],
            "near": [{"project": curie(p), "why": why} for p, why in sorted(m.near.items())],
        })
    return {
        "posting": curie(post), "company": head["company"].value, "title": head["title"].value,
        "requirements": reqs,
        "ranking": [{"project": curie(r.project), "score": r.score, "required": list(r.required),
                     "preferred": list(r.preferred)} for r in ranked],
        "cover": {"budget": budget, "projects": None if chosen is None else
                  [curie(p) for p in chosen], "uncovered": uncovered,
                  "unresolved": Q.unresolved(matches)},
        "questions": [{"kind": q.kind, "requirement": q.requirement,
                       "detail": [curie(d) for d in q.detail]}
                      for q in Q.questions(store, matches)],
        "warnings": {"count": len(store.warns()),
                     "rules": sorted({f.rule for f in store.warns()})},
        "failures_elsewhere": elsewhere,
    }


def blocks(finding, here):
    """Does this FAIL stop matching the posting in `here` (its directory, with a slash)?

    The career, the vocabulary and the posting's own directory: a fault there changes what
    matches. A fault in another application does not - an old advert that no longer quotes
    cleanly must not block every new one - except a syntax error anywhere, which hides that
    file's ids and so switches off the dangling check for the whole workspace.
    """
    return (finding.rule == "syntax" or not finding.file.startswith("applications/")
            or finding.file.startswith(here))


def number(x):
    return str(int(x)) if float(x).is_integer() else str(x)


def markdown(r):
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
    out += ["", "## Requirements", "", "| Requirement | Need | State | Carried by | Evidence |",
            "|---|---|---|---|---|"]
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
        out.append(f"| {q['asked']} | {q['necessity']} | {q['state']} | {carried} | {ev} |")
    out += ["", "## Ranking", "",
            "Required ×3 · preferred ×1 · strength ×2 · recency +1 within 3 years, +0.5 at 4-6 · "
            "seniority +1 at or above the posting's.", "",
            "| Project | Score | Required | Preferred |", "|---|---|---|---|"]
    for row in r["ranking"]:
        out.append(f"| {row['project']} | {number(row['score'])} | {', '.join(row['required'])} | "
                   f"{', '.join(row['preferred'])} |")
    cov = r["cover"]
    out += ["", "## Cover", ""]
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
    out += ["", "## Questions", ""]
    ask = {"ambiguous": "which concept does it mean: {}?",
           "unknown-term": "no concept has this label - add it to the vocabulary?",
           "implied": "only implied, on {} - does the work really count?",
           "broader-held": "only something broader is held, on {} - is there narrower work?",
           "tag-only": "tagged on {}, but no confirmed bullet shows it"}
    for q in r["questions"]:
        if q["kind"] == "unknown-term" and q["detail"]:
            out.append(f"- **unknown-term** {q['requirement']}: no concept has this label - "
                       f"nearest {', '.join(q['detail'])}; name the one meant with j:concept, "
                       f"or add it to the vocabulary?")
            continue
        out.append(f"- **{q['kind']}** {q['requirement']}: "
                   + ask[q["kind"]].format(" or ".join(q["detail"]) if q["kind"] == "ambiguous"
                                           else ", ".join(q["detail"])))
    if not r["questions"]:
        out.append("None: every requirement is matched with confirmed evidence, or missing.")
    return "\n".join(out) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2
    options = {}
    for flag in ("--cover", "--today"):
        if flag in argv:
            at = argv.index(flag)
            if at + 1 >= len(argv):
                print(f"{flag} needs a value")
                return 2
            options[flag] = argv[at + 1]
            del argv[at:at + 2]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if len(argv) != 1:
        print("usage: jsk match <applications/<dir>/posting.ttl> [--cover N] [--json] "
              "[--today YYYY-MM-DD]")
        return 2
    try:
        budget = int(options.get("--cover", COVER))
        today = (datetime.date.fromisoformat(options["--today"]) if "--today" in options
                 else datetime.date.today())
    except ValueError:
        print("--cover takes a whole number and --today a YYYY-MM-DD date")
        return 2
    if budget < 1:
        print("--cover takes a whole number of at least 1")
        return 2
    posting = argv[0]
    root = workspace_of(posting)
    if root is None or not os.path.isfile(posting):
        print(f"{posting}: not a posting.ttl inside an applications/<dir>/ folder of a workspace")
        return 2

    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk match needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ..gates.validate_urs import show
    from . import ontology as O
    from . import store as S

    store = S.load(root)
    here = S.file_name(os.path.dirname(os.path.abspath(posting)), store.root) + "/"
    blocking = [f for f in store.fails() if blocks(f, here)]
    if blocking:
        rep = S.Store(store.root, findings=blocking).report()
        print(f"FAIL  the workspace has {len(rep.fails)} failures - fix them before matching:")
        show(rep.fails, "FAIL", 25)
        return 1
    posts = [iri for iri in store.homes if O.class_of(iri) == "Posting"
             and store.file_of(iri) == S.file_name(posting, store.root)]
    if len(posts) != 1:
        print(f"{posting}: holds no posting")          # the cardinality rule makes this rare
        return 1
    r = result(store, posts[0], today, budget, len(store.fails()) - len(blocking))
    print(json.dumps(r, indent=2, ensure_ascii=False) if as_json else markdown(r), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
