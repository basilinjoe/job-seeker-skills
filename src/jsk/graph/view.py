"""career/kb.ttl as Markdown, to be read end to end - stdout only, never a second file.

docs/WHY.md's rule survives the graph: a person must be able to read their record, whole,
and correct it. kb.ttl is laid out to be read; this is the same record without the
syntax, in the same section order. It is never written anywhere, so it can never drift
from the file it shows.
"""
from . import ontology as O
from .writer import Subjects, curie, order

# The predicate an entry is known by, per class, in the order they are tried.
TITLES = ("fullName", "name", "title", "subject", "institution", "question", "language",
          "jurisdiction", "text")
QUIET = {"provenance", "note", "retired", "reason"}
# Written under the entry, not beside it: paragraphs, not facts.
PROSE = {"problem", "decision", "outcome", "positioning"}
# What nesting already says: a bullet sits under its project, a version under its metric.
NESTED = {"Achievement": {"project"}, "MetricVersion": {"of"}}


def value(t):
    import pyoxigraph as ox
    return curie(t.value) if isinstance(t, ox.NamedNode) else t.value


def facts(sub, s, part, skip):
    """`pred: value` for each predicate of this part, in the class's order."""
    out, prose = [], []
    cls = sub.cls[s]
    for line in cls.lines:
        for p in line:
            if p.name in skip or p.name in QUIET or (p.section or "main") != part:
                continue
            vals = sub.props[s].get(p.name)
            if not vals:
                continue
            text = ", ".join(sorted(value(v) for v in vals))
            (prose if p.name in PROSE or "\n" in text else out).append((p.name, text))
    return out, prose


def entry(sub, s, part, indent=""):
    cls = sub.cls[s]
    title = next((t for t in TITLES if t in sub.props[s] and (cls.preds[t].section or "main") == part),
                 None)
    head = sub.get(s, title) if title else curie(s)
    tags = []
    pv = sub.get(s, "provenance")
    if pv and pv != O.J + "confirmed":
        tags.append(pv[len(O.J):])
    if sub.get(s, "retired"):
        tags.append(f"retired {sub.get(s, 'retired')}: {sub.get(s, 'reason', '')}")
    if cls.name == "Concept":
        tags += [value(t) for t in sub.props[s].get("a", [])]
    short, prose = facts(sub, s, part, {title} | NESTED.get(cls.name, set()))
    line = f"{indent}- **{head}** `{curie(s)}`" + (f" _({'; '.join(tags)})_" if tags else "")
    if short:
        line += " - " + "; ".join(f"{p}: {v}" for p, v in short)
    out = [line]
    for p, text in prose:
        body = text.replace("\n", "\n" + indent + "    ")
        out.append(f"{indent}    {p}: {body}")
    return out


def render(triples, only=None):
    """The Markdown for kb.ttl's triples; `only` limits it to one section."""
    sub = Subjects(triples)
    header = next(iter(sub.of("KB")), None)
    out = [f"# {sub.get(header, 'name', 'Career')}", ""] if header else []
    for section in O.SECTIONS["kb"]:
        if only and section.lower() != only.lower():
            continue
        out += [f"## {section}", ""]
        entries = order(sub, section)
        if not entries:
            out += ["_(none)_", ""]
            continue
        for s, part in entries:
            nested = sub.cls[s].name in ("Achievement", "MetricVersion")
            out += entry(sub, s, part, "  " if nested else "")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
