"""The career's reads and logged writes, bound and returned as values: what the career_view, career_show, career_query, career_log, career_apply and
career_confirm tools do, without the printing.

The kb adapter (adapters/cli/kb/) prints as it goes - the diff before the write, a refusal
as REFUSED lines - so its verbs cannot be called for a result. The MCP server
(adapters/mcp/server.py, docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md
Ruling 18) needs the same work as data, so it is bound here once, over the same use cases
(application/record/read.py, write.py, confirm.py, queries.py) and the same write gate.
The CLI keeps its own flow: its output is a contract its tests pin line by line, and
moving it onto this module would only reorder what it prints when a write fails.

Each read takes `load`, so a caller holding a loaded Store (the server's revision cache,
Ruling 14) can hand it in; the writes always load inside their turn, never from a cache.
Nothing here prints, and the clock is the caller's (`today`).
"""
from dataclasses import dataclass

from ....infra.oxigraph import record as R


@dataclass(frozen=True)
class Written:
    """A logged write of the career, done or - on a dry run - only validated."""

    revision: int               # the revision it makes
    diff: str                   # the career before and after
    minted: tuple               # the ids it adds, as iris
    touched: tuple              # the ids it changes, as iris
    notes: tuple
    written: bool               # False on a dry run


def default_load(load):
    """`load`, or compose.record.load when None."""
    if load is not None:
        return load
    from .record import load as loaded

    return loaded


def view(root, section=None, *, load=None):
    """The career as Markdown (application.record.read.view).

    Raises:
        Unclean: there is no career to show.
    """
    from ....application.record.read import view as viewed

    return viewed(root, section, load=default_load(load), state=R.state)


def show(root, ids, bullets=False, *, load=None):
    """The entries named, as Turtle, with the revision for op:base (application.record.read.show)."""
    from ....application.record.read import show as shown

    return shown(root, list(ids), bullets, load=default_load(load), state=R.state)


def log(root, last=10, *, load=None):
    """The newest `last` log entries (application.record.read.log).

    Raises:
        Refused: the record has no log.
    """
    from ....application.record.read import log as logged

    return logged(root, last, load=default_load(load))


def query(root, name, args=(), *, today, load=None):
    """A named query's answer (application.record.queries.QUERIES).

    Args:
        root: the workspace.
        name: the query's name.
        args: its arguments, as the career_query tool takes them after the name. For `concepts`,
            terms: each answered as `--near <term>` answers it.
        today: the day a dated query counts to.
        load: as view takes it.

    Returns:
        (columns, rows), or for `concepts` with terms {term: (columns, rows)}.

    Raises:
        Refused: no such query, or the wrong number of arguments for it.
    """
    from ....application.record.queries import QUERIES
    from ....application.record.refusals import Refused
    from ....infra.oxigraph.queries import OxigraphQueries

    if name not in QUERIES:
        raise Refused([f"{name!r} is not a named query"], f"one of {', '.join(QUERIES)}")
    want, _, fn, reads, dated = QUERIES[name]
    args = [str(a) for a in args or ()]
    store = default_load(load)(root)
    if name == "concepts" and args:
        return {term: fn(store, near=term, queries=OxigraphQueries(store)) for term in args}
    many = want.endswith("...")
    if many and not args or not many and len(args) != len(want.split()):
        raise Refused([f"{name} takes {want or 'no arguments'}"],
                      f"`args` as the query takes them: {name} {want}".rstrip())
    extra = {"queries": OxigraphQueries(store)} if reads else {}
    return fn(store, *args, **extra, **({"today": today} if dated else {}))


def logged(root, store, quads, by, summary, *, touched=(), minted=(), answer=None, notes=(),
           dry_run=False, today):
    """Stamp, validate and - unless a dry run - write one logged change of the career
    (application.record.write.WriteLogged). The caller holds the turn when it writes.

    Returns:
        The Written.

    Raises:
        Failing, Refused: the change would break the record; nothing written.
        RecordError: the store refused the write.
    """
    from ....application.record.write import WriteLogged
    from .record import load

    gate = WriteLogged(root, load=load, record=R)
    c = gate.candidate(store, quads, by, summary, today, touched, minted, answer, notes)
    if not dry_run:
        gate.write(c)
    return Written(c.revision, c.diff, c.minted, c.touched, c.notes, not dry_run)


def apply_changeset(root, text, *, dry_run=False, today, name="changeset.trig"):
    """A changeset's TriG merged into the career and logged, as the career_apply tool does.

    Args:
        root: the workspace.
        text: the changeset, as TriG.
        dry_run: validate and return the diff, and write nothing; takes no turn.
        today: the day a changed claim is dated and the log entry made.
        name: what its syntax errors are reported under.

    Returns:
        The Written, or None when the record already says all of it.

    Raises:
        Failing, Unclean: the record may not be written. Refused: the changeset does not
            parse. Problems: the career refuses it, each refusal with its fix. RecordError:
            the store refused the write.
    """
    from ....application.record import write as W
    from .record import load, read_changeset

    with R.turn(root, dry_run=dry_run):
        store = load(root)
        W.writable(store, R.state)
        applied = W.apply(store, text, name, today, read_changeset=read_changeset)
        if applied is None:
            return None
        return logged(root, store, applied.quads, "apply", applied.summary,
                      touched=applied.touched, minted=applied.minted, notes=applied.notes,
                      dry_run=dry_run, today=today)


def confirm_ids(root, ids, *, answer=None, source=None, quote=None, today):
    """The entries `ids` confirmed with the person's answer, or a document's quote, and
    logged, as the career_confirm tool does.

    Returns:
        The Written, or None when every one of them is confirmed already.

    Raises:
        Refused, Problems, Failing, Unclean: as the career_confirm tool refuses; nothing written.
        RecordError: the store refused the write.
    """
    from ....application.record import confirm as C
    from ....domain.record.writer import curies
    from ....infra import files, pdf
    from .record import load

    with R.turn(root):
        said = C.answer_of(answer, source, quote, root, files=files, read_pdf=pdf.read_pdf)
        store = load(root)
        plan = C.confirmation(store, list(ids), quote, today, state=R.state)
        if plan is None:
            return None
        return logged(root, store, plan.quads, "confirm", f"Confirmed {curies(plan.ids)}.",
                      touched=plan.touched, answer=said, today=today)
