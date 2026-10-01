"""`jsk kb export`: choosing the bullets a resume.json shows, and writing the file.

Choosing is three steps, because the command says what each found before the next can
refuse: the career is opened and checked (`opened`), the selection is made for a posting,
by rank or not at all (`selection`), and the short file is formed from it with the
numbers its bullets state checked (`short`). Writing it is `write`. Nothing here prints:
adapters/cli/kb/export.py does.

The pieces that read the career are given as parameters - graph/export.py's short file
(`shorts`), graph/select.py's selection (`selector`), graph/match.py's posting lookup -
so this imports nothing outside the application and the domain.
"""
import os
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.record.career import Career
from ...domain.record.state import KB
from ..record.check import untraced_lines
from ..record.refusals import Failing, Refused, Unclean


def opened(root, app, posting, out, replace, *, load, state, file_name, blocks):
    """The career, loaded and checked for what would stop a resume.

    Args:
        root: the workspace.
        app: the application directory for --from-match, or None.
        posting: --from-match as given (truthy when there is one).
        out: --out, or None.
        replace: whether --replace was given.
        load: loads the workspace (graph.store.load).
        state: where the career and its log stand (infra.oxigraph.record.state).
        file_name: a path as a finding names it (infra.files.file_name).
        blocks: whether a finding stops a match of the application (graph.match.blocks).

    Returns:
        The loaded store. Reads the record.

    Raises:
        Unclean: there is no career. Failing: the career (or the posting) has FAILs a
            resume would carry. Refused: --out exists and --replace was not given.
    """
    store = load(root)
    if KB not in store.parsed:
        raise Unclean(state(store))
    # The career always; with --from-match, the application's own directory too, as jsk
    # match.
    here = file_name(app, store.root) + "/" if posting else None
    blocking = [f for f in store.fails() if f.rule != "log-sync"
                and (not f.file.startswith("applications/") or (here and blocks(f, here)))]
    if blocking:
        where = "the career and the posting have" if posting else "the career has"
        raise Failing(blocking, f"REFUSED  {where} {len(blocking)} failures - "
                                "a resume would carry them:", written=False)
    if out and os.path.exists(out) and not replace:
        raise Refused([f"{out} exists - export writes a new resume.json, never over one "
                       "unless told to"],
                      "edit it, or pass --replace to export it again - it holds only ids and "
                      "settings, and the career is read afresh at every render")
    return store


def selection(store, app, posting, select, by_rank, today, budget, *, shorts, selector,
              posting_in):
    """The selection for a posting (--from-match) or by rank (--ranked), or None for neither.

    Args:
        store: the loaded workspace.
        app: the application directory, with --from-match.
        posting: --from-match as given.
        select: the ids --select named, or None.
        by_rank: --ranked.
        today: the date recency is counted from.
        budget: the most projects the cover may use (--cover).
        shorts: the short file's logic (graph.export): Career, chosen, ExportError.
        selector: the selection (graph.select): ranked, select.
        posting_in: the posting an application holds (graph.match.posting_in).

    Returns:
        domain.selection.select.Selection, or None.

    Raises:
        Refused: a --select that cannot be honoured, or an application with no posting.
    """
    if not (posting or by_rank):
        return None
    try:
        shorts.chosen(shorts.Career(store.graph(KB)), select)      # a bad --select refuses first
    except shorts.ExportError as err:
        raise Refused([str(err)], err.fix) from None
    extra = [O.K + t.removeprefix("k:") for t in select or []]
    if by_rank:
        return selector.ranked(store, today, extra)
    post = posting_in(store, app)
    if post is None:
        raise Refused([f"{posting} holds no posting"],
                      f"`jsk posting build {posting}` writes it from posting.md")
    return selector.select(store, post, today, budget, extra)


@dataclass(frozen=True)
class Short:
    """The short resume.json, what forming it noted, and the number checks it fails."""

    doc: dict
    notes: tuple                # NOTE lines: a skills row cut, a project with no role
    faults: tuple               # untraced_lines over the chosen bullets


def short(store, chosen, select, today, *, shorts, queries):
    """The short resume.json for `chosen` (or `select`, or the whole career).

    Args:
        store: the loaded workspace.
        chosen: the Selection, or None.
        select: the ids --select named, or None.
        today: the date the number check runs on.
        shorts: the short file's logic (graph.export): short_file, ExportError.
        queries: the RecordQueries over the store.

    Returns:
        Short.

    Raises:
        Refused: a --select it cannot honour, or a selection with no bullet.
    """
    notes = []
    try:
        doc = shorts.short_file(store, selection=chosen, select=select, notes=notes)
    except shorts.ExportError as err:
        raise Refused([str(err)], err.fix) from None
    faults = untraced_lines(store, queries, today, [O.K + b for b in doc["bullets"]])
    return Short(doc, tuple(notes), tuple(faults))


@dataclass(frozen=True)
class Written:
    """A resume.json written: where, at which revision, and each bullet's first words."""

    path: str
    revision: int | None
    bullets: tuple              # (id, its first 100 characters)


def write(store, path, text, doc, *, state, write_text):
    """Write the short file to `path`.

    Args:
        store: the loaded workspace the file was chosen from.
        path: --out.
        text: the file's text.
        doc: the file as data.
        state: where the career and its log stand (infra.oxigraph.record.state).
        write_text: writes a text file, its folder made first.

    Returns:
        Written. Writes the file.
    """
    write_text(path, text)
    revision = state(store).log_revision
    career = Career(store.graph(KB))
    bullets = tuple((b, " ".join((career.get(O.K + b, "text") or "").split())[:100])
                    for b in doc["bullets"])
    return Written(path, revision, bullets)
