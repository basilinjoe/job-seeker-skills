# Mode: braindump

They talk. You structure. This mode fails if you interrupt.

Everything goes into `user-knowledgebase.md`. Nothing else is written.

## Let them finish

If they are mid-flow, do not interrupt to impose format — recall is associative, and cutting in
loses material that will not come back.

If they have not started, open wide:

> "Tell me about it however it comes out — what it was, what was hard, what you decided, what
> happened. I'll structure it afterwards. Don't worry about order."

## Then, before writing anything

1. **Say how many concepts you heard.** "That's three separate things — the platform, the application
   on top of it, and the migration."
2. **Flag ambiguities and probable transcription errors.** Voice input mangles technical terms; ask
   rather than guess. "evals" heard as "emails" changes what goes on a resume.
3. **Ask the questions that make it resume-grade**, only the ones missing:
   - What was broken, missing, or constrained before?
   - What did *you* decide, as opposed to what the team did?
   - What changed as a result?
   - Scale — users, transactions, tenants, team size, data volume?
   - What was the hardest trade-off?
   - How much of this was yours? (This sets the verb.)

## Numbers

Prompt with where the number might live: monitoring dashboards, cloud billing, release notes,
incident reviews, performance reviews, the original project brief, a colleague who would know.

An honest approximation is marked `estimated` in the metrics table. No number at all → write the
bullet true without one and put a row in `## Open questions`.

## Before the first edit

```bash
grep -n -i "<a distinctive phrase from what they described>" <path>/user-knowledgebase.md
```

If something turns up, **extend the section that exists** rather than adding a rival to it.

## Write it up

Ordinary `Edit` calls. A project touches four sections — in this order, because each names something
the previous established:

1. **`## Organisations`** — the employer, if it is not already there.
2. **`## Roles`** — the job, pointing at `organisation:`.
3. **`## Metrics`** — the number, before the bullet that rests on it. Give it an id.
4. **`## Projects`** — the project, pointing at `role:`, then its prose, then its `**Bullets**`
   naming the metric id.

Add any new `capabilities` or `domains` value to `## Vocabulary` **in the same edit that first uses
it** — matching compares exact strings, so an unrecorded term silently breaks the next tailoring run.

Nothing checks references until `jsk validate` runs over a record, so:

- **Every `id:` you reference must exist.** Read the section you are pointing at.
- **Every id you create must be new.** Grep it before you use it.
- **Never renumber, never reuse a retired id.**

Anything you reconstructed, inferred from context, or wrote to fill a shape is `status: inferred`
and gets a row in `## Open questions`. **Tell them which parts you inferred**, every time, in plain
words.

## Close out

One `log.md` row for the session, not one per edit. Then say back what you wrote: how many projects,
which metrics, what you marked `inferred`, and what is still open. Show the section headings, not the
YAML, unless they want it.

## Look for what they undersold

Ask about mentoring, interview panels, onboarding material, internal tools other teams adopted, a
process they changed, and — most overlooked — work that **prevented** a problem rather than fixing
one. It produces no ticket, and it is exactly what senior hiring looks for.
