# Mode: pipeline

What the job search needs from you this week, and recording what has happened since last time.

If they named a company, "have I been here before?" is `ls applications/ | grep -i <company>` —
also the first thing `mode-tailor.md` runs, before a posting is written down.

## Read the board

The board is `applications/`. `jsk freeze` writes each `application.md` with its `# Timeline`
table; everything after that is rows appended by hand. **Read every timeline before saying
anything:**

```bash
ls <path>/applications/
grep -A 40 "^# Timeline" <path>/applications/*/application.md
```

There is no `outcome:` key and no status word anywhere — the stage is derived from the timeline every
time, so nothing can disagree with the events.

Derive four things per application, and nothing else:

| Thing | Is |
|---|---|
| **stage** | the last advancing event — `submitted`, `screen-scheduled`, `onsite-done`, `offer`, `rejected`, `no-response` |
| **staleness** | days since the last event that restarts the clock. `follow-up-sent` does; `note` does not |
| **due** | the latest non-empty `Due` cell. It beats the staleness rule in both directions |
| **live** | no terminal event yet — not `rejected`, `withdrawn`, `no-response`, `offer-declined` |

**Lead with the overdue items**, in your own words, most urgent first — the two things that matter
today, not the table read out. Cap it at about fifteen rows.

## Record what happened

One row per event, appended to the application's `# Timeline`:

```markdown
| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-09-11 | screen-scheduled | email | Phone screen 2026-09-15, 30 min | 2026-09-15 |
```

**Never edit an existing row**: a correction is a new row.

- **Use the date it happened**, not the date you were told. "They called last Tuesday" is last
  Tuesday.
- **Use the vocabulary below exactly.** A row that says `phone-screen` where the vocabulary says
  `screen-done` stops counting, and nothing reports it.
- **Fill in `Due` when someone commits to something.** "They'll come back by the 22nd" belongs in
  that column.
- **`follow-up-sent` when they chase.** It does not move the stage but restarts the clock, so the
  board stops nagging about work already done.

### The event vocabulary

Advancing: `submitted` · `acknowledged` · `screen-scheduled` · `screen-done` ·
`interview-scheduled` · `interview-done` · `onsite-scheduled` · `onsite-done` · `offer` ·
`offer-accepted`

Terminal: `rejected` · `withdrawn` · `no-response` · `offer-declined`

Neither: `follow-up-sent` · `note` · `referral` · `recruiter-contact`

Dates are `YYYY-MM-DD` or the literal `unknown`.

## Fill in the backlog, one at a time

Live applications often have a `submitted` row and nothing else — the later events are in someone's
inbox. Work through them **one at a time**, most overdue first, since that is where a forgotten event
is most likely hiding.

Do not reconstruct dates they cannot remember. `unknown` is honest; a plausible date is
indistinguishable from a recorded one.

## Name the dead ones

No contact for six weeks is a `no-response` — a board full of things not really happening is a board
people stop reading. Offer to close it; never close it silently, since they may know something the
file does not.

## Companies

When an application is to an employer already in `## Organisations`, point at it by id in the
application's frontmatter, and add whoever you learn about to that organisation's block — recruiter,
referrer, hiring manager, how they know them, last contact.

The application points at the organisation; **the organisation does not list its applications** —
that list is derived.

Applying somewhere they once worked is one organisation with `relationship: both`, not two entries.

## Close the loop

Report what moved, what is still waiting, and what you closed. Append a row to `## Log`.

Then name **the pattern.** Two rejections in a row for the same missing capability is a positioning
problem, not a resume problem, and it belongs in `## Open questions` rather than in another round of
applications.
