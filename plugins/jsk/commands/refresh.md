---
description: Periodic top-up of the career knowledge base - what changed, what numbers moved, what needs re-confirming
argument-hint: 'Optional: the period to cover, e.g. ''last quarter'''
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Refresh

Top up the knowledge base. This command is a shortcut into the skill's `refresh` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="refresh")
```

That loads `references/mode-refresh.md`, which holds the procedure.

`$ARGUMENTS` may name a period. Otherwise read `log.md` and work forward from the last entry.

Orient before asking anything - knowing what is already recorded is what makes the questions worth
answering.

**Before anything else, find `user-knowledgebase.md`.** Sessions do not share state, so never assume
one exists because it did last time. If there is none, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated row to the knowledge base's `## Log` when the session ends.
