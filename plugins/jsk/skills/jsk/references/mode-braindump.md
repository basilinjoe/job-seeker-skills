# Mode: braindump

They talk. You structure. This is the highest-value mode and the one that fails if you interrupt.

Everything they say ends up in **one place** — `user-knowledgebase.md` — under the headings
`references/kb-spec.md` describes. Nothing else is written.

## Let them finish

If they are mid-flow, do not interrupt to impose format. People recall their work associatively —
a constraint reminds them of a workaround, which reminds them of a number. Cutting in loses material
that will not come back.

If they have not started, open wide:

> "Tell me about it however it comes out — what it was, what was hard, what you decided, what
> happened. I'll structure it afterwards. Don't worry about order."

## Then, before writing anything

1. **Say how many concepts you heard.** "That's three separate things — the platform, the application
   on top of it, and the migration."
2. **Flag ambiguities and probable transcription errors.** Voice input mangles technical terms
   reliably. If something sounds off — a garbled product name, an acronym that does not parse —
   ask rather than guess. Getting "evals" wrong as "emails" changes what goes on a resume.
3. **Ask the questions that make it resume-grade**, only the ones missing:
   - What was broken, missing, or constrained before?
   - What did *you* decide, as opposed to what the team did?
   - What changed as a result?
   - Scale — users, transactions, tenants, team size, data volume?
   - What was the hardest trade-off?
   - How much of this was yours? (This sets the verb.)

## Push for numbers, twice

People routinely believe they cannot get a number they can get. Prompt with where it might live:
monitoring dashboards, cloud billing, release notes, incident reviews, performance reviews, the
original project brief, a colleague who would know.

If it genuinely is not available, take an honest approximation and mark it `estimated` in the
metrics table. If there is no number at all, write the bullet true without one and put a row in
`## Open questions`. **Never leave a placeholder in a document they might send.**

## Read the file before you write to it

**One command, before the first edit:**

```bash
grep -n -i "<a distinctive phrase from what they described>" <path>/user-knowledgebase.md
```

People re-tell the same work months apart, in different words, and neither telling mentions the
other. A second entry for one project is the failure that costs most later: the ranking sees two
weak projects where there was one strong one, and the bullets are split across both so neither
reads as evidence. Finding it now is one grep; finding it after a resume is written is a merge
somebody has to do by hand.

If something turns up, **extend the section that exists** rather than adding a rival to it.

Then read the whole file. It is one document and it is meant to be read whole — you are about to
edit four sections of it, and the ids in each have to agree with the others.

## Write it up

**Ordinary `Edit` calls.** There is no write layer any more: the transaction a command used to make
atomic was a several-file write, and there is only one file now.

A project heard in one sitting touches four sections. Do them in this order, because each one names
something the previous established:

1. **`## Organisations`** — the employer, if it is not already there.
2. **`## Roles`** — the job, pointing at `organisation:`.
3. **`## Metrics`** — the number, before the bullet that rests on it. Give it an id.
4. **`## Projects`** — the project, pointing at `role:`, then its prose, then its `**Bullets**`
   naming the metric id.

Add any new `capabilities` or `domains` value to `## Vocabulary` **in the same edit that first uses
it**. That list is the matching axis and compares as exact strings, so a term used and never
recorded silently breaks the next tailoring run.

`references/kb-spec.md` has the exact block for each. The shapes are fixed; the prose is not.

### What nothing checks for you any more

The write commands used to refuse a `role:` naming no role and a `metric:` naming no row. Nothing
does now until `jsk validate` runs over a record, which is a whole tailoring run later. So:

- **Every `id:` you reference must exist.** Read the section you are pointing at.
- **Every id you create must be new.** Grep it before you use it.
- **Never renumber, never reuse a retired id.**

### Provenance

**Write `status: confirmed` only for what they actually said.** Anything you reconstructed, inferred
from context, or wrote to fill a shape is `status: inferred` — and gets a row in `## Open questions`.

There is no command defaulting this for you, which makes it entirely your habit and the single
easiest thing in this mode to get wrong. A concept you wrote and stamped `confirmed` has laundered
your inference into a fact, and nothing downstream can tell.

**Tell them which parts you inferred.** Every time, in chat, in plain words.

## Close out

Append one row to `## Log` — the date, and what changed. One row for the session, not one per edit.

Then say back what you wrote: how many projects, which metrics, what you marked `inferred`, and what
is still open. Show them the section headings, not the YAML, unless they want it.

## Look for what they undersold

People discount work that was not assigned. Ask about mentoring, interview panels, onboarding
material, internal tools other teams adopted, a process they changed, and — most overlooked —
work that **prevented** a problem rather than fixing one. Preventing an outage produces no ticket and
no war story, but it is exactly what senior hiring looks for.
