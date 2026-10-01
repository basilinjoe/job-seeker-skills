"""An application's record graphs: what `jsk app freeze` writes, and `jsk app event` adds to.

`jsk app event` is adapters/cli/event.py, and the event is
added by application/timeline/add_event.py. This module keeps the path (Ruling 4 of the
onion design), the record's reads and writes, and event_quads, which a test patches here.
"""
import os
import sys

from ..domain import ontology as O
from ..domain.timeline.errors import Frozen as Frozen
from ..domain.timeline.errors import Unwritable as Unwritable
from ..domain.timeline.events import LEGACY as LEGACY
from ..domain.timeline.events import WEEKDAYS as WEEKDAYS
from ..domain.timeline.events import application_quads as application_quads
from ..domain.timeline.events import date_literal as date_literal
from ..domain.timeline.events import event_iri as event_iri
from ..domain.timeline.events import event_quads as event_quads
from ..domain.timeline.events import is_date as is_date
from ..domain.timeline.events import legacy_submitted as legacy_submitted
from ..domain.timeline.events import lit as lit
from ..domain.timeline.events import node as node
from ..domain.timeline.events import quad as quad
from ..domain.timeline.events import submitted_day as submitted_day
from ..domain.timeline.events import when as when
from ..infra.files import remove_document
from ..infra.files import write_document as write_document

# An application's record graphs, by kind: in career/store/ as applications/<dir>/<kind>.
RECORD = ("posting", "application", "gaps")


def posting_of(store, rel_dir):
    """(posting iri, stem) of the Posting in the application <rel_dir>, or (None, None)."""
    from ..domain.naming import app_graph

    parsed = store.parsed.get(app_graph(rel_dir, "posting"))
    if parsed is None:
        return None, None
    for q in parsed.quads:
        if O.class_of(q.subject.value) == "Posting":
            iri = q.subject.value
            return iri, iri[len(O.K) + len("post_"):]
    return None, None


# --- what a sent application keeps ---------------------------------------------------
#
# Two tests, both here so that no command writes its own. `frozen`: `jsk app freeze` has run,
# so the documents and resume.json in the directory are what went out - a render or a
# confirm must not touch them. `sent_day`: the application's record holds the day it was
# sent, so the posting it answered and the assessment of it are what they said then. A
# held-back application (submitted false) is frozen but not sent. An application.md is
# one frozen before the career was a graph, and is as frozen as an application record.
#
# The record is the store's application graph and nothing else: `jsk kb load` leaves the
# .ttl files where they were, and a stray application.ttl there must not freeze, or
# unfreeze, anything.


def workspace_of_app(app_dir):
    """(workspace root, `applications/<dir>`) for a directory at
    <root>/applications/<dir>, else (None, None). Both named as they are on disk
    (store.spelled): the graph name is the folder's, however the path was typed."""
    from ..infra.files import spelled

    here = os.path.abspath(app_dir)
    apps = os.path.dirname(here)
    root = os.path.dirname(apps)
    if spelled(root, os.path.basename(apps)) != "applications":
        return None, None
    return root, "applications/" + spelled(apps, os.path.basename(here))


def app_graphs(app_dir, store=None):
    """{kind: triples} of the record graphs the application holds in its workspace's
    store - {} when it is in no workspace with a store. Read from `store` when it is that
    workspace's, loaded; from the store on disk if not."""
    from ..infra.oxigraph import db
    from ..domain.naming import app_graph

    root, rel = workspace_of_app(app_dir)
    if root is None or not db.exists(root):
        return {}
    if store is not None and store.stored and \
            os.path.normcase(os.path.abspath(store.root)) == os.path.normcase(root):
        graphs = {n: p.quads for n, p in store.parsed.items()}
    else:
        graphs = db.read(root)
    return {kind: graphs[app_graph(rel, kind)] for kind in RECORD
            if app_graph(rel, kind) in graphs}


