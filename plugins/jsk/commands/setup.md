---
description: Set up jsk end to end - check the toolchain, close the gaps, create or import a career knowledge base, and prove the pipeline works
argument-hint: Optional path for the workspace, or a resume to import
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, mcp__plugin_jsk_graph__*
---

# Set up jsk

```
Skill(skill="jsk:jsk", args="setup")
```

`references/mode-setup.md` holds the procedure. `$ARGUMENTS` may be a `.docx`, `.pdf` or `.md`
resume to import, or a directory for the knowledge base; empty, ask.
