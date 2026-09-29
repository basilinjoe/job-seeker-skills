"""The workspace in memory: every record graph loaded, types derived, rules run.

The record comes out of career/store/ (db.py) into an in-memory store, graph by graph,
so a finding can say which graph it is in (`kb`, `applications/acme/posting`); the
shipped vocabulary is read from its file each time; derived triples go in j:derived,
which is never written; queries run over the union. Loading never raises on bad
content - it reports, and the caller decides what a FAIL stops.

A workspace still laid out as files (career/kb.ttl, applications/*/*.ttl) is read only
by the one-time import (legacy.py, `jsk kb load`), which names its files; loaded any other
way it is refused, with that import as the fix.
"""
import glob
import os
from dataclasses import dataclass, field

from . import ontology as O
from .io import GraphError, Unreadable, parse

# For the checker alone: importing `typing` costs every command ~3 ms it never uses.
TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any

SHIPPED_VOCABULARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "vocabulary.ttl")


def workspace_files(root, vocabulary=SHIPPED_VOCABULARY):
    """The record files under a workspace root still laid out as files, in a fixed order -
    what the import reads. Missing ones are absent."""
    found = [os.path.join(root, "career", "kb.ttl"), os.path.join(root, "career", "log.ttl")]
    for pattern in ("posting.ttl", "application.ttl", "gaps.ttl"):
        # Escaped: a root named "jobs [2026]" is a glob character class, and would
        # silently match no application at all.
        found += sorted(glob.glob(os.path.join(glob.escape(str(root)), "applications", "*",
                                               pattern)))
    found = [f for f in found if os.path.isfile(f)]
    if vocabulary and os.path.isfile(vocabulary):
        found.append(vocabulary)
    return found


@dataclass
class Store:
    root: str
    findings: list = field(default_factory=list)
    parsed: dict = field(default_factory=dict)      # graph name -> Parsed
    homes: dict = field(default_factory=dict)       # subject iri -> first graph defining it
    definitions: dict = field(default_factory=dict)  # subject iri -> every graph, load order
    unmatched: list = field(default_factory=list)   # kb narrowing quads that removed nothing
    # The record is graphs - out of career/store/, or the candidate a write validates in
    # their place - not files: so no lines, no comments, and no hash for the log to check.
    stored: bool = False
    # The pyoxigraph.Store load() fills; None in a Store built only to report findings.
    # Any, because pyoxigraph is imported inside the functions that need it, never here.
    ox: "Any" = None

    def select(self, sparql):
        """Rows of a SELECT over the union graph, as {variable: term}."""
        result = self.ox.query(sparql, use_default_graph_as_union=True)
        names = [var.value for var in result.variables]
        return [{n: sol[n] for n in names if sol[n] is not None} for sol in result]

    def graph(self, name):
        """One graph's triples, as loaded: a stored graph's as career/store/ keeps them
        (numbers by value - `8.4`, never `8.40`), a file's as parsed. Never read back out
        of the in-memory store, which keeps numbers by value too and would turn a file's
        `8.40` into `8.4` unreported."""
        return self.parsed[name].quads

    def file_of(self, iri):
        """The graph that first defines `iri` - its name, which findings print."""
        return self.homes.get(iri)

    def line_of(self, iri, file=None):
        """The line `iri` starts on in a file the import reads; 0 in a stored graph, which has
        no lines, and a finding at line 0 prints none."""
        file = file or self.homes.get(iri)
        return self.parsed[file].lines.get(iri, 0) if file in self.parsed else 0

    def defined(self):
        return self.homes.keys()

    def fails(self):
        return [f for f in self.findings if f.severity == "FAIL"]

    def warns(self):
        return [f for f in self.findings if f.severity == "WARN"]

    def report(self):
        """The findings as a gates.report.Report, for show() and the gates' output."""
        from ..gates.report import Report

        rep = Report()
        # A syntax error first: until that file parses, what follows is provisional.
        for f in sorted(self.findings, key=lambda f: (f.rule != "syntax", f.file, f.line, f.rule)):
            (rep.fail if f.severity == "FAIL" else rep.warn)(f.text())
        return rep


def rel(path, root):
    """`path` relative to `root`, forward slashes - or, on another Windows drive, where
    relpath raises rather than answering, the absolute path with forward slashes."""
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def inside(path, root):
    """Is `path` (followed through links) under `root`? False across drives, where
    commonpath raises."""
    here, top = (os.path.normcase(os.path.realpath(p)) for p in (path, root))
    try:
        return os.path.commonpath([here, top]) == top
    except ValueError:
        return False


