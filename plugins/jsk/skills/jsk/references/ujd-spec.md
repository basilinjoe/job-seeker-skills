# UJD — Universal Job Description Schema v1

A JSON standard for the job posting, against which a career record is matched.

```
media type   application/jobposting+json
file         *.posting.json
schema       schema/ujd-v1.schema.json
example      schema/example.posting.json
counterpart  schema/urs-v1.schema.json  (URS — the career record)
```

**URS models a record its author owns. UJD models third-party text of unknown fidelity.** That
asymmetry is the whole design. A resume claim is asserted by the person it describes and can be
verified with them. A posting claim is written by someone with an interest in how it reads, syndicated
through systems that drop fields, and taken down before anyone can check it. So every claim here
carries not just *what* was said but *how it was learned* — stated in a feed, read out of prose, or
guessed — and a matcher that ignores that distinction will rank on a guess.

## Why not schema.org JobPosting

schema.org JobPosting is alive and actively maintained (V30.0, 2026-03-19) and remains Google's
supported job rich-result type. It is the right thing to **map to**. It is the wrong thing to
**match on**, because it is an SEO-publisher-facing vocabulary and its looseness is deliberate:

| Gap | Evidence |
|---|---|
| No required-vs-preferred modifier, anywhere on the type | The strings `seniority`, `jobLevel`, `careerLevel`, `experienceLevel` and `preferredQualifications` do not occur anywhere in the schema.org vocabulary |
| `experienceRequirements` ranges over `Text` OR a *pending* type with one property | `OccupationalExperienceRequirements` carries only `monthsOfExperience`; pending terms are "subject to change" |
| `occupationalCategory` is bound to no taxonomy and permits bare `Text` | "preferably using a term from a taxonomy such as BLS O*NET-SOC, ISCO-08 or similar" — and Google's profile does not request it at all, so live postings overwhelmingly lack codes |
| `jobLocationType` is untyped free text | Its only documented value is `TELECOMMUTE`; **hybrid has no sanctioned representation** |
| No boolean-expression structure | Raised in the W3C Talent Marketplace Signaling CG and left unanswered: "slicing and dicing education, experience, and qualification… runs counter to how these attributes are frequently stated in actual postings as boolean expressions" |

schema.org is not requirement-*free* — `eligibilityToWorkRequirement`, `securityClearanceRequirement`,
`physicalRequirement`, `sensoryRequirement`, `educationRequirements`, `qualifications`, `skills` and the
boolean `experienceInPlaceOfEducation` all exist, and UJD reuses their semantics. What is missing is the
priority modifier and the boolean structure, and those are what matching actually runs on.

## Why not JSONJob

JSON Resume's job-description counterpart (`jsonresume.org/job-description-schema`, v1.0.0) repeats,
on the posting side, exactly what URS's own spec objects to on the resume side: `qualifications` is an
array of bare strings, `salary` is a bare string, `experience` is a bare string (`"Mid-level"`), and
`remote` is a bare string (`"Hybrid"`). Nothing carries an id, a priority, or a source. It is a
container around prose, and prose is what a matcher cannot read.

## Prior art worth tracking

**Open Job Protocol** (openjobprotocol.org, v0.2.0, MIT, JSON Schema 2020-12) is the closest live
effort and reached the same two conclusions independently: an explicit `must_have` / `nice_to_have`
split, and a bespoke seniority enum. It is a superset of schema.org's properties restructured into
flat agent-readable fields. UJD differs in carrying provenance on every claim and in modelling boolean
requirement groups. *Assessed from its published overview only — the field-level schema was not
retrieved, so treat the comparison as provisional.*

**HR Open Standards** (4.5 Final, 4.6 Candidate Release) ships genuine JSON Schema 2020-12 artifacts
for `PositionOpeningType` and `PositionProfileType`, free and un-gated. The substantive job fields live
in `PositionProfile`, not `PositionOpening` — the latter is a thin envelope. It is a usable donor for
field naming, but it states no open licence, and it is widely characterised as low-adoption next to
schema.org. **JDX** (Job Data Exchange), now hosted by HR Open, was purpose-built for postings and was
not evaluated.

## Design rules

The first four are URS's, unchanged. The last three are UJD's own.

1. **Every claim is an object, never a bare string.**
2. **Every node carries a stable `id`.** Referencing beats copying.
3. **Ambiguity is illegal.** Dates carry precision; `unstated` is a value, not a missing key.
4. **Unrecognised keys are rejected.** Extensions live under `x`, keyed by reverse DNS.
5. **How a fact was learned is part of the fact.** `structured-feed`, `posting-text` and `inferred`
   are different epistemic states and MUST NOT collapse. An `inferred` source cannot yield a
   `confirmed` status — the schema enforces this, because laundering a guess into a fact is the
   failure this format exists to prevent.
