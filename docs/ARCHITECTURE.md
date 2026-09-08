# Architecture

For anyone editing this repo. If you only want to *use* the plugin, read
[Quickstart](QUICKSTART.md) instead.

## The one-way pipeline

```
user-knowledgebase.md  (one Markdown file, fixed headings)
   |
   |  read and written by the skill, with the person in the loop
   v
resume.json  (URS record, one per application)
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
| `render_resume.py` · `preview_templates.py` · `fit_pages.py` | the CLIs — `jsk render`, `jsk preview`, `jsk fit`. They orchestrate the modules above and decide nothing themselves |

They sat at the top of the package until the boundary was measured. Between this package and the
rest of `jsk` there is exactly **one** import edge, and it is lazy: `profiles` reaching for the
packaged schema path. It was two until the compiler left. 2,388 lines behind one edge is one
subject, so it is one package.

`formatting.py` holds pure functions over single values — no view, no profile, no record — which is
what makes them testable in isolation. Import `plan`; the split is behind it.

## The agent boundary

Four tasks are delegated to subagents, and the line between them is what each may write.

| Agent | Has | Deliberately lacks |
|---|---|---|
| `jsk-verifier` | Bash, Read, Glob | Write and Edit — a defect is fixed in `resume.json` and re-rendered, never patched into the render |
| `jsk-kb-auditor` | Read, Write, Glob, Grep, Bash | Edit — it writes an audit; the knowledge base is the person's |
| `jsk-tailor-analyst` | Read, Write, Edit, Glob, Grep, Bash | nothing, and that is the change worth reading below |
| `jsk-resume-author` | Read, Write, Edit, Glob, Grep, Bash | nothing — it is the one that writes prose |

**The anti-invention guarantee used to be a tool grant, and it is a sentence again.** Both authoring
agents held neither Write nor Edit, because every change they made went through a write command that
checked its shape and refused what a gate would reject later. There is no write layer over one
Markdown file, so both hold Edit now, and what holds them is what the file says:

- `jsk-tailor-analyst` writes the posting's frontmatter and the assessment, and **never touches
  `user-knowledgebase.md`**. Its boundary is absolute and it is prose.
  `tests/test_plugin_surface.py` asserts the sentence is still in the file, which is the most a test
  can do about a rule of that kind.
- `jsk-resume-author` **does** write into the knowledge base — bullets belong in the project they are
  about, so the next application can reuse them. What holds it is not a tool grant either, but it is
  not merely prose: everything it authors is `status: inferred`, and a view carrying
  `provenance_floor: confirmed` means the record gate refuses to render it until a person has
  confirmed each clause. **The guarantee lives in the record gate, not in the agent.**

That asymmetry is the design. Where a rule can be enforced by a gate, it is; where it cannot, it is
stated as plainly as possible and the test checks that the statement survives.

`jsk-verifier` is the conditional one. `jsk gates` runs the record, parse and prose gates in a single
process and prints each one's output verbatim, so a clean ship reads that rather than spawning an
agent to relay three checkers — and a command has no Write tool more thoroughly than an agent does.
What the agent is kept for is the half a command cannot do: reading a `FAIL` line back to the section
it came from, and reading the PDF for the render gate.

Two consequences worth keeping in mind when editing them:

1. **A subagent's output never reaches the person.** Every agent is told to return checker verdicts
   and quoted claims verbatim, and every calling mode is told to relay rather than summarise. Break
   either half and the "show the output" rule quietly stops holding.
2. **Nothing may depend on an agent existing.** The mode files carry the full inline procedure, so
   the skill works unchanged in an environment with no subagents. An agent is a context optimisation,
   not a step.

## Repo layout

```
pyproject.toml                      the jsk-resume package: deps, console script, ruff, pytest
.claude-plugin/marketplace.json     marketplace manifest (carries a version)
docs/                               this directory - human-facing documentation
src/jsk/                            THE CLI. one installed package, `jsk` on the command line
  __init__.py                       __version__
  __main__.py                       `python -m jsk`, the same entry point as `jsk`
  cli.py                            the dispatcher: eight subcommands, forwarded or imported
  cliutil.py                        one contract for --help across the hand-rolled entry points
  paths.py                          where the packaged schema lives - stated once
  kb.py                             `jsk new` - scaffolds user-knowledgebase.md and applications/
  urs/                              record -> document, and the three CLIs that drive it
    plan.py                         every content decision, made exactly once
    resolve.py                      *what* the document says   formatting.py *how* one value reads
    profiles.py                     region profiles            themes.py     appearance only
    emit_latex.py  emit_text.py     markup only                tex.py        the engine
    render_resume.py                `jsk render` - one record to .tex/PDF plus .txt
    preview_templates.py            `jsk preview` - every template, so the look is chosen by looking
    fit_pages.py                    `jsk fit` - fits a render to a page budget
  gates/                            the three mechanical gates `jsk gates` runs
    validate_urs.py                 the record gate - before anything is rendered
    check_ats.py                    the parse gate        check_prose.py    the prose gate
  preflight.py                      `jsk doctor`: what this machine can do
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
    jsk-kb-auditor.md               reads the whole knowledge base, writes a posting-less audit
    jsk-tailor-analyst.md           reads a posting and the knowledge base, ranks in the open
    jsk-resume-author.md            authors the record: bullets, narrative, view
  skills/jsk/
    SKILL.md                        the agent's entry point: routing + hard rules
    references/                     what the agent loads on demand
      README.md                     index of everything below
      mode-*.md                     one procedure per mode
      kb-spec.md                    every heading in user-knowledgebase.md, and applications/
      urs-spec.md                   the record's shape, and the region profiles
      view-format.md                every key a view may carry
      ats-rules.md                  hard rules, two-variant strategy, keyword placement
      writing-rules.md              X-Y-Z bullets, verb accuracy, phrases to cut
      templates.md                  the five visual templates
      rationale.md                  long-form reasoning, loaded to explain a rule
