# Mode: braindump

They talk. You structure. This is the highest-value mode and the one that fails if you interrupt.

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

If it genuinely is not available, take an honest approximation and mark it as such. If there is no
number at all, write the bullet true without one and log it in `open-questions.md`. **Never leave a
placeholder in a document they might send.**

## Write it up

Follow `references/bundle-spec.md`. Read two existing project concepts first so you match house style
and reuse existing `capabilities` values rather than inventing synonyms.

**For a project, prefer the command over hand-authoring it:**

```bash
echo "The project's prose." | python3 <skill-dir>/scripts/okf.py project add --bundle <bundle> \
  --title "…" --role <role-stem> \
  --strength 4 --recency 2026 --seniority hands-on-senior --domain <domain> \
  --capability <term> --description "one line" --status inferred
```

It writes the concept, the `projects/index.md` entry and the `log.md` row together, and refuses a
`--role` that names no concept — which no gate catches and which aborts the next tailoring run.
`--dry-run --json` shows what it would touch first. `references/write-commands.md` has the full flag
list and the three rules it enforces.

**Pipe the body in, or close stdin.** `--body` defaults to `-`, so with stdin left open the command
waits forever and writes nothing. Add `< /dev/null` if the prose comes later.

**Pass `--status inferred` for anything you wrote rather than heard.** The flag defaults to
`confirmed`, which is right when they just told you and wrong in exactly the case that matters.

Still yours either way: link from the relevant role concept, add numbers to
`achievements/metrics.md`, and run the validator. Every other concept type is hand-written.

Mark anything you inferred as `status: inferred` and tell them which parts those are.

## Look for what they undersold

People discount work that was not assigned. Ask about mentoring, interview panels, onboarding
material, internal tools other teams adopted, a process they changed, and — most overlooked —
work that **prevented** a problem rather than fixing one. Preventing an outage produces no ticket and
no war story, but it is exactly what senior hiring looks for.
