# A vocabulary graph, so a posting's words match the knowledge base's

**Status:** **superseded** by `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md` (the record becomes
Turtle queried through Oxigraph; LadybugDB is dropped). The model and matching rules below carry over into the
roadmap's P2. Originally: design, approved 2026-09-24, revised the same day after the LadybugDB spike.
**Scope:** `jsk` vocabulary matching and packaging. No change to what a resume claims.

Every posting names the same thing differently: `K8s`, `Kubernetes`, `AKS`; `.NET`, `Dot Net`,
`ASP.NET Core`; `Azure AD`, `Entra ID`. Ranking compares requirement values against project tags as
exact strings ([kbindex.py:284-287](../../../src/jsk/kbindex.py)), so today the analyst translates
every term into the knowledge base's slug by hand, on every application, and a missed translation
silently scores as absent.

This document replaces that hand translation with a maintained graph of **concepts** and the
**labels** postings use for them, stored as data and queried through LadybugDB.

## What stays true

- **Nothing matches unless someone declared it.** The graph widens matching only along edges a
  person wrote down. An undeclared synonym still scores zero.
- **Never a number you cannot show the terms behind.** Every match through the graph reports the
  path it took.
- **Nothing is guessed.** A label that could mean two concepts is asked about, never resolved
  silently.
- **The data is the source of truth, not the database.** The database is rebuilt from text on every
  run and is never read back as the record.

## 1. Packaging

LadybugDB (`ladybug` on PyPI, MIT, formerly Kùzu) becomes the first hard dependency.

- `dependencies = ["ladybug>=0.18.3,<0.19"]`. Pinned to one minor, because releases in the Kùzu
  lineage have changed both API and storage format between minors. Raising it is a deliberate
  commit with the graph tests run against the new version **on Windows and Linux**.
  - Why 0.18 and not the newest: the spike (section 8) found every Windows wheel from 0.19.0 to
    0.20.4 broken — they omit the C-API shared library their default backend loads, and the pybind
    fallback links OpenSSL 3 DLLs the wheel does not ship, so `Database(":memory:")` raises on a
    clean install. 0.18.3 bundles its DLLs and works on Windows and Linux. The pin moves when a
    newer release passes the spike on Windows.
- `requires-python = ">=3.10"` (was `>=3.8`). 3.8 and 3.9 are past end of life and were never
  tested: CI ran 3.13 only.
- `MIN_PYTHON = (3, 10)` in `src/jsk/preflight.py`.
- The "deliberately empty" comment above `dependencies` is rewritten, not deleted. It keeps the rule
  (every other package is optional and imported at the point of use) and says why `ladybug` is the
  one exception: matching is core to tailoring, and a tailoring run that quietly matched worse
  because an extra was missing would be worse than a larger install.
- `jsk doctor` gains a check that `ladybug` imports and opens an in-memory database, reported as the
  capability it costs ("vocabulary matching") like every other check.
- CI runs the suite on 3.10 and 3.13.

The version floor and the dependency land in one commit, before any graph code.

## 2. The model

### Concepts and labels

A **concept** is one thing, with a stable id: `kubernetes`, `golang`, `entra-id`. Project tags in the
knowledge base (`capabilities`, `technologies`) are concept ids, as the backticked vocabulary terms
are today.

A **label** is a name a posting might use for a concept: `Kubernetes`, `K8s`, `Go`, `Golang`. A
concept's id is always one of its own labels.

**A label may name more than one concept.** `Go` names `golang` and `go-game`; `Swift` names
`swift-lang` and `swift-payments`; `R`, `C`, `Spark`, `Ray` and `Flow` are the same kind of case.
Such a label is **ambiguous** and is never resolved automatically (section 4).

### Normalisation

Labels are compared after lower-casing, trimming, and collapsing runs of whitespace to a single `-`.
Punctuation is kept: `.NET` normalises to `.net`, which reaches `dotnet` only because `.net` is
declared one of its labels. No stemming, no fuzzy matching.

