"""jsk match - a posting's requirements joined with the career, through the vocabulary.

Usage: jsk match <applications/<dir>> [--cover N] [--json] [--today YYYY-MM-DD]
                 [--gaps <gaps.txt> | --draft-gaps <gaps.txt>]

  --cover N         the most projects the cover may use (default 3)
  --json            the same result, structured
  --today           the date recency is measured from (default: today)
  --gaps F          check the application's gaps.txt against the match, then write the
                    assessment and gaps.md; a `<!-- jsk: ... -->` slot still in it is a
                    FAIL, and on a FAIL nothing is written
  --draft-gaps F    write the assessment and gaps.md from the match alone, then draft
                    gaps.txt with a slot wherever judgement is needed; refuses an F that
                    exists

Reads the whole record of the workspace the application belongs to - the career, the
applications, the shipped vocabulary - and validates it first: a record with a FAIL is
not matched, because a match over a broken record would be a guess.

Exit 0 matched (missing requirements included: this is an assessment, not a gate),
1 the workspace has FAIL findings, or --gaps found a FAIL, 2 called wrong.

Each requirement lands in one bucket. `matched`: a project holds the concept, or one that
counts as it. `near`: only through an implies edge, for a required requirement, or the
project holds something broader. `missing`, `ambiguous` (the label names more than one
concept - the analyst answers with j:concept), `candidate` (it names none), `implicit`.
Each gets a default Verdict from its bucket and evidence; gaps.txt may lower it, never raise it.
"""
import datetime
import json
import os
import sys

from ..cliutil import docstring_usage, wants_help
from ..domain.ontology import ENUMS

COVER = 3


def application(arg, command="jsk match"):
    """(workspace root, application directory) for the application `arg` names - its
    directory, applications/<dir> - or (None, [what is wrong, the fix]).

    Ruling 11 of the 2026-09-29 plan: the posting is a graph in career/store/ now, not a
    file to point at, so every command takes the application, as `jsk posting build` and
    `jsk freeze` always did. A path to posting.ttl is how a shell history or an older
    agent file still calls it, so it is refused with the new form."""
    here = os.path.abspath(arg)
    if os.path.basename(here) == "posting.ttl":
        folder = os.path.dirname(arg.rstrip("/\\")) or "."
        return None, [f"{arg}: {command} takes the application now, not its posting.ttl",
                      f"fix:  {command} {folder}"]
    apps = os.path.dirname(here)
    root = os.path.dirname(apps)
    career = os.path.join(root, "career")
    if not os.path.isdir(here) or os.path.basename(apps) != "applications" or not (
            os.path.isdir(os.path.join(career, "store"))
            or os.path.isfile(os.path.join(career, "kb.ttl"))):
        return None, [f"{arg}: not an application - a folder in the applications/ of a "
                      "workspace", f"fix:  {command} applications/<dir>, the folder "
                      "holding posting.md"]
    return root, here


