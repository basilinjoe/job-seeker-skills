# OKF as a property graph

Replacing the file-per-concept bundle with a graph as the authoritative store.

## The finding that de-risks this

The bundle is already a graph. It has typed nodes (concept types), typed directed edges
(`role:`, `organisation:`, `metric:`, `include[].ref`, `company_ref`), a derived node type
(engagement), and a vocabulary plane (`capabilities`, `domains`, `technologies`). What it lacks is
an engine. Every consequence of that absence is written down in this repo already:

- `query/walk.py` opens by naming **five separate walks** over the bundle, each unable to answer the
  others' question.
- `query/refs.py` exists solely to re-derive "what points at this", across **six different shapes**,
  and is careful not to answer it twice because two readers would disagree.
- `authoring/schema.py` documents **three rules it cannot enforce** — all three are edge-integrity
  rules — and notes that a dangling `role:` aborts a tailoring run rather than failing a gate.
- The same module records that closed vocabularies "compare as exact strings … a synonym does not
  fail, it silently stops matching."

So this is not a rewrite into a different paradigm. It is the same model with the joins made real.

**Only one of the three frozen surfaces breaks.** `okf`'s command surface (#1) is unchanged — the
verbs keep their names and write nodes instead of files. The compiled record's shape (#3) is
unchanged — URS becomes a *projection* of the graph, emitted by the same code path that consumes it
today. Only bundle-layout-on-disk (#2) breaks, and that is the one this change is *for*. It needs a
major version and a migration, per `ARCHITECTURE.md`.

## The decision, and its cost

The graph is the source of truth. Markdown becomes a generated export.

The cost is real and is accepted deliberately: the README's *"plain Markdown files you own — any
editor opens it, Git versions it"* becomes *"a store you own, exported to Markdown you can read"*.
Hand-editing an exported file no longer changes anything. Whatever physical form the store takes,
the design below is unchanged; the form is a separate decision recorded elsewhere.

## Principles carried over

These are not new. They are the invariants the current codebase already enforces, restated as graph
rules, and every decision below is downstream of them.

| # | Invariant | Graph rule |
|---|---|---|
| 1 | Nothing is stored twice | Every node and edge is **asserted** or **materialized**, never both. A materialized element is recomputed and `okf gates` diffs it against the store. |
| 2 | Nothing is invented | A `View` node carries **no text-typed property**. All content reaches a document through `SELECTS` edges. The rule stops being validated and starts being structural. |
| 3 | Nothing is assumed | `status` (`confirmed` / `inferred` / `needs-verification`) is a property of every asserted **node and edge**. Today only nodes carry it. |
| 4 | A synonym must not silently stop matching | Vocabulary is a plane of `Term` nodes. A synonym is an `ALIAS_OF` edge, so it **resolves** instead of failing quietly. |
| 5 | Frozen is immutable | Freezing clones nodes into an immutable island. It never takes a reference to something still editable. |
| 6 | Status words drift from the prose beneath them | Stage, staleness and outcome stay **queries**. There is no `outcome` property on `Application`. |

## The meta-model

```
Node  (id, label, origin, status, created, updated, frozen, props{}, embedding?)
Edge  (id, type, from, to, origin, status, order?, props{})
```

Two fields carry the design:

**`origin`** is `asserted` or `materialized`. Asserted elements are written by an `okf` verb and are
the truth. Materialized elements are computed by a rule in the ledger below, are never writable, and
are re-derived and diffed by the record gate. This is invariant 1 made mechanical.

**Edges are first-class.** They have identity, provenance and properties. That is the capability the
file store cannot have and the reason several rules below can exist at all: "this contribution
evidences this capability, and that claim is `inferred`" is not expressible as a string in a YAML
list.

### The id scheme is the compatibility anchor

Node ids are the existing compiled ids, unchanged. `query/ids.py` already owns their derivation and
`tests/test_query.py` already pins both directions of it.

| Prefix | Node | Minted today by |
|---|---|---|
| `prj_` `pos_` `org_` `edu_` `cred_` | Contribution (`mode: project`), Role, Organisation, Education, CertificationStatus | `okf_compile.ident()` |
| `prc_` | Contribution (`mode: practice`) | *new* |
| `eng_` `nar_` `view_` | Engagement, Narrative, View | `okf_compile.slug()` |
| `met_` | Metric | `okf_compile.metrics_table()` |
| `ach_` `skill_` `cred_<n>` | Bullet, Skill, Credential | `authoring.body.derived_*_id` |

Keeping them means a `.view.md` written last year still resolves, `okf view include ach_latency`
still works, and the id-phantom refusals `ids.py` was built to make stay valid. New node types get
new prefixes (`pst_`, `req_`, `app_`, `evt_`, `art_`, `src_`, `q_`, `dec_`); vocabulary uses a
namespaced form (`term:capability:event-driven-architecture`) because a Term is not a document and
should not look like one.

---

## Node catalogue

Five planes. The plane is a modelling aid, not a stored property.

### Plane A — Identity

| Node | id | Properties | Origin |
|---|---|---|---|
| `Person` | `person` | `name.full`, `headline`, `location.label` | asserted, singleton |
| `Contact` | `ct_<kind>` | `kind` (email / phone / linkedin / github), `value`, `renderable` | asserted |

`build_person()` today reads *only* the `# Contact` table, specifically so the home address in the
identity concept cannot leak onto a resume. The graph keeps that guarantee structurally: only
`Contact` nodes are reachable by `HAS_CONTACT`, and `renderable: false` is a property a resolver
must opt past rather than a fact buried in prose.

### Plane B — Career record

| Node | id | Properties | Origin |
|---|---|---|---|
| `Organisation` | `org_*` | `title`, `relationship`, `industry[]`, `sector`, `size`, `url`, `employment`, `location` | asserted |
| `Engagement` | `eng_*` | `kind`, `period{start,end,state}` | **materialized** |
| `Role` | `pos_*` | `title`, `functional_title`, `start`, `end`, `state`, `seniority`, `change` | asserted |
| `Contribution` | `prj_*` · `prc_*` | `mode` (project / practice), `title`, `strength`, `recency`, `headline_metric`, `url`, `retired`, `retired_reason` | asserted |
| `Bullet` | `ach_*` | `text`, `status` | asserted |
| `Metric` | `met_*` | `label`, `value`, `as_of` | asserted |
| `Education` | `edu_*` | `qualification`, `institution`, `level`, `field`, `location`, `period` | asserted |
| `Credential` | `cred_*_<n>` | `name`, `issuer`, `issued`, `expires`, `status` | asserted |
| `Skill` | `skill_*` | `name`, `category`, `aliases[]`, `last_used` | asserted |
| `Narrative` | `nar_*` | `text`, `kind`, `audience`, `status` | asserted |

`seniority` stays an ordered enum property rather than becoming a Term. It is closed, ordinal, has
no synonyms, and ranking compares it by position — a node buys nothing and costs a join.

### Not every bullet has a project

`Project` generalises to `Contribution` because **a great deal of senior work is not a project**.
Mentoring, running the hiring loop, presales and solution consulting, on-call and incident command,
standards and review culture, conference talks — each has a duration, a volume, capabilities it
evidences, numbers behind it and resume lines it has earned. None of them has a deliverable.

Today there is nowhere to put them, and the codebase knows it. `okf_compile.bullets()` is called
from exactly one place, inside `build_projects()`, and `authoring/claims.py:_refuse_missing` exists
solely to intercept the mistake that fact invites:

> *"the role case is named on its own because it is the mistake the layout invites: `roles/` and
> `projects/` both hold work, and a `# Bullets` block in a Role compiles to nothing … bullets are
> projects' alone … Name the project the work was done on, or `okf project add` it first."*

So the only sanctioned way to record "interviewed 60 candidates over two years" is to invent a
Project called *Mentoring*, and the write layer enforces that invention with a refusal. A record
whose central rule is *nothing is invented* should not require a fictional project to hold a true
sentence.

There is also a vestige worth naming: `for` is an accepted bullet key in both `body.BULLET_KEYS`
and `okf_compile.bullets()`, and **is read by nothing** but `okf list`. Somebody already reached for
this slot and stopped.

A practice takes the same selection keys a project does — `strength`, `recency`, `seniority`,
`domains`, `capabilities` — because the ranking asks it the same questions. One node type with a
`mode`, not two node types with identical property sets.

### The bullet carrier ladder

A Bullet is claimed by **exactly one** carrier, and the carrier decides where it renders. Four
levels, because work genuinely happens at four scopes:

| Carrier | Renders | Example |
|---|---|---|
| `Contribution` | inside the project or practice, within its role | *Cut event propagation from 5 minutes to under 1 second.* |
| `Role` | in the role's block, attached to no contribution | *Ran the platform team's hiring loop end to end.* |
| `Organisation` | at the top of the company block, above the roles | *Promoted twice in four years; grew the team from 4 to 22.* |
| `Person` | summary or leadership section, spans employers | *Mentored 14 engineers across three companies; 5 promoted to senior.* |

The `Organisation` rung exists rather than an `Engagement` rung for one structural reason:
`Engagement` is materialized, and asserting an edge into a computed node is how a materialized
element stops being safely recomputable. `Organisation` is asserted and stable, and a company-scoped
bullet is what an engagement-scoped bullet actually is.

**Inheritance rule.** A bullet under a `Contribution` inherits its carrier's `EVIDENCES` edges for
matching. A bullet on any other rung has no carrier to inherit from, so it **must** carry its own
`DEMONSTRATES` edges — enforced at write time. That is what stops the upper rungs becoming a dumping
ground for bullets the ranker cannot see, which is the real thing `claims.py`'s refusal was
protecting.

### Plane C — Vocabulary

The plane that does not exist today, and the one that pays for three of the four drivers.

| Node | id | Properties | Origin |
|---|---|---|---|
| `Term` | `term:<facet>:<slug>` | `label`, `facet` (capability / domain / technology), `canonical`, `embedding` | asserted |
| `Theme` | `theme:<slug>` | `label` | asserted |

Today `capabilities`, `domains` and `technologies` are three parallel lists of bare strings on a
Project, checked against a Markdown file that `validate_bundle.py` only consults when it happens to
be populated. As nodes they collapse into one edge type carrying a `facet`, and the vocabulary file
becomes a projection.

### Plane D — Market and pipeline

| Node | id | Properties | Origin |
|---|---|---|---|
| `Posting` | `pst_*` | `title`, `company`, `url`, `seniority`, `body`, `captured` | asserted |
| `Requirement` | `req_<posting>_<n>` | `label` (their wording), `kind`, `necessity`, `sentence`, `embedding` | asserted |
| `Assessment` | `gap_*` | `fit`, `assessed`, `note` | asserted |
| `Verdict` | `vd_<req>` | `verdict`, `axis`, `shortfall`, `score` | **materialized** |
| `View` | `view_*` | `label`, `format_profile`, `region_profile`, `locale`, `provenance_floor`, `budget`, `redact[]`, `x{}` | asserted, **no text property** |
| `Application` | `app_*` | `company`, `role`, `channel`, `submitted` | asserted |
| `TimelineEvent` | `evt_<app>_<n>` | `date`, `event`, `channel`, `note`, `due` | asserted, append-only |
| `RenderedArtifact` | `art_*` | `path`, `variant`, `sha256`, `pages` | asserted |

`Verdict` is the assessment's arithmetic, and it is materialized — one node per requirement, holding
the verdict, the named axis and the shortfall. What stays asserted on `Assessment` is the human
judgement: the overall `fit` and whatever a person wrote. This is the split the current
`.gaps.md` cannot make, because a document is either hand-written or generated and this one is both.

### Plane E — Governance

| Node | id | Properties | Origin |
|---|---|---|---|
| `Source` | `src_*` | `title`, `kind` (interview / document / import), `captured`, `path` | asserted |
| `Question` | `q_*` | `text`, `opened`, `closed` | asserted |
| `Decision` | `dec_*` | `text`, `date` | asserted |
| `RuleSet` | `rule:<scope>:<name>` | `scope` (region / format / ats / writing / structure / pipeline), `payload`, `mode` (replaces / extends) | asserted |

`RuleSet.mode` is the "declare your scope" rule from `bundle-spec.md` turned into a property. Today
an override that forgets to say whether it replaces or extends is silently treated as an extension,
and a resume quietly loses whichever sections it never covered. As an enum with no default, the
write refuses.

### Three node types that dissolve

`Skill Set`, `Metric Set` and `Certification Status` exist because a file must contain something.
A graph has no files, so their contents become nodes directly and the containers go.

That leaves one real casualty worth handling: `Certification Status` carried the meaningful
statement *"none held"*, which the type comment defends as "a legitimate status that evidences no
credential." In the graph that becomes what it actually is — a `Question` node, linked by `RAISES`
to the `Person`, with no `Credential` on the other end. A gap that is a first-class open question is
a stronger record than a document titled after the absence of one.

---

## Edge catalogue

Cardinality is written from the `from` side. `!` marks an edge whose absence is a hard error.

### Career

| Type | From → To | Card | Origin | Properties | Replaces |
|---|---|---|---|---|---|
| `HELD_AT` ! | Role → Organisation | N:1 | asserted | — | `organisation:` |
| `DELIVERED_UNDER` ! | Contribution → Role or Person | N:1 | asserted | — | `role:` |
| `PART_OF` | Role → Engagement | N:1 | materialized | — | `build_engagements` |
| `WITH` | Engagement → Organisation | 1:1 | materialized | — | `build_engagements` |
| `SUCCEEDS` | Role → Role | 0..1 | materialized | `change` | the progression line |
| `CLAIMS` ! | Contribution, Role, Organisation or Person → Bullet | 1:N | asserted | `order` | `# Bullets` block |
| `RESTS_ON` | Bullet → Metric | N:1 | asserted | — | `metric:` field |
| `MEASURED_IN` | Metric → any carrier | N:1 | asserted | — | metrics table col 3 |
| `EVIDENCES` | Contribution → Term | N:M | asserted | `facet`, `status` | three string lists |
| `DEMONSTRATES` | Bullet → Term | N:M | asserted | `status` | the `for:` key nothing reads |
| `DISPLAYS` | Skill → Term | N:M | asserted | — | *new — no join exists today* |
| `HAS_CONTACT` | Person → Contact | 1:N | asserted | — | `# Contact` table |
| `HOLDS` | Person → Credential or Education | 1:N | asserted | — | directory placement |

`DELIVERED_UNDER` stays required but becomes polymorphic. Its `Person` target admits work done under
no employer — the bundle already has an `open-source/` directory and nowhere for it to compile to —
while keeping the guarantee the required edge exists for: a contribution that cannot say whose time
it was on renders nowhere.

`DISPLAYS` is worth calling out. `bundle-spec.md` is explicit that a Skill (`C# / .NET`, editorial,
aliased, for a reader) is *deliberately not the same thing* as a Project's `technologies` (exact
strings, for matching). That is correct and should stay — but today **nothing joins them**, so a
view can select a skill the record has no evidence for. The edge makes the join available without
merging the concepts.