6. **Hard filters are not scored requirements.** Work authorization, clearance and applicant location
   live in `eligibility`, never in `requirements`, so no amount of skills overlap can offset a visa bar.
7. **Absence is data.** `disclosed: false`, `sponsorship: "unstated"` and an empty
   `required_technologies` are assertions about the posting. Filling them in from what the posting
   *implies* invents a requirement.

## Document shape

```json
{
  "$schema": "https://openresume.dev/ujd/v1/posting.schema.json",
  "ujd": "1.0.0",
  "meta": { },
  "posting": { },
  "organization": { },
  "role": { },
  "engagement": { },
  "locations": [ ],
  "eligibility": { },
  "compensation": { },
  "requirements": [ ],
  "requirement_groups": [ ],
  "responsibilities": [ ],
  "benefits": [ ],
  "process": { },
  "emphasis": [ ],
  "concerns": [ ],
  "source": { },
  "x": { }
}
```

Only `ujd`, `meta` and `posting` are required. A posting with a title and nothing else is a valid
document; an ambiguous one is not.

## Core types

### Provenance

URS's four statuses, unchanged, so `confirmed` means the same thing in the bundle, the resume and the
posting. What differs is `source.kind`:

| kind | Means |
|---|---|
| `structured-feed` | The publisher put it in a field |
| `posting-text` | It was read out of prose |
| `employer-site` | It came from the employer, not the aggregator copy |
| `recruiter` | Someone said it, and it is not in the ad |
| `inferred` | Nothing in the posting states it |

`confirmed` here means **the posting says it**, not that it is true. A salary band and a claim of
"unlimited leave" are both `confirmed` when stated; whether they survive contact with reality is
`concerns`, not `provenance`.

Level 2 requires a `source.span` on anything with `kind: posting-text` — the substring it was read
from. An extraction nobody can trace back to a span is an assertion.

### Requirement

The matching axis, and the reason UJD exists.

```json
{ "id": "req_azure", "kind": "technology", "necessity": "must-have",
  "value": "azure", "label": "Azure integration services",
  "raw_text": "Hands-on with Azure integration services within the last two years.",
  "experience": { "min_months": 36, "recency_months": 24 },
  "provenance": { "status": "confirmed", "source": { "kind": "posting-text", "span": "…" } } }
```

`value` is the vocabulary term the score is computed on. `label` is the posting's own phrasing. They
are separate because **the resume should mirror the posting's wording while the score runs on the
vocabulary term** — for `kind: capability`, `value` MUST be an exact string from the capabilities
vocabulary named in `meta.vocabularies`, since matching is literal and a synonym scores zero while
looking like absent evidence.

`necessity` has three values, not two:

- `must-have` — stated as required.
- `preferred` — stated as desirable.
- `implicit` — the posting clearly operates under it but never states it. It MUST carry
  `provenance.source.kind: inferred` (enforced), so a scorer can exclude every inference in one
  predicate. Naming this tier is what stops an inference from being quietly promoted to a requirement.

`experience` stores months, and both bounds are optional: `"5+ years"` has no maximum and inventing
one changes the meaning. `recency_months` is a separate demand from a total — "three years, within the
last five" is two numbers.

### RequirementGroup

The boolean case, which a flat list genuinely cannot express:

> *A bachelor's degree in a technical discipline and six years in architecture roles, or a
> postgraduate qualification in a related field.*

Decomposed flat, this becomes three must-haves and scores a PhD holder as missing two of them.
Flattened to a single `any` over all three, a bare degree satisfies it. Both are wrong, so groups
nest:

```json
{ "id": "grp_qualification", "satisfy": "any",
  "members": ["grp_degree_and_years", "req_postgrad"] }
{ "id": "grp_degree_and_years", "satisfy": "all",
  "members": ["req_degree", "req_six_years"] }
```

`satisfy` is `all`, `any` or `at-least` (with `n`). Members are requirement ids *or* group ids. Two
levels covers every real posting seen; deeper is legal but a scorer that cannot explain its verdict in
one sentence has stopped being reviewable.

A requirement's `group` names the **innermost** group containing it.

### OccupationCode

Never a bare code, and never without a vintage:

```json
{ "scheme": "onet-soc", "scheme_version": "2019", "code": "15-1299.08",
  "label": "Computer Systems Engineers/Architects",
  "match_type": "close", "confidence": 0.78 }
```

