"""Where do kb.ttl's extra tokens go? Measure layout variants of the same graph.

Each variant must still parse to the same triples, minus what it derives (types from
id prefixes), so the saving is layout, not lost content.
"""
import re
from pathlib import Path

import pyoxigraph as ox

HERE = Path(__file__).parent
MD = (HERE / "sample-kb.md").read_text(encoding="utf-8")
TTL = (HERE / "sample-kb.ttl").read_text(encoding="utf-8")


def tokens(text):
    return len(text.encode("utf-8")) // 4


def triples(text):
    return {(str(q.subject), str(q.predicate), str(q.object))
            for q in ox.parse(text.encode("utf-8"), ox.RdfFormat.TURTLE)}


def short_banners(t):
    return re.sub(r"^# ── (.+?) ─+$", r"# == \1", t, flags=re.M)


def no_header_comment(t):
    return re.sub(r"\A(# .*\n)+\n", "", t)


def derived_types(t):
    """`k:prj_x a j:Project ;` -> `k:prj_x` : the prefix already says what it is."""
    return re.sub(r"^((?:k|c):\S+) a j:\w+ ;\s*\n?\s*", r"\1 ", t, flags=re.M)


def one_line_short(t):
    """Join a subject's short predicate lines onto one line where they fit in 100 cols."""
    out = []
    for block in t.split("\n\n"):
        lines = block.split("\n")
        joined = " ".join(x.strip() for x in lines)
        out.append(joined if len(joined) <= 100 and '"""' not in block else block)
    return "\n\n".join(out)


base = triples(TTL)
variants = {"as drafted": TTL}
t = TTL
for name, fn in (("+ short banners", short_banners), ("+ no header comment", no_header_comment),
                 ("+ types from id prefix", derived_types), ("+ short subjects on one line", one_line_short)):
    t = fn(t)
    variants[name] = t

md = tokens(MD)
print(f"{'variant':<32} {'tokens':>6} {'ratio':>6}  triples")
for name, text in variants.items():
    got = triples(text)
    lost = base - got
    note = "same" if not lost else f"-{len(lost)} (all rdf:type)" if all("rdf-syntax-ns#type" in x[1] for x in lost) else f"LOST {len(lost)}"
    print(f"{name:<32} {tokens(text):>6} {tokens(text) / md:>6.2f}  {note}")
print(f"{'kb.md':<32} {md:>6}")
(HERE / "sample-kb.tight.ttl").write_text(t, encoding="utf-8", newline="\n")
