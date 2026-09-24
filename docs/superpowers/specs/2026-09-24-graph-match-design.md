# Vocabulary and matching (P2): `jsk match`, the shipped vocabulary, and the queries

**Status:** approved design, 2026-09-24. Phase P2 of `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md`.
**Builds on:** P1, the graph core (`docs/superpowers/specs/2026-09-24-graph-core-design.md`, built on
`feat/vocabulary-graph`). **Carries over:** the matching rules of
`docs/superpowers/specs/2026-09-24-vocabulary-graph-design.md` (sections 3-4), now over Turtle rather
than Markdown and JSON, and the queries proven by the graph simulation
(`docs/superpowers/experiments/2026-09-24-graph-simulation/`).

## What P2 delivers

`jsk match <posting.ttl>`: a posting's requirements joined with the career through the vocabulary,
deterministically. It sorts each requirement into a bucket, ranks the projects, finds the smallest
set of projects that covers the posting, and derives the questions a tailoring round should ask.

**Graph workspaces only.** It reads `career/kb.ttl` and `applications/<dir>/posting.ttl`; nobody has
those files until P4 migrates a knowledge base and P6 has the analyst write postings. That is the
roadmap's order, chosen deliberately: `jsk index --rank` keeps working for Markdown knowledge bases
until P7, and the analyst keeps using it until P6. P2 changes the plugin only where the surface
test forces it.

**Success:** graphsim's scenarios S0-S7 and S11 pass through `jsk match`'s queries with the
simulation's hand-worked answers; precision and recall against the truth set are 1.000 / 0.958;
every matching rule is proven by a mutation that breaks it; the shipped vocabulary loads clean;
every token budget passes with no ceiling moved.

## The matching rules (unchanged from the vocabulary spec)

| Requirement asks | Project holds | Result |
|---|---|---|
| `Kubernetes` | `c:kubernetes` | **matched** |
| `K8s` | `c:kubernetes` | **matched** - a label of the concept |
| `Azure AD` | `c:entra-id` | **matched** - a former label |
| `Kubernetes` | `c:aks` | **matched**, shown `via c:aks` - narrower counts as broader |
| `AKS` | `c:kubernetes` | **near** - broader does not count as narrower |
| `Go` | `c:golang` | **ambiguous** until resolved - asked, never guessed |
| `Computing` | `c:azure` -> `c:cloud-platform` -> `c:computing` | **missing** past the hop limit |
| `K3s` (no concept) | - | **candidate** term |

- **One way.** A counts-as path (`isA`, `partOf`, `implies`) runs from what a project holds up to
  what the posting asks for, never down.
- **Hop limit 2**: P1's closure materialises paths of 0, 1 and 2 hops and no longer, so a match can
  only join on those.
- **`implies` never carries a required requirement.** A path with an `implies` edge matches a
  `preferred` one; for a `required` one it is **near** - "implied by c:terraform; confirm".
- **Distinct is a wall** (P1's `wall-crossed` rule refuses the graph that breaks it).
- **Implicit requirements** are listed and score nothing.
- **Weights unchanged** - they are `kbindex.WEIGHTS`, imported, not copied.

## Resolving a requirement to a concept

First match wins:

1. **`j:concept`** on the requirement - the analyst's answer to an ambiguity.
2. **An id.** `norm(asked)` equals a concept's slug (`SQL Server` -> `c:sql-server`, `golang` ->
   `c:golang`) - and no *other* concept has that word as a label. If one does, it is ambiguous with
   the id's concept among the candidates: a person's own slug meets free advert text, and were their
   board game `c:go`, "Go" would otherwise silently mean it. (Changed after the final review.)
3. **Labels.** `norm(asked)` against every concept's `j:label` and `j:former`, shipped and the
   person's own merged: one concept is resolved; more than one is **ambiguous** (all named); none is
   a **candidate** term.

`norm` is P1's `ontology.norm` (lowercase, whitespace runs to `-`). A project's `uses` tags are
already concepts - P1's `dangling` rule fails a tag that points at nothing.

## Narrowing the shipped vocabulary

A person can add to a shipped concept in `kb.ttl` (labels, edges - P1 allows it). To remove what is
wrong for their field, two new optional Concept predicates, `kb.ttl` only:

```turtle
c:golang j:unlabel "Go" .       # drop a shipped label or former label
c:aks j:unlink c:azure .        # drop a shipped isA or partOf edge to c:azure
```

