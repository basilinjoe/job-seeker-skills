"""Break each matching rule and watch the scenarios catch it.

tests/test_graph_match.py passing proves the rules hold on its fixture; it does not prove
the tests would notice if a rule stopped holding. So each mutation below breaks one rule
in a throwaway copy of the package - the kind of break a well-meant refactor makes - and
the scenarios must then fail. A control copy with no mutation must pass, or a harness
that fails for any reason would look like every mutation being caught.

Ported from the graph simulation's mutate.py.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).parent
SRC = TESTS.parent / "src"

# name: (file under the copy, text, replacement), or a list of them
MUTATIONS = {
    "counts-as runs both ways": (
        "src/jsk/graph/queries.py",
        'm.near.setdefault(proj, f"holds broader {curie(held)}")',
        "m.carriers.setdefault(proj, (held, 1, False))"),
    "a third hop": (
        # The two-hop insert, made to join three edges: every "2-hop" path is now three.
        "src/jsk/graph/store.py",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?m }} GRAPH ?h3 {{ ?m ?k3 ?b }} "
        "FILTER(?k3 IN ({kinds}))"),
    "no second hop": (
        "src/jsk/graph/store.py",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }} FILTER(false)"),
    "implies carries a required requirement": (
        "src/jsk/graph/queries.py",
        'if implied and req.necessity == "required":',
        "if False:"),
    "the wall is ignored": [
        # The rule disabled and an edge that crosses it added: nothing refuses the graph,
        # so the scenarios themselves must notice .NET counting as .NET Framework.
        ("src/jsk/graph/rules.py", "{{ ?focus j:distinct ?b .",
         "{{ ?focus j:distinct ?b . FILTER(false)"),
        ("tests/match_fixtures/vocabulary.ttl",
         'c:dotnet a j:Technology ; j:label ".NET", "Dot Net" ; j:distinct c:dotnet-framework .',
         'c:dotnet a j:Technology ; j:label ".NET", "Dot Net" ; j:isA c:dotnet-framework .')],
    "a tag counts as evidence": (
        "src/jsk/graph/queries.py",
        'return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "tag"',
        'return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "confirmed"'),
    "a tag-only match is satisfied": (
        "src/jsk/graph/match.py",
        'else "unevidenced")',
        'else "satisfied")'),
    "gaps.md may raise a verdict": (
        "src/jsk/graph/match.py",
        "and RANK[said] > RANK[default])",
        "and False)"),
    "ambiguity is guessed": (
        "src/jsk/graph/queries.py",
        "    if len(found) == 1:",
        "    if len(found) >= 1:"),
}


def run(mutation=None):
    """The scenarios' exit code over a copy of the package, with `mutation` applied."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(SRC, tmp / "src", ignore=shutil.ignore_patterns("__pycache__"))
        (tmp / "tests").mkdir()
        shutil.copy(TESTS / "test_graph_match.py", tmp / "tests")
        shutil.copytree(TESTS / "match_fixtures", tmp / "tests" / "match_fixtures")
        for file, old, new in ([mutation] if isinstance(mutation, tuple) else mutation or []):
            path = tmp / file
            text = path.read_text(encoding="utf-8")
            assert text.count(old) == 1, f"{old!r} is not once in {file}"
            path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        env = dict(os.environ, PYTHONPATH=str(tmp / "src"))
        done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                               str(tmp / "tests" / "test_graph_match.py")],
                              capture_output=True, text=True, env=env, cwd=tmp)
        return done.returncode, done.stdout[-2000:]


class EveryMutationIsCaught(unittest.TestCase):
    def test_the_control_passes(self):
        code, out = run()
        self.assertEqual(code, 0, out)

    def test_each_mutation_fails_the_scenarios(self):
        for name, mutation in MUTATIONS.items():
            with self.subTest(mutation=name):
                code, out = run(mutation)
                self.assertEqual(code, 1, f"{name} was not caught:\n{out}")


if __name__ == "__main__":
    unittest.main()
