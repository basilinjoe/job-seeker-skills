"""The rings of the onion architecture, held by a test.

docs/superpowers/specs/2026-09-30-onion-architecture-design.md (Ruling 7) puts every module
of src/jsk in one of five rings - domain, ports, application, infra, adapters, innermost
first - and lets an import point only at its own ring or one further in. The prose said the
same about pyoxigraph and preflight for a year; the lazy imports that broke it were the
ones nobody could see without reading function bodies. So this walks every import,
including the ones inside functions, and fails an edge that points outward.

A module not yet moved into a ring is "unsorted". It may import anything but an adapter,
and nothing sorted may import it - moving it is how an edge into it goes away. KNOWN
holds today's violations. An entry may only leave it: the inverse test fails the moment a
listed violation is gone, so the list cannot outlive what it excuses.

Standard library only, like the rest of the suite's structure tests, so it runs in the
sdist job and on a machine without pyoxigraph.
"""
import ast
import sys
import unittest

from fixtures import SCRIPTS

PACKAGE = "jsk"
RINGS = ("domain", "ports", "application", "infra", "adapters")
RANK = {ring: i for i, ring in enumerate(RINGS)}
UNSORTED = "unsorted"

# Adapters that still live at the package root, where their documented paths are.
ROOT_ADAPTERS = {"jsk.cli", "jsk.__main__", "jsk.preflight", "jsk.mcp"}
# paths.py is where the packaged data is on disk: infra by what it does, kept at the root
# because the wheel and the sdist are built around it.
ROOT_INFRA = {"jsk.paths"}

# Ruling 2: the pyoxigraph names that carry no I/O.
TERMS = {"NamedNode", "Literal", "BlankNode", "Triple", "Quad", "DefaultGraph"}
DOMAIN_FORBIDDEN_IMPORTS = {"os", "sys", "subprocess", "shutil", "glob", "tempfile",
                            "pathlib", "urllib"}
# Quoting a name for an IRI is string work; the rest of urllib is the network.
DOMAIN_ALLOWED_SUBMODULES = ("urllib.parse",)
DOMAIN_FORBIDDEN_ATTRIBUTES ={"today", "now", "utcnow", "ox"}
DOMAIN_FORBIDDEN_NAMES = {"record_graphs"}
NO_PYOXIGRAPH = {"jsk.domain.ontology", "jsk.domain.matching.scoring"}
# A port states a shape; the date is the one value type from outside typing it names.
PORT_IMPORTS = {"typing", "dataclasses", "__future__", "datetime"}
STDLIB_ONLY = {"jsk.preflight", "jsk.adapters.mcp"}

# (importer, imported) -> the names it imports. Today's outward edges, each to be removed by
# the phase that moves or splits one end of it.
KNOWN_EDGES = {}

# (module, what it does that its ring forbids).
KNOWN_FORBIDDEN = set()

# Package cycles among the unsorted packages: (package, package) pairs that import each
# other, P1's work. A ring cannot be in one without an outward edge, which is failed above.
KNOWN_CYCLES = set()


def module_name(path):
    """The dotted name of the module at `path`, a file under SCRIPTS.

    Returns `jsk`, `jsk.graph` for a package's __init__.py, `jsk.graph.store` for a module.
    """
    parts = (PACKAGE,) + path.relative_to(SCRIPTS).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def ring_of(name):
    """The ring `name` (a dotted jsk module) sits in, or UNSORTED."""
    if name in ROOT_ADAPTERS:
        return "adapters"
    if name in ROOT_INFRA:
        return "infra"
    parts = name.split(".")
    if len(parts) > 1 and parts[1] in RANK:
        return parts[1]
    return UNSORTED


# The line that makes a module an alias of one that moved: its old path is kept for the
# tests until P6 rewrites their imports, and it is the moved module, not a dependency on it.
ALIAS = "sys.modules[__name__] = _moved"


