"""`jsk kb pack`: a starter pack drafted as a changeset of what the record lacks, based on
the revision the log last recorded. Nothing is applied."""
from dataclasses import dataclass

from .refusals import Unclean


def logged_base(store, state):
    """The log's revision, which a drafted changeset names as its op:base.

    Args:
        store: the loaded workspace.
        state: where the career and its log stand (infra.oxigraph.record.state).

    Returns:
        The revision.

    Raises:
        Unclean: there is no record, or its log has no revision to base a change on.
    """
    st = state(store)
    if st.kind == "missing" or st.log_revision is None:
        raise Unclean(st)
    return st.log_revision


@dataclass(frozen=True)
class Drafted:
    """A pack drafted: the changeset's text (None when there is nothing to add), what it
    adds, and each part of the pack left out, with why."""

    text: str | None
    what: str
    skipped: tuple


def pack(root, name, *, load, state, packs):
    """Draft the pack called `name` against the workspace.

    Args:
        root: the workspace.
        name: a key of packs.PACKS.
        load: loads the workspace (compose.record.load).
        state: where the career and its log stand (infra.oxigraph.record.state).
        packs: where the packs are and how one is read (infra.packs): PACKS, read_pack.

    Returns:
        Drafted. Reads the record and the pack's file.

    Raises:
        Unclean: the record has no logged revision to base the changeset on.
    """
    from ...domain.record.pack import draft, trig

    store = load(root)
    base = logged_base(store, state)
    d = draft(store, packs.read_pack(packs.PACKS[name]))
    if not d.add:
        return Drafted(None, "", tuple(d.skipped))
    what = f"{len(d.added)} concepts added, {len(d.enriched)} enriched"
    text = trig(base, f"Adopted the {name} pack: {what}.", {"add": d.add},
                comments=[f"jsk kb pack {name}: {what}, {len(d.skipped)} skipped.",
                          "Read its diff with the career_preview tool (jsk mcp) before applying it with "
                          "career_apply."])
    return Drafted(text, what, tuple(d.skipped))
