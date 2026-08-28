# Career OKF: making the plugin easier to understand and handle

**Date:** 2026-08-25
**Status:** implemented — see *Outcome* at the end

## Problem

Career OKF is a disciplined plugin with a comprehension problem. Every reference file has a clear
job, the headings are consistent, and nothing is tracked that shouldn't be. The difficulty is what a
newcomer meets first.

- The README spends ~200 lines arguing *why* the design is right before a reader learns what to type.
- Ten pieces of vocabulary — bundle, OKF, URS, view, region profile, provenance status, four gates,
  two variants, presentation vs ATS-maximal — arrive at once, with no progressive introduction.
- Nine scripts and six modes are presented flat, with no signal that day one needs two of them.
- `urs-spec.md` is 376 lines; `urs/plan.py` is 614.

Three audiences suffer differently: the job seeker who wants a resume, the maintainer who edits the
skill later, and Claude itself, which must route correctly and not shortcut a gate.

## Constraints

Frozen, because this is a published v1.3.0 with script names appearing ~90 times across the docs:

- **Script names and CLI flags.** `check_ats.py`, `render_resume.py`, `--strict`, `--level N` and the
  rest are public API. Internals may be refactored freely; the invocation surface may not move.
- **Bundle layout on disk.** `projects/`, `achievements/`, `resume-generation/` and siblings keep
  their names and meaning, so bundles built against v1.3.0 need no migration.
- **URS schema and gate behaviour.** `urs-v1.schema.json` stays wire-compatible and every gate keeps
  failing on exactly what it fails on today.

Additionally discovered during design: the test suite makes 108 `assertIn` assertions against script
output. Verdict strings (`PASS - safe to send`, `DO NOT SEND`, `does not open on a verb`) are
effectively API. Output may be *added to*; existing lines may not be reworded.

Explicitly **not** frozen: the prose voice. The essayistic, reason-giving register is a real
differentiator, but argument-per-paragraph density is part of the load a newcomer carries. It is a
lever, kept where it serves and trimmed where it tolls.

## Approach

Three stages, sequenced so each ships independently and work can stop after any of them. Docs first,
because that is where the pain concentrates and the regression risk is nil; command surface second,
additive so nothing breaks; internal splits last, behind the frozen contracts with the existing
9-file test suite as the net.

### Stage 1 — Documentation architecture

New `docs/` at the repo root:

| File | Job |
|---|---|
| `QUICKSTART.md` | Install, `/jsk:setup`, first resume. Imperative, no rationale, no unmet vocabulary. |
| `CONCEPTS.md` | The glossary in one screen. Each term: one sentence of definition, one line of why it matters. |
| `WHY.md` | The design rationale lifted from the README. The current voice lives here. |
| `ARCHITECTURE.md` | Maintainer map: annotated tree, data flow, a *where do I change X* table, test layout, release ritual. |
| `SCRIPTS.md` | The nine-script reference: flags, dependencies, exit codes. |

`README.md` is rewritten to roughly 70 lines: what it is, three differentiators, install, the one
command, the mode table, the rhythm, and a nav block. The reader learns what to type before they
learn why it is designed that way.

`SKILL.md` is rewritten to roughly 120 lines. **The frontmatter is untouched** — that `description`
block is the router, and degrading it degrades triggering.

**The risk, and the rule that manages it.** The justification passages in `SKILL.md` are not
decoration. "A page count nobody measured is a page count nobody knows" is *why* the agent does not
shrug off a missing renderer. Stripping them yields an agent that shortcuts gates. Therefore: every
hard rule keeps a compressed one-line reason inline, and only long-form narrative — the tofu-box
story, the two-documents-drift essay — moves to `references/rationale.md`, which the agent loads when
it needs to explain a rule to a person. Compliance pressure stays; the essay moves.

`references/README.md` is added as a nav index for the reference files.

### Stage 2 — Command surface

