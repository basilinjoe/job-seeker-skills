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
  tailoring/            selection-method · targets/ · applications/<yyyy>/
```

Every directory gets an `index.md` listing its contents. `index.md` and `log.md` are the only
reserved filenames.

### Rule overrides declare their scope

`resume-generation/ats-rules.md`, `writing-rules.md` and `structure-rules.md` override the
skill's `references/` defaults of the same name. An override **must say, in its opening
lines, whether it replaces the default or extends it**, because that sentence is what an
agent reads to decide whether to open the default at all:

> **Bundle override — replaces `references/writing-rules.md` entirely.**

> **Bundle override — extends `references/writing-rules.md`.** Its `## Titles` and
> `## Summaries` sections still apply; everything else here wins.

An override that says neither is treated as an extension and both files get read. That is the
safe default and it is also the slow one: a bare "takes precedence" reads like a replacement
and is not one, so a resume silently loses whichever sections the override never covered.
`structure-rules.md` has no skill default, so the question does not arise for it.

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
| 7 | the archive is partitioned by submission year — `tailoring/applications/<yyyy>/` |

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
okf compile <bundle> --dump-record record.json
```

`--dump-record` is for reading, never for editing: the next compile overwrites it. An edit made there
is a claim with no concept behind it. `--view ID` (repeatable) and `--no-views` narrow what is
emitted, and nothing else about the record changes: a bundle retires no working view, so a hundred
answered postings compile to a hundred of them — half the file, in something several agents read on
every run. The default stays every view, because `validate_urs.py <bundle>` checks all of them and a
broken view nobody is rendering today is still a broken view.

`--compact` and `--for score` narrow the same way and are documented in `docs/SCRIPTS.md`: the first
drops the indentation, the second emits projects carrying only the keys a ranking runs on. **None of
the four changes what is true.** They choose how much of the record is written out, never what the
concepts say — a flag that could make a record claim something the bundle does not is a flag this
format has no room for.

**The compile does not read `tailoring/applications/` at all.** The archive is frozen and nothing
downstream compiles from it — the resume that was sent is rebuilt from the commit it was sent at, not
from the copy beside it. Walking it was not merely wasted work: a frozen `<stem>.view.md` declares the
same view id as the live `targets/` copy it was made from, and the archived one shadowed the live one,
so a tailoring run rendered last quarter's selection from this quarter's record and nothing said a
word. *A view compiled from two files is a view nobody chose.* This holds at every revision — an r3
bundle with a flat archive is skipped exactly the same way.

## Postings on disk

**A posting is a Markdown concept**, `tailoring/targets/<company>-<role>.posting.md`, with the
advertisement verbatim in its body and its requirements in frontmatter — each carrying `value` (the
vocabulary term the ranking runs on), `kind`, `necessity` and the posting's own wording as `label`.

The assessment of that posting against the record sits beside it as `<company>-<role>.gaps.md`, and
the view that renders from it as `<company>-<role>.view.md`. All three are working copies and stay
editable until an application freezes them.

**Career content never lives under `tailoring/`.** Those three companions are what the directory
holds, and `validate_bundle.py` enforces them. A Project or a Role belongs in `projects/` or
`roles/`, and one filed here does not reach the record: the compile reads only `*.view.md` under
`tailoring/`, because a posting and an assessment are read by nobody downstream and walking them
cost a hundred-application bundle most of its compile. A concept placed here would compile to
nothing with no gate to say so — the directory is where a job description goes, not where evidence
goes.

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

One submission is a **set of files sharing a stem**, all in one place. The stem is
`<yyyy-mm-dd>-<company>-<role>`, the date being the day it was sent:

| File | Is |
|---|---|
| `<stem>.md` | the log: what was sent, what was selected, what came back |
| `<stem>.posting.md` | the posting **frozen at submission** |
| `<stem>.gaps.md` | the assessment it was answering, frozen with it |
| `<stem>.view.md` | the view it rendered from |
| `<Name>_<Company>_Resume*.{pdf,tex,txt}` | the files actually sent |

At revision 7 that place is `tailoring/applications/<yyyy>/`, the year it was submitted:

```
tailoring/applications/
  index.md                          the year directories
  2025/
    index.md                        that year's applications
    2025-11-03-acme-engineer.md          .posting.md · .gaps.md · .view.md
    Priya_Raman_Acme_Resume.pdf
  2026/
    ...
  undated/                          only where no year could be established