O*NET-SOC 2010 → 2019 changed 107 codes, removed 157 and added 63: `15-1141.00` meant Database
Administrators under 2010 and is not a valid 2019 code at all. Cross-scheme codes need `match_type`
too, because the official O*NET↔ESCO crosswalk is an ML-derived mapping with human validation whose
best model returned the correct exact match first only 85% of the time, and whose `related` tier
shipped with explicitly lower quality assurance. **Do not score `match_type: "related"` as a match.**

`match_type: "asserted"` means the posting itself named the code — rare, since Google's profile does
not request `occupationalCategory` and so almost nothing emits it.

### Location and eligibility

`mode` is a closed enum — `onsite`, `hybrid`, `remote` — matching URS `Location.mode`. `hybrid`
requires a `city`, because hybrid without a place is not a work mode but an unanswered question, and
`onsite_days_per_week` is the number that decides whether the role is workable at all. It is absent
from every format surveyed.

Where the work happens (`locations`) and where an applicant may be based
(`eligibility.applicant_locations`) are separate, as they are in schema.org. A "remote" posting that is
remote-within-one-country is where the distinction bites.

## The matching model

UJD pairs with URS field for field on the axes `score_projects.py` already weighs:

| UJD | URS | Term |
|---|---|---|
| `requirements[kind: capability].value` | `projects[].capabilities` | ×3, a count |
| `requirements[kind: technology].value` | `projects[].technologies` | ×2, a count |
| `role.domains` | `projects[].domains` | ×2, binary — any overlap scores full |
| `role.seniority` | `projects[].seniority` | ×2, graded 1.0 → 0.0 |
| `eligibility.work_authorization` | `work_authorization` | hard filter, never scored |
| `process.documents_required` | `views[].sections`, `narratives[]` | render selection |

`role.seniority` reuses URS's eight-value enum **verbatim**. It must stay identical or the axis breaks.
It is bespoke because no open standard exists to borrow: seniority appears nowhere in schema.org, and
LinkedIn's list is behind an authenticated API and conflates engagement type (`Unpaid`, `Training`)
with hierarchical rank, making the values unorderable. Engagement type therefore lives on
`engagement.kind`, on its own axis, and never in seniority.

## Conformance levels

| Level | Requires | Reachable from |
|---|---|---|
| **0 — Core** | `posting.title`, `organization.name`; requirements may be prose in `raw_text` | mechanical conversion from schema.org JobPosting |
| **1 — Structured** | requirements carry `kind`, `necessity` and vocabulary `value`s; `role.seniority` set | one analyst pass |
| **2 — Traceable** | provenance on every claim, `source.span` on every `posting-text` extraction, `source.raw_text` retained | the posting analyst working from the ad |

Level 0 exists so ingesting a feed costs nothing. A format without a zero-cost entry point is a format
nobody adopts.

## Interoperability

The layered design: a tight core, plus documented mappings inward. Every inbound mapping MUST record
what it dropped in `source.ingest_notes` — a lossy mapping that reports nothing is indistinguishable
from a lossless one.

### schema.org JobPosting → UJD

| schema.org | UJD | Note |
|---|---|---|
| `title` | `posting.title` | |
| `hiringOrganization` | `organization` | |
| `datePosted`, `validThrough` | `posting.posted`, `posting.valid_through` | |
| `employmentType` | `engagement.arrangement` | `FULL_TIME` → `full-time` |
| `jobLocation` | `locations[]` | |
| `jobLocationType: TELECOMMUTE` | `locations[].mode: remote` | the only documented value |
| `applicantLocationRequirements` | `eligibility.applicant_locations` | |
| `baseSalary` | `compensation.figures[]` | `basis` is not expressible inbound → `unstated` |
| `occupationalCategory` | `role.occupation[]` | `CategoryCode.inCodeSet` → `scheme`; bare `Text` → `scheme: other` |
| `experienceRequirements` | `requirements[kind: experience]` | `Text` → `raw_text`, `necessity: must-have`, needs extraction |
| `skills`, `qualifications` | `requirements[]` | prose; `necessity` not recoverable |
| `eligibilityToWorkRequirement` | `eligibility.work_authorization` | |
| `securityClearanceRequirement` | `eligibility.security_clearance` | |
| `experienceInPlaceOfEducation` | `requirements[].substitutable_by` | boolean → an explicit link |
| — | `requirements[].necessity` | **not recoverable**; default `must-have` and flag |
| — | `emphasis`, `concerns`, `process.stages` | no counterpart |

