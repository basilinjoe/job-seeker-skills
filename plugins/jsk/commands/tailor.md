---
description: Tailor the resume to a specific job description - scores your evidence against the posting and tells you where you fall short
argument-hint: "A posting URL, the job description pasted, or a path to a file. Add --rounds N to change the gap-round cap."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Tailor

```
Skill(skill="jsk:jsk", args="tailor")
```

`references/mode-tailor.md` holds the procedure. `$ARGUMENTS` is the posting — a URL (fetch it
yourself), the text, or a file path — plus an optional `--rounds N` overriding the gap-round cap.
