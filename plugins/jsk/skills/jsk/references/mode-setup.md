# Mode: setup

Create a bundle from nothing, or from an existing resume.

**`/jsk:setup` wraps this mode** with a toolchain check either side of it — preflight before,
a real render after. When someone arrives through that command, phases 1 and 2 have already run and
this file is phase 3; do not re-run preflight. When they arrive here directly, run it first, because
a bundle built on a toolchain that cannot render is a bundle nobody can use yet:

```bash
python3 <skill-dir>/scripts/preflight.py
```

## Ask two things

1. **Where should it live?** Default `career-okf/` in a folder they control. Version control is
   ideal — this should outlive any tool.
2. **Do they have an existing resume?** It is the fastest skeleton available.

## Create the skeleton

```bash
python3 <skill-dir>/scripts/init_bundle.py <path> --name "Their Name"
```

That creates directories, index files and an empty capability vocabulary — nothing else. The rules
and scripts stay with the skill, so a bundle is never stale.

If the script is unavailable, create the layout in `references/bundle-spec.md` by hand.

**Only if they ask to customise rendering**, seed `resume-generation/ats-rules.md`,
`writing-rules.md` or `structure-rules.md` from the references here. Those files override the
skill's defaults, so create them deliberately, not by habit — an absent file means "use the
defaults", which is what most people want.

## If they have a resume

Archive it verbatim at `sources/prior-resume.md`, then read it critically and record:

- What you removed and why — learning statements, repeated bullets, filler, references, home address
- Any **internal contradictions**. Old resumes often disagree with themselves on dates between a
  summary table and section headers. Log it in `open-questions.md`; a three-month discrepancy is
  exactly what a background check surfaces.
- Detail worth keeping that will not fit the current resume

Extract roles, employers, dates and projects into concepts. Mark everything `confirmed` if it came
from the document, and note the source.

## Then go deeper

An old resume describes what someone did. It rarely captures what they **decided**, what constraint
they were under, or what changed as a result — which is the material that makes a senior resume work.
Switch to `mode-braindump.md` and work through their most significant projects.

## Finish

Write `getting-started.md` explaining the modes in plain language. Run the validator. Append to
`log.md`. Then tell them what to do next — usually: fill the biggest gaps, then generate a resume.
