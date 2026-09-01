# URS — Universal Résumé Schema v1

A JSON standard for the career record, from which a resume is rendered.

```
media type   application/resume+json
file         *.resume.json
compiler     jsk_okf/okf_compile.py
profiles     schema/profiles/<region>.json
discovery    https://example.com/.well-known/resume.json
```

**The document is the record. A resume is a view over it.** That inversion is the whole design: a
tailored resume is a *selection*, expressed as references to IDs, and a renderer that cannot invent
text is a renderer that cannot embellish.

## Why not JSON Resume

JSON Resume is a container around unstructured prose: a bullet is a bare string so no metric can be
verified, nothing carries an id so tailoring means copy-and-mutate, nothing carries provenance, and a
promotion has to be modelled as two duplicate employers.

URS keeps a **normative bidirectional mapping** to JSON Resume at conformance Level 0, so adoption
costs nothing and is reversible. See *Interoperability* below, and `docs/urs-guide.md` for the gap
table and the reasoning.

## Design rules

1. **Every claim is an object, never a bare string.**
2. **Every node carries a stable `id`.** Referencing beats copying.
3. **Provenance is a field, not a convention.**
4. **Selection, never rewriting.** A view references IDs; it MUST NOT contain content text.
5. **Ambiguity is illegal.** Dates carry precision. "Ongoing" is a state, not a missing key.
6. **No self-rated anything.** Skills carry evidence links, not "Expert".
7. **Core is what is true everywhere.** Everything market-specific is a profile.

## Document shape

```json
{
  "$schema": "https://openresume.dev/urs/v1/resume.schema.json",
  "urs": "1.0.0",
  "meta": { "id": "...", "lang": "en", "updated": "2026-08-25",
            "vocabularies": { "capabilities": "..." } },
  "person": { },
  "work_authorization": [ ],
  "identity_documents": [ ],
  "languages": [ ],
  "organizations": [ ],
  "engagements": [ ],
  "education": [ ],
  "credentials": [ ],
  "projects": [ ],
  "skills": [ ],
  "narratives": [ ],
  "referees": [ ],
  "availability": { },
  "compensation": { },
  "views": [ ],
  "x": { }
}
```

Only `urs`, `meta`, `person` and `views` are required. An empty career is a valid document; an
ambiguous one is not.

## Core types

### Instant and Period

Precision is explicit, and so is the difference between *ongoing* and *unknown* — the ambiguity an
omitted `endDate` creates in every other format.

```json
{ "start": { "value": "2023-04", "precision": "month" },
  "state": "ongoing" }
```

`precision` is `year`, `month` or `day`. `state` is `ongoing`, `ended` or `unknown`.
`state: "ended"` REQUIRES `end`; `state: "ongoing"` FORBIDS it. No times and no zones — resumes do
not have them.

`calendar` and `display` are optional, for Japanese era, Hijri or Bikram Sambat rendering. The stored
`value` stays Gregorian ISO-8601 so it remains computable.

### Provenance

On every claim. The statuses match the bundle's own vocabulary, so `confirmed` means the same thing
in both.

```json
{ "status": "confirmed",
  "asserted": "2026-08-25",
  "source": { "kind": "self", "ref": "sources/interview-2026-03.md" } }
```

`status` is `confirmed`, `inferred`, `needs-verification` or `disputed`.
`source.kind` is `self`, `document`, `system` or `reference`.

### Metric

The type that makes a bullet computable rather than merely searchable.

```json
{ "kind": "delta",
  "subject": "p95 event latency",
  "baseline": { "value": 5, "unit": "min" },
  "quantity": { "value": 1, "unit": "s" },
  "direction": "decrease",
  "confidence": "measured" }
```

`kind` is `absolute`, `delta`, `ratio`, `duration`, `rank` or `count`.
`confidence` is `measured`, `estimated` or `reported`.

The prose stays authored; the metric is its machine mirror. **A validator MUST check that every
numeral appearing in an achievement's `text` also appears in one of its `metrics`.** That single rule
is what stops a rewritten bullet from quietly inflating a number, and it is checkable.

### Achievement

Owned by exactly one parent, globally addressable.

```json
{ "id": "ach_latency",
  "text": "Cut p95 event latency from 5 minutes to under 1 second by ...",
  "metrics": [ ],
  "skills": ["skill_azure"],
  "capabilities": ["ai-platform-architecture"],
  "scope": { "team_size": 6, "users_affected": 40000 },
  "weight": 5,
  "provenance": { } }
```

`weight` is 1-5 evidence strength — the same axis as a Project's `strength` in the bundle.
`capabilities` draws on the vocabulary named in `meta.vocabularies.capabilities`; the standard ships
no taxonomy of its own, because no single capability taxonomy survives contact with every industry.

