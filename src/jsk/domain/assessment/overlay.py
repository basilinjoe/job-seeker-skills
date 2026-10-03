"""The analyst's overlay on the assessment the match already derived: a lowered verdict with
its reason, a flagged row kept, fit, eligibility, what falls short, surplus and the
questions. Code folds it in (domain/assessment/fold.py) and writes the assessment's graph.

A graph-native application's overlay is its review graph, read into an Overlay by
domain/assessment/review.py and changed through `assessment_review`, which checks each row
it is sent (application/tailor/review.py). Until 6.0 it was also read from an application's
gaps.txt (`parse`, `jsk tailor match --gaps`); that file and its verb retired with the
file-made pipeline (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2).
"""
from dataclasses import dataclass, field

# An unfilled slot of the gaps.txt drafts 5.x wrote; fold.py still FAILs one wherever it
# finds it, so the mark is named once, here.
MARK = "<!-- jsk:"


@dataclass(frozen=True)
class Row:
    line: int               # the row's position in the review, for messages
    slug: str               # req_<posting stem>_<slug>
    verdict: str            # keep, or a verdict name
    reason: str = ""        # becomes j:shortfall; "" when absent


@dataclass
class Overlay:
    """The review as read: the keyed values and the rows, each in the order given."""

    fit: str | None = None
    eligibility: str | None = None
    rows: list = field(default_factory=list)
    short: list = field(default_factory=list)
    surplus: list = field(default_factory=list)
    ask: list = field(default_factory=list)
    # {question: the requirement's slug} for an ask about one requirement. The review graph
    # keeps it as the item's j:about (Ruling 4), so the question's j:Ask carries the
    # requirement and its concepts and counts in `repeated`.
    about: dict = field(default_factory=dict)
