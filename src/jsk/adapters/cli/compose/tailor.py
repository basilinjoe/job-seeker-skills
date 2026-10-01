"""The tailoring commands' ports, bound: what `jsk tailor prepare` and `jsk tailor match`
hand their use cases.

Each binding is built inside the call that needs it (Ruling 6 of the onion design): nothing
here reads the record or the disk at import.
"""


def short_file(store, selection=None, select=None, notes=None):
    """The short resume.json for a selection (application.tailor.export.short_file), the
    region profiles that ship read from data/.

    Args:
        store: a loaded workspace.
        selection: the Selection for a posting or by rank, or None.
        select: the ids --select named, or None.
        notes: a list the NOTE lines are appended to, or None.

    Returns:
        The short file as a dict.

    Raises:
        ExportError: a `select` it cannot honour, or a selection holding no bullet.
    """
    from ....application.tailor.export import short_file as formed
    from ....infra.profiles import ships

    return formed(store, selection, select, notes, ships=ships)


def read_assessment(path):
    """Read the gaps.txt at `path` and parse it (domain.assessment.overlay.parse).

    Args:
        path: the gaps file.

    Returns:
        Overlay: the analyst's overlay the file holds.

    Raises:
        Missing: when there is no file at `path`.
        Unreadable: when it is not UTF-8.
        AssessmentError: on the first bad line.
    """
    from ....domain.assessment.overlay import parse
    from ....infra.files import read_text

    return parse(read_text(path, "gaps.txt"))


def derive(r, store, today=None):
    """The Derived assessment for the match result `r` over `store`
    (domain.assessment.derive.derive over the engine's queries), with the career's
    absences: a confirmed "no" still standing on `today` answers what it denies (Ruling 9
    of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md).

    Args:
        r: match.result's plain data for one posting.
        store: the loaded workspace the match ran on.
        today: the day an absence's lapse is measured against; None takes no absence.

    Returns:
        domain.assessment.derive.derive's Derived. Reads the confirmed bullets' words.
    """
    from ....application.tailor.match_text import question_line
    from ....domain.assessment.derive import derive as derived
    from ....domain.record.absence import of_triples
    from ....domain.record.state import KB
    from ....infra.oxigraph.queries import OxigraphQueries

    absences = of_triples(store.graph(KB)) if today is not None and KB in store.parsed else []
    return derived(r, OxigraphQueries(store), question_line, absences=absences, today=today)


def advert(path):
    """posting.md's lines, as advert_lines numbers them.

    Args:
        path: the posting.md.

    Returns:
        The numbered lines; none when there is no posting.md.

    Raises:
        Unreadable: there is one and it cannot be read.
    """
    from ....domain.posting.advert import advert_lines
    from ....infra.files import Missing, read_text

    try:
        return advert_lines(read_text(path, "posting.md"))
    except Missing:
        return []


def drops(post_dir):
    """decisions.txt's drops, or none for a posting written before decisions.txt existed.
    DecisionsError and Unreadable propagate: a file `jsk posting build` would refuse is
    not guessed at.

    Args:
        post_dir: the application directory.

    Returns:
        The Drops.
    """
    import os

    from ....infra.files import Missing
    from .posting import read_decisions

    try:
        return read_decisions(os.path.join(post_dir, "decisions.txt"), "decisions.txt").drops
    except Missing:
        return []


def draft_gaps(derived, store, advert_path):
    """gaps.txt for the Derived assessment `derived`, with a slot wherever judgement is
    needed (application.tailor.draft_gaps.draft_gaps over this module's Folder).

    Args:
        derived: the Derived assessment.
        store: the loaded workspace.
        advert_path: the posting.md the slots quote.

    Returns:
        The draft's text.
    """
    from ....application.tailor.draft_gaps import draft_gaps as drafted

    return drafted(derived, store, advert_path, folder=Folder())


class Folder:
    """An application's folder and its record, as the assessment and the gaps.txt draft
    read and write them: the files on disk, the store through compose.timeline's writers."""

    def name_of(self, path, root):
        """`path` as findings name it (infra.files.file_name)."""
        from ....infra.files import file_name

        return file_name(path, root)

    def sent_day(self, app_dir, store):
        """The day the application was sent, or None (compose.timeline.sent_day).

        Raises:
            GraphError: whether it was sent cannot be read.
        """
        from .timeline import sent_day

        return sent_day(app_dir, store)

    def derive(self, r, store, today=None):
        """The Derived assessment for the match `r`, with the absences standing on `today`
        (this module's derive)."""
        return derive(r, store, today)

    def read_text(self, path, what):
        """An authored file's text (infra.files.read_text).

        Raises:
            Missing, Unreadable: with the fix.
        """
        from ....infra.files import read_text

        return read_text(path, what)

    def drops(self, app_dir):
        """decisions.txt's drops, or none when there is no decisions.txt (this module's drops)."""
        return drops(app_dir)

    def advert(self, path):
        """posting.md's numbered lines, or none when there is none (this module's advert)."""
        return advert(path)

    def person(self, store):
        """(columns, rows) of the person's facts (application.record.queries.person)."""
        from ....application.record.queries import person

        return person(store)

    def write_graphs(self, app_dir, graphs, store):
        """Replace the application's graphs in one update (compose.timeline.write_app_graphs).

        Raises:
            Unwritable: nothing was written; Frozen when the application is sent.
        """
        from .timeline import write_app_graphs

        return write_app_graphs(app_dir, graphs, store)

    def write_file(self, app_dir, name, text, store):
        """Write the document `name` in the folder (compose.timeline.write_app_file).

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
    """Write the assessment - the gaps graph - for the match `r` of the posting in `app_dir`
    (application.tailor.check_gaps.build over this module's Folder). The caller holds its
    turn (record.turn) and loaded `store` inside it.

    Args:
        app_dir: the application directory.
        store: the workspace, loaded inside the turn.
        r: match.result's plain data.
        today: the day the assessment is dated.
        derived: the Derived assessment when the caller has it, else None.

    Returns:
        (what was written, the findings, the assessment rendered or None). On a FAIL
        nothing is written.
    """
    from ....application.tailor.check_gaps import build as built

    return built(app_dir, store, r, today, derived, folder=Folder())


class Reads:
    """The named reads the digest shows, and their table (application/tailor/prepare.py's
    `reads`): application.record.queries over the engine's feature reads."""

    def evidence_for(self, store, *terms):
        """What the record holds for each term (application.record.queries.evidence_for).

        Args:
            store: a loaded workspace.
            *terms: the terms.

        Returns:
            (columns, rows).
        """
        from ....application.record.queries import evidence_for
        from ....infra.oxigraph.queries import OxigraphQueries

        return evidence_for(store, *terms, queries=OxigraphQueries(store))

    def person(self, store):
        """The person's facts (application.record.queries.person).

        Args:
            store: a loaded workspace.

        Returns:
            (columns, rows).
        """
        from ....application.record.queries import person

        return person(store)

    def unconfirmed(self, store):
        """What the career holds unconfirmed (application.record.queries.unconfirmed).

        Args:
            store: a loaded workspace.

        Returns:
            (columns, rows).
        """
        from ....application.record.queries import unconfirmed

        return unconfirmed(store)

    def table(self, columns, rows):
        """The rows as a markdown table (adapters.cli.presenters.table).

        Args:
            columns: the column names.
            rows: the rows, as dicts.

        Returns:
            The table's text.
        """
        from ..presenters import table

        return table(columns, rows)
