"""The one gate every `jsk kb` write goes through, and the career_apply tool (jsk mcp).

A write is logged: the career is stamped with the next revision, the log gains the entry
naming what the write touched and minted, and both are validated as the record they would
make before either is written, in one update. WriteLogged does it in two steps, because
the command prints the diff between them: `candidate` stamps and validates, `write`
writes. The command already holds its turn (record.turn), so nothing lands between the
two.
"""
from dataclasses import dataclass
from typing import Any

from ...domain.record.state import KB, Prepared, diff, new_failures
from ...domain.record.writer import curies
from .refusals import Failing, Problems, Refused, Unclean


def writable(store, state):
    """Refuse a record that may not be written: only a clean one may - in a store,
    anything else means something outside jsk wrote it.

    Args:
        store: the loaded workspace.
        state: where the career and its log stand (infra.oxigraph.record.state).

    Returns:
        None.

    Raises:
        Failing: the career has FAILs (an application's count only when it will not
            parse). Unclean: the record is not clean.
    """
    from ...domain.naming import is_own

    blocking = [f for f in store.fails() if f.rule not in ("log-sync",)
                and (not is_own(f.file) or f.rule == "syntax")]
    if blocking:
        raise Failing(blocking, f"REFUSED  the career has {len(blocking)} failures - fix them first:")
    st = state(store)
    if st.kind != "clean":
        raise Unclean(st)


def changed_subjects(before, after):
    """The subjects whose triples differ between two versions of the career, leaving out
    the header's revision and day, which every write moves: what a write's log entry must
    name as touched or minted, or a changeset drafted before it would rebase over it
    unrefused (edit.base_conflicts checks ids, and only the ids the log names).

    Args:
        before: the career's quads as stored.
        after: the career's quads as the write would leave them.

    Returns:
        The set of subject iris.
    """
    from ...domain import ontology as O

    stamp = {(O.K + "kb", O.J + "revision"), (O.K + "kb", O.J + "updated")}

    def triples(quads):
        return {(q.subject.value, q.predicate.value, str(q.object)) for q in quads
                if (q.subject.value, q.predicate.value) not in stamp}
    return {s for s, _, _ in triples(before) ^ triples(after)}


@dataclass(frozen=True)
class Candidate:
    """A write stamped and validated: what to write, its diff, and what it says it did."""

    prepared: Prepared
    diff: str                   # the career before and after, as the writer lays it out
    minted: tuple
    touched: tuple
    notes: tuple

    @property
    def revision(self):
        """The revision the write makes."""
        return self.prepared.revision


class WriteLogged:
    """The logged write of the career of the workspace at `root`.

    Args:
        root: the workspace.
        load: loads the workspace (compose.record.load); here, the candidate record.
        record: the write gate (infra.oxigraph.record): state, prepared, write_graphs.
    """

    def __init__(self, root, *, load, record):
        self.root = root
        self.load = load
        self.record = record

    def candidate(self, store, quads, by, summary, today, touched=(), minted=(), answer=None,
                  notes=()):
        """Stamp `quads` as the next revision and validate the record it would make.

        Args:
            store: the record as it stands, read inside the command's turn.
            quads: the career as the write leaves it.
            by: what writes it: apply, confirm, ...
            summary: the log entry's summary.
            today: the day the entry is dated.
            touched, minted: the ids it changes and the ids it adds.
            answer: the person's answer, for a confirmation.
            notes: what to say beside the diff.

        Returns:
            Candidate. Loads the candidate record once, to validate it.

        Raises:
            Refused: the write changes an id it does not log - a jsk bug.
            Failing: the record would be left with FAILs it has not got now.
        """
        from ...domain.record.writer import write

        missed = changed_subjects(store.graph(KB), quads) - set(touched) - set(minted)
        if missed:
            # Rebase trusts the log to name every id a write changed; one it left out would
            # let a changeset drafted before this write overwrite it unrefused.
            raise Refused([f"this write changes {curies(missed)} without logging it - a jsk bug"],
                          "report it; the record is untouched")
        p = self.record.prepared(store, quads, today, by, summary, touched, minted, answer)
        after = self.load(self.root, graphs=p.graphs())
        broken = new_failures(store, after)
        if broken:
            raise Failing(broken, f"REFUSED  the change would leave {len(broken)} failures:")
        return Candidate(p, diff(write(store.graph(KB), "kb"), p.kb_text), tuple(minted),
                         tuple(touched), tuple(notes))

    def write(self, candidate):
        """Write the candidate: the career and its log in one update, then the backup.

        Returns:
            The revision written.

        Raises:
            RecordError: the store refused the write (domain.record.state.RecordError).
        """
        self.record.write_graphs(self.root, candidate.prepared.graphs())
        return candidate.revision


@dataclass(frozen=True)
class Applied:
    """A changeset merged: the career as it leaves it, what it minted and touched, what to
    note, and the log entry's summary."""

    quads: list
    touched: Any                # the ids it changes, as edit.apply gives them
    minted: Any                 # and the ids it adds
    notes: tuple
    summary: str


def apply(store, text, name, today, *, read_changeset):
    """Merge the changeset in `text` into the career.

    Args:
        store: the record as it stands, already writable.
        text: the changeset's TriG.
        name: its file name, for its syntax errors and the default summary.
        today: the day a changed claim is dated.
        read_changeset: parses and checks a changeset (compose.record.read_changeset).

    Returns:
        Applied, or None when the record already says all of it.

    Raises:
        Refused: the changeset does not parse. Problems: the career refuses it, each
            refusal with its own fix.
    """
    from ...domain.record import edit
    from ...domain.record.changeset import Refused as ChangesetRefused
    from ...domain.record.parsed import GraphError

    try:
        cs = read_changeset(text, name)
        e = edit.apply(store, cs, today)
    except GraphError as err:
        raise Refused([str(err)], err.fix) from None
    except ChangesetRefused as err:
        # Each refusal keeps its own fix as a field: folded into the line, an MCP caller got
        # the fix inside the finding's text and none beside it (2026-10-02). The CLI prints
        # Problems as it printed the folded lines, byte for byte (presenters.refuse_each).
        raise Problems([(r.line(), r.fix) for r in err.refusals]) from None
    if not e.touched and not e.minted:
        return None
    summary = cs.summary or (f"Applied {name}: {len(e.minted)} added, "
                             f"{len(e.touched)} changed.")
    return Applied(e.quads, e.touched, e.minted, tuple(e.notes), summary)
