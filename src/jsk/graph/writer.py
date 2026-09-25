"""The canonical Turtle writer: the same triples always give the same bytes.

gofmt's contract. `write` is a pure function of the triple set - input order, the
parser's order and hash seeds change nothing - and its output parses back to exactly the
triples it was given. pyoxigraph's own serializer is neither (P0), so it is used only to
parse and query.

Layout comes from ontology.py: sections in SECTIONS order, subjects by their natural key,
predicates in the class's line order, one line per `lines` entry.
"""
import re
from collections import defaultdict

from . import ontology as O

WIDTH = 100
INDENT = "    "
PN_LOCAL = re.compile(r"[A-Za-z0-9_](?:[A-Za-z0-9_.\-]*[A-Za-z0-9_\-])?")
BARE_DECIMAL = re.compile(r"[+-]?[0-9]*\.[0-9]+")
BARE_INTEGER = re.compile(r"[+-]?[0-9]+")


class WriteError(ValueError):
    """The triples cannot be written in this file kind's layout. Validation catches
    every such graph first; reaching this means a caller skipped validation."""


# --- terms -----------------------------------------------------------------------------

def curie(iri):
    # Only the prefixes every written file declares: an `op:` CURIE in a kb.ttl would not
    # parse. Changesets are P3's, with their own prefix block.
    for name, ns in O.PREFIXES:
        if iri.startswith(ns) and PN_LOCAL.fullmatch(iri[len(ns):]):
            return f"{name}:{iri[len(ns):]}"
    return f"<{iri}>"


