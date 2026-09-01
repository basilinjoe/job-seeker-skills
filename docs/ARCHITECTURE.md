# Architecture

For anyone editing this repo. If you only want to *use* the plugin, read
[Quickstart](QUICKSTART.md) instead.

## The one-way pipeline

```
bundle (Markdown + YAML frontmatter)
   |
   |  read by the skill, with the person in the loop
   v
resume.json  (URS record)
   |
   |  urs/plan.py resolves it exactly once:
   |  selection, ordering, provenance filtering,
   |  region gating, ASCII folding, date formatting
   v
render plan
   |
   +--> emit_latex.py  -->  .tex  -->  .pdf   (the deliverable; --ats-max picks the variant)
   +--> emit_text.py   -->  .txt          (paste-in boxes)
```

**The narrow waist is the design.** Every content decision happens once, in the plan. The emitters
translate a resolved plan into markup and decide nothing. That is what guarantees the PDF and the
plain text cannot say different things — neither of them chose what to say.

`emit_docx.py` used to sit alongside them and produced two more files. It went because the same
argument applies one level up: `fit_pages.py` measured the `.docx` through LibreOffice while the PDF
was what got sent, they disagreed, and a resume reported as two pages shipped as three. There is now
one rendered deliverable, and the thing measured is the thing sent.

If you find yourself making a content decision inside an emitter, it belongs in the plan. If you find
yourself making a formatting decision inside the plan, it belongs in an emitter.

### Inside the `urs` package

`plan.py` is a facade over a second seam:

| Module | Decides |
|---|---|
| `plan.py` | nothing — the public face. `from urs import plan`, `plan.build(...)` |
| `resolve.py` | *what* the document says: selection, ordering, provenance filtering, region gating |
| `formatting.py` | *how* one value reads: dates, grades, quantities, the fold to ASCII |
| `profiles.py` | region profile loading and the gate that applies it |
| `emit_*.py` | markup only |
| `themes.py` | *appearance* only: palette, typeface, rhythm. Below `emit_latex.py`, and it cannot reach the text |

`formatting.py` holds pure functions over single values — no view, no profile, no record — which is
what makes them testable in isolation. Import `plan`; the split is behind it.

## The agent boundary

Four tasks are delegated to subagents. The line used to be **Write versus Edit**: an agent wrote its
own analysis, and only the conversation edited the person's record. It is now narrower and structural
— **nothing that touches a bundle holds either tool.** Every write is an `okf` command, so the two
agents that author into the bundle carry no way to hand-write a file in it.

| Agent | Has | Deliberately lacks |
|---|---|---|
| `jsk-verifier` | Bash, Read, Glob | Write and Edit — a defect is fixed in `resume.json` and re-rendered, never patched into the render |
| `jsk-bundle-auditor` | Read, Write, Glob, Grep, Bash | Edit — it writes an audit; a concept is the person's |
| `jsk-tailor-analyst` | Read, Glob, Grep, Bash | Write and Edit — the posting's requirements and the assessment are commands |
| `jsk-resume-author` | Read, Glob, Grep, Bash | Write and Edit — the bullets and the view are commands, and it is the one that writes prose |

**The anti-invention guarantee moved from an instruction into a tool grant.** Both authoring agents
used to be handed `Write, Edit` and told in prose to follow `bundle-spec.md`; the mechanical half of
a concept written from memory is where the defects came from. `src/jsk_okf/authoring/` is now the only
path either has, and it refuses a dangling `role:`, a capability synonym, a bullet naming a metric
that is not there, and a half-finished write that would otherwise go green. See
`docs/superpowers/specs/2026-08-31-okf-write-cli-design.md`.

The escape hatch matters as much as the grant: **if the CLI cannot express something, the agent
reports that and stops.** A blocked write is a bug report naming a missing verb, which is the signal
that keeps the layer honest. It is not permitted to degrade to a hand-edit, and it no longer has the
tools to.

`jsk-verifier` is the conditional one. `okf gates` runs the record, parse and prose gates in a single
process and prints each one's output verbatim, so a clean ship reads that rather than spawning an
agent to relay three checkers — and a script has no Write tool more thoroughly than an agent does.
What the agent is kept for is the half a command cannot do: reading a `FAIL` line back to the concept
it came from, and reading the PDF for the render gate.

`jsk-resume-author` is the exception worth understanding. It authors the narrative, the retuned
summary and the view, so restraint alone would not be enough. Everything it writes is marked
`inferred`, and a view with `provenance_floor: confirmed` means `validate_urs.py` refuses to render
it until a person has confirmed each clause. **The guarantee lives in the record gate, not in the
agent.**

