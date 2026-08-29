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

`$ARGUMENTS` may hold a posting URL, the description itself, or a path to a file. **Fetch a URL
yourself** - the posting analyst has no network tools. Boards refuse often, so when a fetch fails say
what happened and ask them to paste it. That is an ordinary outcome, not an error.

**Gaps close before the resume is written.** Each round scores the record against the posting,
assesses it into a UGS gap document, and asks the whole queue at once. Answers go into the bundle
concepts *and* `record.json`, and the round runs again. The resume is authored once, at the end -
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
record together.

Finish by telling them where they fall short against this posting. Being flattered costs
interviews.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
