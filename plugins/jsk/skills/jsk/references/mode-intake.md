# Mode: intake

Whatever they bring becomes part of the career: talk, an old resume, writing, an older bundle. One
path: they talk or hand over, you structure, the extractor drafts one changeset, one `career_apply`
writes it. The only other file written is their material, verbatim under `sources/`.

`$ARGUMENTS` may be a file, or what to talk about. Empty → ask what they have been working on, or
whether they have a document. For what is weak in what the career holds, use `mode-review.md`.

## Talk: let them finish

This half fails if you interrupt. Do not cut in to impose format — recall is associative, and what is
cut off does not come back. If they have not started, open wide:

> "Tell me about it however it comes out — what it was, what was hard, what you decided, what
> happened. I'll structure it afterwards. Don't worry about order."

Then, before writing anything:

1. **Say how many projects you heard.** "That's three separate things — the platform, the
   application on top of it, and the migration."
2. **Flag ambiguities and probable transcription errors.** Voice input mangles technical terms; ask
   rather than guess. "evals" heard as "emails" changes what goes on a resume.
3. **Ask only the questions still missing** that make it resume-grade:
   - What was broken, missing, or constrained before?
   - What did *you* decide, as opposed to what the team did?
   - What changed as a result?
   - Scale — users, transactions, tenants, team size, data volume?
   - What was the hardest trade-off?
   - How much of this was yours? (This sets the verb.)

**Numbers.** Prompt with where one might live: monitoring dashboards, cloud billing, release notes,
incident reviews, performance reviews, the original brief, a colleague. An honest approximation is
`j:confidence j:estimated`. No number at all → write the bullet true without one; set
`j:noneQuantified true` on the project if nothing is measurable.

**Is it already there?** People re-tell one project months apart in other words.
```
career_query(name="similar", args=["<their words>"])  # first: the closest projects, and why
career_query(name="holds", args=["c:<concept>"])      # then: the projects holding one concept
```

If it turns up, **extend the project that exists** (`career_show(ids=["<id>"])`) rather than adding a
rival: two entries split one project's evidence so neither reads as strong.

## A document, or a bundle

Keep the document verbatim — `sources/prior-resume.md`, or whatever format it arrived in — then
read it critically and note what you removed and why (learning statements, repeated bullets, filler,
references, home address); any **internal contradictions**, such as dates that disagree between a
summary and section headers, each a `q_` question, since a background check surfaces a three-month
discrepancy; and detail worth keeping that will not fit the current resume.

An older **bundle** (`projects/` and `resume-generation/`) has no migration command: read it whole
and build the record from it like a resume, one `jsk-extractor` per bundle file, each changeset
shown and applied through `career_apply`. A changeset cannot confirm, so it carries
`j:needs-verification` and `j:disputed` as the bundle held them and everything else lands
`inferred`; then `career_confirm(ids=[every id the bundle held confirmed], source="<bundle file>",
quote="…")`. Keep the bundle until they confirm the record is complete.

## Save, extract, apply

**Save their words first.** Once they have finished and answered, write their messages verbatim —
their words, not a summary — to `<workspace>/sources/<yyyy-mm-dd>-braindump.md` (Write tool).

**Send `jsk-extractor`** the workspace, the file(s) in `sources/` and the skill directory. It reads
what the career holds, drafts one changeset and previews it; it never applies. Back come the
changeset, the diff, every clause that is not the source's own words, quoted with its id, and the
questions still open.

**Show them the diff and the quoted clauses** — names, not Turtle — and ask about each. Then
`career_apply` the changeset it returned, corrected as they said. Everything lands `inferred`, and
only what the source says in so many words is confirmed:

- **Talk**: `career_confirm(ids=[...], answer="…")`, or `source="sources/<that file>", quote="their
  words"`, checked against what you saved.
- **A document**: the confirm lines the agent proposed, `career_confirm(ids=[...],
  source="<file>", quote="its exact words")`, each number in the quote.

**Tell them which parts were inferred**, every time.

No agents available? Run `agents/jsk-extractor.md`'s procedure inline: one changeset — the
organisation, role, metric and its version, then the project and its bullets —
`references/kb-format.md` for the shapes, `career_preview` first.

## Go deeper

A document rarely captures what they **decided**, what constraint they were under, or what changed
as a result — the material that makes a senior resume work. After a document, work through their
most significant projects as talk, above.

Then ask what they undersold: mentoring, interview panels, onboarding material, internal tools other
teams adopted, a process they changed, and — most overlooked — work that **prevented** a problem
rather than fixing one. It produces no ticket, and it is exactly what senior hiring looks for.

## Close out

Say back what was written — the ids minted, the metrics, what is `inferred`, what is still open
(`career_query(name="open")`). Show names, not Turtle.