### Name

Naive `given` / `family` breaks most of the world: two Spanish surnames, an Arabic patronymic chain,
a family-name-first Japanese name, a mononym.

```json
{ "full": "...",
  "given": "...", "family": "...", "additional": ["..."],
  "display_order": "given-first",
  "transliterations": { "ja-Kana": "..." },
  "related_names": [ { "relation": "father", "name": "..." } ] }
```

**`full` is authoritative and MUST NOT be reconstructed from the parts.** `display_order` is
`given-first`, `family-first` or `mononym`. `related_names` exists because Indian resumes routinely
carry a father's or husband's name as a distinct field; it is `private` by default.

### Employment: three levels, not one

This is what fixes promotions and contracting.

```json
"organizations": [
  { "id": "org_acme", "name": "Acme Health", "industry": ["healthcare"] }
],
"engagements": [
  { "id": "eng_1",
    "kind": "employment",
    "organization": "org_acme",
    "employment": { "arrangement": "full-time", "via": null },
    "location": { "city": "Melbourne", "region": "VIC", "country": "AU", "mode": "hybrid" },
    "period": { },
    "positions": [
      { "id": "pos_1", "title": "Member of Technical Staff",
        "functional_title": "Senior Engineer", "period": { } },
      { "id": "pos_2", "title": "Principal Engineer", "period": { }, "change": "promotion" }
    ],
    "achievements": [ ] }
]
```

`kind` is `employment`, `contract`, `freelance`, `internship`, `volunteer`, `break` or
`education-fulltime`. `employment.via` names the agency or umbrella company for a contractor, so
client and payer stop being the same field.

`kind: "break"` is deliberate. A career break becomes a declarable entry with an optional reason
rather than a hole in the chronology that a screener infers something about.

`functional_title` is the bridge for a title that is internal-only, niche, or does not describe the
work — "Member of Technical Staff", "Client Success Associate", any ladder rung that means something
only inside one company. It renders in parentheses **after** `title` on the role line, in both
variants:

```
Member of Technical Staff (Senior Engineer)                          Jun 2025 - Present
```

It never replaces `title`, because `title` is what a reference check confirms. It also never
promotes: the gloss says what the role *was*, so a Senior Engineer does not gain "(Engineering
Manager)". Omit it whenever the official title already reads plainly — most do, and a gloss on
"Senior Engineer" is noise. The resolver drops one that merely repeats the title.

UJD carries `normalized_title` for the same problem on the posting side, but that one *replaces* an
employer's ladder noise with a comparable title for matching. Different operation, different name,
deliberately.

### Grade

Grading scales are not comparable, and one of them runs backwards.

```json
{ "scheme": "in-cgpa-10", "value": 8.4,
  "scale": { "min": 0, "max": 10 },
  "direction": "higher-is-better",
  "label": "First Class with Distinction" }
```

German *Note* is `direction: "lower-is-better"`. A comparator that assumes higher-is-better silently
inverts every German applicant, which is why direction is stored rather than inferred from the
scheme.

`education[].level` uses ISCED codes, so India's 10th and 12th standard results are first-class
entries rather than a footnote to a degree.

### Work authorization

Core, not a profile extension: required in AU, AE, US and most of the Gulf and EU. In the Gulf it is
the first thing screened.

```json
{ "jurisdiction": "AE",
  "kind": "employment-visa",
  "status": "held",
  "transferable": true,
  "expires": { "value": "2027-03", "precision": "month" },
  "visibility": "recruiter" }
```

`kind` is `citizen`, `permanent`, `employment-visa`, `residence`, `student`, `working-holiday` or
`none`. `status` is `held`, `expired`, `eligible` or `requires-sponsorship`.

### Language

With a modality split, because Indian and Gulf resumes list read, write and speak separately.

```json
{ "language": "ar", "scheme": "cefr", "overall": "B2",
  "modalities": { "speak": "B2", "read": "C1", "write": "B1" } }
```

`scheme` is `cefr`, `ilr`, `jlpt`, `ielts` or `self-reported`.

### Skill

No self-rated level. A skill earns its place by pointing at evidence.

```json
{ "id": "skill_azure", "name": "Azure", "category": "cloud-platform",
  "aliases": ["Microsoft Azure", "MS Azure"],
  "identifier": { "scheme": "esco", "code": "..." },
  "evidence": ["ach_latency"],
  "last_used": { "value": "2026", "precision": "year" } }
```

`aliases` does real ATS work: keyword matching is literal, so a renderer can emit the variant a given
portal expects. `identifier` against ESCO or O*NET is what makes the format interoperable rather than
another silo.

