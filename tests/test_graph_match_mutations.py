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

from fixtures import one_test_each

TESTS = Path(__file__).parent
SRC = TESTS.parent / "src"

# name: (file under the copy, text, replacement), or a list of them. "src" is whichever
# module holds the text: the rules move between rings, and a mutation follows its rule.
MUTATIONS = {
    "counts-as runs both ways": (
        "src",
        'm.near.setdefault(proj, f"holds broader {curie(held)}")',
        "m.carriers.setdefault(proj, (held, 1, False))"),
    "a third hop": (
        # The two-hop insert, made to join three edges: every "2-hop" path is now three.
        "src",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?m }} GRAPH ?h3 {{ ?m ?k3 ?b }} "
        "FILTER(?k3 IN ({kinds}))"),
    "no second hop": (
        "src",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }}",
        "GRAPH ?g {{ ?a ?k1 ?via }} GRAPH ?h {{ ?via ?k2 ?b }} FILTER(false)"),
    "implies carries a required requirement": (
        "src",
        'if implied and req.necessity == "required":',
        "if False:"),
    "the wall is ignored": [
        # The rule disabled and an edge that crosses it added: nothing refuses the graph,
        # so the scenarios themselves must notice .NET counting as .NET Framework.
        ("src", "{{ ?focus j:distinct ?b .",
         "{{ ?focus j:distinct ?b . FILTER(false)"),
        ("tests/match_fixtures/vocabulary.ttl",
         'c:dotnet a j:Technology ; j:label ".NET", "Dot Net" ; j:distinct c:dotnet-framework .',
         'c:dotnet a j:Technology ; j:label ".NET", "Dot Net" ; j:isA c:dotnet-framework .')],
    "a tag counts as evidence": (
        "src",
        'return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "tag"',
        'return "confirmed" if "confirmed" in levels else "unconfirmed" if levels else "confirmed"'),
    "a tag-only match is satisfied": (
        "src",
        'else "unevidenced")',
        'else "satisfied")'),
    "gaps.txt may raise a verdict": (
        "src",
        "return RANK[said] > RANK[matched]",
        "return False"),
    "ambiguity is guessed": (
        "src",
        "    if len(found) == 1:",
        "    if len(found) >= 1:"),
}


def run(mutation=None):
    """The scenarios' exit code over a copy of the package, with `mutation` applied."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(SRC, tmp / "src", ignore=shutil.ignore_patterns("__pycache__"))
        (tmp / "tests").mkdir()
        # appkit and storekit seed the store GapsFlags runs against; fixtures, which they
        # import first, puts the copy's src/ on the path.
        for helper in ("test_graph_match.py", "appkit.py", "storekit.py", "fixtures.py"):
            shutil.copy(TESTS / helper, tmp / "tests")
        shutil.copytree(TESTS / "match_fixtures", tmp / "tests" / "match_fixtures")
        for file, old, new in ([mutation] if isinstance(mutation, tuple) else mutation or []):
            if file == "src":
                holding = [p for p in (tmp / "src").rglob("*.py")
                           if p.read_text(encoding="utf-8").count(old) == 1]
                assert len(holding) == 1, f"{old!r} is not once in one module: {holding}"
                path = holding[0]
            else:
                path = tmp / file
            text = path.read_text(encoding="utf-8")
            assert text.count(old) == 1, f"{old!r} is not once in {path}"
            path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        env = dict(os.environ, PYTHONPATH=str(tmp / "src"))
        done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                               str(tmp / "tests" / "test_graph_match.py")],
                              capture_output=True, text=True, env=env, cwd=tmp)
        return done.returncode, done.stdout[-2000:]


@one_test_each(list(MUTATIONS), "test_{}_is_caught", "caught")
class EveryMutationIsCaught(unittest.TestCase):
    def test_the_control_passes(self):
        code, out = run()
        self.assertEqual(code, 0, out)

    def caught(self, name):
        code, out = run(MUTATIONS[name])
        self.assertEqual(code, 1, f"{name} was not caught:\n{out}")
        # Caught by an assertion, not by an error: a sandbox missing a helper exits 1 too,
        # and for a while every mutation here "was caught" by a ModuleNotFoundError.
        self.assertIn("\nFAILED ", out, f"{name} broke the harness, not a scenario:\n{out}")
        self.assertNotIn("\nERROR ", out, f"{name} broke the harness, not a scenario:\n{out}")


if __name__ == "__main__":
    unittest.main()
