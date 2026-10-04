"""Reading the record: entries by id as Turtle, the whole career as Markdown, the log.

the career_show, career_view and career_log tools. Each loads the workspace through the `load` it is given
(adapters/cli/compose/record.py's) and returns what to print; adapters/cli/kb/read.py prints it.
"""
import difflib
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.record.state import KB, LOG, integer
from ...domain.record.writer import curie, entry_text, with_children
from .refusals import Refused, Unclean


def iri_of(text):
    """k:prj_x, prj_x or c:kafka as an iri.

    Args:
        text: an id as a person or an agent types it.

    Returns:
        The full iri: k: when no prefix is given.
    """
    if text.startswith("k:"):
        return O.K + text[2:]
    if text.startswith("c:"):
        return O.C + text[2:]
    return O.K + text


def unknown(iri, store):
    """(detail, fix) for an id the record does not hold, naming the nearest one it does.

    Args:
        iri: the id asked for.
        store: the loaded workspace.

    Returns:
        The refusal's line and its fix.
    """
    near = difflib.get_close_matches(iri, list(store.homes), n=1)
    return (f"{curie(iri)} is not in the record",
            f"did you mean {curie(near[0])}?" if near else "check the id: the career_view tool (jsk mcp) lists them")


@dataclass(frozen=True)
class Entry:
    """One id the career_show tool (jsk mcp) was asked for: why it is missing, or where it is and its text."""

    text: str                   # the id as given
    missing: tuple | None       # (detail, fix) when the record has no such id
    graphs: tuple = ()          # (graph name, heading line or None, the entries as Turtle)


@dataclass(frozen=True)
class Shown:
    """What the career_show tool (jsk mcp) found: the revision a changeset's op:base names, and each id."""

    log_revision: int | None
    entries: tuple


def show(root, ids, bullets, *, load, state):
    """The entries named, each with its children, under each graph that holds it.

    Args:
        root: the workspace.
        ids: the ids asked for, as typed.
        bullets: a project as its name and its bullets only.
        load: loads the workspace (compose.record.load).
        state: where the career and its log stand (infra.oxigraph.record.state).

    Returns:
        Shown. Reads the record.
    """
    store = load(root)
    revision = state(store).log_revision
    entries = []
    for text in ids:
        iri = iri_of(text)
        files = [f for f in store.definitions.get(iri, []) if f in store.parsed]
        if not files:
            entries.append(Entry(text, unknown(iri, store)))
            continue
        graphs = []
        for f in files:
            quads = store.graph(f)
            shown, heading = with_children(quads, iri), None
            if bullets and O.class_of(iri) == "Project":
                name = next((q.object.value for q in quads if q.subject.value == iri
                             and q.predicate.value == O.J + "name"), "")
                heading = f"# {curie(iri)} - {name}"
                shown = shown[1:]
            graphs.append((f, heading, "\n\n".join(entry_text(quads, i) for i in shown)))
        entries.append(Entry(text, None, tuple(graphs)))
    return Shown(revision, tuple(entries))


def view(root, section, *, load, state):
    """The whole career as Markdown, in the career's section order.

    Args:
        root: the workspace.
        section: the one section to show, or None for all.
        load: loads the workspace (compose.record.load).
        state: where the career and its log stand (infra.oxigraph.record.state).

    Returns:
        The Markdown. Reads the record.

    Raises:
        Unclean: there is no career to show.
    """
    from ...domain.record.view import render

    store = load(root)
    if KB not in store.parsed:
        raise Unclean(state(store))
    return render(store.graph(KB), section)


@dataclass(frozen=True)
class LogEntry:
    """One revision of the record as its log keeps it."""

    revision: str
    date: str
    by: str                     # what made it: apply, confirm, new, ...
    summary: str
    minted: tuple
    touched: tuple


def log(root, last, *, load):
    """The newest `last` entries of the record's log, newest first.

    Args:
        root: the workspace.
        last: how many.
        load: loads the workspace (compose.record.load).

    Returns:
        [LogEntry]. Reads the record.

    Raises:
        Refused: the record has no log.
    """
    store = load(root)
    if LOG not in store.parsed:
        raise Refused(["the record has no log"], "`jsk kb check` says what is wrong")
    entries = {}
    for q in store.graph(LOG):
        if O.class_of(q.subject.value) == "LogEntry":
            entries.setdefault(q.subject.value, {}).setdefault(
                q.predicate.value[len(O.J):], []).append(q.object.value)
    rows = sorted(entries.values(), key=lambda e: -int(integer(e.get("revision", ["0"])[0]) or 0))
    return [LogEntry(e.get("revision", ["?"])[0], e.get("date", ["?"])[0],
                     e.get("by", ["?"])[0].rsplit("#", 1)[-1].rsplit("/", 1)[-1],
                     e.get("summary", [""])[0], tuple(e.get("minted", ())),
                     tuple(e.get("touched", ()))) for e in rows[:last]]
