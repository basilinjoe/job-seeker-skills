"""`assessment_review` and `assessment_complete`: the analyst's review of a graph-native
assessment, kept as the review graph.

What gaps.txt held for a file-built application - a lowered verdict and its reason, a flag
answered `keep`, the fit, eligibility, and the short, surplus and ask lines - arrives here
as a batch (Ruling 18's `assessment_review`) and is upserted into
`applications/<stem>/review` (Ruling 4 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md): a verdict by its slug,
replaced or, sent with no verdict, cleared; each list replaced whole when given. Every
verdict is checked by fold.check against the match as it stands now, so a raised verdict
FAILs at once and nothing is written. `complete` is fold.check with `reviewed`: every flag
answered, no FAIL, then the review's `j:state complete`.

Both write the gaps graph in the same update as the review, folded with it (check_gaps'
`native_*`), so the assessment a caller reads next is the one the review made; a
re-derivation reads the review back and writes the same.

An ask may name the requirement it is about (`{question, about}`); the review keeps it as
the item's j:about, so the question's j:Ask carries that requirement and its concepts.

The FAILs: a slug not lowercase words; a verdict that is neither `keep` nor a verdict; a fit
that is none; an ask about a slug that is no requirement; and every fold.check FAIL - a slug
that is no requirement, a verdict above the match's, a lowered verdict with no reason, and
at `complete` a flag left unanswered. Each use case refuses (Refused) an application made
from files, one with no posting or a draft one, a frozen application (sent or held back),
and a FAIL that stops the match. It prints nothing.
"""
import re
from dataclasses import dataclass

from ...domain import ontology as O
from ..posting import native as N


@dataclass(frozen=True)
class Reviewed:
    """What one review or complete did."""

    target: str | None          # the review graph's name; None when nothing was written
    state: str                  # the review's state after it
    fit: str | None             # the fit that stands once it is folded in
    findings: tuple             # (severity, text, fix)
    written: tuple              # the graph names written


def review(root, stem, *, fit=None, eligibility=None, verdicts=(), short=None,
           surplus=None, asks=None, today, ports):
    """Upsert a batch into `applications/<stem>`'s review, checked against the match. The
    caller holds the workspace's turn.

    Args:
        root: the workspace root.
        stem: the application's name.
        fit: strong, partial or poor; "" clears it back to the match's; None leaves it.
        eligibility: the eligibility judgement; "" clears it; None leaves it.
        verdicts: each {slug, verdict, reason} as a dict or an object; `verdict` keep or a
            verdict, or empty to clear the slug's row.
        short: where it falls short, one item each, replacing the review's; None leaves it.
        surplus: likewise for surplus worth knowing.
        asks: likewise for the questions, which then replace the match's: each its text,
            or {question, about} with `about` the slug of the requirement it asks about.
        today: the day the match runs and the assessment is dated.
        ports: the bound ports (compose.native.Ports).

    Returns:
        The Reviewed; with a FAIL among its findings nothing was written.

    Raises:
        Refused: a legacy application, no posting, a draft one, a frozen application, or a
            FAIL that stops the match.
    """
    from ...domain.assessment.overlay import Row
    from .check_gaps import review_of

    app, store = opened(root, stem, ports)
    overlay, done = review_of(store, app.rel)
    prior = "complete" if done else "draft"
    found = []
    if fit is not None:
        if fit and fit not in O.ENUMS["fit"]:
            found.append(("FAIL", f"fit {fit!r} is not one of {', '.join(O.ENUMS['fit'])}",
                          "name one, or send it empty for the match's"))
        overlay.fit = fit or None
    if eligibility is not None:
        overlay.eligibility = str(eligibility).strip() or None
    rows = {row.slug: row for row in overlay.rows}
    for i, v in enumerate(verdicts or (), 1):
        slug, verdict = str(N.field(v, "slug") or ""), str(N.field(v, "verdict") or "")
        reason = str(N.field(v, "reason") or "").strip()
        if not re.fullmatch(O.SLUG, slug):
            found.append(("FAIL", f"verdicts[{i}]: slug {slug!r} is not lowercase words "
                                  "joined by `_`", "the requirement's slug, as app_show names it"))
        elif not verdict:
            rows.pop(slug, None)
        elif verdict not in ("keep", *O.ENUMS["verdict"]):
            found.append(("FAIL", f"verdicts[{i}]: {slug}: {verdict!r} is not keep or a "
                                  "verdict", f"keep, or one of {', '.join(O.ENUMS['verdict'])}"))
        else:
            rows[slug] = Row(0, slug, verdict, reason)
    for kind, items in (("short", short), ("surplus", surplus)):
        if items is not None:
            setattr(overlay, kind, [str(x).strip() for x in items if str(x).strip()])
    if asks is not None:
        overlay.ask, overlay.about = asked(asks, set(N.stored(store, app).reqs), found)
    overlay.rows = [Row(n, slug, row.verdict, row.reason)
                    for n, (slug, row) in enumerate(sorted(rows.items()), 1)]
    if N.fails(found):
        return Reviewed(None, prior, None, N.clean(found), ())
    return folded(app, store, overlay, "draft", found, today, ports, prior)