### Vocabulary

| Type | From → To | Card | Origin | Properties |
|---|---|---|---|---|
| `ALIAS_OF` | Term → Term | N:1 | asserted | — |
| `IN_THEME` | Term → Theme | N:1 | asserted | — |
| `BROADER_THAN` | Term → Term | N:M | asserted | — |
| `NEAR` | Term → Term | N:M | materialized | `score`, `method` |

`ALIAS_OF` must point at a Term with `canonical: true`, and chains are refused — one hop resolves any
synonym, always. `BROADER_THAN` is the hierarchy that answers *"they asked for Kubernetes; this
person has container-orchestration"* — a real, defensible partial match that string equality reports
as a total miss. `NEAR` is the embedding edge and is materialized above a threshold, so a semantic
match is inspectable and revocable rather than a number computed inside a scorer.

### Market and pipeline

| Type | From → To | Card | Origin | Properties |
|---|---|---|---|---|
| `POSTED_BY` | Posting → Organisation | N:1 | asserted | — |
| `REQUIRES` | Posting → Requirement | 1:N | asserted | — |
| `MATCHES_TERM` | Requirement → Term | N:1 | asserted | `via` (exact / alias / broader / near) |
| `ASSESSES` | Assessment → Posting | 1:1 | asserted | — |
| `VERDICT_ON` | Verdict → Requirement | 1:1 | materialized | — |
| `SATISFIED_BY` | Verdict → Contribution, Bullet, Credential, Education or Skill | N:M | materialized | `score`, `path` |
| `RENDERS` | View → Posting | N:1 | asserted | — |
| `SELECTS` | View → Engagement, Contribution, Bullet, Skill, Credential or Education | N:M | asserted | `order` |
| `NARRATES` | View → Narrative | N:1 | asserted | — |
| `UNDER` | View → RuleSet | N:M | asserted | — |
| `AGAINST` | Application → Posting | 1:1 | asserted, frozen | — |
| `ANSWERS` | Application → Assessment | 1:1 | asserted, frozen | — |
| `SUBMITS` | Application → View | 1:1 | asserted, frozen | — |
| `TO` | Application → Organisation | N:1 | asserted | — |
| `LOGS` | Application → TimelineEvent | 1:N | asserted, append-only | — |
| `PRODUCED` | Application → RenderedArtifact | 1:N | asserted | — |
| `SUPERSEDES` | Application → Application | 0..1 | asserted | — |
| `FROZEN_FROM` | frozen node → working node | N:1 | asserted | — |

