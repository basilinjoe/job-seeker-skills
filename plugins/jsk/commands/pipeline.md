---
description: What the job search needs from you this week - what has gone quiet, what is overdue, what you owe someone an answer on
argument-hint: "Optional: a path to the career folder, or a company name"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Pipeline

Work the application pipeline. This command is a shortcut into the skill's `pipeline` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="pipeline")
```

That loads `references/mode-pipeline.md`, which holds the procedure.

`$ARGUMENTS` may name the career folder, or a company - "have I been here before?" is
`ls applications/ | grep -i <company>`.

**Read every timeline before saying anything.** Stage, staleness and next action are derived from
each application's `# Timeline` and stored nowhere, so there is no status word that can disagree
with the events beneath it. Then lead with the two things that actually matter today rather than
reading the table out.

**Record events, never edit them.** A correction is a new row. Use the date it happened, use the
event vocabulary in `references/mode-pipeline.md` exactly - a synonym is a row that stops counting -
and put a `Due` date in when somebody commits to one.

If applications have no history beyond submission, work through them one at a time. `unknown` is a
legitimate date and an honest one; a plausible date is not.

**Before anything else, find `user-knowledgebase.md`.** Sessions do not share state, so never assume
one exists because it did last time. If there is none, say so and offer `/jsk:setup`.

Append a dated row to the knowledge base's `## Log` when the session ends.
