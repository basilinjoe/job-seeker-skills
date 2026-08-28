# Career OKF: tracking a job search, not just its resumes

**Date:** 2026-08-26
**Status:** implemented — see *Outcome* at the end

## Problem

The bundle records what was *sent*. It records nothing about what happened next, and at any real
volume that is the larger half of a job search.

At ten applications this is invisible. At a hundred it is the whole problem:

| Today | At 100 applications |
|---|---|
| `tailoring/applications/index.md` is a hand-maintained table | 100 rows nobody updates reliably — and a drifted index is worse than no index |
| Every question means reading N markdown files | "Which ones have gone quiet?" is 100 file reads |
| `outcome:` is a single frontmatter word | No dates, so "how long has this been sitting?" has no answer |
| `mode-tailor.md` promises *"after a handful of applications, patterns emerge about which evidence gets traction"* | Nothing computes that. It is a promise with no mechanism |
| `organisations/` holds employers the person **worked for** | Companies **applied to** have no home at all |

So this is less a new feature than finishing one the skill already claims.

**The question the design optimises for**, chosen over three alternatives: *what should I do this
week?* Not "what's working" (the learning loop) and not "what did I tell them" (interview recall).
Those are real and are addressed below as consequences, not as goals.

## Constraints

Everything in `ARCHITECTURE.md`'s frozen list still holds. Two apply directly:

- **Bundle layout on disk.** Additions only, behind a revision. `validate_bundle.py` must keep
  *warning* rather than failing on the older shape, or every bundle in existence breaks.
- **The tests assert on output text.** New output lines may be added; existing verdict lines may not
  be reworded.

Three decisions were settled during design and are treated as given here:

1. **Every application is tailored.** The four-part stem (`.md`, `.target.md`, `.resume.json`,
   rendered files) always exists. A bare entry is an error, not a supported shape.
2. **Company records carry people and history only** — recruiter, referrer, hiring manager, and
   prior applications. Not research notes, not salary bands, not interview prep.
3. **Append-only, everything derived.** Rejected: a mutable `stage:` field (throws away the history
   that makes question two answerable later), and a central `tailoring/pipeline.md` board (a second
   source of truth that drifts — the exact failure `mode-resume.md` describes for hand-built
   documents, with a hundred chances to happen).

The chosen shape is the narrow waist the plugin already uses, applied to the pipeline:

```
bundle    -> resume.json     -> documents      (existing)
timeline  -> pipeline state  -> weekly board   (proposed)
```

Same guarantee, same reason: the board and the application files cannot disagree, because the board
decided nothing.

## The data model

### Application frontmatter — immutable facts only

```yaml
type: Application
title: "Kestrel Health - Principal Platform Architect"
company: "Kestrel Health"
company_ref: "../../organisations/kestrel-health.md"
role: "Principal Platform Architect"
posting: "kestrel-health-principal-platform-architect.target.md"
target_working_copy: "../targets/kestrel-health-principal-platform-architect.md"
record: "kestrel-health-principal-platform-architect.resume.json"
view: view_kestrel_principal
submitted: 2026-08-26
channel: "Workday portal"
```

**`outcome:` is removed.** It is derived from the timeline. Keeping it would rebuild the
two-sources-of-truth problem one field at a time, and it is the field most likely to be edited
without the prose beneath it being updated.

`company_ref` is new and points into `organisations/`.

### The timeline — appended to, never edited

```markdown
# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-08-26 | submitted | Workday | ATS variant uploaded, presentation copy to the referrer | |
| 2026-09-02 | recruiter-contact | email | T. Okafor asked for availability; replied same day | |
| 2026-09-11 | screen-scheduled | email | Phone screen 2026-09-15, 30 min | 2026-09-15 |
| 2026-09-15 | screen-done | phone | Went well. They flagged the Terraform gap, as expected | 2026-09-22 |
```

The `Due` column expresses *"they promised to come back on the 22nd"* without a mutable field: a
later row supersedes an earlier one, and what was promised survives in the history. The latest
non-empty `Due` wins, and an explicit `Due` always beats the staleness rule.

### Event vocabulary

Controlled exactly as `capabilities` is, and for the same reason: the script computes stage from
these strings, so a synonym silently breaks it. The canonical list lives in
`framework/pipeline-vocabulary.md`; `validate_bundle.py` rejects values absent from it.

That file is **seeded with the full vocabulary**, unlike `capability-vocabulary.md` which starts
empty and grows with the person. The distinction matters: capabilities describe someone's work and
are theirs to extend, while these describe a process the script has to reason about. `init_bundle.py`
writes it at creation and the r3 migration writes it for existing bundles. Absent, the validator
leaves events unchecked rather than rejecting all of them — the same fallback `capabilities` uses.

Two independent attributes, which is the part worth getting right:

| Event | Advances stage | Resets the clock |
|---|---|---|
| `submitted` `acknowledged` `recruiter-contact` `screen-scheduled` `screen-done` `task-issued` `task-submitted` `interview-scheduled` `interview-done` `offer` | yes | yes |
| `accepted` `declined` `rejected` `withdrawn` `no-response` | terminal | n/a |
| `follow-up-sent` | no | **yes** |
| `note` | no | no |

