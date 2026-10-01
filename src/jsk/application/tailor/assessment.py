"""`assessment_derive`: a graph-native application's assessment, derived and written, and
returned as data.

`jsk tailor match --gaps` printed findings and wrote gaps.md for a person to read. A tool's
caller reads structure (Ruling 16 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md), so this returns the
match result, each requirement's row - the match's verdict, the one that stands after the
review, its evidence, why, and any flag - the fit and the questions. The derivation is
check_gaps' graph-native one: the review graph folded in, the career's confirmed "no"s
taken (Ruling 9), the gaps graph written with j:Ask nodes - and written through
application/posting/native.py's validated write, so a gaps graph that would newly break a
rule is a FAIL with nothing written (Ruling 14). The review is never written here, so it
survives every re-derivation (Ruling 4).

It refuses an application made from files, one with no posting, a draft posting, a frozen
application (sent or held back), and a workspace whose FAILs stop the match. It prints
nothing.
"""
from dataclasses import dataclass

from ...domain.posting.errors import Refused
from ..posting import native as N


@dataclass(frozen=True)
class Assessed:
    """One application's assessment, as data."""

    result: dict                # match_posting.result's plain data
    rows: tuple                 # a dict per requirement (row_of), in the match's order
    fit: str                    # the fit that stands: the review's, else the match's
    eligibility: str | None     # the review's judgement, when it gave one
    questions: tuple            # {position, question, requirement}: what to ask, in order
    short: tuple                # where it falls short, the review's own words
    surplus: tuple
    findings: tuple             # (severity, text, fix) from checking the review
    written: tuple              # the graph names written


def matched(store, app, today, ports, budget=N.COVER):
    """(the match's plain data, the Derived assessment) for the application's posting.

    Args:
        store: the loaded workspace.
        app: the App.
        today: the day recency and an absence's lapse are measured from.
        ports: the bound ports (compose.native.Ports).
        budget: the most projects the cover may use.

    Raises:
        Refused: a FAIL in the career, the vocabulary or this application stops the match.
    """
    from ...domain.matching.report import blocks
    from .match_posting import posting_in

    blocking = [f for f in store.fails() if blocks(f, app.rel + "/")]
    if blocking:
        raise Refused.every([(f"the match is stopped by a FAIL: {f.text()}",
                              "fix:  `jsk kb check` shows it; correct it first")
                             for f in blocking])
    post = posting_in(store, app.rel)
    r = ports.match(store, post, today, budget, len(store.fails()) - len(blocking))
    return r, ports.derive(r, store, today)


def row_of(row, verdict=None, shortfall=None, kept=False):
    """One requirement's row as data: a derive.Row, and the verdict that stands on it.

    Args:
        row: the derive.Row.
        verdict: the verdict that stands; the match's (fold.standing) when None.
        shortfall: the review's reason, when it lowered the verdict.
        kept: a flag the review answered `keep`.
    """
    from ...domain.assessment.fold import standing

    return {"slug": row.slug, "asked": row.asked, "necessity": row.necessity,
            "state": row.state, "matched": row.matched, "verdict": verdict or standing(row),
            "evidence": [e.removeprefix("k:") for e in row.evidence], "basis": row.basis,
            "flags": list(row.flags), "flag_text": row.flag_text, "shortfall": shortfall,
            "kept": kept, "concepts": list(row.concepts)}


def questions_of(questions, derived, asks=()):
    """{position, question, requirement slug or None} for each of `questions`, as the j:Ask
    nodes hold them: one the match derived knows its requirement, one the review wrote
    knows the one its `about` named (`asks`, Assessment.asks), or none."""
    about = dict(asks or derived.asks)
    slugs = {row.id: row.slug for row in derived.rows}
    return tuple({"position": i, "question": q, "requirement": slugs.get(about.get(q))}
                 for i, q in enumerate(questions, 1))


def derive_assessment(root, stem, *, today, ports):
    """Match `applications/<stem>`'s posting, derive the assessment, fold the stored review
    in and write the gaps graph. The caller holds the workspace's turn.

    Args:
        root: the workspace root.
        stem: the application's name.
        today: the day it is derived, and absences measured.
        ports: the bound ports (compose.native.Ports).

    Returns:
        The Assessed. With a FAIL among its findings - a review the match has moved under -
        the gaps graph is not written, and the rows are the match's.

    Raises:
        Refused: a legacy application, no posting, a draft one, a frozen application, or a
            FAIL that stops the match.
    """
    from .check_gaps import native_assessed, native_triples, review_of

    app = N.app_of(root, stem)
    store = N.loaded(app, ports)
    N.native(store, app, ports, posting="complete")
    N.refuse_if_frozen(app, store, ports)
    r, derived = matched(store, app, today, ports)
    overlay, reviewed = review_of(store, app.rel)
    a, found = native_assessed(store, app.rel, derived, overlay, reviewed)
    if a is None:
        return assessed(r, derived, None, found, ())
    # Through N.write, as every other graph-native writer: the workspace loaded with the
    # candidate gaps graph standing in, and anything it newly breaks refused with nothing
    # written (Ruling 14). check_gaps.build wrote it unvalidated until 2026-10-02.
    written, broken = N.write(app, store, {"gaps": native_triples(store, app.rel, a, today)},
                              ports)
    if broken:
        return assessed(r, derived, None, list(found) + broken, ())
    return assessed(r, derived, a, found, written)


def assessed(r, derived, a, found, written):
    """The Assessed for the match `r`, its Derived, and the Assessment folded from it - or
    None when the review did not fold, when the rows are the match's alone."""
    if a is None:
        return Assessed(r, tuple(row_of(row) for row in derived.rows), derived.fit, None,
                        questions_of(derived.questions, derived), (), (), N.clean(found),
                        tuple(written))
    return Assessed(r, tuple(row_of(v.row, v.verdict, v.shortfall, v.kept) for v in a.verdicts),
                    a.fit, a.eligibility, questions_of(a.questions, derived, a.asks),
                    tuple(a.short),
                    tuple(a.surplus), N.clean(found), tuple(written))
