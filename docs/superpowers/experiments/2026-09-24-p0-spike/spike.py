"""P0 spike for the graph rewrite: the pyoxigraph facts P1's spec depends on.

Throwaway. Prints one line per question; `--wheels` also asks PyPI which wheels exist.
"""
import json
import random
import sys
import time
import urllib.request

t0 = time.perf_counter()
import pyoxigraph as ox  # noqa: E402

IMPORT_MS = (time.perf_counter() - t0) * 1000
J = "https://jsk.dev/ns#"
K = "https://jsk.dev/id/"
PFX = f"@prefix j: <{J}> .\n@prefix k: <{K}> .\n"


def say(q, a):
    print(f"{q:<44} {a}")


def wheels():
    d = json.load(urllib.request.urlopen("https://pypi.org/pypi/pyoxigraph/json"))
    v = d["info"]["version"]
    names = [f["filename"] for f in d["releases"][v] if f["filename"].endswith(".whl")]
    say("latest pyoxigraph", v)
    for n in sorted(names):
        print("   ", n)


def parse_errors():
    bad = PFX + 'k:a j:name "ok" .\nk:b j:name "unterminated .\nk:c j:name "x" .\n'
    try:
        list(ox.parse(bad.encode(), ox.RdfFormat.TURTLE))
        say("turtle syntax error", "NOT RAISED")
    except SyntaxError as exc:
        say("turtle syntax error type/position", f"{type(exc).__name__}: {exc}"[:160])
    except Exception as exc:
        say("turtle syntax error type/position", f"{type(exc).__name__}: {exc}"[:160])
    bad2 = PFX + "k:a j:knows k:b\nk:c j:x k:d .\n"
    try:
        list(ox.parse(bad2.encode(), ox.RdfFormat.TURTLE))
        say("missing dot", "NOT RAISED")
    except Exception as exc:
        say("missing dot", f"{type(exc).__name__}: {exc}"[:160])


def serializer():
    triples = [(f"k:s{i}", f"j:p{j}", f'"v{i}{j}"') for i in range(3) for j in range(3)]
    text = PFX + "".join(f"{s} {p} {o} .\n" for s, p, o in triples)
    shuffled = PFX + "".join(f"{s} {p} {o} .\n" for s, p, o in random.Random(1).sample(triples, len(triples)))
    outs = []
    for t in (text, shuffled):
        s = ox.Store()
        s.load(t.encode(), ox.RdfFormat.TURTLE)
        outs.append(s.dump(format=ox.RdfFormat.TURTLE, from_graph=ox.DefaultGraph()).decode())
    say("serializer order-independent", outs[0] == outs[1])
    s = ox.Store()
    s.add(ox.Quad(ox.NamedNode(K + "p"), ox.NamedNode(J + "problem"),
                  ox.Literal('Line one.\nLine "two" with a quote.\n\nPara three \\ slash.'),
                  ox.DefaultGraph()))
    out = s.dump(format=ox.RdfFormat.TURTLE, from_graph=ox.DefaultGraph()).decode()
    say("multi-line literal written as", repr(out.strip().splitlines()[-1][-70:]))
    say("serializer emits prefixes/comments", "@prefix" in out or "PREFIX" in out)
    # our own writer's escaping must round-trip through the parser
    lit = 'He said """hi""" and ended with a quote"'
    esc = lit.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    if esc.endswith('"'):
        esc = esc[:-1] + '\\"'
    back = list(ox.parse((PFX + f'k:x j:t """{esc}""" .\n').encode(), ox.RdfFormat.TURTLE))[0].object.value
    say("triple-quoted escaping round-trips", back == lit)


