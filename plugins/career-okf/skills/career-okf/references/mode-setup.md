# Mode: setup

Create a bundle from nothing, or from an existing resume.

## Ask two things

1. **Where should it live?** Default `career-okf/` in a folder they control. Version control is
   ideal — this should outlive any tool.
2. **Do they have an existing resume?** It is the fastest skeleton available.

## Create the skeleton

```bash
python3 scripts/init_bundle.py <path> --name "Their Name"
```

If the script is unavailable, create the layout in `references/bundle-spec.md` by hand, then seed
`framework/schema.md`, `framework/capability-vocabulary.md`,
`resume-generation/ats-rules.md`, `resume-generation/writing-rules.md` and
`resume-generation/structure-rules.md` from the references here — so the bundle carries its own rules
and they can edit them without touching the skill.

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
