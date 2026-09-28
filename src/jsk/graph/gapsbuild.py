"""gaps.ttl and gaps.md: the derived assessment with the analyst's gaps.txt folded in.

gaps.txt is the only file a model edits, and it holds only what the match cannot know: a
lowered verdict with its reason, a flagged row kept or lowered, eligibility, fit, and the
prose. Everything else is `gapsderive.derive`. This checks the overlay against the match,
then writes gaps.ttl - loaded with the workspace, so SPARQL reaches it - and renders gaps.md
from the two. Nothing reads gaps.md back.

Both are rebuilt on every run from the career as it stands, so there is no stale copy to
warn about; once application.ttl records the day it was sent, both are left as they were,
because a sent assessment is what it said at the time.
"""
import datetime
import os
from dataclasses import dataclass

from .assessment import MARK

HEADER = "<!-- written by jsk from gaps.ttl - edit gaps.txt, not this -->"
KEPT = "kept after review"
UNREVIEWED = "flagged, not yet reviewed"


@dataclass(frozen=True)
class Verdict:
    row: object             # gapsderive.Row
    verdict: str            # the verdict that stands
    shortfall: str | None   # the analyst's reason, when it lowered one
    kept: bool              # a flagged row the analyst answered `keep`


@dataclass(frozen=True)
class Assessment:
    derived: object         # gapsderive.Derived
    fit: str
    eligibility: str | None
    verdicts: tuple         # Verdict, in the match's order
    short: tuple
    surplus: tuple
    questions: tuple


def standing(row):
    """The verdict a row keeps when gaps.txt says nothing of it. An implicit requirement
    is not assessed, which is indeterminate - about the record, not the candidate."""
    return row.matched or "indeterminate"


def raises(said, matched):
    """Would `said` claim more than the match? Against `indeterminate`, a satisfied or a
    partial does; `indeterminate` itself claims nothing; against an implicit row nothing is
    a raise, because the match did not assess it."""
    from .match import RANK

    if matched is None or said == "indeterminate":
        return False
    if matched == "indeterminate":
        return said in ("satisfied", "partial")
    return RANK[said] > RANK[matched]


def slots(text):
    """(line, text) for each line of gaps.txt still holding a slot."""
    return [(n, line) for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1)
            if MARK in line]


def outcome(o, row, was, rows):
    """The one (severity, text, fix) gaps.txt row `o` gets against the match's `row`, or
    None. `was` is the match's verdict when gaps.ttl was last written; `rows` names the
    requirements when `row` is None.

    One case per return, in the order of the 2026-09-28 review's Ruling 7. A chain of
    `if`s that each appended let two findings fire for one row, and let the order decide
    which: `keep` on a row whose flag the career had since cleared FAILed, and a row
    restating the match FAILed "no reason" beside its "delete the row". Neither changes
    what `fold` writes - both are the match's verdict there - so each warns.
    """
    from .match import RAISE_FIX

    where = f"gaps.txt line {o.line}"
    if row is None:
        return ("FAIL", f"{where}: {o.slug!r} is not a requirement of this posting",
                "name it as posting.ttl's req_<stem>_<slug> does - "
                + ", ".join(sorted(rows))[:200])
    if MARK in o.verdict:
        return None                                     # the slot FAIL names it
    if o.verdict == "keep":
        if row.flags:
            return None
        return ("WARN", f"{where}: `keep` on {o.slug}, which no flag asks about now",
                "delete the row - an unlisted requirement keeps the match's verdict")
    if o.verdict == standing(row):
        return ("WARN", f"{where}: {o.slug} says {o.verdict}, which is the match's verdict "
                "already", "delete the row")
    if raises(o.verdict, row.matched):
        if was is not None and not raises(o.verdict, was):
            return ("WARN", f"{where}: the match now says {row.matched}; the row lowers "
                    "nothing - delete it", "the match's verdict stands")
        return ("FAIL", f"{where}: {o.slug}: {o.verdict}, above the match's {row.matched}",
                RAISE_FIX)
    if not o.reason:
        return ("FAIL", f"{where}: {o.slug} is lowered to {o.verdict} with no reason",
                "say why, after a second `|` - it becomes the Shortfall")
    # An implicit row has no j:matched, so gaps.ttl never recorded a `was` for it.
    if row.matched is not None and was is not None and raises(row.matched, was):
        return ("WARN", f"{where}: the match now says {row.matched}; you lowered it to "
                f"{o.verdict} because {o.reason} - still true?",
                "keep the row if it is, or delete it")
    return None


