"""No module over 600 lines, no test file over 800, no function over 80.

Two modules had passed 1,000 lines (graph/kbcli.py, cli.py) and three test files with
them, each a use case fused with its printing that nobody split because nothing counted.
Ruling 11 of docs/superpowers/specs/2026-09-30-onion-architecture-design.md sets the limits;
this counts. SIZE_KNOWN holds what is over them today, at its length today. An entry may
shrink but not grow, and the inverse test fails an entry that is back under its limit, so
the list cannot outlive what it excuses.
"""
import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "jsk"
TESTS = REPO / "tests"

MODULE_LIMIT = 600
TEST_LIMIT = 800
FUNCTION_LIMIT = 80

# (repo-relative path, function name or None for the whole file) -> its length now.
SIZE_KNOWN = {
    ("src/jsk/cli.py", None): 1302,
    ("src/jsk/graph/kbcli.py", None): 1479,
    ("src/jsk/graph/rules.py", None): 683,
    ("src/jsk/graph/timeline.py", None): 608,
    ("tests/test_cli.py", None): 1067,
    ("tests/test_graph_kbcli.py", None): 1193,
    ("tests/test_ship_freeze.py", None): 1343,
    ("src/jsk/cli.py", "cmd_freeze"): 198,
    ("src/jsk/cli.py", "cmd_ship"): 91,
    ("src/jsk/gates/check_ats.py", "main"): 180,
    ("src/jsk/gates/check_prose.py", "check"): 94,
    ("src/jsk/graph/edit.py", "apply"): 143,
    ("src/jsk/graph/kbcli.py", "cmd_confirm"): 103,
    ("src/jsk/graph/kbcli.py", "cmd_export"): 162,
    ("src/jsk/graph/kbcli.py", "cmd_load"): 83,
    ("src/jsk/graph/merge.py", "draft"): 101,
    ("src/jsk/graph/postingbuild.py", "built"): 190,
    ("src/jsk/graph/prepare.py", "prepare"): 124,
    ("src/jsk/graph/select.py", "select"): 97,
    ("src/jsk/graph/shapes.py", "tier1"): 90,
    ("src/jsk/preflight.py", "gather"): 90,
    ("src/jsk/render/fit_pages.py", "main"): 154,
    ("src/jsk/render/preview_templates.py", "main"): 114,
    ("src/jsk/render/render_resume.py", "main"): 163,
}


def file_lengths(root, limit):
    """{(repo-relative path, None): lines} for each .py file under `root` over `limit`."""
    out = {}
    for path in sorted(root.rglob("*.py")):
        n = len(path.read_text(encoding="utf-8").splitlines())
        if n > limit:
            out[(path.relative_to(REPO).as_posix(), None)] = n
    return out


def function_lengths(root, limit, text_of=None):
    """{(repo-relative path, function name): lines} for each function over `limit`.

    `text_of` maps a path to source text, so a planted file can be measured without
    writing it; by default each file is read from disk.
    """
    out = {}
    for path in sorted(root.rglob("*.py")):
        text = text_of(path) if text_of else path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                n = (node.end_lineno or node.lineno) - node.lineno + 1
                if n > limit:
                    out[(path.relative_to(REPO).as_posix(), node.name)] = n
    return out


def measured():
    """Everything over its limit today, in SIZE_KNOWN's shape."""
    found = file_lengths(SRC, MODULE_LIMIT)
    found.update(file_lengths(TESTS, TEST_LIMIT))
    found.update(function_lengths(SRC, FUNCTION_LIMIT))
    return found


class NothingGrowsPastItsLimit(unittest.TestCase):
    FOUND = measured()

    def test_nothing_new_is_over_its_limit(self):
        new = sorted(k for k in self.FOUND if k not in SIZE_KNOWN)
        self.assertEqual(new, [], f"over the limit (module {MODULE_LIMIT}, test file "
                                  f"{TEST_LIMIT}, function {FUNCTION_LIMIT} lines): split it")

    def test_nothing_listed_has_grown(self):
        grown = sorted((k, SIZE_KNOWN[k], n) for k, n in self.FOUND.items()
                       if k in SIZE_KNOWN and n > SIZE_KNOWN[k])
        self.assertEqual(grown, [], "a listed module or function grew: it may only shrink")

    def test_every_listed_entry_is_still_over(self):
        stale = sorted(k for k in SIZE_KNOWN if k not in self.FOUND)
        self.assertEqual(stale, [], "back under the limit - take these off SIZE_KNOWN")


class TheGuardSeesALongFunction(unittest.TestCase):
    def test_a_planted_81_line_function_is_over(self):
        body = "def f():\n" + "    x = 1\n" * 80
        found = function_lengths(SRC, FUNCTION_LIMIT,
                                 text_of=lambda p: body if p.name == "paths.py" else "")
        self.assertEqual(found, {("src/jsk/paths.py", "f"): 81})


if __name__ == "__main__":
    unittest.main()
