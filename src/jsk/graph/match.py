"""jsk match - a posting's requirements joined with the career, through the vocabulary.

Usage: jsk match <applications/<dir>/posting.ttl> [--cover N] [--json] [--today YYYY-MM-DD]
                 [--gaps <gaps.md>]

  --cover N   the most projects the cover may use (default 3)
  --json      the same result, structured
  --today     the date recency is measured from (default: today)
  --gaps F    check gaps.md's Requirements table against the match instead of printing it

Reads the whole graph workspace the posting belongs to - career/kb.ttl, the applications,
the shipped vocabulary - and validates it first: a record with a FAIL is not matched,
because a match over a broken record would be a guess.

Exit 0 matched (missing requirements included: this is an assessment, not a gate),
1 the workspace has FAIL findings, or --gaps found a FAIL, 2 called wrong.

Each requirement lands in one bucket. `matched`: a project holds the concept, or one that
counts as it. `near`: only through an implies edge, for a required requirement, or the
project holds something broader. `missing`, `ambiguous` (the label names more than one
concept - the analyst answers with j:concept), `candidate` (it names none), `implicit`.
Each gets a default Verdict from its bucket and evidence; gaps.md may lower it, never raise it.
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


SOURCES = "dashboards, retros, release notes"
# The top of the Ranking whose bullets are asked about as well as the selection's.
TOP = 6


def record_faults(store, post, today, budget, ranked=None):
    """The bullets this posting's draft would carry whose numbers the record cannot back -
    one entry per bullet, in the draft's order - as questions for round 1.

    On the ElevenLabs run kb.ttl held six such bullets ("a 300-400 candidate drive" citing
    nothing). `jsk kb export --urs` found them only mid-authoring, and the author "fixed"
    one by moving 300-400 to 300-800 to fit an unrelated metric: a factual change the
    person had to undo. The number is the person's to give, so it is asked here, before
    anyone writes.

    The draft is the one `jsk kb export --from-match` writes for this posting - select.py's
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
    asked about too, by rank: the ones gaps.md cites and the author reads (`ranked`, `TOP`).

    Empty when the workspace has no kb.ttl: the match stands alone."""
    from ..resume.career import Career
    from . import record as R
    from . import select as SEL

    if R.KB not in store.parsed:
        return []
    selection = SEL.select(store, post, today, budget)
    bullets = [b for p in selection.projects for b in selection.bullets.get(p, [])]
    career = Career(store.graph(R.KB))
    live = career.live("Achievement")
    for project in [r.project for r in ranked or () if r.required or r.preferred][:TOP]:
        bullets += sorted((a for a in live if career.get(a, "project") == project),
                          key=lambda a: (int(career.get(a, "rank", 0)), a))
    return faults_in(store, list(dict.fromkeys(bullets)), today)


def faults_in(store, bullets, today):
    """record_faults' entries for `bullets` (iris), in their order: numbers.untraced's
    Faults as the question's data."""
    from ..gates import numbers
    from .shapes import curie

    return [{"bullet": curie(f.bullet), "numbers": f.numbers,
             "superseded": [{"number": s["number"], "version": curie(s["version"]),
                             "until": s["until"]} for s in f.superseded],
             "cites": [curie(m) for m in f.cites]}
            for f in numbers.untraced(store, bullets, today)]


def quoted(numbers):
    shown = [f"'{n}'" for n in numbers]
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def fault_question(q):
    """The question, ready to be asked aloud. It asks for the figure and its source and
    offers only the words as the alternative - never another metric's number, which is
    how the ElevenLabs author turned a 300-400 into a 300-800 nobody had said."""
    parts = []
    if q["numbers"]:
        many = len(q["numbers"]) > 1
        parts.append(f"{quoted(q['numbers'])} in {q['bullet']} {'are' if many else 'is'} in "
                     + ("no metric it cites" if q["cites"] else "no metric (it cites none)"))
    for s in q["superseded"]:
        parts.append(f"'{s['number']}'" + ("" if q["numbers"] else f" in {q['bullet']}")
                     + f" is {s['version']}'s number, replaced on {s['until']}")
    many = len(q["numbers"]) + len(q["superseded"]) > 1
    return ("; ".join(parts) + " - " + ("what are the figures, and where do they come from"
                                         if many else "what is the figure, and where does it "
                                         "come from")
            + f" ({SOURCES})? Or should the words change?")


