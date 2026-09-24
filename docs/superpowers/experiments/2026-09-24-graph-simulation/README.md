# Graph simulation: what a workspace graph solves that the model cannot

**Status:** experiment, 2026-09-24. Throwaway prototype; nothing here is product code.
**Run:** `pip install pyoxigraph`, then `python graphsim.py` (12 scenarios) and `python mutate.py`
(7 mutations). Both exit 0.

## 1. The problem, from the model's side

A job-seeker skill is worth building only where it does something the model cannot do reliably on
its own. The model is good at reading a posting, drafting prose, and interviewing. It is
unreliable at six things this domain depends on:

| # | What the model cannot hold | Why | What it costs the person |
|---|---|---|---|
| M1 | **The same answer twice** | it re-derives matching from scratch each session | two applications disagree about the same career |
| M2 | **One-way reasoning under pressure to match** | it is biased toward finding a fit; "has Kubernetes" drifts into "has EKS" | a resume that collapses in the first technical interview |
| M3 | **Exact joins over many records** | 100 postings × 25 projects × versioned metrics exceeds what it can count in its head | "7 of 10 postings want Terraform" is a guess, not a count |
| M4 | **Time** | a metric revised in March is still quoted from February's draft; years of experience are asserted, not computed | stale or inflated numbers sent to employers |
| M5 | **What it has not read** | the whole career does not fit in a context window, and it does not know which part to open | tokens spent reading everything, or claims made from a partial read |
| M6 | **Where its own questions came from** | gap questions are improvised, so they are generic ("tell me about your cloud work") | slow interviews that do not unblock a specific claim |

`jsk` already answers some of this with files and gates (`kbindex.py` computes the ranking
because "a model doing 900 lookups in its head was the slowest step"). A graph answers the rest
because each of M1-M6 is a **join or a traversal** that is deterministic once the data is linked.

## 2. The graphs

One RDF graph, six regions, each answering one of M1-M6. Built from the files on every run.

```
                      VOCABULARY (G1)                                  POSTING (G3)
   Label ─label─► Concept ─isA/partOf/implies─► Concept      Posting ─requires─► Requirement
                     │  ─distinct─ Concept                                  │ asked: "k8s"
                     │                                                      │ necessity
            ┌────────┴────────── uses ◄──── Project ──bullet──► Bullet ─shows─► Concept
            │                                 │ start,end         │ status   │
   EVIDENCE (G2)                              │ strength          └─cites──► Metric ─version─► MetricVersion
                                              │                                         value, validFrom, validUntil
   HISTORY (G4)   Application ─posting─► Posting                                            ▲
                     └─carried─► Use ─bullet─► Bullet ; Use ─metricVersion─► ──────────────┘
                  LogEntry ─changed─► Metric   (date, note)

   DERIVED (G5)   Path {from, to, hops ≤ 2, implied}   - the counts-as closure, materialised once by SPARQL UPDATE
   DRAFT   (G6)   DraftBullet ─from─► Bullet ; shows Concepts ; numbers  ·  Skill ─concept─► Concept ; aliases
```

| Graph | Answers | Rule it enforces |
|---|---|---|
| **G1 Vocabulary** | "K8s" is `kubernetes`; "Go" is two things; "K3s" is nothing yet | nothing matches unless declared; ambiguity is asked, never guessed |
| **G2 Evidence** | which projects hold a concept, and which *confirmed* bullet shows it | a tag is not evidence |
| **G3 Posting** | what the posting asks, how strongly, in whose words | the posting's label is kept, the graph resolves it |
| **G4 History** | what each application carried, which metric version, what changed and why | a sent application is frozen; a revision is traced to what it affects |
| **G5 Paths** | does `have` count as `want`, by which edges, in how many hops | one-way; ≤ 2 hops; `implies` never carries a required requirement; `distinct` is a wall |
| **G6 Draft** | does every claim in a draft resume trace to held evidence and the current metric | selection, never invention |

**Matching is a join:** `Posting → Requirement → (label) → Concept ← Path ← Concept ← Project`,
then G2 grades the evidence. The result has five buckets, not two: **matched**, **near miss**
(broader held, or implied-only for a required line), **missing**, **ambiguous**, **candidate term**.

## 3. The scenarios

Synthetic data: 27 concepts, 5 projects, 8 bullets, 4 metrics (one revised), 4 postings (24
requirements), 3 sent applications, 1 log entry, 1 draft resume. **Every expected answer was worked
out by hand from the data before its query was written.**

