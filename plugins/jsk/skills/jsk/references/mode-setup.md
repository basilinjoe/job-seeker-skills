# Mode: setup

Get this machine from nothing to a working, verified pipeline, with a knowledge base created from
nothing, from an existing resume, or from an older Markdown one. Four phases, in order; **do not
skip phase 1**.

`$ARGUMENTS` may hold a path: a `.docx`, `.pdf` or `.md` resume is a document to import in phase 3;
a `user-knowledgebase.md` is a knowledge base to migrate; a directory is where the workspace goes.
Empty → ask.

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
| `BLOCKED` | The core pipeline cannot run — a module, the schema, a TeX engine or `pymupdf` missing. Fix the FAIL lines first (phase 2 for an engine or `pymupdf`); nothing else is worth doing. |
| `BROKEN` | The toolchain is present but failed its own gates — a bug in the skill, not their setup. Report the failing step verbatim rather than working around it. |

## Phase 2: Close the gaps — with permission, never silently

The doctor prints what each gap disables and the exact command to fix it. Relay both, then offer the
choice with `AskUserQuestion` before running anything — installing software is theirs to authorise,
and a TeX distribution can be several gigabytes.

- **A TeX engine is required** — without one the doctor reports `BLOCKED`. Recommend `tectonic`, a
  single self-contained binary; MiKTeX or TeX Live only if they already wanted them.
- **`pymupdf` is required** — the parse gate reads the PDF through it and the fitter measures pages
  through it. One `pip install`.
- **`pyoxigraph`** comes with the package; without it the career can be neither changed nor matched.

Re-run the doctor after any install.

## Phase 3: Create or adopt the knowledge base

Ask two things:

1. **Where should the workspace live?** A folder they control, ideally a git repository — this
   should outlive any tool.
2. **Do they have an existing resume?** It is the fastest skeleton available.

```bash
jsk new <path> --name "Their Name"
```

That writes `career/kb.ttl` with every section banner present and empty, `career/log.ttl` at
revision 1, `.gitattributes` and `applications/`. Everything after that goes in through
`jsk kb apply`. On a new record there is nothing for `jsk kb show` to show: `op:base` is 1.

**Fill the identity first — email and phone** on `k:person`. The parse gate fails a resume without
them; it is the most common thing left empty.

**Only if they ask to customise rendering**, create `rules/` beside `career/` and seed
`ats-rules.md`, `writing-rules.md` or `structure-rules.md` from the references here. An absent file
means "use the defaults". An override must say in its opening lines whether it **replaces** or
**extends** the default; one that says neither is an extension and both get read.

### If they have a resume

Keep it verbatim in the workspace — `sources/prior-resume.md`, or whatever format it arrived in —
then read it critically and note:

- What you removed and why — learning statements, repeated bullets, filler, references, home address
- Any **internal contradictions**, such as dates that disagree between a summary and section
  headers. Each becomes a `q_` question; a background check surfaces a three-month discrepancy.
- Detail worth keeping that will not fit the current resume

Extract roles, employers, dates, projects and metrics into one changeset and `jsk kb apply` it
(`references/kb-format.md` has the shapes). It lands `inferred`; then `jsk kb confirm` what the
document states, with `--answer` naming the document ("From prior-resume.pdf, their own resume").

### If they have a `user-knowledgebase.md`

The Markdown format this replaced. Offer the migration; never run it unasked.

```bash
jsk migrate <path>/user-knowledgebase.md --dry-run
jsk migrate <path>/user-knowledgebase.md
```

It writes `career/kb.ttl` and `career/log.ttl` beside it, and `posting.ttl` and `application.ttl` in
each application directory, and refuses unless the graph reads back as exactly what the Markdown
held. **It never deletes anything** and never raises a provenance. Show them its output — what it
kept as notes, and any claims-gate failures it found in their old records. Then `jsk kb view` is
their career, read end to end; keep the Markdown until they confirm it is complete.

An older **bundle** (`projects/` and `resume-generation/`) has no migration command: read it whole
and build the record from it like a resume — `jsk new`, then changesets through `jsk kb apply`
(`--dry-run` first; each refusal names its fix). A changeset cannot confirm, so it carries
`j:needs-verification` and `j:disputed` as the bundle held them and everything else lands `inferred`;
then `jsk kb confirm <every id the bundle held confirmed> --answer` naming the bundle file it came
from. Keep the bundle until they confirm the record is complete.

### Then go deeper

An old resume rarely captures what they **decided**, what constraint they were under, or what changed
as a result — the material that makes a senior resume work. Switch to `mode-braindump.md` and work
through their most significant projects.

## Phase 4: Prove it, on their data

1. Write a thin `resume.json` in the workspace from whatever the career now holds —
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

- **Where the file is**, and that it is theirs — `career/kb.ttl`, plain text readable in any editor,
  worth committing to git. `jsk kb view` shows it as a document.
- **What works and what does not**, naming any gap left open and what it costs them.
- **The rhythm.** Something ships → `braindump`, while they still remember the details. Every quarter
  → `refresh`. Before applying → `gaps`, then `resume`. A specific role → `tailor`.
- **What the career now holds** — how many roles, projects and metrics, and what is `inferred`.
- **The biggest gap in their record right now** — a missing metric, an unconfirmed claim, a role with
  no evidence behind it.
