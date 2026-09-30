"""Every mock.patch of a jsk module-global reaches code that looks the name up there.

`mock.patch.object(render_resume, "compile_pdf", fake)` rebinds one name in one module's
namespace. The fake is seen only by code that looks `compile_pdf` up through that module
at call time: a bare name inside render_resume, `render_resume.compile_pdf` elsewhere, or a
`from ... import compile_pdf` run inside a function. Code that imported the name at the top
of another module holds the original and never sees the fake, so the test runs the real TeX
engine, or passes without testing anything.

Moving a function out of a module (Ruling 4 of
docs/superpowers/specs/2026-09-30-onion-architecture-design.md) is exactly how a patch comes
to aim at a name nothing reads any more, so each patch is checked for a reader. A patch on
an attribute of an object (`db.Writer`, "close") is not a module-global and is not checked;
nor is a patch on something outside jsk.
"""
import ast
import importlib
import unittest
from unittest import mock
from pathlib import Path

import fixtures

TESTS = Path(__file__).resolve().parent
SRC = fixtures.SCRIPTS


def bindings(tree):
    """{local name: dotted jsk module} for every `from jsk... import m [as n]` in `tree`.

    Imports inside functions count: most patching tests import the module they patch in
    the test method itself.
    """
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and \
                (node.module == "jsk" or node.module.startswith("jsk.")):
            for a in node.names:
                out[a.asname or a.name] = f"{node.module}.{a.name}"
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("jsk.") and a.asname:
                    out[a.asname] = a.name
    return out


def is_patch(func, attr):
    """Is `func` (a Call's func) `mock.patch`, `patch`, or `.object` of either?"""
    if attr == "object":
        return isinstance(func, ast.Attribute) and func.attr == "object" and \
            is_patch(func.value, None)
    if isinstance(func, ast.Attribute):
        return func.attr == "patch"
    return isinstance(func, ast.Name) and func.id == "patch"


def targets(tree):
    """[(dotted module, attribute, lineno)] for each patch of a jsk module-global."""
    names = bindings(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) < 1:
            continue
        first = node.args[0]
        if is_patch(node.func, "object") and len(node.args) >= 2 and \
                isinstance(first, ast.Name) and first.id in names and \
                isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
            found.append((names[first.id], node.args[1].value, node.lineno))
        elif is_patch(node.func, None) and isinstance(first, ast.Constant) and \
                isinstance(first.value, str) and first.value.startswith("jsk."):
            module, _, attr = first.value.rpartition(".")
            found.append((module, attr, node.lineno))
    return found


def module_of(path):
    """The dotted name of a module file under src/jsk."""
    parts = ("jsk",) + path.relative_to(SRC).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def absolute(importer, is_package, node):
    """The module an ImportFrom in `importer` names, its relative level resolved."""
    if not node.level:
        return node.module or ""
    base = importer.split(".")[:None if is_package else -1]
    base = base[:len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def readers(module, attr, sources):
    """The places in `sources` ({dotted name: tree}) that look `attr` up through `module`
    at call time; empty when a patch of module.attr would reach nothing."""
    found = []
    for name, (path, tree) in sources.items():
        is_package = path.name == "__init__.py"
        local = {}
        in_function = set()
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                in_function.update(id(n) for n in ast.walk(fn) if n is not fn)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                src = absolute(name, is_package, node)
                for a in node.names:
                    local[a.asname or a.name] = f"{src}.{a.name}"
                    if src == module and a.name == attr and id(node) in in_function:
                        found.append(f"{name}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    local[a.asname or a.name.split(".")[0]] = a.name if a.asname else \
                        a.name.split(".")[0]
        for node in ast.walk(tree):
            if name == module and isinstance(node, ast.Name) and node.id == attr and \
                    isinstance(node.ctx, ast.Load) and id(node) in in_function:
                found.append(f"{name}:{node.lineno}")
            elif isinstance(node, ast.Attribute) and node.attr == attr and \
                    isinstance(node.value, ast.Name) and local.get(node.value.id) == module:
                found.append(f"{name}:{node.lineno}")
    return found


def sources():
    """{dotted name: (path, tree)} for every module under src/jsk."""
    return {module_of(p): (p, ast.parse(p.read_text(encoding="utf-8")))
            for p in sorted(SRC.rglob("*.py"))}


def unread(found, src):
    """[(where, why)] for each patch of a jsk callable that no code looks up there."""
    bad = []
    for where, module_name, attr in found:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue                    # a name bound to a function, not a module
        if not callable(getattr(module, attr, None)):
            continue
        if not readers(module.__name__, attr, src):
            bad.append((where, f"patches {module.__name__}.{attr}, which no code looks up "
                               "there - patch the module whose code calls it"))
    return bad


class PatchesReachTheCode(unittest.TestCase):
    SRC = sources()

    def test_every_patch_has_a_reader(self):
        found = []
        for path in sorted(TESTS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            found += [(f"{path.name}:{line}", m, a) for m, a, line in targets(tree)]
        self.assertTrue(found, "no patch found at all - the walk is broken")
        self.assertEqual(unread(found, self.SRC), [])

    def test_a_patch_on_a_name_nothing_reads_fails(self):
        # named.py imports curie at its top, so patching writer.curie is seen by named's
        # callers; patching named.curie from outside is not seen by writer's.
        tree = ast.parse("from jsk.graph import writer\n"
                         "mock.patch.object(writer, 'nobody_calls_this', lambda: 0)\n")
        found = [("planted", m, a) for m, a, _ in targets(tree)]
        src = dict(self.SRC)
        path, parsed = src["jsk.graph.writer"]
        parsed = ast.parse(path.read_text(encoding="utf-8") +
                           "\ndef nobody_calls_this():\n    return 0\n")
        src["jsk.graph.writer"] = (path, parsed)
        module = importlib.import_module("jsk.graph.writer")
        with mock.patch.object(module, "nobody_calls_this", lambda: 0, create=True):
            self.assertEqual(len(unread(found, src)), 1, found)

    def test_a_top_level_import_elsewhere_is_not_a_reader(self):
        src = {"jsk.a": (SRC / "a.py", ast.parse("def f():\n    return 1\n")),
               "jsk.b": (SRC / "b.py", ast.parse("from .a import f\ndef g():\n    f()\n"))}
        self.assertEqual(readers("jsk.a", "f", src), [])

    def test_a_lazy_import_and_an_attribute_are_readers(self):
        src = {"jsk.b": (SRC / "b.py", ast.parse("def g():\n    from .a import f\n    f()\n")),
               "jsk.c": (SRC / "c.py", ast.parse("from . import a\ndef h():\n    a.f()\n"))}
        self.assertEqual(sorted(readers("jsk.a", "f", src)), ["jsk.b:2", "jsk.c:3"])

    def test_a_string_patch_is_resolved(self):
        tree = ast.parse("mock.patch('jsk.graph.named.curie', lambda i: i)\n")
        self.assertEqual(targets(tree), [("jsk.graph.named", "curie", 1)])


if __name__ == "__main__":
    unittest.main()
