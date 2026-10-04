---
description: "Go over your career: what has happened since last time, what is unconfirmed or missing a number, what needs re-confirming. For new material, use intake."
argument-hint: "Optional: the period to cover, such as last quarter"
allowed-tools: Read, Glob, Grep, AskUserQuestion, Skill, Task, mcp__plugin_jsk_graph__*
---

# Review

```
Skill(skill="jsk:jsk", args="review")
```

`references/mode-review.md` holds the procedure. `$ARGUMENTS` may name a period; otherwise work
forward from the newest entry, the first entry `career_log` returns.
