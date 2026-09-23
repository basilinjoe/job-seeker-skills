# Mode: setup

Get this machine from nothing to a working, verified pipeline, with a knowledge base created from
nothing, from an existing resume, or from an older bundle. Four phases, in order; **do not skip
phase 1**.

`$ARGUMENTS` may hold a path: a `.docx`, `.pdf` or `.md` resume is a document to import in phase 3;
a directory is where the knowledge base goes. Empty → ask.

## Phase 1: Find out what works

```bash
jsk doctor
```

Bare `jsk doctor` is the verifying run: it renders the shipped example end to end and runs every
gate. `--quick` skips the render. **Show the output**, then read the verdict:

| Verdict | What to do |
|---|---|
| `READY` | Everything works, PDF included. Go to phase 3. |
| `READY, with gaps` | The core pipeline works. Go to phase 2 and offer to close the gaps. |
| `BLOCKED` | The install is broken — modules or schema missing. Fix that first; nothing else is worth doing. |
| `BROKEN` | The toolchain is present but failed its own gates — a bug in the skill, not their setup. Report the failing step verbatim rather than working around it. |

## Phase 2: Close the gaps — with permission, never silently

The doctor prints what each gap disables and the exact command to fix it. Relay both, then offer the
choice with `AskUserQuestion` before running anything — installing software is theirs to authorise,
and a TeX distribution can be several gigabytes.

- **A TeX engine is required** — without one the doctor reports `BLOCKED`. Recommend `tectonic`, a
  single self-contained binary; MiKTeX or TeX Live only if they already wanted them.
- **`pymupdf` is required** — the parse gate reads the PDF through it and the fitter measures pages
  through it. One `pip install`.

Re-run the doctor after any install.

## Phase 3: Create or adopt the knowledge base

Ask two things:

1. **Where should it live?** Default `career/` in a folder they control, ideally under version
   control — this should outlive any tool.
2. **Do they have an existing resume?** It is the fastest skeleton available.

```bash
jsk new <path> --name "Their Name"
```

That writes `user-knowledgebase.md` with every heading present and empty, and an `applications/`
directory beside it. Unavailable → write the file by hand from `references/kb-spec.md`.

**Fill `## Identity` first — email and phone.** The parse gate fails a resume without them, so
nothing sendable can render until that block is complete; it is the most common thing left empty.

**Only if they ask to customise rendering**, create `rules/` beside the knowledge base and seed
`ats-rules.md`, `writing-rules.md` or `structure-rules.md` from the references here. An absent file
means "use the defaults", which is what most people want. An override must say in its opening lines
whether it **replaces** or **extends** the default; one that says neither is an extension and both
get read.

### If they have a resume

Keep it verbatim beside the knowledge base — `sources/prior-resume.md`, or whatever format it arrived
in — then read it critically and record:

- What you removed and why — learning statements, repeated bullets, filler, references, home address
- Any **internal contradictions**, such as dates that disagree between a summary table and section
  headers. Put a row in `## Open questions`; a background check surfaces a three-month discrepancy.
- Detail worth keeping that will not fit the current resume

Extract roles, employers, dates and projects into the file's sections. Mark everything `confirmed` if
it came from the document, and say so in `log.md`.

### If they have an older bundle

A directory holding `projects/` and `resume-generation/` is the old format. There is no migration
command: you read it and write one file. Offer it; never run it unasked. Then:

1. **Read the whole bundle.** `index.md`, then `log.md`, then every concept. Do not sample.
2. **Map it section by section.** `organisations/` → `## Organisations`. `roles/` → `## Roles`.
   `projects/` → `## Projects`, prose and `# Bullets` and all. `achievements/metrics.md` → the
   `## Metrics` table. `skills/competencies.md` → `## Skills`. `framework/capability-vocabulary.md`
   → `## Vocabulary`. `resume-generation/open-questions.md` → `## Open questions`.
3. **Carry `status` across unchanged.** Never upgrade one in transit.
4. **Carry `log.md` across** — it stays a file of its own beside the knowledge base — then append
   one row saying the knowledge base was migrated and from where.
5. **Name what you could not place.** A concept type with no home — a `Talk`, a `Patent`, a
   `Reference` — goes under the nearest section with a note, and into `## Open questions`. Say which
   ones out loud.
6. **Move `tailoring/applications/` to `applications/`**, one directory per submission — copied,
   never rewritten.

**Keep the old bundle** until they confirm the new file is complete.

### Then go deeper

An old resume rarely captures what they **decided**, what constraint they were under, or what changed
as a result — the material that makes a senior resume work. Switch to `mode-braindump.md` and work
through their most significant projects.

## Phase 4: Prove it, on their data

1. Write a thin `resume.json` beside the knowledge base from whatever it now holds —
   `references/mode-resume.md` for the procedure. The point is that the path works, not that the
   resume is finished.
2. Choose the region profile that matches where they are applying, and **say why**: a photograph and
   date of birth are conventional on a Gulf resume and a liability on an Australian one, India
   expects academic grades and a declaration block, and the region-neutral default forbids all of it.
   Ask if their location does not make it obvious.
3. Validate, render and gate in one run, and show every step's output:

```bash
jsk ship resume.json --out . --view <id> --pages 2
```

If the PDF step reports the resume **unverified**, say so plainly.

## Hand over

Tell them, in plain language and without the framework vocabulary:

- **Where the file is**, and that it is theirs — one Markdown document, readable in any editor, worth
  putting in git.
- **What works and what does not**, naming any gap left open and what it costs them.
- **The rhythm.** Something ships → `braindump`, while they still remember the details. Every quarter
  → `refresh`. Before applying → `gaps`, then `resume`. A specific role → `tailor`.
- **What the file now holds** — how many roles, projects and metrics, and what is `inferred`.
- **The biggest gap in their record right now** — a missing metric, an unconfirmed claim, a role with
  no evidence behind it.

The `log.md` row covers what was set up and what was left open.
