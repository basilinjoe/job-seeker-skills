"""The assessment's old path, and its binding: application/tailor/check_gaps.py over the
application's folder and record on disk.

The check and the fold are domain/assessment/fold.py's, gaps.md's text and the build
check_gaps.py's. This module keeps every name its callers and tests use, and `build` with
today's signature, handing the use case the real folder (Folder).
"""
from ..application.tailor.check_gaps import HEADER as HEADER
from ..application.tailor.check_gaps import KEPT as KEPT
from ..application.tailor.check_gaps import UNREVIEWED as UNREVIEWED
from ..application.tailor.check_gaps import bare as bare
from ..application.tailor.check_gaps import cell as cell
from ..application.tailor.check_gaps import cut as cut
from ..application.tailor.check_gaps import falls_short as falls_short
from ..application.tailor.check_gaps import new_terms as new_terms
from ..application.tailor.check_gaps import render as render
from ..application.tailor.check_gaps import requirement_rows as requirement_rows
from ..application.tailor.check_gaps import shown as shown
from ..domain.assessment.fold import Assessment as Assessment
from ..domain.assessment.fold import Verdict as Verdict
from ..domain.assessment.fold import assessed as assessed
from ..domain.assessment.fold import check as check
from ..domain.assessment.fold import fold as fold
from ..domain.assessment.fold import outcome as outcome
from ..domain.assessment.fold import previous_verdicts as previous_verdicts
from ..domain.assessment.fold import raises as raises
from ..domain.assessment.fold import same_triples as same_triples
from ..domain.assessment.fold import slots as slots
from ..domain.assessment.fold import standing as standing
from ..domain.assessment.fold import triples as triples
from ..domain.assessment.overlay import MARK as MARK


class Folder:
    """An application's folder and its record, as the assessment and the gaps.txt draft
    read and write them: the files on disk, the store through graph.timeline's writers."""

    def name_of(self, path, root):
        """`path` as findings name it (infra.files.file_name)."""
        from ..infra.files import file_name

        return file_name(path, root)

    def sent_day(self, app_dir, store):
        """The day the application was sent, or None (graph.timeline.sent_day).

        Raises:
            GraphError: whether it was sent cannot be read.
        """
        from .timeline import sent_day

        return sent_day(app_dir, store)

    def derive(self, r, store):
        """The Derived assessment for the match `r` (graph.gapsderive.derive)."""
        from .gapsderive import derive

        return derive(r, store)

    def read_text(self, path, what):
        """An authored file's text (infra.files.read_text).

        Raises:
            Missing, Unreadable: with the fix.
        """
        from ..infra.files import read_text

        return read_text(path, what)

    def drops(self, app_dir):
        """decisions.txt's drops, or none when there is no decisions.txt (gapsdraft.drops)."""
        from .gapsdraft import drops

        return drops(app_dir)

    def advert(self, path):
        """posting.md's numbered lines, or none when there is none (gapsdraft.advert)."""
        from .gapsdraft import advert

        return advert(path)

    def person(self, store):
        """(columns, rows) of the person's facts (application.record.queries.person)."""
        from ..application.record.queries import person

        return person(store)

    def write_graphs(self, app_dir, graphs, store):
        """Replace the application's graphs in one update (graph.timeline.write_app_graphs).

        Raises:
            Unwritable: nothing was written; Frozen when the application is sent.
        """
        from .timeline import write_app_graphs

        return write_app_graphs(app_dir, graphs, store)

    def write_file(self, app_dir, name, text, store):
        """Write the document `name` in the folder (graph.timeline.write_app_file).

        Raises:
            Unwritable: nothing was written; Frozen when the application is sent.
        """
        from .timeline import write_app_file

        return write_app_file(app_dir, name, text, store)

    def create(self, path, text):
        """Write `text` to a new file at `path`, failing if one is there.

        Raises:
            FileExistsError: `path` exists.
        """
        with open(path, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def build(app_dir, store, r, today, derived=None):
    """Write the assessment - the gaps graph and gaps.md - for the match `r` of the posting
    in `app_dir` (application.tailor.check_gaps.build over this folder). The caller holds
    its turn (record.turn) and loaded `store` inside it.

    Returns:
        (what was written, the findings). On a FAIL nothing is written.
    """
    from ..application.tailor.check_gaps import build as built

    return built(app_dir, store, r, today, derived, folder=Folder())
