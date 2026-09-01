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

**Every write is a command.** Never `Write` or `Edit` a file in the bundle —
`references/write-commands.md` is the surface, and `okf <noun> --help` the flags. You do not need to
read `bundle-spec.md` to author a concept: house style is structural now.

A project heard in one sitting is usually four commands. In this order, because each refuses a
reference the one before it establishes:

```bash
OKF="okf"
B="--bundle <bundle>"

# 1. The employer and the job, if they are not already there.
#    --description on every concept: validate_bundle.py warns without one.
$OKF org add  $B --title "…" --description "one line" --relationship employer \
                 --industry <domain> --body -
$OKF role add $B --title "…" --description "one line" --organisation <org-stem> \
                 --start 2023-01 --state ongoing --body -

# 2. The number, before the bullet that rests on it.
$OKF metric add $B --name "Claim latency" --value "4.2s to 380ms" \
                   --evidence <project-stem> --source "the dashboard they named"

# 3. The project.
$OKF project add $B --title "…" --role <role-stem> \
  --strength 4 --recency 2026 --seniority hands-on-senior \
  --domain <domain> --capability <term> --description "one line" --status inferred --body -

# 4. The lines it earned, one command each.
$OKF bullet add $B --project <project-stem> --text "…" --metric "Claim latency" --status confirmed
```

Each one writes the concept, its directory index entry and the `log.md` row together, and refuses
what a gate would catch later — or worse, would not: a `--role` that names no concept aborts the
next tailoring run and no gate reports it, and a `--metric` that names no row crashes the next
compile.

**Run the first one with `--dry-run --json`** if you are unsure what a command will touch. It
decides everything and writes nothing.

**Pipe the body in, or close stdin.** `--body -` reads stdin to EOF, so with stdin left open the
command waits forever and writes nothing. Add `< /dev/null` when the prose comes later — a concept
with no body is perfectly valid, since the frontmatter is what compiles.

**Pass `--status inferred` for anything you wrote rather than heard.** `add` defaults to
`confirmed`, which is right when they just told you and wrong in exactly the case this framework
exists to catch. Tell them which parts you inferred.

**If a change has no command, say so and stop.** Do not hand-edit around it. `--set key=value`
covers a key the format does not model.

Then run the validator: `okf validate <bundle>`. Once, at the end — not after every command.

## Look for what they undersold

People discount work that was not assigned. Ask about mentoring, interview panels, onboarding
material, internal tools other teams adopted, a process they changed, and — most overlooked —
work that **prevented** a problem rather than fixing one. Preventing an outage produces no ticket and
no war story, but it is exactly what senior hiring looks for.
