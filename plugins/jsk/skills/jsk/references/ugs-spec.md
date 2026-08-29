# UGS — Universal Gap Schema v1

A JSON standard for the join between a job posting and a career record: which requirements the
record satisfies, by what evidence, how far short it falls, and what would close the difference.

```
media type   application/gapanalysis+json
file         *.gaps.json
schema       schema/ugs-v1.schema.json
example      schema/example.gaps.json
counterparts schema/ujd-v1.schema.json  (UJD — the posting, the requirement side)
             schema/urs-v1.schema.json  (URS — the career record, the evidence side)
```

**Both sides already exist. This document is only the join.** UJD owns necessity, weight, vocabulary
and raw text; URS owns the career record. UGS restates neither — it references them and adds the one
thing neither can hold, because neither knows about the other: a typed relation from a requirement to
the evidence that bears on it, with partial satisfaction, confidence, and the method that produced
the verdict.

## Why a third document

The relation has to live somewhere, and it cannot live on either side. A posting is written before it
meets any candidate. A career record is written before it meets any posting. Putting satisfaction on
either one makes that document specific to a pairing it should outlive.

It also has nowhere to go in existing vocabularies. Of the standards surveyed:

| Standard | Supplies | Does not supply |
|---|---|---|
| **Open Badges 3.0** `Alignment` | `targetName`, `targetUrl`, `targetFramework`, `targetCode`, `targetType` — anchoring both sides to a shared taxonomy node | Any requirement, partial-satisfaction or gap relation. Models the claim direction only |
| **ESCO** | `essential` vs `optional` on occupation-skill relations | Posting-specific criticality; any numeric weight at all |
| **SFIA** | Seven ordinal responsibility levels, stable four-letter skill codes, and a clean split between professional skills and generic level attributes | The comparison itself |
| **CTDL** | A rich requirement side | The candidate side, by the publisher's own scope: `EvaluationOutcome` carries a usage note barring assessments of people, and its only `Person` subclass models credentialing agents, not holders |
| **schema.org** | `monthsOfExperience`, `EducationalOccupationalCredential` | A required-vs-preferred modifier anywhere on `JobPosting`; `skills` deliberately conflates the claimed and required sides into one untyped property |

So the vocabulary on either side of the join is borrowable and the join is not. That is the whole
reason this file exists, and it is worth being explicit that this part is **authored, not inherited**.

### On the name

"Skill gap" is reportedly a standardised term in EU/Cedefop usage for a *firm-internal, incumbent-worker*
deficiency measured against an employer's current requirements — not a candidate-versus-vacancy delta.
That report **failed verification and was not disproven**; it is recorded here as an open question, not
a fact. If it holds, `gap` is the wrong word for what this document holds and the term to prefer is
*assessment* — which is why the core type is `Assessment` and `gap` appears in the filename and
nowhere in the vocabulary.

## Design rules

The first four are URS's and UJD's, unchanged. The rest are UGS's own.

1. **Every claim is an object, never a bare string.**
2. **Every node carries a stable `id`.** Referencing beats copying.
3. **Ambiguity is illegal.** `indeterminate` is a value, not a missing key.
4. **Unrecognised keys are rejected.** Extensions live under `x`.
5. **A satisfaction claim requires a pointer to what satisfies it.** `satisfied`, `partial` and
   `stale` all require at least one `Evidence`. The schema enforces it. This is the rule the
   document exists for: an unevidenced verdict is an assertion wearing a verdict's clothes.
6. **Neither subject document is restated.** Requirements are referenced by `req_` id. `label` is
   denormalised for readability and is explicitly never matched on.
7. **Eligibility is a gate, never a score component.** `score.eligibility_excluded` can hold exactly
   one value, `true`. UJD keeps visa, clearance and location out of `requirements`; UGS keeps them
   out of the score, so no skills overlap can offset a bar.
8. **No aggregate without its formula.** `score.aggregate` requires `value`, `method` *and*
   `formula`. An aggregate that cannot say how it was computed is refused by the schema.
9. **How an assertion was produced is part of the assertion.** `provenance.method` and
   `provenance.stage` are separate fields because extraction and resolution fail differently.
10. **Unknown is a value.** `Shortfall.unknown` marks a requirement whose demanded level could not be
    read from the posting. Trained human annotators agree only moderately on that judgement, so a
    required level asserted with false precision is worse than one marked unknown.
11. **No protected characteristics, and no proxies for them.** Nothing in this schema holds a name,
    age, gender, nationality, photo or any field that stands in for one. `Review.reviewer` is a role
    or a handle. UJD records `age_or_demographic_restrictions` verbatim because it is a fact about
    the posting; that fact is never carried into an assessment here.

## Document shape

