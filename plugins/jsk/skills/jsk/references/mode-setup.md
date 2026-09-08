# Mode: setup

Create a knowledge base from nothing, from an existing resume, or from an older bundle.

**`/jsk:setup` wraps this mode** with a toolchain check either side of it — preflight before, a real
render after. When someone arrives through that command, phases 1 and 2 have already run and this
file is phase 3; do not re-run preflight. When they arrive here directly, run it first, because a
knowledge base built on a toolchain that cannot render is one nobody can use yet:

```bash
jsk doctor --quick
```

## Ask two things

1. **Where should it live?** Default `career/` in a folder they control. Version control is
   ideal — this should outlive any tool.
2. **Do they have an existing resume?** It is the fastest skeleton available.

## Create the file

```bash
jsk new <path> --name "Their Name"
```

That writes `user-knowledgebase.md` with every heading present and empty, and an `applications/`
directory beside it. Nothing else. The rules and the toolchain stay with the skill, so a knowledge
base is never stale.

If the command is unavailable, write the file by hand from `references/kb-spec.md`.

**Fill `## Identity` first.** The parse gate fails a resume with no email and no phone, so until that
block is complete nothing sendable can render. It is the most common thing left empty and the only
one that blocks everything.

**Only if they ask to customise rendering**, create a `rules/` directory beside the knowledge base
and seed `ats-rules.md`, `writing-rules.md` or `structure-rules.md` from the references here. Those
files override the skill's defaults, so create them deliberately, not by habit — an absent file means
"use the defaults", which is what most people want. An override must say in its opening lines whether
it **replaces** the default or **extends** it; one that says neither is treated as an extension and
both get read.

## If they have a resume

Copy it verbatim beside the knowledge base — `sources/prior-resume.md`, or whatever format it arrived
in — then read it critically and record:

- What you removed and why — learning statements, repeated bullets, filler, references, home address
- Any **internal contradictions**. Old resumes often disagree with themselves on dates between a
  summary table and section headers. Put a row in `## Open questions`; a three-month discrepancy is
  exactly what a background check surfaces.
- Detail worth keeping that will not fit the current resume

Extract roles, employers, dates and projects into the file's sections. Mark everything `confirmed` if
it came from the document, and say so in `## Log`.

## If they have an older bundle

A directory holding `projects/` and `resume-generation/` is the previous format: a folder of linked
Markdown concepts with a compiler over it. **There is no migration command**, because the migration
is reading it and writing one file — which is a thing you do well and a thing a script did badly,
guessing at every relation the old format left in prose.

Offer it; never run it unasked. Then:

1. **Read the whole bundle.** `index.md`, then `log.md`, then every concept. Do not sample.
2. **Map it section by section.** `organisations/` → `## Organisations`. `roles/` → `## Roles`.
   `projects/` → `## Projects`, prose and `# Bullets` and all. `achievements/metrics.md` → the
   `## Metrics` table. `skills/competencies.md` → `## Skills`. `framework/capability-vocabulary.md`
   → `## Vocabulary`. `resume-generation/open-questions.md` → `## Open questions`.
3. **Carry `status` across unchanged.** A concept that was `inferred` in the bundle is `inferred` in
   the file. Never upgrade one in transit — that is exactly the laundering the status exists to
   prevent, and a migration is where it happens invisibly.
4. **Carry `log.md` across**, then append one row saying the knowledge base was migrated and from
   where.
5. **Name what you could not place.** A concept type with no home — a `Talk`, a `Patent`, a
   `Reference` — goes under the nearest section with a note, and into `## Open questions`. Say which
   ones out loud rather than dropping them.
6. **Move `tailoring/applications/` to `applications/`**, one directory per submission. Those are
   frozen and are copied, never rewritten.

**Keep the old bundle** until they confirm the new file is complete. Deleting somebody's only copy of
their career is not a trade this framework gets to make — and a migration nobody has read is a
migration nobody has checked.

## Then go deeper

An old resume describes what someone did. It rarely captures what they **decided**, what constraint
they were under, or what changed as a result — which is the material that makes a senior resume work.
Switch to `mode-braindump.md` and work through their most significant projects.

## Finish

Say back what the file now holds — how many roles, how many projects, how many metrics, what is
marked `inferred`. Append a row to `## Log`. Then tell them what to do next: usually fill the biggest
gaps, then generate a resume.
