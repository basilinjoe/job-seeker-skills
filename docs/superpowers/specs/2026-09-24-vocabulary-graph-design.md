# A vocabulary graph, so a posting's words match the knowledge base's

**Status:** design, approved 2026-09-24
**Scope:** `jsk` matching and packaging. No change to what a resume claims.

Every posting names the same thing differently: `K8s`, `Kubernetes`, `AKS`; `.NET`, `Dot Net`,
`ASP.NET Core`. Ranking compares requirement values against project tags as exact strings
([kbindex.py:284-287](../../../src/jsk/kbindex.py)), so today the analyst has to translate every
term into the knowledge base's slug by hand, on every application, and a missed translation
silently scores as absent.

This document replaces that hand translation with a maintained graph of terms, stored as data and
queried through LadybugDB.

## What stays true

- **Nothing matches unless someone declared it.** The graph widens matching only along edges a
  person wrote down. An undeclared synonym still scores zero.
- **Never a number you cannot show the terms behind.** Every match through the graph reports the
  path it took.
- **The data is the source of truth, not the database.** The database is rebuilt from text on every
  run and is never read back as the record.

## 1. Packaging

LadybugDB (`ladybug` on PyPI, MIT, formerly Kùzu) becomes the first hard dependency.

- `dependencies = ["ladybug>=0.20,<0.21"]`. Pinned to one minor, because releases in the Kùzu
  lineage have changed both API and storage format between minors. Raising it is a deliberate
  commit with the graph tests run against the new version.
- `requires-python = ">=3.10"` (was `>=3.8`). `ladybug` ships wheels for 3.10-3.14 on Windows
  x86_64, macOS arm64 and x86_64, and Linux x86_64, aarch64 and musl. 3.8 and 3.9 are past end of
  life and were never tested: CI ran 3.13 only.
- `MIN_PYTHON = (3, 10)` in `src/jsk/preflight.py`.
- The "deliberately empty" comment above `dependencies` is rewritten, not deleted. It keeps the rule
  (every other package is optional and imported at the point of use) and says why `ladybug` is the
  one exception: matching is core to tailoring, and a tailoring run that quietly matched worse
  because an extra was missing would be worse than a larger install.
- `jsk doctor` gains a check that `ladybug` imports and opens an in-memory database, reported as the
  capability it costs ("vocabulary matching") like every other check.
- CI runs the suite on 3.10 and 3.13.

The version floor and the dependency land in one commit, before any graph code.

## 2. The data

### The shipped graph

`src/jsk/data/vocabulary-graph.json`, curated with jsk and released with it. JSON, because the
standard library reads it and `pyyaml` stays optional.

```json
{
  "version": 1,
  "terms": {
    "kubernetes":   {"same": ["k8s"]},
    "aks":          {"same": ["azure-kubernetes-service"], "is-a": ["kubernetes", "azure"]},
    "azure":        {"same": ["microsoft-azure", "ms-azure"]},
    "dotnet":       {"same": [".net", "dot-net"]},
    "asp-net-core": {"same": ["asp.net-core"], "is-a": ["dotnet"]}
  }
}
```

Each key is a canonical term. `same` lists other names for it; `is-a` lists broader canonical terms.
A term with no edges may still be listed, so that it is known.

### The knowledge base's edges

In `## Vocabulary`, on the term's own list line, after the backticked term:

```markdown
### Technologies

- `aks` — is-a: kubernetes; same: azure-kubernetes-service
- `k8s` — not: kubernetes
```

- `same:` and `is-a:` add edges to the shipped graph.
- `not:` removes a shipped edge touching this term. It exists so a person is never stuck with an
  edge that is wrong for their field; it is expected to be rare.
- A line with no edges stays what it is today: a declared term.
- Only backticked list items count, as today. Prose and fenced examples are ignored.

### Normalisation

Every name is compared after lower-casing, trimming, and collapsing runs of whitespace to a single
`-`. Punctuation is kept: `.NET` normalises to `.net`, which matches `dotnet` only because a `same`
edge says so. No stemming, no fuzzy matching.

### Merge order

Shipped graph, then the knowledge base's additions, then its removals. An edge declared twice, in
either source, is one edge. The result is validated before any query runs (section 5).

## 3. The engine

A new module, `src/jsk/vocabgraph.py`, is the only code that imports `ladybug`.

```python
graph = vocabgraph.load(kb_sections)       # shipped file + KB edges, validated
graph.canonical("K8s")                      # -> "kubernetes", or None if unknown
graph.satisfies(have="aks", want="k8s")     # -> ["aks", "kubernetes"], or None
graph.names("kubernetes")                   # -> ["kubernetes", "k8s"]
graph.broader_than("kubernetes", "aks")     # -> True: the near-miss test
```

- **In-memory database, built every run.** No cache file means nothing to go stale and no on-disk
  format to migrate when `ladybug` moves. A few hundred terms must load well under the interpreter
  floor; the plan measures this and the spec is revisited if it does not.
