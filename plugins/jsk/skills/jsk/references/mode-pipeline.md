# Mode: pipeline

What the job search needs from you this week, and recording what has happened since last time.

If they named a company, "have I been here before?" is `ls applications/ | grep -i <company>` —
also the first thing `mode-tailor.md` runs, before a posting is written down.

## Read the board

The board is every `applications/*/application.ttl`. `jsk freeze` writes each one with its
`submitted` event; everything after that is `jsk event`. **Read the whole board before saying
anything:**

```bash
jsk kb query pipeline      # each application: stage, since, days, due, events
jsk kb query stale         # any that sent a metric since revised
```

There is no `outcome` and no stored status anywhere — the stage is derived from the events every
time, so nothing can disagree with them. The query gives, per application:

| Thing | Is |
|---|---|
| **stage** | the kind of the latest dated event — `submitted`, `screen-scheduled`, `onsite-done`, `offer`, `rejected`, `no-response` |
| **days** | since that event. `follow-up-sent` restarts the clock; `note` does not |
| **due** | a date somebody committed to. It beats the staleness rule in both directions |
| **live** | no terminal event yet — not `rejected`, `withdrawn`, `no-response`, `offer-declined` |

**Lead with the overdue items**, in your own words, most urgent first — the two things that matter
today, not the table read out. Cap it at about fifteen rows.

## Record what happened

One command per event:

```bash
jsk event applications/<dir> screen-scheduled --date 2026-09-11 --channel email --due 2026-09-15 --note "Phone screen, 30 min"
```

**Add-only**: an event is never edited or removed — a correction is a new `note` event.

- **Use the date it happened**, not the date you were told. "They called last Tuesday" is last
  Tuesday.
- **Use the vocabulary below exactly.** A kind outside it is refused, with the nearest suggested.
- **Pass `--due` when someone commits to something.** "They'll come back by the 22nd" is a due date.
- **`follow-up-sent` when they chase.** It does not move the stage but restarts the clock, so the
  board stops nagging about work already done.

An application frozen as `application.md` (not yet migrated) takes one row appended to its
`# Timeline` table instead.

### The event vocabulary

Advancing: `submitted` · `acknowledged` · `screen-scheduled` · `screen-done` ·
`interview-scheduled` · `interview-done` · `onsite-scheduled` · `onsite-done` · `offer` ·
`offer-accepted`

Terminal: `rejected` · `withdrawn` · `no-response` · `offer-declined`

Neither: `follow-up-sent` · `note` · `referral` · `recruiter-contact`

Dates are `YYYY-MM-DD` or the literal `unknown`.

## Fill in the backlog, one at a time

Live applications often have a `submitted` event and nothing else — the later events are in someone's
inbox. Work through them **one at a time**, most overdue first, since that is where a forgotten event
is most likely hiding.

Do not reconstruct dates they cannot remember. `unknown` is honest; a plausible date is
indistinguishable from a recorded one.

## Name the dead ones

No contact for six weeks is a `no-response` — a board full of things not really happening is a board
people stop reading. Offer to close it; never close it silently, since they may know something the
file does not.

## Companies

When an application is to an employer already in the career (`org_`), recruiters, referrers and
hiring managers you learn about go on that organisation as a `j:note`, through `jsk kb apply`.
Applying somewhere they once worked is one organisation with `j:relationship j:both`, not two.

## Close the loop

Report what moved, what is still waiting, and what you closed.

Then name **the pattern.** Two rejections in a row for the same missing capability is a positioning
problem, not a resume problem, and it belongs as a question in the career rather than in another
round of applications.
