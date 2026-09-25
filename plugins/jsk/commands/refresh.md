---
description: Periodic top-up of the career knowledge base - what changed, what numbers moved, what needs re-confirming
argument-hint: 'Optional: the period to cover, e.g. ''last quarter'''
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Refresh

```
Skill(skill="jsk:jsk", args="refresh")
```

`references/mode-refresh.md` holds the procedure. `$ARGUMENTS` may name a period; otherwise work
forward from the last entry of `career/log.ttl`.