def short_string(value):
    return '"' + (value.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\t", "\\t").replace("\r", "\\r")) + '"'


def long_string(value):
    """Triple-quoted, escaping only what the grammar needs: `\\`, a run of three quotes,
    a final quote (it would merge with the closing three) and a carriage return."""
    esc = value.replace("\\", "\\\\").replace("\r", "\\r").replace('"""', '\\"\\"\\"')
    if esc.endswith('"') and (len(esc) - len(esc[:-1].rstrip("\\")) - 1) % 2 == 0:
        esc = esc[:-1] + '\\"'      # a raw final quote, not the tail of an escape
    return '"""' + esc + '"""'


def literal(lit):
    dt = lit.datatype.value
    value = lit.value
    if lit.language:
        text = long_string(value) if "\n" in value else short_string(value)
        return f"{text}@{lit.language}"
    if dt == O.XSD + "string":
        return long_string(value) if "\n" in value else short_string(value)
    if dt == O.XSD + "integer" and BARE_INTEGER.fullmatch(value):
        return value
    if dt == O.XSD + "decimal" and BARE_DECIMAL.fullmatch(value):
        return value
    if dt == O.XSD + "boolean" and value in ("true", "false"):
        return value
    return f"{short_string(value)}^^{curie(dt)}"


def term(t):
    import pyoxigraph as ox

    if isinstance(t, ox.NamedNode):
        return curie(t.value)
    if isinstance(t, ox.Literal):
        return literal(t)
    raise WriteError(f"cannot write {t!r}: blank nodes are not part of the format")


def sort_key(t):
    import pyoxigraph as ox

    # References by id, literals by value; references first so a mixed list is stable.
    return (0, t.value, "") if isinstance(t, ox.NamedNode) else (1, t.value, t.datatype.value)


# --- the graph, by subject -------------------------------------------------------------

class Subjects:
    """{subject iri: {predicate name or "a": [objects]}} plus each subject's class."""

    def __init__(self, triples):
        import pyoxigraph as ox

        self.props = defaultdict(lambda: defaultdict(list))
        for t in triples:
            if not isinstance(t.subject, ox.NamedNode):
                raise WriteError("cannot write a blank-node subject")
            p = t.predicate.value
            if p == O.RDF_TYPE:
                name = "a"
            elif p.startswith(O.J):
                name = p[len(O.J):]
            else:
                raise WriteError(f"{curie(t.subject.value)}: predicate <{p}> is not in the format")
            if t.object not in self.props[t.subject.value][name]:    # a set, not a list
                self.props[t.subject.value][name].append(t.object)
        self.cls = {}
        for s in self.props:
            name = O.class_of(s)
            if name is None:
                raise WriteError(f"<{s}> is not a jsk id")
            self.cls[s] = O.BY_NAME[name]

    def of(self, name):
        return sorted(s for s, c in self.cls.items() if c.name == name)

    def get(self, s, pred, default=None):
        values = self.props.get(s, {}).get(pred)
        return values[0].value if values else default


# --- subject order ---------------------------------------------------------------------

def desc(items, key):
    """Sorted by key descending, missing keys last, id ascending within a tie."""
    have = sorted((x for x in items if key(x) is not None), key=lambda x: x)
    have.sort(key=key, reverse=True)
    return have + sorted(x for x in items if key(x) is None)


def order(sub, section):
    """The subjects written in one section, in order; each is (iri, part) where part
    names which of the subject's predicates this block holds ("main" or a section)."""
    g = sub.get
    if section == "Identity":
        return [(s, "main") for s in sub.of("Person")]
    if section == "Positioning":
        return [(s, section) for s in sub.of("Person") if "positioning" in sub.props[s]]
    if section == "Work authorization and languages":
        return [(s, "main") for s in sub.of("WorkAuthorization") + sub.of("Language")]
    if section == "Vocabulary":
        rank = {c: n for n, c in enumerate(O.ENUMS["conceptClass"])}

        def concept_key(s):
            types = sorted(rank.get(t.value[len(O.J):], 9) for t in sub.props[s].get("a", []))
            return (types[0] if types else 9, s)
        return [(s, "main") for s in sorted(sub.of("Concept"), key=concept_key)]
    if section == "Roles":
        return [(s, "main") for s in desc(sub.of("Position"), lambda s: g(s, "start"))]
    if section == "Organisations":
        newest = {}
        for p in sub.of("Position"):
            org, start = g(p, "organisation"), g(p, "start")
            if org and start and start > newest.get(org, ""):
                newest[org] = start
        return [(s, "main") for s in desc(sub.of("Organisation"), newest.get)]
    if section == "Projects":
        roles = [s for s, _ in order(sub, "Roles")]
        at = {r: n for n, r in enumerate(roles)}
        projects = sorted(sub.of("Project"),
                          key=lambda s: (at.get(g(s, "position"), len(roles)),
                                         -int(g(s, "recency", 0)), s))
        bullets = defaultdict(list)
        for a in sub.of("Achievement"):
            bullets[g(a, "project")].append(a)
        out = []
        for p in projects:
            out.append((p, "main"))
            out += [(a, "main") for a in sorted(bullets.pop(p, []),
                                                key=lambda a: (int(g(a, "rank", 0)), a))]
        out += [(a, "main") for rest in sorted(bullets) for a in bullets[rest]]
        return out
    if section == "Metrics":
        versions = defaultdict(list)
        for v in sub.of("MetricVersion"):
            versions[v.rsplit(".v", 1)[0]].append(v)
        out = []
        for m in sub.of("Metric"):
            out.append((m, "main"))
            out += [(v, "main") for v in sorted(versions.pop(m, []), key=version_number)]
        out += [(v, "main") for rest in sorted(versions)
                for v in sorted(versions[rest], key=version_number)]
        return out
    if section == "Skills":
        return [(s, "main") for s in sorted(
            sub.of("Skill"), key=lambda s: (g(s, "category", ""), rank_or_last(g(s, "rank")),
                                            g(s, "name", ""), s))]
    if section == "Education":
        return [(s, "main") for s in desc(sub.of("Education"),
                                          lambda s: g(s, "end") or g(s, "start"))]
    if section == "Certifications":
        return [(s, "main") for s in desc(sub.of("Credential"), lambda s: g(s, "issued"))]
    if section == "Open questions":
        return [(s, "main") for s in sorted(sub.of("Question"), key=lambda s: (g(s, "asked", ""), s))]
    if section == "Timeline":
        return [(s, "main") for s in sorted(
            sub.of("Event"), key=lambda s: (g(s, "date") == "unknown", g(s, "date", ""), s))]
    if section == "Log":
        return [(s, "main") for s in sorted(sub.of("LogEntry"),
                                            key=lambda s: (int(g(s, "revision", 0)), s))]
    names = [c.name for c in O.CLASSES if c.section == section]
    return [(s, "main") for name in names for s in sub.of(name)]


def version_number(v):
    return int(v.rsplit(".v", 1)[1])


def rank_or_last(value):
    return int(value) if value is not None else 1 << 30


# --- one subject -----------------------------------------------------------------------

def block(sub, s, part):
    """One subject's text: (text, one_line)."""
    cls = sub.cls[s]
    props = sub.props[s]
    lines = []
    if "a" in props:
        if cls.name != "Concept":
            raise WriteError(f"{curie(s)}: rdf:type is derived from the id, never written")
        lines.append([f"a {', '.join(term(t) for t in sorted(props['a'], key=sort_key))}"])
    known = set(cls.preds) | {"a"}
    unknown = sorted(set(props) - known)
    if unknown:
        raise WriteError(f"{curie(s)}: j:{unknown[0]} is not a {cls.name} predicate")
    for line in cls.lines:
        frags = []
        for p in line:
            if p.name not in props or (p.section or "main") != part:
                continue
            objs = sorted(props[p.name], key=sort_key)
            frags.append(f"j:{p.name} {', '.join(term(t) for t in objs)}")
        if frags:
            lines.append(frags)
    if not lines:
        return None
    head = curie(s)
    flat = f"{head} {' ; '.join(f for line in lines for f in line)} ."
    if len(flat) <= WIDTH and "\n" not in flat:
        return flat, True
    body = f" ;\n{INDENT}".join(" ; ".join(line) for line in lines)
    return f"{head} {body} .", False


# --- the file --------------------------------------------------------------------------

def write(triples, kind):
    """The canonical text of one file of kind `kind`."""
    if kind not in O.SECTIONS:
        raise WriteError(f"no layout for file kind {kind!r}")
    sub = Subjects(triples)
    allowed = {c.name for c in O.CLASSES if kind in c.kinds}
    for s, cls in sub.cls.items():
        if cls.name not in allowed:
            raise WriteError(f"{curie(s)}: a {cls.name} does not belong in a {kind} file")

    out = [f"@prefix {name}: <{ns}> ." for name, ns in O.PREFIXES]
    out.append("")
    for cls in O.CLASSES:
        if cls.section is None and kind in cls.kinds:
            for s in sub.of(cls.name):
                out += [block(sub, s, "main")[0], ""] if block(sub, s, "main") else []
    for section in O.SECTIONS[kind]:
        blocks = [b for b in (block(sub, s, part) for s, part in order(sub, section)) if b]
        if not blocks and kind not in O.ALL_BANNERS:
            continue
        out += [f"# == {section}", ""]
        prev_one = False
        for n, (text, one) in enumerate(blocks):
            if n and not (one and prev_one):
                out.append("")
            out.append(text)
            prev_one = one
        if blocks:
            out.append("")
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"
