# Vocabulary Graph Implementation Plan

> **Superseded — do not execute.** Replaced by `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md`:
> the engine is Oxigraph over Turtle files, not LadybugDB over Markdown. Its scenarios and review focus carry into
> the roadmap's P2.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Postings' words (`K8s`, `.NET`, `Azure AD`) match the knowledge base's concepts through a maintained graph of labels and counts-as edges, queried through LadybugDB.

**Architecture:** A new `src/jsk/vocabgraph.py` merges the shipped graph (`src/jsk/data/vocabulary-graph.json`, technologies only) with the knowledge base's `## Vocabulary` clauses and every project tag, builds an in-memory LadybugDB database, runs four queries once (labels, closure within two hops, unbounded reachability, cycles) and answers every later question from dictionaries. `kbindex.rank()` scores through it; a new `jsk vocab` command maintains it; the renderer and the gates never load it.

**Tech Stack:** Python ≥3.10, `ladybug>=0.18.3,<0.19` (LadybugDB, formerly Kùzu; Kùzu-lineage Cypher), unittest/pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-24-vocabulary-graph-design.md` — read it before any task.

## Global Constraints

- `dependencies = ["ladybug>=0.18.3,<0.19"]` — the only hard dependency; every other package stays optional and imported at the point of use.
- `requires-python = ">=3.10"`; `MIN_PYTHON = (3, 10)`.
- `import ladybug` appears in exactly two places: `src/jsk/vocabgraph.py` and the doctor probe in `src/jsk/preflight.py`. Both import it inside a function, never at module top level.
- The renderer (`src/jsk/urs/`) and the gates (`src/jsk/gates/`) never import `vocabgraph`.
- `HOP_LIMIT = 2`, a constant in `vocabgraph.py`, not a setting.
- Weights unchanged: required ×3, preferred ×1, implicit 0.
- Kùzu-lineage Cypher has no list comprehensions; use `properties(nodes(e), 'id')`. `nodes(e)` returns interior nodes only. A null INT64 parameter is a binder error; do not pass `None` for an INT64 column.
- Refusals are verdicts with a fix (`GraphError(message, fix)`, surfaced as `FAIL  ...` / `fix:  ...`), never tracebacks.
- Doc token ceilings in `tests/test_budget.py` hold: SKILL.md < 2400 (now 2,236), jsk-tailor-analyst.md < 2300 (now 2,188), resume author + view-format + urs-spec + ats-rules + writing-rules < 7600 (now 7,211), SKILL.md + mode-tailor + mode-ship < 6000. Replace sentences rather than add them.
- Match the surrounding code: comments explain *why*, in full sentences; lazy imports are deliberate.
- Commit after each task. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never `--amend`, never `--no-verify`.
- Run the suite as `python -m pytest tests -q -n auto` and lint as `python -m ruff check src tests`.

## Review Focus

1. **A knowledge base written before the graph** (plain tags, no clauses, requirement values that are slugs) must rank exactly as it does today. Pinned in Task 4 by the existing scores 19 / 12.5 / 9 surviving unchanged.
2. **A `## Vocabulary` line carrying prose after the dash** (`- \`x\` — what I mean by x`) must not refuse the whole knowledge base; it warns. Pinned in Task 2 (`test_a_clause_nothing_reads_is_a_warning`).
3. **A label differing only by case or spacing** (`MICROSOFT  AZURE`) resolves; a label differing by punctuation (`dot.net`) does not. Pinned in Task 2.
4. **A skill alias written in a render-only form** (`Entra ID (formerly Azure AD)`) must not be refused by `jsk vocab check --record` as an unknown or narrower label. Pinned in Task 5.
5. **A posting directory holding one malformed `posting.md`** must not stop `jsk vocab candidates` from reporting the others. Pinned in Task 5.

---

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | the dependency, the Python floor, the rewritten "deliberately empty" comment |
| `.github/workflows/test.yml` | a Python 3.10 job and a Windows graph job |
| `src/jsk/preflight.py` | `MIN_PYTHON`, the required "vocabulary matching (ladybug)" check, new modules listed |
| `src/jsk/vocabgraph.py` (new) | merge, validate, query once, answer by lookup |
| `src/jsk/data/vocabulary-graph.json` (new) | the curated shipped graph, technologies only |
| `src/jsk/kbindex.py` | ranking and coverage through the graph |
| `src/jsk/vocab.py` (new) | `jsk vocab check / explain / names / candidates` |
| `src/jsk/cli.py` | registers `vocab`; help text |
| `src/jsk/kb.py` | the template's `## Vocabulary` comment and a `### Technologies` subsection |
| `tests/test_vocabgraph.py` (new) | the engine, against a fixture graph |
| `tests/test_vocabulary_data.py` (new) | the shipped file |
| `tests/test_vocab.py` (new) | the command |
| `tests/test_kbindex.py`, `tests/test_preflight.py` | updated |
| `plugins/jsk/...` docs, `docs/SCRIPTS.md` | the interface as written for people and agents |

---

### Task 1: Packaging — LadybugDB as a dependency, Python 3.10

**Files:**
- Modify: `pyproject.toml:11,18-23`
- Modify: `src/jsk/preflight.py:1-22` (docstring), `:35` (`MIN_PYTHON`), `:52-66` (`INSTALL`), `gather()`, `REQUIRED`
- Modify: `.github/workflows/test.yml`
- Test: `tests/test_preflight.py`

**Interfaces:**
- Produces: `preflight.ladybug_opens() -> tuple[bool, str]`; a `Check` named `"vocabulary matching (ladybug)"`, required.

- [ ] **Step 1: Install the engine locally**

Run: `python -m pip install "ladybug>=0.18.3,<0.19"`
Then: `python -c "import ladybug as lb; c = lb.Connection(lb.Database(':memory:')); print(c.execute('RETURN 1+1').get_all())"`
Expected: `[[2]]`. If this raises "Could not find lbug C API shared library", the installed version is ≥0.19 — reinstall with the pin.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_preflight.py` (inside the module, as a new class):

```python
class TheGraphEngine(unittest.TestCase):
    """LadybugDB is the one hard dependency: matching is core to tailoring, so a machine
    that cannot open it cannot tailor, and doctor must say so as a FAIL, not a gap."""

    def test_the_engine_opens_here(self):
        ok, why = preflight.ladybug_opens()
        self.assertTrue(ok, why)

    def test_the_engine_check_is_required(self):
        checks, _ = preflight.gather()
        engine = [c for c in checks if c.name.startswith("vocabulary matching")]
        self.assertEqual(len(engine), 1)
        self.assertTrue(preflight.is_required(engine[0]))
        self.assertTrue(engine[0].ok, engine[0].disables)

    def test_a_broken_engine_names_what_it_costs(self):
        saved = preflight.ladybug_opens
        preflight.ladybug_opens = lambda: (False, "RuntimeError: no C API library")
        try:
            checks, _ = preflight.gather()
        finally:
            preflight.ladybug_opens = saved
        engine = next(c for c in checks if c.name.startswith("vocabulary matching"))
        self.assertFalse(engine.ok)
        self.assertIn("jsk index cannot rank", engine.disables)
        self.assertIn("no C API library", engine.disables)

    def test_the_floor_is_three_ten(self):
        self.assertEqual(preflight.MIN_PYTHON, (3, 10))
```

`tests/test_preflight.py` already has `preflight = load_script(PREFLIGHT)` at the top; the class uses that name.

- [ ] **Step 3: Run them to verify they fail**

Run: `python -m pytest tests/test_preflight.py -q -k "GraphEngine"`
Expected: FAIL — `AttributeError: module 'jsk.preflight' has no attribute 'ladybug_opens'`.

- [ ] **Step 4: Implement**

`pyproject.toml` — replace line 11 and lines 18-23:

```toml
requires-python = ">=3.10"
```

```toml
# One hard dependency, and only one. Every other package is optional and imported at
# the point of use, so a bare install still gives a working record gate, prose gate
# and .txt parse gate, and `jsk doctor` can report on a machine before anything else
# is installed on it.
#
# LadybugDB is the exception because matching is core to tailoring: a posting's `K8s`
# has to reach the knowledge base's `kubernetes`, and a tailoring run that quietly
# matched worse because an extra was missing would be worse than a larger install.
#
# Pinned to 0.18.x. Every Windows wheel from 0.19.0 to 0.20.4 fails on a clean
# install - it omits the C-API library its default backend loads, and the fallback
# links OpenSSL DLLs it does not ship - and releases in the Kùzu lineage have changed
# API and storage format between minors. Raise the pin only after the spike in the
# vocabulary-graph spec passes on Windows and Linux.
dependencies = ["ladybug>=0.18.3,<0.19"]
```

`src/jsk/preflight.py`:

- Docstring, replace the last paragraph (`Standard library only. A preflight that needs installing first is not a preflight.`) with:

```
Standard library only at import time. LadybugDB is probed inside a function, so a
machine without it still gets this report - with the gap named - rather than an
ImportError. A preflight that needs installing first is not a preflight.
```

- `MIN_PYTHON = (3, 10)`
- Leave `MODULES` alone here: the modules check is required, so naming a module that does not exist yet would turn doctor to BLOCKED. Task 2 adds `"vocabgraph"` and Task 5 adds `"vocab"`, each in the commit that creates it.
- `INSTALL` gains:

```python
    "ladybug": {"pip": '"ladybug>=0.18.3,<0.19"',
                "note": "LadybugDB, the graph jsk index ranks through. 0.19 and 0.20 "
                        "do not load on Windows; keep the pin."},
```

- Above `def present(names)`, add:

```python
def ladybug_opens():
    """Can this interpreter open an in-memory LadybugDB? (ok, why-not).

    Opening a database, not just importing the package: every Windows wheel from 0.19.0
    to 0.20.4 imports cleanly and fails at the first Database() call.
    """
    try:
        import ladybug as lb

        db = lb.Database(":memory:")
        conn = lb.Connection(db)
        conn.execute("RETURN 1").get_all()
        conn.close()
        db.close()
        return True, ""
    except Exception as exc:        # a broken native install raises anything at all
        return False, f"{type(exc).__name__}: {exc}"
```

- In `gather()`, after the `markdown-it-py and pyyaml` check, add:

```python
    ok, why = ladybug_opens()
    checks.append(Check(
        "vocabulary matching (ladybug)", ok, key="ladybug",
        disables="jsk index cannot rank and jsk vocab cannot run: a posting's words "
                 "cannot be matched to the knowledge base's concepts"
                 + (f" ({why})" if why else "")))
```

- `REQUIRED` gains `"vocabulary matching"`.

`.github/workflows/test.yml`:

- In the `suite` matrix `include`, add a third entry and use it:

```yaml
          - name: Python 3.10, without a TeX engine
            tex: false
            python: "3.10"
```

and change `python-version: "3.13"` to `python-version: ${{ matrix.python || '3.13' }}`.

- Add a second job after `suite`:

```yaml
  # 0.19 and 0.20 of LadybugDB install cleanly on Windows and fail at the first
  # Database() call, which no Linux job can see. This job exists to catch the pin being
  # raised past a broken wheel.
  windows-graph:
    name: vocabulary graph on Windows
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      # No TeX engine here, so doctor exits 1 on that FAIL by design. What this job
      # asserts is the engine line alone.
      - name: The graph engine opens
        shell: bash
        run: |
          jsk doctor --quick --json > doctor.json || true
          python -c "import json,sys; c=[x for x in json.load(open('doctor.json'))['checks'] if x['name'].startswith('vocabulary matching')]; print(c); sys.exit(0 if c and c[0]['ok'] else 1)"
      - name: Graph tests
        run: python -m pytest tests/test_preflight.py tests/test_vocabgraph.py tests/test_vocabulary_data.py tests/test_kbindex.py tests/test_vocab.py -q