def has_record(app_dir, kind, store=None):
    """Does the application hold its `kind` graph (posting, application, gaps)?"""
    return kind in app_graphs(app_dir, store)


def frozen(app_dir, store=None):
    """What says `app_dir` was frozen, else None: the application graph's name
    (`applications/<dir>/application`), or a legacy application.md's path."""
    if "application" in app_graphs(app_dir, store):
        return f"{workspace_of_app(app_dir)[1]}/application"
    path = os.path.join(app_dir, LEGACY)
    return path if os.path.isfile(path) else None


def sent_day(app_dir, store=None):
    """The day `app_dir` says it was sent - its application record's j:submitted, or a
    legacy application.md's `submitted:` - or None. Raises GraphError when that cannot be
    read: whether it was sent is then unknown, and the writers below refuse rather than
    guess."""
    from .io import GraphError, Unreadable, read_text

    graphs = app_graphs(app_dir, store)
    if "application" in graphs:
        return submitted_day(graphs["application"])
    path = frozen(app_dir, store)
    if path is None:
        return None
    try:
        return legacy_submitted(read_text(path, LEGACY))
    except Unreadable as e:
        raise GraphError(str(e), e.fix, os.path.basename(path)) from None


def refuse_if_sent(app_dir, name, store=None, graph=False):
    """Raise Frozen when `name` in `app_dir` must not change: the application was sent,
    or whether it was cannot be read. `graph`: `name` is a graph's (applications/<dir>/
    gaps), not a file in the directory."""
    from ..domain.record.parsed import GraphError

    try:
        day = sent_day(app_dir, store)
    except GraphError as e:
        raise Frozen(f"{name}: {os.path.basename(frozen(app_dir, store) or LEGACY)} "
                     f"beside it cannot be read, so whether it was sent is unknown ({e})",
                     "`jsk kb check` shows what is wrong with it") from None
    if day:
        raise Frozen(f"{name if graph else os.path.join(app_dir, name)}: the application was "
                     f"sent on {day}, and this is what it answered", "copy the application "
                     "to a new dated directory to reuse it")


def write_app_graphs(app_dir, graphs, store=None):
    """Replace the application's `graphs` ({kind: triples, or None to drop it}) in its
    workspace's store, in one update - or raise Unwritable, writing nothing: Frozen when
    the application is sent. Returns the graph names written. The posting and the
    assessment come through here; the application graph is `jsk app freeze`'s and `jsk
    event`'s, which write to a sent application, and does not."""
    from ..infra.oxigraph import record as R
    from ..domain.naming import app_graph

    root, rel = workspace_of_app(app_dir)
    names = {kind: app_graph(rel, kind) for kind in graphs}
    for kind in graphs:
        refuse_if_sent(app_dir, names[kind], store, graph=True)
    try:
        R.write_graphs(root, {names[k]: t for k, t in graphs.items()})
    except R.Written as e:
        raise Unwritable(f"{rel}: {e}", e.fix) from None
    except R.RecordError as e:
        raise Unwritable(f"{rel}: not written - {e}", e.fix) from None
    return [names[k] for k, t in graphs.items() if t]


def write_app_file(app_dir, name, text, store=None):
    """Write the document `name` in `app_dir` (gaps.md) - or raise Unwritable, writing
    nothing: Frozen when the application is sent, else the file is locked or the disk
    refused. The record's graphs go through write_app_graphs."""
    refuse_if_sent(app_dir, name, store)
    return write_document(os.path.join(app_dir, name), text)


def remove_app_file(app_dir, name, store=None):
    """Remove `name` from `app_dir` if it is there - or raise Unwritable (Frozen when the
    application is sent). True when a file was removed."""
    refuse_if_sent(app_dir, name, store)
    return remove_document(os.path.join(app_dir, name))


# --- what an application sent --------------------------------------------------------

def sent_versions(store, bullets):
    """The current version of each metric the bullets cite - what `jsk kb query stale`
    compares against when a metric is later revised."""
    from ..infra.oxigraph.queries import OxigraphQueries

    if not bullets:
        return []
    return OxigraphQueries(store).cited_current_versions(bullets)


