---
description: Build a verified resume from the knowledge base - one PDF plus plain text, through every gate
argument-hint: 'Optional: region code (au, in, ae) or a view id'
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Resume

```
Skill(skill="jsk:jsk", args="resume")
```

`references/mode-resume.md` holds the procedure. `$ARGUMENTS` may name a region profile (`au`, `in`,
`ae`), a view id, or `--ats-max` for the ATS-maximal variant of the one PDF.