def file_name(path, root):
    """How findings name a file: relative to the workspace, forward slashes. A file outside
    it - the shipped vocabulary - is named by its basename, including when it is on another
    Windows drive."""
    name = rel(path, root)
    return os.path.basename(path) if name.startswith("../") or os.path.isabs(name) else name


def graph_name(path, root):
    """The record graph a file holds, by the name the store gives it and findings use:
    career/kb.ttl is `kb`, career/log.ttl `log`, applications/<stem>/posting.ttl
    `applications/<stem>/posting` (and application, gaps), the shipped vocabulary
    `vocabulary`. Any other path is named as file_name names it."""
    return short_name(file_name(path, root))


def short_name(name):
    """graph_name for a name already relative to the workspace (`career/kb.ttl`). A graph
    name comes back as it is, so a caller may pass either."""
    if name in ("career/kb.ttl", "career/log.ttl"):
        return name[len("career/"):-len(".ttl")]
    if os.path.basename(name) == "vocabulary.ttl":
        return "vocabulary"
    head, _, tail = name.rpartition("/")
    if head.startswith("applications/") and head.count("/") == 1 and \
            tail in ("posting.ttl", "application.ttl", "gaps.ttl"):
        return name[:-len(".ttl")]
    return name


def app_graph(app, kind):
    """The graph name of an application's `kind` (posting, application, gaps). `app` is
    its name relative to the workspace (`applications/<stem>`)."""
    return f"{app.rstrip('/')}/{kind}"


def graph_iri(name):
    """The named graph a record graph's triples live in, in memory as in career/store/:
    the same IRI (db.graph_iri), so a query means the same thing over either."""
    from .db import graph_iri as iri
    return iri(name)


def record_graphs(root):
    """{name: [Triple]} of the workspace's record, from career/store/ - {} in a folder with
    no record yet (before `jsk new`, or a --root that is not one). A career still laid out
    as files is a GraphError: jsk no longer reads or writes those files, and answering from
    them would answer from a record nothing keeps up to date. So is a store that will not
    open - never a traceback."""
    from . import db, legacy

    if not db.exists(root):
        if legacy.has_files(root):
            raise GraphError("the career is still career/kb.ttl, and jsk reads it from "
                             "career/store/ now", "`jsk kb load .` imports the files, once",
                             "career/kb.ttl")
        return {}
    try:
        return db.read(root)
    except db.StoreError as e:
        raise GraphError(str(e), e.fix, "career/store/") from None


# Graphs in the order the file loader met their files: the career, its log, then each
# kind of application graph. The first graph defining an id is its home, and a duplicate
# is reported where it was added - in the application, not in the career it came from.
ORDER = {"kb": 0, "log": 1, "posting": 2, "application": 3, "gaps": 4}


def load_order(name):
    return ORDER.get(name.rsplit("/", 1)[-1], len(ORDER)), name


def parsed_graph(name, triples):
    """A graph out of the store as a Parsed: triples, no text - so no lines and no comments."""
    import pyoxigraph as ox

    from .io import Parsed
    from .ontology import kind_of

    quads = [ox.Quad(t.subject, t.predicate, t.object) for t in triples]
    return Parsed(name, kind_of(name), quads, {}, [])


def load(root, vocabulary=SHIPPED_VOCABULARY, files=None, graphs=None):
    """Load, derive, validate and close over a workspace.

    The record comes from career/store/ (record_graphs). `graphs` ({name: triples, or None
    to drop}) stands in for the store's graphs: how a write validates the record it is
    about to write before writing it. `files` reads those files
    instead and never opens the store - the import's front end (legacy.read_workspace), and
    `jsk kb load` validating what it imports with the vocabulary alone."""
    import pyoxigraph as ox

    from .rules import tier2
    from .shapes import Finding, tier1

    store = Store(os.path.abspath(root), ox=ox.Store())
    # Keyed by graph name, whichever a caller passed: `career/kb.ttl` is `kb`.
    graphs = {short_name(n): t for n, t in (graphs or {}).items()}
    record = None if files is not None else record_graphs(store.root)
    # A career handed over as graphs is the record as the store will hold it (`jsk kb
    # load` validating what it imports), whether or not a store exists yet.
    stored = record is not None or "kb" in graphs
    if record is not None:
        record.update(graphs)
        names = {n for n in record if record[n] is not None}
        items: list = [(n, None) for n in sorted(names, key=load_order)]
        if vocabulary and os.path.isfile(vocabulary):
            items.append((graph_name(vocabulary, store.root), vocabulary))
    else:
        items = [(graph_name(p, store.root), p) for p in files]
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
                parsed = parse(path)
        except GraphError as e:
            detail = str(e).split(": ", 1)[-1]
            if path:
                # A file the import reads: the person fixes the file, so it is named.
                detail = f"{file_name(path, store.root)}: {detail}"
            store.findings.append(Finding("syntax", "FAIL", name, e.line or 0, "", detail,
                                          e.fix))
            continue
        except Unreadable as e:
            raise GraphError(str(e), e.fix, name) from None
        parsed.file = name
        store.parsed[name] = parsed
        graph = ox.NamedNode(graph_iri(name))
        store.ox.extend(ox.Quad(q.subject, q.predicate, q.object, graph) for q in parsed.quads)
        store.findings += tier1(parsed)
        for iri in dict.fromkeys(q.subject.value for q in parsed.quads
                                 if isinstance(q.subject, ox.NamedNode)):
            store.homes.setdefault(iri, name)
            store.definitions.setdefault(iri, []).append(name)
    store.stored = stored
    narrow(store)
    derive_types(store, derived)
    store.findings += tier2(store)
    materialise_paths(store)
    return store