### Edges between concepts

| Edge | Reads as | Scoring treats it as |
|---|---|---|
| `is-a` | AKS **is a kind of** Kubernetes | counts-as |
| `part-of` | LINQ **is part of** .NET | counts-as |
| `implies` | Terraform **implies** infrastructure-as-code | counts-as, restricted (section 4) |
| `distinct` | AngularJS **is not** Angular | a wall: nothing may connect them |

`is-a`, `part-of` and `implies` are directed and point from narrower to broader. They are kept
separate for the people maintaining the graph and for explanations ("via terraform, which implies
infrastructure-as-code"); scoring reads all three as one **counts-as** relation, with the one
restriction below.

`distinct` is symmetric. It exists for false friends — `angular`/`angularjs`, `java`/`javascript`,
`dotnet`/`dotnet-framework`, `python-2`/`python-3` — so that no edge, merge or suggestion ever joins
them.

### Renames

A label can be **former**, with the year the concept stopped using it: `entra-id` has the former
label `Azure AD` until 2023. For matching, a former label is a label like any other. For the ATS
render, it is kept as a former name (section 6).

## 3. The data

### The shipped graph: technologies only

`src/jsk/data/vocabulary-graph.json`, curated with jsk and released with it. JSON, because the
standard library reads it and `pyyaml` stays optional.

```json
{
  "version": 1,
  "concepts": {
    "kubernetes":   {"labels": ["Kubernetes", "K8s"]},
    "aks":          {"labels": ["AKS", "Azure Kubernetes Service"],
                     "is-a": ["kubernetes"], "part-of": ["azure"]},
    "azure":        {"labels": ["Azure", "Microsoft Azure", "MS Azure"]},
    "dotnet":       {"labels": [".NET", "Dot Net", ".NET Core"],
                     "distinct": ["dotnet-framework"]},
    "dotnet-framework": {"labels": [".NET Framework"]},
    "linq":         {"labels": ["LINQ"], "part-of": ["dotnet"]},
    "entra-id":     {"labels": ["Entra ID", "Microsoft Entra ID"],
                     "former": [{"label": "Azure AD", "until": 2023}], "part-of": ["azure"]},
    "golang":       {"labels": ["Go", "Golang"]}
  }
}
```

**The shipped graph holds technology concepts and the edges among them, and nothing else.**
Technology aliases are close to fact: `K8s` is Kubernetes. Capability edges are judgement — whether
"stakeholder management" is part of "technical leadership" — and a judgement shipped to every user
is how a graph starts overclaiming. So:

- no capability concepts in the shipped graph;
- no `implies` edges in the shipped graph, since `implies` is how a technology reaches a capability.

Both live only in a person's knowledge base, where the person answers for them. The CI test on the
shipped file enforces this.

### The knowledge base's edges

In `## Vocabulary`, on the concept's own list line, after the backticked id:

```markdown
### Technologies

- `aks` — labels: Azure Kubernetes Service; is-a: kubernetes
- `terraform` — implies: infrastructure-as-code (from 2026-09-12-contoso-architect)

### Capabilities

- `technical-leadership` — labels: tech lead, technical lead
- `stakeholder-management` — part-of: technical-leadership
```

A concept's **kind** comes from the subsection it is declared under: `### Technologies` makes a
technology, `### Capabilities` a capability, `### Domains` a domain. Every shipped concept is a
technology. A person can also narrow a shipped entry, for instance ``- `golang` — not: labels Go``
under `### Technologies` if "Go" never means the language in their field.

- `labels:`, `is-a:`, `part-of:`, `implies:`, `distinct:` and `former:` (`former: Azure AD until
  2023`) add to the shipped graph.
- `not:` removes a shipped label or edge touching this concept (`not: labels Go`, `not: is-a
  kubernetes`). It exists so a person is never stuck with an entry that is wrong for their field.
- `(from <application>)` after an edge records the application directory that prompted it. It is
  provenance only and changes nothing about matching; `jsk vocab` reports it (section 6).
- A line with no edges stays what it is today: a declared concept.
- Only backticked list items count, as today. Prose and fenced examples are ignored.

### Project tags are concepts too

Every term a project carries in `capabilities` or `technologies` is a concept, whether or not the
vocabulary declares it, with its id as its only label. A knowledge base written before this graph
tags `terraform` and a posting that says `terraform` must still match exactly as it does today.
A requirement label is a **candidate term** only when it names nothing at all: no shipped concept,
no declared concept, no project tag.

### Merge order

Shipped graph, then the knowledge base's additions, then project tags not already known, then the
knowledge base's removals. An edge or label declared
twice, in either source, is one. The result is validated before any query runs (section 5).

## 4. Matching

A posting's requirement `value` is a **label**, written as the posting wrote it. Matching resolves it
to concepts, then asks whether any concept a project holds counts as it.

| Requirement | Project holds | Result |
|---|---|---|
| `Kubernetes` | `kubernetes` | full weight |
| `K8s` | `kubernetes` | full weight — a label of the concept |
| `Azure AD` | `entra-id` | full weight — a former label |
| `Kubernetes` | `aks` | full weight, shown `kubernetes (via aks)` — narrower counts as broader |
| `AKS` | `kubernetes` | **zero**, listed as a near miss — broader does not count as narrower |
| `Go` | `golang` | **zero until resolved** — ambiguous label, asked about |
| `Cloud` | `azure-functions` → `azure` → `cloud-platform` → … | only within the hop limit |
| `K3s` (undeclared) | `kubernetes` | zero, listed as a candidate term |

The rules:

- **One-way.** A counts-as path runs from what the project holds up to what the posting asks for,
  never down. AKS work is Kubernetes work; Kubernetes work is not necessarily AKS work, and scoring
  it as such is the overclaim this pipeline exists to prevent.
- **Hop limit.** A path may be at most **2** counts-as edges. Past that, a chain stops being evidence
  and starts being noise. The limit is a constant in `vocabgraph.py`, not a setting.
- **`implies` cannot carry a required requirement.** A path containing an `implies` edge scores at
  full weight for a `preferred` requirement. For a `required` one it scores zero and is listed as a
  near miss — "implied by terraform; confirm" — because a tool quietly standing in for a required
  capability is the kind of stretch a person should say yes to, not a script.
- **Ambiguity is asked, not guessed.** An ambiguous label scores zero and `jsk index` names the
  concepts it could mean. The analyst resolves it by writing the concept id in `value` (`golang`
  instead of `Go`); an id is always an unambiguous label.
- **Distinct is a wall.** No path may pass between two `distinct` concepts, in either direction.

Weights are unchanged: required ×3, preferred ×1, implicit 0.

## 5. Validation

`vocabgraph.load` refuses, naming the concept and the file it came from, when:

- a counts-as edge (`is-a`, `part-of`, `implies`) has a cycle;
- a counts-as path connects two `distinct` concepts, at any length;
- an edge points at a concept that is neither in the shipped graph nor declared in the knowledge
  base's vocabulary;
- a `not:` names a label or edge that does not exist;
- the shipped graph contains an `implies` edge;
- the knowledge base declares a shipped concept under a subsection other than `### Technologies`.

Ambiguous labels are **not** a refusal: they are real, and they are handled at matching time.

The refusals are verdicts a person can act on, in the style of the existing gates, not tracebacks.
The shipped file is validated on its own in CI and in `jsk doctor`.

## 6. The engine and where it is used

### `src/jsk/vocabgraph.py`

The only module that imports `ladybug`.

```python
graph = vocabgraph.load(kb_sections)          # shipped file + KB edges, validated
graph.resolve("Go")                           # -> ["go-game", "golang"]  (ambiguous)
graph.resolve("K8s")                          # -> ["kubernetes"]
graph.satisfies(have="aks", want="kubernetes")
#   -> Path(["aks", "kubernetes"], edges=["is-a"]), or None
graph.names("entra-id")                       # -> Names(current=[...], former=["Azure AD"])
graph.near_miss(have="kubernetes", want="aks")  # -> True: want is narrower than have
```

- **In-memory database, built every run.** No cache file means nothing to go stale and no on-disk
  format to migrate when `ladybug` moves. Measured in the spike: 135 ms to import, 175-220 ms to
  load 500 concepts and 2,000 labels. Only `jsk index`, `jsk vocab` and the resume author's alias
  step load the graph; the renderer and the gates never do.
- **The database answers once per load, not once per match.** A path query costs about 3.7 ms, so
  asking per project and requirement would add over a second to a ranking. Instead `load()` runs
  three queries and keeps their answers in dictionaries: the counts-as closure within the hop
  limit (33-48 ms for 500 concepts), unbounded reachability for the `distinct` wall, and cycle
  detection. `satisfies`, `near_miss` and `names` are then lookups.
- **Schema:** node tables `Concept(id STRING PRIMARY KEY, kind STRING)` and
  `Label(name STRING PRIMARY KEY)`; relationship tables `NAMES(Label → Concept, former_until INT64)`,
  `COUNTS_AS(Concept → Concept, kind STRING)` holding `is-a`/`part-of`/`implies`, and
  `DISTINCT(Concept → Concept)`, stored once per pair.
- **The queries**, as verified against 0.18.3 (Kùzu-lineage Cypher has no list comprehensions;
  `nodes(e)` returns only the interior nodes of a path):
  - closure: `MATCH (a:Concept)-[e:COUNTS_AS*1..2]->(b:Concept) RETURN a.id, b.id,
    properties(nodes(e), 'id'), properties(rels(e), 'kind')`;
  - reachability: `MATCH (a:Concept)-[:COUNTS_AS* SHORTEST 1..30]->(b:Concept) RETURN a.id, b.id`;
  - cycles: `MATCH (a:Concept)-[:COUNTS_AS]->(b:Concept), (b)-[e:COUNTS_AS* SHORTEST 1..30]->(a)`
    plus self-loops `MATCH (a:Concept)-[:COUNTS_AS]->(a)`.
- **`satisfies`** returns the shortest closure path from `have` to `want` (zero hops when they are
  the same concept); the caller applies the `implies` rule. It needs no `DISTINCT` check, because
  validation has already refused any graph in which a counts-as path crosses a wall.
- Nothing outside `vocabgraph.py` knows a database exists. Replacing the engine touches one module
  and no data.

### Ranking

`kbindex.rank()` resolves each requirement's label and asks `graph.satisfies()` against each
project's `capabilities ∪ technologies`. The row gains three lists beside `matched` and `missed`:

- `matched` shows paths: `kubernetes (via aks)`, `infrastructure-as-code (via terraform, implies)`;
- `near` holds near misses: broader-than-asked, and `implies` against a required requirement;
- `ambiguous` holds labels waiting on the analyst, with the concepts each could mean;
- `candidates` holds labels the graph does not know.

### The analyst

`plugins/jsk/agents/jsk-tailor-analyst.md` changes its rule from "value is vocabulary; a synonym
scores as absent" to "write the posting's own label in `value`; the graph resolves it. When `jsk
index` reports a label as ambiguous, replace it with the concept id the posting means." `label` stays
what it is: the posting's phrasing, kept for prose.

### Skills and the ATS render

The renderer stays pure: it reads the URS record and nothing else. Aliases are resolved when the
record is written.

- A URS skill gains an optional `concept` field; the resume author sets it.
- `jsk vocab names <concept>` supplies the names to merge into `aliases`, under one rule: **the
  render may add the concept's own labels and the labels of broader concepts it counts as, never
  narrower ones.** Adding "Kubernetes" because you hold AKS is true; adding "AKS" because you hold
  Kubernetes is an overclaim.
- Former labels render as former: the ATS variant carries "Entra ID (formerly Azure AD)", so a
  keyword match on either finds it and neither reads as current when it is not.
- Hand-written aliases stay; they are display choices.
- `jsk vocab check --record resume.json` warns when a skill's `concept` is unknown to the graph,
  and refuses an alias that is the label of a narrower concept only. It is a `jsk vocab` check
  rather than part of `validate_urs` because the gates never load the graph: `validate_urs` runs
  in `jsk doctor`'s end-to-end check and on every ship, and reads the record alone.

### `jsk vocab`

A new command for maintaining the graph:

- `jsk vocab check [--kb KB] [--record resume.json]` — validate the shipped graph merged with the
  knowledge base's edges, and optionally a record's skill aliases against it;
- `jsk vocab explain <have> <want>` — print the path, or which rule stopped it;
- `jsk vocab names <concept>` — the names the render may use, current and former;
- `jsk vocab candidates` — requirement labels across every `applications/*/posting.md` that the
  graph does not know or finds ambiguous, counted by how many postings used them, most frequent
  first. This is the demand signal: it says which edges are worth writing. It also lists the
  knowledge base's own technology edges that the shipped graph lacks, with their `(from …)`
  provenance, as proposals for upstream.

### The KB auditor

`jsk-kb-auditor.md` uses `jsk vocab candidates` to suggest edges, and never suggests one that
crosses a `distinct` wall. It still never edits the knowledge base.

### Documentation

`kb-spec.md` (Vocabulary section), `urs-spec.md` (skill `concept`), the template comment in
`src/jsk/kb.py`, and `docs/SCRIPTS.md` for `jsk vocab`.

## 7. Testing

- `vocabgraph` unit tests: merge order; `not:` removal; normalisation; each refusal in section 5;
  the one-way rule; the hop limit at 2 and 3; `implies` scoring for preferred and not for required;
  ambiguous labels; former labels; the `distinct` wall at one hop and at two; multi-parent paths;
  the reported path and edge kinds.
- `tests/test_kbindex.py`: `test_a_synonym_scores_as_absent` splits into a declared label that
  scores and an undeclared one that scores zero; new cases for `via`, `near`, `ambiguous` and
  `candidates`.
- A test that loads and validates the shipped `vocabulary-graph.json`, including that it holds no
  `implies` edges.
- The render rule: an alias from a broader concept is allowed, from a narrower one refused; a former
  label renders as former.
- `jsk vocab candidates` over a fixture `applications/` directory.
- A load-time test with a budget, so a slow build is noticed.
- `jsk doctor` test for the `ladybug` check.

## 8. The LadybugDB spike (done 2026-09-24)

Run on Windows 11 (Python 3.13) and Linux (Docker, `python:3.10-slim`):

| Check | Result |
|---|---|
| Windows, 0.19.0-0.20.4 | fails on a clean install (see section 1) |
| Windows, 0.18.3 | works; about 27 MB installed |
| Linux, 0.18.3 and 0.20.4 | works |
| in-memory database opened and closed repeatedly in one process | works |
| `COUNTS_AS*0..2`: zero hops, one-way, hop limit, edge kinds | works |
| cycles and unbounded reachability via `SHORTEST 1..30` | works |
| load, 500 concepts / 2,000 labels | 175-220 ms, plus 135 ms import |
| one path query | about 3.7 ms, hence the closure design in section 6 |
| closure query within 2 hops | 33-48 ms |

The spike is repeated, on Windows and Linux, before the pin in section 1 is ever raised.

## Not in scope

- Weighted edges and `related` edges.
- Seeding the shipped graph from ESCO, Stack Exchange tag synonyms or any other external source.
  That is its own spec, with a licence review.
- Persisting the database to disk.
- Anything beyond vocabulary. Projects, roles, organisations, metrics and bullets stay where they
  are; a graph of the whole knowledge base would be a separate spec.