`follow-up-sent` resetting the clock is not a detail. Without it, chasing someone on Monday gets you
told to chase them again on Tuesday, and a report that nags about work already done is a report
people stop opening. `note` deliberately does not reset it: writing something down is not contact.

**Stage** = the last advancing event. **Staleness** = days since the last clock-resetting event.

### Staleness rules

Defaults, overridable at `resume-generation/pipeline-rules.md` — consistent with *"a bundle's own
rules win"*:

| Stage | Chase after |
|---|---|
| `submitted`, `acknowledged` | 14 days |
| `recruiter-contact` | 5 days |
| `screen-done`, `interview-done`, `task-submitted` | 7 days |
| `screen-scheduled`, `interview-scheduled`, `task-issued` | see below — the `Due` date governs |
| `offer` | 2 days — you owe *them*. **Advancing, not terminal**: an offer is a stage you are in, and closing the application there would silence the board at the one moment a deadline matters. What ends a pipeline is the answer to the offer |

**Scheduled stages are governed by `Due`, not by elapsed time.** Something booked for next
Thursday is not stale on Wednesday. Three cases, and all three need stating or the report guesses:

| Situation | Treatment |
|---|---|
| `Due` in the future | `WAITING`, shown with the date. Never chased |
| `Due` today or past, no later row | `NEEDS YOU` — the thing was scheduled and nothing was recorded after it |
| No `Due` at all | Falls back to 14 days from the event, and the report says `no date recorded` so the omission is visible rather than silently forgiving |

### Organisation, widened

`organisations/` currently means "one file per employer". It widens rather than gaining a parallel
directory, because a company someone worked at *and* is now applying to is one company:

```yaml
type: Organisation
title: "Kestrel Health"
relationship: prospect        # employer | prospect | both
industry: [healthcare, aged-care]
```

The body carries a `# People` table — name, role, how you know them, contact, last contact.
Hand-maintained: it is reference data with low churn, not a log.

**Linking is one-way.** The application names the company; the company does not list its
applications. That list is derived, so it cannot drift, and "have I burned this one already?" is a
query rather than a maintained table.

No per-recruiter `Person` files. Two hundred files to answer a question a table answers is not a
better graph, just a bigger one.

## `pipeline.py`

The eleventh script, and the only new tool this design adds.

```bash
python3 pipeline.py <bundle> [--as-of DATE] [--all] [--company NAME] [--markdown]
```

| Flag | Does |
|---|---|
| *(none)* | the week: everything needing attention, most urgent first |
| `--all` | the full board, terminal applications included |
| `--company NAME` | every application, outcome and contact for one company |
| `--as-of DATE` | compute against a given date rather than today |
| `--markdown` | emit as a table, to paste into a file |

`--as-of` exists for two reasons: deterministic tests, and answering "what did this look like when I
last checked". A report whose output depends on an unstated clock cannot be tested and cannot be
compared with itself.

Output follows house style — columns, then a count line:

```
pipeline.py   bundle: ~/career-okf   as of 2026-09-18

NEEDS YOU (3)
  overdue 9d    Kestrel Health         Principal Platform Architect   screen-done   follow up
  due today     Harbourline Insurance  Solution Architect             offer         respond - you owe them
  overdue 3d    Northwind Care         Lead Architect                 submitted     chase or close

WAITING (7)
  4d            Ardent Systems         Platform Architect             submitted     chase in 10d
  ...

CLOSED (12)   offer 1 | rejected 9 | withdrawn 1 | no-response 1

ACTION 3 | LIVE 10 | CLOSED 12
```

**Exit codes:** `0` nothing needs attention, `1` something does, `2` called wrong. The `1` is
deliberate and matches `migrate_bundle.py`'s dry run: it makes the command usable as a scheduled
check without writing anything.

Standard library plus `pyyaml` (it reads bundle frontmatter, like `validate_bundle.py` and
`score_projects.py`). Timeline tables are parsed line-wise; nothing is rewritten.

## Mode and command

`references/mode-pipeline.md`, routed from `SKILL.md`, with `/jsk:pipeline` as the slash
command and `okf pipeline` as the shell entry point — forwarded like every other subcommand, with the
same arguments and the same exit code.

The script answers *what needs attention*. The mode does the part a script cannot:

1. **Run the script first**, show the board, and lead with the overdue items.
2. **Append what they tell you** — one event per thing that happened, in the controlled vocabulary,
   with the date it happened rather than the date you were told.
3. **Work the backlog one at a time.** After an r3 migration, live applications have a `submitted`
   row and nothing else. That is the same shape as `open-questions.md`, and it gets the same
   treatment: one question, answered, recorded, next. A list of twelve gets abandoned.
4. **Name the ones that are dead.** An application with no contact in six weeks is a `no-response`,
   and saying so is more useful than leaving it "live" forever. Offer to close it; never close it
   silently.
5. **Append to `log.md`** as every mode does.

