---
description: Build a verified resume from the bundle - two variants plus plain text, through all four gates
argument-hint: 'Optional: region code (au, in, ae) or a view id'
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Resume

Render a resume from the bundle. This command is a shortcut into the skill's `resume` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="resume")
```

That loads `references/mode-resume.md`, which holds the procedure.

`$ARGUMENTS` may name a region profile (`au`, `in`, `ae`) or a view id. If it names a region, use it
and say why it changes the document. If it is empty and their location is not obvious from the
bundle, ask before rendering - a photograph is conventional in one market and a liability in another.

**All four gates must pass before handover, and their output must be shown.** If no PDF renderer is
available, mark the resume unverified rather than treating a passing `check_ats.py` as sufficient.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