def union_graph():
    s = ox.Store()
    s.add(ox.Quad(ox.NamedNode(K + "a"), ox.NamedNode(J + "p"), ox.Literal("1"), ox.NamedNode("file:kb.ttl")))
    s.add(ox.Quad(ox.NamedNode(K + "a"), ox.NamedNode(J + "q"), ox.Literal("2"), ox.NamedNode("file:app.ttl")))
    q = f"SELECT ?p WHERE {{ <{K}a> ?p ?o }}"
    plain = len(list(s.query(q)))
    union = len(list(s.query(q, use_default_graph_as_union=True)))
    g = [x[0].value for x in s.query(f"SELECT ?g WHERE {{ GRAPH ?g {{ <{K}a> <{J}q> ?o }} }}")]
    say("default graph plain / as union", f"{plain} / {union}; GRAPH ?g finds {g}")


def perf():
    rnd = random.Random(3)
    lines = [PFX]
    for i in range(400):                               # ~5k triples of career
        lines.append(f'k:prj_{i} a j:Project ; j:strength {rnd.randint(1, 5)} ; j:start {24000 + i} ; '
                     f'j:end {24010 + i} ; j:uses k:c{rnd.randrange(200)}, k:c{rnd.randrange(200)} ; '
                     f'j:problem """Some prose about project {i}.\nSecond line.""" .\n')
        lines.append(f'k:ach_{i} a j:Achievement ; j:project k:prj_{i} ; j:shows k:c{rnd.randrange(200)} ; '
                     f'j:provenance j:confirmed ; j:text "Did thing {i} and cut 40% of cost" .\n')
    for c in range(200):
        lines.append(f'k:c{c} a j:Concept ; j:label "c{c}" ; j:isA k:c{c // 2} .\n' if c else
                     f'k:c{c} a j:Concept ; j:label "c{c}" .\n')
    kb = "".join(lines).encode()
    apps = []
    for a in range(100):                               # 100 applications
        body = [PFX] + [f'k:app_{a}.e{e} a j:Event ; j:kind "note" ; j:date {25000 + e} .\n' for e in range(10)]
        body += [f'k:app_{a} j:carried k:ach_{rnd.randrange(400)} .\n' for _ in range(20)]
        apps.append("".join(body).encode())
    t = time.perf_counter()
    s = ox.Store()
    s.bulk_load(kb, ox.RdfFormat.TURTLE, to_graph=ox.NamedNode("file:kb.ttl"))
    for a, body in enumerate(apps):
        s.bulk_load(body, ox.RdfFormat.TURTLE, to_graph=ox.NamedNode(f"file:app{a}.ttl"))
    t_load = time.perf_counter()
    kinds = "j:isA|j:partOf|j:implies"
    cyc = bool(s.query(f"PREFIX j: <{J}> ASK {{ ?a ({kinds})+ ?a }}", use_default_graph_as_union=True))
    dangling = len(list(s.query(f"PREFIX j: <{J}> SELECT ?x WHERE {{ ?x j:project ?p FILTER NOT EXISTS {{ ?p a j:Project }} }}",
                                use_default_graph_as_union=True)))
    t_val = time.perf_counter()
    s.update(f"""PREFIX j: <{J}> INSERT {{ GRAPH j:derived {{ ?a j:reach1 ?b }} }} WHERE {{ ?a j:isA ?b }};
                 INSERT {{ GRAPH j:derived {{ ?a j:reach2 ?c }} }} WHERE {{ ?a j:isA ?b . ?b j:isA ?c }}""")
    t_mat = time.perf_counter()
    n = len(s)
    say("import pyoxigraph", f"{IMPORT_MS:.0f} ms")
    say("quads / KB bytes", f"{n} quads, kb.ttl {len(kb) // 1024} KB, 100 apps")
    say("load / validate / materialise", f"{(t_load - t) * 1000:.0f} / {(t_val - t_load) * 1000:.0f} / "
                                         f"{(t_mat - t_val) * 1000:.0f} ms (cycle={cyc}, dangling={dangling})")


if __name__ == "__main__":
    say("python", sys.version.split()[0])
    say("pyoxigraph", ox.__version__ if hasattr(ox, "__version__") else "?")
    if "--wheels" in sys.argv:
        wheels()
    parse_errors()
    serializer()
    union_graph()
    perf()