`SATISFIED_BY.path` records the traversal that found the evidence — `exact`, `alias`, `broader`,
`near(0.83)`. That is what lets the assessment keep saying *how* it matched, which is the difference
between "you have it" and "you have something adjacent and should say so out loud."

### Governance

| Type | From → To | Card | Origin |
|---|---|---|---|
| `DERIVED_FROM` | any → Source | N:M | asserted |
| `RAISES` | any → Question | N:M | asserted |
| `RESOLVES` | Question → any | N:M | asserted |
| `DECIDED_BY` | any → Decision | N:M | asserted |

`DERIVED_FROM` is the lineage edge. Today provenance is one word on a concept; here a
`needs-verification` bullet can point at the interview transcript it came from, and "where did this
claim come from" is a traversal rather than a memory.

---

## Constraints the store enforces

The three rules `authoring/schema.py` documents as impossible for it to check are all edge-existence
rules, and all three become impossible to violate:

| Rule today | In the graph |
|---|---|
| A `capabilities` value must be in `capability-vocabulary.md` — checked only when that file is populated | `EVIDENCES` must terminate on an existing `Term`. Undeclared vocabulary cannot be written; a synonym resolves via `ALIAS_OF` instead of being refused. |
| A Project's `role:` must name a concept in `roles/` — checked by nothing; `okf_compile` refuses outright | `DELIVERED_UNDER` cannot dangle. |
| A Role's `organisation:` must name a concept in `organisations/` — same | `HELD_AT` cannot dangle. |

