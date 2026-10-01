"""`app_show` and `app_list`: a graph-native application's parts, and every application and
resume the store holds, as plain data.

Nothing here writes. A part is read from the graph that holds it (Ruling 18 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md): the posting's header
and state, its lines - each line's concepts found on read through the vocabulary as it
stands, never stored (Ruling 1) - its requirements and drops, the review, and the
assessment as the gaps graph holds it. The assessment also comes as the Markdown
check_gaps.render writes: that needs the match's ranking and cover, which no graph keeps,
so it is rendered from a fresh read-only match with the stored review folded in, dated the
day the gaps graph was made. The selection is P3b's part and is not here yet.

`show` refuses an application made from files (Ruling 11), one with no posting, a part it
does not know, and an assessment not derived yet. `list_apps` reads every application:
file-built ones too, with their stage from the `pipeline` query.
"""
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.posting.errors import Refused
from ..posting import native as N

# The parts app_show reads, in the order the analyst needs them.
PARTS = ("posting", "lines", "requirements", "review", "assessment")


@dataclass(frozen=True)
class Drop:
    """An advert line left out, as check_gaps.render's New terms reads one."""

    n: int
    reason: str


def show(root, stem, part, *, today, ports):
    """One part of `applications/<stem>`, as plain data.

    Args:
        root: the workspace root.
        stem: the application's name.
        part: one of PARTS.
        today: the day the assessment's Markdown is matched on.
        ports: the bound ports (compose.native.Ports).

    Returns:
        A dict (posting, review, assessment) or a list (lines); requirements is
        {requirements, drops}.

    Raises:
        Refused: a part it does not know, a legacy application, no posting, or no
            assessment yet.
    """
    if part not in PARTS:
        raise Refused(f"{part!r} is not a part of an application",
                      f"fix:  one of {', '.join(PARTS)}")
    app = N.app_of(root, stem)
    store = N.loaded(app, ports)
    s = N.native(store, app, ports)
    if part == "posting":
        return posting(store, app, s)
    if part == "lines":
        return lines(store, s, ports)
    if part == "requirements":
        return requirements(s)
    if part == "review":
        return review(store, app)
    return assessment(store, app, s, today, ports)


def posting(store, app, s):
    """The posting's header, state and counts."""
    from .check_gaps import review_of

    _, done = review_of(store, app.rel)
    has_review = app.graph("review") in store.parsed
    return {"app": app.stem, "graph": app.graph("posting"), "company": s.head["company"],
            "title": s.head["title"], "url": s.head["url"] or None,
            "seniority": s.seniority or None,
            "domains": ["c:" + d.removeprefix(O.C) for d in s.domains],
            "captured": s.captured, "state": s.state, "lines": len(s.lines),
            "requirements": len(s.reqs), "dropped": len(s.drops),
            "review": ("complete" if done else "draft") if has_review else None,
            "assessed": app.graph("gaps") in store.parsed}


def lines(store, s, ports):
    """Every advert line: its number, section, flags, text, the concepts its labels name
    now, the requirements quoting it and its drop."""
    named = ports.labels_in(store)
    used = {}
    for slug, row in s.reqs.items():
        used.setdefault(row[4], []).append(slug)
    return [{"n": x.n, "section": x.section, "optional": x.optional, "eligibility": x.elig,
             "text": x.text, "concepts": ["c:" + c.removeprefix(O.C) for c in named(x.text)],
             "requirements": used.get(x.n, []), "dropped": s.drops.get(x.n)}
            for x in s.lines]


def requirements(s):
    """{requirements: [{slug, n, asked, need, concepts, quote}], drops: [{n, reason}]}."""
    return {"requirements": [{"slug": slug, "n": n, "asked": asked, "need": need,
                              "concepts": ["c:" + c.removeprefix(O.C) for c in iris],
                              "quote": quote}
                             for slug, (asked, need, iris, quote, n) in s.reqs.items()],
            "drops": [{"n": n, "reason": why} for n, why in sorted(s.drops.items())]}


def review(store, app):
    """The review: its state, fit, eligibility, verdicts and lists; state None when there
    is none yet."""
    from .check_gaps import review_of

    overlay, done = review_of(store, app.rel)
    there = app.graph("review") in store.parsed
    return {"state": ("complete" if done else "draft") if there else None,
            "fit": overlay.fit, "eligibility": overlay.eligibility,
            "verdicts": [{"slug": r.slug, "verdict": r.verdict, "reason": r.reason or None}
                         for r in overlay.rows],
            "short": list(overlay.short), "surplus": list(overlay.surplus),
            "asks": list(overlay.ask)}


def assessment(store, app, s, today, ports):
    """The gaps graph as data, and the assessment as Markdown.

    Returns:
        {assessed, fit, eligibility, rows, short, surplus, questions, markdown}; markdown
        is None, with `markdown_unavailable` saying why, when the match cannot run now.
    """
    name = app.graph("gaps")
    if name not in store.parsed:
        raise Refused(f"{app.rel} has no assessment yet",
                      f"fix:  the `assessment_derive` tool derives it ({app.stem})")
    out = gaps_data(store.graph(name), app)
    try:
        out["markdown"] = markdown(store, app, s, out["assessed"] or today.isoformat(),
                                   today, ports)
    except Refused as e:
        out["markdown"], out["markdown_unavailable"] = None, str(e)
    return out


