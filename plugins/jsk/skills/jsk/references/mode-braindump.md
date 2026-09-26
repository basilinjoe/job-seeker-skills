# Mode: braindump

They talk. You structure. This mode fails if you interrupt.

Everything goes into `career/kb.ttl`, through one `jsk kb apply`. The only other file written is
their words, kept verbatim under `sources/`.

## Let them finish

If they are mid-flow, do not interrupt to impose format — recall is associative, and cutting in
loses material that will not come back.

If they have not started, open wide:

> "Tell me about it however it comes out — what it was, what was hard, what you decided, what
> happened. I'll structure it afterwards. Don't worry about order."

## Then, before writing anything

1. **Say how many projects you heard.** "That's three separate things — the platform, the
   application on top of it, and the migration."
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

An honest approximation is `j:confidence j:estimated`. No number at all → write the bullet true
without one; set `j:noneQuantified true` on the project if nothing is measurable.

## Is it already there?

```bash
jsk kb query similar "<their words>"  # first: the closest projects, and why
jsk kb query holds c:<concept>        # then: the projects holding one concept
```

If it turns up, **extend the project that exists** (`jsk kb show <id>`) rather than adding a rival:
two entries for one project split its evidence so neither reads as strong.

## Write it up

**Save their words first.** Once they have finished and answered, write their messages verbatim —
their words, not a summary — to `<workspace>/sources/<yyyy-mm-dd>-braindump.md` (Write tool).

**Send `jsk-extractor`** the workspace, that file and the skill directory. It reads what the career
holds, writes one changeset and dry-runs it; it never applies. Back come the diff, every clause
that is not their words, quoted with its id, and the questions still open.

**Show them the diff and the quoted clauses** — names, not Turtle — and ask about each. Then
`jsk kb apply <its file>`. Everything lands `inferred`: only what they said in so many words gets
`jsk kb confirm <ids> --answer "…"`, or `--source sources/<that file> --quote "their words"`,
checked against what you saved. **Tell them which parts were inferred**, every time.

No agents available? Run `agents/jsk-extractor.md`'s procedure inline: one changeset — the
organisation, role, metric and its version, then the project and its bullets —
`references/kb-format.md` for the shapes, `--dry-run` first.

## Close out

Say back what was written — the ids apply minted, the metrics, what is `inferred`, what is still open
(`jsk kb query open`). Show names, not Turtle, unless they want it.

## Look for what they undersold

Ask about mentoring, interview panels, onboarding material, internal tools other teams adopted, a
process they changed, and — most overlooked — work that **prevented** a problem rather than fixing
one. It produces no ticket, and it is exactly what senior hiring looks for.