```json
{
  "$schema": "https://openresume.dev/ugs/v1/gaps.schema.json",
  "ugs": "1.0.0",
  "meta": { },
  "subjects": { },
  "eligibility": { },
  "assessments": [ ],
  "group_assessments": [ ],
  "surplus": [ ],
  "surface": [ ],
  "questions": [ ],
  "score": { },
  "methods": [ ],
  "review": { },
  "x": { }
}
```

Only `ugs`, `meta` and `subjects` are required. `subjects` pins the record and, when there is one,
the posting — with checksums:
a gap verdict recomputed against an edited posting is a different verdict, and postings are edited
and taken down.

## The gap taxonomy

`Assessment.verdict` is the taxonomy, and the distinctions in it are the ones that change what a
person should do next.

| Verdict | Means | Action it implies |
|---|---|---|
| `satisfied` | Evidence meets the requirement | Surface it |
| `partial` | Evidence meets part of it, on a named axis | Close the named shortfall, or argue it |
| `unsatisfied` | The record shows the person does not have it | Substitute, or accept |
| `unevidenced` | The record *claims* it with nothing behind it | Confirm, correct, or cut — never leave |
| `stale` | Held, but not recently enough for what was asked | Refresh, or reframe |
| `indeterminate` | The comparison could not be made | Ask, or exclude |

`unevidenced` is the one that earns its place. It is indistinguishable from `satisfied` to any keyword
matcher and it is the claim that collapses under the first interview question. The schema requires a
`question` on it, because recording one without asking leaves it in the resume.

`indeterminate` must not be silently rendered as `unsatisfied`. They are different answers and only
one of them is about the candidate.

**Surface gaps are separate.** Held in the record, absent from what was actually sent, is a different
failure from not having the thing, with a much cheaper fix — and the two are identical to any reader
looking only at the rendered document. `surface[]` is only meaningful when `subjects.record.view`
names what was rendered; a keyword is always missing *from something*.

**Surplus is first-class.** `surplus[]` holds what the candidate has that the posting never asked for.
No surveyed standard models this at all, and a matcher that only counts deficits cannot see the thing
that makes an application interesting. `relevance: reframes` is the rare and valuable case.

## Answering a requirement group

This is the case UJD built `RequirementGroup` for, and the case a flat requirement list gets wrong in
both directions. From the example posting:

> A bachelor's degree in a technical discipline and six years in architecture roles, or a
> postgraduate qualification in a related field.

That is `any` over [ `all` over [ degree, six-years ], postgraduate ]. The example record holds a
Master of Engineering and 67 months of architecture roles.

| Treatment | Result | Why it is wrong |
|---|---|---|
| Flatten to three independent must-haves | Two misses | Scores a master's holder as unqualified |
| Flatten to one `any` over all three | Pass | A bare bachelor's would also pass it |
| **Answer as a group** | **Satisfied via the postgraduate arm** | The five-month shortfall on the other arm costs nothing |

`GroupAssessment` therefore answers the group as a group. `branches[]` carries one entry per direct
member **in the group's own order**, a member that is itself a group is answered by its own
`GroupAssessment` and referenced, and nesting is preserved rather than expanded.

`closest_branch` is required whenever a group is `partial` or `unsatisfied`. It is the actionable half
of the answer: *"you are five months short on the degree-and-experience arm"* is advice; *"you fail the
qualification clause"* is not.

`branches[].distance` is a **local ordering**, comparable only between branches of the same group, and
the scale it uses must be stated in the component method. It is not a score.

## Scoring

Decomposed, always.

The failure mode is documented. An audit of embedding-based resume screening — whole-document cosine
similarity, top 10% selected, one opaque scalar per candidate — favoured White-associated names in
**85.1%** of test cases and female-associated names in **11.1%**; Black male candidates were
disadvantaged in up to **100%**. When names were swapped for others of comparable frequency in the
model's own pretraining corpus, the direction of preference **reversed**. Shorter resumes produced
*more* biased outcomes than full ones. The number was never about the requirements.

Decomposition is not a fairness guarantee and this spec does not claim it as one. It is the minimum
that makes a disputed outcome traceable to something a person can point at — which is also the unit
published explainable matching systems actually surface: a single requirement-to-evidence pairing,
not an aggregate.

So `score.components[]` is required and `score.aggregate` is optional and constrained: `value`,
`method`, `formula` and `components_included`, or the schema rejects it. `excludes_implicit` records
whether requirements the posting never stated were counted — UJD names them `implicit` precisely so a
scorer can drop them in one predicate, and saying which way it went is part of showing the working.

Note in the example that `cmp_qualification` is scored **from the group verdict, not from its
members**. Summing the members would score it 0.66 and be wrong.

## Method is not a detail

`methods[]` is a registry, referenced from `provenance.method`, so the method is recorded per
assertion without being repeated on every one.

It matters because reliability varies by an order of magnitude. On the same task of linking vacancy
text to a skills taxonomy, a supervised extractor reached F1 54.3 where a general-purpose LLM reached
0.22, and the best reported rank-1 accuracy for skills was **0.3969** — under 40%. Requirement
entities resolved by any automated method are therefore not ground truth, and an assertion whose
method is unknown cannot be weighed. One whose method is assumed will be over-weighed.

