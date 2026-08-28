# Job Target template

One file per posting, at `tailoring/targets/<company>-<role>.md`. Written in step 1 of
`references/mode-tailor.md`, **before anything is generated**.

This is the **working copy**. It stays editable — the same employer posts again, a listing is
revised, the scorer is re-run. When something is actually submitted, step 5 freezes a copy of it into
`tailoring/applications/<company>-<role>.target.md` as `type: Source Document`, and that copy is what
the application was answering. Editing this file afterwards is expected and harmless; editing the
frozen one is not.

The frontmatter is not decoration. `score_projects.py` reads the requirement sets from it, so the
document a human reviews is the document that drives the ranking. A bespoke scorer that re-declares
the same sets in Python drifts from this file immediately, and then the frontmatter stops being true.

```markdown
---
type: Job Target
title: "Acme Corp - Solution Architect"
description: "Enterprise architecture role owning the integration platform."
tags: [healthcare, architecture]
timestamp: 2026-08-24T00:00:00Z
status: confirmed
company: "Acme Corp"
role: "Solution Architect"
source: "https://example.com/jobs/12345"
required_capabilities: [integration-architecture, stakeholder-management, data-sovereignty]
required_technologies: [azure, terraform]
domains: [healthcare]
seniority_sought: architecture-ownership
---

# Posting

The advertisement pasted verbatim. Listings get taken down and they will want the text at
interview.

# Evidence ranking

The output of `score_projects.py --markdown`, pasted. This is the checkpoint: the reasoning is
inspectable here, durably, rather than in a chat message that scrolls away.

# Gaps

What the posting wants that the bundle cannot evidence, written before generation rather than
discovered during it.

# Notes

What the posting says twice. Repetition marks the real priority, and it is often not the first
bullet.
```

## The frontmatter keys

| Key | Meaning |
|---|---|
| `required_capabilities` | The primary matching axis. Exact strings from `framework/capability-vocabulary.md` |
| `required_technologies` | Named stack. Leave the list empty when the posting names none — do not invent one |
| `domains` | Industry or context the posting operates in. Matched as a binary: any overlap, or none |
| `seniority_sought` | One value from the `seniority` vocabulary in `references/bundle-spec.md` |

**`required_capabilities` compares as exact strings.** A typo scores zero on every project and is
invisible in the ranking, which is why `score_projects.py` warns about any value absent from the
capability vocabulary. Decompose the posting into vocabulary values, not into its own phrasing;
mirror its exact wording in the *resume*, not here.

**Leave `required_technologies` empty when the posting names none.** Enterprise architecture
postings often name no stack at all. An empty list makes the technology term inert for every project,
which changes no ranking. Filling it with a stack the posting merely implies invents a requirement
and moves a x2 term — if you want to explore that, pass `--assume-technologies` to the scorer, which
labels the assumption in its output instead of burying it in the file.