- **Schema:** node table `Term(name STRING PRIMARY KEY)`; relationship tables `SAME(Term → Term)`
  and `IS_A(Term → Term)`. `same` groups are collapsed to their canonical term at load, so `SAME`
  holds alias → canonical only and `IS_A` connects canonical terms.
- **`satisfies`** resolves both names to canonical terms, then asks one Cypher query whether `want`
  is reachable from `have` along `IS_A*0..` (zero hops being the same term), returning the
  shortest path.
- Nothing outside `vocabgraph.py` knows a database exists. Replacing the engine touches one module
  and no data.

## 4. Matching

| Requirement | Project holds | Result |
|---|---|---|
| `kubernetes` | `kubernetes` | full weight |
| `k8s` | `kubernetes` | full weight — same group |
| `kubernetes` | `aks` | full weight, shown `kubernetes (via aks)` — narrower satisfies broader |
| `aks` | `kubernetes` | **zero**, listed as a near miss — broader does not satisfy narrower |
| `k3s` (undeclared) | `kubernetes` | zero, flagged as an unknown term |

`is-a` is one-way on purpose. AKS work is Kubernetes work; Kubernetes work is not necessarily AKS
work, and scoring it as such is the overclaim this pipeline exists to prevent.

Weights are unchanged: required ×3, preferred ×1, implicit 0.

## 5. Validation

`vocabgraph.load` refuses, naming the term and the file it came from, when:

- a name belongs to two `same` groups;
- `IS_A` has a cycle;
- an `is-a` edge points at a term that is neither a key in the shipped graph nor a term in the
  knowledge base's vocabulary (a `same` name is new by definition and needs no prior declaration);
- a `not:` names an edge that does not exist.

The refusals are verdicts a person can act on, in the style of the existing gates, not tracebacks.
The shipped file is validated on its own in CI and in `jsk doctor`.

## 6. Where it is used

**Ranking.** `kbindex.rank()` asks `graph.satisfies()` for each requirement against each project's
`capabilities ∪ technologies`. `matched` shows paths (`kubernetes (via aks)`); a new `near` list
holds near misses; `missed` is unchanged in meaning.

**The analyst stops translating.** `plugins/jsk/agents/jsk-tailor-analyst.md` changes its rule from
"value is vocabulary; a synonym scores as absent" to "write the posting's own term in `value`; the
graph resolves it". `jsk index` lists requirement values the graph does not know as **candidate
terms**, with the nearest known term when one shares a word, so the person can add an edge or a new
term. It is a prompt, not a failure.

**Skills and the ATS render.** The renderer stays pure: it reads the URS record and nothing else.
Aliases are resolved when the record is written. A URS skill gains an optional `term` field; the
resume author sets it, and `jsk vocab names <term>` supplies the graph's names to merge into
`aliases`. Hand-written aliases stay; they are display choices. `validate_urs` warns when a skill's
`term` is unknown to the graph.

**`jsk vocab`**, a new command for maintaining the graph:

- `jsk vocab check` — validate the shipped graph merged with the knowledge base's edges;
- `jsk vocab explain <have> <want>` — print the path, or why there is none;
- `jsk vocab names <term>` — every name for a term.

**The KB auditor** (`jsk-kb-auditor.md`) suggests edges for near-miss and candidate terms it finds.
It still never edits the knowledge base.

**Documentation.** `kb-spec.md` (Vocabulary section), `urs-spec.md` (skill `term`), the template
comment in `src/jsk/kb.py`, and `docs/SCRIPTS.md` for `jsk vocab`.

## 7. Testing

- `vocabgraph` unit tests: merge order; `not:` removal; each refusal in section 5; normalisation;
  the one-way `is-a` rule; the reported path; multi-parent `is-a`.
- `tests/test_kbindex.py`: `test_a_synonym_scores_as_absent` splits into a declared synonym that
  scores and an undeclared one that scores zero; new cases for `via` paths and near misses.
- A test that loads and validates the shipped `vocabulary-graph.json`, so a bad edge fails CI.
- A load-time test with a budget, so a slow build is noticed.
- `jsk doctor` test for the `ladybug` check.

## 8. First step of the plan: verify LadybugDB

Before any code depends on it, a spike confirms against `ladybug` 0.20.x on Windows and Linux:

1. an in-memory database opens and closes cleanly in one process, repeatedly;
2. variable-length relationship queries (`-[:IS_A*0..]->`) and shortest-path return what section 3
   needs;
3. load time for a 500-term graph;
4. installed size of the wheel.

If any of these fails, the plan stops and this section of the spec is revisited; the rest of the
design does not depend on the engine.

## Not in scope

- Weighted edges and `related` edges.
- Seeding the shipped graph from ESCO, Stack Exchange tag synonyms or any other external source.
  That is its own spec, with a licence review.
- Persisting the database to disk.
- Using the graph for anything but vocabulary: not for roles, organisations or metrics.