def verdict(state, carriers):
    """The Verdict the record supports, from the bucket and the evidence: the most gaps.md
    may say. A tag or an unconfirmed bullet is a claim, so matching on one is `unevidenced`.
    None for `implicit`: the match does not assess it."""
    if state == "matched":
        return ("satisfied" if any(c["evidence"] == "confirmed" for c in carriers)
                else "unevidenced")
    return {"near": "partial", "missing": "unsatisfied", "ambiguous": "indeterminate",
            "candidate": "indeterminate"}.get(state)


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
        carriers = [{"project": curie(p), "held": curie(h), "hops": hops, "implied": imp,
                     "evidence": Q.evidence(store, p, m.concept)}
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
        "posting": curie(post), "company": head["company"].value, "title": head["title"].value,
        "requirements": reqs,
        "ranking": [{"project": curie(r.project), "score": r.score, "required": list(r.required),
                     "preferred": list(r.preferred)} for r in ranked],
        "cover": {"budget": budget, "projects": None if chosen is None else
                  [curie(p) for p in chosen], "uncovered": uncovered,
                  "unresolved": Q.unresolved(matches)},
        "questions": [{"kind": q.kind, "requirement": q.requirement,
                       "detail": [curie(d) for d in q.detail]}
                      for q in Q.questions(store, matches)]
        # After the requirements' questions: the analyst's order puts a missing metric
        # after the unmet and the unconfirmed, and every one is asked before authoring.
        + [{"kind": "missing-metric", "requirement": None, "detail": [f["bullet"]], **f,
            "ask": fault_question(f)} for f in record_faults(store, post, today, budget,
                                                             ranked)],
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
    out += ["", "## Requirements", "",
            "Verdict is the most the record supports: gaps.md starts from it and may lower it.", "",
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
        if q["kind"] == "missing-metric":
            out.append(f"- **missing-metric** {q['bullet']}: {q['ask']}")
            continue
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


# Raising a verdict is never the analyst's call. When the match under-reads the record, the
# fix is in the career - the tag, or the confirmed bullet - made in the conversation with the
# person present; then the match reads it. A verdict typed higher is a claim nobody made.
RANK = {"satisfied": 3, "partial": 2, "unevidenced": 1, "unsatisfied": 0}
VERDICTS = (*RANK, "indeterminate")
RAISE_FIX = ("lower it, or - if the record really shows it - the career needs the tag or the "
             "confirmation, which the conversation makes; then re-run jsk match")


def gaps_table(text):
    """gaps.md's `# Requirements` table as {column: cell} rows; None when it has none."""
    import re

    def squash(cell):                       # not rules.squash: `_` is part of an id
        return re.sub(r"\s+", " ", re.sub(r"[*`]+", "", cell))

    rows, head, inside = [], None, False
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if s.startswith("#"):
            inside = s.lstrip("#").strip().lower() == "requirements"
            continue
        if not inside or not s.startswith("|"):
            continue
        cells = [squash(c).strip() for c in s.strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif not all(set(c) <= set("-: ") for c in cells):
            rows.append(dict(zip(head, cells)))
    return None if head is None else rows


def cites_id(cell):
    """Does the Evidence cell name a record id (`prj_x`, `k:ach_y`), not a paraphrase?"""
    import re

    from . import ontology as O

    return any((m := O.ID.fullmatch(t.rstrip("."))) and m["prefix"] in O.BY_PREFIX
               for t in re.findall(r"[a-z0-9_.]+", cell))


def check_gaps(reqs, rows):
    """(severity, text, fix) for each way gaps.md's table leaves the match's Verdicts."""
    from . import ontology as O

    out, by = [], {O.norm(q["asked"]): q for q in reqs}
    seen = set()
    for row in rows:
        asked, said = row.get("requirement", ""), row.get("verdict", "").lower()
        q = by.get(O.norm(asked))
        if q is None:
            out.append(("WARN", f"row {asked!r} matches no requirement of the posting",
                        "name it as posting.ttl's j:asked does, or add the requirement"))
            continue
        seen.add(q["id"])
        default = q["verdict"]
        if said not in VERDICTS:
            out.append(("FAIL", f"{asked}: {said!r} is not a verdict",
                        "one of " + ", ".join(VERDICTS)))
            continue
        if default == "indeterminate":
            raised = said in ("satisfied", "partial")
        else:
            raised = (default is not None and said != "indeterminate"
                      and RANK[said] > RANK[default])
        if raised:
            out.append(("FAIL", f"{asked}: {said}, above the match's {default}", RAISE_FIX))
        if said in ("satisfied", "partial") and not cites_id(row.get("evidence", "")):
            out.append(("FAIL", f"{asked}: {said} with no id in Evidence",
                        "cite the project or bullet id that shows it, or lower the verdict"))
        if said == "partial" and not row.get("shortfall"):
            out.append(("FAIL", f"{asked}: partial with no Shortfall",
                        "name the axis it falls short on"))
    for q in reqs:
        if q["id"] not in seen:
            out.append(("WARN", f"{q['asked']} ({q['id']}) has no row",
                        f"add it, starting from the match's verdict ({q['verdict'] or '-'})"))
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2
    options = {}
    for flag in ("--cover", "--today", "--gaps"):
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
              "[--today YYYY-MM-DD] [--gaps <gaps.md>]")
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
    from ..gates.report import show
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
    if "--gaps" in options:
        return report_gaps(r, options["--gaps"])
    print(json.dumps(r, indent=2, ensure_ascii=False) if as_json else markdown(r), end="")
    return 0


def report_gaps(r, path):
    """Print check_gaps' findings; 1 on any FAIL."""
    try:
        with open(path, encoding="utf-8") as fh:
            rows = gaps_table(fh.read())
    except OSError as e:
        print(f"FAIL  {path}: {e.strerror}")
        return 1
    if rows is None:
        print(f"FAIL  {path}: no `# Requirements` table\n      fix: write it - Requirement | "
              f"Need | Verdict | Evidence | Shortfall - one row per requirement")
        return 1
    found = check_gaps(r["requirements"], rows)
    for severity, text, fix in found:
        print(f"{severity}  {text}\n      fix: {fix}")
    fails = sum(s == "FAIL" for s, _, _ in found)
    print(f"{path}: {len(rows)} rows, {fails} FAIL, {len(found) - fails} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