`provenance.stage` separates `extraction` from `resolution` from `assessment` because recognition
errors propagate into disambiguation: a wrong verdict traceable only to "the pipeline" cannot be
localised.

`Evidence.span` retains the verbatim source text. Roughly **1%** of resumes in a 200,000-resume
production corpus carried hidden prompt injections aimed at automated readers, and over 90% avoided
explicit instruction keywords. A verdict that cannot be re-read against the original text cannot be
audited.

## Conformance levels

| Level | Requires | Reachable from |
|---|---|---|
| **0 — Core** | `subjects` pinning both documents; assessments carry `requirement` and `verdict` | A first pass with no evidence linking |
| **1 — Evidenced** | Every `satisfied`/`partial`/`stale` carries evidence; shortfalls typed; `score.components` decomposed | A matcher run over two Level 1 documents |
| **2 — Auditable** | `provenance` with `method` and `stage` on every assertion; `Evidence.span` retained; `review.state` present; both subjects checksummed | A pipeline that records what it did |

Level 0 exists so a first pass costs nothing. Level 2 is what a document needs to be defensible a
month later, when the posting is gone.

## Deliberate exclusions

- **No candidate ranking.** UGS models one record against one posting, for the person that record
  describes. `meta.purpose` has no value for screening or selection, and nothing here is fit for
  filtering applicants. This is a design boundary, not a disclaimer.
- **No fairness metric.** Adverse-impact analysis is a property of a decision process across a
  population. A single-pairing document cannot hold one, and a field that looked like it could would
  invite exactly the wrong use.
- **No free-text overall summary.** The decomposition is the summary.
- **No proficiency self-rating.** URS already replaces it with evidence pointers, for the same reason.

## What this schema does not rest on

- **The join is authored.** No surveyed standard models requirement-versus-evidence with partial
  satisfaction, confidence and provenance. `Evidence.relation`, `Shortfall.dimension`,
  `Assessment.verdict` and `Counterfactual.kind` are this schema's own vocabularies, versioned with it.
- **Two open questions.** Whether HR-XML Competencies 1.0 — reportedly built for "matching an asserted
  competency against one that is demanded", with ratings and weights — survives into HR Open 4.x is
  unresolved, and if it does, parts of this design should be re-expressed in its terms. Whether
  Cedefop's mismatch taxonomy supplies a reusable controlled vocabulary is likewise unresolved. Both
  failed verification without being disproven.
- **The bias and reliability figures cited above are single-source** and have not been independently
  replicated here. They are load-bearing for the *shape* of the schema, not for any number in it.

## Evolution

Additive within `1.x`: new enum values, new optional fields. A removed field or a narrowed enum is a
major version. `Assessment.verdict` and `Evidence.relation` are the two vocabularies most likely to
grow, and both are closed enums on purpose — an open vocabulary here would let a matcher invent a
verdict that no reader can interpret.

### 1.1

Two widenings. Every 1.0 document remains valid against 1.1.

**`Subjects` requires only `record`.** A record audit run against no posting — `meta.purpose:
self-assessment` — has no requirement side to pin, and 1.0 made that document invalid before it could
be written. `posting` stays required in substance rather than in schema: an assessment naming a
`req_` id it cannot resolve is still a broken document, and the validator says so.

**`Question.priority` gains `unmet-requirement`**, second, after `blocking`. The 1.0 enum is
record-quality only and has no value for *the posting asks for this and the record does not answer
it* — which is the most common thing a tailoring round has to ask about. It is named for the
requirement, not the record, because the answer is often evidence that was simply never written down.

It is deliberately **not** `unevidenced-requirement`. The `unevidenced` *verdict* means the opposite
thing — a record claim with nothing behind it — and two vocabularies one letter apart in the same
document is how a reader ends up acting on the wrong one.

## Relationship to mode-gaps

`references/mode-gaps.md` is the conversation; UGS is what the conversation reads from and writes back
to. The mapping is direct:

| mode-gaps | UGS |
|---|---|
| Blocking, then inferred claims, then missing metrics, then unexplored | `Question.priority`, in that enum order — with `unmet-requirement` second when a posting is in view |
| "Quote it exactly, say where it came from, offer the exit" | `Question.quoted_claim` + `expected: confirm-correct-or-cut` |
| Confirm, correct, or delete — all three fine, leaving it is not | `Question.resolution` |
| An honest approximation beats silence | `Shortfall.evidenced` with `provenance.status: needs-verification` |
| "Which claims should be softened or cut" | `verdict: unevidenced` with `resolution: unavailable` |
| One question at a time | `questions[]` ordered by `priority`; `asked` tracks the queue |

The auditor writes the document; the human loop resolves questions against it; the validator checks
that no `satisfied` verdict lost its evidence on the way.
