"""The analyst's gaps.txt checked against the derived assessment and folded into it,
and the assessment as the gaps graph's triples.

gaps.txt holds only what the match cannot know: a lowered verdict with its reason, a
flagged row kept or lowered, eligibility, fit, and the prose. `check` gives each row one
outcome against the match; `fold` gives the verdicts that stand. Nothing here reads a
file: application/tailor/check_gaps.py reads gaps.txt and writes what this builds.
"""
import datetime
from dataclasses import dataclass

from .overlay import MARK

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
    from .verdict import RANK

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
    None. `was` is the match's verdict when the assessment was last written; `rows` names the
    requirements when `row` is None.

    One case per return, in the order of the 2026-09-28 review's Ruling 7. A chain of
    `if`s that each appended let two findings fire for one row, and let the order decide
    which: `keep` on a row whose flag the career had since cleared FAILed, and a row
    restating the match FAILed "no reason" beside its "delete the row". Neither changes
    what `fold` writes - both are the match's verdict there - so each warns.
    """
    from .verdict import RAISE_FIX

    where = f"gaps.txt line {o.line}"
    if row is None:
        return ("FAIL", f"{where}: {o.slug!r} is not a requirement of this posting",
                "name it as the posting's req_<stem>_<slug> does - "
                + ", ".join(sorted(rows))[:200])
    if MARK in o.verdict:
        return None                                     # the slot FAIL names it
    if o.verdict == "keep":
        if row.flags:
            return None
        return ("WARN", f"{where}: `keep` on {o.slug}, which no flag asks about now",
                "delete the row - an unlisted requirement keeps the match's verdict")
    if o.verdict == standing(row):
        if row.flags:
            return None                                 # an answer to the flag, as `keep` is
        return ("WARN", f"{where}: {o.slug} says {o.verdict}, which is the match's verdict "
                "already", "delete the row")
    if raises(o.verdict, row.matched):
        if was is not None and not raises(o.verdict, was):
            # A flagged row cannot just go: with no row the flag FAILs, so it is asked again.
            return ("WARN", f"{where}: the match now says {row.matched}; the row lowers "
                    "nothing - delete it", f"answer the flag again: `{o.slug} | keep`, or "
                    "lower it with a reason" if row.flags else "the match's verdict stands")
        return ("FAIL", f"{where}: {o.slug}: {o.verdict}, above the match's {row.matched}",
                RAISE_FIX)
    if not o.reason:
        return ("FAIL", f"{where}: {o.slug} is lowered to {o.verdict} with no reason",
                "say why, after a second `|` - it becomes the Shortfall")
    # An implicit row has no j:matched, so the assessment never recorded a `was` for it.
    if row.matched is not None and was is not None and raises(row.matched, was):
        return ("WARN", f"{where}: the match now says {row.matched}; you lowered it to "
                f"{o.verdict} because {o.reason} - still true?",
                f"keep the row if it is, or make it `{o.slug} | keep`" if row.flags
                else "keep the row if it is, or delete it")
    return None


def check(derived, overlay, text="", previous=None, reviewed=True):
    """(severity, text, fix) for each way gaps.txt leaves the match. `previous` is
    {slug: the match's verdict when the assessment was last written}: a row that lowered a verdict
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
        # Kept after review: a flag answered with `keep`, or with the match's own verdict
        # and no reason. Only a flag is kept - an unflagged `keep` changes nothing.
        answered = o is not None and bool(row.flags) and (
            o.verdict == "keep" or (o.verdict == standing(row) and not o.reason))
        if o is None or o.verdict == "keep" or MARK in o.verdict or raises(o.verdict, row.matched):
            # A row the match has moved below is the match's now (check WARNed).
            verdicts.append(Verdict(row, standing(row), None, answered))
        else:
            verdicts.append(Verdict(row, o.verdict, o.reason or None, answered))
    return Assessment(derived, overlay.fit or derived.fit, overlay.eligibility, tuple(verdicts),
                      tuple(overlay.short), tuple(overlay.surplus),
                      tuple(overlay.ask) or derived.questions)


def triples(a, today):
    """The assessment graph's triples. Ids are derived: k:gap_<stem>, and k:vrd_<stem>_<slug> for
    k:req_<stem>_<slug> - never chosen, so a rebuild writes the same file."""
    import pyoxigraph as ox

    from .. import ontology as O

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


def previous_verdicts(store, app_rel, stem):
    """{slug: j:matched} from the assessment being replaced - the verdict id's local part
    after `vrd_<stem>_`, which is the requirement's slug."""
    from .. import ontology as O
    from ..naming import app_graph

    parsed = store.parsed.get(app_graph(app_rel, "gaps"))
    head = f"{O.K}vrd_{stem}_"
    return {q.subject.value[len(head):]: q.object.value[len(O.J):]
            for q in (parsed.quads if parsed else ())
            if q.predicate.value == O.J + "matched" and q.subject.value.startswith(head)}


def assessed(store, app_rel):
    """The day the assessment being replaced was made, or None."""
    from .. import ontology as O
    from ..naming import app_graph

    parsed = store.parsed.get(app_graph(app_rel, "gaps"))
    for q in parsed.quads if parsed else ():
        if q.predicate.value == O.J + "assessed":
            return datetime.date.fromisoformat(q.object.value)
    return None


def same_triples(a, b):
    """Do two graphs hold the same triples? Compared as (s, p, o), since one side may be
    Quads out of a store and the other Triples just built."""
    return {(t.subject, t.predicate, t.object) for t in a} == \
        {(t.subject, t.predicate, t.object) for t in b}