And one rule today enforced by refusing the author rather than by modelling the work:

| Rule today | In the graph |
|---|---|
| A `# Bullets` block in a Role "compiles to nothing and reports nothing", so `claims.py` refuses the write and tells the author to name or create a project | `CLAIMS` accepts four carriers. The bullet has somewhere true to go, so the refusal is deleted rather than reworded. |

And the gates become predicates over the graph rather than passes over text:

| Gate rule | Predicate |
|---|---|
| Every number traces to a real metric | for every Bullet whose text contains a digit, a `RESTS_ON` edge must exist |
| A view may not invent content | `View` has no text-typed property. Structural, not validated. |
| `provenance_floor` | for every `SELECTS(v, t)`, `rank(t.status) >= rank(v.provenance_floor)`, where `confirmed=2 > inferred=1 > needs-verification=0` |
| A frozen input may not change | `frozen: true` rejects every mutation and every new outbound asserted edge |
| A timeline is appended to, never edited | `TimelineEvent` is immutable; a correction is a new event |
| `submitted: false` is the one exemption | exactly one of `Application.submitted = false` or a `submitted` `TimelineEvent` |
| An alias must not chain | `ALIAS_OF` target has `canonical: true` |
| A bullet has exactly one carrier | exactly one inbound `CLAIMS` per Bullet — render placement stays deterministic |
| A carrier-less bullet must still be rankable | a Bullet claimed by anything other than a `Contribution` must have at least one `DEMONSTRATES` edge |
| Stage is derived and stays derived | `Application` has no `outcome`, `stage` or `stale` property |

