---
description: "Build one verified resume PDF from your career, through every gate. For a specific job posting, use tailor."
argument-hint: "Optional: a region (au, in or ae), or ats-max"
allowed-tools: Read, Glob, Grep, AskUserQuestion, Skill, Task, mcp__plugin_jsk_graph__*
---

# Resume

```
Skill(skill="jsk:jsk", args="resume")
```

`references/mode-resume.md` holds the procedure. `$ARGUMENTS` may name a region profile (`au`, `in`,
`ae`) or `ats-max` for the ATS-maximal variant of the one PDF.
