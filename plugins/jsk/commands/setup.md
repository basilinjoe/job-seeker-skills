---
description: Set up jsk end to end - check the toolchain, close the gaps, create or adopt a career knowledge base, and prove the pipeline works
argument-hint: Optional path for the knowledge base, or a path to an existing resume to import
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill
---

# Set up jsk

Get this machine from nothing to a working, verified resume pipeline. Four phases, in order, and
**do not skip phase 1** — every later phase depends on knowing what actually runs here.

`$ARGUMENTS` may hold a path. If it points at a `.docx`, `.pdf` or `.md` resume, treat it as a
document to import in phase 3. If it looks like a directory, that is where the knowledge base goes.
If it is empty, ask.

## Phase 1: Find out what works

The skill directory is `${CLAUDE_PLUGIN_ROOT}/skills/jsk`. Run:

```bash
jsk doctor
```

On Windows use `python` or `py -3`. Bare `jsk doctor` is the verifying run: it renders the shipped
example document end to end and runs every gate, so a pass here means the pipeline genuinely works on
this machine rather than looking like it should.

**Show the output.** Then read the verdict:

| Verdict | What to do |
|---|---|
| `READY` | Everything works, PDF included. Go to phase 3. |
| `READY, with gaps` | The core pipeline works. Go to phase 2 and offer to close the gaps. |
| `BLOCKED` | The install is broken — modules or schema missing. Fix that first; nothing else is worth doing. |
| `BROKEN` | The toolchain is present but failed its own gates. This is a bug in the skill, not in their setup. Report the failing step verbatim rather than working around it. |

## Phase 2: Close the gaps — with permission, never silently

The doctor prints what each gap *disables* and the exact command to fix it. Relay both, then ask
before running anything. Installing software is theirs to authorise, and a TeX distribution can be
several gigabytes.

Use `AskUserQuestion` to offer the choice rather than assuming:

- **The TeX engine is not optional.** The PDF is the only rendered deliverable, so without an engine
  there is nothing to send, nothing to check and nothing to measure — the doctor reports **BLOCKED**,
  not a gap. `tectonic` is a single self-contained binary and is the right recommendation; MiKTeX and
  TeX Live are worth it only if they already wanted them.
- **pymupdf is not optional either.** The parse gate reads the PDF's text through it and the fitter
  measures the pages through it. Without it the parse gate and the page budget are both
  unverifiable. One `pip install`.

That is the whole list. There used to be two more — `pyyaml` to read a bundle's frontmatter and
`jsonschema` to check the record's shape — and both left with the bundle format. Nothing imports
either one now.

Re-run the doctor after any install. An install nobody verified is a claim, not a fix.

## Phase 3: Create or adopt the knowledge base

Invoke the skill's own setup mode rather than reimplementing it — it holds the interview logic, and
this command is not the place to fork it:

```
Skill(skill="jsk:jsk", args="setup")
```

That reads `references/mode-setup.md` and handles all three paths: a knowledge base from nothing, one
built from an existing resume, and one migrated from an older bundle. Three things worth getting
right while it runs:

- **Location.** Default `career/` somewhere they control, ideally under version control. This should
  outlive any single tool, including this one.
- **An existing resume is the fastest skeleton available.** If `$ARGUMENTS` named one, or they have
  one anywhere, use it. Keep it verbatim beside the knowledge base before extracting anything.
- **`## Identity` first.** Without an email and a phone number the parse gate fails, so until that
  block is complete nothing sendable can render. It is the most common thing left empty.

There is nothing to validate at this stage. `jsk validate` checks the URS record, and there is not
one yet — the knowledge base is prose, and phase 4 is what proves it can produce a document.

## Phase 4: Prove it, on their data

A pipeline verified against the shipped example is a pipeline verified against someone else's career.
Close the loop on theirs.

1. Write a URS record from whatever the knowledge base now holds — `references/urs-spec.md` for the
   format, `references/mode-resume.md` for the procedure. Thin is fine at this stage; the point is
   that the path works, not that the resume is finished. Save it as `resume.json` beside the
   knowledge base.
2. Pick the region profile that matches where they are applying, and say why you picked it. This is
   the decision people do not know they are making: a photograph and date of birth are conventional
   on a Gulf resume and a liability on an Australian one, India expects academic grades and a
   declaration block, and the region-neutral default forbids all of it. Ask if it is not obvious from
   their location.
3. Validate, render, gate:

```bash
jsk validate resume.json
jsk render resume.json --out . --view <id> --pdf
jsk gates . --pages 2
```

Show every gate's output. If the PDF step reports the resume **unverified**, say so plainly rather
than delivering files that look finished.

## Then hand over

Tell them, in plain language and without the framework vocabulary:

- **Where the file is**, and that it is theirs — one Markdown document, readable in any editor, worth
  putting in git.
- **What works and what does not**, naming any gap left open and what it costs them.
- **The rhythm.** Something ships → `braindump`, five minutes, while they still remember the details.
  Every quarter → `refresh`. Before applying → `gaps`, then `resume`. A specific role → `tailor`.
- **The biggest gap in their record right now** — a missing metric, an unconfirmed claim, a role with
  no evidence behind it. This is the most useful sentence in the whole session, and it is the one they
  cannot get anywhere else. A named gap can be filled; a compliment cannot.

Append a dated row to the knowledge base's `## Log` covering what was set up and what was left open.
