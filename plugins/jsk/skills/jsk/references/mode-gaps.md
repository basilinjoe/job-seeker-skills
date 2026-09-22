# Mode: gaps

Turn unverified and unquantified material into confirmed facts.

## Two entry points, one format

| Entry | Subject | Asks about |
|---|---|---|
| `/jsk:gaps` — a record audit | the knowledge base, no posting in view | record quality: unconfirmed claims, missing metrics, illegible titles, unexplored territory |
| A tailoring round — see `mode-tailor.md` | a posting **and** the knowledge base | both, ranked together: what this posting wants that the record cannot answer, alongside the record-quality problems that would reach *this* resume |

Both write the same Markdown assessment (`agents/jsk-tailor-analyst.md` has the format). This file is
the record audit's conversation.

Why it matters: a vague resume gets screened out ("improved system performance" vs "cut p95 latency
62%"), and an inflated one collapses under questioning — `inferred` content is dangerous because it
reads well.

## Run it

**Scan first, then talk.** Send `jsk-kb-auditor` the knowledge base path. It writes `audit.gaps.md`
beside it — the gaps ordered, each with its question ready to ask.

For a quick look without spawning anything, the queue is two greps:

```bash
grep -n "status: inferred\|status: needs-verification" <path>/user-knowledgebase.md
sed -n '/^## Open questions/,/^## Log/p' <path>/user-knowledgebase.md
```

They cannot miss one, and cannot judge one — that is what the auditor is for.

A record audit carries `purpose: self-assessment` and **no requirements table and no verdicts** —
there is no posting to judge against. Questions are the whole document.

Then work **one question at a time**. *A list of fifteen gets abandoned; one gets answered.* (A
tailoring round asks its whole queue at once because it is bounded; an audit is not.)

Order by what unblocks most:

1. **Blocking** — anything stopping a resume going out: an empty `## Identity` block, an unnamed
   project, a date conflict
2. **Inferred claims**
3. **Illegible titles** — a job title a reader outside that employer cannot place
4. **Missing metrics**, highest-strength projects first
5. **Unexplored territory**

`unmet-requirement` is the tailoring loop's priority and has no meaning here.

## For inferred claims

Quote it exactly, say where it came from, offer the exit:

> "On the care-plan project I wrote that policy grounding was there to stop hallucinated guidance
> reaching staff. You described the mechanism but not the reason — I supplied that. Is it right? If
> not, I'll cut the clause."

Confirm, correct, or delete. Leaving it as-is is not an option.

## For illegible titles

Inside the company the title was clear, so people rarely notice. Ask plainly:

> "Your title there was Member of Technical Staff. If I showed that line to a hiring manager who has
> never worked at that company, what would they think you did? What would the same job be called
> somewhere else?"

Record the answer as `functional_title` on the role and leave the official `title` untouched — it is
what a reference check confirms. An answer that is a level up rather than a translation ("really I
was doing staff engineer work") is a claim about scope: it belongs in the evidence, not in a
parenthesis. Skip titles that already read plainly.

## For missing metrics

Prompt with where the number might live: monitoring dashboards, APM, cloud billing, sprint retros,
release notes, incident reviews, performance and promotion documents, the original project brief, a
colleague.

If unavailable, take an honest approximation and record it as `confidence: estimated` — **"~50
tenants" is worth far more than silence**. No number at all → make the bullet read as true and
complete without one, then close the question.

## For unexplored territory

Ask about mentoring, interview panels, internal tools other teams adopted, talks, writing, patents,
awards, process changes, cost savings, and work that prevented a problem rather than fixing one.

## Record and close

Ordinary `Edit` calls into `user-knowledgebase.md` — the only place to write. Each answer touches two
places:

1. **The section it was about** — the metrics row, the bullet, the role's `functional_title`, the
   project's block. Set its `status` to `confirmed`.
2. **`## Open questions`** — fill the `answered` date on that row. Leave the row.

**Unavailable is a real outcome**: a metric nobody can reconstruct closes the question and should
soften or cut the claim rather than leave it pending forever.

Then append one row to `## Log`, and update `updated:` in the frontmatter.

Report what resolved, what is still open, and **which claims should be softened or cut** because no
evidence turned up — better to lose a bullet now than be asked about it across a table. **End by
naming the single biggest gap in their record** — a named gap can be filled; a compliment cannot.

If the resume changed materially, offer to regenerate.
