"""`jsk kb pack`: a starter pack of capabilities, drafted as a changeset for the career.

data/capabilities.ttl holds capabilities and domains with the wordings postings use and
the counts-as edges that are true for anyone. It is never loaded as vocabulary: the
shipped vocabulary is technologies only (shapes.shipped_vocabulary), because a capability
edge is judgement. The pack is a proposal a person reads and adopts into their own
career, where the judgement is theirs.

`draft` works out what the pack adds to this workspace and nothing else:

- a concept the workspace lacks comes whole;
- one it has with the same class gets only the labels and edges it lacks;
- one it has with another class is skipped - the record's class stands;
- a label that already names another concept (a label, a former label or its id, after
  normalising) is skipped - `label-clash` would warn of it, and matching would ask;
- an edge whose target neither has, or that would make a cycle or cross a distinct wall,
  is skipped - `counts-as-cycle` and `wall-crossed` would fail on it.

Everything skipped is said, so the person can decide it by hand. Nothing is applied:
the changeset goes through `jsk kb apply --dry-run` like any other.

Where the pack file is and reading it are graph/pack.py's; this is the pack's logic.
"""
from collections import defaultdict
from dataclasses import dataclass, field

from .. import ontology as O

NAMES = ("label", "former")
EDGES = ("isA", "partOf", "implies", "distinct")
COUNTS_AS = ("isA", "partOf", "implies")


def node(iri):
    """The named node for `iri`.

    Args:
        iri: the IRI, as a string.

    Returns:
        a pyoxigraph NamedNode.
    """
    import pyoxigraph as ox
    return ox.NamedNode(iri)


def slug(iri):
    """A concept's id as words.

    Args:
        iri: a c: concept IRI.

    Returns:
        what follows the c: namespace, e.g. "ai-agent-design".
    """
    return iri[len(O.C):]


def cur(iri):
    """An IRI as the draft's lines name it.

    Args:
        iri: the IRI, as a string.

    Returns:
        the writer's CURIE for it.
    """
    from .writer import curie
    return curie(iri)


# --- the workspace's concepts ----------------------------------------------------------

def classes(store):
    """{concept iri: {class names}} as the career and the vocabulary state them."""
    from ..naming import graph_iri

    homes = {graph_iri(f) for f, p in store.parsed.items() if p.kind in ("kb", "vocabulary")}
    out = defaultdict(set)
    for r in store.select(f"""PREFIX j: <{O.J}> SELECT ?c ?t ?g WHERE {{ GRAPH ?g {{ ?c a ?t }}
            FILTER(STRSTARTS(STR(?c), "{O.C}")) }}"""):
        if r["g"].value in homes and r["t"].value.startswith(O.J):
            out[r["c"].value].add(r["t"].value[len(O.J):])
    return out


def names(store, skip=()):
    """{normalised name: {concept iris}}: every label and former label, and every
    concept's id, which matching reads as a name too. `skip`: concepts left out."""
    out = defaultdict(set)
    for iri in store.homes:
        if iri.startswith(O.C) and iri not in skip:
            out[slug(iri)].add(iri)
    for r in store.select(f"""PREFIX j: <{O.J}> SELECT ?c ?l WHERE {{ ?c j:label|j:former ?l
            FILTER(STRSTARTS(STR(?c), "{O.C}")) }}"""):
        if r["c"].value not in skip:
            out[O.norm(r["l"].value)].add(r["c"].value)
    return out


def edges(store):
    """{(concept, edge name, concept)} over the workspace, the kb's narrowing applied."""
    rows = store.select(f"""PREFIX j: <{O.J}> SELECT ?a ?k ?b WHERE {{ GRAPH ?g {{ ?a ?k ?b }}
            FILTER(?g != j:derived && ?k IN ({', '.join('j:' + e for e in EDGES)})) }}""")
    return {(r["a"].value, r["k"].value[len(O.J):], r["b"].value) for r in rows}


class Walls:
    """The counts-as graph and its distinct walls, to ask what one more edge would do."""

    def __init__(self, triples):
        """Index the workspace's edges.

        Args:
            triples: (concept, edge name, concept) for every edge the workspace holds.
        """
        self.up, self.apart = defaultdict(set), set()
        for a, k, b in triples:
            self.put(a, k, b)

    def put(self, a, k, b):
        """Add the edge a k b: a distinct wall both ways, or a counts-as step up.

        Args:
            a, b: concept IRIs.
            k: the edge's name; one that is neither distinct nor counts-as is ignored.

        Returns:
            None.
        """
        if k == "distinct":
            self.apart |= {(a, b), (b, a)}
        elif k in COUNTS_AS:
            self.up[a].add(b)

    def reach(self, a):
        """a and everything a counts as."""
        seen, todo = {a}, [a]
        while todo:
            for b in self.up[todo.pop()] - seen:
                seen.add(b)
                todo.append(b)
        return seen

    def below(self, a):
        """a and everything that counts as a."""
        return {x for x in set(self.up) | {a} if a in self.reach(x)}

    def trouble(self, a, k, b):
        """Why a k b cannot be added, or None."""
        if k == "distinct":
            if b in self.reach(a) or a in self.reach(b):
                return "one already counts as the other"
            return None
        if a in self.reach(b):
            return f"{cur(b)} already counts as {cur(a)}: a cycle"
        low, high = self.below(a), self.reach(b)
        for x, y in sorted(self.apart):
            if x in low and y in high:
                return f"{cur(x)} would count as {cur(y)}, and they are distinct"
        return None


