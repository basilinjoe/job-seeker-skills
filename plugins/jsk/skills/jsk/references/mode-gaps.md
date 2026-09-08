# Mode: gaps

Turn unverified and unquantified material into confirmed facts.

## Two entry points, one format

| Entry | Subject | Asks about |
|---|---|---|
| `/jsk:gaps` — a record audit | the knowledge base, no posting in view | record quality: unconfirmed claims, missing metrics, illegible titles, unexplored territory |
| A tailoring round — see `mode-tailor.md` | a posting **and** the knowledge base | both, ranked together: what this posting wants that the record cannot answer, alongside the record-quality problems that would reach *this* resume |

Both write the same Markdown assessment, so the questions have the same shape, the same priorities
and the same resolutions wherever they came from. `agents/jsk-tailor-analyst.md` has the format. This
file is the conversation.

The rest of this file is the record audit. The tailoring round is in `mode-tailor.md`.

## Why it matters

Two failure modes end interviews, both invisible until they happen.

**A vague resume gets screened out.** "Improved system performance" and "cut p95 latency 62%"
describe the same work; one survives a six-second scan.

**An inflated resume collapses under questioning.** A claim they cannot defend costs more than it
gained. This is why `inferred` content is dangerous — it is usually well-written and plausible, which
makes it easy to leave in and hard to defend when someone asks a follow-up.

## Run it

**Scan first, then talk.** Send `jsk-kb-auditor` the knowledge base path. It writes `audit.gaps.md`
beside it — the gaps already ordered, each with the question written ready to ask. That keeps a full
read out of the conversation and leaves you the part that needs a person.

For a quick look without spawning anything, the queue is two greps:

```bash
grep -n "status: inferred\|status: needs-verification" <path>/user-knowledgebase.md
sed -n '/^## Open questions/,/^## Log/p' <path>/user-knowledgebase.md
```

Those are derived from the file, so they cannot miss one — and they cannot judge one either, which is
why the auditor still exists.

A record audit carries `purpose: self-assessment` and **no requirements table and no verdicts**. A
verdict is a judgement against something a posting asked for, and there is no posting here — nothing
is being applied to. Questions are the whole document.

Then work **one question at a time**. *A list of fifteen gets abandoned; one gets answered.*

This is the one place that rule still holds unchanged. A record audit is open-ended and has no natural
end, so a long list is a list nobody finishes. A tailoring round is bounded and every question names
the requirement it would close, which is why it asks the whole queue at once instead.

Order by what unblocks most:

1. **Blocking** — anything stopping a resume going out: an empty `## Identity` block, an unnamed
   project, a date conflict
2. **Inferred claims**
3. **Illegible titles** — a job title a reader outside that employer cannot place
4. **Missing metrics**, highest-strength projects first
5. **Unexplored territory**

`unmet-requirement` is the tailoring loop's priority and has no meaning here — nothing is being
applied to.

## For inferred claims

Quote it exactly, say where it came from, offer the exit:

> "On the care-plan project I wrote that policy grounding was there to stop hallucinated guidance
> reaching staff. You described the mechanism but not the reason — I supplied that. Is it right? If
> not, I'll cut the clause."

Confirm, correct, or delete. All three are fine. Leaving it as-is is not.

## For illegible titles

Most people never notice this one, because inside the company the title was perfectly clear. Ask
plainly:

> "Your title there was Member of Technical Staff. If I showed that line to a hiring manager who has
> never worked at that company, what would they think you did? What would the same job be called
> somewhere else?"

Record their answer as `functional_title` on the role and leave the official `title` untouched — it
is what a reference check confirms, and rewriting it turns a clarification into a discrepancy. Watch
for the answer that is a level up rather than a translation ("really I was doing staff engineer
work"): that is a claim about scope, and it belongs in the evidence, not in a parenthesis.

Most titles need nothing here. Skip the ones that already read plainly.

## For missing metrics

Prompt with where the number might live: monitoring dashboards, APM, cloud billing, sprint retros,
release notes, incident reviews, performance and promotion documents, the original project brief, a
colleague.

If unavailable, take an honest approximation and record it as `confidence: estimated` — **"~50
tenants" is worth far more than silence**. If there is no number at all, make the bullet read as true
and complete without one, then close the question. A bullet permanently awaiting a metric is a bullet
nobody improved.

## For unexplored territory

Most people under-report. Ask about mentoring, interview panels, internal tools other teams adopted,
talks, writing, patents, awards, process changes, cost savings, and work that prevented a problem
rather than fixing one.

## Record and close

Ordinary `Edit` calls into `user-knowledgebase.md`. Each answer touches two places and both matter:

1. **The section it was about** — the metrics row, the bullet, the role's `functional_title`, the
   project's block. Change its `status` to `confirmed`, because they just confirmed it.
2. **`## Open questions`** — fill the `answered` date on that row. Leave the row.

All six outcomes are real, and **unavailable is one of them**: a metric nobody can reconstruct closes
the question and should soften or cut the claim rather than leaving it pending forever.

**The knowledge base is the only place to write.** Nothing is copied anywhere else, so an answer that
reaches the file has reached everything downstream by construction. There is no second copy to keep
in step, which is the whole reason this used to say the opposite.

Then append one row to `## Log`, and update `updated:` in the frontmatter.

Report what resolved, what is still open, and **which claims should be softened or cut** because no
evidence turned up. That last list is the valuable one — better to lose a bullet now than be asked
about it across a table.

If the resume changed materially, offer to regenerate.