```

Test files that do not exist yet (`test_vocabgraph.py`, `test_vocabulary_data.py`, `test_vocab.py`) make pytest error; the job goes green once Tasks 2, 3 and 5 land. That is expected.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_preflight.py -q`
Expected: PASS.
Run: `python -m pytest tests -q -n auto` and `python -m ruff check src tests`
Expected: PASS / clean. If any test uses a 3.11+ feature, it surfaces in CI's 3.10 job, not here; to check locally run `docker run --rm -v "$PWD:/w" -w /w python:3.10-slim sh -c "pip install -q -e '.[dev]' && python -m pytest tests -q -n auto"` (Git Bash: prefix with `MSYS_NO_PATHCONV=1` and use `$(pwd -W)`).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/jsk/preflight.py .github/workflows/test.yml tests/test_preflight.py
git commit -m "build: LadybugDB becomes the one hard dependency; Python 3.10 floor" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The engine — `src/jsk/vocabgraph.py`

**Files:**
- Create: `src/jsk/vocabgraph.py`
- Create: `tests/test_vocabgraph.py`
- Modify: `src/jsk/preflight.py:43` — `MODULES` gains `"vocabgraph"`

**Interfaces:**
- Consumes: `jsk.paths.HERE`; kbindex's section shape — `{"entries": [{"title": str, "body": [(line_no, text), ...]}, ...]}` (what `kbindex.read_kb(text)[1]["Vocabulary"]` returns).
- Produces:
  - `vocabgraph.load(vocabulary=None, tags=(), shipped=SHIPPED) -> Graph`
  - `vocabgraph.GraphError(message, fix)`; `vocabgraph.normalise(label) -> str`; `vocabgraph.HOP_LIMIT`; `vocabgraph.SHIPPED`; `vocabgraph.read_shipped(path) -> dict`
  - `Graph.resolve(label) -> list[str]` (sorted concept ids; `[]` unknown; 2+ ambiguous)
  - `Graph.satisfies(have, want) -> Path | None` (concept ids; zero hops when equal)
  - `Graph.near_miss(have, want) -> bool`; `Graph.beyond_limit(have, want) -> bool`; `Graph.is_distinct(a, b) -> bool`
  - `Graph.names(concept) -> Names`, `Names.for_render() -> list[str]`
  - `Graph.concepts: dict[id, kind]` (kind ∈ technology, capability, domain, tag, or a subsection title); `Graph.edges: set[(src, tgt, kind)]`; `Graph.distinct: set[frozenset]`; `Graph.kb_edges: list[Edge]`; `Graph.warnings: list[str]`; `Graph.stats() -> dict`
  - `Path(nodes: tuple, kinds: tuple)` with `.hops`, `.implied`; `Edge(source, kind, target, provenance)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vocabgraph.py`:

```python
"""The vocabulary graph: concepts, the labels postings use for them, and the counts-as
paths between them.

Built against a fixture graph written to a temp file, never the shipped one, so that
curating the shipped data can never move these assertions.
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

import fixtures  # noqa: F401 - puts src/ on the path

from jsk import vocabgraph as vg

SHIPPED = {"version": 1, "concepts": {
    "kubernetes": {"labels": ["Kubernetes", "K8s"]},
    "aks": {"labels": ["AKS", "Azure Kubernetes Service"],
            "is-a": ["kubernetes"], "part-of": ["azure"]},
    "azure": {"labels": ["Azure", "Microsoft Azure"], "is-a": ["cloud-platform"]},
    "cloud-platform": {"labels": ["Cloud platform"], "is-a": ["computing"]},
    "computing": {"labels": ["Computing"]},
    "dotnet": {"labels": [".NET", "Dot Net"], "distinct": ["dotnet-framework"]},
    "dotnet-framework": {"labels": [".NET Framework"]},
    "linq": {"labels": ["LINQ"], "part-of": ["dotnet"]},
    "entra-id": {"labels": ["Entra ID"], "former": [{"label": "Azure AD", "until": 2023}],
                 "part-of": ["azure"]},
    "golang": {"labels": ["Go", "Golang"]},
}}

TMP = tempfile.TemporaryDirectory()


def shipped_file(data=SHIPPED, name="graph.json"):
    path = Path(TMP.name) / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def section(**groups):
    """section(Technologies=["- `x` — is-a: y"]) -> kbindex's section shape."""
    entries, n = [], 100
    for title, lines in groups.items():
        body = []
        for line in lines:
            n += 1
            body.append((n, line))
        entries.append({"title": title, "body": body})
    return {"entries": entries}


def load(tags=(), shipped=None, **groups):
    return vg.load(section(**groups) if groups else None, tags=tags,
                   shipped=shipped or shipped_file())


class Labels(unittest.TestCase):

    def test_a_label_resolves_to_its_concept(self):
        g = load()
        self.assertEqual(g.resolve("K8s"), ["kubernetes"])
        self.assertEqual(g.resolve("kubernetes"), ["kubernetes"])     # the id is a label

    def test_case_and_spacing_do_not_matter(self):
        self.assertEqual(load().resolve("  MICROSOFT   azure "), ["azure"])

    def test_punctuation_does(self):
        """`.NET` reaches dotnet only because `.NET` is declared; `dot.net` is not."""
        g = load()
        self.assertEqual(g.resolve(".net"), ["dotnet"])
        self.assertEqual(g.resolve("dot.net"), [])

    def test_a_former_label_resolves(self):
        self.assertEqual(load().resolve("azure ad"), ["entra-id"])

    def test_an_ambiguous_label_names_every_concept(self):
        g = load(Technologies=["- `go-game` — labels: Go"])
        self.assertEqual(g.resolve("Go"), ["go-game", "golang"])

    def test_an_unknown_label_names_nothing(self):
        self.assertEqual(load().resolve("K3s"), [])

    def test_a_project_tag_is_a_concept(self):
        g = load(tags=["terraform"])
        self.assertEqual(g.resolve("Terraform"), ["terraform"])
        self.assertEqual(g.concepts["terraform"], "tag")


class Paths(unittest.TestCase):

    def setUp(self):
        self.g = load(Technologies=["- `terraform` — implies: infrastructure-as-code"],
                      Capabilities=["- `infrastructure-as-code` — labels: IaC"])

    def test_narrower_counts_as_broader_and_says_how(self):
        self.assertEqual(self.g.satisfies("aks", "kubernetes"),
                         vg.Path(("aks", "kubernetes"), ("is-a",)))

    def test_broader_does_not_count_as_narrower(self):
        self.assertIsNone(self.g.satisfies("kubernetes", "aks"))
        self.assertTrue(self.g.near_miss("kubernetes", "aks"))
        self.assertFalse(self.g.near_miss("aks", "kubernetes"))

    def test_a_concept_satisfies_itself_in_zero_hops(self):
        self.assertEqual(self.g.satisfies("aks", "aks").hops, 0)

    def test_two_hops_count_and_three_do_not(self):
        self.assertEqual(self.g.satisfies("aks", "cloud-platform").hops, 2)
        self.assertIsNone(self.g.satisfies("aks", "computing"))
        self.assertTrue(self.g.beyond_limit("aks", "computing"))

    def test_a_concept_may_have_two_parents(self):
        self.assertEqual(self.g.satisfies("aks", "azure").kinds, ("part-of",))

    def test_an_implies_path_is_marked(self):
        path = self.g.satisfies("terraform", "infrastructure-as-code")
        self.assertTrue(path.implied)
        self.assertEqual(self.g.concepts["infrastructure-as-code"], "capability")


class Names(unittest.TestCase):

    def test_a_render_may_add_own_and_broader_labels(self):
        names = load().names("aks").for_render()
        self.assertEqual(names[:2], ["AKS", "Azure Kubernetes Service"])
        self.assertIn("Kubernetes", names)

    def test_never_narrower_ones(self):
        self.assertNotIn("AKS", load().names("kubernetes").for_render())

    def test_a_former_label_renders_as_former(self):
        self.assertEqual(load().names("entra-id").for_render()[0], "Entra ID (formerly Azure AD)")

    def test_never_through_implies(self):
        g = load(Technologies=["- `terraform` — implies: infrastructure-as-code"],
                 Capabilities=["- `infrastructure-as-code` — labels: IaC"])
        self.assertEqual(g.names("terraform").broader, ())


class TheKnowledgeBasesClauses(unittest.TestCase):

    def test_labels_and_edges_add_to_the_shipped_graph(self):
        g = load(Technologies=["- `k3s` — labels: K3s; is-a: kubernetes"])
        self.assertEqual(g.resolve("K3s"), ["k3s"])
        self.assertIsNotNone(g.satisfies("k3s", "kubernetes"))

    def test_provenance_is_kept(self):
        g = load(Technologies=["- `k3s` — is-a: kubernetes (from 2026-09-12-contoso)"])
        self.assertIn(vg.Edge("k3s", "is-a", "kubernetes", "2026-09-12-contoso"), g.kb_edges)

    def test_not_removes_a_shipped_label(self):
        self.assertEqual(load(Technologies=["- `golang` — not: labels Go"]).resolve("Go"), [])

    def test_not_removes_a_shipped_edge(self):
        g = load(Technologies=["- `aks` — not: part-of azure"])
        self.assertIsNone(g.satisfies("aks", "azure"))

    def test_a_former_label_from_the_knowledge_base(self):
        g = load(Technologies=["- `fabric` — former: Synapse until 2024"])
        self.assertEqual(g.resolve("synapse"), ["fabric"])

    def test_a_clause_nothing_reads_is_a_warning(self):
        """Prose after the dash predates the graph; refusing it would refuse the file."""
        g = load(Capabilities=["- `team-leadership` — what I mean by leading"])
        self.assertEqual(len(g.warnings), 1)
        self.assertIn("line 101", g.warnings[0])

    def test_seniority_is_never_a_concept(self):
        g = load(**{"Seniority (fixed vocabulary - do not extend)": ["- `junior`"]})
        self.assertNotIn("junior", g.concepts)

    def test_the_subsection_names_the_kind(self):
        g = load(Domains=["- `healthcare`"])
        self.assertEqual(g.concepts["healthcare"], "domain")


class ItRefuses(unittest.TestCase):

    def refuses(self, *words, shipped=None, **groups):
        with self.assertRaises(vg.GraphError) as caught:
            load(shipped=shipped, **groups)
        for word in words:
            self.assertIn(word, str(caught.exception))
        self.assertTrue(caught.exception.fix)

    def test_a_cycle(self):
        self.refuses("cycle", "kubernetes", Technologies=["- `kubernetes` — is-a: aks"])

    def test_a_concept_counting_as_itself(self):
        self.refuses("itself", Technologies=["- `x` — is-a: x"])

    def test_a_path_across_a_distinct_wall(self):
        self.refuses("distinct", Technologies=["- `dotnet-framework` — is-a: dotnet"])

    def test_a_two_hop_path_across_a_distinct_wall(self):
        self.refuses("distinct", Technologies=["- `dotnet-framework` — part-of: linq"])

    def test_an_edge_to_nothing(self):
        self.refuses("nowhere", Technologies=["- `x` — is-a: nowhere"])

    def test_a_not_with_nothing_to_remove(self):
        self.refuses("no such edge", Technologies=["- `aks` — not: is-a azure"])

    def test_a_shipped_technology_redeclared_as_a_capability(self):
        self.refuses("kubernetes", Capabilities=["- `kubernetes`"])

    def test_a_former_label_without_a_year(self):
        self.refuses("no year", Technologies=["- `fabric` — former: Synapse"])

    def test_a_shipped_implies(self):
        bad = {"version": 1, "concepts": {"terraform": {"implies": ["iac"]}, "iac": {}}}
        self.refuses("implies", shipped=shipped_file(bad, "bad.json"))

    def test_an_unreadable_shipped_file(self):
        self.refuses("cannot be read", shipped=str(Path(TMP.name) / "missing.json"))


class LoadTime(unittest.TestCase):

    def test_five_hundred_concepts_load_in_well_under_two_seconds(self):
        concepts = {f"c{i}": {"labels": [f"Label {i}", f"L{i}", f"Alt {i}", f"Other {i}"]}
                    for i in range(500)}
        for i in range(1, 500):
            concepts[f"c{i}"]["is-a"] = [f"c{(i - 1) // 2}"]       # a binary tree
        path = shipped_file({"version": 1, "concepts": concepts}, "big.json")
        vg.load(shipped=path)                                       # import once
        start = time.perf_counter()
        g = vg.load(shipped=path)
        self.assertLess(time.perf_counter() - start, 2.0)
        self.assertEqual(g.satisfies("c3", "c0").hops, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_vocabgraph.py -q`
