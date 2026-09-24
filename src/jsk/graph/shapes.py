"""The rules a record must keep, and the findings that name where it does not.

Tier 1 is generated from ontology.py and runs on one file at a time: shape, ids, values.
Tier 2 is SPARQL over the whole workspace: references, versions, the vocabulary's edges.
Every rule has an id, a severity and a fix, and every finding names file:line and the id
it is about - a finding that says only "invalid" is one nobody can act on.
"""
import difflib
import re
from collections import defaultdict
from dataclasses import dataclass

from . import ontology as O

FAIL, WARN = "FAIL", "WARN"
# The tier-1 rule ids, and "syntax" for a file that does not parse. tests/test_graph_shapes.py
# holds a mutation for every id here and in RULES; a rule with none fails the suite.
TIER1 = ("syntax", "id-form", "id-home", "closed", "cardinality", "object", "no-blank-nodes",
         "no-derived", "retired-reason", "comment", "shipped-vocabulary")
XSD_TYPES = {O.XSD + t: t for t in ("string", "integer", "decimal", "boolean", "date")}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    focus: str       # the id as a CURIE, "" for a whole-file finding
    detail: str
    fix: str

    def text(self):
        where = f"{self.file}:{self.line}" if self.line else self.file
        focus = f" {self.focus}" if self.focus else ""
        return f"{where}{focus} - {self.detail}\n        fix: {self.fix}"


def curie(iri):
    from .writer import curie as c
    return c(iri)


# --- tier 1: one file, generated from the ontology --------------------------------------

def tier1(parsed):
    """Findings for one parsed file."""
    import pyoxigraph as ox

    out = []

    def add(rule, sev, s, detail, fix):
        out.append(Finding(rule, sev, parsed.file, parsed.lines.get(s, 0) if s else 0,
                           curie(s) if s else "", detail, fix))

    for line, text in parsed.comments:
        out.append(Finding("comment", WARN, parsed.file, line, "",
                           f"comment {text[:40]!r} will be lost on the next write",
                           "move it into a j:note on the entry it is about"))

    props = defaultdict(lambda: defaultdict(list))
    for q in parsed.quads:
        if any(isinstance(t, ox.BlankNode) for t in (q.subject, q.object)):
            s = q.subject.value if isinstance(q.subject, ox.NamedNode) else None
            add("no-blank-nodes", FAIL, s, "a blank node ([ ] or _:)",
                "give the node an id of its own and point at it")
            continue
        props[q.subject.value][q.predicate.value].append(q.object)

    head = O.HEADS.get(parsed.kind)
    if head:
        count = sum(1 for s in props if O.class_of(s) == head)
        if count != 1:
            add("cardinality", FAIL, None,
                f"a {parsed.kind} file holds exactly one {head}; this one holds {count}",
                HEAD_FIX[head])

    for s, preds in props.items():
        name = O.class_of(s)
        if name is None:
            add("id-form", FAIL, s, "not a jsk id", id_fix(s))
            continue
        cls = O.BY_NAME[name]
        local = s[len(O.K):] if s.startswith(O.K) else s[len(O.C):]
        if name == "Concept" and not O.CONCEPT_SLUG.fullmatch(local):
            add("id-form", FAIL, s, "a concept slug is lowercase words joined by -",
                "rename it, e.g. c:sql-server")
            continue
        if name == "Achievement" and O.POSITIONAL.search(local):
            add("id-form", FAIL, s, "a numbered bullet id says where it sits, not what it is",
                "name it after its content: ach_<project>_<two to four words>")
        if parsed.kind not in cls.kinds:
            add("id-home", FAIL, s, f"a {name} does not belong in a {parsed.kind} file",
                f"move it to {' or '.join(k + '.ttl' for k in cls.kinds)}")
            continue
        for p, objs in preds.items():
            if p == O.RDF_TYPE:
                if name != "Concept":
                    add("no-derived", FAIL, s, "rdf:type is derived from the id prefix",
                        "delete the `a …` - the prefix already says what it is")
                continue
            pname = p[len(O.J):] if p.startswith(O.J) else None
            pred = cls.preds.get(pname)
            if pred is None:
                near = difflib.get_close_matches(pname or p, list(cls.preds), n=1)
                add("closed", FAIL, s, f"{curie(p)} is not a {name} predicate",
                    f"did you mean j:{near[0]}?" if near else
                    f"a {name} takes {', '.join('j:' + x for x in cls.preds)}")
                continue
            if pred.card in "1?" and len(objs) > 1:
                add("cardinality", FAIL, s, f"j:{pname} holds {len(objs)} values; one allowed",
                    "keep the one that is true")
            for o in objs:
                problem = check_object(pred, o)
                if problem:
                    add("object", FAIL, s, f"j:{pname} {problem}", object_fix(pred))
        for pred in cls.preds.values():
            if pred.card in "1+" and O.J + pred.name not in preds:
                add("cardinality", FAIL, s, f"j:{pred.name} is required",
                    f"add j:{pred.name} ({pred.doc})")
        if name == "Concept":
            types = preds.get(O.RDF_TYPE, [])
            for t in types:
                if t.value not in {O.J + c for c in O.ENUMS["conceptClass"]}:
                    add("object", FAIL, s, f"a concept is a Capability, Domain or Technology, "
                        f"not {curie(t.value)}", "a j:Capability, j:Domain or j:Technology")
            if parsed.kind == "vocabulary":
                shipped_vocabulary(add, s, preds)
        if O.J + "retired" in preds and O.J + "reason" not in preds:
            add("retired-reason", FAIL, s, "retired without a reason",
                "add j:reason: why it no longer belongs on a resume")
    return out


