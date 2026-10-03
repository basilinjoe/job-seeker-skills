---
description: Render a validated resume selection, put it through every gate, and freeze what it was answering
argument-hint: "An application's stem, resumes/<name>, or a resume.json. Add --template NAME, --ats-max, or --pages N."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task, mcp__plugin_jsk_graph__*
---

# Ship

```
Skill(skill="jsk:jsk", args="ship")
```

`references/mode-ship.md` holds the procedure. `$ARGUMENTS` names the selection - a stem,
`resumes/<name>`, or a `resume.json` - plus any of `--template`, `--ats-max` and `--pages`.
Empty: `app_list`, and ask if more than one is unsent.