Expected: FAIL — `ImportError: cannot import name 'vocabgraph' from 'jsk'`.

- [ ] **Step 3: Implement**

Create `src/jsk/vocabgraph.py` with exactly this content. It was run against `ladybug` 0.18.3 while this plan was written; every refusal and lookup below was exercised.

```python
"""The vocabulary graph: which words a posting uses for the concepts a knowledge base holds.

A **concept** is one thing with a stable id (`kubernetes`); a **label** is a name for it
(`K8s`). Concepts connect by `is-a`, `part-of` and `implies`, which all read narrower to
broader and all score as one counts-as relation, and are kept apart by `distinct`.

Two sources merge: the graph shipped with jsk (`data/vocabulary-graph.json`,
technologies only) and the knowledge base's `## Vocabulary` lines. Every project tag
is a concept too, so a knowledge base that never declares a term still matches it.

The data is the record; LadybugDB is where it is queried. `load()` builds an in-memory
database, asks it four questions - the labels, the counts-as closure within the hop
limit, unbounded reachability, and cycles - and keeps the answers. A path query costs
milliseconds, so asking per match would make a ranking slow; every method after
`load()` is a dictionary lookup.

This is the only module that imports `ladybug`.
"""
import json
import os
import re
from dataclasses import dataclass

from .paths import HERE

SHIPPED = os.path.join(HERE, "data", "vocabulary-graph.json")

# A counts-as path longer than this stops being evidence and starts being noise.
HOP_LIMIT = 2

COUNTS_AS = ("is-a", "part-of", "implies")
EDGE_KEYS = COUNTS_AS + ("distinct",)
CLAUSE_KEYS = ("labels", "former", "not") + EDGE_KEYS

# `### Technologies` declares technologies, and so on. Seniority is a closed list the
# render profiles compare against, never a concept.
KINDS = {"technologies": "technology", "capabilities": "capability", "domains": "domain"}

LINE = re.compile(r"^\s*-\s+`([^`]+)`\s*(?:(?:—|–|--|-)\s*(.*))?$")
FROM = re.compile(r"\s*\(from ([^)]+)\)\s*$")
FORMER = re.compile(r"^(.*\S)\s+until\s+(\d{4})$")


class GraphError(Exception):
    """The graph cannot be built as written. Carries the fix, like kbindex.KBError."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


def normalise(label):
    """Lower-cased, trimmed, whitespace runs to one `-`. Punctuation is kept."""
    return re.sub(r"\s+", "-", str(label).strip().lower())


@dataclass(frozen=True)
class Path:
    """have -> ... -> want, both ends included; `kinds` has one entry per edge."""
    nodes: tuple
    kinds: tuple

    @property
    def hops(self):
        return len(self.kinds)

    @property
    def implied(self):
        return "implies" in self.kinds


@dataclass(frozen=True)
class Names:
    """What a render may call a concept: its own labels, its former labels with the
    year they stopped, and the labels of broader concepts it counts as - never
    narrower ones, and never through `implies`."""
    own: tuple
    former: tuple
    broader: tuple

    def for_render(self):
        own = list(self.own)
        if own and self.former:
            was = ", ".join(label for label, _ in self.former)
            own[0] = f"{own[0]} (formerly {was})"
        return own + [b for b in self.broader if b not in self.own]


@dataclass(frozen=True)
class Edge:
    """One edge the knowledge base added, for `jsk vocab candidates`."""
    source: str
    kind: str
    target: str
    provenance: str


class Graph:
    def __init__(self, concepts, labels, display, former, closure, reach, edges, distinct,
                 kb_edges, warnings):
        self.concepts = concepts          # id -> kind
        self.edges = edges                # {(source, target, kind)} after removals
        self.distinct = distinct          # {frozenset((a, b))}
        self._labels = labels             # normalised label -> sorted concept ids
        self._display = display           # id -> [label as written]
        self._former = former             # id -> [(label as written, until)]
        self._closure = closure           # (have, want) -> shortest Path within HOP_LIMIT
        self._reach = reach               # id -> ids reachable at any length
        self.kb_edges = kb_edges          # [Edge] the knowledge base added
        self.warnings = warnings          # clauses nothing reads, by line

    def resolve(self, label):
        """The concepts a label names: [] unknown, one, or several (ambiguous)."""
        return list(self._labels.get(normalise(label), []))

    def satisfies(self, have, want):
        """Does evidence for `have` count as `want`? Concept ids, not labels."""
        if have == want:
            return Path((have,), ())
        return self._closure.get((have, want))

    def near_miss(self, have, want):
        """`want` is narrower than `have`: holding the broader thing is not enough."""
        return have != want and self.satisfies(want, have) is not None

    def is_distinct(self, a, b):
        return frozenset((a, b)) in self.distinct

    def beyond_limit(self, have, want):
        """Reachable, but only past the hop limit."""
        return want in self._reach.get(have, ()) and self.satisfies(have, want) is None

    def names(self, concept):
        broader = []
        for (have, want), path in sorted(self._closure.items()):
            if have == concept and not path.implied:
                broader += [b for b in self._display.get(want, []) if b not in broader]
        return Names(tuple(self._display.get(concept, [])),
                     tuple(self._former.get(concept, [])), tuple(broader))

    def stats(self):
        return {"concepts": len(self.concepts), "labels": len(self._labels),
                "edges": len(self.edges)}


# --- reading the two sources ----------------------------------------------------

def read_shipped(path=SHIPPED):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise GraphError(f"the shipped vocabulary graph cannot be read: {exc}",
                         "reinstall jsk; the file ships with it") from None
    concepts = data.get("concepts")
    if not isinstance(concepts, dict):
        raise GraphError(f"{path}: no `concepts` object", "the file maps concept ids to entries")
    for cid, entry in concepts.items():
        if "implies" in entry:
            raise GraphError(f"shipped concept {cid!r} has an `implies` edge",
                             "implies reaches a capability, and the shipped graph holds "
                             "technologies only - move it to a knowledge base")
    return concepts


def parse_clauses(rest, where, warnings):
    """`labels: a, b; is-a: x (from app)` -> [(key, [values], provenance)]."""
    out = []
    for clause in filter(None, (c.strip() for c in (rest or "").split(";"))):
        key, sep, values = clause.partition(":")
        key = key.strip().lower()
        if not sep or key not in CLAUSE_KEYS:
            warnings.append(f"{where}: {clause!r} is not a vocabulary clause and is ignored")
            continue
        provenance = ""
        found = FROM.search(values)
        if found:
            provenance, values = found.group(1).strip(), values[:found.start()]
        items = [v.strip() for v in values.split(",") if v.strip()]
        out.append((key, items, provenance))
    return out


def read_kb(section):
    """The `## Vocabulary` section as kbindex.read_kb returns it -> declarations."""
    declared, warnings = [], []
    if section is None:
        return declared, warnings
    for entry in section["entries"]:
        title = entry["title"].strip().lower()
        if title.startswith("seniority"):
            continue
        kind = KINDS.get(title, title)
        for n, line in entry["body"]:
            m = LINE.match(line)
            if not m:
                continue
            where = f"## Vocabulary line {n}"
            declared.append({"id": normalise(m.group(1)), "kind": kind, "line": n,
                             "clauses": parse_clauses(m.group(2), where, warnings)})
    return declared, warnings


# --- merging ------------------------------------------------------------------

def merge(shipped, declared, tags):
    """-> concepts, names, display, former, edges, distinct, kb_edges.

    Refuses what cannot be merged: an edge to a concept nobody declared, a shipped
    technology redeclared as something else, a `not:` with nothing to remove.
    """
    concepts, names, former, edges, distinct, kb_edges = {}, {}, {}, set(), set(), []
    display = {}

    def add_label(cid, label, shown=True):
        names.setdefault(normalise(label), set()).add(cid)
        if shown and label not in display.setdefault(cid, []):
            display[cid].append(label)

    for cid, entry in shipped.items():
        cid = normalise(cid)
        concepts[cid] = "technology"
        names.setdefault(cid, set()).add(cid)
        display.setdefault(cid, [])
        for label in entry.get("labels", []):
            add_label(cid, label)
        for f in entry.get("former", []):
            add_label(cid, f["label"], shown=False)
            former.setdefault(cid, []).append((f["label"], int(f["until"])))
        for kind in COUNTS_AS:
            for target in entry.get(kind, []):
                edges.add((cid, normalise(target), kind))
        for target in entry.get("distinct", []):
            distinct.add(frozenset((cid, normalise(target))))

    removals = []
    for d in declared:
        cid, where = d["id"], f"## Vocabulary line {d['line']}"
        if cid in shipped and d["kind"] != "technology":
            raise GraphError(f"{where}: `{cid}` is a shipped technology, declared as a {d['kind']}",
                             "declare it under ### Technologies, or give your concept its own id")
        concepts.setdefault(cid, d["kind"])
        names.setdefault(cid, set()).add(cid)
        display.setdefault(cid, [])
        for key, items, provenance in d["clauses"]:
            if key == "labels":
                for label in items:
                    add_label(cid, label)
            elif key == "former":
                for item in items:
                    m = FORMER.match(item)
                    if not m:
                        raise GraphError(f"{where}: former {item!r} has no year",
                                         "write former: Azure AD until 2023")
                    add_label(cid, m.group(1), shown=False)
                    former.setdefault(cid, []).append((m.group(1), int(m.group(2))))
            elif key == "not":
                removals += [(cid, item, where) for item in items]
            else:
                for target in items:
                    t = normalise(target)
                    if key == "distinct":
                        distinct.add(frozenset((cid, t)))
                    else:
                        edges.add((cid, t, key))
                    kb_edges.append(Edge(cid, key, t, provenance))

    for tag in tags:
        t = normalise(tag)
        if t not in concepts:
            concepts[t] = "tag"
            names.setdefault(t, set()).add(t)
            display.setdefault(t, [])

    for source, target, kind in sorted(edges):
        if target not in concepts:
            raise GraphError(f"`{source}` {kind} `{target}`, and `{target}` is not a concept",
                             f"declare `{target}` in ## Vocabulary, or fix the spelling")
    for pair in distinct:
        for cid in pair:
            if cid not in concepts:
                raise GraphError(f"distinct names `{cid}`, which is not a concept",
                                 f"declare `{cid}` in ## Vocabulary, or fix the spelling")

    for cid, item, where in removals:
        kind, _, value = item.partition(" ")
        kind, value = kind.strip().lower(), value.strip()
        if kind == "labels":
            owners = names.get(normalise(value), set())
            if cid not in owners or normalise(value) == cid:
                raise GraphError(f"{where}: not: labels {value} - `{cid}` has no such label",
                                 "remove the not: clause, or fix the spelling")
            owners.discard(cid)
            display[cid] = [x for x in display.get(cid, []) if normalise(x) != normalise(value)]
            former[cid] = [f for f in former.get(cid, []) if normalise(f[0]) != normalise(value)]
        elif kind in COUNTS_AS and (cid, normalise(value), kind) in edges:
            edges.discard((cid, normalise(value), kind))
        elif kind == "distinct" and frozenset((cid, normalise(value))) in distinct:
            distinct.discard(frozenset((cid, normalise(value))))
        else:
            raise GraphError(f"{where}: not: {item} - there is no such edge to remove",
                             "write not: <labels|is-a|part-of|implies|distinct> <value>")

    names = {k: sorted(v) for k, v in names.items() if v}
    return concepts, names, display, former, edges, distinct, kb_edges


