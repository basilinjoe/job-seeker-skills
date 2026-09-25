> **Legacy.** This is the format of `user-knowledgebase.md` before the graph record. It is
> kept for one purpose: fixing a Markdown file that `jsk migrate` refuses, so it can be
> migrated. New records are `career/kb.ttl`; their format is
> `plugins/jsk/skills/jsk/references/kb-format.md`. This page goes with `jsk migrate` in release
> 5.0.

# The knowledge base: one file

`user-knowledgebase.md` is the whole career, in a fixed order under fixed headings.
`jsk new <path> --name "…"` writes it with every heading present and empty. The headings are the
contract: **never rename one, never reorder them, never add a top-level one.** An empty section says
`_None recorded yet._` and stays.

```
career/
  user-knowledgebase.md     the whole career - everything below
  log.md                    its history: dated, appended to, never edited
  applications/
    README.md
    2026-09-08-acme-platform-engineer/
      posting.md            the advertisement, and what it asks for
      gaps.md               the assessment, and the question queue
      resume.json           the URS record this submission rendered from
      application.md        what was sent, through what channel, what came back - written by jsk freeze
      Priya_Raman_Resume.{tex,pdf}  Priya_Raman_Resume_ATS.txt
```

The knowledge base keeps moving; an application directory is frozen, so it can always say what it
was answering. `jsk freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--view ID]
[--doc FILE ...]` writes `application.md`; do not create it by hand.

**One edit, one subject.** Adding a project touches the project, its metrics and possibly the
vocabulary — make those edits together and log them once.

## Frontmatter

```yaml
---
kb: 2                    # format revision - an integer, not the plugin's version
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

### Identity

Fill this first: the parse gate fails a resume with no email and no phone.

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

The matching axis. Capabilities compare as **exact strings** against a posting, so a synonym breaks
matching. Only backticked list items count; prose and fenced examples are ignored.

```markdown
### Capabilities

- `ai-platform-architecture`
- `data-sovereignty`
```

Add a term in the same edit that first uses it. A value on three or more projects is safe to claim
as a through-line in a summary.

`seniority` is **closed**: `architecture-ownership`, `product-ownership`, `platform-design`,
`team-leadership`, `technical-ownership`, `hands-on-senior`, `hands-on`, `junior`. Never extend it —
the render profiles compare against these eight.

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

**Roles sharing an `organisation` render as one employer block**, ordered by `start`, so a promotion
reads as progression; `change` names it. For an internal-only title, set `functional_title` rather
than editing `title` (`writing-rules.md` says when).

### Projects

The evidence: a block, prose, and bullets.

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

**Bullets are written once and reused** across applications. A bullet's `metric` points at a row in
`## Metrics` rather than restating the figure, so a rewrite cannot inflate it. Anything authored
during tailoring arrives `status: inferred`; a view with `provenance_floor: confirmed` will not render
it until confirmed.

### Metrics

Every verified number, recorded once.

```markdown
| id | subject | baseline | value | unit | direction | confidence | source | status |
|---|---|---|---|---|---|---|---|---|
| metric_event_latency | p95 clinical event latency | 5 | 1 | min→s | decrease | measured | Grafana dashboard | confirmed |
| metric_sites | residential care sites served | | 42 | sites | | measured | platform admin console | confirmed |
```

`confidence` is `measured`, `estimated` or `self-reported`. Label an estimate as one; never record it
as measured.

### Skills

Display names, grouped and aliased — not a project's `capabilities`, which are matching vocabulary.
An ATS-maximal render expands each with its aliases.

```markdown
### language

- C# / .NET `skill_dotnet` — aliases: C#, .NET, ASP.NET Core, LINQ, Entity Framework

### cloud-platform

- Azure `skill_azure` — aliases: Microsoft Azure, Azure AI Foundry, Bicep
```

### Certifications

**Nothing outside this section becomes a credential.** "None held" is legitimate; certifications
somebody is *considering* do not belong here.

```markdown
- Azure Solutions Architect Expert `cred_azarch`
  - issuer: Microsoft
  - issued: 2024-05
  - status: active
```

### Open questions

The gap queue. Anything `inferred` above has a row here until confirmed.

```markdown
| id | question | about | asked | answered |
|---|---|---|---|---|
| q_latency_source | Where did the 5-minute baseline come from? | metric_event_latency | 2026-09-08 | |
```

Resolve a row by filling `answered` with the date and writing the answer into the entry it was
about. The row stays.

## Ids

Prefixed, lowercase, underscore-separated: `org_`, `role_`, `proj_`, `metric_`, `skill_`, `cred_`,
`edu_`, `q_`. They appear in the `###` heading in backticks and again as `id:` in the block.

Ids are written down, never derived from position. Never renumber; never reuse a retired id.

## Provenance

Every entry carries `status`: `confirmed` (they said it, or a source document does), `inferred`
(written while drafting, unverified), or `needs-verification` (a known gap).

## Retiring, not deleting

An entry that no longer belongs on a resume gets `retired: true` in its block and stays where it is;
the record written from this file skips it.

Delete only an entry that was **wrong** — a duplicate, or recorded against the wrong person or
employer — and say so in `log.md`.

## log.md

The history, in its own file so that nothing reading the career to tailor or author pays for it.
One table, `| date | what changed |`, a row per session rather than per edit. A correction is a
new row, never an edit to an old one.

**A `kb: 1` file still has `## Log` as its last section.** Move the section's table into `log.md`
under a `# Log - <name>` heading, delete the section, set `kb: 2`, and log the move.

## A bundle from an older version

An older bundle is a directory of concepts; migrating is reading it and writing this file.
`mode-setup.md` has the procedure. Keep the old directory until the person confirms the new file is
complete.
