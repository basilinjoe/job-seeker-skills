# Mode: refresh

A periodic pass so nobody has to reconstruct two years from memory.

## Orient first

If they named a period, cover that. Otherwise start at `log.md` — when the last update happened and
what was left open — work forward from its last row, then read `## Open questions`.

For anything more than a quick top-up, send `jsk-kb-auditor` the file path first. It flags stale
`headline_metric` values and questions open across three or more entries — the two things a refresh
exists to catch and the easiest to miss from the log alone.

Open with something concrete rather than a blank prompt:

> "Last updated in February, and you'd flagged three things as unresolved. Shall we start with what's
> new, then see if any of those are answerable now?"

## What changed

Move fast where nothing happened; this should feel light.

**New work** — shipped, launched, migrated, fixed, rescued. Include unfinished work worth recording.

**Role and scope** — promotion, title, team size, remit, new kinds of responsibility such as
pre-sales, hiring, architecture review, on-call ownership.

**Numbers on existing projects** — the most valuable and most overlooked question. A platform serving
200 users at launch may serve 5,000 now. Walk the recent entries in `## Projects` and ask whether any
`headline_metric` has moved. Numbers unavailable last time may exist now.

**Credentials** — certifications passed or started, courses, degrees.

**Recognition** — awards, talks, publications, patents, internal frameworks other teams adopted.

**Things that never reach resumes** — mentoring, interview panels, onboarding material, an internal
tool everyone quietly depends on, a process they changed.

## Close what you can

Walk `## Open questions`. For each row now answerable: fill the `answered` date, write the answer
into the section it was about, and set that entry's `status` to `confirmed`. The row stays.

Open across three refreshes → say so, and suggest resolving it properly or dropping the claim.

## Write it up

Ordinary `Edit` calls, across the sections that changed:

| What happened | Where it goes |
|---|---|
| new work | a `###` block under `## Projects`, plus any new metric row |
| a number that moved | the existing row in `## Metrics`, and the `updated:` date in frontmatter |
| a promotion | a new `###` under `## Roles`, `change: promotion`, and `end:` + `state: ended` on the previous one |
| a job that ended | `end:` and `state: ended` on that role |
| work being dropped | `retired: true` on the entry — **never delete it** |
| a new capability term | `## Vocabulary`, in the same edit that first uses it |

**Every claim whose substance you change goes back to `inferred`** with a row in `## Open questions`,
unless they confirmed it in this conversation — a number updated from memory is not re-confirmed.
Ask, then mark it `confirmed`. This is the most important habit in this mode.

A career ladder that changed shape — a new levelling scheme, a title that means something different
now — is prose under `## Positioning`.

Append one row to `log.md` and update `updated:` in the frontmatter.

## Close the loop

Report what was added, resolved, and still open. Then ask whether their **positioning** has shifted —
if they are targeting a different kind of role now, `## Positioning` and the summary variants need
rewriting.

Offer a recurring reminder if they do not have one. Quarterly suits most people; monthly while
actively job-hunting.