## The materialization ledger

Invariant 1, enumerated. Nothing here is writable, and `okf gates` re-derives each row and diffs it
against the store — which is the check that keeps "nothing is stored twice" true rather than
aspirational.

| Materialized | Rule | Replaces |
|---|---|---|
| `Engagement`, `PART_OF`, `WITH` | group Role by `HELD_AT`, order by `start` | `build_engagements()` |
| `SUCCEEDS` + `change` | consecutive roles within one engagement | the progression line |
| `Verdict`, `VERDICT_ON`, `SATISFIED_BY` | requirement against evidence, scored | `score_projects.py` |
| `NEAR` | cosine similarity of Term embeddings above a threshold | *new* |
| URS record | projection of the whole graph | `okf_compile.py` |
| Markdown export | projection, one file per node | *new* |
| Stage, staleness, due | last advancing / clock-resetting `TimelineEvent` | `pipeline.py` — stays a query, is **not** materialized |

Stage is deliberately in the last row and deliberately not a stored node. `bundle-spec.md` refuses
to store it for a reason that a graph does not change: a status word and the prose beneath it stop
agreeing the moment one is edited.

## Freezing

An application freezes its posting, its assessment and its view. In the file store that is a file
copy; here it is a **copy-on-freeze into an immutable island**:

1. Clone `pst_acme`, `gap_acme`, `view_acme` to `pst_acme#app_2026-08-26-acme-engineer` and siblings.
2. Set `frozen: true` on each clone and add `FROZEN_FROM` back to the working node.
3. Point `AGAINST`, `ANSWERS` and `SUBMITS` at the clones, never at the working nodes.
4. Clone the transitive closure of `SELECTS` targets, so the *evidence* is frozen too — not just the
   selection of it.

