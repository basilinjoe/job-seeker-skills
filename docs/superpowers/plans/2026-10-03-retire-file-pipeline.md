# Retire the file-made application pipeline - implementation plan

## Status (2026-10-03)

P1 built (2026-10-03). P2 waits on its precondition (below). Builds on
`2026-10-01-graph-native-applications-mcp.md`, whose Ruling 11 left the file pipeline in place
"until a later plan's decision". This is that plan.

**Spec:** none. This plan and its Rulings are the spec. The decision is the user's (2026-10-03):
the CLI keeps what no tool does (setup, maintenance, CI, the verifier's tracing) and what
duplicates a tool cheaply; the commands that exist only to serve applications made from files
retire.

**Precondition.** No *unsent* application made from files is left in the person's workspace. On
2026-10-03 the author's workspace held 7 applications frozen in the store and 15 directories with
a `resume.json`, so about 8 file-made applications were unsent. Each is sent and frozen, or
dropped, before P2 ships. P1 makes that list visible.

## What retires, and what replaces it

| Retires | Serves only | Replacement |
|---|---|---|
| `jsk posting fetch URL D` | `posting.md` | `posting_capture(app, url=)` |
| `jsk posting extract D` | `posting.md` | `app_show(app, part="lines")` |
| `jsk posting build D [decisions]` | `decisions.txt` | `posting_decide`, `posting_complete` |
| `jsk tailor prepare D [--draft-gaps]` | `gaps.txt` digest/draft | `assessment_derive` |
| `jsk tailor match D [--gaps F \| --draft-gaps F]` | `gaps.txt` | `assessment_derive`, `assessment_review`, `assessment_complete` |
| `jsk kb export --from-match D --out R.json`, `--ranked --out R.json` | `resume.json` | `resume_select(target, mode)` |
| `jsk resume check\|render\|preview\|ship <resume.json>` | `resume.json` | the same verbs on `<stem>` / `resumes/<name>` |
| `jsk kb confirm --summary\|--headline <resume.json>` | `resume.json` | `career_confirm(target, block)` / `--summary <stem>` |
| `jsk letter check L --record <resume.json>` | `resume.json` | `letter_check(letter, record=<stem>)` / `--record <stem>` |
| `jsk app freeze D` on a file-made application | `resume.json` | `app_freeze` on a graph-native one |

**Stays:** `jsk mcp`, `jsk kb new`, `jsk doctor`, `jsk kb dump|load`, `jsk kb check|show|view|query|log|path|pack|merge|apply|confirm <ids>`, `jsk resume check|ship <stem>`,
`jsk resume check <dir> [--only ...]` (the verifier), `jsk resume fit TEX`, `jsk app event`,
`jsk app drop` (not a file verb: it sets any unsent application aside, Ruling 5),
`jsk app freeze` and `jsk letter check` on graph-native applications. The `tailor` and `posting`
nouns go whole.

## Rulings

1. **Two releases, never a silent shim** (CLAUDE.md). Release N (P1) keeps every file verb
   working and prints one WARN line on each: `WARN  <command> serves applications made from
   files and retires in <N+1> - finish this application or drop it` with the replacing tool as
   its fix. Release N+1 (P2) makes each retired command exit 2 naming its replacement, through
   `main.py`'s retired-commands table (the precedent `jsk new` → `jsk kb new` uses).
2. **What is frozen stays readable.** A frozen file-made application's graphs stay in the store
   and are validated on every load: `quote-verbatim` and `advert-uncovered` read its
   `posting.md` and `decisions.txt` (`ports/advert.py`, `infra/adverts.py`,
   `domain/record/advert_rules.py`). That read path stays, read-only and for frozen postings
   only. Nothing that writes a file-made application survives. Converting frozen adverts into
   `j:AdvertLine`s was weighed and declined: `refuse_if_sent` forbids rewriting a sent
   application's graphs, and the files are the archive of what was sent.
3. **`resume.json`'s format stays frozen as an interchange shape** (CLAUDE.md "Frozen public
   surfaces"): `domain/resume/short.py` still checks the dict `doc_of(selection)` returns, and
   `plan.build` still takes it. Only the *file* goes: no command reads or writes a
   `resume.json` path after P2.
4. **The import keeps working.** `jsk kb load` of a dump or an old workspace still loads frozen
   file-made applications (their graphs and the read path of Ruling 2). It no longer tells the
   person to copy `decisions.txt` or `gaps.txt` (`load.py:59`, `load_import.py:196`): only
   `posting.md` and the renders.
5. **An unsent file-made application found after P2 is not stranded silently.** `app_list`,
   `jsk doctor` and `kb check` name it with the fix "send it with this 5.x CLI (jsk 5.1.0) before
   upgrading to 6.0, or drop it: `jsk app drop applications/<stem>`". The CLI version that still
   finishes it is named in the message.

   *Amended 2026-10-03:* the fix first read "or drop it (`jsk kb apply` a changeset retiring its
   posting)". That could not be followed: a changeset writes only the career graph, never an
   application's, and many unsent applications have no posting graph at all. `jsk app drop
   <app-dir> [--reason TEXT] [--dry-run]` is the command now (`application/timeline/drop.py`):
   for an application that is not frozen it removes every graph the store holds for it in one
   validated update, then moves its folder, files intact, to `dropped/<stem>/` with a
   `DROPPED.txt`. A frozen one, sent or held back, is refused as an archive. It is not a file
   verb, so 6.0 keeps it (Stays, above).

## Phases

### P1 - release N: say what is retiring (5.1.0)

- The WARN of Ruling 1 on every file verb in the table, and a test per verb that it prints and
  that the command still works (exit code and verdict lines unchanged; the WARN is an added line).
- `app_list` reports `unsent: true` for each unsent file-made application; `jsk doctor` prints an
  `info` line counting them; `kb check` a WARN `file-made-unsent` (a rule across entries: its
  mutation in `tests/test_graph_rules.py`).
- Prose: SKILL.md, mode-tailor.md and docs/SCRIPTS.md say the file verbs retire in 6.0 and
  where the list of unsent ones is.
- Version 5.1.0 in `__version__`, `plugin.json`, `marketplace.json`.

### P2 - release N+1: retire (6.0.0)

Only once the precondition holds for the author's workspace (checked with `app_list` on it).

- `adapters/cli/main.py`: `posting` and `tailor` leave `NOUNS`; their verbs join the retired
  table with replacements. `kb export --out`, the `resume.json` positional of `resume
  check|render|preview|ship`, `kb confirm --summary|--headline <file>`, `letter check --record
  <file>` exit 2 naming the target form. `resume render` and `resume preview` gain the target
  form first (P3b of the graph-native plan gave `check` and `ship` one; `preview` has none
  today).
- Code deleted, each after an LSP `findReferences` shows no caller left but the ones going:
  - `application/posting/{fetch,extract,build}.py`'s file paths (capture keeps
    `fetch.source/advert`), `adapters/cli/posting.py`, `compose/posting.py`'s file folder;
  - `application/tailor/{prepare,draft_gaps,match_text}.py`, `check_gaps.py`'s file branch and
    `gaps_refusal`, `adapters/cli/{match,tailor,prepare}.py`;
  - `domain/record/decisions.py` (the text format; `Drop` moves to `domain/posting/rows.py`
    if `check_gaps.render` still needs it), `domain/assessment/overlay.py`'s `parse` (the
    `Overlay` dataclass stays: the review graph reads into it), `domain/assessment/draft.py`;
  - `domain/posting/posting_md.py` and `errors.BROWSER_FIX`'s hand-written-file advice;
  - the file branches of `load_resume`, `record_gate`, `confirm_summary`, `freeze.check`,
    `letter.check_letter`, `guards.record_refusal`, `application/tailor/export.write`.
- Kept, per Ruling 2: `infra/adverts.py` and `advert_rules`' file reads, guarded to frozen
  file-made postings, with a test that a frozen legacy posting still validates and an unsent
  one is reported (Ruling 5).
- Tests: the file-pipeline tests go with their code (`test_posting_build`, `test_gaps_build`,
  `test_gaps_draft`, `test_gaps_txt`, `test_decisions`, `test_tailor_prepare`,
  `test_tailor_match`, `test_graph_match`'s `--gaps` cases, `test_awkward_input`'s file reads,
  the `resume.json` CLI cases in `test_resume_check`, `test_record_gate`, `test_resume_ship`,
  `test_kb_confirm`, `test_grammar`, `test_letter`). Each behaviour they pinned that still
  exists for graph-native applications is checked to have a graph-native test before its file
  test is deleted (a table in the commit message: file test -> graph-native test). The match
  fixtures (`tests/match_fixtures/`) stay: `jsk kb query` and the derivation still run on them.
- A test per retired command: exit 2, its replacement named, nothing written.
- Docs: SCRIPTS.md loses the posting/tailor sections and the `resume.json` forms; ARCHITECTURE.md
  the tailoring pipeline's file diagram and every deleted module's layout line
  (`ArchitectureNamesTheCode`), and the noun count; SKILL.md, mode-tailor.md (the file-made
  paragraph becomes Ruling 5's one line), `resume-format.md` (the keys as the selection's,
  no file), README, QUICKSTART, CONCEPTS, WHY. `test_plugin_surface.py`'s pins on
  "Keep `resume.json` inside the workspace" and "a `resume.json` outside a workspace has no
  career to build from" change on purpose.
- Version 6.0.0.

### P3 - replay and review

- Replay on a scratch copy of the real workspace (never the original): `jsk kb check` clean
  with the frozen file-made applications in it; each retired command exits 2 with its
  replacement; a full graph-native application through the tools, freeze included.
- A code review of the deletion (callers left behind, a frozen record that no longer
  validates) and a prose review (a retired command still named).

## Risks

- **A frozen record stops validating.** Ruling 2's read path and its test; the replay over the
  real workspace's frozen applications.
- **Coverage lost with the deleted tests.** P2's file-test -> graph-native-test table; nothing
  is deleted without its row.
- **Other people's unsent applications.** The two-release path, Ruling 5's message, and the
  release notes naming the last version that finishes a file-made application.
- **The size of P2.** It touches most of `application/tailor` and the CLI. It is split into
  commits by noun (posting, tailor, export, resume, confirm, letter, freeze), each green.

## Verification

1. `python -m pytest tests -n auto`, ruff, pyright on the rings, `test_graph_budget.py` alone.
2. CI on Linux and Windows; the package job's `jsk posting build` exits 2.
3. P3's replay.
