"""Mutation check: break one rule at a time and confirm the scenario guarding it fails.

A scenario suite that passes against a broken graph proves nothing. Each mutation below
is a one-line edit to graphsim.py's source, compiled into a fresh module; the named
scenario must go from PASS to FAIL, and every other scenario is reported too.
"""
import sys
import types
from pathlib import Path

SOURCE = (Path(__file__).parent / "graphsim.py").read_text(encoding="utf-8")

MUTATIONS = {
    "counts-as runs both ways": (
        'if proj not in entry["matched"]:\n                entry["near"].setdefault(proj, f"holds broader {have}")',
        'if proj not in entry["matched"]:\n                entry["matched"][proj] = (have, 1, False)',
        "S2"),
    "hop limit raised to 3": (
        '''                                 STRAFTER(STR(?b), "concept/"))) AS ?p) }}""")
''',
        '''                                 STRAFTER(STR(?b), "concept/"))) AS ?p) }}""")
    s.update(PREFIX + f"""
        INSERT {{ ?p j:from ?a ; j:to ?b ; j:hops 3 ; j:implied false ; j:via ?a }}
        WHERE {{ ?a ?k1 ?m . ?m ?k2 ?n . ?n ?k3 ?b . FILTER(?k1 IN ({kinds}) && ?k2 IN ({kinds}) && ?k3 IN ({kinds}))
                 BIND(IRI(CONCAT(STR(?a), "/p3/", STRAFTER(STR(?b), "concept/"))) AS ?p) }}""")
''',
        "S3"),
    "implies carries required": (
        'if implied and necessity == "required":', 'if False:', "S5"),
    "an edge crosses a distinct wall": (
        '"distinct": ["dotnet-framework"]', '"distinct": ["dotnet-framework"], "isA": ["dotnet-framework"]',
        "S0"),
    "a distinct wall deleted, edge added": (
        '"distinct": ["dotnet-framework"]', '"isA": ["dotnet-framework"]', "S4"),
    "metric versions ignored": (
        "FILTER NOT EXISTS {{ ?v j:validUntil ?u }}", "", "S8"),
    "tags count as evidence": (
        'return "confirmed" if "confirmed" in statuses else "unconfirmed" if statuses else "tag"',
        'return "confirmed"', "S11"),
}


def run(source):
    module = types.ModuleType("mutant")
    module.__file__ = str(Path(__file__).parent / "graphsim.py")
    exec(compile(source, "mutant", "exec"), module.__dict__)
    results, _ = module.scenarios()
    return {name.split()[0]: ok for name, ok, *_ in results}


def main():
    baseline = run(SOURCE)
    assert all(baseline.values()), baseline
    caught = 0
    for label, (old, new, guard) in MUTATIONS.items():
        assert SOURCE.count(old) == 1, f"{label}: the edit does not apply exactly once"
        try:
            outcome = run(SOURCE.replace(old, new))
            failed = sorted(k for k, ok in outcome.items() if not ok)
        except Exception as exc:              # a mutation that breaks validation outright
            failed = [f"raised {type(exc).__name__}"]
        hit = guard in failed
        caught += hit
        print(f"{'caught' if hit else 'MISSED'}  {label:<32} guarded by {guard}; failing: {', '.join(failed) or 'none'}")
    print(f"\n{caught}/{len(MUTATIONS)} mutations caught")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