def check(derived, overlay, text="", previous=None, reviewed=True):
    """(severity, text, fix) for each way gaps.txt leaves the match. `previous` is
    {slug: the match's verdict when gaps.ttl was last written}: a row that lowered a verdict
    the match has since moved is named, not failed, because the career moved, not the row.
    `reviewed` is False when there is no gaps.txt at all: a flagged row waits for the analyst
    then, and the derived assessment is still written - that is the path with no agent.
    Each row gets at most one finding, from `outcome`."""
    previous = previous or {}
    out = [("FAIL", f"gaps.txt line {n}: unfilled slot", "fill it, or delete the line")
           for n, _ in slots(text)]
    rows = {r.slug: r for r in derived.rows}
    said = {}
    for o in overlay.rows:
        if o.slug in rows:
            said[o.slug] = o
        found = outcome(o, rows.get(o.slug), previous.get(o.slug), rows)
        if found:
            out.append(found)
    for row in derived.rows if reviewed else ():
        if row.flags and row.slug not in said:
            out.append(("FAIL", f"{row.slug} is flagged ({row.flag_text}) and gaps.txt has no "
                        f"row for it", f"add `{row.slug} | keep` or lower it with a reason"))
    return out


def fold(derived, overlay, previous=None):
    """The verdicts that stand. Call after `check` found no FAIL."""
    previous = previous or {}
    said = {o.slug: o for o in overlay.rows}
    verdicts = []
    for row in derived.rows:
        o = said.get(row.slug)
        if o is None or o.verdict == "keep" or MARK in o.verdict or raises(o.verdict, row.matched):
            # A row the match has moved below is the match's now (check WARNed).
            verdicts.append(Verdict(row, standing(row), None, o is not None and o.verdict == "keep"))
        else:
            verdicts.append(Verdict(row, o.verdict, o.reason or None, False))
    return Assessment(derived, overlay.fit or derived.fit, overlay.eligibility, tuple(verdicts),
                      tuple(overlay.short), tuple(overlay.surplus),
                      tuple(overlay.ask) or derived.questions)


def triples(a, today):
    """gaps.ttl's triples. Ids are derived: k:gap_<stem>, and k:vrd_<stem>_<slug> for
    k:req_<stem>_<slug> - never chosen, so a rebuild writes the same file."""
    import pyoxigraph as ox

    from . import ontology as O

    def j(name):
        return ox.NamedNode(O.J + name)

    def k(curie):
        return ox.NamedNode(O.K + curie.split(":", 1)[1])

    d = a.derived
    gap = ox.NamedNode(f"{O.K}gap_{d.stem}")
    out = [ox.Triple(gap, j("posting"), k(d.posting)),
           ox.Triple(gap, j("assessed"), ox.Literal(today.isoformat(),
                                                    datatype=ox.NamedNode(O.XSD + "date"))),
           ox.Triple(gap, j("fit"), j(a.fit))]
    if a.eligibility:
        out.append(ox.Triple(gap, j("eligibility"), ox.Literal(a.eligibility)))
    for pred, items in (("fallsShort", a.short), ("surplus", a.surplus),
                        ("questions", a.questions)):
        if items:
            out.append(ox.Triple(gap, j(pred), ox.Literal("\n".join(items))))
    for v in a.verdicts:
        row = v.row
        s = ox.NamedNode(f"{O.K}vrd_{d.stem}_{row.slug}")
        out += [ox.Triple(s, j("assessment"), gap), ox.Triple(s, j("requirement"), k(row.id)),
                ox.Triple(s, j("verdict"), j(v.verdict)),
                ox.Triple(s, j("basis"), ox.Literal(row.basis))]
        if row.matched:
            out.append(ox.Triple(s, j("matched"), j(row.matched)))
        out += [ox.Triple(s, j("flag"), j(f)) for f in row.flags]
        out += [ox.Triple(s, j("evidence"), k(p)) for p in row.evidence]
        if v.shortfall:
            out.append(ox.Triple(s, j("shortfall"), ox.Literal(v.shortfall)))
    return out


# --- gaps.md ---------------------------------------------------------------------------

def bare(curie):
    """`prj_x` for `k:prj_x`: the id as the analyst and the author cite it."""
    return curie.removeprefix("k:")


def cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