Step 4 is stronger than what exists today. The current design argues a frozen copy is unnecessary
for the record because "it compiles from concepts that are in git, so a resume sent last March
rebuilds from the commit it was sent at." Once the store is a graph rather than a tree of committed
files, that argument no longer holds, and the closure has to be frozen explicitly.

## Indexes

| Index | On | Serves |
|---|---|---|
| unique | `node.id` | identity |
| btree | `node.label`, `node.status` | typed scans |
| btree | `edge(type, from)`, `edge(type, to)` | traversal both directions — this is `refs.py` |
| full text | `Bullet.text`, `Narrative.text`, `Posting.body`, `Requirement.label` | `okf search` |
| vector | `Term.embedding`, `Requirement.embedding`, `Bullet.embedding` | `NEAR`, semantic matching |
| covering | `Contribution(mode, strength, recency)` | ranking without a full compile |

## What the store now answers

**Traversal** — a through-line claim, safe to put in a summary. Today this needs a compile plus
bespoke Python; `bundle-spec.md` states the "three or more" rule and nothing computes it. It now
spans practices as well as projects, which is the point: mentoring across three employers is exactly
the kind of through-line the old model could not see.

```cypher
MATCH (c:Contribution)-[:EVIDENCES {facet:'capability'}]->(t:Term)
MATCH (c)-[:DELIVERED_UNDER]->(:Role)-[:HELD_AT]->(o:Organisation)
MATCH (c)-[:CLAIMS]->(b:Bullet)-[:RESTS_ON]->(:Metric)
WHERE b.status = 'confirmed'
RETURN t.label, count(DISTINCT c) AS carriers, count(DISTINCT o) AS employers
HAVING carriers >= 3 AND employers >= 2
```

**Integrity** — `refs.py`'s six shapes, as one query.

```cypher
MATCH (x)-[e]->(target {id: $id}) RETURN x.id, type(e), e.origin, x.frozen
```

**Semantics** — the synonym that silently stops matching today.

```cypher
MATCH (r:Requirement {id:$req})-[m:MATCHES_TERM]->(t:Term)
MATCH (t)<-[:ALIAS_OF|BROADER_THAN*0..1]-(t2:Term)
MATCH (c:Contribution)-[:EVIDENCES]->(t2)
RETURN c.id, m.via, t2.label
```

**Speed** — ranking reads six columns and two edge types instead of compiling the whole record,
which is what `okf score` does today via `okf_compile.load()`.

## What breaks

| Frozen surface | Status |
|---|---|
| #1 `okf` command surface | **Survives**, and gains one verb. `okf practice add` joins `okf project add`; every other verb is unchanged. |
| #2 Bundle layout on disk | **Breaks.** Major version, `CURRENT_REVISION` bump, a migration that reads every revision back to 1, and `validate_bundle.py` warning rather than failing on the old shape. |
| #3 Compiled record shape and gate behaviour | **Survives.** URS becomes a projection; `resolve.py` and the emitters are untouched. Gates keep failing on exactly what they fail on today. |
| #4 (undocumented) Tests assert on output text | **Survives**, provided verdict lines are added to and never reworded. One refusal in `claims.py` is deleted rather than reworded, and its test goes with it. |

Also breaking, and worth stating plainly: hand-editing an exported Markdown file stops having any
effect, and `git diff` over the store stops being a diff over readable career prose.

## Deliberately not designed

- **Bitemporal versioning / time-travel.** Freezing covers the only real requirement — "what did I
  send them" — and a full history engine is a large amount of machinery for a question nobody in
  this codebase has asked.
- **`seniority` as a Term.** Closed, ordinal, no synonyms.
- **A fifth carrier rung.** `Education` could carry bullets; nothing in the record asks it to.
- **An inference layer over the ontology.** `ALIAS_OF` and `BROADER_THAN` are hand-declared, one hop.
  A reasoner is a different project.
- **Multi-person graphs.** `Person` is a singleton and stays one.
- **The physical store.** Node/edge shape, constraints and the materialization ledger are all
  engine-agnostic. Choosing between a text-native graph serialization, a single embedded database,
  or an event log with a materialized fold is a separate decision, and none of them changes a row
  above.
