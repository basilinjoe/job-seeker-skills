# Bundle specification

## Layout

```
career-okf/
  index.md              navigation, how to use, provenance conventions
  getting-started.md    human entry point
  log.md                chronological history, newest appended
  profile/              identity · positioning · career-progression · communication-preferences
  organisations/        one file per employer
  roles/                one file per job title
  projects/             one file per engagement or product   <- the evidence
  achievements/         metrics.md - every verified number in one place
  skills/               competencies.md - grouped keyword taxonomy
  education/            degrees · certifications
  open-source/          public code, if any
  sources/              archived source documents, interview records
  framework/            schema · concept-types · capability-vocabulary · templates · scripts
  resume-generation/    ats-rules · structure-rules · writing-rules · decisions-log · open-questions
  tailoring/            selection-method · targets/ · applications/
```

Every directory gets an `index.md` listing its contents. `index.md` and `log.md` are the only
reserved filenames.

## Concept file format

```markdown
---
type: Project
title: "Client or product - what it is"
description: "One sentence. Quote the value if it contains a colon."
tags: [domain, key-tech]
timestamp: 2026-01-01T00:00:00Z
status: confirmed
---

# The problem
# What I decided
# What changed
```

`type` is the only key OKF requires. `title`, `description`, `resource`, `tags` and `timestamp` are
recommended. Everything else is an extension key.

**One concept per file.** If you write "and also" about an unrelated thing, that is a second concept.
Split it and link with a relative Markdown link — links are how the graph is traversed.

## Concept types

`Index` · `Log` · `Guide` · `Person` · `Positioning` · `Career Progression` · `Preference` ·
`Organisation` · `Role` · `Project` · `Metric Set` · `Skill Set` · `Education` ·
`Certification Status` · `Open Source` · `Rule Set` · `Method` · `Decision Log` · `Open Questions` ·
`Source Document` · `Source Interview` · `Schema` · `Vocabulary` · `Template` · `Prompt` ·
`Job Target` · `Application`

Worth adding as someone's career grows: `Talk` · `Publication` · `Patent` · `Award` · `Reference` ·
`Training Programme` · `Framework` · `Community`.

Reuse these. A near-synonym fragments the graph.

## Selection keys — Project concepts only

Job matching is only as good as this metadata. Without it, tailoring is guesswork.

```yaml
strength: 5                  # 1-5. Evidence quality. 5 = flagship, 1 = filler
recency: 2026                # year
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture, data-sovereignty]
technologies: [azure-ai-foundry, bicep]
headline_metric: "event latency 5 min to under 1 s"   # or none-quantified
```

`seniority` ∈ `architecture-ownership` · `product-ownership` · `platform-design` ·
`team-leadership` · `technical-ownership` · `hands-on-senior` · `hands-on` · `junior`

`capabilities` is the **primary matching axis** and compares as exact strings, so a synonym silently
breaks matching. Maintain `framework/capability-vocabulary.md` as the canonical list, grouped by
theme. Check it before inventing a value; add new values there in the same edit.

Values appearing on three or more projects are the ones safe to claim as a through-line in a summary.

## Structure rules for rendering

```
Header               name | current title | years | location · phone · email · links
Professional Summary a claim their bullets prove, not a job title restated
Technical Skills     grouped; architecture-level first, then stacks
Professional Experience
Education            + certifications, languages, open source
```

**Recency gets the weight** — roughly 4:1 toward recent roles. Ten years' experience targeting a
senior role earns one or two lines for the first two years.

**Many roles at one employer:** one company block, a single progression line, achievements grouped by
scope era. Repeating the employer six times fragments the page and turns a promotion story into
clutter. (ATS-maximal reverses this — see `ats-rules.md`.)

**Label domains inline on every project.** For one long tenure this is the main defence against
"narrow exposure", and it is free.

**Platform above product.** If they built a platform and something on it, render them adjacent with
"(built on the platform above)". It pre-empts a real doubt about platform architects who never
shipped on their own platform.

**Two pages.** If content outgrows it, compress older roles rather than adding a page.
