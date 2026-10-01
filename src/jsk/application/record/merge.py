"""`jsk kb merge`: two concepts that are one, drafted as a changeset against the revision
the log last recorded. Nothing is applied."""
from dataclasses import dataclass

from ...domain.record import merge as M
from ...domain.record.writer import curies
from .pack import logged_base
from .refusals import Problems


@dataclass(frozen=True)
class Merged:
    """A merge drafted: c:a and c:b as iris, domain.record.merge.draft's result, the
    changeset's text and its summary."""

    a: str
    b: str
    draft: dict
    text: str
    summary: str


def merge(root, away, into, *, load, state):
    """Draft merging the concept `away` into `into`.

    Args:
        root: the workspace.
        away: c:a, the concept merged away, as typed.
        into: c:b, the one it becomes, as typed.
        load: loads the workspace (graph.store.load).
        state: where the career and its log stand (infra.oxigraph.record.state).

    Returns:
        Merged. Reads the record.

    Raises:
        Unclean: the record has no logged revision to base the changeset on.
        Problems: the merge is refused, each reason with its fix.
    """
    from ...domain.record.pack import trig

    a, b = M.concept_iri(away), M.concept_iri(into)
    store = load(root)
    base = logged_base(store, state)
    try:
        m = M.draft(store, a, b)
    except M.Refused as err:
        raise Problems(err.reasons) from None
    summary = M.summary(a, b, m)
    text = trig(base, summary, {"delete": m["delete"], "add": m["add"], "retire": m["retire"]},
                entries=m["entries"], comments=[f"jsk kb merge {curies([a])} --into {curies([b])}"])
    return Merged(a, b, m, text, summary)
