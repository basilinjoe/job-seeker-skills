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
  resume-generation/    open-questions, plus optional rule overrides: ats-rules ·
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
| 5 | roles and projects declare their relations in frontmatter, so the record compiles rather than being transcribed |
| 6 | the working posting r5 replaced is marked `superseded_by:`, and every live reference points at the posting |

`validate_bundle.py` warns on an older revision and never fails it. `migrate_bundle.py` moves a
bundle forward, reports what it cannot establish, and marks anything it reconstructs
`needs-verification`.

## The record — compiled, not stored

**There is no record file.** `okf_compile.py` builds it from the concepts in under a second and hands
it to whatever asked: the scorer, the validator, the renderer. Every field in it is a frontmatter key
or a table cell, so building it is a mapping rather than a judgement.

It used to be `resume-generation/record.json`, transcribed by a model. Everything heavy in the old
formats hung off that one decision — checksums to notice the transcription drifting, a reconcile pass
to bring it back, conformance levels to say how complete it was, provenance re-asserted per entity
because the transcription had to carry it across. A compile needs none of that: run it again and it is
current by construction.

The bundle is in git, so a resume sent last March rebuilds from the commit it was sent at. That is a
stronger guarantee than a checksum over a copied file, and it costs nothing to keep.

```bash
python3 <skill-dir>/scripts/okf_compile.py <bundle> --dump-record record.json
```

`--dump-record` is for reading, never for editing: the next compile overwrites it. An edit made there
is a claim with no concept behind it.

## Postings on disk

**A posting is a Markdown concept**, `tailoring/targets/<company>-<role>.posting.md`, with the
advertisement verbatim in its body and its requirements in frontmatter — each carrying `value` (the
vocabulary term the ranking runs on), `kind`, `necessity` and the posting's own wording as `label`.

The assessment of that posting against the record sits beside it as `<company>-<role>.gaps.md`, and
the view that renders from it as `<company>-<role>.view.md`. All three are working copies and stay
editable until an application freezes them.

A bundle migrated from an earlier revision also holds the file the posting replaced, under the
bare `<company>-<role>.md`. It is kept — deleting somebody's only copy of an advertisement is not a
trade a migration gets to make — and it carries `superseded_by:` naming the posting that took over.
Nothing reads it. An unmarked one is a validation error, because two documents describing one job
with nothing to say which is live is how a scorer ends up reading the wrong requirements.

Revision 4 made the posting a JSON document because Markdown frontmatter could not say which
requirements were demanded and which were merely preferred. That was true and it is worth one key per
requirement, which is what `necessity` now is. The rest of that document — provenance spans on every
field, boolean requirement groups, a scored assessment with its own arithmetic — was read by nothing
but its own validator. `migrate_bundle.py` converts an older bundle and reports what it could not
recover; archived JSON postings stay readable, because an application that has been sent is frozen.

## Applications on disk

One submission is a **set of files sharing a stem**, all in `tailoring/applications/`. The stem is
`<yyyy-mm-dd>-<company>-<role>`, the date being the day it was sent:

| File | Is |
|---|---|
| `<stem>.md` | the log: what was sent, what was selected, what came back |
| `<stem>.posting.md` | the posting **frozen at submission** |
| `<stem>.gaps.md` | the assessment it was answering, frozen with it |
| `<stem>.view.md` | the view it rendered from |
| `<Name>_<Company>_Resume*.{pdf,tex,txt}` | the files actually sent |

**The date is in the stem because applying twice is ordinary.** A posting is re-advertised, a first
attempt is superseded by a better one, a rejection is followed by a second round a year later. Each
of those is its own submission answering its own assessment, and without the date the second one has
nowhere to go but on top of the first. The target it answers keeps the undated `<company>-<role>`
slug, because there is only ever one live working copy of a job.

**Every input is frozen, not just the view.** The files in `tailoring/targets/` are working copies
and stay editable; the copies beside the application are the archive and do not. An application that
links to a mutable posting cannot answer what it was answering.

The record is not among them, and does not need to be. It compiles from concepts that are in git, so
a resume sent last March rebuilds from the commit it was sent at — a stronger guarantee than a copy
beside the application, which only ever proved what somebody wrote down.

The `Application` concept names both, and the distinction is the point:

