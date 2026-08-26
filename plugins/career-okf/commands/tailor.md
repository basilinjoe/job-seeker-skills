---
description: Tailor the resume to a specific job description - scores your evidence against the posting and tells you where you fall short
argument-hint: Paste the job description, or a path to a file containing it
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Tailor

Tailor to a posting. This command is a shortcut into the skill's `tailor` mode - it does not reimplement anything.

```
Skill(skill="career-okf:career-okf", args="tailor")
```

That loads `references/mode-tailor.md`, which holds the procedure.

`$ARGUMENTS` may hold the job description, or a path to one. If it is empty, ask them to paste it.

**Tailoring selects; it never invents.** A view references evidence by id and reorders it. If the
posting wants something the record has no evidence for, that is a gap to report - not a bullet to
write.

Finish by telling them where they fall short against this posting. Being flattered costs
interviews.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/career-okf:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
