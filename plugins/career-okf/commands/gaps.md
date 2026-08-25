---
description: Find and close what is missing - unconfirmed claims, missing metrics, roles with no evidence behind them
argument-hint: Optional: a bundle path
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill
---

# Gaps

Resolve open questions in the bundle. This command is a shortcut into the skill's `gaps` mode - it does not reimplement anything.

```
Skill(skill="career-okf:career-okf", args="gaps")
```

That loads `references/mode-gaps.md`, which holds the procedure.

Run this before applying anywhere. It works through `inferred` claims that need sign-off, bullets
with no metric behind them, and territory the record never covered.

End by naming the single biggest gap in their record. A named gap can be filled; a compliment
cannot.

**Before anything else, find the bundle.** Sessions do not share state, so never assume one exists
because it did last time. If there is no bundle, say so and offer `/career-okf:setup` - but if what
they asked for can be delivered anyway, deliver it first and offer to capture it afterwards.

Append a dated entry to the bundle's `log.md` when the session ends.
