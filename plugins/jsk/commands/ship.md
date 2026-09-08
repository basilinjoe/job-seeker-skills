---
description: Render a validated record, put it through all four gates, freeze what it was answering, and log the submission
argument-hint: "A resume.json path. Add --view ID, --template NAME, --ats-max, or --pages N."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Ship

Hand over a finished resume. This command is a shortcut into the skill's `ship` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="ship")
```

That loads `references/mode-ship.md`, which holds the procedure.

`$ARGUMENTS` names the record. If it is empty, look for `applications/*/resume.json` and any
`resume.json` beside the knowledge base, and ask which if there is more than one.

**The template defaults to the ink-only default.** `--template NAME` is the only way to get another;
`templates.md` has the catalogue. `--ats-max` is a separate axis and switches which variant the one
PDF holds - reach for it when the posting names a portal known to parse badly, or when the target is
a form rather than a person.

**Four gates, all of them, every time.** `jsk gates` runs the three mechanical ones in a single pass
and prints each verdict verbatim; the render gate is a person opening the PDF, and no command claims
it. Show that output rather than summarising it. Passing one gate says nothing about the others.

The record gate matters more than it used to: nothing compiles the record now, so an unrecognised key
is a section that renders as nothing, and `jsk validate` is the only thing that sees it.

`jsk-verifier` is for a failure that needs tracing back to the section it came from, not for a clean
pass — relaying three checkers is work the command does more cheaply.

A defect is repaired in `resume.json` and re-rendered - never patched into the `.tex` and never
worked around by loosening a check. If the record gate fails on freshly authored prose, that is the
`provenance_floor` doing its job: go back and get confirm-correct-or-cut on each clause.

**Nothing is frozen until every gate passes.** An archive of a document that was not sendable is
worse than no archive, because later it reads as though it was. What is frozen is the whole
application directory - the posting, the assessment, the record and the files actually sent - renamed
to the day it went out.

**Before anything else, find `user-knowledgebase.md`.** Sessions do not share state, so never assume
one exists because it did last time.

Append a dated row to the knowledge base's `## Log` when the session ends.