Two consequences worth keeping in mind when editing them:

1. **A subagent's output never reaches the person.** Every agent is told to return checker verdicts
   and quoted claims verbatim, and every calling mode is told to relay rather than summarise. Break
   either half and the "show the output" rule quietly stops holding.
2. **Nothing may depend on an agent existing.** The mode files carry the full inline procedure, so
   the skill works unchanged in an environment with no subagents. An agent is a context optimisation,
   not a step.

## Repo layout

```
pyproject.toml                      the jsk-okf package: deps, console scripts, ruff, pytest
.claude-plugin/marketplace.json     marketplace manifest (carries a version)
docs/                               this directory - human-facing documentation
src/jsk_okf/                        THE CLI. one installed package, `okf` on the command line
  __init__.py                       __version__
  __main__.py                       `python -m jsk_okf`, the same entry point as `okf`
  cli.py                            the dispatcher: forwards the reads, dispatches the writes
  paths.py                          where the packaged schema lives - stated once
  authoring/                        the write layer - every change to a bundle goes through it
    schema.py                       what each type takes, and what each value must satisfy
    concept.py                      one concept's frontmatter: emit, or splice one key
    body.py                         the authored blocks and the prose sections
    bookkeeping.py                  the derived companions: index entries, log rows
    stage.py                        the transaction: stage, validate, publish in order
    common.py                       the rules that need the bundle in hand
    commands.py                     the CLI, and the one place a verb is dispatched
    career.py                       project, role, org, education
    claims.py                       bullet, skill, credential, metric
    upkeep.py                       capability, question, log, reindex
    tailoring.py                    posting, gaps, view
    archive.py                      application file, application event
  urs/                              record -> document; plan decides, emitters only mark up
  okf_compile.py                    bundle -> record
  validate_bundle.py                the bundle gate       validate_urs.py   the record gate
  check_ats.py                      the parse gate        check_prose.py    the prose gate
  render_resume.py                  one record to .tex/PDF plus .txt
  preview_templates.py              one record in every template, so the look is chosen by looking
  fit_pages.py                      fits a render to a page budget
  score_projects.py                 ranks projects against a posting
  init_bundle.py                    scaffolds a bundle    migrate_bundle.py revision steps
  pipeline.py                       the weekly board      pipeline_model.py what an event means
  preflight.py                      `okf doctor`: what this machine can do
  data/schema/                      package data, reached through paths.py
    profiles/*.json                 region profiles: default, au, in, ae
    profile.schema.json             what a region profile must contain
    example.resume.json             one complete worked record
plugins/jsk/                        THE SKILL. markdown only - it ships no code
  .claude-plugin/plugin.json        plugin manifest (carries a version)
  commands/                         slash commands
    setup.md                        the four-phase setup procedure
    braindump|resume|tailor|...     thin delegations into the skill's modes
  agents/                           subagents the modes delegate to
    jsk-verifier.md                 interprets a failed gate against the record
    jsk-bundle-auditor.md           reads the whole bundle, writes a posting-less audit
    jsk-tailor-analyst.md           reads a posting and the compiled record
    jsk-resume-author.md            authors the tailored record: narrative, summary, view
  skills/jsk/
    SKILL.md                        the agent's entry point: routing + hard rules
    references/                     what the agent loads on demand
      README.md                     index of everything below
      mode-*.md                     one procedure per mode
      bundle-spec.md                bundle layout, frontmatter schema, selection keys
      urs-spec.md                   the shape the record compiles to, and the region profiles
      view-format.md                every key a view may carry
      ats-rules.md                  hard rules, two-variant strategy, keyword placement
      writing-rules.md              X-Y-Z bullets, verb accuracy, phrases to cut
      rationale.md                  long-form reasoning, loaded to explain a rule
tests/                              unittest: one file per module, plus the manifest surface
  fixtures.py                       temp bundles and records; nothing here is committed
```

**The code and the skill are two artefacts now.** `src/jsk_okf/` is a Python package
installed from PyPI as `jsk-okf`; `plugins/jsk/` is markdown that calls `okf`. They used
to be one tree - the scripts lived at `plugins/jsk/skills/jsk/scripts/` and every mode
file invoked them by absolute path. Fifteen paths to get right became one command.

## Where do I change X