# --- the database -------------------------------------------------------------

SCHEMA = (
    "CREATE NODE TABLE Concept(id STRING PRIMARY KEY, kind STRING)",
    "CREATE NODE TABLE Label(name STRING PRIMARY KEY)",
    "CREATE REL TABLE NAMES(FROM Label TO Concept)",
    "CREATE REL TABLE COUNTS_AS(FROM Concept TO Concept, kind STRING)",
)

# Kùzu-lineage Cypher: no list comprehensions, and nodes(e) is the interior only.
CLOSURE = (f"MATCH (a:Concept)-[e:COUNTS_AS*1..{HOP_LIMIT}]->(b:Concept) "
           "RETURN a.id, b.id, properties(nodes(e), 'id'), properties(rels(e), 'kind')")
REACH = "MATCH (a:Concept)-[:COUNTS_AS* SHORTEST 1..30]->(b:Concept) RETURN a.id, b.id"
CYCLES = ("MATCH (a:Concept)-[:COUNTS_AS]->(b:Concept), "
          "(b)-[e:COUNTS_AS* SHORTEST 1..30]->(a) RETURN a.id, b.id, properties(nodes(e), 'id')")
LOOPS = "MATCH (a:Concept)-[:COUNTS_AS]->(a) RETURN a.id"
LABELS = "MATCH (l:Label)-[:NAMES]->(c:Concept) RETURN l.name, c.id"


def query(concepts, names, edges):
    """Build the database, ask it everything once, close it."""
    import ladybug as lb

    db = lb.Database(":memory:")
    conn = lb.Connection(db)
    try:
        for statement in SCHEMA:
            conn.execute(statement)
        conn.execute("UNWIND $rows AS r CREATE (:Concept {id: r.id, kind: r.kind})",
                     {"rows": [{"id": c, "kind": k} for c, k in sorted(concepts.items())]})
        conn.execute("UNWIND $rows AS r CREATE (:Label {name: r})", {"rows": sorted(names)})
        conn.execute("UNWIND $rows AS r MATCH (l:Label {name: r.l}), (c:Concept {id: r.c}) "
                     "CREATE (l)-[:NAMES]->(c)",
                     {"rows": [{"l": n, "c": c} for n, cs in sorted(names.items()) for c in cs]})
        conn.execute("UNWIND $rows AS r MATCH (a:Concept {id: r.a}), (b:Concept {id: r.b}) "
                     "CREATE (a)-[:COUNTS_AS {kind: r.k}]->(b)",
                     {"rows": [{"a": a, "b": b, "k": k} for a, b, k in sorted(edges)]})
        loops = conn.execute(LOOPS).get_all()
        cycles = conn.execute(CYCLES).get_all()
        closure = conn.execute(CLOSURE).get_all()
        reach = conn.execute(REACH).get_all()
        labels = conn.execute(LABELS).get_all()
    finally:
        conn.close()
        db.close()
    return loops, cycles, closure, reach, labels


def load(vocabulary=None, tags=(), shipped=SHIPPED):
    """The merged, validated graph. `vocabulary` is kbindex's `## Vocabulary` section."""
    declared, warnings = read_kb(vocabulary)
    concepts, names, display, former, edges, distinct, kb_edges = \
        merge(read_shipped(shipped), declared, tags)
    loops, cycles, rows, reach_rows, label_rows = query(concepts, names, edges)

    if loops:
        raise GraphError(f"`{loops[0][0]}` counts as itself",
                         "remove the edge from the concept to itself")
    if cycles:
        a, b, interior = cycles[0]
        ring = " -> ".join([a, b] + list(interior) + [a])
        raise GraphError(f"the counts-as edges form a cycle: {ring}",
                         "remove one edge; counts-as runs narrower to broader only")

    reach = {}
    for a, b in reach_rows:
        reach.setdefault(a, set()).add(b)
    for pair in sorted(distinct, key=sorted):
        a, b = sorted(pair)
        if b in reach.get(a, ()) or a in reach.get(b, ()):
            raise GraphError(f"`{a}` and `{b}` are distinct, but a counts-as path joins them",
                             "remove the edge that connects them, or the distinct")

    closure = {}
    for a, b, interior, kinds in rows:
        path = Path(tuple([a] + list(interior) + [b]), tuple(kinds))
        best = closure.get((a, b))
        if best is None or (path.hops, path.implied, path.nodes) < \
                (best.hops, best.implied, best.nodes):
            closure[(a, b)] = path

    labels = {}
    for name, cid in label_rows:
        labels.setdefault(name, []).append(cid)
    labels = {k: sorted(v) for k, v in labels.items()}
    return Graph(concepts, labels, display, former, closure, reach, edges, distinct, kb_edges,
                 warnings)
```

Then in `src/jsk/preflight.py`: `MODULES = ["cli", "cliutil", "kb", "kbindex", "paths", "vocabgraph"]`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_vocabgraph.py -q`
Expected: PASS, every test in the file.
Run: `python -m ruff check src tests`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/jsk/vocabgraph.py tests/test_vocabgraph.py src/jsk/preflight.py
git commit -m "feat: vocabgraph merges, validates and answers from LadybugDB" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The shipped graph — `src/jsk/data/vocabulary-graph.json`

**Files:**
- Create: `src/jsk/data/vocabulary-graph.json`
- Create: `tests/test_vocabulary_data.py`
- Modify: `src/jsk/preflight.py` — a required "shipped vocabulary graph" check (spec section 5: the shipped file is validated in `jsk doctor`)
- Test: `tests/test_preflight.py`

**Interfaces:**
- Consumes: `vocabgraph.load()`, `vocabgraph.read_shipped()`, `vocabgraph.normalise()`, `vocabgraph.SHIPPED` (Task 2).
- Produces: the default graph every `load()` without `shipped=` reads.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vocabulary_data.py`:

```python
"""The graph shipped with jsk. Everything here is a property of the data file, so a bad
edge in a curation commit fails CI before it reaches anyone's ranking."""
import json
import time
import unittest

import fixtures  # noqa: F401 - puts src/ on the path

from jsk import vocabgraph as vg


