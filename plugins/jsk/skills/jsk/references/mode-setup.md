# Mode: setup

Get this machine from nothing to a working, verified pipeline, with a knowledge base created from
nothing or from an existing resume. Four phases, in order; **do not
skip phase 1**.

`$ARGUMENTS` may hold a path: a `.docx`, `.pdf` or `.md` resume is a document to import in phase 3;
a directory is where the workspace goes.
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
- **`pyoxigraph` and `mcp`** come with the package; without them the career can be neither changed
  nor matched, and every agent works through the `jsk mcp` tools the plugin starts. If the tools are
  missing after an install, restart Claude Code.

Re-run the doctor after any install.

## Phase 3: Create or import the knowledge base

**A workspace that still holds `career/kb.ttl` and no `career/store/`** is a record from before the
store: `jsk kb load .` from it imports it, once. It validates the files as before, lists every
number it rewrites (`8.40` kept as `8.4`), and leaves the files in place; jsk never reads them again.
Show the output. On `REFUSED`, apply each printed fix to the files and run `jsk kb load .` again;
once it loads, go to phase 4.

Otherwise ask two things:

1. **Where should the workspace live?** A folder they control and back up — this should outlive
   any tool.
2. **Do they have an existing resume?** It is the fastest skeleton available.

```bash
jsk kb new <path> --name "Their Name"
```

That creates `career/store/`, holding an empty career and its log at revision 1, and
`applications/`. Everything after that goes in through `career_apply`. On a new record there is
nothing for `career_show` to show: `op:base` is 1.

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

Send `jsk-extractor` the workspace, the document (`sources/prior-resume.md`) and the skill
directory: it extracts roles, employers, dates, projects and metrics into one changeset and
previews it. Show them the diff, then apply the changeset it returns (`career_apply`). It lands `inferred`; then run the confirm lines the
agent proposed for what the document states — `career_confirm(ids=[...], source="<file>", quote="its
exact words")`, each number in the quote — and ask about every clause it quoted as its own. No
agents? Do the same inline (`references/kb-format.md` has the shapes).

An older **bundle** (`projects/` and `resume-generation/`) has no migration command: read it whole
and build the record from it like a resume — `jsk kb new`, then `jsk-extractor` per bundle file, each
changeset shown and applied through `career_apply`. A changeset cannot confirm, so it carries
`j:needs-verification` and `j:disputed` as the bundle held them and everything else lands `inferred`;
then `career_confirm(ids=[every id the bundle held confirmed], source="<bundle file>", quote="…")`.
Keep the bundle until they confirm the record is complete.

### Then go deeper

An old resume rarely captures what they **decided**, what constraint they were under, or what changed
as a result — the material that makes a senior resume work. Switch to `mode-braindump.md` and work
through their most significant projects.

## Phase 4: Prove it, on their data

1. Select a thin general resume from whatever the career now holds —
   `resume_select(target="resumes/general", mode="ranked")`; `references/mode-resume.md` for the
   procedure. The point is that the path works, not that the
   resume is finished.
2. Choose the region profile that matches where they are applying, and **say why**: India expects
   three pages, academic grades and a declaration block, Australia and the Gulf a work-rights line,
   and the paper size follows the region.
   Ask if their location does not make it obvious.
3. Validate, render and gate in one run, and show every step's output:

```bash
jsk resume ship resumes/general --pages 2
```

If the PDF step reports the resume **unverified**, say so plainly.

## Hand over

Tell them, in plain language and without the framework vocabulary:

- **Where the record is**, and that it is theirs — `career/store/`, opened only through `jsk`.
  Ask `career_view` to show it as a document; `jsk kb dump` writes it all out as text, and every write
  refreshes a copy in `.jsk/backup.trig`. Back the workspace up.
- **What works and what does not**, naming any gap left open and what it costs them.
- **The rhythm.** Something ships → `braindump`, while they still remember the details. Every quarter
  → `refresh`. Before applying → `gaps`, then `resume`. A specific role → `tailor`.
- **What the career now holds** — how many roles, projects and metrics, and what is `inferred`.
- **The biggest gap in their record right now** — a missing metric, an unconfirmed claim, a role with
  no evidence behind it.
