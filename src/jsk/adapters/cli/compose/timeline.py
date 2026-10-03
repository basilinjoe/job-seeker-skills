"""An application's record, bound: application/timeline/records.py over the folder on disk
and career/store/ (infra.oxigraph.applications.StoredApplications).

Each function keeps the signature its callers use, with no `records` to pass. A test
patches write_frozen here, and the freeze looks it up here at each call.

`freeze_app` and `add_event` are `jsk app freeze` and `jsk app event` past their argument
checks, bound and run in the record's turn: the CLI adapters and the MCP tools
(adapters/mcp/server.py) call the same two, so a freeze or an event made either way is the
same write (2026-10-03). `drop_app` is `jsk app drop`, which has no tool: setting an
application aside is the person's call, not an agent's. Nothing here prints; a refusal is
raised for the caller to say.
"""
import os


def records():
    """The real folders and store: infra.oxigraph.applications.StoredApplications."""
    from ....infra.oxigraph.applications import StoredApplications

    return StoredApplications()


def app_graphs(app_dir, store=None):
    """{kind: triples} the application holds (application.timeline.records.app_graphs)."""
    from ....application.timeline import records as T

    return T.app_graphs(app_dir, store, records=records())


def has_record(app_dir, kind, store=None):
    """Whether the application holds its `kind` graph (records.has_record)."""
    from ....application.timeline import records as T

    return T.has_record(app_dir, kind, store, records=records())


def frozen(app_dir, store=None):
    """What says `app_dir` was frozen, else None (records.frozen)."""
    from ....application.timeline import records as T

    return T.frozen(app_dir, store, records=records())


def sent_day(app_dir, store=None):
    """The day `app_dir` was sent, or None (records.sent_day).

    Raises:
        GraphError: whether it was sent cannot be read.
    """
    from ....application.timeline import records as T

    return T.sent_day(app_dir, store, records=records())


def made_from_files(app_dir, store=None):
    """Whether `app_dir` is an application made from files and not frozen: a posting graph
    with no advert lines (Ruling 11 of the graph-native plan), or no posting graph and a
    file only the file pipeline wrote (application.timeline.unsent.FILE_MADE), and no
    application graph. What `jsk app freeze` and the `app_freeze` tool refuse since 6.0
    (Ruling 1 of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md); an application
    with neither is no file-made one, and is told it holds no posting."""
    from ....application.posting.native import native_graphs
    from ....application.timeline.unsent import FILE_MADE
    from ....domain.timeline.events import LEGACY

    graphs = app_graphs(app_dir, store)
    if "application" in graphs or native_graphs(graphs) or \
            os.path.isfile(os.path.join(app_dir, LEGACY)):
        return False
    return "posting" in graphs or any(os.path.isfile(os.path.join(app_dir, name))
                                      for name in FILE_MADE)


def refuse_if_sent(app_dir, name, store=None, graph=False):
    """Raise Frozen when `name` must not change: the application was sent (records.refuse_if_sent)."""
    from ....application.timeline import records as T

    T.refuse_if_sent(app_dir, name, store, graph, records=records())


def write_app_graphs(app_dir, graphs, store=None):
    """Replace the application's graphs in one update; the names written (records.write_app_graphs).

    Raises:
        Unwritable: nothing was written; Frozen when the application is sent.
    """
    from ....application.timeline import records as T

    return T.write_app_graphs(app_dir, graphs, store, records=records())


def write_app_file(app_dir, name, text, store=None):
    """Write the document `name` in the folder; the path (records.write_app_file).

    Raises:
        Unwritable: nothing was written; Frozen when the application is sent.
    """
    from ....application.timeline import records as T

    return T.write_app_file(app_dir, name, text, store, records=records())


def remove_app_file(app_dir, name, store=None):
    """Remove `name` from the folder if it is there; True when one was (records.remove_app_file).

    Raises:
        Unwritable: Frozen when the application is sent, else it could not be removed.
    """
    from ....application.timeline import records as T

    return T.remove_app_file(app_dir, name, store, records=records())


