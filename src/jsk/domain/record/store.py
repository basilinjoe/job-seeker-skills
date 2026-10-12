"""The workspace in memory: every record graph loaded, types derived, rules run.

Each graph is kept apart, so a finding can say which graph it is in (`kb`,
`applications/acme/posting`); derived triples go in j:derived, which is never written;
queries run over the union. The engine holding them is a GraphEngine the loader was given
(application/record/load.py), never opened here.
"""
from dataclasses import dataclass, field

from .. import ontology as O
from ..naming import graph_iri

# For the checker alone: importing `typing` costs every command ~3 ms it never uses.
TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any

# Graphs in the order the file loader met their files: the career, its log, then each
# kind of application graph. The first graph defining an id is its home, and a duplicate
# is reported where it was added - in the application, not in the career it came from.
ORDER = {"kb": 0, "log": 1, "posting": 2, "application": 3, "gaps": 4, "review": 5, "resume": 6}

# career predicate -> the shipped predicates it removes
NARROWS = {"unlabel": ("label", "former"), "unlink": ("isA", "partOf")}


@dataclass
class Store:
    """A loaded workspace: its graphs as parsed, its findings, and the engine they are in."""

    root: str
    findings: list = field(default_factory=list)
    parsed: dict = field(default_factory=dict)      # graph name -> Parsed
    homes: dict = field(default_factory=dict)       # subject iri -> first graph defining it
    definitions: dict = field(default_factory=dict)  # subject iri -> every graph, load order
    unmatched: list = field(default_factory=list)   # kb narrowing quads that removed nothing
    # The record is graphs - out of career/store/, or the candidate a write validates in
    # their place - not files: so no lines, no comments, and no hash for the log to check.
    stored: bool = False
    # A ports.engine.GraphEngine; None in a Store built only to report findings.
    engine: "Any" = None

    @property
    def ox(self):
        """The engine, by the name it had while it was a pyoxigraph Store itself."""
        return self.engine

    def select(self, sparql):
        """Rows of a SELECT over the union graph, as {variable: term}."""
        return self.engine.select(sparql)

    def graph(self, name):
        """One graph's triples, as loaded: a stored graph's as career/store/ keeps them
        (numbers by value - `8.4`, never `8.40`), a file's as parsed. Never read back out
        of the engine, which keeps numbers by value too and would turn a file's `8.40`
        into `8.4` unreported."""
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
        """Every subject iri some graph defines."""
        return self.homes.keys()

    def fails(self):
        """The FAIL findings, in the order they were found."""
        return [f for f in self.findings if f.severity == "FAIL"]

    def warns(self):
        """The WARN findings, in the order they were found."""
        return [f for f in self.findings if f.severity == "WARN"]

    def report(self):
        """The findings as a domain.gates.report.Report, a syntax error first."""
        from ..gates.report import Report

        rep = Report()
        # A syntax error first: until that file parses, what follows is provisional.
        for f in sorted(self.findings, key=lambda f: (f.rule != "syntax", f.file, f.line, f.rule)):
            (rep.fail if f.severity == "FAIL" else rep.warn)(f.text())
        return rep


def load_order(name):
    """The key graphs load in: by kind as ORDER ranks it, then by name."""
    return ORDER.get(name.rsplit("/", 1)[-1], len(ORDER)), name


def parsed_graph(name, triples):
    """A graph out of the store as a Parsed: triples, no text - so no lines and no comments."""
    import pyoxigraph as ox

    from ..ontology import kind_of
    from .parsed import Parsed

    quads = [ox.Quad(t.subject, t.predicate, t.object) for t in triples]
    return Parsed(name, kind_of(name), quads, {}, [])


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
                    if store.engine.contains(quad):
                        store.engine.remove(quad)
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
    store.engine.add(quads)


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
        store.engine.update(f"{pre}{head} WHERE {{ {where} {pid} }}")
