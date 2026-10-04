# Retire the CLI verbs the MCP tools duplicate

Date: 2026-10-04. Branch `feat/graph-native-mcp`, still unreleased as 6.0.0.

## The decision

6.0 serves the career and its applications as MCP tools (`jsk mcp`), and every agent reaches the record
through them. Eleven CLI verbs now either duplicate a tool or are called by nothing. The person chose to
retire all of them (2026-10-04):

| Retired | Group | Replacement it names |
|---|---|---|
| `jsk kb apply` | write | the `career_preview` and `career_apply` tools |
| `jsk kb confirm` | write | the `career_confirm` tool |
| `jsk kb show` | read | the `career_show` tool |
| `jsk kb view` | read | the `career_view` tool; `jsk kb dump` for the whole record as TriG |
| `jsk kb query` | read | the `career_query` tool |
| `jsk kb log` | read | the `career_log` tool |
| `jsk kb export` | unreferenced | the `resume_select` tool; `app_show` prints the selection |
| `jsk kb path` | unreferenced | `jsk doctor` (it names the workspace) |
| `jsk app freeze` | app | the `app_freeze` tool |
| `jsk app event` | app | the `app_event` tool |
| `jsk letter check` | letter | the `letter_check` tool |

These stay, because no tool does their job and agents with Bash run them:
- `jsk doctor` and `jsk mcp`
- `jsk kb new`, `check`, `load`, `dump`, `pack` and `merge`
- `jsk resume check`, `render`, `preview`, `fit` and `ship`
- `jsk app drop`

## Rulings

1. **They go into 6.0.0.** Nothing is tagged and `origin/main` does not hold 6.0, so there is no
   released version to warn from first.
2. **Each retired verb exits 2, names its tool, and writes nothing** (CLAUDE.md's frozen-surface rule).
   - One mechanism serves every noun. `main.RETIRED` takes `"<noun> <verb>"` keys, and `main` checks
     them before dispatch for any noun, including `kb`, whose adapter prints its own usage.
   - The noun `letter` has no verbs left, so it goes into `RETIRED_NOUNS`.
   - The old top-level `event` and `freeze` entries now name the tools, not `jsk app ...`.
3. **`mcp` becomes a required dependency.** Without `kb apply` and `kb confirm` a plain install cannot
   change a career, so the tools are the product, not an extra.
   - `dependencies = ["pyoxigraph>=0.5.11,<0.6", "mcp>=1.30,<2"]`.
   - The `mcp` extra stays as an alias, so `pip install 'jsk-resume[mcp]'` still works.
   - `mcp` is still imported only inside `adapters/mcp`, so `jsk doctor` and `preflight.py` stay
     standard-library only.
   - `adapters/mcp/__init__.too_old()` stays: a global Python can still hold an old `mcp` that another
     package pinned.
4. **The application and compose layers stay. Only the CLI front ends go.**
   - The MCP tools already call `compose.career` (`view`, `show`, `query`, `log`, `apply_changeset`,
     `confirm_ids`), `compose.selection.confirm`, `compose.timeline`, and the letter gate.
   - Delete:
     - `adapters/cli/freeze.py` and `adapters/cli/event.py`
     - `adapters/cli/kb/confirm.py` and `kb/export.py`
     - `kb/read.py`'s `cmd_show`, `cmd_view`, `cmd_query`, `cmd_log` and `cmd_path` (`cmd_check` stays)
     - `kb/write.py`'s `cmd_apply` and `changeset_text`
     - `main.app_freeze` and `main.letter_check`
     - `dispatch`'s `timeline.py` entry
   - Keep what `kb/load.py` and `kb/draft.py` still import.
   - Keep `application/tailor/export.py`: `resume_select` uses it.
   - `adapters/cli/gates/letter.py` stays only if `adapters/mcp/acts.letters` reaches it. Otherwise move
     what the act needs and delete the rest.
5. **Every message names a tool, never a retired verb.**
   - All of the following say "the career_apply tool (jsk mcp)", or the matching tool, instead of the
     retired verb:
     - "fix:" lines
     - refusals
     - `kb pack` / `kb merge` "not applied" notes
     - `jsk --help`
     - `kb --help`
     - docstrings
   - The verdict lines themselves (`PASS - safe to send`, ...) are untouched.
6. **Tests move to the layer that remains, and keep their rule.**
   - A test of a retired verb's behaviour (a diff, a refusal, a confirm landing, a query's output) calls
     what the tool calls, through a new test kit `tests/recordkit.py`. The kit exposes:
     - `apply(root, text, dry_run=False)`
     - `confirm(root, ids, ...)`
     - `show`, `view`, `query` and `log`
     - `freeze` and `event`
     - `letter(...)`

     Each returns `(exit code, output)` in the shape the old CLI helper returned, so assertions on
     output text carry over.
   - The kit formats compose results the way the MCP tools do. If a tool's text differs from what the
     CLI printed, the test asserts the tool's text and says so in a comment.
   - Tests of a retired verb's flag parsing or usage go. Each is replaced by a `test_retired.py` case
     asserting exit 2, the replacement named, and the store unchanged.
   - `test_graph_queue.py` keeps concurrent writers. It starts child interpreters that call
     `compose.career.apply_changeset` through `python -c`, because the queue (`record.turn`) is what it
     pins, not the CLI.
   - No test is weakened to pass. A failing assertion means the conversion is wrong.
