---
description: Build a verified resume from the knowledge base - one PDF plus plain text, through all four gates
argument-hint: 'Optional: region code (au, in, ae) or a view id'
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Resume

Render a resume from the knowledge base. This command is a shortcut into the skill's `resume` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="resume")
```

That loads `references/mode-resume.md`, which holds the procedure.

`$ARGUMENTS` may name a region profile (`au`, `in`, `ae`) or a view id. If it names a region, use it
and say why it changes the document. If it is empty and their location is not obvious from the
knowledge base, ask before rendering - a photograph is conventional in one market and a liability in
another.

`--ats-max` in `$ARGUMENTS` renders the PDF in the ATS-maximal variant instead of the presentation
one. It switches the variant; it does not add a second file.

**All four gates must pass before handover, and their output must be shown.** A TeX engine is
required, not optional - the PDF is the only rendered deliverable, so without one there is nothing to
send and `jsk render --pdf` exits non-zero saying UNVERIFIED. Never treat a passing parse gate as
sufficient in its place.

**Before anything else, find `user-knowledgebase.md`.** Sessions do not share state, so never assume
one exists because it did last time. If there is none, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated row to the knowledge base's `## Log` when the session ends.
