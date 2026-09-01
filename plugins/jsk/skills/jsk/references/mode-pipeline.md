# Mode: pipeline

What the job search needs from you this week, and recording what has happened since last time.

## Why it matters

A bundle that records only what was *sent* describes the smaller half of a job search. At ten
applications the rest fits in someone's head. At a hundred it does not, and the failures are
mundane: an offer nobody replied to for four days, a recruiter chased twice in one week, a role
still counted as live six weeks after it died.

## Run the script first

```bash
okf pipeline <bundle>
```

It reads every application's timeline and derives the stage, the staleness and the next action.
Nothing is computed by hand, and nothing is stored twice — *the board and the application files
cannot disagree, because the board decided nothing.*

| Flag | For |
|---|---|
| *(none)* | the week: what needs attention, most urgent first |
| `--all` | the full board, closed applications included |
| `--company NAME` | every application to one employer — "have I been here before?" |
| `--as-of DATE` | what the board looked like on a given day |
| `--top N` | rows per block, default 15 — the board is a list of what to do today, not an inventory |
| `--markdown` / `--json` | a table to paste into a file · the whole board, for something else to read |

`--company` is the first thing `mode-tailor.md` runs, before a posting is even written down. It is
cheap, and re-applying to a company mid-search is not.

**Lead with the overdue items**, in your own words. The person does not need the table read out;
they need to know which two things matter today.

## Record what happened

One row per event, appended to the application's `# Timeline`. Never edit an existing row: a
correction is a new row, for the same reason `log.md` records mistakes rather than hiding them.

- **Use the date it happened**, not the date you were told. "They called last Tuesday" is
  last Tuesday.
- **Use the vocabulary** in `framework/pipeline-vocabulary.md`. A synonym is not a small mistake —
  the row stops counting, and the validator rejects it.
- **Fill in `Due` when someone commits to something.** "They'll come back by the 22nd" belongs in
  that column, and it beats the staleness rule in both directions.
- **`follow-up-sent` when they chase.** It does not move the stage but it restarts the clock, which
  is what stops the board nagging about work already done.

## Fill in the backlog, one at a time

After a migration, live applications have a `submitted` row and nothing else — every subsequent
event is in someone's inbox, not the bundle.

Work through them **one at a time**, the way `mode-gaps.md` works `open-questions.md`. A list of
twelve gets abandoned; one gets answered. Start with whatever the board says is most overdue, since
that is where a forgotten event is most likely to be hiding.

Do not reconstruct dates they cannot remember. `unknown` is a legitimate value and an honest one;
a plausible date is indistinguishable from a recorded one, which is the whole problem.

## Name the dead ones

An application with no contact for six weeks is a `no-response`, and saying so is worth more than
leaving it "live" forever — a board full of things that are not really happening is a board people
stop reading.

Offer to close it. Never close it silently: they may know something the bundle does not.

## Companies

When an application is to an employer already in `organisations/`, link it with `company_ref` and
add whoever you learn about to that file's `# People` table — recruiter, referrer, hiring manager.

The application points at the company; **the company does not list its applications.** That list is
derived, so it cannot drift, and `--company` answers it on demand.

If they are applying somewhere they once worked, that is one organisation with
`relationship: both`, not two files.

## Close the loop

Report what moved, what is still waiting, and what you closed. Append to `log.md`, then run
`validate_bundle.py`.

Then say the useful thing: **what the pattern is.** Two rejections in a row for the same missing
capability is a positioning problem, not a resume problem, and it belongs in `open-questions.md`
rather than in another round of applications.
