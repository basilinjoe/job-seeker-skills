"""A changeset: the one way an agent changes career/kb.ttl, as TriG.

    @prefix op: <tag:jsk,2026:op#> .
    op:changeset op:base 7 ; op:summary "The payments project, from the braindump" .
    op:add    { k:prj_payments j:name "Payments platform" ; ... }
    op:set    { k:prj_legacy j:strength 2 . }
    op:retire { k:prj_intranet j:reason "Too old to earn a line." . }
    op:delete { k:q_duplicate a op:Entry . k:ach_x j:shows c:java . }

`op:add` adds triples, `op:set` replaces every value of each (subject, predicate) it names,
`op:retire` retires an entry with its reason, `op:delete` removes exact triples - or, for
`a op:Entry`, the whole entry. `op:base` is the log revision the changeset was drafted
against; `op:summary` is what the log says it did.

This module reads a changeset and refuses what can be refused without the career in
front of it. What needs the career - does the entry exist, is it referenced, was it
sent - is edit.py's.
"""
import difflib
from dataclasses import dataclass, field

from . import ontology as O

OP = O.OP
GRAPHS = O.OPS
# Written by jsk, never by a changeset: the header's revision and day, and the format.
WRITTEN_BY_JSK = {"format", "updated", "revision"}


@dataclass(frozen=True)
class Refusal:
    focus: str         # a CURIE, or "" for the whole changeset
    detail: str
    fix: str

    def text(self):
        return f"{self.focus + ' - ' if self.focus else ''}{self.detail}\n        fix: {self.fix}"


class Refused(Exception):
    """Every reason a changeset was not applied - all of them, not the first."""

    def __init__(self, refusals):
        super().__init__(f"{len(refusals)} refusal(s)")
        self.refusals = refusals


@dataclass
class Changeset:
    add: list = field(default_factory=list)       # (s, p, o) pyoxigraph terms
    set: list = field(default_factory=list)
    retire: list = field(default_factory=list)
    delete: list = field(default_factory=list)
    base: int = None
    summary: str = None


def curie(iri):
    if iri.startswith(OP):
        return "op:" + iri[len(OP):]
    from .writer import curie as c
    return c(iri)


def article(cls):
    return ("an " if cls[0] in "AEIOU" else "a ") + cls


def name(t):
    import pyoxigraph as ox
    if isinstance(t, ox.BlankNode):
        return "a blank node"
    return curie(t.value) if isinstance(t, ox.NamedNode) else repr(t.value)


def read(text, file="changeset.trig"):
    """The changeset in `text`. Raises GraphError on a syntax error and Refused on
    anything else wrong with it."""
    import pyoxigraph as ox

    from .io import parse_text

    parsed = parse_text(text, file, kind="changeset")
    cs, refusals = Changeset(), []

    def refuse(focus, detail, fix):
        refusals.append(Refusal(focus, detail, fix))

    for q in parsed.quads:
        s, p, o, g = q.subject, q.predicate, q.object, q.graph_name
        if isinstance(g, ox.DefaultGraph):
            header(cs, s, p, o, refuse)
            continue
        where = g.value[len(OP):] if isinstance(g, ox.NamedNode) and g.value.startswith(OP) else None
        if where not in GRAPHS:
            refuse("", f"a graph named {name(g)}",
                   "changes go in op:add, op:set, op:retire or op:delete")
            continue
        if check(where, s, p, o, refuse):
            getattr(cs, where).append((s, p, o))
    bullets_named(parsed.quads, refuse)
    if refusals:
        raise Refused(refusals)
    return cs


def header(cs, s, p, o, refuse):
    import pyoxigraph as ox

    if s == ox.NamedNode(OP + "changeset") and p.value == OP + "base" and \
            isinstance(o, ox.Literal) and o.value.isdigit():
        cs.base = int(o.value)
    elif s == ox.NamedNode(OP + "changeset") and p.value == OP + "summary" and \
            isinstance(o, ox.Literal) and o.value.strip():
        cs.summary = o.value.strip()
    else:
        refuse(name(s), f"{name(p)} {name(o)} is outside any graph",
               "the default graph holds only op:changeset op:base N ; op:summary \"…\"; "
               "put changes in op:add, op:set, op:retire or op:delete")


