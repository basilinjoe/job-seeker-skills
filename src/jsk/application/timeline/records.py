"""An application's record graphs: what `jsk app freeze` writes, and what a sent application keeps.

Two tests, both here so that no command writes its own. `frozen`: `jsk app freeze` has run,
so the documents and resume.json in the directory are what went out - a render or a
confirm must not touch them. `sent_day`: the application's record holds the day it was
sent, so the posting it answered and the assessment of it are what they said then. A
held-back application (submitted false) is frozen but not sent. An application.md is
one frozen before the career was a graph, and is as frozen as an application record.

The record is the store's application graph and nothing else: `jsk kb load` leaves the
.ttl files where they were, and a stray application.ttl there must not freeze, or
unfreeze, anything. The folder and the store are reached through `records`
(ports.applications.ApplicationRecords); adapters/cli/compose/timeline.py binds the real one.
"""
import os

from ...domain import ontology as O
from ...domain.naming import app_graph
from ...domain.record.parsed import GraphError, Unreadable
from ...domain.record.state import RecordError, Written
from ...domain.timeline.errors import Frozen, Unwritable
from ...domain.timeline.events import LEGACY, application_quads, legacy_submitted, submitted_day

# An application's record graphs, by kind: in career/store/ as applications/<dir>/<kind>.
# `review` and `resume` are a graph-native application's (Ruling 10 of
# docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md): the analyst's
# review and the selection, which a sent application keeps as it keeps its posting.
RECORD = ("posting", "application", "gaps", "review", "resume")
# What a rename at freeze carries to the new name with the application graph: every kind
# but that one, which freeze writes itself.
MOVED = tuple(kind for kind in RECORD if kind != "application")


def posting_of(store, rel_dir):
    """The Posting in the application `rel_dir`.

    Args:
        store: a loaded workspace.
        rel_dir: the application as the store names it, `applications/<dir>`.

    Returns:
        (posting iri, stem), or (None, None) when its posting graph holds none.
    """
    parsed = store.parsed.get(app_graph(rel_dir, "posting"))
    if parsed is None:
        return None, None
    for q in parsed.quads:
        if O.class_of(q.subject.value) == "Posting":
            iri = q.subject.value
            return iri, iri[len(O.K) + len("post_"):]
    return None, None


def app_graphs(app_dir, store=None, *, records):
    """The record graphs the application holds in its workspace's store.

    Args:
        app_dir: the application directory.
        store: the workspace, loaded - read from when it is this application's workspace's.
        records: the folder and the store (ApplicationRecords).

    Returns:
        {kind: triples}; {} when it is in no workspace with a store. Reads the store on
        disk when `store` is not that workspace's.
    """
    root, rel = records.workspace_of_app(app_dir)
    if root is None or not records.has_store(root):
        return {}
    if store is not None and store.stored and \
            os.path.normcase(os.path.abspath(store.root)) == os.path.normcase(root):
        graphs = {n: p.quads for n, p in store.parsed.items()}
    else:
        graphs = records.read_store(root)
    return {kind: graphs[app_graph(rel, kind)] for kind in RECORD
            if app_graph(rel, kind) in graphs}


def has_record(app_dir, kind, store=None, *, records):
    """Whether the application holds its `kind` graph.

    Args:
        app_dir: the application directory.
        kind: posting, application or gaps.
        store: the workspace, loaded, or None.
        records: the folder and the store (ApplicationRecords).

    Returns:
        True when the graph is in the store.
    """
    return kind in app_graphs(app_dir, store, records=records)


def frozen(app_dir, store=None, *, records):
    """What says `app_dir` was frozen.

    Args:
        app_dir: the application directory.
        store: the workspace, loaded, or None.
        records: the folder and the store (ApplicationRecords).

    Returns:
        The application graph's name (`applications/<dir>/application`), or a legacy
        application.md's path, else None.
    """
    if "application" in app_graphs(app_dir, store, records=records):
        return f"{records.workspace_of_app(app_dir)[1]}/application"
    path = os.path.join(app_dir, LEGACY)
    return path if records.is_file(path) else None


def sent_day(app_dir, store=None, *, records):
    """The day `app_dir` says it was sent: its application record's j:submitted, or a
    legacy application.md's `submitted:`.

    Args:
        app_dir: the application directory.
        store: the workspace, loaded, or None.
        records: the folder and the store (ApplicationRecords).

    Returns:
        The day, or None when it was not sent.

    Raises:
        GraphError: that cannot be read - whether it was sent is then unknown, and the
            writers below refuse rather than guess.
    """
    graphs = app_graphs(app_dir, store, records=records)
    if "application" in graphs:
        return submitted_day(graphs["application"])
    path = frozen(app_dir, store, records=records)
    if path is None:
        return None
    try:
        return legacy_submitted(records.read_text(path, LEGACY))
    except Unreadable as e:
        raise GraphError(str(e), e.fix, os.path.basename(path)) from None


