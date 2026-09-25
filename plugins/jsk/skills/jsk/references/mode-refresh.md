# Mode: refresh

A periodic pass so nobody has to reconstruct two years from memory.

## Orient first

If they named a period, cover that. Otherwise start from the record's own state:

```bash
jsk kb check                  # the record is clean, and at which revision
jsk kb query open             # questions not yet answered, oldest first
jsk kb query unconfirmed      # what is still inferred, with the question on each
jsk kb query stale            # applications that sent a number since revised
```

`career/log.ttl` dates every change; its last entries say when the last update happened. For more
than a quick top-up, send `jsk-kb-auditor` the workspace first — it finds stale headline metrics and
questions open for months, the two things a refresh exists to catch.

Open with something concrete rather than a blank prompt:

> "Last updated in February, and you'd flagged three things as unresolved. Shall we start with what's
> new, then see if any of those are answerable now?"

## What changed

Move fast where nothing happened; this should feel light.

**New work** — shipped, launched, migrated, fixed, rescued. Include unfinished work worth recording.

**Role and scope** — promotion, title, team size, remit, new kinds of responsibility such as
pre-sales, hiring, architecture review, on-call ownership.

**Numbers on existing projects** — the most valuable and most overlooked question. A platform serving
200 users at launch may serve 5,000 now. Walk each live project's headline metric
(`jsk kb view --section Metrics`) and ask whether it has moved.

**Credentials** — certifications passed or started, courses, degrees.

**Recognition** — awards, talks, publications, patents, internal frameworks other teams adopted.

**Things that never reach resumes** — mentoring, interview panels, onboarding material, an internal
tool everyone quietly depends on, a process they changed.

## Write it up

One changeset for the session, `jsk kb show <ids>` first for the `op:base`:

| What happened | In the changeset |
|---|---|
| new work | `op:add` a project with bullets and metrics, as in `mode-braindump.md` |
| a number that moved | `op:set` a new `j:value` on its current `k:met_x.vN` — one an application sent is kept, and apply adds the next version |
| a promotion | `op:add` a new `pos_` with `j:change j:promotion`; `op:set` `j:end` and `j:state j:ended` on the previous one |
| a job that ended | `op:set` `j:end` and `j:state j:ended` on that role |
| work being dropped | `op:retire` it with a `j:reason` — **never delete it** |
| a new capability term | `op:add` it under the vocabulary, in the same changeset that first uses it |

A changed claim comes back `inferred` with a question, by itself — a number updated from memory is
not re-confirmed. **Ask, then `jsk kb confirm <ids> --answer "…"`.** An answered question closes
with the confirm; one that cannot be answered means softening or retiring the claim.

A career ladder that changed shape — a new levelling scheme, a title that means something different
now — is prose in `j:positioning`.

Open across three refreshes → say so, and suggest resolving it properly or dropping the claim.

## Close the loop

Report what was added, resolved, and still open. Then ask whether their **positioning** has shifted —
if they are targeting a different kind of role now, the positioning and the summary variants need
rewriting.

Offer a recurring reminder if they do not have one. Quarterly suits most people; monthly while
actively job-hunting.