`store.load` removes the named triples from the in-memory vocabulary graph **before** tier 2 and the
closure; no file is touched. The ontology gains the two predicates (additive; the format stays 3).

## New rules

| Rule | Tier | Checks | Severity |
|---|---|---|---|
| `shipped-vocabulary` | 1 (vocabulary.ttl) | only `a j:Technology`; no `implies`, `unlabel` or `unlink` | FAIL |
| `narrows-nothing` | 2 | an `unlabel` / `unlink` names a label or edge the shipped vocabulary does not have | FAIL |
| `concept-reclassed` | 2 | kb.ttl gives a shipped concept a class other than the shipped one | FAIL |
| `quote-verbatim` | 2 | a requirement's `j:quote` is not in the `posting.md` beside its `posting.ttl` (whitespace-normalised, case-sensitive), or that file is missing | FAIL |
| `necessity-wording` | 2 | the quote says "a plus", "nice to have", "bonus" or "desirable" and necessity is `required`; or says "must", "required" or "essential" and necessity is `preferred` / `implicit` | WARN |

Each joins the P1 mutation sweeps (one mutation, fires exactly once, at its line). P1's deferred
minor - `concept-class` firing twice when two classes share a predicate name (`Project.domain`,
`Posting.domain`) - is fixed here, since postings' domains start to matter.

## The queries (`src/jsk/graph/queries.py`)

Ported from the graph simulation; SPARQL over the store's union graph, Python for the assembly.
All take a loaded `Store` and a posting iri.

| Function | Returns |
|---|---|
| `requirements(store, post)` | `[Requirement(iri, asked, quote, necessity, concept)]` in id order |
| `resolve(store, req)` | `Resolution(state, concepts, via)` - state is `resolved`, `ambiguous` or `candidate`; `via` is `concept`, `id` or `label` |
| `match(store, post)` | `{req iri: Match(req, resolution, state, carriers, near)}` - state is `matched`, `near`, `missing`, `ambiguous`, `candidate` or `implicit`; `carriers` maps a project to its best path `(held, hops, implied)`; `near` maps a project to why |
| `evidence(store, project, concept)` | `confirmed`, `unconfirmed` or `tag` |
| `rank(store, post, matches, today)` | `[Row(project, score, required, preferred)]`, score by `kbindex` weights, `recency_points` and `SENIORITY` |
| `cover(matches, budget, ranking)` | `(projects, uncovered)` - the smallest set within `budget` carrying every carriable required requirement; among sets that small, the highest-scoring (the cover goes on the resume), then by id. `uncovered` is missing or near only; `unresolved(matches)` lists the ambiguous and candidate ones apart |
| `questions(store, matches)` | `[Question(kind, requirement, detail)]`, kind one of `ambiguous`, `unknown-term`, `implied`, `broader-held`, `tag-only` |

Retired projects and retired bullets never carry, rank or evidence anything.

**Evidence:** `confirmed` when a live bullet of the project with `j:provenance j:confirmed`
`j:shows` the concept or a narrower one (a non-implied path); `unconfirmed` when only an inferred or
needs-verification bullet does - a disputed bullet is evidence of nothing; `tag` when only the project's `uses` reaches it.

**Near** is either `implied by <held>; confirm` (an implies path, required requirement) or `holds
broader <held>` (the project holds a concept the requirement's concept counts as - the reverse
direction, which never matches).

## The command (`src/jsk/graph/match.py`)

```
jsk match <applications/<dir>/posting.ttl> [--cover N] [--json] [--today YYYY-MM-DD]
```

- The workspace root is the directory holding `applications/`; a path not in that layout exits 2.
- The whole workspace is loaded and validated. **A FAIL in the career, the vocabulary or this
  posting's own directory - or a syntax error anywhere - prints the findings and exits 1**: matching a
  broken record would be a guess. A FAIL in another application is a count line only, so an old
  advert that no longer quotes cleanly cannot block every new one. WARNs are a line naming their
  rules. (Narrowed after the final review.)
- Otherwise it exits 0, missing requirements included: an assessment, not a gate. Usage errors exit
  2; `--help` prints usage and exits 0, like every other subcommand.
- `--cover N` is the cover budget, default 3. `--json` prints the same data structured - what P6's
  analyst will read.