def refuse_if_sent(app_dir, name, store=None, graph=False, *, records):
    """Refuse a change to `name` in `app_dir` once the application was sent.

    Args:
        app_dir: the application directory.
        name: what would change: a file in the directory, or with `graph` a graph's name
            (applications/<dir>/gaps).
        store: the workspace, loaded, or None.
        graph: `name` is a graph's.
        records: the folder and the store (ApplicationRecords).

    Raises:
        Frozen: the application was sent, or whether it was cannot be read.
    """
    try:
        day = sent_day(app_dir, store, records=records)
    except GraphError as e:
        raise Frozen(f"{name}: {os.path.basename(frozen(app_dir, store, records=records) or LEGACY)} "
                     f"beside it cannot be read, so whether it was sent is unknown ({e})",
                     "`jsk kb check` shows what is wrong with it") from None
    if day:
        raise Frozen(f"{name if graph else os.path.join(app_dir, name)}: the application was "
                     f"sent on {day}, and this is what it answered", "copy the application "
                     "to a new dated directory to reuse it")


def write_app_graphs(app_dir, graphs, store=None, *, records):
    """Replace the application's graphs in its workspace's store, in one update. The posting
    and the assessment come through here; the application graph is `jsk app freeze`'s and
    `jsk app event`'s, which write to a sent application, and does not.

    Args:
        app_dir: the application directory.
        graphs: {kind: triples, or None to drop it}.
        store: the workspace, loaded, or None.
        records: the folder and the store (ApplicationRecords).

    Returns:
        The graph names written.

    Raises:
        Unwritable: nothing was written - Frozen when the application is sent.
    """
    root, rel = records.workspace_of_app(app_dir)
    names = {kind: app_graph(rel, kind) for kind in graphs}
    for kind in graphs:
        refuse_if_sent(app_dir, names[kind], store, graph=True, records=records)
    try:
        records.write_graphs(root, {names[k]: t for k, t in graphs.items()})
    except Written as e:
        raise Unwritable(f"{rel}: {e}", e.fix) from None
    except RecordError as e:
        raise Unwritable(f"{rel}: not written - {e}", e.fix) from None
    return [names[k] for k, t in graphs.items() if t]


def write_app_file(app_dir, name, text, store=None, *, records):
    """Write the document `name` in `app_dir`. The record's graphs go through
    write_app_graphs.

    Args:
        app_dir: the application directory.
        name: the document's file name.
        text: its whole text.
        store: the workspace, loaded, or None.
        records: the folder and the store (ApplicationRecords).

    Returns:
        The path written.

    Raises:
        Unwritable: nothing was written - Frozen when the application is sent, else the
            file is locked or the disk refused.
    """
    refuse_if_sent(app_dir, name, store, records=records)
    return records.write_document(os.path.join(app_dir, name), text)


def remove_app_file(app_dir, name, store=None, *, records):
    """Remove `name` from `app_dir` if it is there.

    Args:
        app_dir: the application directory.
        name: the file's name.
        store: the workspace, loaded, or None.
        records: the folder and the store (ApplicationRecords).

    Returns:
        True when a file was removed.

    Raises:
        Unwritable: Frozen when the application is sent, else it could not be removed.
    """
    refuse_if_sent(app_dir, name, store, records=records)
    return records.remove_document(os.path.join(app_dir, name))


def sent_versions(queries, bullets):
    """The current version of each metric the bullets cite - what `jsk kb query stale`
    compares against when a metric is later revised.

    Args:
        queries: the record's feature reads (ports.queries.RecordQueries).
        bullets: the bullet iris sent.

    Returns:
        The version iris; none for no bullets.
    """
    if not bullets:
        return []
    return queries.cited_current_versions(bullets)


class Sealed:
    """What freeze() validated inside the turn, for write_frozen: the application's graph
    name as it stands, the application graph to write, and the graphs a rename moves - as
    that load read them, so nothing is read again once the folder has moved."""

    def __init__(self, rel, quads, moves):
        """Hold what write_frozen writes.

        Args:
            rel: the application's name in the store, `applications/<dir>`, before a rename.
            quads: the application graph.
            moves: {kind: triples} of the graphs a rename carries over (MOVED).
        """
        self.rel, self.quads, self.moves = rel, quads, moves