# --- the pack --------------------------------------------------------------------------

def pack_of(quads):
    """A starter pack as `draft` reads it.

    Args:
        quads: the pack file's quads, as the codec parsed them.

    Returns:
        {concept iri: {"class": name, "label": [(pred, text)], "edges": [(name, iri)]}},
        each list sorted.
    """
    out = defaultdict(lambda: {"class": None, "label": [], "edges": []})
    for q in quads:
        s, p, o = q.subject.value, q.predicate.value, q.object
        if p == O.RDF_TYPE:
            out[s]["class"] = o.value[len(O.J):]
        elif p[len(O.J):] in NAMES:
            out[s]["label"].append((p[len(O.J):], o.value))
        elif p[len(O.J):] in EDGES:
            out[s]["edges"].append((p[len(O.J):], o.value))
    for e in out.values():
        e["label"].sort()
        e["edges"].sort()
    return dict(out)


@dataclass
class Draft:
    """What a pack adds to the workspace: the triples, the concepts new to it and those
    enriched, and a line for each thing skipped."""

    add: list = field(default_factory=list)       # (s, p, o) pyoxigraph terms
    added: list = field(default_factory=list)     # concept iris new to the workspace
    enriched: list = field(default_factory=list)  # concept iris it gains labels or edges on
    skipped: list = field(default_factory=list)   # a line each


def draft(store, pack):
    """What `pack` adds to the workspace, and what it skips and why."""
    import pyoxigraph as ox

    have, said, known = classes(store), names(store), edges(store)
    walls = Walls(known)
    out, taken = Draft(), set()
    for x in sorted(pack):
        cls = pack[x]["class"]
        if x in store.homes and cls not in have.get(x, set()):
            was = " or ".join(sorted(have.get(x, ()))) or "no class"
            out.skipped.append(f"{cur(x)}: the pack has it as a {cls}, the record as {was} - "
                               "kept as the record has it")
            continue
        taken.add(x)
        said[slug(x)].add(x)
    for x in sorted(taken):
        new = x not in store.homes
        adds: list = [(node(x), node(O.RDF_TYPE), node(O.J + pack[x]["class"]))] if new else []
        for pred, text in pack[x]["label"]:
            owners = said[O.norm(text)]
            if x in owners:
                continue
            if owners:
                out.skipped.append(f"{pred} {text!r} on {cur(x)}: it already names "
                                   + ", ".join(cur(o) for o in sorted(owners)))
                continue
            owners.add(x)
            adds.append((node(x), node(O.J + pred), ox.Literal(text)))
        for k, y in pack[x]["edges"]:
            if (x, k, y) in known:
                continue
            if y in pack and y not in taken:
                why = f"{cur(y)} was skipped"
            elif y not in taken and y not in store.homes:
                why = f"{cur(y)} is in neither the pack nor the record"
            else:
                why = walls.trouble(x, k, y)
            if why:
                out.skipped.append(f"{cur(x)} j:{k} {cur(y)}: {why}")
                continue
            walls.put(x, k, y)
            adds.append((node(x), node(O.J + k), node(y)))
        if adds:
            (out.added if new else out.enriched).append(x)
            out.add += adds
    return out


# --- a changeset, as TriG --------------------------------------------------------------

def trig(base, summary, graphs, entries=(), comments=()):
    """A changeset's text: the header, then each graph that has triples. `graphs` maps
    op:add / op:set / op:retire / op:delete names to (s, p, o) terms; `entries` are the
    iris op:delete removes whole."""
    import pyoxigraph as ox

    from .writer import INDENT, Subjects, block, literal

    out = [f"@prefix {name}: <{ns}> ." for name, ns in O.PREFIXES]
    out += [f"@prefix op: <{O.OP}> .", ""]
    out += [f"# {line}" for line in comments] + ([""] if comments else [])
    out += [f"op:changeset op:base {base} ; op:summary {literal(ox.Literal(summary))} .", ""]
    for name in ("delete", "set", "add", "retire"):
        triples = graphs.get(name, [])
        gone = sorted(entries) if name == "delete" else []
        if not triples and not gone:
            continue
        out.append(f"op:{name} {{")
        sub = Subjects([ox.Triple(s, p, o) for s, p, o in triples])
        for s in sorted(sub.props):
            parts = ["main"] + sorted({p.section for p in sub.cls[s].preds.values() if p.section})
            for part in parts:
                b = block(sub, s, part)
                if b:
                    # Indented for reading - except a long string, whose lines are its text.
                    out += [b[0]] if '"""' in b[0] else [INDENT + x for x in b[0].split("\n")]
        out += [f"{INDENT}{cur(e)} a op:Entry ." for e in gone]
        out += ["}", ""]
    return "\n".join(out).rstrip("\n") + "\n"
