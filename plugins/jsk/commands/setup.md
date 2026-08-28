---
description: Set up jsk end to end - check the toolchain, close the gaps, create or adopt a career bundle, and prove the pipeline works
argument-hint: Optional path for the bundle, or a path to an existing resume to import
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill
---

# Set up jsk

Get this machine from nothing to a working, verified resume pipeline. Four phases, in order, and
**do not skip phase 1** — every later phase depends on knowing what actually runs here.

`$ARGUMENTS` may hold a path. If it points at a `.docx`, `.pdf` or `.md` resume, treat it as a
document to import in phase 3. If it looks like a directory, that is where the bundle goes. If it is
empty, ask.

## Phase 1: Find out what works

The skill directory is `${CLAUDE_PLUGIN_ROOT}/skills/jsk`. Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/jsk/scripts/preflight.py --verify
```

On Windows use `python` or `py -3`. `--verify` renders the shipped example document end to end and
runs every gate, so a pass here means the pipeline genuinely works on this machine rather than
looking like it should.

**Show the output.** Then read the verdict:

| Verdict | What to do |
|---|---|
| `READY` | Everything works, PDF included. Go to phase 3. |
| `READY, with gaps` | The core pipeline works. Go to phase 2 and offer to close the gaps. |
| `BLOCKED` | The skill install is broken — scripts or schema missing. Fix that first; nothing else is worth doing. |
| `BROKEN` | The toolchain is present but failed its own gates. This is a bug in the skill, not in their setup. Report the failing step verbatim rather than working around it. |

## Phase 2: Close the gaps — with permission, never silently

Preflight prints what each gap *disables* and the exact command to fix it. Relay both, then ask
before running anything. Installing software is theirs to authorise, and a TeX distribution can be
several gigabytes.

Use `AskUserQuestion` to offer the choice rather than assuming:

- **The TeX engine is not optional.** The PDF is the only rendered deliverable, so without an engine
  there is nothing to send, nothing to check and nothing to measure — preflight reports **BLOCKED**,
  not a gap. `tectonic` is a single self-contained binary and is the right recommendation; MiKTeX and
  TeX Live are worth it only if they already wanted them.
- **pymupdf is not optional either.** `check_ats.py` reads the PDF's text through it and
  `fit_pages.py` measures the pages through it. Without it the parse gate and the page budget are
  both unverifiable. One `pip install`.
- **pyyaml** is needed to read the bundle at all — `validate_bundle.py` and `score_projects.py` both
  fail without it. Recommend installing it.
- **jsonschema** catches a mistyped key in the URS record. Without it the structural rules still run,
  but an unrecognised key is a field that vanishes with nothing reporting it. Cheap; recommend it.

Re-run preflight after any install. An install nobody verified is a claim, not a fix.

## Phase 3: Create or adopt the bundle

Invoke the skill's own setup mode rather than reimplementing it — it holds the interview logic, and
this command is not the place to fork it:

```
Skill(skill="jsk:jsk", args="setup")
```

That reads `references/mode-setup.md` and handles both paths: a bundle from nothing, or a bundle built
from an existing resume. Two things worth getting right while it runs:

- **Location.** Default `career/` somewhere they control, ideally under version control. This
  should outlive any single tool, including this one.
- **An existing resume is the fastest skeleton available.** If `$ARGUMENTS` named one, or they have
  one anywhere, use it. Archive it verbatim at `sources/prior-resume.md` before extracting anything.

Then validate:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/jsk/scripts/validate_bundle.py <bundle>
```

## Phase 4: Prove it, on their data

A pipeline verified against the shipped example is a pipeline verified against someone else's career.
Close the loop on theirs.

1. Build a URS record from whatever the bundle now holds — `references/urs-spec.md` for the format,
   `references/mode-resume.md` for the procedure. Thin is fine at this stage; the point is that the
   path works, not that the resume is finished.
2. Pick the region profile that matches where they are applying, and say why you picked it. This is
   the decision people do not know they are making: a photograph and date of birth are conventional
   on a Gulf resume and a liability on an Australian one, India expects academic grades and a
   declaration block, and the region-neutral default forbids all of it. Ask if it is not obvious from
   their location.
3. Validate, render, gate:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/jsk/scripts/validate_urs.py <bundle>/resume-generation/resume.json
python3 ${CLAUDE_PLUGIN_ROOT}/skills/jsk/scripts/render_resume.py <bundle>/resume-generation/resume.json --out . --pdf
python3 ${CLAUDE_PLUGIN_ROOT}/skills/jsk/scripts/check_ats.py <Name>_Resume.pdf
python3 ${CLAUDE_PLUGIN_ROOT}/skills/jsk/scripts/check_prose.py <Name>_Resume.tex
```

Show every gate's output. If the PDF step reports the resume **unverified**, say so plainly rather
than delivering files that look finished.

## Then hand over

Tell them, in plain language and without the framework vocabulary:

- **Where the bundle is**, and that it is theirs — plain Markdown, readable in any editor, worth
  putting in git.
- **What works and what does not**, naming any gap left open and what it costs them.
- **The rhythm.** Something ships → `braindump`, five minutes, while they still remember the details.
  Every quarter → `refresh`. Before applying → `gaps`, then `resume`. A specific role → `tailor`.
- **The biggest gap in their record right now** — a missing metric, an unconfirmed claim, a role with
  no evidence behind it. This is the most useful sentence in the whole session, and it is the one they
  cannot get anywhere else. A named gap can be filled; a compliment cannot.

Append a dated entry to the bundle's `log.md` covering what was set up and what was left open.