def freeze(root, app_dir, plan, short_bytes, submitted, channel, documents):
    """(Sealed, None), or (None, the lines saying why not) (records.freeze over the
    workspace's load and the engine's queries)."""
    from ....application.timeline import records as T
    from .record import load
    from ....infra.oxigraph.queries import OxigraphQueries

    return T.freeze(root, app_dir, plan, short_bytes, submitted, channel, documents,
                    load=load, records=records(), queries=OxigraphQueries)


def write_frozen(root, sealed, final):
    """Write what freeze() validated; the application graph's name (records.write_frozen)."""
    from ....application.timeline import records as T

    return T.write_frozen(root, sealed, final, records=records())


class Applications:
    """An application's record graphs, as this module binds them, looked up at each call.

    A test patches write_frozen here, so the freeze is handed this rather than the
    functions themselves: the patch is then what the freeze writes with.
    """

    def frozen(self, app_dir):
        """What says `app_dir` was frozen, else None (frozen above)."""
        return frozen(app_dir)

    def has_record(self, app_dir, kind):
        """Whether the application holds its `kind` graph (has_record above)."""
        return has_record(app_dir, kind)

    def selection(self, app_dir):
        """None for an application made from files; for a graph-native one (its posting
        graph holds the advert's lines, Ruling 11), its ref and its stored selection as
        resume.json's dict, or None in the dict's place when it stores none."""
        from ....application.posting.native import native_graphs
        from ....application.render.selection import REF
        from ....domain.resume.selection import doc_of

        from ....infra.files import workspace_of_app

        graphs = app_graphs(app_dir)
        if not native_graphs(graphs):
            return None
        # As the disk spells the folder: the graphs are named so, however it was typed.
        root, rel = workspace_of_app(app_dir)
        here = os.path.join(root, *rel.split("/")) if root and rel else app_dir
        ref = os.path.join(os.path.abspath(here), REF)
        return ref, (doc_of(graphs["resume"]) if graphs.get("resume") else None)

    def freeze(self, root, app_dir, plan, short_bytes, submitted, channel, documents):
        """(Sealed, None) or (None, the lines saying why not) (freeze above)."""
        return freeze(root, app_dir, plan, short_bytes, submitted, channel, documents)

    def write_frozen(self, root, sealed, final):
        """Write what freeze() validated; the graph's name (write_frozen above)."""
        return write_frozen(root, sealed, final)


class Gates:
    """jsk.cli's gate plumbing, as application.timeline.freeze.gate runs it.

    Looked up in jsk.cli at each call, so `jsk app freeze`, `jsk resume check` and `jsk
    resume ship` run one set of gates and not three copies of it.
    """

    def run(self, app_dir, record, only):
        """Every `jsk resume check` result over the documents `only`, the render gate last."""
        from .... import cli

        return cli.gate_results(app_dir, record, only=only)

    def read(self, app_dir, only):
        """The paths of `only` that those gates read."""
        from .... import cli

        extensions = sorted({ext for _, _, exts in cli.DOC_GATES for ext in exts} | {".pdf"})
        return cli.rendered_documents(app_dir, extensions, only)

    def letter(self, path, record, name):
        """The letter gate's result over `path`, against the application's resume.json or,
        graph-native, its selection's ref."""
        from .... import cli
        from ....application.gates.run_gates import step
        from ....application.render.selection import parse_ref
        from ..gates.check import Shown, contained

        found = parse_ref(record)
        against = found[1].split("/", 1)[1] if found else cli.DEFAULT_RECORD
        return Shown(step("letter gate", f"letter.py {name} --record {against}",
                          *contained("letter.py", [path, "--record", record])))

    def failed(self, results):
        """Whether any result is not a pass."""
        from .... import cli

        return bool(cli.worst_exit(results))


