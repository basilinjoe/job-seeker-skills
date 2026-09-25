"""The workspace in memory: every record file loaded, types derived, rules run.

Each file is its own named graph, so a finding can say which file it is in; derived
triples go in j:derived, which is never written; queries run over the union. Loading
never raises on bad content - it reports, and the caller decides what a FAIL stops.
"""
import glob
import os
from dataclasses import dataclass, field
from urllib.parse import quote

from . import ontology as O
from .io import GraphError, parse, parse_text

SHIPPED_VOCABULARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "vocabulary.ttl")


def workspace_files(root, vocabulary=SHIPPED_VOCABULARY):
    """The record files under a workspace root, in a fixed order. Missing ones are absent."""
    found = [os.path.join(root, "career", "kb.ttl"), os.path.join(root, "career", "log.ttl")]
    for pattern in ("posting.ttl", "application.ttl"):
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
    parsed: dict = field(default_factory=dict)      # file -> Parsed
    homes: dict = field(default_factory=dict)       # subject iri -> first file defining it
    definitions: dict = field(default_factory=dict)  # subject iri -> every file, load order
    unmatched: list = field(default_factory=list)   # kb.ttl narrowing quads that removed nothing
    ox: object = None

    def select(self, sparql):
        """Rows of a SELECT over the union graph, as {variable: term}."""
        result = self.ox.query(sparql, use_default_graph_as_union=True)
        names = [var.value for var in result.variables]
        return [{n: sol[n] for n in names if sol[n] is not None} for sol in result]

    def graph(self, file):
        """One file's triples, for the writer - as parsed, never read back out of
        Oxigraph, which keeps numbers by value ("8.40" would come back as 8.4)."""
        return self.parsed[file].quads

    def file_of(self, iri):
        return self.homes.get(iri)

    def line_of(self, iri, file=None):
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


def file_name(path, root):
    """How findings name a file: relative to the workspace, forward slashes. A file outside
    it - the shipped vocabulary - is named by its basename, including when it is on another
    Windows drive, where relpath raises rather than answering."""
    try:
        name = os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return os.path.basename(path)
    return os.path.basename(path) if name.startswith("../") else name


def graph_iri(name):
    """The named graph a file's triples live in. Percent-encoded: a hand-made folder can
    hold a space, and an IRI cannot."""
    return "file:" + quote(name, safe="/-._~")


def load(root, vocabulary=SHIPPED_VOCABULARY, files=None, texts=None):
    """Load, derive, validate and close over a workspace. `files` overrides discovery;
    `texts` ({file name: text}) stands in for what is on disk - how `jsk kb apply`
    validates the record it is about to write before writing it."""
    import pyoxigraph as ox

    from .rules import tier2
    from .shapes import Finding, tier1

    store = Store(os.path.abspath(root), ox=ox.Store())
    paths = files if files is not None else workspace_files(root, vocabulary)
    texts = texts or {}
    names = {file_name(p, store.root) for p in paths}
    paths = list(paths) + [os.path.join(store.root, n) for n in sorted(texts) if n not in names]
    derived = ox.NamedNode(O.DERIVED)
    for path in paths:
        name = file_name(path, store.root)
        try:
            parsed = parse_text(texts[name], name) if name in texts else parse(path)
        except GraphError as e:
            store.findings.append(Finding("syntax", "FAIL", name, e.line or 0, "",
                                          str(e).split(": ", 1)[-1], e.fix))
            continue
        except OSError as e:
            raise GraphError(f"{name}: {e.strerror}", "check the path", name) from None
        parsed.file = name
        store.parsed[name] = parsed
        graph = ox.NamedNode(graph_iri(name))
        store.ox.extend(ox.Quad(q.subject, q.predicate, q.object, graph) for q in parsed.quads)
        store.findings += tier1(parsed)
        for iri in dict.fromkeys(q.subject.value for q in parsed.quads
                                 if isinstance(q.subject, ox.NamedNode)):
            store.homes.setdefault(iri, name)
            store.definitions.setdefault(iri, []).append(name)
    narrow(store)
    derive_types(store, derived)
    store.findings += tier2(store)
    materialise_paths(store)
    return store


# kb.ttl predicate -> the shipped predicates it removes
NARROWS = {"unlabel": ("label", "former"), "unlink": ("isA", "partOf")}


def narrow(store):
    """kb.ttl's `unlabel` and `unlink`, applied to the shipped vocabulary - in memory only.

    A shipped entry can be wrong for one person's field ("Go" is never the language in
    theirs). The shipped file is not theirs to edit, and a copy of it would stop tracking
    releases, so the removal is a statement in kb.ttl that the loader honours. One that
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
