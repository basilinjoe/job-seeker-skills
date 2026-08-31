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
`--dump-record`, and `validate_urs <bundle>` compiling on each of its three invocations. At
~1.1s each that is 7.7 seconds, of which **about 5.6 seconds is Python and `pyyaml` starting
up** rather than any work. The compile is 0.44s in process.

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

## Lever 1 — Kill the redundant compiles

*Pure latency. No behavioural change, so it goes first.*

**1a. `validate_urs.py --record <file>`.** It currently takes a bundle path and compiles.
Both agents have already written `record.json` by the time they call it, and so has the ship
sequence. Accepting the record removes three of the seven compiles.

The bundle path must stay supported and stay the default. `okf validate <bundle>` is the
documented entry point and a person running it by hand has no `record.json`.

**1b. `okf.py` dispatches in process where it safely can.** `run()` currently spawns
`subprocess.call([sys.executable, path] + args)`, paying ~800ms of interpreter and `pyyaml`
import per call. Where the target script exposes a clean `main(argv)` returning an exit code,
import and call it instead.

`validate_bundle.py` is **not** import-safe: it executes at module level and calls
`sys.exit()` directly. It stays a subprocess. The dispatcher decides per script from an
explicit list rather than by trying and catching, because a script that half-ran before
failing an import is worse than one that never started.

The scripts remain independently callable with unchanged arguments and exit codes. That is
the documented API and `okf.py` says so in its own opening lines.

**Expected:** 7 compiles → 3. Script time 12.3s → ~7.9s; the remaining levers take it to ~6.6s.
`render_resume --pdf` is 2.3s of that floor and is irreducible - it is a TeX compile.

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
| script wall clock | 12.3s | ~6.6s |
| compiles per run | 7 | 3 |
| subagent spawns per clean ship | 3 | 2 |

No change to any rendered resume, and 542 tests still green.
