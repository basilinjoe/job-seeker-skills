# Mode: pipeline

What the job search needs from you this week, and recording what has happened since last time.

## Why it matters

A record that holds only what was *sent* describes the smaller half of a job search. At ten
applications the rest fits in someone's head. At a hundred it does not, and the failures are mundane:
an offer nobody replied to for four days, a recruiter chased twice in one week, a role still counted
as live six weeks after it died.

## Read the board

There is no command that derives this any more. The board is `applications/`, and reading it is
reading each `application.md`'s `# Timeline`:

```bash
ls <path>/applications/
grep -A 40 "^# Timeline" <path>/applications/*/application.md
```

**Nothing is stored twice.** There is no `outcome:` key and no status word anywhere — the stage is
the last advancing event in the timeline, and it is derived every time somebody asks. A status word
and the prose beneath it stop agreeing the moment one is edited.

Derive four things per application, and nothing else:

| Thing | Is |
|---|---|
| **stage** | the last advancing event — `submitted`, `screen-scheduled`, `onsite-done`, `offer`, `rejected`, `no-response` |
| **staleness** | days since the last event that restarts the clock. `follow-up-sent` does; `note` does not |
| **due** | the latest non-empty `Due` cell. It beats the staleness rule in both directions |
| **live** | no terminal event yet — not `rejected`, `withdrawn`, `no-response`, `offer-declined` |

**Lead with the overdue items**, in your own words, most urgent first. The person does not need the
table read out; they need to know which two things matter today. Cap it at about fifteen rows — this
is a list of what to do today, not an inventory.

"Have I been here before?" is `ls applications/ | grep -i <company>`, and it is the first thing
`mode-tailor.md` runs, before a posting is even written down. It is cheap, and re-applying to a
company mid-search is not.

## Record what happened

One row per event, appended to the application's `# Timeline`. **Never edit an existing row**: a
correction is a new row, for the same reason `## Log` records mistakes rather than hiding them.

- **Use the date it happened**, not the date you were told. "They called last Tuesday" is last
  Tuesday.
- **Use the vocabulary below**, and use it exactly. A synonym is not a small mistake — a row that
  says `phone-screen` where the vocabulary says `screen-done` stops counting, and nothing reports it.
- **Fill in `Due` when someone commits to something.** "They'll come back by the 22nd" belongs in
  that column.
- **`follow-up-sent` when they chase.** It does not move the stage but it restarts the clock, which
  is what stops the board nagging about work already done.

### The event vocabulary

Advancing: `submitted` · `acknowledged` · `screen-scheduled` · `screen-done` ·
`interview-scheduled` · `interview-done` · `onsite-scheduled` · `onsite-done` · `offer` ·
`offer-accepted`

Terminal: `rejected` · `withdrawn` · `no-response` · `offer-declined`

Neither: `follow-up-sent` · `note` · `referral` · `recruiter-contact`

Dates are `YYYY-MM-DD` or the literal `unknown`.

## Fill in the backlog, one at a time

Live applications often have a `submitted` row and nothing else — every subsequent event is in
someone's inbox, not the file.

Work through them **one at a time**, the way `mode-gaps.md` works `## Open questions`. A list of
twelve gets abandoned; one gets answered. Start with whatever looks most overdue, since that is where
a forgotten event is most likely to be hiding.

Do not reconstruct dates they cannot remember. `unknown` is a legitimate value and an honest one; a
plausible date is indistinguishable from a recorded one, which is the whole problem.

## Name the dead ones

An application with no contact for six weeks is a `no-response`, and saying so is worth more than
leaving it "live" forever — a board full of things that are not really happening is a board people
stop reading.

Offer to close it. Never close it silently: they may know something the file does not.

## Companies

When an application is to an employer already in `## Organisations`, point at it by id in the
application's frontmatter, and add whoever you learn about to that organisation's block — recruiter,
referrer, hiring manager, how they know them, last contact.

The application points at the organisation; **the organisation does not list its applications.** That
list is derived, so it cannot drift.

If they are applying somewhere they once worked, that is one organisation with `relationship: both`,
not two entries.

## Close the loop

Report what moved, what is still waiting, and what you closed. Append a row to `## Log`.

Then say the useful thing: **what the pattern is.** Two rejections in a row for the same missing
capability is a positioning problem, not a resume problem, and it belongs in `## Open questions`
rather than in another round of applications.