tests/                              unittest: one file per module, plus the manifest surface
  fixtures.py                       temp records; nothing here is committed
```

**The code and the skill are two artefacts.** `src/jsk/` is a Python package installed from PyPI as
`jsk-resume`; `plugins/jsk/` is markdown that calls `jsk`.

**Six modules and two subpackages left in one commit** — `okf_compile`, `validate_bundle`,
`init_bundle`, `migrate_bundle`, `pipeline`, `pipeline_model`, `score_projects`, `markup`, plus
`authoring/` and `query/`: about 15,000 lines. Every one of them existed to keep a folder of several
hundred concepts consistent with a record derived from it. One file has no such problem, and the
half of the package that was never about the bundle — the record, the renderer, the gates — is what
is left.

## What is a package here, and what is not

Two subpackages, and both were measured before they were made. The test is whether the members
import *each other* more than they import outward — a group whose members share no edges is a folder
with a theme, not a module.

| Group | Edges crossing the boundary | Edges inside | Verdict |
|---|---|---|---|
| `urs/` — rendering, preview, page fitter, over the record→document pipeline | **1**, lazy | many | **made** |
| `gates/` — record, parse, prose | **1**, lazy | 1 | **made** |

Both counts fell by one when the compiler left: `render_resume` and `validate_urs` each reached for
`okf_compile` to turn a bundle into a record, and neither takes a bundle now.

A third, `query/`, passed the same test at 9 edges out against 24 inside and was made — and then
deleted with the format it read. It is worth recording as the case where the measurement was right
and the subject was temporary: the module was well-factored and the question it answered stopped
being a question anyone had.

Two groups were measured and rejected, and the reasoning still applies to anything proposed here.
`bundle/` — compile, validate, init, migrate — had 8 edges out and **zero** inside: four modules
that all operated on a bundle and never once imported each other. Grouping them would have added
eight boundary crossings and bought a directory named after a noun they had in common. `pipeline/`
had 5 out and 1 in, for the same reason.

`cli.SUBPACKAGE` is the one map from a documented script name to where its module lives, and
`tests/fixtures.load_script` reads that map rather than keeping a second copy.

## Where do I change X

| To change | Edit | And also |
|---|---|---|
| What the parse gate rejects | `src/jsk/gates/check_ats.py` | `references/ats-rules.md`, `tests/test_check_ats.py` |
| What the prose gate rejects | `src/jsk/gates/check_prose.py` | `references/writing-rules.md`, `tests/test_check_prose.py` |
| What makes a record invalid | `src/jsk/gates/validate_urs.py` | `references/urs-spec.md`, `tests/test_validate_urs.py` |
| **What content is selected** | `src/jsk/urs/plan.py` | never an emitter |
| **How a document looks** | `src/jsk/urs/emit_*.py` | never `plan.py` |
| **A palette, typeface or rule** | `src/jsk/urs/themes.py` | `references/templates.md`, `tests/test_themes.py` |
| Support for a new market | `data/schema/profiles/<code>.json` | the region section of `references/urs-spec.md` |
| What a view may carry | `references/view-format.md` | `src/jsk/gates/validate_urs.py`, `agents/jsk-resume-author.md` — never `references/urs-spec.md`, which defines no view key |
| **The knowledge base format** | `references/kb-spec.md` | `src/jsk/kb.py` — the template and the spec are one rule in two languages, and a heading in one and not the other is a defect |
| What `jsk new` scaffolds | `src/jsk/kb.py` | `references/kb-spec.md`, `references/mode-setup.md` |
| A posting's or assessment's shape | `agents/jsk-tailor-analyst.md` | `references/mode-tailor.md` — the format is written out in the agent, so it is one place |
| How postings are ranked | `agents/jsk-tailor-analyst.md` | nowhere else — there is no scorer any more, and the weighting table in that file is the whole of it |
| A mode's procedure | `references/mode-<name>.md` | the routing table in `SKILL.md` |
| What an agent may do | `plugins/jsk/agents/<name>.md` | the delegation note in every mode that calls it, and the Agents table in `SKILL.md` |
| Add a mode | a new `references/mode-<name>.md` | routing table in `SKILL.md`, a `commands/<name>.md` |
| A subcommand | `src/jsk/cli.py` | the help docstring in the same file, the command table in `SKILL.md`, `docs/SCRIPTS.md` — all three pinned by `tests/test_plugin_surface.py` |

## What is frozen

This is a published plugin. Two surfaces may not move without a major version and a migration story:

1. **The `jsk` command surface.** Subcommand names and flags — `jsk check --strict`,
   `jsk render --view` and the rest — are public API. They appear in shell histories, in README
   examples, and in every mode file. Module names inside the package are free; the invocation
   surface is not.

   Version 4.0 broke this deliberately and completely: the command was `okf`, twenty-odd subcommands
   of it, and the format those subcommands operated on no longer exists. There is no compatibility
   shim, because a shim over `okf project add` would have to write into a file whose shape it cannot
   know. `docs/SCRIPTS.md` closes with the mapping from each removed subcommand to what replaced it.

2. **The record's shape and gate behaviour.** What the renderer reads stays wire-compatible with an
   archived `resume.json` — an application filed two years ago is still re-renderable — and a gate
   keeps failing on exactly what it fails on today.

**Bundle layout on disk** used to be the third, and it was the strongest of the three: renaming
`projects/` broke every bundle in existence, so additions went behind a revision number pinned across
three modules. There is one file now and its headings are the contract; `references/kb-spec.md` says
never to rename or reorder one, and `jsk new` writes them all. A knowledge base from before this
change is migrated by reading it and writing the new file — `references/mode-setup.md` has the
procedure, and it is a conversation rather than a command because every relation the old format left
in prose is a judgement a script guessed at.

A fourth, discovered the hard way: **the tests assert on output text.** There are over 240 `assertIn`
calls against strings like `PASS - safe to send` and `DO NOT SEND`. You may *add* lines to a command's
output. Rewording an existing verdict line breaks tests, and those tests are the gate on the gate.

## Tests

```bash
python -m pytest tests -n auto             # the whole suite in parallel
python -m pytest tests -q                  # serially; what CI would do without xdist
python -m pytest tests/test_themes.py -q   # one file, while you are working on it
python -m unittest discover -s tests       # the same tests, with no pytest installed
```

`tests/fixtures.py` puts `src/` on the path itself and passes it to every child interpreter it
spawns, so no install is needed and the suite always tests the working tree rather than whatever
`jsk-resume` happens to be on the machine. That second part matters more than it looks.

**"Runs on a bare Python" is now true of the suite as well as the toolchain.** It was not: `pyyaml`
was needed to read a bundle, most tests built one, and a run without it reported around 460 failures
rather than skipping. There are no bundles to build, so only the TeX-engine and `pymupdf` tests skip
themselves and everything else runs anywhere.

The tests are standard-library `unittest` and import nothing from pytest; pytest is simply the
pleasanter way to run a subset and read a failure. Either command works from anywhere — every path
in `tests/fixtures.py` is resolved from the test file's own location, not from the working directory.

Most of the runtime is TeX: the tests that dominate the clock compile real PDFs and extract their
text layers, because the claim they check — five templates, one document — cannot be checked any
other way. Where a TeX engine or `pymupdf` is absent those tests skip themselves, so a bare-Python
run finishes in seconds on fewer assertions rather than failing on the machine's setup.

Fixtures are built into temp directories by `tests/fixtures.py`; nothing is committed. Every test
pins a specific documented rule — the checker is the gate, so it does not go unchecked.

`tests/test_budget.py` and `tests/test_plugin_surface.py` are the two that read the markdown rather
than the code, and they are what stops the skill and the CLI drifting apart. The first caps what a
mode costs to read; the second asserts that every subcommand `jsk` dispatches is named in `SKILL.md`
and `docs/SCRIPTS.md`, and that the agent boundary above is still written in the agent files.

A failing test after a refactor means the refactor was wrong. Do not edit a test to accommodate a
change in behaviour unless the behaviour change is the point and it is written down.

## Dependencies

Deliberately close to zero, and **`pyproject.toml` declares none as required** — every one is an
optional extra, imported at the point of use. `pip install jsk-resume` gives a working record gate,
prose gate and `.txt` parse gate on a bare interpreter. `jsk doctor` especially, because a preflight
that needs installing first is not a preflight.

```bash
pip install jsk-resume              # the record gate, prose gate, .txt parse gate
pip install 'jsk-resume[all]'       # + pymupdf
pip install -e '.[dev]'             # the above plus pytest, pytest-xdist, ruff
```

| Required | Why |
|---|---|
| a TeX engine | the PDF is the only rendered deliverable; without one there is nothing to send |
| `pymupdf` | without it the parse gate and the page budget are both unverifiable |

There are no optional extras left. `pyyaml` went with the bundle format — nothing reads YAML off disk
any more. `jsonschema` went too, and it is the more instructive of the two: **nothing ever imported
it.** It was declared, reported by `jsk doctor` as a capability, and documented as unlocking "full
schema validation in `validate_urs.py`" — and there was no URS JSON Schema for it to validate
against. A dependency that buys a line in a report and nothing else is worse than none, because it
teaches people the report is decorative.

A TeX engine and `pymupdf` were optional while the `.docx` was the portal artefact. `jsk doctor`
reports their absence as BLOCKED rather than a gap. LibreOffice left the list entirely: it existed
only to render the `.docx` for measurement.

Anything that cannot run reports loudly and exits non-zero rather than passing quietly.

## Releasing

There are **two release trains** since the code left the skill, and they version independently.

The **plugin** version lives in two files and they must agree — `tests/test_plugin_surface.py`
asserts it:

- `plugins/jsk/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

The **CLI** version is `__version__` in `src/jsk/__init__.py`, which `pyproject.toml` reads through
`[tool.hatch.version]`. `jsk --version` and `jsk doctor` both report it.

```bash
python -m build          # wheel + sdist into dist/
```

Tag them distinctly — `cli-vX.Y.Z` and `plugin-vX.Y.Z` — or the history stops being readable.

Before tagging: run the tests, run `jsk doctor` (the verifying form, not `--quick`), and check that
every internal doc link still resolves.

**The version skew this introduces is real and is not yet handled**, and version 4.0 makes it sharper
rather than softer: a plugin on the new markdown against an installed `okf` finds no `jsk` command at
all, which at least fails loudly. The subtler case — a flag the installed CLI does not have — still
fails mid-session on an argparse error. The fix is a floor the skill states and
`jsk doctor --require X.Y` enforces; it is not built.

---

Next: [Why it works this way](WHY.md) · [Commands](SCRIPTS.md)