def freeze_app(app_dir, workspace, submitted, channel, named, *, gated=None):
    """The FreezeResult of freezing `app_dir`: checked, planned, gated, then written in the
    record's turn (application.timeline.freeze).

    Args:
        app_dir: the application directory, inside `workspace`'s applications/.
        workspace: the workspace root.
        submitted: YYYY-MM-DD, or "false" for one held back.
        channel: where it was sent.
        named: the --doc paths, or None to list the directory's documents.
        gated: results -> None, called with every gate's step (each a Shown dict) before
            the freeze decides on them: the CLI prints them there, and a tool keeps them.

    Returns:
        The FreezeResult. Runs every gate; renames the directory and writes the store.

    Raises:
        FreezeRefused: frozen already, nothing to freeze, a gate failed, or the record
            would not validate - nothing renamed or written.
        FreezeLanded: the record was written and the store failed after it.
    """
    from ....application.timeline import freeze as F
    from ....infra import files
    from ....infra.oxigraph import db
    from ....infra.oxigraph import record as R
    from .resume import from_path

    checked = F.check(app_dir, record=Applications(), build=from_path)
    planned = F.plan(app_dir, submitted, named, checked, spelled=files.spelled)
    done = F.gate(planned, Gates())
    if gated is not None:
        gated(done.results)
    if done.refusal:
        raise F.FreezeRefused(*done.refusal)
    # The turn before the record is read: what freeze() validates is what it writes over.
    with R.turn(workspace):
        return F.write(workspace, planned, submitted, channel, record=Applications(),
                       files=files, store_errors=(db.StoreError,))


def frozen_record(root, graph):
    """What the frozen application graph `graph` holds that a caller checks: its
    recordSha256 (or None), the bullets it carried as curies, and its documents, sorted.

    Read back from the store rather than from what the freeze was given, so what is
    reported is what was written.
    """
    from ....domain import ontology as O
    from ....domain.record.writer import curie
    from ....infra.oxigraph import db

    held = {"recordSha256": None, "carried": [], "documents": []}
    for t in db.read(root).get(graph) or ():
        name = t.predicate.value.removeprefix(O.J)
        if name == "recordSha256":
            held["recordSha256"] = t.object.value
        elif name == "carried":
            held["carried"].append(curie(t.object.value))
        elif name == "document":
            held["documents"].append(t.object.value)
    return {k: sorted(v) if isinstance(v, list) else v for k, v in held.items()}


def add_event(root, app_dir, kind, date, channel, note, due, today):
    """The EventResult of adding one event to a frozen application's record, inside this
    process's turn (application.timeline.add_event).

    Args:
        root: the workspace root.
        app_dir: the application directory.
        kind, date, channel, note, due: the event, as `jsk app event`'s flags give it.
        today: the date the call runs on, read once at the edge.

    Returns:
        The EventResult. Writes the application graph.

    Raises:
        EventRefused: nothing was written, and why.
        EventLanded: the event was written and the store failed after it.
    """
    from ....application.timeline.add_event import add_event as added
    from ....domain.timeline import events
    from ....infra.files import file_name
    from ....infra.oxigraph import record as R
    from .record import load

    with R.turn(root):
        return added(root, app_dir, kind, date, channel, note, due, today, load=load,
                     name_of=file_name, event_quads=events.event_quads,
                     write_graphs=R.write_graphs)


def drop_app(app_dir, *, reason, today, dry_run):
    """The Dropped result of setting an unsent application aside, inside this process's turn
    (application.timeline.drop); a dry run takes no turn and writes nothing.

    Args:
        app_dir: the application's directory, `<workspace>/applications/<stem>`.
        reason: why, for DROPPED.txt, or None.
        today: the date the call runs on, read once at the edge.
        dry_run: say what would be removed and moved, and write nothing.

    Returns:
        The Dropped result. Removes the graphs and moves the folder, unless `dry_run`.

    Raises:
        NotAnApplication, DropRefused, DropLanded: as application.timeline.drop.drop says.
    """
    from ....application.timeline.drop import NotAnApplication, drop
    from ....infra import files
    from ....infra.oxigraph import db
    from ....infra.oxigraph import record as R
    from .record import load

    root = records().workspace_of_app(app_dir)[0]
    if root is None or not db.exists(root):
        raise NotAnApplication(f"{app_dir} is not an application in a workspace",
                               "pass applications/<stem>, in the applications/ folder beside "
                               "career/store/")
    with R.turn(root, dry_run):
        return drop(app_dir, reason=reason, today=today, dry_run=dry_run, load=load,
                    records=records(), files=files, store_errors=(db.StoreError,))
