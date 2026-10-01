"""An application's record, bound: application/timeline/records.py over the folder on disk
and career/store/ (infra.oxigraph.applications.StoredApplications).

Each function keeps the signature its callers use, with no `records` to pass. A test
patches write_frozen here, and the freeze adapter looks it up here at each call.
"""


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
    from ....graph import store as S
    from ....infra.oxigraph.queries import OxigraphQueries

    return T.freeze(root, app_dir, plan, short_bytes, submitted, channel, documents,
                    load=S.load, records=records(), queries=OxigraphQueries)


def write_frozen(root, sealed, final):
    """Write what freeze() validated; the application graph's name (records.write_frozen)."""
    from ....application.timeline import records as T

    return T.write_frozen(root, sealed, final, records=records())
