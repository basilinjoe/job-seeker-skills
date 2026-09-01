# Mode: refresh

A periodic pass so nobody has to reconstruct two years from memory.

## Orient first

Read `log.md` for when the last update happened and what was left open, then `open-questions.md`.

For anything more than a quick top-up, send `jsk-bundle-auditor` the bundle path first. It
flags the `headline_metric` values that have gone stale and the questions open across three or more
entries — the two things a refresh exists to catch and the two easiest to miss by reading `log.md`
alone.
Open with something concrete rather than a blank prompt:

> "Last updated in February, and you'd flagged three things as unresolved. Shall we start with what's
> new, then see if any of those are answerable now?"

## What changed

Move fast where nothing happened; this should feel light.

**New work** — shipped, launched, migrated, fixed, rescued. Include unfinished work worth recording.

**Role and scope** — promotion, title, team size, remit, new kinds of responsibility such as
pre-sales, hiring, architecture review, on-call ownership.

**Numbers on existing projects.** The most valuable and most overlooked question. Systems grow — a
platform serving 200 users at launch may serve 5,000 now. Walk recent `projects/` and ask whether any
`headline_metric` has moved. Numbers unavailable last time may exist now.

**Credentials** — certifications passed or started, courses, degrees.

**Recognition** — awards, talks, publications, patents, internal frameworks other teams adopted.

**Things that never reach resumes** — mentoring, interview panels, onboarding material, an internal
tool everyone quietly depends on, a process they changed.

## Close what you can

Walk `open-questions.md`. Some items are now answerable:

```bash
$OKF <noun> set $B --slug <stem> --status confirmed [--<key> <new value>]
$OKF question resolve $B --match "team size" --answer "Six engineers."
```

`question resolve` strikes the row and records the answer in `log.md`. It refuses a match that hits
nothing and a match that hits more than one, so name enough of the question to be unambiguous.

If something has been open across three refreshes, say so and suggest either resolving it properly
or dropping the claim.

## Write it up

**Every write is a command** — never `Write` or `Edit` inside the bundle. `okf <noun> --help` has
the verbs; `references/write-commands.md` has the reasoning.

```bash
OKF="okf"
B="--bundle <bundle>"

$OKF project add    $B --title "…" --role <role-stem> [...]        # new work
$OKF bullet add     $B --project <stem> --text "…"                 # a line it earned
$OKF metric add     $B --name "…" --value "…" --evidence <stem>    # a number that moved
$OKF project set    $B --slug <stem> --strength 5                  # a claim that changed
$OKF role set       $B --slug <stem> --end 2026-06 --state ended   # a job that ended
$OKF project retire $B --slug <stem> --reason "no longer claimed"  # work being dropped
$OKF log            $B --message "Quarterly refresh - what was covered."
```

**A `set` re-stamps `status: inferred`** unless you pass `--status confirmed`. That is the rule doing
its job: a number you updated is a claim they have not yet re-confirmed. Ask, then pass the flag.

If the ladder changed, `profile/career-progression.md` has no command and is still hand-written —
say so rather than working around it.

Then `okf validate <bundle>`, once, at the end.

## Close the loop

Report what was added, resolved, and still open. Then ask whether their **positioning** has shifted —
if they are targeting a different kind of role now, `profile/positioning.md` and the summary variants
need rewriting. A bundle that accumulates evidence but never revisits its target slowly stops
describing the person.

Offer a recurring reminder if they do not have one. Quarterly suits most people; monthly while
actively job-hunting.
