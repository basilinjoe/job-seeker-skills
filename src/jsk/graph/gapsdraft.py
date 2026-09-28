"""The gaps.txt draft `jsk match --draft-gaps` writes: only what needs the analyst's judgement,
each as a `<!-- jsk: ... -->` slot, with everything else left to the derived assessment.

On the three fast-tailor runs the analyst kept the match's verdict on all but seven rows, so
the draft lists only the rows the review flag fired on; gaps.md shows the rest with their
evidence, and the analyst lowers one by adding a row. `--gaps` FAILs on any slot left
unfilled.

gapsbuild renders gaps.md; gapsderive derives the verdicts, the evidence and the questions.
"""
import os

from .assessment import MARK

CUT = 80


def slot(text):
    return f"{MARK} {text} -->"


def advert(path):
    """posting.md's lines, as advert_lines numbers them; none when there is no posting.md.
    io.Unreadable propagates for one that is there and cannot be read."""
    from .io import Missing, read_text
    from .rules import advert_lines

    try:
        return advert_lines(read_text(path, "posting.md"))
    except Missing:
        return []


def drops(post_dir):
    """decisions.txt's drops, or none for a posting written before decisions.txt existed.
    DecisionsError and io.Unreadable propagate: a file `jsk posting build` would refuse is
    not guessed at."""
    from . import decisions as D
    from .io import Missing

    try:
        return D.read(os.path.join(post_dir, "decisions.txt"), "decisions.txt").drops
    except Missing:
        return []


def cut(text):
    if len(text) <= CUT:
        return text
    return text[:CUT].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def eligibility(store, lines):
    """The person's facts and the advert's eligibility lines, as `#` comments over the slot:
    what the analyst judges against, kept out of the value it writes."""
    from .named import person

    _, rows = person(store)
    facts = [f"#   {r['fact']}: {r['value']}" + (f" ({r['provenance']})" if r["provenance"]
                                                 else "") for r in rows]
    elig = [f'#   advert: "{x.text}"' for x in lines if x.elig] or \
        ["#   advert: nothing it says is about eligibility"]
    return ["# eligibility is judged against:", *facts, *elig,
            f"eligibility: {slot('judge eligibility against the facts above')}"]


HEAD = [
    "# gaps.txt - your overlay on the assessment jsk derived from the match.",
    "# `jsk match <posting.ttl> --gaps <this file>` checks it and writes gaps.ttl and gaps.md.",
    "# A requirement not listed keeps the match's verdict (gaps.md shows each, with its evidence).",
    "# A row is `slug | verdict | reason`: it lowers a verdict, never raises one.",
]


def dropped(post_dir, lines):
    """decisions.txt's drops as comments, so the analyst sees what the posting left out."""
    by_n = {x.n: x.text for x in lines}
    return [f"# dropped advert line {d.n}: {cut(by_n.get(d.n, '(not in posting.md)'))} - "
            f"{d.reason}" for d in drops(post_dir)]


def draft_gaps(derived, store, advert_path):
    """gaps.txt for the Derived assessment `derived`, with a slot wherever judgement is
    needed: eligibility, each flagged row, the shortfall, the surplus, a blocking question."""
    lines = advert(advert_path)
    # `/`, not `|`, inside the verdict slot: the row itself splits on `|`.
    review = slot("keep, or lower: partial / unevidenced / unsatisfied")
    rows = []
    for row in derived.rows:
        if row.flags:
            rows += [f"# {one_line(row.asked)}: {one_line(row.flag_text or ', '.join(row.flags))}",
                     f"{row.slug} | {review} |", ""]
    out = [*HEAD, *dropped(os.path.dirname(os.path.abspath(advert_path)), lines), "",
           f"fit: {derived.fit}", "",
           *eligibility(store, lines), "",
           *rows,
           "short: " + slot("the unmet and partial requirements that matter, most load-bearing "
                            "first"),
           f"surplus: {slot('optional - delete this line if there is none')}", "",
           f"ask: {slot('blocking: an eligibility question, or delete this line')}",
           *(f"ask: {one_line(q)}" for q in derived.questions),
           "# reword each ask to be said aloud; add from jsk kb query unconfirmed"]
    return "\n".join(out) + "\n"


def one_line(text):
    """gaps.txt is read a line at a time: a newline inside a value would start a new one."""
    return " ".join(text.split())
