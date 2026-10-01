"""The gaps.txt draft: only what needs the analyst's judgement, each as a `<!-- jsk: ... -->`
slot, with everything else left to the derived assessment.

On the three fast-tailor runs the analyst kept the match's verdict on all but seven rows, so
the draft lists only the rows the review flag fired on; the printed assessment shows the rest with their
evidence, and the analyst lowers one by adding a row. `--gaps` FAILs on any slot left
unfilled. The text is built here from what the caller read: the person's facts, posting.md's
lines and decisions.txt's drops (application/tailor/draft_gaps.py reads them).
"""
from .overlay import MARK

CUT = 80

HEAD = [
    "# gaps.txt - your overlay on the assessment jsk derived from the match.",
    "# `jsk tailor match <application> --gaps <this file>` checks it, then writes the assessment and prints it.",
    "# A requirement not listed keeps the match's verdict (the assessment shows each, with its evidence).",
    "# A row is `slug | verdict | reason`: it lowers a verdict, never raises one.",
]


def slot(text):
    """`text` as a slot the analyst fills: `<!-- jsk: text -->`."""
    return f"{MARK} {text} -->"


def slot_count(text):
    """How many lines of a drafted gaps.txt still hold a slot."""
    return sum(MARK in line for line in text.split("\n"))


def cut(text):
    """`text` cut at a word to at most CUT characters, an ellipsis marking the cut."""
    if len(text) <= CUT:
        return text
    return text[:CUT].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def one_line(text):
    """gaps.txt is read a line at a time: a newline inside a value would start a new one."""
    return " ".join(text.split())


def eligibility(rows, lines):
    """The person's facts and the advert's eligibility lines, as `#` comments over the slot:
    what the analyst judges against, kept out of the value it writes.

    Args:
        rows: the person's facts, each {fact, value, provenance} (application.record.queries.person).
        lines: posting.md's numbered lines (domain.posting.advert.advert_lines).

    Returns:
        The comment lines, then the `eligibility:` slot.
    """
    facts = [f"#   {r['fact']}: {r['value']}" + (f" ({r['provenance']})" if r["provenance"]
                                                 else "") for r in rows]
    elig = [f'#   advert: "{x.text}"' for x in lines if x.elig] or \
        ["#   advert: nothing it says is about eligibility"]
    return ["# eligibility is judged against:", *facts, *elig,
            f"eligibility: {slot('judge eligibility against the facts above')}"]


def dropped(drops, lines):
    """decisions.txt's drops as comments, so the analyst sees what the posting left out.

    Args:
        drops: decisions.txt's drops, each with its line number and reason.
        lines: posting.md's numbered lines.

    Returns:
        One comment line a drop.
    """
    by_n = {x.n: x.text for x in lines}
    return [f"# dropped advert line {d.n}: {cut(by_n.get(d.n, '(not in posting.md)'))} - "
            f"{d.reason}" for d in drops]


def draft_text(derived, rows, lines, drops):
    """gaps.txt for the Derived assessment `derived`, with a slot wherever judgement is
    needed: eligibility, each flagged row, the shortfall, the surplus, a blocking question.

    Args:
        derived: the Derived assessment (domain.assessment.derive).
        rows: the person's facts, as eligibility takes them.
        lines: posting.md's numbered lines.
        drops: decisions.txt's drops.

    Returns:
        The draft's text.
    """
    # `/`, not `|`, inside the verdict slot: the row itself splits on `|`.
    review = slot("keep, or lower: partial / unevidenced / unsatisfied")
    flagged = []
    for row in derived.rows:
        if row.flags:
            flagged += [f"# {one_line(row.asked)}: {one_line(row.flag_text or ', '.join(row.flags))}",
                        f"{row.slug} | {review} |", ""]
    out = [*HEAD, *dropped(drops, lines), "",
           f"fit: {derived.fit}", "",
           *eligibility(rows, lines), "",
           *flagged,
           "short: " + slot("the unmet and partial requirements that matter, most load-bearing "
                            "first"),
           f"surplus: {slot('optional - delete this line if there is none')}", "",
           f"ask: {slot('blocking: an eligibility question, or delete this line')}",
           *(f"ask: {one_line(q)}" for q in derived.questions),
           "# reword each ask to be said aloud; add from jsk kb query unconfirmed"]
    return "\n".join(out) + "\n"
