# Mode: gaps

Turn unverified and unquantified material into confirmed facts.

## Two entry points, one format

| Entry | Subject | Asks about |
|---|---|---|
| `/jsk:gaps` — a record audit | the career, no posting in view | record quality: unconfirmed claims, missing metrics, illegible titles, unexplored territory |
| A tailoring round — see `mode-tailor.md` | a posting **and** the career | both, ranked together: what this posting wants that the record cannot answer, alongside the record-quality problems that would reach *this* resume |

A tailoring round's assessment is a graph the analyst reviews through the tools; the audit's is
`audit.gaps.md`. This file is the record audit's conversation.

Why it matters: a vague resume gets screened out ("improved system performance" vs "cut p95 latency
62%"), and an inflated one collapses under questioning — `inferred` content is dangerous because it
reads well.

## Run it

**Scan first, then talk.** Send `jsk-kb-auditor` the workspace. It writes `audit.gaps.md` beside
`career/` — the gaps ordered, each with its question ready to ask.

For a quick look without spawning anything, the queue is two queries:

```
career_query(name="unconfirmed")  # every entry not confirmed, with its open question
career_query(name="open")         # every question not yet answered
career_query(name="absences")     # each "no" they gave; a due one is asked again
```

They cannot miss one, and cannot judge one — that is what the auditor is for.

A record audit carries `purpose: self-assessment` and **no requirements table and no verdicts** —
there is no posting to judge against. Questions are the whole document.

Then work **one question at a time**. *A list of fifteen gets abandoned; one gets answered.* (A
tailoring round asks its whole queue at once because it is bounded; an audit is not.)

Order by what unblocks most:

1. **Blocking** — anything stopping a resume going out: no email or phone on `k:person`, an unnamed
   project, a date conflict
2. **Inferred claims**
3. **Illegible titles** — a job title a reader outside that employer cannot place
4. **Missing metrics**, highest-strength projects first
5. **Unexplored territory**

`unmet-requirement` is the tailoring loop's priority and has no meaning here.

## For inferred claims

Quote it exactly (`career_show(ids=["<id>"])`), say where it came from, offer the exit:

> "On the care-plan project I wrote that policy grounding was there to stop hallucinated guidance
> reaching staff. You described the mechanism but not the reason — I supplied that. Is it right? If
> not, I'll cut the clause."

Confirm, correct, or cut. Leaving it as-is is not an option.

## For illegible titles

Inside the company the title was clear, so people rarely notice. Ask plainly:

> "Your title there was Member of Technical Staff. If I showed that line to a hiring manager who has
> never worked at that company, what would they think you did? What would the same job be called
> somewhere else?"

Record the answer as `j:functionalTitle` on the role and leave `j:title` untouched — it is what a
reference check confirms. An answer that is a level up rather than a translation ("really I was
doing staff engineer work") is a claim about scope: it belongs in the evidence, not in a
parenthesis. Skip titles that already read plainly.

## For missing metrics

Prompt with where the number might live: monitoring dashboards, APM, cloud billing, sprint retros,
release notes, incident reviews, performance and promotion documents, the original project brief, a
colleague.

If unavailable, take an honest approximation and record it as `j:confidence j:estimated` — **"~50
tenants" is worth far more than silence**. No number at all → make the bullet read as true and
complete without one.

## For unexplored territory

Ask about mentoring, interview panels, internal tools other teams adopted, talks, writing, patents,
awards, process changes, cost savings, and work that prevented a problem rather than fixing one.

## Record and close

Each answer is one of four moves (`career_confirm`, `career_apply`, `career_show`):

- **Confirmed as it stands**: `career_confirm(ids=["<id>"], answer="their words")`. It answers the open
  questions about that entry too.
- **Corrected, or a new number or title**: a changeset through `career_apply` (`career_show` first
  for the `op:base`). It comes back `inferred`; confirm it with the answer they just gave.
- **A "no"** — they have never done the thing ("never used Kafka"): `op:add { k:abs_kafka
  j:concept c:kafka ; j:said "<today>"^^xsd:date ; j:answer "their words" . }` (with
  `@prefix xsd: <http://www.w3.org/2001/XMLSchema#>`), then confirm it with the same words.
  Confirmed, it answers every posting that asks only that, with no question, for a year; then it
  is due (`career_query(name="absences")`) and asked again. A project that holds the concept is a WARN:
  one of the two is stale.
- **Unavailable**: soften the claim in a changeset, or `op:retire` it with a `j:reason` — a real
  outcome, never a question left pending forever.

Report what resolved, what is still open, and **which claims should be softened or cut** because no
evidence turned up — better to lose a bullet now than be asked about it across a table. **End by
naming the single biggest gap in their record** — a named gap can be filled; a compliment cannot.

If the resume changed materially, offer to regenerate.
