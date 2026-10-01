"""The gaps.txt draft `jsk tailor match --draft-gaps` and `jsk tailor prepare --draft-gaps` write:
the advert, the drops and the person read, the draft built (domain/assessment/draft.py),
and - for --draft-gaps - the assessment written from the match alone first. It prints
nothing; the commands say what was written.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Drafted:
    """What `jsk tailor match --draft-gaps` did: the assessment's build, and the draft if written."""

    written: list               # the gaps graph and gaps.md, as check_gaps.build names them
    found: list                 # check_gaps.build's (severity, text, fix) findings
    path: str | None            # the gaps.txt written, or None when the build FAILed
    slots: int                  # the slots in it left to fill


def draft_gaps(derived, store, advert_path, *, folder):
    """gaps.txt for the Derived assessment `derived`, with a slot wherever judgement is needed.

    Args:
        derived: the Derived assessment.
        store: the loaded workspace, whose person's facts the eligibility slot shows.
        advert_path: the application's posting.md; decisions.txt is read beside it.
        folder: the application's folder and record (compose.tailor.Folder).

    Returns:
        The draft's text.

    Raises:
        Unreadable: posting.md is there and cannot be read.
        DecisionsError: decisions.txt does not parse.
    """
    from ...domain.assessment.draft import draft_text

    lines = folder.advert(advert_path)
    drops = folder.drops(os.path.dirname(os.path.abspath(advert_path)))
    _, rows = folder.person(store)
    return draft_text(derived, rows, lines, drops)


def draft_over_match(report, app, today, path, *, folder):
    """--draft-gaps: the assessment from the match alone, then gaps.txt drafted over it.

    Args:
        report: the MatchReport (application.tailor.match_posting).
        app: the application's directory.
        today: the day the assessment is dated.
        path: the gaps.txt to create; the caller has checked it is not there.
        folder: the application's folder and record (compose.tailor.Folder).

    Returns:
        The Drafted. Writes the gaps graph, gaps.md and, when the build found no FAIL, `path`.
    """
    from ...domain.assessment.draft import slot_count
    from .check_gaps import build

    r, store = report.result, report.store
    derived = folder.derive(r, store)
    written, found = build(app, store, r, today, derived, folder=folder)
    if any(s == "FAIL" for s, _, _ in found):
        return Drafted(written, found, None, 0)
    text = draft_gaps(derived, store, os.path.join(app, "posting.md"), folder=folder)
    folder.create(path, text)
    return Drafted(written, found, path, slot_count(text))