- One thin command per mode: `commands/braindump.md`, `resume.md`, `tailor.md`, `refresh.md`,
  `gaps.md`. Each delegates to the skill with the mode as its argument, so nobody has to learn that
  "modes" exist in order to use one. `setup.md` stays as it is — it is a genuine four-phase procedure,
  not a delegation.
- `scripts/okf.py`, a dispatcher over the existing nine (`okf check`, `okf render`, `okf verify`,
  `okf new`, `okf score`). The nine stay callable directly, unchanged, and remain the documented
  stable API. The dispatcher is a convenience, never a replacement.
- Failure output gains a `fix:` line where a script exits on a missing dependency. Additive only —
  existing verdict lines are left byte-identical because the tests assert on them.

### Stage 3 — Internal splits

- `urs/plan.py` (614 lines) splits into `urs/format.py` (the `fold_ascii` / `fmt_*` / `period_key`
  helpers) and `urs/resolve.py` (the `Resolver` class and `build`). `plan.py` remains as a facade
  re-exporting both, so `from urs import plan as planner` and `planner.build(...)` keep working
  unchanged.
- `references/urs-spec.md` (376 lines) splits into a normative spec — document shape, core types,
  views, region profiles, conformance — and `docs/urs-guide.md` for the discursive material: why not
  JSON Resume, evolution, deliberate exclusions, the worked example walkthrough.

## Verification

- `python -m unittest discover -s tests` passes unchanged after every stage. No test is edited to
  accommodate a change; a failing test means the change was wrong.
- `preflight.py --verify` still reaches its verdict.
- Every internal doc link resolves.
- `SKILL.md` frontmatter is byte-identical before and after.

## Out of scope

Renaming scripts, changing bundle layout, altering schema or gate behaviour, and reworking existing
verdict strings. All are frozen above.

## Outcome

All three stages shipped. 243 tests pass (228 before, plus 15 new for the dispatcher), no existing
test was edited, `preflight.py --verify` still reaches `READY, with gaps`, and all 28 internal
documentation links resolve. `SKILL.md` frontmatter is byte-identical to the previous commit.

| File | Before | After |
|---|---|---|
| `README.md` | 208 | 110 |
| `SKILL.md` | 184 | 179 |
| `urs-spec.md` | 376 | 367 |
| `urs/plan.py` | 614 | 23 facade + 517 `resolve.py` + 95 `formatting.py` |

New: `docs/` (776 lines across six documents), `references/rationale.md`, `references/README.md`,
five mode commands, `scripts/okf.py`, `tests/test_okf.py`.

**Two honest notes on where the design over-promised.**

*`SKILL.md` barely shrank* — 184 to 179 lines, against a predicted ~120. The file was already
operational rather than padded: what came out (the tofu-box narrative, the drift essay, the
answerable-a-year-later passage) was replaced by compressed one-line reasons, per the rule above, plus
a uniform exit-code line and a pointer to `rationale.md`. Cutting further would have meant removing
compliance pressure, which was the one thing the design said not to do. The comprehension win for the
agent is the restructure — a reference index, a rationale file loaded only when explaining — not the
line count.

*The `urs-spec.md` split returned 9 lines*, not the substantial reduction implied. Only three of its
sections were genuinely discursive; `Evolution` reads as prose but carries normative MUSTs and stayed
put. The real gain was additive: `docs/urs-guide.md` gives a human a way into URS that is not a
376-line normative spec.

**Found and fixed along the way**, both outside the original scope:

- `validate_bundle.py` imported `yaml` bare, so a missing pyyaml produced a raw traceback where
  `score_projects.py` printed a helpful line for the identical situation. Now guarded to match.
- `urs/plan.py` defined `SENIORITY_LABEL`, a 10-line lookup table referenced nowhere in the scripts
  or the tests. Removed during the split.

**Not done, and deliberately left for a release decision:** the version in
`plugins/jsk/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` is still
`1.3.0`. Five new commands and a new script are user-visible additions and want a minor bump when
this ships.
