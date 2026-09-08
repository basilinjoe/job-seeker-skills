# The knowledge base: one file

`user-knowledgebase.md` is the whole career. Everything a resume is built from lives in it, in a
fixed order, under fixed headings. `jsk new <path> --name "…"` writes it with every heading present
and empty, and the headings are the contract: **never rename one, never reorder them, never add a
top-level one.** A section with nothing in it says `_None recorded yet._` and stays.

```
career/
  user-knowledgebase.md     the whole career - everything below
  applications/
    README.md
    2026-09-08-acme-platform-engineer/
      posting.md            the advertisement, and what it asks for
      gaps.md               the assessment, and the question queue
      resume.json           the URS record this submission rendered from
      application.md        what was sent, through what channel, what came back
      Priya_Raman_Acme_Resume.{tex,pdf,txt}
```

Two things, and the second one is frozen. The knowledge base keeps moving; an application that
pointed at a moving record could not answer what it was answering.

## Why one file

This was a folder of several hundred linked Markdown concepts — a graph, with a compiler over it, a
write command per noun, a query layer to read it back and a migration tool to move it between
layouts. That shape is right for a knowledge base too large to hold in one context. A career is not.

One file changes what the rules have to be. There is no write transaction to make atomic, because a
write to one file either happened or did not. There is no id to resolve across documents, because
everything an id could point at is a heading away. There is no compile, because the reader of this
file is a model that can hold all of it and write the record directly. What is left is a document a
person can open in any editor, read end to end, and correct — which is the property that actually
decides whether a career record survives a year.

What it costs is the guarantees a compiler used to give for free. Those moved to `jsk validate`,
which now checks the record's shape as well as its claims — see `urs-spec.md`.

## Editing it

**Ordinary file tools.** `Read` it, `Edit` it. There is no command layer and no verb per noun; the
refusals a write command used to make are now your own care plus the record gate.

Three habits carry most of the weight the write layer used to:

- **Read before you write.** A section you have not read is a section you are about to duplicate.
- **Search before you add.** People re-tell the same work months apart in different words, and
  neither telling mentions the other. Grep a distinctive phrase first.
- **One edit, one subject.** Adding a project touches the project, its metrics and possibly the
  vocabulary. Make those edits together and log them once.

Append a row to `## Log` after every session. When you find your own earlier mistake, record the
correction rather than editing silently.

## Frontmatter

```yaml
---
kb: 1                    # format revision - an integer, not the plugin's version
name: Priya Raman
updated: 2026-09-08      # the day the last edit landed
---
```

## The sections, in order

| Heading | Holds | Shape |
|---|---|---|
| `## Identity` | name, headline, location, contacts | one `yaml` block |
| `## Positioning` | what they are for, in their own words | prose |
| `## Work authorization and languages` | visas, citizenship, languages | one `yaml` block |
| `## Vocabulary` | capabilities, domains, the fixed seniority list | backticked list items |
| `## Organisations` | one `###` per employer or client | `yaml` block each |
| `## Roles` | one `###` per job title | `yaml` block each |
| `## Projects` | one `###` per engagement or product — **the evidence** | block, prose, bullets |
| `## Metrics` | every verified number, once | one table |
| `## Skills` | display names, grouped and aliased | list items |
| `## Education` | degrees | `yaml` block each |
| `## Certifications` | only what was actually earned | list items |
| `## Open source` | public code | list items |
| `## Open questions` | the gap queue | one table |
| `## Log` | dated, appended to, never edited | one table |

### Identity

The parse gate fails a resume with no email and no phone, so this block is what makes the file able
to render anything sendable at all. It is the first thing to fill in and the most common thing left
empty.

```yaml
full_name: Priya Raman
given_name: Priya
family_name: Raman
headline: Principal Solution Architect
location:
  city: Melbourne
  region: VIC
  country: AU              # ISO 3166-1 alpha-2
  mode: hybrid             # onsite | hybrid | remote
contacts:
  - kind: email
    value: priya.raman@example.com
    primary: true
  - kind: phone
    value: "+61 400 000 000"
  - kind: linkedin
    value: linkedin.com/in/priyaraman
status: confirmed
```

### Vocabulary

The matching axis. Capabilities compare as **exact strings** when a posting is scored against this
file, so a synonym silently breaks matching. Only backticked list items count as vocabulary; prose
and fenced examples are ignored.

```markdown
### Capabilities

- `ai-platform-architecture`
- `data-sovereignty`
```

Add a term here in the same edit that first uses it. A value appearing on three or more projects is
the one safe to claim as a through-line in a summary.

`seniority` is a **closed** vocabulary and the file says so: `architecture-ownership`,
`product-ownership`, `platform-design`, `team-leadership`, `technical-ownership`, `hands-on-senior`,
`hands-on`, `junior`. Do not extend it — the render profiles compare against these eight.

### Organisations and Roles

```markdown
### Meridian Health `org_meridian`

​```yaml
id: org_meridian
relationship: employer      # employer | prospect | both
industry: [healthcare]
size: 1001-5000
status: confirmed
​```
```

```markdown
### Principal Solution Architect - Meridian Health `role_meridian_principal`

​```yaml
id: role_meridian_principal
organisation: org_meridian
title: Principal Solution Architect
functional_title:           # renders in parentheses; never replaces title
start: 2023-07
end:                        # omit while ongoing
state: ongoing              # ended | ongoing | unknown
seniority: architecture-ownership
change: promotion           # hire | promotion | lateral | title-change
status: confirmed
​```
```