7. **The prose follows.**
   - The skill, the mode files, the agents and `kb-format.md` name tools.
   - `docs/SCRIPTS.md`, `docs/ARCHITECTURE.md`, `docs/QUICKSTART.md`, `README.md` and `CLAUDE.md` follow.
   - `CHANGELOG.md` gets the 6.0.0 entries.
   - `test_plugin_surface.py` (every dispatched subcommand named) and `test_budget.py` (mode-file
     size) still hold.
   - Commands and the main session reach `career_confirm` through the `mcp__plugin_jsk_graph__*`
     wildcard. Still no agent is granted it.

## Phases

- **P1, code (one agent):** Rulings 2-5 under `src/`, plus `pyproject.toml`.
  - Add `tests/recordkit.py` and the new `test_retired.py` cases.
  - Run the suite and list the failures by file. Do not commit.
- **P2, tests (two agents, disjoint files):** convert the failing test files under Ruling 6.
  - Agent A takes `test_kb_*`, `test_graph_*` and `storekit.py`/`careerkit.py`.
  - Agent B takes everything else.
  - Neither touches `test_plugin_surface.py` or `test_budget.py`.
- **P3, prose (one agent, alongside P2):** Ruling 7, including `test_plugin_surface.py` and
  `test_budget.py`.
- **P4, verify:**
  - Full suite, ruff, pyright and the budget test run alone.
  - A code review of the diff.
  - A replay on a scratch copy of the real workspace (`C:\Projects\basilin-joe-resume`):
    - each retired verb exits 2 and the store's revision does not move;
    - a changeset, a confirm, an event and a letter check go through the tools;
    - `kb pack`/`merge` output is applied with `career_apply`.
  - Reinstall the plugin and the global `jsk`.

## Status

- P1 (code), P2 (tests) and P3 (prose): done, in `07fdd50`.
  - The repo has no `CHANGELOG.md`; the 6.0.0 notes live in `README.md`, which lists the retired verbs.
  - `jsk doctor` checks `mcp` as a required package beside pyoxigraph (Ruling 3); the `info` extras line
    and the `--json` `extras` key went with the extra.
  - Every fix line names a tool and its argument names: `career_confirm`'s `source`/`quote`/answer, not
    `--source`/`--quote`/`--answer`; `career_query("concepts", [term])`, not `--near`; the letter gate's
    `record=`, not `--record`. `jsk resume check` keeps its own `--record`.
  - Tests deleted with their verb test flag parsing, file or stdin reading, `--help`, or `kb path`. The
    unloaded-workspace refusal, pinned until now through the retired verbs, is pinned on the tools
    (`test_mcp_server.Unloaded`).
- P4 (verify): done.
  - Results: the full suite passed (1582, 3 skipped), ruff and pyright are clean, and the budget test
    run alone took 487 ms.
  - The code review had no shell, so I compared the deleted tests by name myself: every behaviour that
    still exists maps to a renamed or converted test.
  - The replay ran on a scratch copy of the real workspace:
    - each of the 11 verbs exits 2, the revision stays at r95, and no file changes;
    - `career_view`, `career_query`, `career_confirm`, `app_event` on a frozen application, and
      `letter_check` against a graph-native application all go through the tools;
    - `jsk kb check` still validates.
  - `kb pack capabilities` had nothing to add to that career, so applying a drafted changeset through
    `career_apply` was exercised by the suite, not the replay.
  - The replay found one defect, now fixed: `letter_check` given a file-made application read its name
    as a path holding a `resume.json`. It now refuses: no selection to trace a number against.
