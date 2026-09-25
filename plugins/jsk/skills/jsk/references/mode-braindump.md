# Mode: braindump

They talk. You structure. This mode fails if you interrupt.

Everything goes into `career/kb.ttl`, through one `jsk kb apply`. Nothing else is written.

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
jsk kb view --section Projects        # every project, to read
jsk kb query holds c:<concept>        # the projects holding one concept
```

If it turns up, **extend the project that exists** (`jsk kb show <id>`) rather than adding a rival:
two entries for one project split its evidence so neither reads as strong.

## Write it up

One changeset for the session, in this order, because each names what the previous established:
the organisation (`org_`) if new, the role (`pos_`), the metric and its first version, then the
project with its prose and bullets. A concept it uses that no vocabulary has goes in too.

```turtle
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix op: <tag:jsk,2026:op#> .
op:changeset op:base 7 ; op:summary "Payments platform, from the braindump." .
op:add {
  k:met_settlement j:subject "settlement latency" ; j:unit "ms" ; j:direction j:decrease .
  k:met_settlement.v1 j:of k:met_settlement ; j:baseline 800 ; j:value 200 ; j:confidence j:reported .
  k:prj_payments j:name "Payments platform" ; j:position k:pos_acme_lead ; j:strength 4 ;
      j:recency 2025 ; j:uses c:kafka ; j:headlineMetric k:met_settlement ;
      j:problem "…" ; j:decision "…" ; j:outcome "…" .
  [] j:project k:prj_payments ; j:rank 1 ; j:text "Cut settlement latency from 800 ms to 200 ms." ;
      j:cites k:met_settlement ; j:shows c:kafka .
}
```

`op:base` is the revision `jsk kb show` prints. `references/kb-format.md` lists every field.

```bash
jsk kb apply braindump.trig --dry-run      # read the diff
jsk kb apply braindump.trig
```

Leave provenance out: everything you write lands `inferred`, each with a question. Only what they
said in so many words gets `jsk kb confirm <ids> --answer "…"`, afterwards. A refusal names its fix
— an unknown concept, a dangling id, a missing `j:rank`; fix the changeset and re-run.

**Tell them which parts you inferred**, every time, in plain words.

## Close out

Say back what was written — the ids apply minted, the metrics, what is `inferred`, what is still open
(`jsk kb query open`). Show names, not Turtle, unless they want it.

## Look for what they undersold

Ask about mentoring, interview panels, onboarding material, internal tools other teams adopted, a
process they changed, and — most overlooked — work that **prevented** a problem rather than fixing
one. It produces no ticket, and it is exactly what senior hiring looks for.
