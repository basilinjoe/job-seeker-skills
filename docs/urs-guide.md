# URS, explained

A reading path into the résumé record format, for people rather than parsers. The normative
definition — every type, every field, every MUST — is
[`urs-spec.md`](../plugins/career-okf/skills/career-okf/references/urs-spec.md). Start here, go there
when you need the exact rule.

## The one idea

**The document is the record. A resume is a view over it.**

That inversion is the whole design. You do not write a resume and keep it updated; you keep a record
and render resumes from it. A tailored resume is a *selection* — a list of references to things
already in the record — so a renderer that cannot invent text is a renderer that cannot embellish.

```
media type   application/resume+json
file         *.resume.json
schema       schema/urs-v1.schema.json
profiles     schema/profiles/<region>.json
```

## Why not just use JSON Resume

JSON Resume is a JSON container around unstructured prose, and four gaps follow from that:

| Gap | Consequence |
|---|---|
| A bullet is a bare string in `highlights[]` | Nothing machine-usable. Metrics cannot be verified, ranked or matched — only grepped. |
| No stable identifiers | Nothing can be referenced, diffed or deduplicated. Tailoring means copy-and-mutate, and the copies drift apart permanently. |
| No provenance | "I measured this" and "a model wrote this for me" are indistinguishable in the file. |
| No employer/role model | A promotion becomes two duplicate `work` entries; a contractor cannot express client versus agency. |

URS keeps a **normative bidirectional mapping** to JSON Resume at conformance Level 0, so adopting it
costs nothing and is reversible.

## A walk through a real record

[`schema/example.resume.json`](../plugins/career-okf/skills/career-okf/schema/example.resume.json) is
a complete, valid document. Its top level:

```
$schema · urs · meta          what this file is
person · work_authorization · languages
organizations                 who you worked for
engagements                   what you did there — the evidence
education · credentials · skills · narratives · referees
availability · compensation
views                         the resumes rendered from all of the above
```

### Organizations and engagements are separate

An organization is a company. An engagement is a stretch of time you spent working with one. They are
separate because a contractor works *for* an agency *at* a client, and a single `work` entry cannot
say that.

### A promotion is one engagement with two positions

This is the structure JSON Resume cannot express without duplicating the employer:

```json
"positions": [
  { "title": "Senior Solution Architect",    "change": "hire",      "seniority": "platform-design" },
  { "title": "Principal Solution Architect", "change": "promotion", "seniority": "architecture-ownership" }
]
```

One employer, one continuous period, two titles, and the promotion is visible *as* a promotion. A
renderer can show the progression, and a scorer can see seniority increase over time.

### Every date carries its precision

```json
"period": { "start": { "value": "2021-02", "precision": "month" }, "state": "ongoing" }
```

`state` is a field, so "ongoing" is a stated fact rather than an absent end date. Ambiguity is
illegal in this format: there is no way to write a date and leave the reader guessing whether the
month was unknown or merely omitted.

### An achievement carries its numbers as data

```json
{
  "id": "ach_latency",
  "text": "Cut p95 clinical event latency from 5 minutes to under 1 second...",
  "metrics": [ ... ]
}
```

The `text` is what a resume shows. The `metrics` are what makes it checkable — every numeral in the
text must appear in a metric, or `validate_urs.py` fails the record before anything renders. It is
the check that catches a bullet rewritten for flow with the figure quietly moving too.

The `id` is what makes it selectable. A view points at `ach_latency`; it never copies the sentence.

### A view is a resume

```json
{
  "id": "view_au_default",
  "format_profile": "presentation",
  "region_profile": "urs:profile:au/1",
  "provenance_floor": "confirmed",
  "budget": { "pages": 2 }
}
```

Six lines, and that is an entire resume: which market, which format, how many pages, and — via
`provenance_floor` — a refusal to include anything not yet confirmed.

A view MUST NOT contain content text. That is a schema rule, not a guideline, and it is what makes
"tailoring cannot invent" a structural property rather than a promise.

## Region profiles

A profile decides what a market may and must not see. A photograph and date of birth are conventional
on a Gulf resume and a liability on an Australian one; India expects academic grades on a CGPA scale,
a father's name and a declaration block. The core carries what is true everywhere; everything
market-specific is a profile, so adding a market is a JSON file rather than a schema change.

Australia, India and the UAE ship. The region-neutral default forbids all of it.

## Why an unknown key is rejected

Most formats ignore what they do not recognise. URS rejects it, everywhere except the extension slot.

A resume is written once and then read by machines its author never sees, so the failure that
actually costs someone an interview is a silent one: `startDate` where the schema says `start` is an
unknown field, it is ignored, and the date disappears from the rendered document with nothing
reporting it. **A rejected typo is a fixed typo.**

Extensions get a place of their own — under `x`, keyed by reverse DNS, preserved on round-trip —
precisely because an open object cannot tell a typo from an extension.

## What URS deliberately does not do

Time zones · rich text in any field, because renderers own formatting · embedded image binaries, URIs
only · self-rated skill levels · "references available on request" as data rather than a profile
render setting · cover letters.

## Two things it does not claim to support

Stated plainly rather than implied away:

**Japan's rirekisho** is a JIS-standardised *form* — fixed fields, a photograph at set dimensions,
commute time, dependents, oldest-first ordering, and a companion *shokumu keirekisho*. A profile can
emit an approximation. Claiming URS "supports Japan" would be false.

**Australian public-sector selection criteria** are a distinct genre: several hundred words per
criterion, STAR-structured. Accommodated cheaply as `narratives[].kind: "criterion-response"` with a
criterion reference, but it is a companion document rather than a resume section.

---

Next: [the normative spec](../plugins/career-okf/skills/career-okf/references/urs-spec.md) ·
[Concepts](CONCEPTS.md) · [Why it works this way](WHY.md)
