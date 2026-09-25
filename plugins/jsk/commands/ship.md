---
description: Render a validated resume.json, put it through every gate, and freeze what it was answering
argument-hint: "A resume.json path. Add --template NAME, --ats-max, or --pages N."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Ship

```
Skill(skill="jsk:jsk", args="ship")
```

`references/mode-ship.md` holds the procedure. `$ARGUMENTS` names the `resume.json`, plus any of
`--template`, `--ats-max` and `--pages`. Empty: look for `applications/*/resume.json` and a
`resume.json` in the workspace, and ask if there is more than one.