def modules():
    """{dotted name: (path, parsed tree)} for every module under src/jsk but the aliases."""
    out = {}
    for path in sorted(SCRIPTS.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if ALIAS not in text:
            out[module_name(path)] = (path, ast.parse(text))
    return out


def aliases():
    """The dotted names of the modules left at a moved module's old path."""
    return {module_name(p) for p in SCRIPTS.rglob("*.py")
            if ALIAS in p.read_text(encoding="utf-8")}


def resolve(importer, is_package, node):
    """The absolute module an ImportFrom names, relative levels resolved.

    `importer` is the importing module's dotted name; a package's own __init__ resolves
    level 1 to itself, a module's to its parent.
    """
    if not node.level:
        return node.module or ""
    base = importer.split(".")
    if not is_package:
        base = base[:-1]
    base = base[:len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def imports(name, path, tree, known):
    """[(imported module, [names], lineno)] for every import in `tree`, nested ones included.

    `from pkg import sub` where `sub` is a module counts as an import of `pkg.sub`, so an
    edge names the module whose code is reached, not the package that happens to hold it.
    """
    is_package = path.name == "__init__.py"
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(a.name, [], node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            target = resolve(name, is_package, node)
            subs = [a.name for a in node.names if f"{target}.{a.name}" in known]
            rest = [a.name for a in node.names if f"{target}.{a.name}" not in known]
            found += [(f"{target}.{s}", [], node.lineno) for s in subs]
            if rest or not subs:
                found.append((target, rest, node.lineno))
    return found


def jsk_edges(mods, keep=()):
    """{(importer, imported): {names}} over jsk modules only, self-edges dropped.

    An import of a name not in `mods` is credited to its nearest enclosing package, unless
    the name is in `keep` - the aliases, which a test needs to see imported.
    """
    edges = {}
    known = set(mods) | set(keep)
    for name, (path, tree) in mods.items():
        for target, names, _ in imports(name, path, tree, known):
            if target == name or not (target == PACKAGE or target.startswith(PACKAGE + ".")):
                continue
            while target not in known and "." in target:
                target = target.rsplit(".", 1)[0]
            edges.setdefault((name, target), set()).update(names)
    return edges


def outward(edges):
    """The edges that point from a ring to one further out, or into an unsorted module."""
    bad = {}
    for (src, dst), names in edges.items():
        a, b = ring_of(src), ring_of(dst)
        if b == "adapters" and a != "adapters":
            bad[(src, dst)] = names
        elif a == UNSORTED or a == "adapters":
            continue
        elif b == UNSORTED or RANK[b] > RANK[a]:
            bad[(src, dst)] = names
    return bad


def forbidden(mods):
    """{(module, what)} for each per-ring rule a module breaks."""
    out = set()
    stdlib = set(sys.stdlib_module_names)
    for name, (path, tree) in mods.items():
        ring = ring_of(name)
        for target, names, _ in imports(name, path, tree, mods):
            top = target.split(".")[0]
            if top == PACKAGE or not top:
                continue
            if ring == "domain" and top in DOMAIN_FORBIDDEN_IMPORTS and \
                    not target.startswith(DOMAIN_ALLOWED_SUBMODULES):
                out.add((name, f"imports {top}"))
            if ring == "domain" and top == "pyoxigraph" and set(names) - TERMS:
                out.add((name, f"imports pyoxigraph.{sorted(set(names) - TERMS)[0]}"))
            if name in NO_PYOXIGRAPH and top == "pyoxigraph":
                out.add((name, "imports pyoxigraph"))
            if ring == "ports" and top not in PORT_IMPORTS:
                out.add((name, f"imports {top}"))
            if name in STDLIB_ONLY and top not in stdlib:
                out.add((name, f"imports {top}, which is not the standard library"))
        if ring == "domain":
            out |= domain_calls(name, tree)
    return out


def domain_calls(name, tree):
    """{(module, what)} for the calls and attributes a domain module may not reach.

    An import walk cannot see `open(...)` or `date.today()`; the clock and the disk are
    reached through names, so the names are what is checked.
    """
    out = set()
    aliases = {a.asname or a.name for node in ast.walk(tree) if isinstance(node, ast.Import)
               for a in node.names if a.name == "pyoxigraph"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "open":
            out.add((name, "calls open"))
        elif isinstance(node, ast.Attribute):
            if node.attr in DOMAIN_FORBIDDEN_ATTRIBUTES:
                out.add((name, f"reaches .{node.attr}"))
            if isinstance(node.value, ast.Name) and node.value.id in aliases \
                    and node.attr not in TERMS:
                out.add((name, f"reaches pyoxigraph.{node.attr}"))
        elif isinstance(node, ast.Name) and node.id in DOMAIN_FORBIDDEN_NAMES:
            out.add((name, f"names {node.id}"))
    return out


def package_of(name):
    """`jsk.graph.store` -> `jsk.graph`; a root module is its own package."""
    parts = name.split(".")
    return ".".join(parts[:2]) if len(parts) > 2 or (len(parts) == 2 and parts[1] in RANK) \
        else name


def cycles(edges):
    """{(a, b)} sorted pairs of unsorted top-level packages (or root modules) importing
    each other."""
    pkg = {}
    for src, dst in edges:
        a, b = package_of(src), package_of(dst)
        if a != b and PACKAGE not in (a, b) and UNSORTED == ring_of(a) == ring_of(b):
            pkg.setdefault(a, set()).add(b)
    return {tuple(sorted((a, b))) for a, bs in pkg.items() for b in bs if a in pkg.get(b, ())}


class DependenciesPointInward(unittest.TestCase):
    MODS = modules()
    EDGES = jsk_edges(MODS)

    def test_no_module_imports_an_old_path(self):
        old = aliases()
        through = sorted((src, dst) for src, dst in jsk_edges(self.MODS, old) if dst in old)
        self.assertEqual(through, [], "import the module where it lives now")

    def test_no_edge_points_outward(self):
        bad = {e: n for e, n in outward(self.EDGES).items() if e not in KNOWN_EDGES}
        self.assertEqual(bad, {}, "an import points outward; move one end, or pass the "
                                  "dependency in through a port")

    def test_every_known_edge_still_exists(self):
        stale = sorted(e for e in KNOWN_EDGES if e not in outward(self.EDGES))
        self.assertEqual(stale, [], "these edges are gone - take them off KNOWN_EDGES")

    def test_no_ring_reaches_what_it_forbids(self):
        bad = sorted(forbidden(self.MODS) - KNOWN_FORBIDDEN)
        self.assertEqual(bad, [], "a module reaches what its ring forbids")

    def test_every_known_forbidden_use_still_exists(self):
        stale = sorted(KNOWN_FORBIDDEN - forbidden(self.MODS))
        self.assertEqual(stale, [], "these are gone - take them off KNOWN_FORBIDDEN")

    def test_no_new_package_cycle(self):
        found = cycles(self.EDGES)
        self.assertEqual(sorted(found - KNOWN_CYCLES), [], "two packages import each other")
        self.assertEqual(sorted(KNOWN_CYCLES - found), [],
                         "these cycles are gone - take them off KNOWN_CYCLES")


class TheGuardSeesEachWayRound(unittest.TestCase):
    """A planted violation of each kind has to fail, or the guard encodes the hole."""

    @staticmethod
    def tree(text):
        return ast.parse(text)

    def edges_of(self, name, text, others=()):
        path = SCRIPTS / (name.replace(".", "/").removeprefix("jsk/") + ".py")
        mods = {name: (path, self.tree(text))}
        mods.update({o: (SCRIPTS / "x.py", self.tree("")) for o in others})
        return outward(jsk_edges(mods))

    def test_a_lazy_import_is_an_edge(self):
        text = "def f():\n    from ...adapters.cli import main\n"
        bad = self.edges_of("jsk.domain.record.x", text, ["jsk.adapters.cli"])
        self.assertIn(("jsk.domain.record.x", "jsk.adapters.cli"), bad)

    def test_an_inner_ring_may_not_import_an_outer_one(self):
        text = "from ...infra import files\n"
        bad = self.edges_of("jsk.application.record.x", text, ["jsk.infra.files"])
        self.assertIn(("jsk.application.record.x", "jsk.infra.files"), bad)

    def test_a_sorted_module_may_not_import_an_unsorted_one(self):
        bad = self.edges_of("jsk.domain.x", "from ..graph import store\n", ["jsk.graph.store"])
        self.assertIn(("jsk.domain.x", "jsk.graph.store"), bad)

    def test_an_outer_ring_may_import_an_inner_one(self):
        bad = self.edges_of("jsk.adapters.cli.x", "from ...domain import naming\n",
                            ["jsk.domain.naming"])
        self.assertEqual(bad, {})

    def test_the_domain_may_not_open_a_file_or_read_the_clock(self):
        found = domain_calls("jsk.domain.x", self.tree(
            "import datetime\nopen('f')\ndatetime.date.today()\nstore.ox.query('')\n"))
        self.assertEqual({w for _, w in found}, {"calls open", "reaches .today", "reaches .ox"})

    def test_the_domain_may_use_terms_but_not_the_store(self):
        found = domain_calls("jsk.domain.x", self.tree(
            "import pyoxigraph as ox\nox.NamedNode('x')\nox.Store()\n"))
        self.assertEqual({w for _, w in found}, {"reaches pyoxigraph.Store"})

    def test_an_import_of_an_old_path_is_seen(self):
        mods = {"jsk.x": (SCRIPTS / "x.py", self.tree("from .graph import kbcli\n"))}
        self.assertIn(("jsk.x", "jsk.graph.kbcli"), jsk_edges(mods, {"jsk.graph.kbcli"}))

    def test_a_cycle_is_seen(self):
        edges = {("jsk.graph.a", "jsk.gates.b"): set(), ("jsk.gates.c", "jsk.graph.d"): set()}
        self.assertEqual(cycles(edges), {("jsk.gates", "jsk.graph")})


if __name__ == "__main__":
    unittest.main()