| # | Scenario | Model gap | Result |
|---|---|---|---|
| S0 | graph validates: no cycle, no path across a `distinct` wall | M1 | PASS |
| S1 | K8s / .NET / Azure AD (former label) resolve; Go ambiguous; K3s unknown | M1 | PASS |
| S2 | AKS counts as Kubernetes; Kubernetes is only a near miss for EKS | M2 | PASS |
| S3 | aks → azure → cloud-platform → computing (3 hops) does not match | M2 | PASS |
| S4 | dotnet ≠ .NET Framework; angularjs ≠ Angular | M2 | PASS |
| S5 | required IaC implied by Terraform/Bicep → near miss; preferred EDA via Kafka → match | M2 | PASS |
| S6 | precision / recall of matching against hand-worked truth | M1, M2 | PASS — P 1.000, R 0.958 |
| S7 | top-2 by score leave Python uncovered; the smallest cover is events + data | M3 | PASS |
| S8 | honesty gate on the draft: unheld EKS, superseded "1 s", inferred source, untraced "8", unheld aliases, "8 years" vs 5y1m | M2, M4 | PASS — 7 flags, 0 false |
| S9 | app1 and app3 sent the pre-revision latency; the log says why | M4 | PASS |
| S10 | demand across postings: Terraform ×4 evidenced; .NET, SQL Server tag-only; Python inferred | M3 | PASS |
| S11 | the tailoring questions, each derived from a named gap | M6 | PASS — 5 questions |
| S12 | what an agent reads as the career grows (5 → 205 projects) | M5 | PASS — see below |

**Matching quality against the same truth:**

| Method | Precision | Recall | Failures |
|---|---|---|---|
| **Graph** | **1.000** | **0.958** | misses "Azure Kubernetes" — a real synonym nobody declared |
| Exact string match | 1.000 | 0.625 | misses K8s, .NET, Azure AD, EDA, Kubernetes-via-AKS |
| Fuzzy "similar words" | 0.792 | 0.792 | matches Go→board game, .NET Framework→.NET, Angular→AngularJS, JavaScript→Java |

The graph fails **safe**: its one miss is a recall gap `jsk vocab candidates` would surface, not a
false claim. The fuzzy baseline — roughly what "the model decides it's similar" does — produces a
false match in one of every five.

**What an agent reads (S12):**

| Projects in the career | Whole KB (tokens, approx.) | Match result (tokens) | Query time |
|---|---|---|---|
| 5 | ~900 | ~379 | 1 ms |
| 55 | ~16,100 | ~379 | 1 ms |
| 205 | ~61,700 | ~379 | 2 ms |

The read scales with the posting, not with the career.

**The suite can fail (`mutate.py`):** seven one-line breaks to the rules — two-way counts-as, a
third hop, implies carrying required, an edge across a `distinct` wall, a wall deleted, metric
versions ignored, tags counted as evidence — each turns its guarding scenario from PASS to FAIL.
7 of 7 caught.

**One defect found and fixed during the run:** the first honesty gate read "p95" as a claimed
number. The repo already had the answer — `validate_urs.numerals()` treats p95, K8s and EC2 as
designators — and the prototype now reuses it, as a real gate would.

## 4. What this does not show

- **The data is synthetic and small.** The truth table encodes the same domain facts the edges do,
  so P = 1.000 measures that the *rules* are enforced, not that a real vocabulary is complete.
  Real-world recall depends on vocabulary coverage — measure it on real postings.
- **Extraction is not simulated.** Postings arrive as prose; the analyst turning them into
  requirements is the step the graph depends on and cannot improve. The quote and necessity checks
  proposed earlier are the guard there.
- **The token figures are estimates** (bytes / 4, filler prose at the fixture's average).
- **Time is modelled for metrics only.** Roles, titles and project facts can change too.

## 5. The engine

Oxigraph handled everything here in milliseconds: SPARQL UPDATE materialises the counts-as closure
as `Path` nodes (G5), property paths (`(j:isA|j:partOf|j:implies)+`) validate cycles and walls, and
the join queries are single SELECTs. The one awkwardness is edge properties — a requirement's
necessity and a path's hop count needed their own nodes — which is ordinary RDF modelling.

## 6. What to build, in order

1. **G1 + G5** — the vocabulary graph already planned (`docs/superpowers/plans/2026-09-24-vocabulary-graph.md`).
2. **G6 honesty gate** — S8: the one feature that makes a sent resume safer. Needs G2's `shows`
   (which concepts a bullet's text shows) and metric versions.
3. **G2 + G4** — the evidence and history graph over the whole workspace (S7, S9, S10, S11). A
   separate spec: it needs a parser for every file shape, and versioned metrics in the KB format.
4. **Question generation and set cover** — S11 and S7 on top of 3.

The files stay the record throughout; the graph is rebuilt from them.