```yaml
posting: "<stem>.posting.md"                      # frozen - what was applied against
assessment: "<stem>.gaps.md"                      # frozen - the gaps it answered
target_working_copy: "../targets/<company>-<role>.posting.md"     # editable
view_file: "<stem>.view.md"                       # frozen - what was rendered
company_ref: "../../organisations/<company>.md"
view: view_<id>                                   # the id inside it
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

An extension key, so no validator change was needed to carry it — but it is the field the compiled
record reads, so spell it exactly. `writing-rules.md` has when to reach for it and, more often, when
not to.

### The relational keys

A role also declares who it was for and when. These are what the compile reads to build the
engagement history, and they are required: a role that cannot say who it was for and when cannot be
placed on a resume.

```yaml
type: Role
organisation: experion-technologies   # the Organisation file's stem, not its display name
start: 2019-04                        # 2019, 2019-04 or 2019-04-01 - precision is read from what you write
end: 2021-12                          # omit entirely while state is ongoing
state: ended                          # ended | ongoing | unknown
seniority: team-leadership            # the closed vocabulary Projects already use
change: promotion                     # hire | promotion | lateral | title-change
```

**Roles sharing an `organisation` compile into one engagement**, ordered by `start`, each becoming a
position in its history. That is what puts a promotion on the resume as progression within one
employer rather than as two unrelated jobs, and `change` is what names it.

A Project points at the role it was done under:

```yaml
type: Project
role: lead-software-engineer-experion   # the Role file's stem
```

The body's `**Role:**` link stays — it is how a reader navigates — but the compile reads the key,
because prose can be rephrased and a key cannot.

Before revision 5 all of this lived in prose: tenure under a `# Tenure` heading, the employer
inferable only from the title's suffix, the progression left for a model to work out. Each was a
judgement made during transcription, which is exactly where a resume acquires a fact nobody wrote
down. `migrate_bundle.py` fills them in where it can and names every role it could not place.

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
`Application`

Worth adding as someone's career grows: `Talk` · `Publication` · `Patent` · `Award` · `Reference` ·
`Training Programme` · `Framework` · `Community`.

Reuse these. A near-synonym fragments the graph.

`Job Posting` was called `Job Target` before revision 4, and was a JSON document for one revision
after it. It is a Markdown concept again, with its requirements in frontmatter — see **Postings on
disk** above.

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

## Authored content - bullets and skills

Almost everything in a bundle is a frontmatter key, and the record compiles from it without
anyone transcribing anything. Two things are different: they are *written*. Both live in the
concept they belong to, so a sentence written once is reusable by the next application rather
than stranded in one.

**A project's `# Bullets`** are the resume lines its prose earned:

```markdown
# Bullets

- Cut event propagation from 5 minutes to under 1 second across 15+ integrated applications.
  metric: Event propagation latency
  status: confirmed
```

`metric` names a row in `achievements/metrics.md`. The number lives there once and a bullet
points at it rather than restating it, which is what stops a rewritten clause inflating it -
"cut latency 62%" becoming "by over 60%" becoming "by two thirds". `status` is `confirmed`,
`inferred` or `needs-verification`; anything authored during tailoring arrives `inferred`, and
a view carrying `provenance_floor: confirmed` will not render it until the person has said
otherwise.

**A Skill Set's `# Skills`** are the competencies as a reader should see them:

```markdown
# Skills

- C# / .NET
  id: skill_dotnet
  category: language
  aliases: C#, .NET, ASP.NET Core, LINQ, Entity Framework
```

Deliberately not the same thing as a project's `capabilities` and `technologies`. Those are
matching vocabulary and compare as exact strings, so a synonym silently breaks matching. These
are display names, grouped and aliased by someone with a view about how the block should read.
A view selects from them by id; `ats-maximal` expands them with their aliases.

**A Certification Status concept's `# Held`** are the certifications actually earned:

```markdown
# Held

- Azure Solutions Architect Expert
  issuer: Microsoft
  issued: 2024-05
  status: active
```

**Nothing outside this block becomes a credential.** The type is a *status*, and "none held" is a
legitimate one — a concept recording a certification gap, or listing the ones someone is
considering, compiles to no credentials at all and says so in the compile output. The concept's
own `title` is a document title, never a credential name. A concept about a single certification
may instead carry one `- **Issuer:** <name>` line in its body, and then its title is the
certification.

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