class TheShippedFile(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(vg.SHIPPED, encoding="utf-8") as fh:
            cls.raw = json.load(fh)
        cls.graph = vg.load()

    def test_it_loads_and_validates(self):
        self.assertGreaterEqual(self.graph.stats()["concepts"], 40)

    def test_it_holds_technologies_only(self):
        """Capability edges are judgement; judgement shipped to everyone overclaims."""
        offenders = [c for c, e in self.raw["concepts"].items() if "implies" in e]
        self.assertEqual(offenders, [])
        self.assertEqual(set(self.graph.concepts.values()), {"technology"})

    def test_every_id_is_already_normalised(self):
        bad = [c for c in self.raw["concepts"] if c != vg.normalise(c)]
        self.assertEqual(bad, [])

    def test_no_label_is_ambiguous_in_the_shipped_graph(self):
        """Ambiguity is real, but it belongs to a person's field, not to the default."""
        seen = {}
        for cid, entry in self.raw["concepts"].items():
            names = entry.get("labels", []) + [f["label"] for f in entry.get("former", [])]
            for label in names:
                seen.setdefault(vg.normalise(label), set()).add(cid)
        clashes = {k: v for k, v in seen.items() if len(v) > 1 or (k in self.raw["concepts"]
                                                                   and k not in v)}
        self.assertEqual(clashes, {})

    def test_the_cases_the_spec_names(self):
        g = self.graph
        self.assertEqual(g.resolve("K8s"), ["kubernetes"])
        self.assertEqual(g.resolve("Dot Net"), ["dotnet"])
        self.assertEqual(g.resolve(".NET Framework"), ["dotnet-framework"])
        self.assertEqual(g.resolve("Azure AD"), ["entra-id"])
        self.assertIsNotNone(g.satisfies("aks", "kubernetes"))
        self.assertIsNone(g.satisfies("kubernetes", "aks"))
        self.assertTrue(g.is_distinct("dotnet", "dotnet-framework"))
        self.assertTrue(g.is_distinct("java", "javascript"))
        self.assertTrue(g.is_distinct("angular", "angularjs"))

    def test_it_loads_fast(self):
        start = time.perf_counter()
        vg.load()
        self.assertLess(time.perf_counter() - start, 1.5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_vocabulary_data.py -q`
Expected: FAIL — `GraphError: the shipped vocabulary graph cannot be read`.

- [ ] **Step 3: Write the data**

Create `src/jsk/data/vocabulary-graph.json`:

```json
{
  "version": 1,
  "concepts": {
    "kubernetes": {"labels": ["Kubernetes", "K8s"]},
    "aks": {"labels": ["AKS", "Azure Kubernetes Service"], "is-a": ["kubernetes"], "part-of": ["azure"]},
    "eks": {"labels": ["EKS", "Amazon EKS", "Amazon Elastic Kubernetes Service"], "is-a": ["kubernetes"], "part-of": ["aws"]},
    "gke": {"labels": ["GKE", "Google Kubernetes Engine"], "is-a": ["kubernetes"], "part-of": ["gcp"]},
    "openshift": {"labels": ["OpenShift", "Red Hat OpenShift"], "is-a": ["kubernetes"]},
    "helm": {"labels": ["Helm"], "part-of": ["kubernetes"]},
    "docker": {"labels": ["Docker"]},

    "azure": {"labels": ["Azure", "Microsoft Azure", "MS Azure"]},
    "aws": {"labels": ["AWS", "Amazon Web Services"]},
    "gcp": {"labels": ["GCP", "Google Cloud", "Google Cloud Platform"]},
    "azure-functions": {"labels": ["Azure Functions"], "part-of": ["azure"]},
    "aws-lambda": {"labels": ["AWS Lambda", "Lambda"], "part-of": ["aws"]},
    "entra-id": {"labels": ["Entra ID", "Microsoft Entra ID"],
                 "former": [{"label": "Azure AD", "until": 2023}, {"label": "Azure Active Directory", "until": 2023}],
                 "part-of": ["azure"]},
    "bicep": {"labels": ["Bicep", "Azure Bicep"], "part-of": ["azure"]},
    "cloudformation": {"labels": ["CloudFormation", "AWS CloudFormation"], "part-of": ["aws"]},
    "terraform": {"labels": ["Terraform", "HashiCorp Terraform"]},
    "ansible": {"labels": ["Ansible"]},

    "dotnet": {"labels": [".NET", "Dot Net", "DotNet", ".NET Core"], "distinct": ["dotnet-framework"]},
    "dotnet-framework": {"labels": [".NET Framework", "Dot Net Framework"]},
    "csharp": {"labels": ["C#", "C Sharp"], "part-of": ["dotnet"]},
    "fsharp": {"labels": ["F#", "F Sharp"], "part-of": ["dotnet"]},
    "aspnet-core": {"labels": ["ASP.NET Core"], "part-of": ["dotnet"]},
    "entity-framework": {"labels": ["Entity Framework", "EF Core", "Entity Framework Core"], "part-of": ["dotnet"]},
    "linq": {"labels": ["LINQ"], "part-of": ["csharp"]},

    "java": {"labels": ["Java"], "distinct": ["javascript"]},
    "spring-boot": {"labels": ["Spring Boot"], "part-of": ["java"]},
    "kotlin": {"labels": ["Kotlin"]},
    "javascript": {"labels": ["JavaScript", "JS", "ECMAScript"]},
    "typescript": {"labels": ["TypeScript", "TS"]},
    "nodejs": {"labels": ["Node.js", "NodeJS", "Node"]},
    "react": {"labels": ["React", "React.js", "ReactJS"]},
    "nextjs": {"labels": ["Next.js", "NextJS"], "part-of": ["react"]},
    "angular": {"labels": ["Angular"], "distinct": ["angularjs"]},
    "angularjs": {"labels": ["AngularJS", "Angular.js"]},
    "vue": {"labels": ["Vue", "Vue.js", "VueJS"]},

    "python": {"labels": ["Python", "Python 3"]},
    "django": {"labels": ["Django"], "part-of": ["python"]},
    "fastapi": {"labels": ["FastAPI"], "part-of": ["python"]},
    "golang": {"labels": ["Go", "Golang"]},
    "rust": {"labels": ["Rust"]},

    "postgresql": {"labels": ["PostgreSQL", "Postgres"]},
    "sql-server": {"labels": ["SQL Server", "MSSQL", "MS SQL", "Microsoft SQL Server"]},
    "azure-sql": {"labels": ["Azure SQL", "Azure SQL Database"], "is-a": ["sql-server"], "part-of": ["azure"]},
    "mysql": {"labels": ["MySQL"]},
    "mongodb": {"labels": ["MongoDB", "Mongo"]},
    "cosmos-db": {"labels": ["Cosmos DB", "Azure Cosmos DB", "CosmosDB"], "part-of": ["azure"]},
    "redis": {"labels": ["Redis"]},
    "kafka": {"labels": ["Kafka", "Apache Kafka"]},
    "rabbitmq": {"labels": ["RabbitMQ"]},

    "apache-spark": {"labels": ["Spark", "Apache Spark"]},
    "pyspark": {"labels": ["PySpark"], "part-of": ["apache-spark"]},
    "databricks": {"labels": ["Databricks", "Azure Databricks"]},
    "snowflake": {"labels": ["Snowflake"]},
    "airflow": {"labels": ["Airflow", "Apache Airflow"]},
    "pytorch": {"labels": ["PyTorch"]},
    "tensorflow": {"labels": ["TensorFlow"]},
    "scikit-learn": {"labels": ["scikit-learn", "sklearn"]},

    "github-actions": {"labels": ["GitHub Actions"]},
    "azure-devops": {"labels": ["Azure DevOps", "ADO"],
                     "former": [{"label": "VSTS", "until": 2018}]},
    "jenkins": {"labels": ["Jenkins"]},
    "gitlab-ci": {"labels": ["GitLab CI", "GitLab CI/CD"]},
    "graphql": {"labels": ["GraphQL"]}
  }
}
```

- [ ] **Step 4: Doctor validates the shipped file**

Append to the `TheGraphEngine` class in `tests/test_preflight.py`:

```python
    def test_the_shipped_graph_is_checked_and_required(self):
        checks, _ = preflight.gather()
        graph = [c for c in checks if c.name.startswith("shipped vocabulary graph")]
        self.assertEqual(len(graph), 1)
        self.assertTrue(graph[0].ok, graph[0].disables)
        self.assertTrue(preflight.is_required(graph[0]))
        self.assertIn("concepts", graph[0].name)
```

In `src/jsk/preflight.py`, add beside `ladybug_opens()`:

```python
def shipped_graph():
    """(ok, summary-or-why) for the graph shipped with jsk, merged with nothing."""
    try:
        from . import vocabgraph

        stats = vocabgraph.load().stats()
        return True, f"{stats['concepts']} concepts, {stats['labels']} labels"
    except Exception as exc:        # GraphError, or the engine failing underneath it
        return False, f"{exc}"
```

and in `gather()`, right after the `vocabulary matching (ladybug)` check:

```python
    if ok:                          # the engine opened; otherwise that check already failed
        graph_ok, summary = shipped_graph()
        checks.append(Check(
            f"shipped vocabulary graph ({summary})" if graph_ok else "shipped vocabulary graph",
            graph_ok,
            disables=f"the graph shipped with jsk does not validate ({summary}), so "
                     "nothing can be ranked - reinstall jsk"))
```

`REQUIRED` gains `"shipped vocabulary graph"`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_vocabulary_data.py tests/test_vocabgraph.py tests/test_preflight.py -q`
Expected: PASS.

Also confirm the file ships in the wheel: `python -m pip install -e .` already covers an editable install; for a built wheel, `hatch` includes everything under `src/jsk` (`[tool.hatch.build.targets.wheel] packages = ["src/jsk"]`), so no manifest change is needed. Verify: `python -m build --wheel 2>/dev/null && python -c "import zipfile,glob; print([n for n in zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]).namelist() if 'vocabulary-graph' in n])"` — expect one entry. Skip if `build` is not installed; say so in the report.

- [ ] **Step 6: Commit**

```bash
git add src/jsk/data/vocabulary-graph.json tests/test_vocabulary_data.py src/jsk/preflight.py tests/test_preflight.py
git commit -m "feat: ship a curated technology vocabulary graph" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Ranking through the graph — `src/jsk/kbindex.py`

**Files:**
- Modify: `src/jsk/kbindex.py` — docstring (lines 1-27), imports, `rank()` (276-301), `build()` (336-435), `main()` error handling
- Test: `tests/test_kbindex.py`

**Interfaces:**
- Consumes: `vocabgraph.load`, `vocabgraph.GraphError`, `vocabgraph.normalise`, `vocabgraph.SHIPPED`, `Graph.resolve/satisfies/near_miss`, `Path.hops/implied/nodes` (Task 2).
- Produces:
  - `kbindex.rank(projects, posting, today, graph) -> list[row]`; row keys: `id, score, matched, near, missed, strength, recency`
  - `kbindex.counting_path(graph, terms, requirement, concept) -> Path | None`
  - `kbindex.graph_for(by_title, projects, shipped=vocabgraph.SHIPPED) -> Graph` (raises `KBError`, never `GraphError`)
  - `kbindex.build(text, posting_text=None, today=None, shipped=vocabgraph.SHIPPED) -> str`

- [ ] **Step 1: Write the failing tests**

In `tests/test_kbindex.py`:

1. Add imports and a fixture graph after `FENCE = "```"`:

```python
import json

from jsk import vocabgraph

GRAPH = {"version": 1, "concepts": {
    "dotnet": {"labels": [".NET", "Dot Net"]},
    "kubernetes": {"labels": ["Kubernetes", "K8s"]},
    "aks": {"labels": ["AKS"], "is-a": ["kubernetes"]},
    "golang": {"labels": ["Go", "Golang"]},
}}
GRAPH_DIR = tempfile.TemporaryDirectory()
GRAPH_PATH = str(Path(GRAPH_DIR.name) / "graph.json")
Path(GRAPH_PATH).write_text(json.dumps(GRAPH), encoding="utf-8")
```

2. Replace `ranking()` and the direct `rank` call in `test_the_order_is_by_score`:

```python
def graph(kb=KB):
    _, sections, _ = kbindex.read_kb(kb)
    return kbindex.graph_for(sections, kbindex.projects_of(sections), shipped=GRAPH_PATH)


def ranking(kb=KB, posting=POSTING):
    _, sections, _ = kbindex.read_kb(kb)
    return {r["id"]: r for r in kbindex.rank(kbindex.projects_of(sections),
                                             kbindex.read_posting(posting), TODAY, graph(kb))}
```

```python
    def test_the_order_is_by_score(self):
        _, sections, _ = kbindex.read_kb(KB)
        order = [r["id"] for r in kbindex.rank(kbindex.projects_of(sections),
                                               kbindex.read_posting(POSTING), TODAY, graph())]
        self.assertEqual(order, ["proj_alpha", "proj_beta", "proj_gamma"])
```

3. Replace `test_a_synonym_scores_as_absent` with:

```python
    def test_a_declared_label_scores_as_its_concept(self):
        """`.NET` is a label of dotnet in the graph, so it scores exactly as dotnet."""
        posting = POSTING.replace("value: dotnet", "value: .NET")
        self.assertEqual(ranking(posting=posting)["proj_alpha"]["score"], 19)

    def test_an_undeclared_synonym_still_scores_as_absent(self):
        """Nothing matches unless someone declared it: `dot.net` names nothing."""
        posting = POSTING.replace("value: dotnet", "value: dot.net")
        self.assertEqual(ranking(posting=posting)["proj_alpha"]["score"], 16)
```

4. Add a new class after `TheRankingIsTheAnalystsTable`:

```python
class TheGraphWidensOnlyWhatWasDeclared(unittest.TestCase):

    def test_a_narrower_tag_counts_and_says_how(self):
        kb = KB.replace("technologies: [python]", "technologies: [aks]")
        gamma = ranking(kb=kb)["proj_gamma"]
        self.assertIn("kubernetes (via aks) (preferred)", gamma["matched"])
        self.assertEqual(gamma["score"], 10)

    def test_a_broader_tag_is_a_near_miss_and_scores_nothing(self):
        posting = POSTING.replace("value: kubernetes", "value: aks")
        alpha = ranking(posting=posting)["proj_alpha"]
        self.assertEqual(alpha["score"], 18)
        self.assertIn("aks (holds broader kubernetes)", alpha["near"])

    def test_implies_cannot_carry_a_required_requirement(self):
        kb = KB.replace("### Capabilities\n",
                        "### Technologies\n\n- `terraform` — implies: infrastructure-as-code\n\n"
                        "### Capabilities\n\n- `infrastructure-as-code`\n")
        posting = POSTING.replace("value: terraform", "value: infrastructure-as-code")
        beta = ranking(kb=kb, posting=posting)["proj_beta"]
        self.assertIn("infrastructure-as-code", beta["missed"])
        self.assertIn("infrastructure-as-code (implied by terraform; confirm)", beta["near"])
        self.assertEqual(beta["score"], 9.5)

    def test_implies_carries_a_preferred_one(self):
        kb = KB.replace("### Capabilities\n",
                        "### Technologies\n\n- `terraform` — implies: infrastructure-as-code\n\n"
                        "### Capabilities\n\n- `infrastructure-as-code`\n")
        posting = POSTING.replace("value: kubernetes", "value: infrastructure-as-code")
        beta = ranking(kb=kb, posting=posting)["proj_beta"]
        self.assertIn("infrastructure-as-code (via terraform, implies) (preferred)",
                      beta["matched"])

    def test_an_ambiguous_label_is_asked_about(self):
        kb = KB.replace("### Capabilities\n",
                        "### Technologies\n\n- `go-game` — labels: Go\n\n### Capabilities\n")
        posting = POSTING.replace("value: kubernetes", "value: Go")
        report = kbindex.build(kb, posting, TODAY, shipped=GRAPH_PATH)
        self.assertIn("- `Go`: go-game | golang", report)
        self.assertIn("| Go | preferred | none | ambiguous: go-game | golang |", report)

    def test_a_candidate_term_is_listed(self):
        report = kbindex.build(KB, POSTING, TODAY, shipped=GRAPH_PATH)
        self.assertIn("- `quantum-annealing`", report)

    def test_a_graph_that_cannot_be_built_is_a_refusal_with_a_fix(self):
        kb = KB.replace("- `mentoring`\n", "- `mentoring` — part-of: nowhere\n")
        with self.assertRaises(kbindex.KBError) as caught:
            kbindex.build(kb, POSTING, TODAY, shipped=GRAPH_PATH)
        self.assertIn("nowhere", str(caught.exception))
        self.assertTrue(caught.exception.fix)
```

5. In `test_the_report_carries_what_an_agent_reads_it_for`, call `kbindex.build(KB, POSTING, TODAY, shipped=GRAPH_PATH)` and change the coverage assertion to:

```python
        self.assertIn("| quantum-annealing | preferred | none | candidate term |", report)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_kbindex.py -q`
Expected: FAIL — `AttributeError: module 'jsk.kbindex' has no attribute 'graph_for'` and signature errors.

- [ ] **Step 3: Implement**

`src/jsk/kbindex.py`:

- Docstring, replace the paragraph beginning `The ranking is the table in jsk-tailor-analyst.md` with:

```
The ranking is the table in jsk-tailor-analyst.md, computed rather than recited. A
requirement's value is the posting's own word - a label - and the vocabulary graph
(vocabgraph.py) resolves it to a concept and says whether a project's tag counts as
it: the same concept, or a narrower one within two hops. The graph is loaded only for
--rank, so the overview alone never pays for it.
```

- Imports: after `from .cliutil import docstring_usage, wants_help` add `from . import vocabgraph`.

- Replace `rank()` with:

```python
def graph_for(by_title, projects, shipped=vocabgraph.SHIPPED):
    """The graph this knowledge base ranks through. A GraphError becomes a KBError, so
    every refusal leaves `jsk index` the same way: a reason and a fix."""
    tags = [t for p in projects for t in p["capabilities"] + p["technologies"]]
    try:
        return vocabgraph.load(by_title.get("Vocabulary"), tags=tags, shipped=shipped)
    except vocabgraph.GraphError as exc:
        raise KBError(f"the vocabulary graph cannot be built: {exc}", exc.fix) from None


def counting_path(graph, terms, requirement, concept):
    """The path by which one of `terms` counts as `concept` for this requirement.

    Shortest first, and a path without `implies` before one with it. A path through
    `implies` never carries a required requirement: a tool standing in for a required
    capability is a stretch a person says yes to, not a script.
    """
    paths = [p for p in (graph.satisfies(t, concept) for t in terms) if p]
    path = min(paths, key=lambda p: (p.implied, p.hops, p.nodes), default=None)
    if path and path.implied and requirement["necessity"] == "required":
        return None
    return path


def matched_text(requirement, path):
    text = requirement["value"]
    if path.hops:
        text += f" (via {path.nodes[0]}{', implies' if path.implied else ''})"
    return text + ("" if requirement["necessity"] == "required" else " (preferred)")


def near_text(graph, terms, requirement, concept):
    """Why a requirement this project nearly carries does not count, or None."""
    implied = [p for p in (graph.satisfies(t, concept) for t in terms) if p and p.implied]
    if implied and requirement["necessity"] == "required":
        return f"{requirement['value']} (implied by {implied[0].nodes[0]}; confirm)"
    broader = [t for t in terms if graph.near_miss(t, concept)]
    if broader:
        return f"{requirement['value']} (holds broader {broader[0]})"
    return None


def rank(projects, posting, today, graph):
    reqs = posting["requirements"]
    level = posting.get("seniority")
    level_at = SENIORITY.index(level) if level in SENIORITY else None
    # One concept or none: an ambiguous label scores nothing until the analyst picks.
    concept = {r["value"]: (found[0] if len(found) == 1 else None)
               for r in reqs for found in [graph.resolve(r["value"])]}
    rows = []
    for p in projects:
        if p["retired"]:
            continue
        terms = sorted({vocabgraph.normalise(t) for t in p["capabilities"] + p["technologies"]})
        matched, near, missed = [], [], []
        for r in reqs:
            want = concept[r["value"]]
            path = counting_path(graph, terms, r, want) if want else None
            if path and r["necessity"] != "implicit":
                matched.append((r, path))
            elif want and r["necessity"] != "implicit":
                why = near_text(graph, terms, r, want)
                if why:
                    near.append(why)
            if r["necessity"] == "required" and not path:
                missed.append(r["value"])
        rec = recency_points(p["recency"], today)
        sen = 1 if level_at is not None and SENIORITY.index(p["block"]["seniority"]) <= level_at else 0
        score = sum(WEIGHTS[r["necessity"]] for r, _ in matched) + 2 * p["strength"] + rec + sen
        why = [matched_text(r, path) for r, path in matched]
        why.append(f"strength {p['strength']}")
        if rec:
            why.append("recent" if rec == 1 else "recency half")
        if sen:
            why.append("seniority-match")
        rows.append({"id": p["block"]["id"], "score": score, "matched": why, "near": near,
                     "missed": missed, "strength": p["strength"], "recency": p["recency"]})
    rows.sort(key=lambda r: (-r["score"], -r["strength"], -r["recency"], r["id"]))
    return rows
```

- `build()`: change the signature to `def build(text, posting_text=None, today=None, shipped=vocabgraph.SHIPPED):` and replace the whole `if posting_text is not None:` block with:

```python
    if posting_text is not None:
        posting = read_posting(posting_text)
        reqs = posting["requirements"]
        graph = graph_for(by_title, projects, shipped)
        resolved = {r["value"]: graph.resolve(r["value"]) for r in reqs}
        out += ["", "# Ranking", "",
                f"Against `{posting.get('title', 'the posting')}` at {posting.get('seniority') or 'no stated seniority'}: "
                f"{sum(r['necessity'] == 'required' for r in reqs)} required, "
                f"{sum(r['necessity'] == 'preferred' for r in reqs)} preferred, "
                f"{sum(r['necessity'] == 'implicit' for r in reqs)} implicit (implicit scores nothing).",
                "Required ×3 · preferred ×1 · strength ×2 · recency +1 within 3 years, +0.5 at 4-6 · "
                "seniority +1 at or above the posting's. A narrower tag counts as a broader "
                "requirement within two hops (`via`); a broader tag is a near miss and scores nothing.", "",
                "| Project | Score | Matched | Near | Missed |", "|---|---|---|---|---|"]
        if posting.get("seniority") not in SENIORITY:
            out.insert(-4, "The posting's seniority is missing or not one of the eight, so no "
                           "project earns the seniority point.")
        # Missed terms in full for the projects a resume leads with; below that the
        # Coverage table says the same thing from the requirement's side.
        for place, row in enumerate(rank(projects, posting, today, graph)):
            missed = (", ".join(row["missed"]) if place < TOP_MISSED
                      else f"{len(row['missed'])} required - see Coverage")
            out.append(f"| {row['id']} | {number(row['score'])} | {', '.join(row['matched'])} | "
                       f"{'; '.join(row['near'])} | {missed} |")

        ambiguous = {v: c for v, c in resolved.items() if len(c) > 1}
        unknown = [v for v, c in resolved.items() if not c]
        if ambiguous:
            out += ["", "Ambiguous labels score nothing until `value` is rewritten as the concept "
                        "id the posting means:", ""]
            out += [f"- `{v}`: {' | '.join(c)}" for v, c in ambiguous.items()]
        if unknown:
            out += ["", "Candidate terms - no shipped concept, vocabulary term or project tag "
                        "names them. Add a term or an edge, or report them as new:", ""]
            out += [f"- `{v}`" for v in unknown]

        out += ["", "# Coverage", "",
                "Which projects carry each requirement's term. A tag is not evidence: a project",
                "whose prose never shows the work is `unevidenced`. Read those ranges.", "",
                "| Requirement | Need | Tagged on | Note |", "|---|---|---|---|"]
        for r in reqs:
            found = resolved[r["value"]]
            carriers = [] if len(found) != 1 else [
                p["block"]["id"] for p in projects if not p["retired"] and counting_path(
                    graph, {vocabgraph.normalise(t) for t in p["capabilities"] + p["technologies"]},
                    r, found[0])]
            note = ("candidate term" if not found
                    else f"ambiguous: {' | '.join(found)}" if len(found) > 1 else "")
            out.append(f"| {r['value']} | {r['necessity']} | {', '.join(carriers) or 'none'} | {note} |")
    return "\n".join(out) + "\n"
```

The variable `known` and its two lines are gone; `used` is still computed above for the Vocabulary listing — leave that.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_kbindex.py -q`
Expected: PASS. The existing scores (19, 12.5, 9) must be unchanged — that is Review Focus item 1.
Run: `python -m pytest tests -q -n auto` and `python -m ruff check src tests`
Expected: PASS / clean.

- [ ] **Step 5: Commit**

```bash
git add src/jsk/kbindex.py tests/test_kbindex.py
git commit -m "feat: jsk index ranks through the vocabulary graph" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The command — `jsk vocab`

**Files:**
- Create: `src/jsk/vocab.py`
- Create: `tests/test_vocab.py`
- Modify: `src/jsk/cli.py` — docstring menu (lines 14-26, 28-31), `SIMPLE` (line 50-56)
- Modify: `src/jsk/preflight.py` — `MODULES` gains `"vocab"`
- Modify: `docs/SCRIPTS.md` — "The whole surface" block and a `### \`jsk vocab\`` section after `### \`jsk index\``
- Modify: `plugins/jsk/skills/jsk/SKILL.md` — one row in the command table (after the `jsk index` row, line 87)

**Interfaces:**
- Consumes: `vocabgraph.*` (Task 2), `kbindex.read_kb`, `kbindex.projects_of`, `kbindex.read_posting`, `kbindex.graph_for`, `kbindex.KBError`, `kbindex.yaml`, `kbindex.MarkdownIt` (Task 4).
- Produces: `vocab.main(argv) -> int`; pure helpers returning printable lines — `vocab.check_record(graph, doc) -> (fails, warns)`, `vocab.explain(graph, have, want) -> list[str]`, `vocab.names(graph, concept) -> list[str]`, `vocab.candidates(graph, apps_dir, shipped=vocabgraph.SHIPPED) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vocab.py`:

```python
"""jsk vocab: keeping the vocabulary graph honest. The helpers are tested against a
fixture graph; the command itself once, end to end, against the shipped one."""
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import CLI, run

from jsk import vocab, vocabgraph

GRAPH = {"version": 1, "concepts": {
    "kubernetes": {"labels": ["Kubernetes", "K8s"]},
    "aks": {"labels": ["AKS"], "is-a": ["kubernetes"]},
    "azure": {"labels": ["Azure"], "is-a": ["cloud-platform"]},
    "cloud-platform": {"labels": ["Cloud platform"], "is-a": ["computing"]},
    "computing": {"labels": ["Computing"]},
    "entra-id": {"labels": ["Entra ID"], "former": [{"label": "Azure AD", "until": 2023}],
                 "part-of": ["azure"]},
    "dotnet": {"labels": [".NET"], "distinct": ["dotnet-framework"]},
    "dotnet-framework": {"labels": [".NET Framework"]},
    "golang": {"labels": ["Go"]},
}}
TMP = tempfile.TemporaryDirectory()
SHIPPED = str(Path(TMP.name) / "graph.json")
Path(SHIPPED).write_text(json.dumps(GRAPH), encoding="utf-8")


def graph(**groups):
    section = None
    if groups:
        section = {"entries": [{"title": t, "body": list(enumerate(lines, 1))}
                               for t, lines in groups.items()]}
    return vocabgraph.load(section, shipped=SHIPPED)


class Explain(unittest.TestCase):

    def test_a_match_shows_its_path(self):
        self.assertEqual(vocab.explain(graph(), "AKS", "K8s"), ["match      aks -is-a-> kubernetes"])

    def test_broader_for_narrower_is_a_near_miss(self):
        self.assertIn("near miss", vocab.explain(graph(), "Kubernetes", "AKS")[0])

    def test_past_the_hop_limit(self):
        self.assertIn("past 2 hops", vocab.explain(graph(), "Entra ID", "Computing")[0])

    def test_a_distinct_pair(self):
        self.assertIn("distinct", vocab.explain(graph(), ".NET", ".NET Framework")[0])

    def test_an_unknown_label(self):
        self.assertIn("candidate term", vocab.explain(graph(), "K3s", "K8s")[0])

    def test_an_ambiguous_label(self):
        g = graph(Technologies=["- `go-game` — labels: Go"])
        self.assertIn("ambiguous", vocab.explain(g, "Go", "Go")[0])


class Names(unittest.TestCase):

    def test_by_id_or_by_label(self):
        self.assertEqual(vocab.names(graph(), "entra-id")[0], "Entra ID (formerly Azure AD)")
        self.assertEqual(vocab.names(graph(), "AKS"), vocab.names(graph(), "aks"))

    def test_an_unknown_concept_is_a_refusal(self):
        with self.assertRaises(vocabgraph.GraphError):
            vocab.names(graph(), "nothing-here")


class CheckRecord(unittest.TestCase):

    def test_a_narrower_alias_fails(self):
        doc = {"skills": [{"id": "skill_k8s", "name": "Kubernetes", "concept": "kubernetes",
                           "aliases": ["K8s", "AKS"]}]}
        fails, warns = vocab.check_record(graph(), doc)
        self.assertEqual(len(fails), 1)
        self.assertIn("AKS", fails[0])

    def test_a_broader_or_render_only_alias_passes(self):
        """`Entra ID (formerly Azure AD)` is written for the render; it names nothing."""
        doc = {"skills": [{"id": "skill_entra", "name": "Entra ID", "concept": "entra-id",
                           "aliases": ["Azure", "Entra ID (formerly Azure AD)"]}]}
        self.assertEqual(vocab.check_record(graph(), doc), ([], []))

    def test_an_unknown_concept_warns(self):
        doc = {"skills": [{"id": "skill_x", "name": "X", "concept": "nope"}]}
        fails, warns = vocab.check_record(graph(), doc)
        self.assertEqual(fails, [])
        self.assertIn("nope", warns[0])


class Candidates(unittest.TestCase):

    def posting(self, root, name, *values):
        d = Path(root) / name
        d.mkdir()
        reqs = "".join(f"  - value: {v}\n    necessity: preferred\n" for v in values)
        (d / "posting.md").write_text(f"---\ntitle: x\nrequirements:\n{reqs}---\n\nAd.\n",
                                      encoding="utf-8")

    def test_unknown_labels_are_counted_by_posting(self):
        with tempfile.TemporaryDirectory() as root:
            self.posting(root, "2026-09-01-a", "K3s", "K8s")
            self.posting(root, "2026-09-02-b", "k3s")
            (Path(root) / "2026-09-03-broken").mkdir()
            (Path(root) / "2026-09-03-broken" / "posting.md").write_text("no frontmatter",
                                                                         encoding="utf-8")
            lines = vocab.candidates(graph(), root, shipped=SHIPPED)
        text = "\n".join(lines)
        self.assertIn("| k3s | 2 |", text)
        self.assertNotIn("| k8s |", text)
        self.assertIn("2026-09-03-broken", text)          # reported, not fatal

    def test_knowledge_base_edges_the_shipped_graph_lacks(self):
        g = graph(Technologies=["- `k3s` — is-a: kubernetes (from 2026-09-01-a)"])
        with tempfile.TemporaryDirectory() as root:
            lines = vocab.candidates(g, root, shipped=SHIPPED)
        self.assertIn("- k3s is-a kubernetes (from 2026-09-01-a)", lines)


class TheCommand(unittest.TestCase):

    def test_explain_against_the_shipped_graph(self):
        code, out = run(CLI, "vocab", "explain", "AKS", "K8s")
        self.assertEqual(code, 0, out)
        self.assertIn("match", out)

    def test_check_with_no_knowledge_base(self):
        code, out = run(CLI, "vocab", "check")
        self.assertEqual(code, 0, out)
        self.assertIn("concepts", out)

    def test_called_wrongly(self):
        code, _ = run(CLI, "vocab", "explain", "only-one")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_vocab.py -q`
Expected: FAIL — `ImportError: cannot import name 'vocab' from 'jsk'`.

- [ ] **Step 3: Implement**

Create `src/jsk/vocab.py`:

```python
#!/usr/bin/env python3
"""Keep the vocabulary graph honest: check it, explain a match, list a concept's names,
and find the posting labels worth writing an edge for.

Usage: jsk vocab check [--kb KB] [--record resume.json]
       jsk vocab explain HAVE WANT [--kb KB]
       jsk vocab names CONCEPT [--kb KB]
       jsk vocab candidates APPLICATIONS_DIR [--kb KB]

Exit 0 = printed, nothing refused. Exit 1 = the graph, the knowledge base or the record
could not be read as written, or a record's alias names a narrower concept. Exit 2 =
called wrongly.

Without --kb only the graph shipped with jsk is loaded. With it, the knowledge base's
## Vocabulary clauses and every project tag join it: the graph `jsk index --rank` scores
through. Reading a knowledge base or a posting needs the optional `index` extra.

The record check lives here rather than in validate_urs because the gates never load
the graph: validate_urs runs in `jsk doctor`'s end-to-end check and on every ship, and
reads the record alone.
"""
import glob
import json
import os
import sys

from . import kbindex, vocabgraph
from .cliutil import docstring_usage, wants_help

VERBS = {"check": 0, "explain": 2, "names": 1, "candidates": 1}


def need_index():
    if kbindex.yaml is None or kbindex.MarkdownIt is None:
        raise kbindex.KBError("reading a knowledge base or a posting needs markdown-it-py and "
                              "pyyaml, and this Python has not got them",
                              'python -m pip install markdown-it-py pyyaml   (the "index" extra)')


def load_graph(kb_path, shipped=vocabgraph.SHIPPED):
    if kb_path is None:
        return vocabgraph.load(shipped=shipped)
    need_index()
    with open(kb_path, encoding="utf-8") as fh:
        _, by_title, _ = kbindex.read_kb(fh.read())
    projects = kbindex.projects_of(by_title) if "Projects" in by_title else []
    return kbindex.graph_for(by_title, projects, shipped)


def one_concept(graph, label):
    """(concept, None) or (None, why there is not exactly one)."""
    found = graph.resolve(label)
    if not found:
        return None, f"{label!r} names no concept - a candidate term"
    if len(found) > 1:
        return None, f"{label!r} is ambiguous: {' | '.join(found)} - write the concept id"
    return found[0], None


def explain(graph, have, want):
    h, why = one_concept(graph, have)
    w, why_w = one_concept(graph, want)
    if why or why_w:
        return [f"no match   {why or why_w}"]
    path = graph.satisfies(h, w)
    if path:
        steps = h + "".join(f" -{k}-> {n}" for k, n in zip(path.kinds, path.nodes[1:]))
        out = [f"match      {steps}"]
        if path.implied:
            out.append("           through implies: counts for a preferred requirement, "
                       "never a required one")
        return out
    if graph.is_distinct(h, w):
        return [f"no match   {h} and {w} are distinct: nothing may connect them"]
    if graph.near_miss(h, w):
        return [f"no match   {w} is narrower than {h}: holding the broader thing is not "
                f"enough (a near miss)"]
    if graph.beyond_limit(h, w):
        return [f"no match   {w} is reachable from {h} only past {vocabgraph.HOP_LIMIT} hops"]
    return [f"no match   nothing connects {h} to {w}"]


def names(graph, concept):
    cid = concept if concept in graph.concepts else None
    if cid is None:
        cid, why = one_concept(graph, concept)
        if cid is None:
            raise vocabgraph.GraphError(why, "jsk vocab check lists what the graph holds")
    return graph.names(cid).for_render()


def check_record(graph, doc):
    """A skill's aliases may be its own or broader labels, never a narrower concept's."""
    fails, warns = [], []
    for skill in doc.get("skills") or []:
        cid = skill.get("concept")
        if not cid:
            continue
        if cid not in graph.concepts:
            warns.append(f"skill {skill.get('id')}: concept {cid!r} is not in the graph")
            continue
        for alias in skill.get("aliases") or []:
            found = graph.resolve(alias)
            narrower = [c for c in found if c != cid and graph.satisfies(c, cid)]
            if found and narrower and cid not in found and len(narrower) == len(found):
                fails.append(f"skill {skill.get('id')}: alias {alias!r} names "
                             f"{', '.join(narrower)}, narrower than {cid} - holding {cid} "
                             f"is not holding that")
    return fails, warns


def shipped_edges(path):
    edges = set()
    for cid, entry in vocabgraph.read_shipped(path).items():
        for kind in vocabgraph.EDGE_KEYS:
            for target in entry.get(kind, []):
                edges.add((vocabgraph.normalise(cid), vocabgraph.normalise(target), kind))
    return edges


def candidates(graph, apps_dir, shipped=vocabgraph.SHIPPED):
    need_index()
    unknown, ambiguous, skipped = {}, {}, []
    postings = sorted(glob.glob(os.path.join(apps_dir, "*", "posting.md")))
    for path in postings:
        app = os.path.basename(os.path.dirname(path))
        try:
            with open(path, encoding="utf-8") as fh:
                reqs = kbindex.read_posting(fh.read())["requirements"]
        except (OSError, kbindex.KBError) as exc:
            skipped.append(f"- {app}: {exc}")
            continue
        for r in reqs:
            found = graph.resolve(r["value"])
            key = vocabgraph.normalise(r["value"])
            if not found:
                unknown.setdefault(key, set()).add(app)
            elif len(found) > 1:
                ambiguous.setdefault(key, (set(), found))[0].add(app)

    out = [f"Candidate terms across {len(postings)} postings - no concept names them:", "",
           "| label | postings |", "|---|---|"]
    out += [f"| {k} | {len(v)} |" for k, v in sorted(unknown.items(), key=lambda i: (-len(i[1]), i[0]))]
    out += ["", "Ambiguous labels:", "", "| label | postings | could mean |", "|---|---|---|"]
    out += [f"| {k} | {len(apps)} | {' | '.join(c)} |"
            for k, (apps, c) in sorted(ambiguous.items(), key=lambda i: (-len(i[1][0]), i[0]))]
    upstream = shipped_edges(shipped)
    proposals = [e for e in graph.kb_edges if graph.concepts.get(e.source) == "technology"
                 and (e.source, e.target, e.kind) not in upstream]
    out += ["", "Knowledge-base technology edges the shipped graph lacks - proposals for upstream:", ""]
    out += [f"- {e.source} {e.kind} {e.target}" + (f" (from {e.provenance})" if e.provenance else "")
            for e in proposals] or ["- none"]
    if skipped:
        out += ["", "Postings that could not be read, and were skipped:", ""] + skipped
    return out


def take(argv, flag):
    if flag not in argv:
        return None
    at = argv.index(flag)
    if at + 1 >= len(argv):
        raise SystemExit(f"{flag} needs a value")
    value = argv[at + 1]
    del argv[at:at + 2]
    return value


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2
    try:
        kb, record = take(argv, "--kb"), take(argv, "--record")
    except SystemExit as exc:
        print(exc)
        return 2
    verb, args = argv[0], argv[1:]
    if verb not in VERBS or len(args) != VERBS[verb] or (record and verb != "check"):
        print(docstring_usage(__doc__))
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    try:
        graph = load_graph(kb)
        if verb == "explain":
            lines, code = explain(graph, *args), 0
        elif verb == "names":
            lines, code = names(graph, args[0]), 0
        elif verb == "candidates":
            lines, code = candidates(graph, args[0]), 0
        else:
            s = graph.stats()
            lines = [f"ok    {s['concepts']} concepts, {s['labels']} labels, {s['edges']} edges"]
            lines += [f"warn  {w}" for w in graph.warnings]
            code = 0
            if record:
                with open(record, encoding="utf-8") as fh:
                    fails, warns = check_record(graph, json.load(fh))
                lines += [f"FAIL  {f}" for f in fails] + [f"warn  {w}" for w in warns]
                code = 1 if fails else 0
    except OSError as exc:
        print(f"FAIL  cannot read {exc.filename}: {exc.strerror}")
        return 1
    except ValueError as exc:                                # a record that is not JSON
        print(f"FAIL  {record}: not valid JSON - {exc}")
        return 1
    except (kbindex.KBError, vocabgraph.GraphError) as exc:
        print(f"FAIL  {exc}")
        print(f"fix:  {exc.fix}")
        return 1
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
```

`src/jsk/cli.py`:

- In the docstring menu, after the `jsk index KB [--rank POST]` line, add:

```
    jsk vocab check|explain|names|candidates   the vocabulary graph: validate, explain, list
```

- Change `Only \`jsk index\` reads \`user-knowledgebase.md\`, and it never writes it.` to `Only \`jsk index\` and \`jsk vocab --kb\` read \`user-knowledgebase.md\`, and neither writes it.`
- Change the last docstring paragraph to: `Standard library only, pymupdf to read a PDF, markdown-it-py with pyyaml for \`jsk index\`, and LadybugDB for the vocabulary graph.` (keep it starting with `Standard library` — `usage()` splits on that phrase).
- `SIMPLE` gains `"vocab": ("vocab.py", "check, explain and list the vocabulary graph"),` after `"index"`.

`src/jsk/preflight.py`: `MODULES` gains `"vocab"`.

`docs/SCRIPTS.md`:

- In "The whole surface" code block, after the `jsk index ...` line, add:

```
jsk vocab explain AKS K8s        # why two terms match, or which rule stopped them
```

- After the `### \`jsk index\`` section (before `## The record`), add:

````markdown
### `jsk vocab`

The vocabulary graph `jsk index --rank` scores through: the graph shipped with jsk
(technologies only) plus the knowledge base's `## Vocabulary` clauses and every project tag.

```bash
jsk vocab check --kb user-knowledgebase.md                        # validate the merged graph
jsk vocab check --kb user-knowledgebase.md --record resume.json   # plus a record's skill aliases
jsk vocab explain AKS K8s --kb user-knowledgebase.md              # the path, or the rule that stopped it
jsk vocab names entra-id                                          # what a render may call a concept
jsk vocab candidates applications --kb user-knowledgebase.md      # posting labels nothing names, by frequency
```

Exit 0 printed; exit 1 refused (a graph that cannot be built, or a skill alias that names a
narrower concept); exit 2 called wrongly. `--kb` and `candidates` need the `index` extra.
````

`plugins/jsk/skills/jsk/SKILL.md`, after the `jsk index` row (line 87):

```markdown
| `jsk vocab check\|explain\|names\|candidates [--kb <kb>]` | the vocabulary graph: validate, explain a match, a concept's names, unknown labels |
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_vocab.py tests/test_plugin_surface.py tests/test_budget.py tests/test_cli.py tests/test_preflight.py -q`
Expected: PASS — including `test_the_help_text_lists_every_subcommand`, `test_the_scripts_page_lists_every_subcommand`, `test_SKILL_md_names_every_subcommand` and the SKILL.md budget (< 2400).
Run: `python -m pytest tests -q -n auto` and `python -m ruff check src tests`
Expected: PASS / clean.

- [ ] **Step 5: Commit**

```bash
git add src/jsk/vocab.py tests/test_vocab.py src/jsk/cli.py src/jsk/preflight.py docs/SCRIPTS.md plugins/jsk/skills/jsk/SKILL.md
git commit -m "feat: jsk vocab checks, explains and lists the vocabulary graph" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The interface in writing — specs, template and agents

**Files:**
- Modify: `plugins/jsk/skills/jsk/references/kb-spec.md:82-99` (the `### Vocabulary` section)
- Modify: `plugins/jsk/skills/jsk/references/urs-spec.md:212-225` (the `### Skill` section)
- Modify: `src/jsk/kb.py:103-116` (the template's `## Vocabulary`)
- Modify: `plugins/jsk/agents/jsk-tailor-analyst.md` (the requirements YAML comment, line ~46, and the `value` bullet, lines 60-63)
- Modify: `plugins/jsk/agents/jsk-kb-auditor.md` (items at lines ~73 and ~104)
- Modify: `plugins/jsk/agents/jsk-resume-author.md` (where it writes `skills`)
- Test: `tests/test_budget.py`, `tests/test_plugin_surface.py` (existing; no new tests)

**Interfaces:**
- Consumes: the behaviour of Tasks 2-5 exactly as implemented; read `src/jsk/vocab.py`'s usage text before writing any command line.
- Produces: nothing code depends on.

- [ ] **Step 1: kb-spec.md — replace the `### Vocabulary` section's first paragraph and example (lines 84-92) with:**

````markdown
The matching axis. Project tags are **concept ids**; a posting's words are **labels** that the
vocabulary graph resolves to them — the graph shipped with jsk (technologies only) plus the clauses
written here. Only backticked list items count; prose and fenced examples are ignored.

```markdown
### Technologies

- `aks` — labels: Azure Kubernetes Service; is-a: kubernetes
- `terraform` — implies: infrastructure-as-code (from 2026-09-12-contoso-architect)

### Capabilities

- `infrastructure-as-code` — labels: IaC
```

Clauses, `;`-separated: `labels:`, `former: Azure AD until 2023`, `is-a:` and `part-of:` and
`implies:` (narrower to broader), `distinct:` (never joined), `not: <kind> <value>` (drops a shipped
entry). A narrower concept counts toward a broader one within two hops, never the reverse; `implies`
never carries a required requirement; a label naming two concepts is asked about. A term never
declared still matches itself. `jsk vocab check --kb` validates this section and `jsk vocab explain`
shows why two terms do or do not match.
````

Keep the paragraphs that follow (`Add a term in the same edit…`, the closed `seniority` list) unchanged.

- [ ] **Step 2: urs-spec.md — in `### Skill`, add `"concept": "azure",` to the JSON example after `"category"`, and replace the sentence beginning `` `aliases` lets a renderer`` with:**

```markdown
`aliases` lets a renderer emit the variant a portal's literal keyword match expects. `concept` names
the vocabulary-graph concept the skill is; `jsk vocab names <concept>` gives the aliases a render may
add — its own and broader labels, never narrower. `identifier` is against ESCO or O*NET.
```

- [ ] **Step 3: kb.py template — replace the `## Vocabulary` comment and add a Technologies subsection:**

```
## Vocabulary

<!-- The matching axis. A posting's words are labels; the vocabulary graph - shipped with
     jsk, plus the clauses written here - resolves them to these concepts. A line may add
     labels:, is-a:, part-of:, implies:, distinct:, former: or not: clauses; kb-spec.md
     shows each. Add a term in the same edit that first uses it. Only backticked list
     items count as vocabulary. -->

### Technologies

_None recorded yet._

### Capabilities
```

(The rest — `_None recorded yet._` under Capabilities, `### Domains`, `### Seniority …` — unchanged.)

- [ ] **Step 4: jsk-tailor-analyst.md — two edits, net length about zero:**

In the requirements YAML example, change `# a term from the knowledge base's ## Vocabulary` to `# the posting's word; the graph resolves it`.

Replace the `value` bullet (lines 60-63) with:

```markdown
- **`value` is the posting's word, `label` its phrasing.** Write the label as advertised (`K8s`,
  `.NET`); the vocabulary graph resolves it. `jsk index --rank` lists **ambiguous** labels — rewrite
  each as the concept id meant — and **candidate terms** nothing names: report them as new, never
  bend one onto a near-match. A `Near` entry is not a match.
```

- [ ] **Step 5: jsk-kb-auditor.md** — in the item naming `## Vocabulary` (line ~73) and the paragraph flagging near-misses (line ~104), replace "invented synonyms" guidance with: `Run \`jsk vocab candidates <applications> --kb <kb>\` and propose an edge or a term for each label it lists; never propose one across a \`distinct\`.` Keep the auditor's "reads and reports; never edits" wording intact.

- [ ] **Step 6: jsk-resume-author.md** — where it describes writing `skills`, add one sentence: `A skill that is a vocabulary concept carries \`concept\`; take extra \`aliases\` from \`jsk vocab names <concept> --kb <kb>\` and check them with \`jsk vocab check --kb <kb> --record <resume.json>\`.` If the file has no skills paragraph, add it to the paragraph about the record's sections.

- [ ] **Step 7: Run the doc tests and the suite**

Run: `python -m pytest tests/test_budget.py tests/test_plugin_surface.py -q`
Expected: PASS. If a budget fails, shorten your own additions — do not raise a ceiling.
Run: `python -m pytest tests -q -n auto` and `python -m ruff check src tests`
Expected: PASS / clean.

- [ ] **Step 8: Commit**

```bash
git add plugins/jsk src/jsk/kb.py
git commit -m "docs: the vocabulary graph in the specs, the template and the agents" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## After the last task

- Run the whole suite on Windows (this machine) and in Docker on Linux with Python 3.10:
  `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/w" -w /w python:3.10-slim sh -c "pip install -q -e '.[dev]' && python -m pytest tests -q -n auto"`
- `jsk doctor` must print `ok    vocabulary matching (ladybug)`.
- Whole-branch review against the spec before merging.