class Sealed:
    """What freeze() validated inside the turn, for write_frozen: the application's graph
    name as it stands, the application graph to write, and the graphs a rename moves - as
    that load read them, so nothing is read again once the folder has moved."""

    def __init__(self, rel, quads, moves):
        self.rel, self.quads, self.moves = rel, quads, moves


def freeze(root, app_dir, plan, short_bytes, submitted, channel, documents):
    """(Sealed, None) for an application whose resume.json is a short file, validated with
    the whole workspace - or (None, [lines saying why not]). write_frozen writes it.

    `plan` is what the builder rendered: its `sent` names the bullets that cleared the
    floor, so a bullet the file lists but the render withheld is not claimed as sent. No
    copy of the words is kept - the PDF, .txt and .tex beside it are what went out - so
    the short file's own hash is what `recordSha256` pins."""
    def sent(store):
        bullets = [O.K + b for b in plan["sent"]]
        return bullets, sent_versions(store, bullets)

    return write_application(root, app_dir, "resume", submitted, channel, documents,
                             short_bytes, sent)


def write_application(root, app_dir, view, submitted, channel, documents, record_bytes,
                      carried_of):
    """Validated where it stands, before any rename: renaming the directory changes no
    triple, and the posting beside it, which the rules read, is there only now.
    `carried_of(store)` is (bullet iris, metric version iris) for what was sent."""
    from . import store as S
    from ..domain.record.state import new_failures

    store = S.load(root)
    # Asked again here, inside the turn: another freeze of this application may have
    # landed since `jsk app freeze` asked, while this one waited.
    held = frozen(app_dir, store)
    if held:
        return None, [f"{held} already exists. A frozen application is never re-frozen.",
                      "Later events are `jsk app event`, one each."]
    rel = S.file_name(os.path.abspath(app_dir), store.root)
    posting, stem = posting_of(store, rel)
    if posting is None:
        broken = [f.text() for f in store.findings if f.file == S.app_graph(rel, "posting")]
        return None, ([f"no posting in {app_dir}"] + broken +
                      ["the application record names the posting it answered: "
                       f"`jsk posting build {app_dir}` writes it from posting.md"])
    bullets, versions = carried_of(store)
    _, quads = application_quads(stem, posting, view, submitted, channel, documents,
                                 record_bytes, bullets, versions)
    after = S.load(root, graphs={S.app_graph(rel, "application"): quads})
    broken = new_failures(store, after)
    if broken:
        return None, (["the application record it would write does not validate:"]
                      + [f.text() for f in broken])
    moves = {kind: store.graph(S.app_graph(rel, kind)) for kind in ("posting", "gaps")
             if S.app_graph(rel, kind) in store.parsed}
    return Sealed(rel, quads, moves), None


def write_frozen(root, sealed, final):
    """Write what freeze() validated, once the directory is at `final` (renamed to the day
    it was sent, or left where it was). Returns the graph's name.

    A graph is named by its directory, so a rename moves the posting and the assessment
    to the new name in the same update that writes the application - all three land, or
    none does."""
    from ..infra.oxigraph import record as R
    from ..domain.naming import app_graph

    old, new = sealed.rel, workspace_of_app(final)[1]
    graphs = {}
    if old != new:
        for kind, triples in sealed.moves.items():
            graphs[app_graph(old, kind)] = None
            graphs[app_graph(new, kind)] = triples
    graphs[app_graph(new, "application")] = sealed.quads
    R.write_graphs(root, graphs)
    return app_graph(new, "application")


# --- jsk app event -----------------------------------------------------------------------

def main(argv=None):
    """`jsk app event` (adapters.cli.event.main).

    Args:
        argv: the arguments after `event`; sys.argv's when None.

    Returns:
        The exit code.
    """
    from ..adapters.cli.event import main as event

    return event(argv)


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.graph.timeline", "jsk app event"))
