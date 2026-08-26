---
description: Periodic bundle top-up - what changed, what numbers moved, what needs re-confirming
argument-hint: 'Optional: the period to cover, e.g. ''last quarter'''
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Refresh

Top up the bundle. This command is a shortcut into the skill's `refresh` mode - it does not reimplement anything.

```
Skill(skill="career-okf:career-okf", args="refresh")
```

That loads `references/mode-refresh.md`, which holds the procedure.

`$ARGUMENTS` may name a period. Otherwise read `log.md` and work forward from the last entry.

Orient before asking anything - knowing what is already recorded is what makes the questions worth
answering.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/career-okf:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
