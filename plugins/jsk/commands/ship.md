---
description: "The last step of resume and tailor: render, run every gate, and record the application as sent (or held back)."
argument-hint: "An application's stem, or resumes/<name>; optionally a template, ats-max or a page count"
allowed-tools: Read, Glob, Grep, AskUserQuestion, Skill, Task, mcp__plugin_jsk_graph__*
---

# Ship

```
Skill(skill="jsk:jsk", args="ship")
```

`references/mode-ship.md` holds the procedure. `$ARGUMENTS` names the selection, a stem or
`resumes/<name>`, plus optionally a template, `ats-max` or a page count.
Empty: `app_list`, and ask if more than one is unsent.