def posting_in(store, app):
    """The one Posting the application `app` (its directory) holds, or None."""
    from ..domain import ontology as O
    from . import store as S

    name = S.app_graph(S.file_name(app, store.root), "posting")
    posts = [iri for iri in store.homes if O.class_of(iri) == "Posting"
             and store.file_of(iri) == name]
    return posts[0] if len(posts) == 1 else None


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

    Empty when the workspace has no career: the match stands alone."""
    from ..domain.record.career import Career
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
    from ..application.gates import numbers
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
                     "evidence": Q.evidence(store, p, m.concepts)}
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


# Raising a verdict is never the analyst's call. When the match under-reads the record, the
# fix is in the career - the tag, or the confirmed bullet - made in the conversation with the
# person present; then the match reads it. A verdict typed higher is a claim nobody made.
VERDICTS = ENUMS["verdict"]
# satisfied 3 … unsatisfied 0; `indeterminate`, last, ranks nowhere.
RANK = {v: len(VERDICTS) - 2 - n for n, v in enumerate(VERDICTS[:-1])}
RAISE_FIX = ("lower it, or - if the record really shows it - the career needs the tag or the "
             "confirmation, which the conversation makes; then re-run jsk match")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2
    options = {}
    for flag in ("--cover", "--today", "--gaps", "--draft-gaps"):
        if flag in argv:
            at = argv.index(flag)
            if at + 1 >= len(argv):
                print(f"{flag} needs a value")
                return 2
            options[flag] = argv[at + 1]
            del argv[at:at + 2]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if len(argv) != 1 or {"--gaps", "--draft-gaps"} <= options.keys():
        print("usage: jsk match <applications/<dir>> [--cover N] [--json] "
              "[--today YYYY-MM-DD] [--gaps <gaps.txt> | --draft-gaps <gaps.txt>]")
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
    root, app = application(argv[0])
    if root is None:
        print("\n".join(app))
        return 2
    for flag in ("--gaps", "--draft-gaps"):
        refused = flag in options and gaps_refusal(app, options[flag], flag == "--draft-gaps")
        if refused:
            print(refused)
            return 1

    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk match needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from . import record as R

    # --gaps and --draft-gaps write the assessment, so they take their turn before they
    # read: what they validate is what they write over. A plain match only reads.
    writes = "--gaps" in options or "--draft-gaps" in options
    with R.turn(root, dry_run=not writes):
        return matched(root, app, argv[0], options, today, budget, as_json)


def matched(root, app, named, options, today, budget, as_json):
    from ..cliutil import show
    from . import store as S

    store = S.load(root)
    here = S.file_name(app, store.root) + "/"
    blocking = [f for f in store.fails() if blocks(f, here)]
    if blocking:
        rep = S.Store(store.root, findings=blocking).report()
        print(f"FAIL  the workspace has {len(rep.fails)} failures - fix them before matching:")
        show(rep.fails, "FAIL", 25)
        return 1
    post = posting_in(store, app)
    if post is None:
        print(f"{named}: holds no posting\n"
              f"      fix: `jsk posting build {named}` writes it from posting.md")
        return 1
    r = result(store, post, today, budget, len(store.fails()) - len(blocking))
    if "--gaps" in options:
        return report_gaps(r, store, app, today)
    if "--draft-gaps" in options:
        return write_draft(r, store, app, today, options["--draft-gaps"])
    print(json.dumps(r, indent=2, ensure_ascii=False) if as_json else markdown(r), end="")
    return 0


def gaps_refusal(app, path, drafting):
    """Why `path` is not this application's gaps.txt, or None. gaps.md is written by jsk
    now, and read by nothing: a gaps.md jsk did not write is an older assessment."""
    if path.endswith(".md"):
        return (f"FAIL  {path}: gaps.md is written by jsk now; one it did not write is an "
                f"older assessment, read by people only\n"
                f"      fix: pass the application's gaps.txt - --draft-gaps drafts one")
    want = os.path.join(os.path.abspath(app), "gaps.txt")
    if os.path.normcase(os.path.abspath(path)) != os.path.normcase(want):
        return (f"FAIL  {path}: not this application's gaps.txt\n"
                f"      fix: pass {want} - gaps.md is written beside it")
    if drafting and os.path.exists(path):
        # The analyst's filled slots are its judgement; a re-run must not wipe them.
        return (f"FAIL  {path} exists - the draft would overwrite it\n"
                f"      fix: check it with --gaps, or delete it to draft again")
    if not drafting and not os.path.isfile(path):
        return (f"FAIL  {path}: no such file\n"
                f"      fix: draft it with --draft-gaps, or let `jsk tailor prepare` write "
                f"the assessment alone")
    return None


def show_build(written, found, label):
    """Print gapsbuild.build's findings and what it wrote; 1 on any FAIL."""
    for severity, text, fix in found:
        print(f"{severity}  {text}\n      fix: {fix}")
    fails = sum(s == "FAIL" for s, _, _ in found)
    if written:
        from .gapsbuild import shown
        wrote = " - wrote " + " and ".join(shown(w) for w in written)
    else:
        wrote = " - nothing written" if fails else ""
    print(f"{label}: {fails} FAIL, {len(found) - fails} WARN{wrote}")
    return 1 if fails else 0


def report_gaps(r, store, app, today):
    """--gaps: check gaps.txt, then write the assessment and gaps.md; 1 on any FAIL."""
    from .gapsbuild import build

    written, found = build(app, store, r, today)
    return show_build(written, found, os.path.join(app, "gaps.txt"))


def write_draft(r, store, app, today, path):
    """--draft-gaps: the assessment from the match alone, then gaps.txt drafted over it."""
    from . import store as S
    from .gapsbuild import build
    from .gapsderive import derive
    from .gapsdraft import MARK, draft_gaps

    derived = derive(r, store)
    written, found = build(app, store, r, today, derived)
    if show_build(written, found, S.app_graph(S.file_name(app, store.root), "gaps")):
        return 1
    text = draft_gaps(derived, store, os.path.join(app, "posting.md"))
    with open(path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    slots = sum(MARK in line for line in text.split("\n"))
    print(f"wrote {path}: {len(r['requirements'])} requirements, {slots} slots to fill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
