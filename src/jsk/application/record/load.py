"""Loading a workspace: its graphs into an engine, types derived, every rule run.

Loading never raises on bad content - it reports, and the caller decides what a FAIL
stops. Where the graphs come from and what engine holds them are the caller's to give
(ports.workspace.WorkspaceSource, ports.engine.GraphEngine), and so is where the rules
read an application's own files from (ports.advert.AdvertSource): graph/store.py binds the
real ones.
"""
from ...domain import ontology as O
from ...domain.naming import graph_iri, short_name
from ...domain.record.parsed import GraphError, Unreadable
from ...domain.record.store import (Store, derive_types, load_order, materialise_paths, narrow,
                                    parsed_graph)


def load(root, vocabulary, files, graphs, *, source, new_engine, adverts):
    """Load, derive, validate and close over a workspace.

    Args:
        root: the workspace root.
        vocabulary: the shipped vocabulary's file, loaded beside a stored record; None or a
            path that is not a file leaves it out.
        files: None to read the record from career/store/; else the files to read instead,
            without opening the store - the import's front end, and `jsk kb load`
            validating what it imports with the vocabulary alone.
        graphs: {name: triples, or None to drop} standing in for the store's graphs - how a
            write validates the record it is about to write before writing it.
        source: the workspace (ports.workspace.WorkspaceSource).
        new_engine: makes an empty ports.engine.GraphEngine.
        adverts: the ports.advert.AdvertSource the rules read posting.md through.

    Returns:
        The loaded domain.record.store.Store, its findings every rule's.

    Raises:
        GraphError: a record that cannot be read at all - still laid out as files, a store
            that will not open, a file that cannot be read.
    """
    import pyoxigraph as ox

    from ...domain.record.shapes import Finding, tier1
    from ...domain.record.rules import tier2

    store = Store(source.absolute(root), engine=new_engine())
    # Keyed by graph name, whichever a caller passed: `career/kb.ttl` is `kb`.
    graphs = {short_name(n): t for n, t in (graphs or {}).items()}
    record = None if files is not None else source.record_graphs(store.root)
    # A career handed over as graphs is the record as the store will hold it (`jsk kb
    # load` validating what it imports), whether or not a store exists yet.
    stored = record is not None or "kb" in graphs
    if record is not None:
        record.update(graphs)
        names = {n for n in record if record[n] is not None}
        items: list = [(n, None) for n in sorted(names, key=load_order)]
        if vocabulary and source.is_file(vocabulary):
            items.append((source.graph_name(vocabulary, store.root), vocabulary))
    else:
        items = [(source.graph_name(p, store.root), p) for p in files or ()]
        if graphs:
            record = dict(graphs)
            items = [(n, p) for n, p in items if n not in record]
            items += [(n, None) for n in sorted(record, key=load_order)
                      if record[n] is not None]
    derived = ox.NamedNode(O.DERIVED)
    for name, path in items:
        try:
            if record is not None and name in record:
                parsed = parsed_graph(name, record[name])
            else:
                parsed = source.parse(path)
        except GraphError as e:
            detail = str(e).split(": ", 1)[-1]
            if path:
                # A file the import reads: the person fixes the file, so it is named.
                detail = f"{source.file_name(path, store.root)}: {detail}"
            store.findings.append(Finding("syntax", "FAIL", name, e.line or 0, "", detail,
                                          e.fix))
            continue
        except Unreadable as e:
            raise GraphError(str(e), e.fix, name) from None
        parsed.file = name
        store.parsed[name] = parsed
        graph = ox.NamedNode(graph_iri(name))
        store.engine.add(ox.Quad(q.subject, q.predicate, q.object, graph) for q in parsed.quads)
        store.findings += tier1(parsed)
        for iri in dict.fromkeys(q.subject.value for q in parsed.quads
                                 if isinstance(q.subject, ox.NamedNode)):
            store.homes.setdefault(iri, name)
            store.definitions.setdefault(iri, []).append(name)
    store.stored = stored
    narrow(store)
    derive_types(store, derived)
    store.findings += tier2(store, adverts, source.record_state)
    materialise_paths(store)
    return store
