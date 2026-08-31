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
| `mode-ship.md` | A record is finished and needs rendering, checking, freezing and logging |
| `mode-refresh.md` | Periodic top-up: what changed, what numbers moved |
| `mode-gaps.md` | Resolving unanswered questions and unverified claims |
| `mode-pipeline.md` | Working the application pipeline: what is overdue, what to record, what to close |

## Specifications — the formats

| File | Defines |
|---|---|
| `bundle-spec.md` | Bundle layout on disk, concept file format, frontmatter schema, selection keys, concept types |
| `urs-spec.md` | The URS record: document shape, core types, region profiles, conformance levels |
| `view-format.md` | The other half of URS: every key a view may carry, and the rule that it may carry no prose |
| `write-commands.md` | Writing a concept with a command instead of by hand: `okf project add`, the files one write implies, and where the commands stop |

`urs-spec.md` and `view-format.md` are one specification in two files, split because
`jsk-resume-author` writes views and never writes a record. **Neither restates the other**, and each
carries a pointer to its other half — a key belongs in exactly one of them.

## Rules — what good looks like

| File | Covers |
|---|---|
| `writing-rules.md` | X-Y-Z bullets, verb accuracy, phrases to cut, phrases that damage seniority |
| `ats-rules.md` | Hard rules for both variants, the two-variant strategy, keyword placement, what `check_ats.py` verifies |
| `templates.md` | The five visual templates, what each is for, and the design rules behind them |

## Reasoning

| File | Covers |
|---|---|
| `rationale.md` | Why each rule exists, with the failure behind it, and how to explain it to a person |

Load `rationale.md` when someone questions a rule or you need to justify one. The rules themselves
carry a compressed reason in `SKILL.md`; this is the long form.

## A bundle's own rules win

If the person's bundle has `resume-generation/*.md`, those override anything here. Setup does not
scaffold them, so their presence means somebody customised deliberately.
