# What a tailoring run costs, and what to do about it

**Status:** design, approved 2026-08-31
**Scope:** `jsk` internals only. No change to what a resume says.

A tailoring run costs about **42,900 tokens of mandated reading and 12.3 seconds of script
time**, and spawns three subagents. Almost none of that is the work; most of it is the same
bundle being compiled seven times, and one agent reading a specification it mostly does not
need.

This document says what to change, in what order, and what not to change.

## The measurement

Taken on a synthetic 100-application bundle (760 files, 25 projects, 6 roles), against the
tree at `288280a`. Reads are counted from what `mode-tailor.md` and the agent files actually
instruct; they exclude model reasoning and the conversation itself, so the real figure is
higher.

| | tokens |
|---|---|
| main: `SKILL.md` + `mode-tailor.md` + `mode-ship.md` | 8,230 |
| `jsk-resume-author` — def 3,040 · record 7,717 · `urs-spec` 4,127 · `ats-rules` 2,396 · `writing-rules` 1,039 · posting+gaps ~2,500 | 20,819 |
| `jsk-tailor-analyst` — def 2,401 · record 7,717 · posting ~1,500 | 11,618 |
| `jsk-verifier` — def 1,236 · gate output ~1,000 | ~2,200 |
| **per run** | **42,867** |

Script wall clock, measured through the CLI as an agent invokes it:

| | ms |
|---|---|
| bare Python interpreter start | 109 |
| `okf_compile` (CLI) | 1,271 |
| `okf_compile` (`load()`, in process) | 440 |
| `validate_urs` (bundle) | 1,147 |
| `render_resume --pdf` | 2,292 |
| the five mechanical gate commands, together | 924 |

**The bundle is compiled seven times per run**: main's recompile after the answers, the
analyst's `--dump-record`, `okf score` compiling again inside itself, the author's
`--dump-record`, and `validate_urs <bundle>` compiling on each of its three invocations.

The cost is not process startup. A compile of a *tiny* bundle costs 166ms, so that is the
startup floor; the 100-job bundle costs 1,024ms, and the ~860ms difference is the walk itself.
And the walk is the thing worth attacking, because of what it reads:

| concept type parsed | count | read by `load()`? |
|---|---|---|
| Gap Assessment | 100 | **no** |
| Job Posting | 100 | **no** |
| View | 100 | only when views are asked for |
| Project · Role · Organisation · Person · Metric Set · Skill Set · Vocabulary | 45 | yes |

**The compile parses 345 concepts to build a record out of 41 of them.** `Gap Assessment` and
`Job Posting` are absent from `NON_CONTENT`, so they are read, YAML-parsed, bucketed into
`by_type` and then never looked at again.

## What is not on the table

**No cached record, on disk or in a daemon.** `bundle-spec.md` argues the case already — *a
cache of a file you can regenerate in under a second is a liability rather than an asset* —
and every defect the 2.2.0 audit found came from a copy of something that could disagree with
its source. Everything below either passes an already-compiled record along a call chain or
does less work. Nothing remembers.

**No trading output quality for tokens.** This plugin exists to produce resumes somebody can
defend in an interview. A cheaper run that authors weaker bullets is a loss, not a saving. A
read is removed only where it can be shown to be unnecessary, never on the grounds that it is
large.

`jsk-resume-author` keeps reading `references/ats-rules.md`. It was considered and rejected:
the read may inform keyword placement and vocabulary mirroring while bullets are being
written, and 2,396 tokens is not worth the risk of finding out otherwise in an interview.

## Lever 1 — Stop walking what the record does not read

*Pure latency, no behavioural change, entirely inside `okf_compile.py`. It goes first.*

`concepts()` walks every `.md` in the bundle. Under `tailoring/` the only thing `load()` ever
consumes is a `View`; postings and gap assessments are parsed and discarded.

**1a. Under `tailoring/`, read only `*.view.md`.** Everywhere else is unchanged.

**1b. When views are not requested, skip `tailoring/` entirely.** `--no-views` is already how
both agents compile, so both get this for free.

Measured on the 100-application bundle, against today's already-archive-pruned walk:

| | concepts | walk |
|---|---|---|
| today | 345 | 412ms |
| 1a — skip postings and gaps | 145 | 125ms (**70% faster**) |
| 1a + 1b — skip `tailoring/` | 45 | 37ms (**91% faster**) |

**The conservation check must not weaken.** `check_conservation` compares concept types on
disk against record keys, and it exists because *every other check iterates that key, and an
empty list satisfies all of them*. It is fed by `census()`, which today shares `concepts()`.
If a narrowed walk would make `census()` blind to a type, `census()` does its own full walk
instead. A faster compile that quietly stops noticing a dropped concept type is the exact
defect this gate was written for.

### Rejected: passing a pre-compiled record to `validate_urs`

An earlier draft proposed `validate_urs.py --record <file>` to avoid recompiling. Measurement
killed it twice over, and the reasoning is recorded so nobody proposes it again:

- **It saves nothing.** `census()` costs 489ms against `load()`'s 425ms — both are dominated
  by the same walk. Skipping the build while still paying the walk saves no measurable time.
- **The naive form silently weakens a gate.** `validate_urs record.json` already works today,
  and on the measured bundle reports 75 failures where `validate_urs <bundle>` reports 376,
  because `check_conservation` only runs on the bundle path. Instructing the agents to pass
  `record.json` would have looked like a pure speedup and quietly removed a gate.