| To change | Edit | And also |
|---|---|---|
| What the parse gate rejects | `src/jsk_okf/check_ats.py` | `references/ats-rules.md`, `tests/test_check_ats.py` |
| What the prose gate rejects | `src/jsk_okf/check_prose.py` | `references/writing-rules.md`, `tests/test_check_prose.py` |
| What makes a record invalid | `src/jsk_okf/validate_urs.py` | `references/urs-spec.md`, `tests/test_validate_urs.py` |
| **What content is selected** | `src/jsk_okf/urs/plan.py` | never an emitter |
| **How a document looks** | `src/jsk_okf/urs/emit_*.py` | never `plan.py` |
| **A palette, typeface or rule** | `src/jsk_okf/urs/themes.py` | `references/templates.md`, `tests/test_themes.py` |
| Support for a new market | `schema/profiles/<code>.json` | the region section of `references/urs-spec.md` |
| What a view may carry | `references/view-format.md` | `src/jsk_okf/validate_urs.py`, `agents/jsk-resume-author.md` — never `references/urs-spec.md`, which defines no view key |
| Bundle layout | `src/jsk_okf/init_bundle.py` | `src/jsk_okf/validate_bundle.py`, `references/bundle-spec.md`, **a new revision in `migrate_bundle.py`** |
| **How a frontmatter value is quoted** | `src/jsk_okf/authoring/concept.py` | never a caller, never a second emitter |
| **What a concept type may carry** | `src/jsk_okf/authoring/schema.py` | `references/bundle-spec.md` — the two are one rule in two languages, and a rule in one and not the other is a defect |
| **How an authored block is read or written** | `src/jsk_okf/authoring/body.py` | never a verb module — and it must keep agreeing with `okf_compile.blocks()`, which a test asserts |
| A write verb, or a new one | `src/jsk_okf/authoring/<tranche>.py` | `references/write-commands.md`, `WRITE_NOUNS` in `cli.py`, the `CATALOGUE` in `tests/test_okf_write_surface.py`, the write table in `SKILL.md` and `docs/SCRIPTS.md` |
| What a migration does | `src/jsk_okf/migrate_bundle.py` | `docs/SCRIPTS.md`, `tests/test_migrate_bundle.py` |
| **What a timeline event means** | `src/jsk_okf/pipeline_model.py` | never in a caller — `pipeline.py`, `validate_bundle.py` and `migrate_bundle.py` all read it |
| How the record is built | `src/jsk_okf/okf_compile.py` | `references/bundle-spec.md`, `tests/test_okf_compile.py` — and the render test, which is what a schema used to do |
| How postings are scored | `src/jsk_okf/score_projects.py` | `agents/jsk-tailor-analyst.md` (it writes the requirements), `tests/test_score_projects.py` |
| A posting's or assessment's shape | `agents/jsk-tailor-analyst.md` | `references/mode-tailor.md` — the format is written out in the agent, so it is one place |
| A mode's procedure | `references/mode-<name>.md` | the routing table in `SKILL.md` |
| What an agent may do | `plugins/jsk/agents/<name>.md` | the delegation note in every mode that calls it, and the Agents table in `SKILL.md` |
| Add a mode | a new `references/mode-<name>.md` | routing table in `SKILL.md`, a `commands/<name>.md` |

## What is frozen

This is a published plugin. Three surfaces may not move without a major version and a migration
story:

1. **The `okf` command surface.** Subcommand names and flags — `okf check --strict`,
   `okf validate --level N` and the rest — are public API. They appear in shell histories, in README
   examples, and in every mode file. Module names inside the package are free; the invocation
   surface is not.

   This clause used to freeze the *script filenames* — `check_ats.py`, `validate_urs.py`, invoked by
   absolute path out of the skill directory. Version 3.0 broke that deliberately: the scripts became
   one installed CLI, so the fifteen paths are gone and everything goes through `okf <verb>`. The
   modules are still importable under those names (`jsk_okf.check_ats`, and `python -m
   jsk_okf.check_ats` still runs it), but a shell alias pointing into the old skill directory will
   not resolve.
2. **Bundle layout on disk.** Renaming `projects/` breaks every bundle already in existence.
   Layout *additions* are allowed, but only behind a revision: bump `CURRENT_REVISION` in
   `migrate_bundle.py`, teach it the step, and keep `validate_bundle.py` **warning** rather than
   failing on the older shape. `BUNDLE_REVISION` in `init_bundle.py` and `CURRENT_BUNDLE_REVISION`
   in `validate_bundle.py` must move in the same commit — all three are pinned to each other by
   `tests/test_plugin_surface.py`, because new bundles are born current and a bundle that lies about
   its revision is worse than one that carries no stamp at all.
3. **The compiled record's shape and gate behaviour.** What `okf_compile.py` hands the renderer
   stays wire-compatible with an archived `resume.json`, and a gate keeps failing on exactly what
   it fails on today.

