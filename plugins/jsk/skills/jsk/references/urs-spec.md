# URS — Universal Résumé Schema v1

A JSON standard for the career record, from which a resume is rendered.

```
media type   application/resume+json
file         resume.json
written by   the skill, out of user-knowledgebase.md
validated by jsk validate
profiles     schema/profiles/<region>.json
discovery    https://example.com/.well-known/resume.json
```

**The document is the record; a resume is a view over it.** A tailored resume is a *selection*,
expressed as references to IDs, so the renderer cannot invent text. URS maps to JSON Resume at
Level 0 (see *Interoperability*; `docs/urs-guide.md` has the gap table).

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

Only `urs`, `meta`, `person` and `views` are required. An empty career is valid; an ambiguous one is
not.

## Core types

### Instant and Period

```json
{ "start": { "value": "2023-04", "precision": "month" },
  "state": "ongoing" }
```

`precision` is `year`, `month` or `day`. `state` is `ongoing`, `ended` or `unknown`.
`state: "ended"` REQUIRES `end`; `state: "ongoing"` FORBIDS it. No times and no zones.

`calendar` and `display` are optional, for Japanese era, Hijri or Bikram Sambat rendering. The stored
`value` stays Gregorian ISO-8601.

### Provenance

On every claim. The statuses mean the same as in the knowledge base.

```json
{ "status": "confirmed",
  "asserted": "2026-08-25",
  "source": { "kind": "self", "ref": "sources/interview-2026-03.md" } }
```

`status` is `confirmed`, `inferred`, `needs-verification` or `disputed`.
`source.kind` is `self`, `document`, `system` or `reference`.

### Metric

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

**A validator MUST check that every numeral in an achievement's `text` also appears in one of its
`metrics`** — this stops a rewritten bullet inflating a number.

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

`weight` is 1-5 evidence strength — the same axis as a project's `strength` in the knowledge base.
`capabilities` draws on the vocabulary named in `meta.vocabularies.capabilities`; the standard ships
no taxonomy of its own.

### Name

```json
{ "full": "...",
  "given": "...", "family": "...", "additional": ["..."],
  "display_order": "given-first",
  "transliterations": { "ja-Kana": "..." },
  "related_names": [ { "relation": "father", "name": "..." } ] }
```

**`full` is authoritative and MUST NOT be reconstructed from the parts.** `display_order` is
`given-first`, `family-first` or `mononym`. `related_names` (e.g. a father's or husband's name on
Indian resumes) is `private` by default.

### Employment: three levels

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
`education-fulltime`. `employment.via` names the agency or umbrella company for a contractor.
`kind: "break"` declares a career break, with an optional reason.

`functional_title` glosses a title that is internal-only, niche, or does not describe the work. It
renders in parentheses **after** `title` on the role line, in both variants:

```
Member of Technical Staff (Senior Engineer)                          Jun 2025 - Present
```

It never replaces `title` (what a reference check confirms) and never promotes: a Senior Engineer
does not gain "(Engineering Manager)". Omit it when the official title reads plainly; the resolver
drops one that repeats the title. (UJD's `normalized_title` is a different operation: it *replaces*
a posting's title for matching.)

### Grade

```json
{ "scheme": "in-cgpa-10", "value": 8.4,
  "scale": { "min": 0, "max": 10 },
  "direction": "higher-is-better",
  "label": "First Class with Distinction" }
```

`direction` is stored, never inferred from the scheme: German *Note* is `lower-is-better`.
`education[].level` uses ISCED codes, so India's 10th and 12th standard results are first-class
entries.

### Work authorization

Core, not a profile extension.

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

```json
{ "language": "ar", "scheme": "cefr", "overall": "B2",
  "modalities": { "speak": "B2", "read": "C1", "write": "B1" } }
```

`scheme` is `cefr`, `ilr`, `jlpt`, `ielts` or `self-reported`.

### Skill

No self-rated level; a skill points at evidence.

```json
{ "id": "skill_azure", "name": "Azure", "category": "cloud-platform",
  "aliases": ["Microsoft Azure", "MS Azure"],
  "identifier": { "scheme": "esco", "code": "..." },
  "evidence": ["ach_latency"],
  "last_used": { "value": "2026", "precision": "year" } }
```

`aliases` lets a renderer emit the variant a portal's literal keyword match expects. `identifier` is
against ESCO or O*NET.

## Views

Defined in `view-format.md`: every key a view may carry, and the rule that a view MUST NOT contain
content text. No view key is defined here.

## Region profiles

Market-specific rules live in a profile, published as data, so a new country is a new file.

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

`urs:profile:au/1`, by contrast, **forbids** photo, date of birth and marital status, requires
`work_authorization`, renders referees inline, and allows four pages. Fields like photo and date of
birth live in the record gated `visibility: private` and are emitted only where a profile permits.

A field enters core only if two or more unrelated markets require it; everything else is a profile
extension under `x`.

A renderer MUST omit any field a profile lists as `forbidden`, MUST warn when a `required` field is
absent, and MUST NOT emit a `private` field unless the profile lists it in `required` or `expected`.

## Privacy

Every field group carries `visibility`: `public`, `recruiter` or `private`. The default for
`person.demographics`, `identity_documents`, `referees`, `compensation` and `related_names` is
`private`. A view opts in explicitly, and only a region profile can justify it.

## Conformance levels

| Level | Requires | Reachable from |
|---|---|---|
| **0 — Core** | person, engagements, education; plain-text achievements | mechanical conversion from JSON Resume |
| **1 — Structured** | stable IDs, metrics, skills with evidence | one authoring pass |
| **2 — Verified** | provenance on every claim, views with a `provenance_floor`, validator clean | a maintained knowledge base |

## Interoperability

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

**Extensions live under `x`, keyed by reverse DNS.** Every object may carry one. `x` MUST be
ignorable by a tool that does not recognise a key, and **MUST be preserved on round-trip**.

**Everywhere else, an unrecognised key is rejected** — `startDate` where the schema says `start`
would otherwise vanish from the rendered document silently.

## Deliberate exclusions

Time zones · rich text in any field · embedded image binaries (URIs only) · self-rated skill levels
· "references available on request" as data rather than a profile render setting · cover letters.

## Beyond the boundary

Not claimed as supported: **Japan's rirekisho** (a JIS form a profile can only approximate) and
**Australian public-sector selection criteria** (accommodated as
`narratives[].kind: "criterion-response"`, but a companion document). `docs/urs-guide.md` covers
both.