Process startup is also not worth chasing on its own: it is 166ms, and an earlier estimate of
~846ms was wrong — it compared a cold CLI run against a warm in-process call.

## Lever 2 — Collapse the mechanical gates

*Wins both axes: removes a subagent spawn and four process starts.*

```
okf gates <out-dir> --record <r.json> --view <id> [--pages N] [--json]
```

Runs the record, parse and prose gates in one process and prints each one's output. Exit code
is the worst of them.

Three properties it must have, each of which is an existing rule in this codebase rather than
a new one:

- **It prints gate output verbatim, never a summary.** *The person should see the evidence
  rather than take your word for it.*
- **A missing input is `SKIPPED` and a failure.** *A gate that did not run is not a gate that
  passed.* This is already how `okf check` behaves and the wording should match.
- **It does not attempt the render gate.** It prints an explicit line saying somebody has to
  open the PDF and read it. The render gate is the one nobody else can run, and a command that
  exits 0 having silently skipped it would be the most dangerous thing in this document.

`jsk-verifier` becomes **optional rather than mandatory**. `mode-ship.md` step 4 calls
`okf gates` directly and shows the output; the agent is still the right tool when gates fail
and the failures need interpreting against the record. Its file, its no-Write constraint and
its place in `SKILL.md` all stay — what changes is that a passing ship no longer spawns it.

Note this is *more* aligned with the existing design, not less: the verifier has no Write tool
deliberately, and a script has none more thoroughly still.

**Expected:** 924ms → ~400ms, and ~2,200 tokens plus one subagent spawn removed from every
clean ship.

## Lever 3 — Slice what agents must read

*Largest token win, and the only lever that changes what an agent is told to read, so it goes
last and needs the most care.*

**3a. `okf_compile --compact`.** `--dump-record` writes `indent=2`. On the measured bundle
that is 30,870 bytes against 20,318 compact — **34% of every record read, for whitespace no
model needs.** Nothing is lost and nothing else changes. Both agents pass it.

**3b. `okf_compile --for score`.** Emits projects carrying only the keys the ranking runs on —
`id`, `label`, `capabilities`, `technologies`, `domains`, `seniority`, `strength`, `recency`,
`engagement` — and drops narratives, education and credentials. Measured: `projects[]` is 80%
of the record and the scorer slice is 39% of `projects[]`, because **61% of it is achievement
prose the scorer never reads a word of**.

`jsk-tailor-analyst` assesses against requirements and ranks projects. Its record read drops
from 7,717 tokens to 2,589 - the projection and `--compact` compounding.

The projection is computed in `okf_compile`, not by the caller, so there is exactly one
definition of what a scorer needs. A second list of keys somewhere else is the transcription
problem this format was built to avoid.

**3c. Split the Views section out of `urs-spec.md` into `references/view-format.md`.**
`jsk-resume-author` is told to *"Read `references/urs-spec.md` first either way"* and needs the
view format from it. That file is 4,127 tokens; the view format is a fraction of it.

**A split, never a copy.** The Views material moves; `urs-spec.md` keeps a pointer where the
section was. Backed by a test asserting neither file defines a key the other defines, so the
two cannot drift into disagreeing — the same structural argument this codebase makes
everywhere else, that a shape where the wrong thing is impossible beats a rule saying not to
do it.

**Expected:** analyst 11,618 → 6,490. Author 20,819 → 15,254. Run total 42,867 → 29,974,
with the verifier's 2,200 removed by Lever 2 rather than by this one.

## Sequencing

1. **Lever 1** — invisible to behaviour, so it lands first and the suite proves it alone.
2. **Lever 2** — removes a wrapper; `mode-ship.md` and `jsk-verifier.md` change together.
3. **Lever 3** — changes instructed reads; lands last, when everything under it is stable.

Each is a separate commit. Lever 3's three parts are independent and may be split further.

## Testing

The existing 542 tests must stay green throughout; none of this is permitted to change what a
resume says, so a behavioural test that moves is a defect in the change.

New coverage, per lever:

- **1a** `validate_urs --record` agrees with `validate_urs <bundle>` on the same bundle —
  identical findings, identical exit code. The two paths giving different verdicts is the
  whole risk of the change.
- **1b** every script in the in-process list exposes `main(argv)` and returns rather than
  exiting; `validate_bundle.py` is asserted *absent* from that list, so a later refactor
  cannot quietly add it.
- **2** exit code is the worst gate's; a missing input is SKIPPED *and* non-zero; the render
  gate is never reported as passed.
- **3a** compact and indented records are equal as parsed objects.
- **3b** the projection carries every key `score_projects.py` reads and no achievement text.
- **3c** the drift test above.

**`tests/test_budget.py`** asserts each agent's mandated-read total stays under a ceiling,
derived the way the table at the top of this document was. The audit that produced this work
found a plugin whose costs nobody had measured; a ceiling that CI checks is how that stops
being true again. The ceilings are set from the post-implementation figures, with headroom
stated in the test rather than left implicit.

## What success looks like

| | now | target |
|---|---|---|
| mandated reads per run | 42,867 tok | 29,974 tok |
| script wall clock | 12.3s | ~5.5s |
| compiles per run | 7 | 7, each ~10x cheaper |
| subagent spawns per clean ship | 3 | 2 |

No change to any rendered resume, and 542 tests still green.