def gaps_data(quads, app):
    """The gaps graph's assessment, verdicts and questions as plain data."""
    props = {}
    for q in quads:
        if q.predicate.value.startswith(O.J):
            props.setdefault(q.subject.value, {}).setdefault(
                q.predicate.value[len(O.J):], []).append(q.object.value)
    req = f"{O.K}req_{app.ids}_"

    def one(p, key):
        return p.get(key, [None])[0]

    def slug(iri):
        return iri.removeprefix(req) if iri else None

    def enum(value):
        return value.removeprefix(O.J) if value else None

    gap = props.get(f"{O.K}gap_{app.ids}", {})
    rows, asks = [], []
    for s, p in sorted(props.items()):
        if O.class_of(s) == "Verdict":
            rows.append({"slug": slug(one(p, "requirement")), "matched": enum(one(p, "matched")),
                         "verdict": enum(one(p, "verdict")), "basis": one(p, "basis"),
                         "flags": sorted(f.removeprefix(O.J) for f in p.get("flag", [])),
                         "evidence": sorted(e.removeprefix(O.K) for e in p.get("evidence", [])),
                         "shortfall": one(p, "shortfall")})
        elif O.class_of(s) == "Ask":
            asks.append({"position": int(one(p, "position") or 0),
                         "question": one(p, "question"),
                         "requirement": slug(one(p, "requirement")),
                         "concepts": sorted("c:" + c.removeprefix(O.C)
                                            for c in p.get("concept", []))})

    def listed(key):
        text = one(gap, key)
        return text.split("\n") if text else []

    return {"assessed": one(gap, "assessed"), "fit": enum(one(gap, "fit")),
            "eligibility": one(gap, "eligibility"), "rows": rows,
            "short": listed("fallsShort"), "surplus": listed("surplus"),
            "questions": sorted(asks, key=lambda x: x["position"])}


def markdown(store, app, s, assessed, today, ports):
    """check_gaps.render's Markdown for the assessment, from a read-only match.

    Raises:
        Refused: the match is stopped, or the review no longer folds into it.
    """
    import datetime

    from .assessment import matched
    from .check_gaps import native_assessed, render, review_of

    r, derived = matched(store, app, today, ports)
    overlay, done = review_of(store, app.rel)
    a, found = native_assessed(store, app.rel, derived, overlay, done)
    if a is None:
        raise Refused("the review no longer folds into the match: "
                      + "; ".join(text for sev, text, _ in found if sev == "FAIL"),
                      f"fix:  the `assessment_review` tool ({app.stem})")
    return render(r, a, datetime.date.fromisoformat(assessed), s.lines,
                  [Drop(n, why) for n, why in sorted(s.drops.items())])


def list_apps(root, *, today, ports):
    """Every application and general resume the store holds.

    Args:
        root: the workspace root.
        today: the day the pipeline counts to.
        ports: the bound ports (compose.native.Ports).

    Returns:
        {applications: [{app, kind, posting, review, assessed, submitted, stage, since}],
        resumes: [{name, graph}]}. `kind` is native, legacy, or None for no posting;
        `posting` the posting's state - legacy ones have none, and are complete.

    Raises:
        Refused: there is no store at `root`.
    """
    from ..record.queries import pipeline

    if not ports.has_store(root):
        raise Refused(f"no workspace (career/store/) at {root}",
                      "fix:  `jsk kb new` creates one, or run from inside a workspace")
    store = ports.load(root)
    rels = sorted({n.rsplit("/", 1)[0] for n in store.parsed
                   if n.startswith("applications/") and n.count("/") == 2})
    stages = {}
    for row in pipeline(store, today=today)[1]:
        home = store.file_of(O.K + row["application"].removeprefix("k:"))
        if home:
            stages[home.rsplit("/", 1)[0]] = row
    out = []
    for rel in rels:
        quads = store.parsed.get(f"{rel}/posting")
        native = quads is not None and N.has_lines(quads.quads)
        state = review_state = None
        for q in quads.quads if quads is not None else ():
            if q.predicate.value == O.J + "state" and O.class_of(q.subject.value) == "Posting":
                state = q.object.value.removeprefix(O.J)
        reviewed = store.parsed.get(f"{rel}/review")
        if reviewed is not None:
            review_state = "draft"
            for q in reviewed.quads:
                if q.predicate.value == O.J + "state":
                    review_state = q.object.value.removeprefix(O.J)
        stage = stages.get(rel, {})
        out.append({"app": rel.split("/", 1)[1],
                    "kind": "native" if native else "legacy" if quads is not None else None,
                    "posting": state, "review": review_state,
                    "assessed": f"{rel}/gaps" in store.parsed,
                    "submitted": stage.get("submitted"), "stage": stage.get("stage") or None,
                    "since": stage.get("since") or None})
    resumes = sorted(n for n in store.parsed if n.startswith("resumes/"))
    return {"applications": out,
            "resumes": [{"name": n.split("/")[1], "graph": n} for n in resumes]}