def freeze(root, app_dir, plan, short_bytes, submitted, channel, documents, *, load, records,
           queries):
    """The application record for an application whose resume.json is a short file,
    validated with the whole workspace; write_frozen writes it.

    `plan` is what the builder rendered: its `sent` names the bullets that cleared the
    floor, so a bullet the file lists but the render withheld is not claimed as sent. No
    copy of the words is kept - the PDF and .tex beside it are what went out - so
    the short file's own hash is what `recordSha256` pins. A graph-native application has
    no file: its bytes are the stored selection's canonical text (Ruling 7 of
    docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md).

    Args:
        root: the workspace root.
        app_dir: the application directory.
        plan: the render plan; its `sent` names the bullets sent.
        short_bytes: the short resume.json as it is on disk, or the selection's
            canonical text, UTF-8.
        submitted: the day it was sent, or `false`.
        channel: where it was sent.
        documents: the documents that went out.
        load: loads the workspace (ports: application/record/load.py, bound).
        records: the folder and the store (ApplicationRecords).
        queries: makes the record's feature reads over a loaded store.

    Returns:
        (Sealed, None), or (None, [lines saying why not]). Reads the record.
    """
    def sent(store):
        bullets = [O.K + b for b in plan["sent"]]
        return bullets, sent_versions(queries(store), bullets)

    return write_application(root, app_dir, "resume", submitted, channel, documents,
                             short_bytes, sent, load=load, records=records)


def write_application(root, app_dir, view, submitted, channel, documents, record_bytes,
                      carried_of, *, load, records):
    """The application graph, validated where the directory stands, before any rename:
    renaming the directory changes no triple, and the posting beside it, which the rules
    read, is there only now.

    Args:
        root: the workspace root.
        app_dir: the application directory.
        view: what was rendered (`resume`).
        submitted: the day it was sent, or `false`.
        channel: where it was sent.
        documents: the documents that went out.
        record_bytes: the record the render was made from, as it is on disk.
        carried_of: (store) -> (bullet iris, metric version iris) for what was sent.
        load: loads the workspace, with `graphs=` standing in for the store's.
        records: the folder and the store (ApplicationRecords).

    Returns:
        (Sealed, None), or (None, [lines saying why not]). Reads the record twice: as it
        is, and with the application graph in it.
    """
    from ...domain.record.state import new_failures

    store = load(root)
    # Asked again here, inside the turn: another freeze of this application may have
    # landed since `jsk app freeze` asked, while this one waited.
    held = frozen(app_dir, store, records=records)
    if held:
        return None, [f"{held} already exists. A frozen application is never re-frozen.",
                      "Later events are `jsk app event`, one each."]
    rel = records.file_name(os.path.abspath(app_dir), store.root)
    posting, stem = posting_of(store, rel)
    if posting is None:
        broken = [f.text() for f in store.findings if f.file == app_graph(rel, "posting")]
        return None, ([f"no posting in {app_dir}"] + broken +
                      ["the application record names the posting it answered: the "
                       "`posting_capture` tool (`jsk mcp`) stores one"])
    bullets, versions = carried_of(store)
    _, quads = application_quads(stem, posting, view, submitted, channel, documents,
                                 record_bytes, bullets, versions)
    after = load(root, graphs={app_graph(rel, "application"): quads})
    broken = new_failures(store, after)
    if broken:
        return None, (["the application record it would write does not validate:"]
                      + [f.text() for f in broken])
    moves = {kind: store.graph(app_graph(rel, kind)) for kind in MOVED
             if app_graph(rel, kind) in store.parsed}
    return Sealed(rel, quads, moves), None


def write_frozen(root, sealed, final, *, records):
    """Write what freeze() validated, once the directory is at `final`. A graph is named by
    its directory, so a rename moves the posting, the assessment, the review and the
    selection to the new name in the same update that writes the application - all of them
    land, or none does.

    Args:
        root: the workspace root.
        sealed: freeze()'s Sealed.
        final: the directory as it is now: renamed to the day it was sent, or left.
        records: the folder and the store (ApplicationRecords).

    Returns:
        The application graph's name. Writes the store.
    """
    old, new = sealed.rel, records.workspace_of_app(final)[1]
    graphs = {}
    if old != new:
        for kind, triples in sealed.moves.items():
            graphs[app_graph(old, kind)] = None
            graphs[app_graph(new, kind)] = triples
    graphs[app_graph(new, "application")] = sealed.quads
    records.write_graphs(root, graphs)
    return app_graph(new, "application")