### UJD → schema.org JobPosting

Lossy in three known places, and they should be stated rather than discovered:

1. **`hybrid` does not round-trip.** `jobLocationType` accepts only `TELECOMMUTE`; Google excludes
   hybrid from markup entirely. Emitting `Hybrid` is a validation failure — a mainstream CMS shipped
   exactly that bug (joomla/joomla-cms#48033). Emit `hybrid` as an onsite `jobLocation` with no
   `jobLocationType`, and keep `onsite_days_per_week` in the description.
2. **`necessity` is dropped.** There is nowhere to put it. `preferred` and `implicit` requirements
   should not be emitted as `skills`, or a nice-to-have becomes a stated requirement.
3. **Requirement groups flatten.** `monthsOfExperience` takes a single number that Google specifies as
   "the lowest bar for entry"; the boolean structure survives only in prose.

### Other inbound formats

| Format | Direction | Status |
|---|---|---|
| Open Job Protocol v0.2.0 | inbound | `must_have`/`nice_to_have` → `necessity`; mapping not yet written |
| HR Open `PositionProfileType` | inbound | donor for field naming; licence terms unverified |
| JSONJob v1.0.0 | inbound | Level 0 only — everything arrives as prose |
| Greenhouse, Lever, Workday, Ashby, Indeed XML, LinkedIn feed | inbound | **unresearched, see below** |

## What this schema does not rest on

Stated plainly because a schema that hides its unvalidated parts invites people to trust the wrong ones.

- **ATS and job-board feed shapes were not researched.** Greenhouse, Lever, Workday, Ashby, Indeed XML
  and the LinkedIn feed produced no verified findings. `source.ingested_from` names them, but no
  mapping is written and no claim is made about what they emit. This is the largest gap.
- **Compensation modelling is reasoned, not surveyed.** `Compensation` and `CompensationFigure` are
  extrapolated from URS's own `CompensationFigure` (whose CTC-versus-base distinction is carried over
  intact) rather than from evidence about how postings state pay. US state pay-transparency law and the
  EU Pay Transparency Directive were not researched. Expect a 1.1 revision.
- **ESCO is referenced but nothing is embedded.** Whether ESCO content is redistributable is
  genuinely unresolved — competing claims about its licence were both refuted. `esco` is a permitted
  `scheme` value, which requires no rights; no ESCO label or identifier ships in this repo. Read
  `esco.ec.europa.eu/en/copyright-notice-esco-skills-competences` before that changes.
- **O*NET/SOC crosswalk files are CC BY 4.0** and safely embeddable, with attribution, a licence link
  and a change statement. The Web Services API is under stricter terms than the downloadable files.
- **Lightcast Open Skills is not a default.** Commercial use is gated behind a negotiated contract and
  the grant is non-sublicensable, so it cannot ship to downstream implementers.
- **`OccupationalExperienceRequirements` is a pending schema.org term**, explicitly subject to change.
  Re-verify before freezing the mapping.

## Evolution

`ujd` carries the version; the major version appears in the `$schema` path. Minor versions are
**additive only**. Extensions live under `x`, keyed by reverse DNS, MUST be ignorable, and MUST be
preserved on round-trip. Everywhere else an unrecognised key is rejected — for the same reason URS
gives: a silently ignored `startDate` where the schema says `start` is a date that vanishes with
nothing reporting it, and a rejected typo is a fixed typo.

## Deliberate exclusions

Application state and outcomes, which belong to the pipeline, not the posting · employer reviews and
ratings · scored match results, which are computed and not stored here · the resume that answered the
posting, which is a URS view · rich text in any field · salary estimates from third parties, since
schema.org's own `estimatedSalary` was dropped from Google Search in June 2025.

## Relationship to the Job Target file

UJD **replaced** it, at bundle revision 4. `tailoring/targets/<company>-<role>.md` and its
`target-template.md` are gone, and `score_projects.py` reads `requirements[]` directly.

The Markdown file could not carry the three things matching actually runs on: `necessity`, so a
preferred skill scored as a demand; boolean requirement groups, so *"a degree and six years, or a
postgraduate qualification"* had to be flattened into a reading that was wrong either way; and a
provenance span, so no extraction could be checked against the advertisement it came from.

What is not lost is the human checkpoint, which was the reason to keep a Markdown file. It comes back
as `validate_ugs.py --report` — rendered from the JSON on demand, so unlike editable frontmatter it
cannot drift from what the scorer read. `migrate_bundle.py` converts an older bundle and reports what
it could not recover, `necessity` first among it.
