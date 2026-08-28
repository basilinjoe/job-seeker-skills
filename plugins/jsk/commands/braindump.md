---
description: Capture what you shipped - tell it about your work and it structures, verifies and files the result
argument-hint: 'Optional: what you want to talk about. Or just run it and start talking.'
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill
---

# Braindump

Capture work into the bundle. This command is a shortcut into the skill's `braindump` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="braindump")
```

That loads `references/mode-braindump.md`, which holds the procedure.

Ramble is the expected input. Take the whole thing before structuring any of it - interrupting
to impose format loses material people only surface once.

`$ARGUMENTS` may hold what they want to talk about. If it is empty, ask what they have been working
on and let them answer at length.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