## Views — the tailoring model

**This section now lives in `references/view-format.md`.** A view is a rendering instruction: it
selects, orders, redacts and sets a budget. That file defines every key one may carry, including the
normative rule that a view MUST NOT contain content text; this file defines everything a view points
at.

It moved for `jsk-resume-author`, the one agent that writes a view by hand and needs almost nothing
else here — it reads the compiled record rather than this schema. **It was a move, not a copy:** no
view key is defined in this file, and no record key is defined in that one. Do not restate either
half in the other. A specification split across two files that paraphrase each other stops agreeing
the moment one is edited, and the first anyone hears of it is a validator rejecting a document the
other half called legal.

## Region profiles

The core schema is universal and permissive. Everything market-specific lives in a profile, published
as **data rather than spec prose**, so adding a country is a new file and not a schema version.

```json
{ "id": "urs:profile:ae/1",
  "region": "AE",
  "required":  ["person.nationality", "work_authorization", "languages"],
  "expected":  ["person.photo", "person.date_of_birth", "person.marital_status",
                "compensation.expected", "availability.notice_period"],
  "forbidden": [],
  "render": { "pages": 3, "order": "reverse-chronological",
              "attestation_block": false, "referees": "on-request" } }
```

Compare `urs:profile:au/1`, which **forbids** photo, date of birth and marital status, requires
`work_authorization`, renders referees inline, and allows four pages.

The property this buys: **one record, legally correct output in every market.** The photograph and
date of birth expected in Dubai and unlawful to solicit in Sydney both live in the record, gated
`visibility: private`, emitted only where a profile permits.

**The rule that keeps the core from bloating:** a field enters core only if two or more unrelated
markets require it. Everything else is a profile extension under `x`.

A renderer MUST omit any field a profile lists as `forbidden`, MUST warn when a `required` field is
absent, and MUST NOT emit a `private` field unless the profile lists it in `required` or `expected`.

## Privacy

Every field group carries `visibility`: `public`, `recruiter` or `private`. The default for
`person.demographics`, `identity_documents`, `referees`, `compensation` and `related_names` is
`private`. A view opts in explicitly, and only a region profile can justify it.

## Conformance levels

The adoption path. A tool declares what it emits and what it consumes.

| Level | Requires | Reachable from |
|---|---|---|
| **0 — Core** | person, engagements, education; plain-text achievements | mechanical conversion from JSON Resume |
| **1 — Structured** | stable IDs, metrics, skills with evidence | one authoring pass |
| **2 — Verified** | provenance on every claim, views with a `provenance_floor`, validator clean | a maintained bundle |

Level 0 exists so nobody has to rewrite anything to start. A richer format without a zero-cost entry
point is a format nobody adopts.

## Interoperability

Normative bidirectional mappings ship with the standard:

| Format | Direction | Loss |
|---|---|---|
| JSON Resume | to and from Level 0 | lossless inbound; outbound drops metrics, provenance, views |
| HR Open Standards `CandidateProfile` | outbound | what ATS vendors actually speak |
| schema.org `Person` and `Occupation` | outbound | for the public web |
| Europass | to and from | EU public sector |
| LinkedIn export | inbound | the real-world import path |

## Evolution

`urs` carries the version; the major version appears in the `$schema` path. Minor versions are
**additive only**.

**Extensions live under `x`, keyed by reverse DNS.** Every object may carry one. `x` is open, MUST be
ignorable by a tool that does not recognise a key, and **MUST be preserved on round-trip** — a tool
that reads a document and writes it back may not silently drop another tool's extension.

**Everywhere else, an unrecognised key is rejected.** That is the opposite of the usual trade, and
deliberate. A resume is written once and then read by machines its author never sees, so the failure
that actually costs someone an interview is a silent one: `startDate` where the schema says `start`
is an unknown field, it is ignored, and the date disappears from the rendered document with nothing
anywhere reporting it. A rejected typo is a fixed typo. An open object cannot tell a typo from an
extension, which is exactly why extensions are given a place of their own.

## Deliberate exclusions

Time zones · rich text in any field, because renderers own formatting · embedded image binaries, URIs
only · self-rated skill levels · "references available on request" as data rather than a profile
render setting · cover letters.

## Beyond the boundary

Two cases the standard does not claim: **Japan's rirekisho**, a JIS-standardised form that a profile
can only approximate, and **Australian public-sector selection criteria**, accommodated as
`narratives[].kind: "criterion-response"` but a companion document rather than a resume section.
Neither is claimed as supported. `docs/urs-guide.md` states both in full.
