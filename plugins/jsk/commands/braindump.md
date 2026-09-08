---
description: Capture what you shipped - tell it about your work and it structures, verifies and files the result
argument-hint: 'Optional: what you want to talk about. Or just run it and start talking.'
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill
---

# Braindump

Capture work into the knowledge base. This command is a shortcut into the skill's `braindump` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="braindump")
```

That loads `references/mode-braindump.md`, which holds the procedure.

Ramble is the expected input. Take the whole thing before structuring any of it - interrupting
to impose format loses material people only surface once.

**Everything goes into one file**, under the headings `references/kb-spec.md` describes. Grep a
distinctive phrase before adding anything - people re-tell the same work months apart in different
words, and two entries for one project split its bullets so neither reads as evidence.

`$ARGUMENTS` may hold what they want to talk about. If it is empty, ask what they have been working
on and let them answer at length.

**Before anything else, find `user-knowledgebase.md`.** Sessions do not share state, so never assume
one exists because it did last time. If there is none, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated row to the knowledge base's `## Log` when the session ends.