def cut(text, n=80):
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
    by_n = {x.n: x.text for x in lines}
    out = [f"- **{q['asked']}** — candidate: no concept holds it."
           for q in r["requirements"] if q["state"] == "candidate"]
    # An eligibility drop is judged under # Eligibility, not offered as a term.
    out += [f"- **{cut(by_n.get(d.n, f'advert line {d.n}'))}** — dropped: {d.reason}"
            for d in dropped if not d.reason.lower().startswith("elig")]
    return out or ["None."]


def requirement_rows(a):
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
    """gaps.md: what the person reads, from the assessment and the match."""
    from .match import cover_lines, ranking_lines

    out = ["---", "type: Gap Assessment", "posting: posting.ttl",
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


# --- the build -------------------------------------------------------------------------

def previous_verdicts(store, app_rel, stem):
    """{slug: j:matched} from the gaps.ttl being replaced - the verdict id's local part
    after `vrd_<stem>_`, which is the requirement's slug."""
    from . import ontology as O

    parsed = store.parsed.get(f"{app_rel}/gaps.ttl")
    head = f"{O.K}vrd_{stem}_"
    return {q.subject.value[len(head):]: q.object.value[len(O.J):]
            for q in (parsed.quads if parsed else ())
            if q.predicate.value == O.J + "matched" and q.subject.value.startswith(head)}


def assessed(store, app_rel):
    """The day the gaps.ttl being replaced was made, or None."""
    from . import ontology as O

    parsed = store.parsed.get(f"{app_rel}/gaps.ttl")
    for q in parsed.quads if parsed else ():
        if q.predicate.value == O.J + "assessed":
            return datetime.date.fromisoformat(q.object.value)
    return None


def build(app_dir, store, r, today, derived=None):
    """Write gaps.ttl and gaps.md for the match `r` of the posting in `app_dir`.
    Returns (paths written, findings). On a FAIL nothing is written; with no gaps.txt the
    derived assessment is written alone - the path that needs no agent."""
    from . import assessment as A
    from . import decisions as D
    from . import store as S
    from .gapsderive import derive
    from .gapsdraft import advert, drops
    from .io import GraphError, Missing, Unreadable, read_text
    from .timeline import Frozen, sent_day, write_app_file
    from .writer import WriteError, write

    app_rel = S.file_name(os.path.abspath(app_dir), store.root)
    try:
        day = sent_day(app_dir)
    except GraphError as e:
        return [], [("FAIL", f"{app_rel}/application.ttl: {e}", e.fix)]
    if day:
        return [], [("FAIL", f"{app_rel}: sent on {day} - gaps.ttl and gaps.md are frozen",
                     "a sent assessment is what it said at the time; nothing to rebuild")]
    derived = derived or derive(r, store)
    try:
        text, reviewed = read_text(os.path.join(app_dir, "gaps.txt"), "gaps.txt"), True
    except Missing:
        text, reviewed = "", False
    except Unreadable as e:
        return [], [("FAIL", str(e), e.fix)]
    try:
        overlay = A.parse(text)
    except A.AssessmentError as e:
        return [], [("FAIL", f"gaps.txt: {e}", "correct that line")]
    previous = previous_verdicts(store, app_rel, derived.stem)
    found = check(derived, overlay, text, previous, reviewed)
    if any(s == "FAIL" for s, _, _ in found):
        return [], found
    a = fold(derived, overlay, previous)
    # An assessment that has not changed keeps the day it was made: re-running prepare
    # tomorrow must not rewrite the file for its date alone.
    try:
        before = assessed(store, app_rel)
        if before and write(triples(a, before), "gaps") == \
                store.parsed[f"{app_rel}/gaps.ttl"].text:
            today = before
        ttl_text = write(triples(a, today), "gaps")
    except WriteError as e:          # an id jsk would not write: a bug here, never a crash
        return [], found + [("FAIL", f"gaps.ttl: {e}", "report it - the assessment is derived, "
                             "so nothing in gaps.txt can cause it")]
    try:
        dropped = drops(app_dir)
        lines = advert(os.path.join(app_dir, "posting.md"))
    except D.DecisionsError as e:
        return [], found + [("FAIL", f"decisions.txt: {e}",
                             "correct that line; `jsk posting build` reads the same file")]
    except Unreadable as e:
        return [], found + [("FAIL", str(e), e.fix)]
    md_text = render(r, a, today, lines, dropped)
    written = []
    for name, body in (("gaps.ttl", ttl_text), ("gaps.md", md_text)):
        try:
            written.append(write_app_file(app_dir, name, body))
        except Frozen as e:         # sent between the check above and this write
            return written, found + [("FAIL", str(e), e.fix)]
    return written, found
