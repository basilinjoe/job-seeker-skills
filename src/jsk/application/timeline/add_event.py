"""Adding one event to an application's record: minted, validated with the workspace, written.

Adds k:evt_<stem>_<date>_<kind> to the application's graph (applications/<dir>/application)
- never edits one, never removes one. A second of the same kind on the same day is minted
_2, then _3; only an event identical to one already there is refused. The application is
not logged in the career's log: the log is the career's, and an application is not the
career. It prints nothing: adapters/cli/event.py says what it added.
"""
import datetime
import os
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.naming import app_graph
from ...domain.record.state import RecordError, Written, diff, new_failures
from ...domain.record.writer import curie, write


class EventRefused(Exception):
    """An event that was not added, with nothing written.

    `lines` say why, one each; `fix` is what to do about it.
    """

    def __init__(self, lines, fix):
        super().__init__(lines[0] if lines else fix)
        self.lines = lines
        self.fix = fix


class EventLanded(Exception):
    """The event is in the store, and the store failed after the write. Carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


@dataclass(frozen=True)
class EventResult:
    """One event added to an application's record."""

    diff: str                   # the application graph before and after, as a diff
    iri: str                    # the event, as a curie
    kind: str
    date: str                   # YYYY-MM-DD or "unknown"
    due: str | None
    today: datetime.date
    ahead: bool                 # the date is after today


def free_iri(store, base, quads):
    """The iri to mint for an event, or the one already there that is this one exactly.

    Two notes on one day, a round-1 and a round-2 interview-done, two recruiter-contacts
    dated unknown are all real, so the id is the first of base, base_2, base_3... that is
    free. Only an event identical in every field (kind, date, channel, note, due) is a
    duplicate: running the same command twice records nothing new.

    Args:
        store: the loaded workspace.
        base: the event's iri as event_quads minted it.
        quads: the event's quads under `base`.

    Returns:
        (iri to mint, None), or (None, the iri of the event that is this one).
    """
    want = {(q.predicate, q.object) for q in quads}
    iri, n = base, 2
    while iri in store.homes:
        have = {(q.predicate, q.object) for parsed in store.parsed.values()
                for q in parsed.quads if q.subject.value == iri}
        if have == want:
            return None, iri
        iri, n = f"{base}_{n}", n + 1
    return iri, None


def add_event(root, app_dir, kind, date, channel, note, due, today, *, load, name_of,
              event_quads, write_graphs):
    """Add one event to the application's record, inside the caller's turn.

    The turn is taken before the application is read, so an event that queued behind
    another write is added to what that one left.

    Args:
        root: the workspace root.
        app_dir: the application directory, frozen.
        kind: one of the pipeline vocabulary.
        date: the day it happened, YYYY-MM-DD, or "unknown".
        channel: how it came, or None.
        note: what it said, or None.
        due: the day a scheduled one is, YYYY-MM-DD, or None.
        today: the date the command runs on, read once by the adapter.
        load: (root, graphs=None) -> the loaded workspace (graph.store.load).
        name_of: (path, root) -> how findings name the file (infra.files.file_name).
        event_quads: (app, stem, date, kind, channel, note, due, iri=None) -> (iri, quads).
        write_graphs: (root, {name: triples}) writes them (ports.record.RecordRepository).

    Returns:
        An EventResult. Writes the application graph.

    Raises:
        EventRefused: the record is missing or broken, the event is there already, or the
            workspace would fail with it; nothing was written.
        EventLanded: the event was written and the store failed after it.
    """
    store = load(root)
    rel = app_graph(name_of(os.path.abspath(app_dir), store.root), "application")
    parsed = store.parsed.get(rel)
    if parsed is None:
        raise EventRefused([f.text() for f in store.findings if f.file == rel] or
                           [f"{rel} is not in the store"], "`jsk kb check` shows what is wrong")
    app = next((q.subject.value for q in parsed.quads
                if O.class_of(q.subject.value) == "Application"), None)
    if app is None:
        raise EventRefused([f"{rel} holds no application"], "`jsk app freeze` writes one")
    stem = app[len(O.K) + len("app_"):]
    iri, quads = event_quads(app, stem, date, kind, channel, note, due)
    iri, same = free_iri(store, iri, quads)
    if same:
        raise EventRefused([f"{curie(same)} is already recorded: this {kind} on {date}, with "
                            "the same channel, note and due"],
                           f"`jsk kb show {curie(same)}`; an event is never edited - add a "
                           "`note` event to say more")
    iri, quads = event_quads(app, stem, date, kind, channel, note, due, iri=iri)
    new = list(parsed.quads) + quads
    after = load(root, graphs={rel: new})
    broken = new_failures(store, after)
    if broken:
        raise EventRefused([f"the event would leave {rel} failing:"] + [f.text() for f in broken],
                           "check the date against the application's; `jsk kb check` shows "
                           "the rest")
    try:
        write_graphs(root, {rel: new})
    except Written as e:
        raise EventLanded(str(e), e.fix) from None
    except RecordError as e:
        raise EventRefused([str(e)], e.fix) from None
    # Every kind's date is the day it happened - a booking's too, its day is --due - so a
    # future one is arithmetic gone wrong, and it would sort as the latest stage.
    ahead = date != "unknown" and datetime.date.fromisoformat(date) > today
    return EventResult(diff(write(parsed.quads, "application"), write(new, "application"), rel),
                       curie(iri), kind, date, due, today, ahead)
