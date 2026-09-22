---
description: Render a validated record, put it through all four gates, freeze what it was answering, and log the submission
argument-hint: "A resume.json path. Add --view ID, --template NAME, --ats-max, or --pages N."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Ship

```
Skill(skill="jsk:jsk", args="ship")
```

`references/mode-ship.md` holds the procedure. `$ARGUMENTS` names the record, plus any of `--view`,
`--template`, `--ats-max` and `--pages`. Empty: look for `applications/*/resume.json` and a
`resume.json` beside the knowledge base, and ask if there is more than one.