def asked(asks, slugs, found):
    """(the questions, {question: slug}) for a batch of asks, each a question's text or
    {question, about} with `about` a requirement's slug; an `about` naming no requirement of
    the posting is a FAIL appended to `found`.

    Args:
        asks: the batch.
        slugs: the posting's requirement slugs.
        found: the findings, appended to.
    """
    questions, about = [], {}
    for i, a in enumerate(asks, 1):
        if isinstance(a, str):
            text, slug = a.strip(), ""
        else:
            text = str(N.field(a, "question") or "").strip()
            slug = str(N.field(a, "about") or "").strip()
        if not text:
            continue
        questions.append(text)
        if not slug:
            continue
        if slug not in slugs:
            found.append(("FAIL", f"asks[{i}]: about {slug!r} is not a requirement of this "
                                  "posting", "the requirement's slug, as app_show names it - "
                          + ", ".join(sorted(slugs))[:200]))
        else:
            about[text] = slug
    return questions, about


def complete(root, stem, *, today, ports):
    """Settle `applications/<stem>`'s review: every flag answered and no FAIL against the
    match, then `j:state complete`. The caller holds the workspace's turn.

    Args:
        root: the workspace root.
        stem: the application's name.
        today: the day the match runs and the assessment is dated.
        ports: the bound ports (compose.native.Ports).

    Returns:
        The Reviewed; with a FAIL among its findings nothing was written.

    Raises:
        Refused: as review does.
    """
    from .check_gaps import review_of

    app, store = opened(root, stem, ports)
    overlay, done = review_of(store, app.rel)
    return folded(app, store, overlay, "complete", [], today, ports,
                  "complete" if done else "draft")


def opened(root, stem, ports):
    """(App, the loaded workspace) for a graph-native application whose posting is complete
    and which was not sent.

    Raises:
        Refused: anything else.
    """
    app = N.app_of(root, stem)
    store = N.loaded(app, ports)
    N.native(store, app, ports, posting="complete")
    N.refuse_if_frozen(app, store, ports)
    return app, store


def folded(app, store, overlay, state, found, today, ports, prior):
    """Check `overlay` against the match, then write it as the review at `state` with the
    gaps graph it folds into, in one update.

    Args:
        app: the App.
        store: the workspace, loaded inside the turn.
        overlay: the review's Overlay as it is to be.
        state: draft, or complete - which FAILs a flag the review has not answered.
        found: the findings so far.
        today: the day the match runs and the assessment is dated.
        ports: the bound ports (compose.native.Ports).
        prior: the review's state before, which stands when nothing is written.

    Returns:
        The Reviewed.
    """
    from ...domain.assessment.review import triples
    from .assessment import matched
    from .check_gaps import native_assessed, native_triples

    _, derived = matched(store, app, today, ports)
    a, more = native_assessed(store, app.rel, derived, overlay, state == "complete")
    found = list(found) + list(more)
    if a is None:
        return Reviewed(None, prior, None, N.clean(found), ())
    names, broken = N.write(app, store, {"review": triples(overlay, app.ids, state),
                                         "gaps": native_triples(store, app.rel, a, today)},
                            ports)
    if broken:
        return Reviewed(None, prior, None, N.clean(found + broken), ())
    return Reviewed(app.graph("review"), state, a.fit, N.clean(found), tuple(names))
