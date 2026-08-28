---
description: Tailor the resume to a specific job description - scores your evidence against the posting and tells you where you fall short
argument-hint: "Paste the job description, or a path to a file containing it. Add --ats-max for the ATS-maximal variant."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Task
---

# Tailor

Tailor to a posting. This command is a shortcut into the skill's `tailor` mode - it does not reimplement anything.

```
Skill(skill="jsk:jsk", args="tailor")
```

That loads `references/mode-tailor.md`, which holds the procedure.

`$ARGUMENTS` may hold the job description, or a path to one. If it is empty, ask them to paste it.

**`--ats-max` in `$ARGUMENTS`** means render the PDF in the ATS-maximal variant instead of the
presentation one: pass `--ats-max` through to `render_resume.py`. It *switches* the variant - one
posting in, one PDF out - it does not add a second file.

Reach for it when the posting names a portal known to parse badly (Workday, Taleo, SuccessFactors,
Naukri) or when the target is unknown and the submission is through a form rather than a person. The
presentation variant is right for a referral, a direct email, or anything a human opens first. When
in doubt, ATS-maximal: a plain resume that parses beats a beautiful one that arrives fragmented.

The ATS-maximal render is deliberately longer - it repeats the employer on every role line and
expands the skills block with keyword aliases - so it carries its own page budget,
`budget.ats_maximal_pages` on the view. Do not cut evidence to force it onto the presentation
variant's budget; a parser does not care about length.

**Tailoring selects; it never invents.** A view references evidence by id and reorders it. If the
posting wants something the record has no evidence for, that is a gap to report - not a bullet to
write.

Finish by telling them where they fall short against this posting. Being flattered costs
interviews.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/jsk:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
