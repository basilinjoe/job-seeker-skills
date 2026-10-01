"""The assessment: the derived assessment with the analyst's gaps.txt folded in.

gaps.txt is the only file a model edits, and it holds only what the match cannot know: a
lowered verdict with its reason, a flagged row kept or lowered, eligibility, fit, and the
prose. Everything else is derived (domain/assessment/derive.py). `build` checks the overlay
against the match (domain/assessment/fold.py), then writes the assessment as the
application's gaps graph - part of the record, so SPARQL reaches it - and renders it as text
for the person. No gaps.md is written (Ruling 24 of the graph-native plan): nothing read it
back. It prints nothing: `jsk tailor match --gaps` and `jsk tailor prepare` say what it found
and wrote, and print the rendered assessment.

It is rebuilt on every run from the career as it stands, so there is no stale copy to warn
about; once the application records the day it was sent, it is left as it was, because a
sent assessment is what it said at the time.

A graph-native application (Ruling 11 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md) has no gaps.txt and no
gaps.md: its overlay is the review graph (domain/assessment/review.py), its questions are
j:Ask nodes, and gaps.txt, decisions.txt and posting.md are never read for it (`native_*`,
which application/tailor/review.py and assessment.py share). The derivation takes the
career's confirmed "no"s for every application, file-built too (Ruling 9).
"""
import os

from ...domain.assessment.fold import standing
from .match_text import cover_lines, ranking_lines

HEADER = "<!-- written by jsk from the assessment - edit gaps.txt, not this -->"
KEPT = "kept after review"
UNREVIEWED = "flagged, not yet reviewed"


def bare(curie):
    """`prj_x` for `k:prj_x`: the id as the analyst and the author cite it."""
    return curie.removeprefix("k:")


def cell(text):
    """`text` as one gaps.md table cell: a `|` escaped, a newline a space."""
    return (text or "").replace("|", "\\|").replace("\n", " ")


def cut(text, n=80):
    """`text` cut at a word to at most `n` characters, an ellipsis marking the cut."""
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def falls_short(a):
    """The analyst's list, or - with no gaps.txt - the required requirements the verdicts
    leave short, in the match's order: the agent-free assessment still says where it is weak."""
    if a.short:
        return [f"- {x}" for x in a.short]
    out = [f"- **{v.row.asked}** ({v.row.necessity}): {v.verdict} - {v.row.basis}"
           for v in a.verdicts if v.row.necessity == "required" and v.verdict != "satisfied"]
    return out or ["Nothing required falls short."]


def new_terms(r, dropped, lines):
    """gaps.md's New terms: each candidate requirement, and each advert line
    decisions.txt dropped for a reason other than eligibility.

    Args:
        r: the match's plain data.
        dropped: decisions.txt's drops.
        lines: posting.md's numbered lines.

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
    """gaps.md's Requirements table for the Assessment `a`, one row a verdict."""
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
    """The assessment as the person reads it, from the assessment and the match - printed by
    `jsk tailor match --gaps`/`--draft-gaps` and `jsk tailor prepare`, never written to a file.

    Args:
        r: the match's plain data.
        a: the Assessment.
        today: the day it is dated.
        lines: posting.md's numbered lines.
        dropped: decisions.txt's drops.

    Returns:
        The assessment's text.
    """
    out = ["---", "type: Gap Assessment", f"posting: {a.derived.posting}",
           f"assessed: {today.isoformat()}", f"fit: {a.fit}", "---", HEADER, "",
           "# Eligibility", "",
           a.eligibility or "Not judged: gaps.txt has no `eligibility:` line.", "",
           "# Requirements", "", *requirement_rows(a), "",
           "# Ranking", "", *ranking_lines(r), "", *cover_lines(r), "",
           "# Where this falls short", "", *falls_short(a), ""]
    if a.surplus:
        out += ["# Surplus worth knowing about", "", *(f"- {x}" for x in a.surplus), ""]
    out += ["# New terms", "", *new_terms(r, dropped, lines), "",
            "# Questions", "", *([f"- {q}" for q in a.questions] or ["None."])]
    return "\n".join(out) + "\n"


def shown(written):
    """How a written thing is named in a report: a file by its name, a graph by its own."""
    return written if written.startswith("applications/") else os.path.basename(written)


def gaps_refusal(app, path, drafting):
    """Why `path` is not this application's gaps.txt, or None. No gaps.md is written now -
    `jsk tailor match` prints the assessment - and nothing reads one: a gaps.md is an older
    assessment.

    Args:
        app: the application's directory.
        path: the gaps.txt --gaps or --draft-gaps named.
        drafting: True for --draft-gaps, which refuses a file that exists.

    Returns:
        The refusal's two lines as one string, or None when `path` will do.
    """
    if path.endswith(".md"):
        return (f"FAIL  {path}: gaps.md is an older assessment, read by people only - jsk "
                f"prints the assessment now and reads no gaps.md\n"
                f"      fix: pass the application's gaps.txt - --draft-gaps drafts one")
    want = os.path.join(os.path.abspath(app), "gaps.txt")
    if os.path.normcase(os.path.abspath(path)) != os.path.normcase(want):
        return (f"FAIL  {path}: not this application's gaps.txt\n"
                f"      fix: pass {want}")
    if drafting and os.path.exists(path):
        # The analyst's filled slots are its judgement; a re-run must not wipe them.
        return (f"FAIL  {path} exists - the draft would overwrite it\n"
                f"      fix: check it with --gaps, or delete it to draft again")
    if not drafting and not os.path.isfile(path):
        return (f"FAIL  {path}: no such file\n"
                f"      fix: draft it with --draft-gaps, or let `jsk tailor prepare` write "
                f"the assessment alone")
    return None