```

Four Markdown files and the documents sent, per submission — and a real search runs to a hundred
submissions. Flat, that is four hundred concepts in one directory plus every PDF ever sent: nothing
can be found by looking, and every tool that walks the archive walks all of it. The year is the
cheapest cut that fixes both.

**The partition is by year, and by nothing else.** The obvious alternative — `open/` and `closed/`,
or an `archived:` flag — puts the outcome in the path, and this specification has already refused to
put it in a key: there is no `outcome:`, *because a status word and the prose beneath it stop
agreeing the moment one is edited*. A directory name is a status word with a rename attached, and it
is wrong from the first rejection nobody filed. Stage is derived from the `# Timeline` and stays derived;
`pipeline.py --all` answers "what is still live" on demand and cannot drift. The submission year is
the opposite kind of fact — immutable, and already the first four characters of the stem — so
partitioning by it stores nothing new that could disagree with anything.

The year comes from the stem. A stem that does not start `<yyyy-mm-dd>-` — an r2-era `kestrel.md` —
falls back to the year of its `submitted:` date; where that is absent, `false` or `unknown`, the file
goes to `undated/` and the migration **says so** rather than guessing a year onto somebody's record.
`undated/` is a legitimate directory to find in a real bundle, not a sign the migration failed: a
year nobody recorded and a year somebody invented look identical a month later, and only one of them
can be corrected. `migrate_bundle.py` writes each year's `index.md` as it files.

The documents actually sent are the awkward case. `<Name>_<Company>_Resume.pdf` is named after the
person and the employer, so it shares no stem with the application it belongs to and no key in the
`Application` concept names it. A migration attributes one by its filename prefix, then by a link in
the application's log, then — where there is only one application it could belong to — to that one,
and leaves anything still unclaimed where it is, reported for hand-filing. A resume filed under the
wrong application is a worse record than one nobody moved.

**A filed application sits one directory deeper than it used to.** Every relative path in it that
leaves its own directory gains exactly one `../` — `target_working_copy`, `company_ref`, and any
Markdown link in the body. The companions sharing its stem are beside it and are unchanged.
`migrate_bundle.py` rewrites them, which is the argument for letting it do the filing.

**The date is in the stem because applying twice is ordinary.** A posting is re-advertised, a first
attempt is superseded by a better one, a rejection is followed by a second round a year later. Each
of those is its own submission answering its own assessment, and without the date the second one has
nowhere to go but on top of the first. The target it answers keeps the undated `<company>-<role>`
slug, because there is only ever one live working copy of a job.

**Every input is frozen, not just the view.** The files in `tailoring/targets/` are working copies
and stay editable; the copies beside the application are the archive and do not. An application that
links to a mutable posting cannot answer what it was answering.

Which is why **`validate_bundle.py` reports a problem in a frozen copy as a warning rather than an
error**. The rule above forbids editing `<stem>.posting.md`, `<stem>.gaps.md`, `<stem>.view.md` and
the r2-era `<stem>.target.md`, so an error in one is a red nobody is permitted to clear — and *a gate
that cannot go green is a gate people stop running*. The application's own `<stem>.md` is still an
error: its `# Timeline` is appended to for as long as the process is live, so what is wrong in it is
something somebody can put right.

The record is not among them, and does not need to be. It compiles from concepts that are in git, so
a resume sent last March rebuilds from the commit it was sent at — a stronger guarantee than a copy
beside the application, which only ever proved what somebody wrote down.

The `Application` concept names both, and the distinction is the point:

```yaml
posting: "<stem>.posting.md"                      # frozen - what was applied against
assessment: "<stem>.gaps.md"                      # frozen - the gaps it answered
target_working_copy: "../../targets/<company>-<role>.posting.md"  # editable
view_file: "<stem>.view.md"                       # frozen - what was rendered
company_ref: "../../../organisations/<company>.md"
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

**An application that was never sent says so.** A posting worked through, rendered and then
held back is a real application with a real timeline, and it has no `submitted` row because
nothing was submitted. Write `submitted: false` in its frontmatter and `validate_bundle.py`
stops asking for the row. That key is the exemption and the only one — a file that says
nothing either way still fails, because there the missing row means nobody finished the
record rather than nobody sent the application, and `submitted:` carrying a date with no row
beneath it fails too, because the two then disagree. Never write a `submitted` row to clear
the error: it trades an accurate red for a false green, and every stage derived from that
timeline afterwards is wrong.

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