# career predicate -> the shipped predicates it removes
NARROWS = {"unlabel": ("label", "former"), "unlink": ("isA", "partOf")}


def narrow(store):
    """The career's `unlabel` and `unlink`, applied to the shipped vocabulary - in memory only.

    A shipped entry can be wrong for one person's field ("Go" is never the language in
    theirs). The shipped file is not theirs to edit, and a copy of it would stop tracking
    releases, so the removal is a statement in the career that the loader honours. One that
    removes nothing is kept in `store.unmatched` for the narrows-nothing rule: a typo
    there would otherwise change nothing, silently.
    """
    import pyoxigraph as ox

    vocab = [ox.NamedNode(graph_iri(f)) for f, p in store.parsed.items() if p.kind == "vocabulary"]
    for p in store.parsed.values():
        if p.kind != "kb":
            continue
        for q in p.quads:
            name = q.predicate.value[len(O.J):] if q.predicate.value.startswith(O.J) else None
            if name not in NARROWS:
                continue
            removed = False
            for g in vocab:
                for target in NARROWS[name]:
                    quad = ox.Quad(q.subject, ox.NamedNode(O.J + target), q.object, g)
                    if quad in store.ox:
                        store.ox.remove(quad)
                        removed = True
            if not removed:
                store.unmatched.append(q)


def derive_types(store, derived):
    """rdf:type from each k: id's prefix, into j:derived."""
    import pyoxigraph as ox

    rdf_type = ox.NamedNode(O.RDF_TYPE)
    quads = []
    for iri in store.homes:
        name = O.class_of(iri)
        if name and name != "Concept":
            quads.append(ox.Quad(ox.NamedNode(iri), rdf_type, ox.NamedNode(O.J + name), derived))
    store.ox.extend(quads)


def materialise_paths(store):
    """The counts-as closure within the hop limit, as Path nodes in j:derived.

    One way, narrower to broader: `a isA b` gives a path from a to b, never back. Paths
    of 0, 1 and 2 hops; `implied` when an implies edge is on it, since an implied match
    never satisfies a required requirement (P2's rule). Ported from the graph
    simulation's materialise_paths, S0-S7.
    """
    pre = f"PREFIX j: <{O.J}>\nPREFIX c: <{O.C}>\n"
    kinds = "j:isA, j:partOf, j:implies"
    # A path's id is minted from its ends and its hop count, so one found twice is one node.
    pid = ('BIND(IRI(CONCAT("{derived}/path/", MD5(CONCAT(STR(?a), " ", STR(?via), " ", '
           'STR(?b), " ", STR(?hops))))) AS ?p)').format(derived=O.DERIVED)
    head = ("INSERT { GRAPH j:derived { ?p a j:Path ; j:from ?a ; j:to ?b ; j:hops ?hops ; "
            "j:implied ?imp ; j:via ?via } }")
    for where in (
        """{ SELECT DISTINCT ?a WHERE { GRAPH ?g { ?a a ?t }
               FILTER(?g != j:derived && STRSTARTS(STR(?a), STR(c:))) } }
           BIND(?a AS ?b) BIND(?a AS ?via) BIND(0 AS ?hops) BIND(false AS ?imp)""",
        f"""GRAPH ?g {{ ?a ?k ?b }} FILTER(?g != j:derived && ?k IN ({kinds}))
            BIND(?a AS ?via) BIND(1 AS ?hops) BIND(?k = j:implies AS ?imp)""",
        f"""GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}
            FILTER(?g != j:derived && ?h != j:derived && ?a != ?b)
            FILTER(?k1 IN ({kinds}) && ?k2 IN ({kinds}))
            BIND(2 AS ?hops) BIND(?k1 = j:implies || ?k2 = j:implies AS ?imp)""",
    ):
        store.ox.update(f"{pre}{head} WHERE {{ {where} {pid} }}")
