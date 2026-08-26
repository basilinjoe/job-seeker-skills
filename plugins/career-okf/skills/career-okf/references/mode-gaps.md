# Mode: gaps

Turn unverified and unquantified material into confirmed facts.

## Why it matters

Two failure modes end interviews, both invisible until they happen.

**A vague resume gets screened out.** "Improved system performance" and "cut p95 latency 62%"
describe the same work; one survives a six-second scan.

**An inflated resume collapses under questioning.** A claim they cannot defend costs more than it
gained. This is why `inferred` content is dangerous — it is usually well-written and plausible, which
makes it easy to leave in and hard to defend when someone asks a follow-up.

## Run it

**Scan first, then talk.** Send `career-okf-bundle-auditor` the bundle path; it reads every concept
and returns the gaps already ordered, each with the question written ready to ask. That keeps a
full-bundle read out of the conversation and leaves you the part that needs a person.

Then work **one question at a time**, from that queue and `open-questions.md`. A list of fifteen gets abandoned; one
gets answered.

Order by what unblocks most:

1. **Blocking** — anything stopping a resume going out: an unnamed project, an unresolved contact
   detail, a date conflict
2. **Inferred claims**
3. **Missing metrics**, highest-strength projects first
4. **Unexplored territory**

## For inferred claims

Quote it exactly, say where it came from, offer the exit:

> "On the care-plan project I wrote that policy grounding was there to stop hallucinated guidance
> reaching staff. You described the mechanism but not the reason — I supplied that. Is it right? If
> not, I'll cut the clause."

Confirm, correct, or delete. All three are fine. Leaving it as-is is not.

## For missing metrics

Prompt with where the number might live: monitoring dashboards, APM, cloud billing, sprint retros,
release notes, incident reviews, performance and promotion documents, the original project brief, a
colleague.

If unavailable, take an honest approximation — **"~50 tenants" is worth far more than silence**.
If there is no number at all, make the bullet read as true and complete without one, then drop the
item. A bullet permanently awaiting a metric is a bullet nobody improved.

## For unexplored territory

Most people under-report. Ask about mentoring, interview panels, internal tools other teams adopted,
talks, writing, patents, awards, process changes, cost savings, and work that prevented a problem
rather than fixing one.

## Record and close

Update the concept, set `confirmed`, add numbers to `achievements/metrics.md`, remove from
`open-questions.md`, append to `log.md`, run the validator.

Report what resolved, what is still open, and **which claims should be softened or cut** because no
evidence turned up. That last list is the valuable one — better to lose a bullet now than be asked
about it across a table.

If the resume changed materially, offer to regenerate.