def build(app_dir, store, r, today, derived, *, folder):
    """Write the assessment - the gaps graph - for the match `r` of the posting in `app_dir`,
    and render it for the person to read. On a FAIL nothing is written; with no gaps.txt the
    derived assessment is written alone - the path that needs no agent. No gaps.md is
    written (Ruling 24 of the graph-native plan): the caller prints the rendered text.

    Args:
        app_dir: the application's directory.
        store: the workspace, loaded inside the caller's turn (record.turn).
        r: match_posting.result's plain data for the posting.
        today: the day the assessment is dated, unless it has not changed.
        derived: the Derived assessment, or None to derive it from `r`.
        folder: the application's folder and record, as compose.tailor.Folder reads and
            writes them.

    Returns:
        (what was written - graph names -, the (severity, text, fix) findings, and the
        assessment rendered (render) or None when nothing was written). Writes the gaps
        graph.
    """
    from ...domain.assessment import overlay as A
    from ...domain.assessment.fold import assessed, check, fold, previous_verdicts
    from ...domain.assessment.fold import same_triples, triples
    from ...domain.naming import app_graph
    from ...domain.record.decisions import DecisionsError
    from ...domain.record.parsed import GraphError, Missing, Unreadable
    from ...domain.timeline.errors import Unwritable

    app_rel = folder.name_of(os.path.abspath(app_dir), store.root)
    gaps = app_graph(app_rel, "gaps")
    try:
        day = folder.sent_day(app_dir, store)
    except GraphError as e:
        return [], [("FAIL", f"{app_graph(app_rel, 'application')}: {e}", e.fix)], None
    if day:
        return [], [("FAIL", f"{app_rel}: sent on {day} - its assessment and gaps.md are "
                     "frozen", "a sent assessment is what it said at the time; nothing to "
                     "rebuild")], None
    derived = derived or folder.derive(r, store, today)
    if native_posting(store, derived):
        return native_build(app_dir, store, app_rel, r, derived, today, folder)
    try:
        text, reviewed = folder.read_text(os.path.join(app_dir, "gaps.txt"), "gaps.txt"), True
    except Missing:
        text, reviewed = "", False
    except Unreadable as e:
        return [], [("FAIL", str(e), e.fix)], None
    try:
        overlay = A.parse(text)
    except A.AssessmentError as e:
        return [], [("FAIL", f"gaps.txt: {e}", "correct that line")], None
    previous = previous_verdicts(store, app_rel, derived.stem)
    found = check(derived, overlay, text, previous, reviewed)
    if any(s == "FAIL" for s, _, _ in found):
        return [], found, None
    a = fold(derived, overlay, previous)
    # An assessment that has not changed keeps the day it was made: re-running prepare
    # tomorrow must not rewrite it for its date alone.
    before = assessed(store, app_rel)
    if before and same_triples(triples(a, before), store.graph(gaps)):
        today = before
    try:
        dropped = folder.drops(app_dir)
        lines = folder.advert(os.path.join(app_dir, "posting.md"))
    except DecisionsError as e:
        return [], found + [("FAIL", f"decisions.txt: {e}",
                             "correct that line; `jsk posting build` reads the same file")], None
    except Unreadable as e:
        return [], found + [("FAIL", str(e), e.fix)], None
    try:
        written = folder.write_graphs(app_dir, {"gaps": triples(a, today)}, store)
    except Unwritable as e:         # locked, or the store refused the write
        return [], found + [("FAIL", str(e), e.fix)], None
    return written, found, render(r, a, today, lines, dropped)


def native_posting(store, derived):
    """Whether the posting `derived` assesses is graph-native: its lines are in the store
    (Ruling 11 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md)."""
    from ...domain import ontology as O
    from ...domain.posting.lines import native

    return O.K + derived.posting.removeprefix("k:") in native(store)


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
    overlay checked against the match and folded in, as gaps.txt's is.

    Args:
        store: the loaded workspace.
        app_rel: the application, `applications/<dir>`.
        derived: the Derived assessment.
        overlay: the review's Overlay.
        reviewed: the review is complete, so a flag it has not answered FAILs; a draft's
            waits, as a missing gaps.txt's does.
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


def native_build(app_dir, store, app_rel, r, derived, today, folder):
    """(the graph names written, the findings, the assessment rendered or None), as build's,
    for a graph-native application: the overlay is the review graph's, never gaps.txt, and
    the assessment is the gaps graph alone - no gaps.md (Ruling 24). The rendered text takes
    the advert's lines and drops from the posting graph."""
    from ...domain import ontology as O
    from ...domain.posting.lines import lines_of
    from ...domain.record.decisions import Drop
    from ...domain.timeline.errors import Unwritable

    overlay, reviewed = review_of(store, app_rel)
    a, found = native_assessed(store, app_rel, derived, overlay, reviewed)
    if a is None:
        return [], found, None
    try:
        written = folder.write_graphs(app_dir, {"gaps": native_triples(store, app_rel, a,
                                                                       today)}, store)
    except Unwritable as e:
        return [], found + [("FAIL", str(e), e.fix)], None
    lines, drops = lines_of(store, O.K + derived.posting.removeprefix("k:"))
    # Drop's first field is decisions.txt's line number; a stored drop has none.
    dropped = [Drop(0, n, why) for n, why in sorted(drops.items())]
    return written, found, render(r, a, today, lines, dropped)