**No new agent.** The script does the reading, which is what an agent would have been for. Filling in
history is a conversation and belongs in the main thread. Revisit if the learning loop lands, since
*that* is a cross-file analysis with a compact answer.

## Migration: r3

`migrate_bundle.py` gains one step, following the rules r2 established.

| Change | Mechanical? |
|---|---|
| `framework/pipeline-vocabulary.md` seeded | yes |
| `relationship: employer` on existing organisations | yes — that is what they are |
| `submitted:` → the first timeline row | yes |
| `outcome: <terminal>` → a terminal timeline row | **the date is unknown** |
| `outcome:` retained, marked deprecated, for one revision | yes |

The outcome date is the honest gap. `outcome: rejected-after-interview` records *what* happened, not
*when*. The migration reads the `# Outcome` prose for a date (`"Rejected after first interview,
2026-07-02"` is findable) and, failing that, writes `unknown` with `[reconstructed at migration]` in
the note.

**That loss lands in the right place.** Terminal applications are closed, so a fuzzy date cannot
affect "what should I do this week" at all. It degrades only time-in-stage analysis — the secondary
use case — which is where the cost belongs.

Live applications get a `submitted` row and nothing else, and are **listed for a person** rather than
guessed at:

```
12 live applications have no timeline beyond submission.
Run /jsk:pipeline to fill them in - one at a time.
```

## Validation

`validate_bundle.py` gains checks that apply **only at revision 3 or above**, so no existing bundle
starts failing:

| Check | Severity |
|---|---|
| An `Application` has a `# Timeline` with a `submitted` row | ERROR |
| Every `Event` value is in `framework/pipeline-vocabulary.md` | ERROR |
| Every `Date` parses | ERROR |
| Rows are non-decreasing by date | WARNING — backfilling legitimately arrives out of order |
| An advancing event follows a terminal one | WARNING — usually a reopened process, occasionally a mistake |
| `company_ref` resolves | ERROR (existing broken-link rule covers it) |

## Testing

`tests/test_pipeline.py`, following the house pattern — temp bundles, no fixtures committed:

- stage derivation from the last advancing event, ignoring `note` and `follow-up-sent`
- `follow-up-sent` resets the clock and `note` does not — the regression most likely to be
  reintroduced, and the one users would feel first
- explicit `Due` beats the stage rule; the latest non-empty `Due` wins
- terminal applications never appear in `NEEDS YOU`
- `--as-of` makes output deterministic; the same bundle on two dates differs predictably
- unknown dates from a migration do not crash the report and do not produce a chase
- exit codes: 0 with nothing due, 1 with something due, 2 on a bad path
- `--company` returns every application for one company, closed ones included
- an r2 bundle still validates after the r3 checks exist

## Out of scope

Deliberately, and each for a reason:

- **Interview prep notes on companies.** Scoped out at design time; it would let the company file
  grow unboundedly and it serves a different question.
- **Email or calendar import.** The bundle is a folder of Markdown that outlives any tool. A parser
  for someone's inbox is a different product with a different lifetime.
- **Reminders and notifications.** The script exits 1 when something is due; anything that wants to
  nag can call it. Building a scheduler inside a career bundle is not the job.
- **Salary and compensation tracking.** Real, but it belongs with `compensation` in the URS record.
- **The learning loop** — which evidence gets traction, which gaps keep costing interviews.
  **Deferred, not abandoned.** It is the reason the timeline is append-only: outcomes joined to stage
  transitions is a reporting change on this data model, and would have been a redesign on a mutable
  `stage:` field.

## Verification

- `pipeline.py` reproduces a known board from a fixture bundle under `--as-of`
- an r2 bundle migrates to r3, still validates, and reports a coherent board
- the full suite passes; no existing verdict line is reworded
- `preflight.py` counts the new script
- `okf pipeline` forwards with the same arguments and exit code

## Outcome

Implemented 2026-08-26, as designed, with three changes made during the build:

- **`pipeline_model.py` was added.** The spec described `pipeline.py`, `validate_bundle.py` and
  `migrate_bundle.py` each dealing with timelines; that is three places deciding what an event means,
  and two of them would eventually disagree about someone's job search. One module owns it and the
  other three read it.
- **Three migration tests were rewritten rather than added to.** `test_index_is_stamped` asserted
  `okf_bundle: 2` and now reads `CURRENT_REVISION` from the script, so r4 will not edit it. Two
  others asserted an exit code or a blocker count that r3 legitimately changed — both now assert the
  message they actually care about.
- **`offer` was moved from terminal to advancing.** The spec contradicted itself: the event table
  listed `offer` as terminal while the staleness table gave it a two-day chase. Following the first
  made the second unreachable, and a demo board showed the consequence — an offer with a passed `Due`
  sitting quietly under CLOSED. An offer is a stage you are in; what ends a pipeline is the answer to
  it, so `accepted` and `declined` were added and the migration maps an old `outcome: offer` to a
  live `offer` row rather than guessing how it ended.
- **`--markdown` covers the board only**, not `--company`. The company query is a different shape and
  a table of it answers a question nobody asked.

296 tests pass, up from 257. No existing verdict line was reworded.
