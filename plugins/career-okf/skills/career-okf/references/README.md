# References

What the skill loads on demand. `SKILL.md` stays small by keeping everything here and reading only
what the current task needs.

## Modes — one procedure each

| File | Run it when |
|---|---|
| `mode-setup.md` | No bundle exists, or one is being built from an existing resume |
| `mode-braindump.md` | They are telling you about their work |
| `mode-resume.md` | They need a resume — the full JSON-first build order |
| `mode-tailor.md` | A specific job description is on the table |
| `mode-refresh.md` | Periodic top-up: what changed, what numbers moved |
| `mode-gaps.md` | Resolving unanswered questions and unverified claims |

## Specifications — the formats

| File | Defines |
|---|---|
| `bundle-spec.md` | Bundle layout on disk, concept file format, frontmatter schema, selection keys, concept types |
| `urs-spec.md` | The URS record: document shape, core types, views, region profiles, conformance levels |
| `target-template.md` | The Job Target file, including the frontmatter `score_projects.py` reads |

## Rules — what good looks like

| File | Covers |
|---|---|
| `writing-rules.md` | X-Y-Z bullets, verb accuracy, phrases to cut, phrases that damage seniority |
| `ats-rules.md` | Hard rules for both variants, the two-variant strategy, keyword placement, what `check_ats.py` verifies |

## Reasoning

| File | Covers |
|---|---|
| `rationale.md` | Why each rule exists, with the failure behind it, and how to explain it to a person |

Load `rationale.md` when someone questions a rule or you need to justify one. The rules themselves
carry a compressed reason in `SKILL.md`; this is the long form.

## A bundle's own rules win

If the person's bundle has `resume-generation/*.md`, those override anything here. Setup does not
scaffold them, so their presence means somebody customised deliberately.
