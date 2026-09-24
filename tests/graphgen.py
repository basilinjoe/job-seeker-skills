"""Random valid graphs drawn from the ontology, for the writer's property tests.

Seeded, so a failure names its seed and reproduces. Values are chosen to be hard for the
writer rather than realistic: runs of quotes, backslashes, newlines, tabs, non-ASCII.
"""
import random

import pyoxigraph as ox

from jsk.graph import ontology as O

NASTY = ['"', '""', '"""', '""""', '\\', '\\"', "\n", "\n\n", "\t", "→", "é", "#", "'", "'''",
         " ", "a", "Bb", "0", "p95", "C# / .NET", "<x>", "\r"]
XSD = {t: ox.NamedNode(O.XSD + t) for t in ("string", "integer", "decimal", "boolean", "date")}


def text(rnd, multiline):
    parts = [rnd.choice(NASTY) for _ in range(rnd.randint(1, 8))]
    value = "".join(parts)
    if not multiline:
        value = value.replace("\n", " ")
    return value or "x"


def value(rnd, pred, ids):
    kind = pred.obj
    if isinstance(kind, O.Enum):
        return ox.NamedNode(O.J + rnd.choice(O.ENUMS[kind.name]))
    if isinstance(kind, O.Concept):
        return ox.NamedNode(O.C + rnd.choice(["kafka", "sql-server", "a", "b-c"]))
    if isinstance(kind, O.Ref):
        pool = [i for i, c in ids if kind.classes == O.ANY or c in kind.classes]
        return ox.NamedNode(rnd.choice(pool) if pool else O.K + "org_x")
    t = rnd.choice(kind.types)
    if kind.pattern == r"\d{4}(-(0[1-9]|1[0-2]))?":
        return ox.Literal(f"{rnd.randint(1990, 2030)}-{rnd.randint(1, 12):02d}")
    if kind.pattern == r"\d{4}-\d{2}-\d{2}|false":
        return ox.Literal("false", datatype=XSD["boolean"]) if t == "boolean" else \
            ox.Literal("2026-09-10", datatype=XSD["date"])
    if kind.pattern == r"\d{4}-\d{2}-\d{2}|unknown":
        return ox.Literal("unknown") if t == "string" else \
            ox.Literal(f"2026-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}", datatype=XSD["date"])
    if kind.pattern:
        return ox.Literal({r"[A-Z]{2}": "AU", r"[0-9a-f]{64}": "a" * 64, r"\S+": "https://x/y",
                           r"posting\.md": "posting.md"}.get(kind.pattern, "en"))
    if t == "integer":
        lo = int(kind.lo) if kind.lo is not None else 0
        hi = int(kind.hi) if kind.hi is not None else lo + 50
        return ox.Literal(str(rnd.randint(lo, hi)), datatype=XSD["integer"])
    if t == "decimal":
        return ox.Literal(f"{rnd.randint(0, 99)}.{rnd.randint(0, 9)}", datatype=XSD["decimal"])
    if t == "boolean":
        return ox.Literal(rnd.choice(["true", "false"]), datatype=XSD["boolean"])
    if t == "date":
        return ox.Literal(f"2026-0{rnd.randint(1, 9)}-2{rnd.randint(0, 8)}", datatype=XSD["date"])
    return ox.Literal(text(rnd, pred.obj is O.TEXT))


def graph(seed, kind):
    """(triples, ids) for one random file of `kind`."""
    rnd = random.Random(seed)
    ids = []
    for cls in O.CLASSES:
        if kind not in cls.kinds:
            continue
        if cls.prefix and cls.prefix.startswith("="):
            ids.append((O.K + cls.prefix[1:], cls.name))
            continue
        for n in range(rnd.randint(0, 3)):
            if cls.name == "Concept":
                ids.append((O.C + f"con-{n}-{rnd.randint(0, 9)}", cls.name))
            elif cls.name == "MetricVersion":
                ids.append((O.K + f"met_m{n % 2}.v{n + 1}", cls.name))
            else:
                ids.append((O.K + f"{cls.prefix}_s{n}_{rnd.choice(['a', 'b', 'cc'])}", cls.name))
    triples = []
    for iri, name in dict(ids).items():
        cls = O.BY_NAME[name]
        s = ox.NamedNode(iri)
        if name == "Concept":
            triples.append(ox.Triple(s, ox.NamedNode(O.RDF_TYPE),
                                     ox.NamedNode(O.J + rnd.choice(O.ENUMS["conceptClass"]))))
        for pred in cls.preds.values():
            if pred.card in "1+" or rnd.random() < 0.5:
                count = rnd.randint(1, 3) if pred.card in "*+" else 1
                for _ in range(count):
                    triples.append(ox.Triple(s, ox.NamedNode(O.J + pred.name),
                                             value(rnd, pred, ids)))
    return list({str(t): t for t in triples}.values()), ids
