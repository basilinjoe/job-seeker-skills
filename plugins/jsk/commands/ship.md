---
description: Render a validated record, put it through all four gates, freeze what it was answering, and log the submission
argument-hint: "A resume.json path. Add --view ID, --template NAME, --ats-max, or --pages N."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Ship

Hand over a finished resume. This command is a shortcut into the skill's `ship` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="ship")
```

That loads `references/mode-ship.md`, which holds the procedure.

`$ARGUMENTS` names the record. If it is empty, look for `tailoring/targets/*.resume.json` and
`resume-generation/resume.json`, and ask which if there is more than one.

**The template defaults to the ink-only default.** `--template NAME` is the only way to get another;
`templates.md` has the catalogue. `--ats-max` is a separate axis and switches which variant the one
PDF holds - reach for it when the posting names a portal known to parse badly, or when the target is
a form rather than a person.

**Four gates, all of them, every time.** `jsk-verifier` runs them and reports each verdict verbatim.
Show that output rather than summarising it. Passing one gate says nothing about the others.

A defect is repaired in `resume.json` and re-rendered - never patched into the `.tex` and never
worked around by loosening a check. If the record gate fails on freshly authored prose, that is the
`provenance_floor` doing its job: go back and get confirm-correct-or-cut on each clause.

**Nothing is frozen until every gate passes.** An archive of a document that was not sendable is
worse than no archive, because later it reads as though it was.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time.

Append a dated entry to the bundle's `log.md` when the session ends.
