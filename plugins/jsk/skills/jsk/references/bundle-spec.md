# Bundle specification

## Layout

```
career/
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
  framework/            capability-vocabulary · schema · concept-types · templates
  resume-generation/    record.json - the standing URS transcription of this bundle -
                        plus open-questions and optional rule overrides: ats-rules ·
                        structure-rules · writing-rules · decisions-log
  tailoring/            selection-method · targets/ · applications/
```

Every directory gets an `index.md` listing its contents. `index.md` and `log.md` are the only
reserved filenames.

## The layout revision

The bundle root's `index.md` carries one extra key:

```yaml
okf_bundle: 3      # layout revision - NOT the plugin version
```

An integer, deliberately not the plugin's semver: the plugin ships releases that do not touch the
on-disk shape, and conflating the two makes every release look like a migration until nobody reads
them. **An absent stamp means revision 1** — every bundle created before the stamp existed has no
way to say so.

| Rev | Shape |
|---|---|
| 1 | applications point at a mutable target file via `target:` |
| 2 | the posting is frozen beside each application as `<stem>.target.md` |
| 3 | an application's outcome is derived from an append-only `# Timeline` |
| 4 | the posting is a UJD document, `<stem>.posting.json`, not Markdown frontmatter |

`validate_bundle.py` warns on an older revision and never fails it. `migrate_bundle.py` moves a
bundle forward, reports what it cannot establish, and marks anything it reconstructs
`needs-verification`.

## The record — `resume-generation/record.json`

**Derived, and never hand-edited.** It is the URS transcription of every concept in this bundle:
organizations, engagements, projects, skills, education, credentials and achievements, each carrying
its concept's `status` across as URS `provenance`. `jsk-record-builder` writes it.

Everything downstream reads it rather than the Markdown — `score_projects.py` ranks over its
`projects[]`, the gap analysis assesses against it and pins it in `subjects.record`, and the author
selects from it. That is the point: when the scorer read the bundle and the assessment read a record,
the two could disagree about what the record held and nothing would have said so.

Because it is derived, an edit made here is a claim with no concept behind it. Edit the concept and
rebuild. It is worth committing anyway — a gap analysis pins it by checksum, so the file is what makes
a past assessment reproducible.

## Postings on disk

**A posting is a UJD document**, `tailoring/targets/<company>-<role>.posting.json`, with the
advertisement verbatim in `source.raw_text` and every requirement carrying its own `kind`,
`necessity` and provenance. `references/ujd-spec.md` has the format; `schema/example.posting.json` is
a worked one.

The gap analysis of that posting against the record sits beside it as `<company>-<role>.gaps.json`,
a UGS document. Both are working copies and stay editable.

Before revision 4 a posting was a Markdown file whose frontmatter carried four flat arrays. That shape
could not say which requirements were required and which were merely preferred, could not express
"a degree and six years, or a postgraduate qualification", and left every gap as prose nobody could
re-check. `migrate_bundle.py` converts an older bundle and reports what it could not recover.

## Applications on disk

One submission is a **set of files sharing a stem**, all in `tailoring/applications/`:

| File | Is |
|---|---|
| `<company>-<role>.md` | the log: what was sent, what was selected, what came back |
| `<company>-<role>.posting.json` | the posting **frozen at submission** |
| `<company>-<role>.gaps.json` | the assessment it was answering, frozen with it |
| `<company>-<role>.resume.json` | the URS record it rendered from |
| `<Name>_<Company>_Resume*.{pdf,tex,txt}` | the files actually sent |

**Every input is frozen, not just the record.** The files in `tailoring/targets/` are working copies
and stay editable; the copies beside the application are the archive and do not. An application that
links to a mutable posting cannot answer what it was answering — and the gap document pins both by
checksum, so a verdict recomputed against an edited posting is caught rather than believed.

The `Application` concept names both, and the distinction is the point:

```yaml
posting: "<company>-<role>.posting.json"          # frozen - what was applied against
assessment: "<company>-<role>.gaps.json"          # frozen - the gaps it answered
target_working_copy: "../targets/<company>-<role>.posting.json"   # editable
record: "<company>-<role>.resume.json"
company_ref: "../../organisations/<company>.md"
view: view_<id>
submitted: 2026-08-26
channel: "Workday portal"
```

Frontmatter carries **only what was true at submission and never changes**. There is no `outcome:`
key: at revision 3 the outcome is derived from the timeline below, because a status word and the
prose beneath it stop agreeing the moment one is edited.

## The application timeline

Appended to, never edited. A correction is a new row, for the same reason `log.md` records mistakes
rather than hiding them.

```markdown
# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-08-26 | submitted | Workday | ATS variant uploaded, presentation copy to the referrer | |
| 2026-09-11 | screen-scheduled | email | Phone screen 2026-09-15, 30 min | 2026-09-15 |
| 2026-09-15 | screen-done | phone | They flagged the Terraform gap, as expected | 2026-09-22 |
```

`Event` values come from `framework/pipeline-vocabulary.md` and compare as exact strings — a synonym
is a row that stops counting, and `validate_bundle.py` rejects it. Dates are `YYYY-MM-DD` or the
literal `unknown`, which is what a migration writes when it could not establish one.

**Stage** is the last advancing event. **Staleness** is measured from the last event that restarts
the clock — which `follow-up-sent` does and `note` does not. `Due` records what somebody promised,
the latest non-empty one wins, and it beats the staleness rule in both directions.

`pipeline.py` derives all of it. Nothing is stored twice.

## Organisations

One file per company, whether they worked there, applied there, or both:

```yaml
type: Organisation
relationship: prospect        # employer | prospect | both
```

The body carries a `# People` table — recruiter, referrer, hiring manager, how you know them, last
contact. Hand-maintained, because it is reference data with low churn rather than a log.

**Linking is one-way.** The application names the company via `company_ref`; the company does not
list its applications. That list is derived — `pipeline.py --company NAME` — so it cannot drift.

## Roles

One file per job title. Where the official title is internal-only, niche, or does not describe the
work, record the bridge beside it rather than editing the title:

```yaml
type: Role
title: "Member of Technical Staff"
functional_title: "Full-Stack Engineer"    # renders in parentheses; never replaces title
```

An extension key, so no validator change was needed to carry it — but it is the field
`resume.json` reads, so spell it exactly. `writing-rules.md` has when to reach for it and, more
often, when not to.

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

Record each value as a Markdown list item in backticks — ``- `data-sovereignty` `` — under a theme
heading. Only list items count as vocabulary; prose and fenced examples are ignored, and while the
file holds none the validator leaves capabilities unchecked rather than rejecting every value.

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

**Bridge a title nobody outside that employer can place.** "Member of Technical Staff
(Full-Stack Engineer)" on the role line. The official title stays first and verbatim — see
`writing-rules.md`, which also says when to leave a title alone.

**Label domains inline on every project.** For one long tenure this is the main defence against
"narrow exposure", and it is free.

**Platform above product.** If they built a platform and something on it, render them adjacent with
"(built on the platform above)". It pre-empts a real doubt about platform architects who never
shipped on their own platform.

**Two pages.** If content outgrows it, compress older roles rather than adding a page.
