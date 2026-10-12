---
description: "Tailor your resume to a specific job posting: it scores your evidence against the posting, asks about the gaps, then writes the resume once. For a general resume, use resume."
argument-hint: "A posting URL, the job description pasted, or a path to a file; optionally a number of gap rounds"
allowed-tools: Read, Glob, Grep, AskUserQuestion, Skill, Task, mcp__plugin_jsk_graph__*
---

# Tailor

```
Skill(skill="jsk:jsk", args="tailor")
```

`references/mode-tailor.md` holds the procedure. `$ARGUMENTS` is the posting: a URL, the text,
or a file path (`.docx`, `.html`, `.txt`), each captured with `posting_capture`, plus an optional
number of gap rounds overriding the cap.