def check(where, s, p, o, refuse):
    """True when (s, p, o) may stand in graph `where`; otherwise refuses and says why."""
    import pyoxigraph as ox

    if isinstance(o, ox.BlankNode):
        refuse(name(s), f"{name(p)} points at a blank node",
               "give the entry an id of its own and point at that")
        return False
    if isinstance(s, ox.BlankNode):
        if where != "add":
            refuse("", f"a blank node in op:{where}", "name the entry by its id")
            return False
        return predicate(where, "Achievement", s, p, o, refuse)
    cls = O.class_of(s.value)
    if cls is None:
        refuse(name(s), "not a jsk id", "ids are k:<prefix>_<words>; concepts c:<words-with-dashes>")
        return False
    if "kb" not in O.BY_NAME[cls].kinds:
        home = " or ".join(k + ".ttl" for k in O.BY_NAME[cls].kinds)
        refuse(name(s), f"{article(cls)} lives in {home}", "`jsk kb apply` writes career/kb.ttl only")
        return False
    if where == "delete" and p.value == O.RDF_TYPE and o == ox.NamedNode(OP + "Entry"):
        return True
    return predicate(where, cls, s, p, o, refuse)


def predicate(where, cls, s, p, o, refuse):
    import pyoxigraph as ox

    focus = name(s) if isinstance(s, ox.NamedNode) else "a new bullet"
    if any(isinstance(t, ox.NamedNode) and t.value.startswith(OP) for t in (p, o)):
        refuse(focus, f"{name(p)} {name(o)}: op: terms name graphs and whole entries only",
               "use j: predicates inside a graph; `a op:Entry` only in op:delete")
        return False
    if p.value == O.RDF_TYPE:
        if cls == "Concept" and where in ("add", "set"):
            return True
        refuse(focus, "rdf:type is derived from the id prefix",
               "drop the `a …`; only a c: concept states its class")
        return False
    pname = p.value[len(O.J):] if p.value.startswith(O.J) else None
    preds = O.BY_NAME[cls].preds
    if pname not in preds:
        near = difflib.get_close_matches(pname or p.value, list(preds), n=1)
        refuse(focus, f"{name(p)} is not {article(cls)} predicate",
               f"did you mean j:{near[0]}?" if near else
               f"{article(cls)} takes {', '.join('j:' + x for x in preds)}")
        return False
    if cls == "KB" and pname in WRITTEN_BY_JSK:
        refuse(focus, f"j:{pname} is written by jsk", "leave the header's j:format, j:updated "
               "and j:revision out; every write sets them")
        return False
    if pname == "provenance" and where in ("add", "set") and o == ox.NamedNode(O.J + "confirmed"):
        refuse(focus, "a changeset cannot confirm", "confirm with the person, then "
               "`jsk kb confirm <id> --answer \"what they said\"`; leave provenance out or "
               "state j:inferred")
        return False
    if where == "retire" and pname != "reason":
        refuse(focus, f"op:retire takes j:reason only, not {name(p)}",
               "state why it is retired; jsk dates it")
        return False
    return True


def bullets_named(quads, refuse):
    """A blank node is a new bullet waiting for its id, so it has to say which project it
    belongs to - that is where the id's stem comes from."""
    import pyoxigraph as ox

    blanks = {q.subject for q in quads if isinstance(q.subject, ox.BlankNode)}
    for b in blanks:
        if not any(q.subject == b and q.predicate.value == O.J + "project" for q in quads):
            refuse("a new bullet", "a blank node with no j:project",
                   "only a new bullet may leave its id to jsk, and it names its j:project; "
                   "any other new entry names its own id")
