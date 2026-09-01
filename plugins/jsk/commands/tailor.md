---
description: Tailor the resume to a specific job description - scores your evidence against the posting and tells you where you fall short
argument-hint: "A posting URL, the job description pasted, or a path to a file. Add --rounds N to change the gap-round cap."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Tailor

Tailor to a posting. This command is a shortcut into the skill's `tailor` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="tailor")
```

That loads `references/mode-tailor.md`, which holds the procedure.

**Ask the pipeline whether they have been here before, first.**

```bash
okf pipeline <bundle> --company "<name>"
```

Before the posting is written down and before anything is scored. Applying twice is ordinary, which
is why this is a check and not a prohibition - the second round is often right, and it is only right
on purpose. If anything comes back, show the stem, the role, the stage derived from its timeline and
the date of the last event, then stop and let them decide. That decision is theirs and it comes
before the work.

`$ARGUMENTS` may hold a posting URL, the description itself, or a path to a file. **Fetch a URL
yourself** - the analyst has no network tools. Boards refuse often, so when a fetch fails say
what happened and ask them to paste it. That is an ordinary outcome, not an error.

**Gaps close before the resume is written.** Each round scores the record against the posting,
assesses it into `<slug>.gaps.md`, and asks the whole queue at once. Answers go into the bundle
concepts - the only place there is - and the record recompiles. The resume is authored once, at the end -
there is no reason to write a document from a record you are about to change.

**Offer the skip every round.** It is the ordinary exit, not a failure. The loop also ends by itself
when there is nothing left worth asking, when only `unexplored` questions remain, when a round
produces no new answerable question, or at three rounds. Say which reason ended it: "nothing left to
ask" and "you hit the cap with four things open" call for different next moves.

**Tailoring selects; it never invents.** A view references evidence by id and reorders it. If the
posting wants something the record has no evidence for, that is a gap to report - not a bullet to
write. `jsk-resume-author` marks everything it wrote `inferred`, and a `provenance_floor: confirmed`
view will not render it until the person has confirmed each clause. Read those quotes back to them.

Rendering is `/jsk:ship`, which runs all four gates and freezes the posting, the assessment and the
view together under `tailoring/applications/<yyyy>/`. The record is not copied: it compiles from
concepts that are in git, so the resume this application sent rebuilds from the commit it was sent at.

Finish by telling them where they fall short against this posting. Being flattered costs
interviews.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
