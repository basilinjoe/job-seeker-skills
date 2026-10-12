# Mode: review

One pass over the career, in order: where the record stands, what has happened since last time, and
what is weak in what is there. It turns unverified and unquantified material into confirmed facts, so
nobody has to reconstruct two years from memory. For new material they bring, use `mode-intake.md`.

`$ARGUMENTS` may name a period ("last quarter") or the workspace; otherwise work forward from the
newest entry, the first `career_log` returns.

Why it matters: a vague resume gets screened out ("improved system performance" vs "cut p95 latency
62%"), and an inflated one collapses under questioning — `inferred` content is dangerous because it
reads well.

A tailoring round asks the same questions about a posting **and** the career, ranked together; its
assessment is a graph the analyst reviews through the tools (`mode-tailor.md`). This file is the
review with no posting in view: `audit.gaps.md`, with **no requirements table and no verdicts**.

## 1. Orient

Start from the record's own state:

```
career_check()                    # the record is clean, and at which revision
career_query(name="open")         # questions not yet answered, oldest first
career_query(name="unconfirmed")  # what is still inferred, with the question on each
career_query(name="stale")        # applications that sent a number since revised
career_query(name="absences")     # each "no" they gave; a due one lapsed a year after it was said
```

`career_log` dates every change; its newest entries say when the last pass happened. Open with
something concrete rather than a blank prompt:

> "Last updated in February, and you'd flagged three things as unresolved. Shall we start with what's
> new, then see if any of those are answerable now?"

Each **due absence** is a question again: "In March last year you said you had never used Kafka —
still true?" Still no: `op:set` its `j:said` to today and `j:answer` to their words, then confirm.
Now yes: `op:retire` it with a `j:reason`, and record the work.

## 2. What happened since

Move fast where nothing happened; this should feel light.

- **New work** — shipped, launched, migrated, fixed, rescued, including unfinished work worth recording.
- **Role and scope** — promotion, title, team size, remit, pre-sales, hiring, architecture review,
  on-call ownership.
- **Numbers on existing projects** — the most valuable and most overlooked question. A platform
  serving 200 users at launch may serve 5,000 now. Walk each live project's headline metric
  (`career_view(section="Metrics")`) and ask whether it has moved.
- **Credentials and recognition** — certifications, courses, degrees, awards, talks, publications,
  patents, internal frameworks other teams adopted.
- **What never reaches resumes** — mentoring, interview panels, onboarding material, an internal tool
  everyone quietly depends on, a process they changed, work that prevented a problem.

Material that is more than a line or two is `mode-intake.md`'s: save it, send the extractor.

## 3. What is weak

**Scan first, then talk.** Send `jsk-kb-auditor` the workspace. It writes `audit.gaps.md` beside
`career/` — the gaps ordered, each with its question ready to ask. It also finds stale headline
metrics and questions open for months. For a quick look without it, the queries above are the queue:
they cannot miss one, and cannot judge one — that is what the auditor is for.

Work **one question at a time**. *A list of fifteen gets abandoned; one gets answered.* Order by what
unblocks most:

1. **Blocking** — no email or phone on `k:person`, an unnamed project, a date conflict
2. **Inferred claims**
3. **Illegible titles** — a job title a reader outside that employer cannot place
4. **Missing metrics**, highest-strength projects first
5. **Unexplored territory** — as in step 2's last two lines

**An inferred claim**: quote it exactly (`career_show(ids=["<id>"])`), say where it came from, offer
the exit:

> "On the care-plan project I wrote that policy grounding was there to stop hallucinated guidance
> reaching staff. You described the mechanism but not the reason — I supplied that. Is it right? If
> not, I'll cut the clause."

Confirm, correct, or cut. Leaving it as-is is not an option.

**An illegible title**: inside the company it was clear, so people rarely notice. Ask plainly:

> "Your title there was Member of Technical Staff. If I showed that line to a hiring manager who has
> never worked at that company, what would they think you did? What would the same job be called
> somewhere else?"

Record the answer as `j:functionalTitle` on the role and leave `j:title` untouched — it is what a
reference check confirms. An answer that is a level up rather than a translation ("really I was doing
staff engineer work") is a claim about scope: it belongs in the evidence, not in a parenthesis. Skip
titles that already read plainly.

**A missing metric**: prompt with where the number might live — monitoring dashboards, APM, cloud
billing, sprint retros, release notes, incident reviews, performance and promotion documents, the
original brief, a colleague. An honest approximation is `j:confidence j:estimated` — **"~50 tenants"
is worth far more than silence**. No number at all → make the bullet read as true and complete
without one.

## 4. Record

One changeset for the session, `career_show(ids)` first for the `op:base`, then `career_preview`
and `career_apply`. Each answer is one of these moves:

| What happened | In the changeset |
|---|---|
| confirmed as it stands | no changeset: `career_confirm(ids=["<id>"], answer="their words")`; it answers the open questions about that entry too |
| corrected, or a new number or title | `op:set` it; it comes back `inferred`, so confirm it with the answer they just gave |
| new work | `op:add` a project with bullets and metrics, as in `mode-intake.md` |
| a number that moved | `op:set` a new `j:value` on its current `k:met_x.vN` — one an application sent is kept, and apply adds the next version |
| a promotion | `op:add` a new `pos_` with `j:change j:promotion`; `op:set` `j:end` and `j:state j:ended` on the previous one |
| a job that ended | `op:set` `j:end` and `j:state j:ended` on that role |
| a "no": they have never done the thing | `op:add { k:abs_kafka j:concept c:kafka ; j:said "<today>"^^xsd:date ; j:answer "their words" . }` (with `@prefix xsd: <http://www.w3.org/2001/XMLSchema#>`), then confirm it with the same words |
| work being dropped, or unavailable | `op:retire` it with a `j:reason` — **never delete it**; or soften the claim — a real outcome, never a question left pending forever |
| a new capability term | `op:add` it under the vocabulary, in the same changeset that first uses it |
| `concepts-bare` in `career_check` | `career_pack(pack="capabilities")`, then its `changeset` through `career_preview` and `career_apply`; then label the top of `career_query(name="bare")` |
| two concepts that are one | re-point any unfrozen posting's `c:a` to `c:b` first (`posting_decide` on its row; `app_drop` an unsent one made from files, once the person agrees), or `c:a` is only retired; `career_merge(concept="c:a", into="c:b")`, then its `changeset` through `career_preview` and `career_apply`; confirm the bullets it lists |

A confirmed "no" answers every posting that asks only that, with no question, for a year; then it is
due and asked again. A project that holds the concept is a WARN: one of the two is stale.

A changed claim comes back `inferred` with a question, by itself — a number updated from memory is
not re-confirmed. **Ask, then `career_confirm(ids=[...], answer="…")`.** An answered question closes
with the confirm; one that cannot be answered means softening or retiring the claim. A career ladder
that changed shape — a new levelling scheme, a title that means something different now — is prose in
`j:positioning`.

## Close

Report what was added, resolved and still open, and **which claims should be softened or cut**
because no evidence turned up — better to lose a bullet now than be asked about it across a table.
Open across three reviews → say so, and suggest resolving it properly or dropping the claim.

Ask whether their **positioning** has shifted: if they are targeting a different kind of role now,
the positioning and the summary variants need rewriting. **End by naming the single biggest gap in
their record** — a named gap can be filled; a compliment cannot. If the resume changed materially,
offer to regenerate it.

Offer a recurring reminder if they do not have one. Quarterly suits most people; monthly while
actively job-hunting.