def shipped_vocabulary(add, s, preds):
    """What the shipped vocabulary may hold: technologies and the edges among them.

    Technology aliases are close to fact - K8s is Kubernetes. A capability edge is
    judgement, and a judgement shipped to every user is how a graph starts overclaiming,
    so capabilities, domains and `implies` live only in a person's own kb.ttl. Narrowing
    is the person's too: a shipped file that unlabels itself is a file to fix.
    """
    for t in preds.get(O.RDF_TYPE, []):
        if t.value != O.J + "Technology":
            add("shipped-vocabulary", FAIL, s, f"the shipped vocabulary is technologies only, "
                f"not {curie(t.value)}", "move it into a person's kb.ttl")
    for name in ("implies", "unlabel", "unlink"):
        if O.J + name in preds:
            add("shipped-vocabulary", FAIL, s, f"j:{name} does not belong in the shipped vocabulary",
                "implies is a person's claim, and narrowing is a person's choice: kb.ttl")


HEAD_FIX = {
    "KB": 'start the file with k:kb j:format 3 ; j:name "…" ; j:updated "YYYY-MM-DD"^^xsd:date .',
    "Posting": "one k:post_<stem> per posting.ttl; another posting gets its own directory",
    "Application": "one k:app_<stem> per application.ttl; another gets its own directory",
}


def real_date(value):
    """YYYY-MM-DD, and a day the calendar has: 2026-02-30 is the right shape and no date."""
    import datetime

    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def check_object(pred, o):
    """None when `o` is a valid object for `pred`, else what is wrong with it."""
    import pyoxigraph as ox

    kind = pred.obj
    if isinstance(kind, O.Lit):
        if not isinstance(o, ox.Literal):
            return "must be a value, not a reference"
        dt = XSD_TYPES.get(o.datatype.value)
        if dt not in kind.types or o.language:
            return f"is {curie(o.datatype.value)}; expected {' or '.join(kind.types)}"
        # ASCII: `\d` also matches fullwidth and other Unicode digits.
        if kind.pattern and not re.fullmatch(kind.pattern, o.value, re.ASCII):
            return f"{o.value!r} does not have the expected form"
        if kind.lo is not None or kind.hi is not None:
            try:
                n = float(o.value)
            except ValueError:
                return f"{o.value!r} is not a number"
            if (kind.lo is not None and n < kind.lo) or (kind.hi is not None and n > kind.hi):
                return f"{o.value} is out of range"
        if dt == "date" and not real_date(o.value):
            return f"{o.value!r} is not a real YYYY-MM-DD date"
        return None
    if not isinstance(o, ox.NamedNode):
        return "must be a reference, not a value"
    if isinstance(kind, O.Enum):
        values = O.ENUMS[kind.name]
        if not (o.value.startswith(O.J) and o.value[len(O.J):] in values):
            return f"{curie(o.value)} is not one of {', '.join(values)}"
        return None
    if isinstance(kind, O.Concept):
        return None if o.value.startswith(O.C) else f"{curie(o.value)} is not a c: concept"
    if isinstance(kind, O.Ref):
        target = O.class_of(o.value)
        if target is None or target == "Concept":
            return f"{curie(o.value)} is not a k: id"
        if kind.classes != O.ANY and target not in kind.classes:
            return f"{curie(o.value)} is a {target}; expected {' or '.join(kind.classes)}"
    return None


def object_fix(pred):
    kind = pred.obj
    if isinstance(kind, O.Enum):
        return "one of " + ", ".join(f"j:{v}" for v in O.ENUMS[kind.name])
    if isinstance(kind, O.Ref):
        return "a k: id" + ("" if kind.classes == O.ANY else f" of a {' or '.join(kind.classes)}")
    if isinstance(kind, O.Concept):
        return "a c: concept (" + ", ".join(kind.classes) + ")"
    return pred.doc


def id_fix(iri):
    prefixes = sorted(p for p in O.BY_PREFIX if not p.startswith("=") and "." not in p)
    return ("ids are k:<prefix>_<words> with prefix one of " + ", ".join(prefixes)
            + "; concepts are c:<words-with-dashes>")
