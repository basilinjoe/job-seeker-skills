# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Installed CLI Tools
- **ripgrep** (`rg`) is installed — use instead of `grep` for file content searches.
- **fd** is installed — use instead of `find` for finding files by name.
- **sd** is installed — use instead of `sed` for regex find-and-replace text tasks.
- **jq** is installed — use for processing JSON objects in shell workflows.

## Code navigation
- A Python LSP (pyright) is available through the `LSP` tool. It is deferred, so the schema is not loaded
  until you ask: run ToolSearch `select:LSP` as the first step of any task that touches Python under `src/`
  or `tests/`.
- Before you rename, move, delete, or change the signature of a Python symbol, run `findReferences` on it.
  `rg` misses re-exports (`from .x import y as y`), lazy imports inside functions, and attribute calls.
- To answer "where is this defined" or "who calls this", use `goToDefinition` or `incomingCalls`,
  not `rg`. Keep `rg` for text, strings, docs and non-Python files.
- When you hand Python navigation to a subagent, tell it in the prompt to load `LSP` first.
  A subagent does not inherit the tools this session has loaded.

## What this repo is

Two things that ship and version on their own:
- **`jsk-resume`**, a Python CLI (`src/jsk/`, the `jsk` command). It keeps a person's career as an RDF
  graph in a pyoxigraph/RocksDB store (`career/store/`) and renders verified resumes from it.
  Its version is `__version__` in `src/jsk/__init__.py`.
- **The `jsk` Claude Code plugin** (`plugins/jsk/`): one skill (`skills/jsk/SKILL.md` plus `references/mode-*.md`),
  slash commands, and five subagents that drive the CLI. Its version is in `plugins/jsk/.claude-plugin/plugin.json`
  and `.claude-plugin/marketplace.json`, and the two must agree.

`docs/ARCHITECTURE.md` is the contributor guide. Its "Where do I change X" table lists, for each kind of change,
the files that have to move together. Read it before you change behaviour.

## Commands

```bash
uv sync --extra dev                        # or: pip install -e '.[dev]'
python -m pytest tests -n auto             # full suite in parallel (~5-6 min on 6 cores; CPU-bound: store writes, TeX, subprocesses)
python -m pytest tests/test_themes.py -q   # one file
python -m pytest tests/test_build.py -q -k <name>   # one test
python -m unittest discover -s tests       # same suite with no pytest
python -m ruff check src tests             # lint (CI gate)
python -m pyright src/jsk/domain src/jsk/ports src/jsk/application src/jsk/infra src/jsk/adapters   # type check (CI gate)
python -m pytest tests/test_graph_budget.py -q -rs -s   # load-time budget; run it alone, not beside the parallel suite
jsk doctor [--quick]                       # what this machine can do (TeX engine, pymupdf)
python -m build                            # wheel + sdist
```

- The tests are standard-library `unittest`. `tests/fixtures.py` puts `src/` on the path, so the suite always
  tests the working tree, not the installed package.
- Render tests skip themselves when no TeX engine or `pymupdf` is installed. Without a TeX engine,
  `jsk doctor` reports BLOCKED and exits 1. That is by design.
- Committed fixture workspaces (`tests/graph_fixtures/`, `match_fixtures/`, `claims_fixtures/`) are copied before
  they are changed. `tests/careerkit.py` builds edited careers in temp directories.

## Architecture

**Onion rings, enforced by a test.** Every module under `src/jsk/` belongs to one of five rings: `domain`, `ports`,
`application`, `infra`, `adapters`. A module may import only from its own ring or one further in.
`tests/test_layers.py` walks every import, including lazy imports inside functions, and fails on:
- an edge that points outward;
- a module that belongs to no ring.

The domain has extra limits:
- no `os`, `sys`, `pathlib`, `subprocess` or `open()`;
- no reading the clock;
- no Store;
- from pyoxigraph, only term classes such as `NamedNode` and `Literal`, imported inside functions.

Ports are `typing.Protocol`s. Infra implements them. `adapters/compose/` is the one composition root: it binds
real ports to use cases and reads the clock once, for both doors (`adapters/cli/`, the `jsk` command, and
`adapters/mcp/`, the tools); `adapters/entry/` holds the argv entry points they both run. Root modules `cli.py`, `__main__.py` and `preflight.py` count as
adapters, and `paths.py` counts as infra.

**The render plan is the narrow waist.** `domain/resume/plan.py` builds the plan once from the career plus a target's
selection (`<stem>` or `resumes/<name>`), stored as a graph with `resume.json`'s keys. It holds bullet ids in order and
settings, never a bullet's words; no command reads a `resume.json` file since 6.0. `domain/render/emit_latex.py`
and `emit_text.py` turn the finished plan into markup and decide nothing, which is why the PDF and the text the gates
read cannot disagree. No `.txt` is written: the gates read `emit_text.emit(plan)` in memory. Content selection goes
in `plan.py`, never in an emitter.

**A model writes only decisions; code writes every graph.** A new application is graph-native: agents send their
decisions to `jsk mcp` tools (`posting_capture` → `posting_decide` → `posting_complete` → `assessment_derive` →
`assessment_review` → `assessment_complete` → `resume_select`/`resume_update` → `resume_ship` → `app_freeze`),
and code writes and checks every triple:
- every quote is a stored line of the advert;
- a verdict can only be lowered from the match's, never raised.

