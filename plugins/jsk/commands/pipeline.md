---
description: What the job search needs from you this week - what has gone quiet, what is overdue, what you owe someone an answer on
argument-hint: "Optional: a bundle path, --all, or --company NAME"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Pipeline

Work the application pipeline. This command is a shortcut into the skill's `pipeline` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="pipeline")
```

That loads `references/mode-pipeline.md`, which holds the procedure.

`$ARGUMENTS` may name a bundle path, or pass `--all` or `--company NAME` straight through to the
script.

**Run the script before saying anything.** Stage, staleness and next action are derived from each
application's timeline; none of it is judged by eye. Then lead with the two things that actually
matter today rather than reading the table out.

**Record events, never edit them.** A correction is a new row. Use the date it happened, use the
vocabulary in `framework/pipeline-vocabulary.md`, and put a `Due` date in when somebody commits to
one.

If applications have no history beyond submission - the usual state after a migration - work through
them one at a time. `unknown` is a legitimate date and an honest one; a plausible date is not.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/jsk:setup`.

Append a dated entry to the bundle's `log.md` when the session ends.