- `--today` is the date recency is measured from, default the local date - as `jsk index` has it,
  so a past run can be replayed and tests fix it.

The Markdown it prints:

```
# Match - Platform Engineer at Acme Health (k:post_acme_platform_engineer)

4 required, 3 preferred, 1 implicit. 5 matched, 1 near, 1 missing, 1 ambiguous.

## Requirements

| Requirement | Need | State | Carried by | Evidence |
|---|---|---|---|---|
| K8s | required | matched | prj_events (via c:aks, 1 hop) | confirmed |
| Go | preferred | ambiguous | c:golang or c:go-game? | |
…

## Ranking

Required ×3 · preferred ×1 · strength ×2 · recency +1 within 3 years, +0.5 at 4-6 · seniority +1 at
or above the posting's.

| Project | Score | Required | Preferred |
…

## Cover

prj_events, prj_identity carry every required requirement that can be carried.
Nothing carries: .NET Framework.

## Questions

- **ambiguous** Go: c:golang or c:go-game?
…
```

Wiring: `SIMPLE["match"] = ("match.py", …)` and `SUBPACKAGE["match.py"] = "graph"` in `cli.py`, so
it runs in process like `jsk index`.

## The shipped vocabulary (`src/jsk/data/vocabulary.ttl`)

The 62-concept draft (Kubernetes and its managed services, the three clouds, .NET, the JavaScript
frameworks, data and infrastructure tools), merged with the simulation's technologies, written by
the canonical writer. Technology only, no `implies` (the `shipped-vocabulary` rule). A test asserts
it loads with no findings, has no label clash outside a short, commented allowlist of words that
really are ambiguous, and that every `distinct` pair survives the closure.

## Tests

| File | Covers |
|---|---|
| `tests/match_fixtures/` | graphsim as Turtle: kb.ttl (5 projects, bullets, capabilities, the `implies` edges, the `go-game` domain), 4 application directories (posting.ttl + posting.md), and graphsim's vocabulary as a test-only `vocabulary.ttl` - so the hand-worked answers do not drift when the shipped file grows |
| `tests/test_graph_match.py` | S0-S7 and S11 with graphsim's expected values; S6 precision and recall against the truth set; ranking against a hand-computed table; resolution precedence (`j:concept` > id > label); retired projects and bullets excluded; narrowing (`unlabel`, `unlink`) changes the match |
| `tests/test_graph_match_mutations.py` | graphsim's `mutate.py`: each matching rule broken in a temporary copy of the package - in `queries.py`: counts-as two-way, `implies` carrying required, tags counted as evidence, ambiguity guessed; in `store.py`: a third hop; in `rules.py` plus one crossing edge in the fixture: the wall ignored - and the scenarios must fail |
| `tests/test_graph_shapes.py`, `tests/test_graph_rules.py` | the five new rules in the sweeps; `concept-class` fires once |
| `tests/test_graph_vocabulary.py` | the shipped file: clean load, the clash allowlist, walls |
| `tests/test_cli.py` | `jsk match`: exit 0 with the four sections; 1 on a broken record; 2 outside the layout; `--json` parses; `--help` |

## The plugin surface and the budget

`tests/test_plugin_surface.py` requires every subcommand in SKILL.md, the `cli.py` docstring and
`docs/SCRIPTS.md`, so `match` gets a row in each. SKILL.md + mode-tailor + mode-ship is 5,985 tokens
against a 6,000 ceiling, and the row costs about 22. **The ceiling does not move:** existing SKILL.md
wording is tightened, with no content lost, to make room - the ceilings are the guard against the
okf-era failure where SKILL.md named 30 verbs. If that cannot honestly be done, the fallback is
6,000 -> 6,050 with the measured before and after in the test's comment, and it is reported.

## Exit criteria

1. S0-S7, S11 and the precision/recall test pass through `queries.py`.
2. Every mutation in `test_graph_match_mutations.py` makes the scenarios fail (seven: two-way, third
   hop, no second hop, implies carrying required, wall ignored, tags as evidence, ambiguity guessed),
   and an unmutated control copy passes. Drafting found the simulation had no scenario joining at two
   hops, so deleting the second hop went unnoticed; `test_two_hops_still_count` pins it.
3. The shipped vocabulary loads with no findings.
4. `jsk match` on the fixture postings prints the four sections; the full suite and ruff pass; no
   token ceiling moved (or the move is measured and reported).