A fourth, discovered the hard way: **the tests assert on output text.** There are over 240 `assertIn`
calls against strings like `PASS - safe to send` and `DO NOT SEND`. You may *add* lines to a script's
output. Rewording an existing verdict line breaks tests, and those tests are the gate on the gate.

## Tests

```bash
python -m pytest tests -n auto             # the whole suite in parallel - 2m17s
python -m pytest tests -q                  # serially - 4m58s; what CI would do without xdist
python -m pytest tests/test_themes.py -q   # one file, while you are working on it
python -m unittest discover -s tests       # the same tests, with no pytest installed
```

`tests/fixtures.py` puts `src/` on the path itself and passes it to every child interpreter it
spawns, so no install is needed and the suite always tests the working tree rather than whatever
`jsk-okf` happens to be on the machine. That second part matters more than it looks.

**"Runs on a bare Python" is true of the toolchain, not of the suite.** `pyyaml` is needed to read a
bundle at all, and most of these tests build one, so a run without it reports around 460 failures
rather than skipping. Only the TeX-engine and `pymupdf` tests skip themselves properly. Install
`.[dev]` before running anything and this never comes up; the claim is recorded here because the
numbers look alarming and mean nothing.

The tests are standard-library `unittest` and import nothing from pytest; pytest is simply the
pleasanter way to run a subset and read a failure. Either command works from anywhere — every path
in `tests/fixtures.py` is resolved from the test file's own location, not from the working
directory.

Most of that time is TeX — 1,420 tests, and the ones that dominate the clock compile real PDFs and
extract their text layers, because the claim they check — five templates, one document — cannot be
checked any other way. Where a TeX engine or `pymupdf` is absent those tests skip themselves, so a
bare-Python run finishes in seconds on fewer assertions rather than failing on the machine's setup.

Fixtures are built into temp directories by `tests/fixtures.py`; nothing is committed. Every test
pins a specific documented rule — the checker is the gate, so it does not go unchecked.

A failing test after a refactor means the refactor was wrong. Do not edit a test to accommodate a
change in behaviour unless the behaviour change is the point and it is written down.

## Dependencies

Deliberately close to zero, and **`pyproject.toml` declares none as required** — every one is an
optional extra, imported at the point of use. `pip install jsk-okf` gives a working write layer,
compile, prose gate and `.txt` parse gate on a bare interpreter. `okf doctor` especially, because a
preflight that needs installing first is not a preflight.

```bash
pip install jsk-okf              # the write layer, compile, prose gate, .txt parse gate
pip install 'jsk-okf[all]'       # pyyaml + pymupdf + jsonschema
pip install -e '.[dev]'          # the above plus pytest, pytest-xdist, ruff
```

| Optional | Unlocks |
|---|---|
| `pyyaml` | reading the bundle at all: `validate_bundle.py`, `score_projects.py` |
| `jsonschema` | full schema validation in `validate_urs.py` (structural rules run without it) |

| Required | Why |
|---|---|
| a TeX engine | the PDF is the only rendered deliverable; without one there is nothing to send |
| `pymupdf` | without it the parse gate and the page budget are both unverifiable |

A TeX engine and `pymupdf` were optional while the `.docx` was the portal artefact. `okf doctor`
now reports their absence as BLOCKED rather than a gap. LibreOffice left the list entirely: it
existed only to render the `.docx` for measurement.

Anything that cannot run reports loudly and exits non-zero rather than passing quietly.

## Releasing

There are **two release trains** since the code left the skill, and they version independently.

The **plugin** version lives in two files and they must agree — `tests/test_plugin_surface.py`
asserts it:

- `plugins/jsk/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

The **CLI** version is `__version__` in `src/jsk_okf/__init__.py`, which `pyproject.toml` reads
through `[tool.hatch.version]`. `okf --version` and `okf doctor` both report it.

```bash
python -m build          # wheel + sdist into dist/
```

Tag them distinctly — `cli-vX.Y.Z` and `plugin-vX.Y.Z` — or the history stops being readable.

Before tagging: run the tests, run `okf doctor` (the verifying form, not `--quick`), and check that
every internal doc link still resolves.

**The version skew this introduces is real and is not yet handled.** A plugin updated to markdown
that uses a flag the installed CLI does not have fails mid-session on an argparse error. The fix is
a floor the skill states and `okf doctor --require X.Y` enforces; it is not built.

---

Next: [Why it works this way](WHY.md) · [Scripts](SCRIPTS.md)
