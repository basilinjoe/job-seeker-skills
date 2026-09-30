"""The gaps.txt draft's old path, and the files it reads: posting.md's lines and
decisions.txt's drops.

The draft's text is domain/assessment/draft.py's and the reads around it
application/tailor/draft_gaps.py's; `draft_gaps` keeps today's signature and hands the use
case the real folder (graph.gapsbuild.Folder).
"""
from ..domain.assessment.draft import CUT as CUT
from ..domain.assessment.draft import HEAD as HEAD
from ..domain.assessment.draft import cut as cut
from ..domain.assessment.draft import one_line as one_line
from ..domain.assessment.draft import slot as slot
from ..domain.assessment.overlay import MARK as MARK


def advert(path):
    """posting.md's lines, as advert_lines numbers them; none when there is no posting.md.
    io.Unreadable propagates for one that is there and cannot be read."""
    from ..infra.files import Missing, read_text
    from ..domain.posting.advert import advert_lines

    try:
        return advert_lines(read_text(path, "posting.md"))
    except Missing:
        return []


def drops(post_dir):
    """decisions.txt's drops, or none for a posting written before decisions.txt existed.
    DecisionsError and io.Unreadable propagate: a file `jsk posting build` would refuse is
    not guessed at."""
    import os

    from . import decisions as D
    from ..infra.files import Missing

    try:
        return D.read(os.path.join(post_dir, "decisions.txt"), "decisions.txt").drops
    except Missing:
        return []


def draft_gaps(derived, store, advert_path):
    """gaps.txt for the Derived assessment `derived`, with a slot wherever judgement is
    needed (application.tailor.draft_gaps.draft_gaps over graph.gapsbuild.Folder)."""
    from ..application.tailor.draft_gaps import draft_gaps as drafted
    from .gapsbuild import Folder

    return drafted(derived, store, advert_path, folder=Folder())