Each agent's `tools:` lists its MCP tools by name, which is what holds it to its boundary (the analyst has no tool
that writes the career; no agent has `career_confirm`). The plan is
`docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md`. 6.0 retired the file-made pipeline
(`jsk posting`, `jsk tailor`, every `resume.json` form; `docs/superpowers/plans/2026-10-03-retire-file-pipeline.md`):
each exits 2 naming its replacement - the two nouns through `adapters/cli/main.py`'s `RETIRED`, each `resume.json`
form by its own verb's adapter (`application/guards.resume_json_refusal`). A frozen file-made application stays
readable - `domain/record/advert_rules.py` checks its quotes against its `posting.md` - and an unsent one is named by
`career_check`, `app_list` and `jsk doctor` (`application/timeline/unsent.py`).

**One write gate for the record.** Every career change goes through the `career_apply` and `career_confirm`
tools (`jsk mcp`; 6.0 retired `jsk kb apply` and `confirm`), over one validate → write → log path. Writes land in
`infra/oxigraph/record.py` and storage is in `infra/oxigraph/db.py`.
`tests/test_db.py` fails if a second module opens or writes the store. New claims always arrive `j:inferred`, and only
`career_confirm` with the person's answer can raise them. `career_pack` and `career_merge` draft changesets
(they write nothing) that are applied by passing their text to `career_preview`, then `career_apply`.

**The format lives in two places.** `src/jsk/domain/ontology.py` *is* the record format. Its prose is in
`plugins/jsk/skills/jsk/references/kb-format.md` and `docs/ONTOLOGY.md`. A class or predicate that appears in one and
not the others is a defect.

**The CLI keeps five commands.** Everything else is a tool of `jsk mcp` (6.0;
`docs/superpowers/plans/2026-10-04-mcp-first.md`), and its old command exits 2 naming the tool. What stays is
`jsk doctor`, `jsk kb new`, `jsk kb load`, `jsk kb dump` and `jsk mcp`, because each has to work when the server
cannot start or no session is running. Dispatch is in-process: `adapters/cli/main.py` holds the noun table, and
`adapters/entry/dispatch.py`'s `ADAPTERS` maps each verb to its adapter's `main()`. A tool reaches the same entry
points through `adapters/mcp/captured.py`, so the `resume_ship` tool runs every gate (record, then render, then
parse, prose and layout) in one interpreter, and a verdict line is the text the tests pin, word for word.

## Conventions

The commenting and coding standards for `src/` are in `.claude/rules/src-standards.md`. They load when you work on
files under `src/`. Outside `src/`:

- **Test modules start with a docstring naming the documented rule they pin.** Inline comments in tests say why an
  assertion matters.
- **Tests:**
  - standard-library `unittest` only, never pytest imports;
  - test classes are named for the subject (`class Read`);
  - test methods read as the rule in a sentence: `test_a_legacy_record_points_at_export`;
  - build workspaces in `tempfile.TemporaryDirectory()` via `careerkit`, and never change a committed fixture
    in place;
  - a new check gets a test that plants the violation and asserts it fails. A passing fixture alone can encode
    the hole.
- **Commits:** Conventional Commits types (`feat`, `fix`, `refactor`, `docs`, `test`). The subject is a lowercase
  sentence stating the result, not the action: `refactor: the clock is read once, at the edge; untraced takes no
  date`.

## Rules that will bite you

- **Tests assert on exact output text** (`PASS - safe to send`, `DO NOT SEND`, …). You may add output lines.
  Rewording an existing verdict line breaks the gate's tests.
- **Docs are pinned by `tests/test_plugin_surface.py`:**
  - every dispatched subcommand must be named in `SKILL.md` and `docs/SCRIPTS.md`;
  - every module under `src/jsk/` must appear in ARCHITECTURE.md's repo layout, so a new module with no line there
    fails the suite;
  - the agent-boundary sentences must still be in the agent files;
  - the two plugin versions must agree.
- **`tests/test_budget.py` caps how much each mode file costs to read.**
- **A rule across entries** (`domain/record/rules.py`) needs a mutation in `tests/test_graph_rules.py`.
  A rule without one fails the suite.
- **Frozen public surfaces:**
  - the `jsk` noun/verb/flag set;
  - a selection's keys - `resume.json`'s, the interchange shape (`"resume": 2`, and an unknown key fails);
  - the career format (`ontology.FORMAT`). Optional additions are fine. A rename, a removal, or a new required
    field needs a format revision and a migration.

  A retired command or flag exits 2 and names its replacement. It never gets a silent shim.
- **Dependencies:** two are required. pyoxigraph is pinned to one minor version because the store's on-disk
  format follows it. `mcp` (the SDK behind `jsk mcp`) became required in 6.0, because its tools are the only way to
  change a career; it is imported only inside `adapters/mcp`, and `jsk doctor` checks it like pyoxigraph. Both are
  imported inside functions, so `jsk doctor` and `preflight.py` stay standard-library only. Everything else is
  optional and imported where it is used. Lazy imports (`PLC0415`) are deliberate.
- **Ruff** covers only `E,F,W,B,BLE`, with line length 100. Every `noqa: BLE001` states on its own line why nothing
  narrower will do.
- **A failing test after a refactor means the refactor is wrong.** Don't edit a test to fit new behaviour unless that
  change is the point and it is written down.
- **`docs/superpowers/`** holds dated specs, plans and experiments. They are history and rulings, not current docs.
  The specs carry the rulings that ARCHITECTURE.md cites, such as `2026-09-30-onion-architecture-design.md`.