**Roles sharing an `organisation` render as one employer block**, ordered by `start`, each a
position in its history. That is what puts a promotion on the resume as progression within one
employer rather than as two unrelated jobs, and `change` is what names it.

Where the official title is internal-only or does not describe the work, record the bridge in
`functional_title` rather than editing the title. `writing-rules.md` has when to reach for it and,
more often, when not to.

### Projects

The evidence, and the only section with three parts.

````markdown
### Clinical event pipeline `proj_clinical_events`

```yaml
id: proj_clinical_events
role: role_meridian_principal
strength: 5                 # 1-5. Evidence quality. 5 = flagship, 1 = filler
recency: 2026
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture, data-sovereignty]
technologies: [azure-ai-foundry, bicep]
headline_metric: metric_event_latency      # or: none-quantified
status: confirmed
```

**The problem.** The legacy scheduler could not express care-plan constraints, so every site
maintained its own spreadsheet beside it.

**What I decided.** Event-sourced the schedule rather than versioning the table, on the argument
that the audit requirement was the real constraint.

**What changed.** Propagation fell from five minutes to under a second across 15 integrated
applications.

**Bullets**

- Cut p95 clinical event latency from 5 minutes to under 1 second across 40,000 daily
  ingestion jobs.
  - metric: metric_event_latency
  - status: confirmed
````

**Bullets are written once and reused.** A sentence written for one application is available to the
next, which is the whole reason they live in the project and not in a resume. A bullet naming a
`metric` points at a row in `## Metrics` rather than restating the figure — that is what stops a
rewritten clause inflating a number: "cut latency 62%" becoming "by over 60%" becoming "by two
thirds".

Anything authored during tailoring arrives `status: inferred`, and a view carrying
`provenance_floor: confirmed` will not render it until the person has said otherwise.

### Metrics

Every verified number, recorded once.

```markdown
| id | subject | baseline | value | unit | direction | confidence | source | status |
|---|---|---|---|---|---|---|---|---|
| metric_event_latency | p95 clinical event latency | 5 | 1 | min→s | decrease | measured | Grafana dashboard | confirmed |
| metric_sites | residential care sites served | | 42 | sites | | measured | platform admin console | confirmed |
```

`confidence` is `measured`, `estimated` or `self-reported`. An estimate is worth recording and worth
labelling; an estimate recorded as measured is worse than no number.

### Skills

Deliberately not the same thing as a project's `capabilities`. Those are matching vocabulary and
compare as exact strings; these are display names, grouped and aliased by someone with a view about
how the block should read. An ATS-maximal render expands each with its aliases.

```markdown
### language

- C# / .NET `skill_dotnet` — aliases: C#, .NET, ASP.NET Core, LINQ, Entity Framework

### cloud-platform

- Azure `skill_azure` — aliases: Microsoft Azure, Azure AI Foundry, Bicep
```

### Certifications

**Nothing outside this section becomes a credential.** "None held" is a legitimate state, and a
section listing certifications somebody is *considering* compiles to no credentials at all.

```markdown
- Azure Solutions Architect Expert `cred_azarch`
  - issuer: Microsoft
  - issued: 2024-05
  - status: active
```

Never invent a credential, or call one "in progress", unless they said so.

### Open questions

The gap queue. Anything `inferred` anywhere above should have a row here until it is confirmed.

```markdown
| id | question | about | asked | answered |
|---|---|---|---|---|
| q_latency_source | Where did the 5-minute baseline come from? | metric_event_latency | 2026-09-08 | |
```

Resolve a row by filling `answered` with the date and writing the answer into the concept it was
about. The row stays — a question that was asked and answered is how the record shows its work.

## Ids

Prefixed, lowercase, underscore-separated: `org_`, `role_`, `proj_`, `metric_`, `skill_`, `cred_`,
`edu_`, `q_`. They appear in the `###` heading in backticks and again as `id:` in the block, because
one is what a reader scans for and the other is what an edit matches on.

An id is written down rather than derived from position, so a later insertion cannot repoint
something that named it. Never renumber; never reuse a retired id.

## Provenance

Every concept carries `status`:

- `confirmed` — they said it, or it is in a source document
- `inferred` — written while drafting; plausible but unverified
- `needs-verification` — a known gap

**Never let `inferred` content reach a resume without asking them to confirm it.** The danger is
precisely that it reads well — plausible, well-written, and indefensible when an interviewer asks a
follow-up. A view with `provenance_floor: confirmed` enforces this at the record gate rather than
relying on anybody's restraint.

## Retiring, not deleting

A concept that no longer belongs on a resume is not deleted. Add `retired: true` to its block and
leave it where it is. The record written from this file skips it; the history stays readable, and a
role that becomes relevant again three years later is one key away.

Delete only a concept that was **wrong** — a duplicate, or something recorded against the wrong
person or employer. Then say so in `## Log`, because a knowledge base that hides its errors cannot
be trusted.

## A bundle from an older version

Bundles from before this format were a directory of concepts. There is no migration tool: the
knowledge base is a document a model writes, so the migration is reading the old bundle and writing
the new file. `mode-setup.md` has the procedure. Keep the old directory until the person confirms
the new file is complete — deleting somebody's only copy of their career is not a trade this
framework gets to make.
