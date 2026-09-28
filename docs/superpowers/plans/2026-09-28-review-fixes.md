# Review fixes - implementation plan

**Spec:** none. This plan and its Rulings are the spec. The evidence is a full review of
`src/jsk` on 2026-09-28: one pass over this branch's diff, then five reviewers over the whole
package (graph core, matching and tailoring, CLI and kbcli, render/resume/gates, migrate). Every
finding below was re-read against the source before it was listed. None has been reproduced by
running it yet: each task's first step is the failing test that does that.

The plan fixes the nine defects, and it also removes the four patterns that produced them, so
that the next one of each kind cannot be written.

## Context

### The defects

| # | Where | Defect | Pattern |
|---|---|---|---|
| 1 | `cli.py:434-446`, `:1029` | `jsk freeze` archives a cover letter no gate read | C |
| 2 | `graph/postingbuild.py:276-279` | `posting build --replace` on a sent application deletes its frozen `gaps.ttl` / `gaps.md` | B |
| 3 | `migrate.py:1822-1823` | a BOM in `application.md` hides its frontmatter; the application is skipped and its `resume.json` shortened as a draft | A, B |
| 4 | `graph/gapsbuild.py:92-96` | `keep` on a row whose flag the career has since cleared FAILs | D |
| 5 | `graph/gapsbuild.py:97-99` | a row restating the match's verdict FAILs "no reason" before the "delete the row" WARN | D |
| 6 | `graph/record.py:47-62` | `int()` on a revision literal (`j:revision 3.0`) raises out of `store.load()` | A |
| 7 | `graph/postingbuild.py:49-52`, `:159-161`, `graph/gapsbuild.py:309-310` | a non-UTF-8 `posting.md`, `decisions.txt` or `gaps.txt` raises `UnicodeDecodeError` past `except OSError` | A |
| 8 | `render/render_resume.py:61-65` | `company_of` reads `posting.ttl` strictly; a non-UTF-8 one crashes `jsk render` without `--name` | A |
| 9 | `graph/kbcli.py:436-437` | `inside()` calls `os.path.commonpath` across drives, which raises `ValueError` | A |

**Below the bar, kept as notes:**

- `graph/pack.py:220` calls `short_string` directly, bypassing `writer.literal`'s newline guard. No
  caller passes a newline today (Task 12).
- `migrate.achievements()` swallows a `resume.json` parse failure and drops the bullet links. This
  matches the file's stated "not ours to judge; jsk validate names it", so it is left alone.

**What held up** and is not in scope: LaTeX escaping (`emit_latex.SPECIALS` is complete), the
`fit_pages` lever loop, `record.commit`'s staged write, Turtle output through pyoxigraph objects,
and ranking and verdict logic in `match` / `select` / `queries`.

### The patterns behind them

- **A. Every command reads its own files.** About 50 hand-written `open(...)` calls in `src/jsk`
  spell the encoding `utf-8` 42 times, `utf8` 4 times and `ascii` once. Only 11 places go through
  `io.normalise`, and each picks its own `except`. The code already knows the cross-drive trap:
  `store.file_name` (`store.py:80-89`) catches the `ValueError` that `relpath` raises across
  drives. `kbcli.inside` is the same situation, handled differently. Five of the nine defects are
  this pattern.
- **B. "A sent application is frozen" relies on each command remembering it.** The check lives in
  at least three places: `gapsbuild.sent`, `kbcli.py:559`, and freeze/ship in `cli.py`.
  `postingbuild` forgot it. `migrate` decides "frozen" by whether a file exists, which is a
  different test for the same thing.
- **C. Two lists that must agree are built separately.** Freeze decides what was sent from
  `os.listdir`, and the gates decide what to read from a `*_Resume*` glob. Nothing checks that they
  match.
- **D. Order-dependent `if` chains.** `gapsbuild.check` appends findings from a series of `if`s,
  so the result depends on which test runs first, and two findings can fire for one row.

### What does not catch them today

- Ruff selects only `E`, `F` and `W` (`pyproject.toml:97`). `B` (bugbear) and `BLE` (blind except)
  are the rule sets that look at exception handling.
- Pyright is configured, but the comment at `pyproject.toml:126` says nothing in CI runs it.
- No test feeds the readers a BOM, CRLF line endings or cp1252 bytes. Findings 3, 7 and 8 would
  each have failed such a test.

### Size

`src/jsk` is 18.1k lines, of which about 3.7k (20%) are docstrings and comments. They record the
rulings, so this plan does not cut them for their own sake. The reductions that are real:

| Where | Size | What |
|---|---|---|
| `migrate.py` | 2,518 lines, 116 functions | A one-time conversion from the old format. It can move out once no workspace needs it: about 14% of the code. |
| File reads and refusals | ~50 call sites | The Task 1 helper removes 3–6 lines at each site: about 150–250 lines. |
| `cli.py` + `kbcli.py` | 2,422 lines | Arguments are parsed by hand in most commands, and `argparse` in 4 files. One style would shrink both. |
| Sent-application checks | 3+ copies | They become the one check in Task 2. |

Beyond `migrate.py`, expect 1–1.5k lines from the rest. Most of the value is fewer places where a
mistake can happen.

## Rulings

Each ruling says what it costs if it turns out wrong.

1. **One reader for authored text.** `graph/io.py` gains `read_text(path, what)`. It opens as
   UTF-8, passes the text through `normalise`, and raises one refusal type for a missing file
   ("no <what> at <path>") and for bad bytes ("<path> is not UTF-8 - save it as UTF-8"). Callers
   that must tolerate a missing file catch that type. *If wrong:* a caller that wanted the raw
   bytes reads them itself and is on the allowlist (Ruling 3).
2. **One pair of path helpers.** `inside(path, root)` and `rel(path, root)` live beside
   `store.file_name` and never raise across drives: `inside` answers `False`, and `rel` falls back
   the way `file_name` does. `kbcli.inside`, and the `relpath` calls in `kbcli`, `migrate` and
   `render_resume`, use them. *If wrong:* one helper's fallback changes, in one place.
3. **A test bans `open(` outside an allowlist.** `tests/test_plugin_surface.py`, beside the
   architecture test, greps `src/jsk` and fails on `open(` in any module not on a named list. Each
   entry carries a one-line reason: `io.py` reads, the writers write, the gates read PDFs through
   pymupdf, and so on. *If wrong:* a new module adds itself to the list, with its reason, where a
   reviewer can see it.
4. **The frozen rule lives where application files are written.** `timeline.py`, which owns
   `application.ttl`, gains `sent_day(app_dir)` and `write_app_file(app_dir, name, text)` /
   `remove_app_file(app_dir, name)`. The two writers refuse when the application is sent.
   `postingbuild`, `gapsbuild`, `kbcli`'s sent check and `cli`'s ship/freeze checks all go
   through them. Freeze's own write of `application.ttl` is the one exemption, because it is what
   makes the application sent. *If wrong:* a writer that has to touch a sent application is
   exempted by name, as freeze is.
5. **Every document freeze lists must have passed a gate that read it.** After `gate_results`,
   `cmd_freeze` checks that each entry in `sent` (excluding the `.tex` companions) was in some
   gate's `found`. A `.txt` or `.md` that is not `*_Resume*` goes through the letter gate with
   `--record` set to the application's `resume.json`. Any other unread document (a `.pdf` cover
   letter, for instance) refuses the freeze, with the fix "send the letter's .txt beside it, or
   leave it out with --doc". *If wrong:* someone who sends only a PDF letter cannot freeze without
   a `.txt` copy. That is one extra file, and it is the only way the letter gets checked.
6. **A sent application's posting is not rebuilt.** Through Ruling 4 this covers `posting.ttl`
   itself, not just the gaps files: a sent posting is what the application answered. *If wrong:*
   a genuinely mis-built sent posting has to be fixed by hand, which is what a frozen file already
   means.
7. **Each `gaps.txt` row gets exactly one outcome.** `check`'s per-row body becomes a function
   that returns one `(severity, text, fix)` or `None`, one case per return, in this order:
   - an unknown slug: FAIL;
   - an unfilled slot: none, because the slot FAIL names it;
   - `keep`: WARN if no flag asks about it now, otherwise none;
   - the match's own verdict: WARN, delete the row;
   - a raise: WARN if the career moved, otherwise FAIL;
   - no reason: FAIL;
   - a lowered row the match has since raised: WARN.

   This fixes findings 4 and 5. `fold` already treats `keep` and a restated verdict as the match's
   verdict, so neither row changed the output. *If wrong:* an analyst who writes `keep`
   everywhere gets warnings, not a stop.
8. **`company_of` falls back to no suffix.** It is a naming nicety, so a refusal from `read_text`
   returns `None`, as a missing file does. *If wrong:* the output file has no company in its name.
9. **A revision that is not an integer reads as unreadable.** `header_revision` and `last_entry`
   return `None` for a non-integer lexical value, and `record.state` then reports the same way it
   does for a missing one. Tier 1 already FAILs the datatype, so the person sees the real cause.
   *If wrong:* the log-sync rule reports out-of-step on a record that already FAILs.
10. **Lint and types grow one step at a time.** Ruff adds `B`, then `BLE`, each in its own commit,
    fixing or ignoring by line (with a reason) so that `ruff check src tests` stays clean.
    Pyright runs in CI on `src/jsk/graph/` first, in `basic` mode. *If wrong:* a rule set that
    is mostly noise is removed again, in one line.
11. **`migrate.py` leaves only when no workspace needs it.** It stays until you confirm that every
    workspace you care about has been migrated. Then it is frozen at a tagged release and removed
    from the package, and the release notes give the tag. *If wrong:* an old workspace installs
    that tag once.

## Global constraints

- Each task starts with a test that fails for the reason it names, and commits only once that test
  passes.
- `pytest` for the touched test files after each task. Before merging, run the full suite and
  `pyright` on each changed module.
- Match the refusal and finding wording already used in each module: `Refused(message, "fix:  …")`
  in `postingbuild`, `(severity, text, fix)` tuples in `gapsbuild`.
- Write fixtures with a BOM or with cp1252 bytes from Python (`bytes` literals), never with a
  shell heredoc, which can silently corrupt escape sequences.
- The plan holds no fix code. Where a task names a function, the implementer writes it and runs
  it; nothing here has been executed.

## Build order

- **Phase 1** (Tasks 1–2) is the foundation. Build it on the main thread, in order, before
  anything fans out: every later task calls into it.
- **Phase 2** (Tasks 3–7) fixes the defects through the foundation. The tasks touch different
  modules and can run as parallel subagents once Phase 1 is committed.
- **Phase 3** (Tasks 8–10) is the prevention layer. It can run in parallel with Phase 2, except
  Task 8, which needs Phase 2's readers in place to pass.
- **Phase 4** (Tasks 11–12) is reduction and is decided after Phase 3. Task 11 waits on Ruling 11.
- Do not commit on the main thread while an agent is working. An agent's `git commit --amend` can
  rewrite your commit.

---

## Phase 1 - the foundation

### Task 1 - one reader, one pair of path helpers, and the guard (Rulings 1–3)

- **Modify** `src/jsk/graph/io.py`: add `read_text` and its refusal type (Ruling 1).
- **Modify** `src/jsk/graph/store.py`: add `inside` and `rel` beside `file_name`, sharing its
  cross-drive fallback (Ruling 2).
- **Tests:** `tests/test_graph_io.py` and `tests/test_graph_store.py`:
  - `read_text` returns the same string for plain UTF-8, UTF-8 with a BOM, and CRLF input;
  - it refuses cp1252 bytes and a missing file, each with its own message;
  - `inside("D:\\x", "C:\\y")` is `False`, and `rel` falls back rather than raising. Skip these
    two tests when not on Windows.
- **Add** the `open(` guard to `tests/test_plugin_surface.py`, with today's modules on the
  allowlist, so that it passes now (Ruling 3). Phase 2 takes entries off the list as it moves each
  module over.
- Commit: `refactor: one reader for authored text, cross-drive path helpers, and a test that keeps reads in one place`.

### Task 2 - the frozen rule at the write (Ruling 4)

- **Modify** `src/jsk/graph/timeline.py`: add `sent_day`, `write_app_file` and `remove_app_file`.
  `gapsbuild.sent` becomes a call to `sent_day`.
- **Tests:** `tests/test_ship_freeze.py` (or a new `tests/test_frozen.py`): on a sent application,
  `write_app_file` and `remove_app_file` refuse and the file keeps its bytes. On an unsent one,
  they write and remove.
- Commit: `refactor: a sent application's files are refused where they are written`.

## Phase 2 - the defects, through the foundation

### Task 3 - freeze gates every document it lists (finding 1, Ruling 5)

- **Modify** `src/jsk/cli.py`: in `cmd_freeze`, add the letter gate for sent `.txt` / `.md` files
  that are not `*_Resume*`. It is `call_gate("letter.py", [doc, "--record", record])`, through
  `gate_result` as the other gates are. Then add the coverage check from Ruling 5 before
  `timeline.freeze`. Leave `rendered_documents` alone: `jsk gates` and `jsk ship` rely on it.
- **Tests:** `tests/test_ship_freeze.py`:
  - resume passes, `cover-letter.txt` holds a placeholder: freeze refuses and writes no
    `application.ttl`;
  - resume and a clean `cover-letter.txt`: freeze succeeds and lists both;
  - resume and `Cover_Letter.pdf` with no `.txt`: freeze refuses with Ruling 5's fix.
- Commit: `fix: freeze gates every document it archives, cover letters included`.

### Task 4 - builders write through the frozen rule (finding 2 and findings 4–5, Rulings 6–7)

These two parts share `gapsbuild.py`, so they go to one agent.

- **Modify** `src/jsk/graph/postingbuild.py` `build`: write `posting.ttl` and remove the gaps
  files through `write_app_file` / `remove_app_file`. Move the sent check to before any write, so
  that a refusal writes nothing.
- **Modify** `src/jsk/graph/gapsbuild.py`: write through `write_app_file`. Write the per-row
  outcome function from Ruling 7 **after** the table test below, then replace `check`'s loop body
  with it.
- **Tests:**
  - `tests/test_posting_build.py`: on a sent application, `--replace` refuses, and `posting.ttl`,
    `gaps.ttl` and `gaps.md` keep their bytes. An unsent one rebuilds as today.
  - `tests/test_gaps_txt.py`: a table test, generated, over every combination of:
    - verdict: `keep`, satisfied, partial, missing, indeterminate;
    - flagged or not;
    - reason given or not;
    - previous verdict: the same, raised, lowered, or none.

    Each case asserts exactly one outcome, taken from Ruling 7. Findings 4 and 5 are two of its
    rows, and must fail before the fix.
- **Take** both modules off the Task 1 allowlist.
- Commit: `fix: a sent posting is not rebuilt, and a gaps.txt row that lowers nothing warns`.

### Task 5 - readers go through read_text (findings 7 and 8, Rulings 1 and 8)

- **Modify** `postingbuild.read_advert`, `decisions.read`, `gapsbuild.build`'s `gaps.txt` read and
  `render_resume.company_of` to use `read_text`. `company_of` catches the refusal and returns
  `None`.
- **Then** move the remaining hand-written reads in `graph/`, `render/`, `resume/`, `posting.py`,
  `kb.py` and `kbindex.py` over, one module per commit, taking each off the allowlist. A read whose
  module owns a deliberate, documented `errors="replace"` (the gates' `read_tex`, `read_txt` and
  `letter.read`) stays, with that reason on the allowlist.
- **Tests:** a cp1252 `posting.md`, `decisions.txt` and `gaps.txt` (each with a `\x93` curly
  quote) each give a refusal or FAIL naming the file, with exit code 1 and no traceback. A cp1252
  `posting.ttl` beside the record renders with no company suffix.
- Commit, first: `fix: a posting, decisions or gaps file that is not UTF-8 is refused, not a traceback`.
  Then one `refactor: <module> reads through read_text` per module.

### Task 6 - migration reads through read_text (finding 3)

- **Modify** `src/jsk/migrate.py`: `application()` reads `application.md` with `read_text`, and so
  does every other text read in the file that does not already use `normalise`. Its `relpath` call
  (`migrate.py:2317`) uses `rel`.
- **Tests:** `tests/test_migrate.py`: an application whose `application.md` starts with a BOM and
  says `submitted: 2026-05-01` migrates to an `application.ttl`, and its `resume.json` is left
  unshortened.
- **Replay:** run the migration on a scratch copy of `C:\Projects\basilin-joe-resume\career`, never
  on the original. Confirm that the count of `application.ttl` files written matches the count of
  `application.md` files with a `submitted:` date.
- Commit: `fix: migration reads application.md through read_text, so a BOM cannot un-freeze it`.

### Task 7 - the remaining crashes (findings 6 and 9, Rulings 2 and 9)

- **Modify** `src/jsk/graph/record.py`: in `header_revision` and `last_entry`, return `None` for a
  lexical value that is not an integer. In `last_entry`, skip such entries when choosing the
  newest.
- **Modify** `src/jsk/graph/kbcli.py`: delete its `inside` and use the Task 1 helper. Its
  `relpath` calls (`kbcli.py:537`, `:584`) use `rel`. Its sent check (`kbcli.py:559`) uses
  `sent_day`.
- **Tests:**
  - `tests/test_graph_record.py` / `test_graph_store.py`: `k:kb j:revision 3.0` loads, has a tier-1
    FAIL on the datatype, and does not raise. First check that tier 1 does FAIL it; if it does
    not, add that check in this task.
  - `tests/test_graph_kbcli.py`: `jsk kb confirm --source` with a source on another drive refuses
    cleanly. Skip this test when not on Windows.
- Commit: `fix: a decimal revision and a path on another drive become refusals`.

## Phase 3 - prevention

### Task 8 - the awkward-input fixture

- **Add** a fixture in `tests/fixtures.py` that writes a given authored file four ways: plain
  UTF-8, UTF-8 with a BOM, CRLF line endings, and cp1252.
- **Add** a parametrised test that runs each command reading an authored file over all four. The
  commands are `posting extract` / `build`, `match --gaps`, `tailor prepare`, `render`,
  `kb confirm` and the migration. The first three forms must succeed with identical output. The
  fourth must refuse cleanly, or, for `render`'s company suffix, fall back.
- Commit: `test: every authored-file reader over BOM, CRLF and cp1252 input`.

### Task 9 - ruff's exception rules (Ruling 10)

- **Modify** `pyproject.toml`: add `B` to `select`. Fix or line-ignore each finding, with a reason,
  until `ruff check src tests` is clean. Commit. Then do the same for `BLE`.
- Commits: `chore: ruff checks bugbear`, `chore: ruff checks blind excepts`.

### Task 10 - pyright in CI (Ruling 10)

- **Modify** `pyproject.toml`: add `pyright` to the `dev` extra, which today holds only ruff and
  the test tools.
- **Modify** `.github/workflows/test.yml`: after the ruff step, run pyright on `src/jsk/graph/`
  in `basic` mode. Fix what it reports first; if a finding is a false positive, ignore it by line
  with a reason.
- **Update** the comment at `pyproject.toml:126`, which says nothing in CI runs pyright.
- Commit: `ci: pyright checks the graph package`.

## Phase 4 - reduction

### Task 11 - move migrate.py out (Ruling 11)

- Waits on your confirmation that no workspace still needs it.
- Tag the last release that ships `migrate.py`. Remove it, its CLI entry and `tests/test_migrate.py`
  / `tests/migrate_fixtures/`, and name the tag in the release notes and in `docs/SCRIPTS.md`.
- Commit: `refactor: migration leaves the package; <tag> is the last release that carries it`.

### Task 12 - one argument style, and the pack literal

- **Survey first.** List how each command in `cli.py` and `kbcli.py` parses its arguments today,
  and count the lines each spends on it. Write the survey into this plan before changing anything.
  Choose one style from the survey (`argparse`, which 4 files already use, is the likely one), and
  move one command group per commit, keeping `--help` output and exit codes the same. The
  existing `tests/test_cli.py` and `tests/test_graph_kbcli.py` are the check.
- **Survey (2026-09-28, done).** Four styles, not the two the Size table assumed:

  | Style | Where | Uses | Unknown flag |
  |---|---|---|---|
  | `cli.parse_flags(args, values, switches, repeats)` | `cli.py` | 4 | refused, named |
  | `kbcli.take(args, flag, value)`, popping by name | `kbcli.py` | 20 | not seen: caught only if the positional count is then wrong |
  | a hand `while args: args.pop(0)` loop | `timeline.main`, `letter.parse`, `record.parse` | 3 | refused, named, each in its own words |
  | `argparse` | `render/fit_pages.py` (an internal script) | 1 | argparse's own message and exit |

  **Choice: `parse_flags`, moved to `cliutil`, not argparse.** argparse would change every
  usage message and `--help` text the tests pin, and it exits by raising `SystemExit` with
  its own wording. `parse_flags` already refuses an unknown flag by name, which `take` does
  not. Move it to `cliutil`, then convert the three hand loops and then `kbcli`'s `take`
  calls, one command group per commit. That is probably 60–100 lines, not the Size table's
  guess. `fit_pages` stays on argparse: nobody types it.
- **Modify** `src/jsk/graph/pack.py:220`: `short_string(summary)` becomes `writer.literal`'s
  newline-aware form. Test in `tests/test_graph_pack.py`: a two-line summary round-trips through
  `trig()` and parses.
- Commits: `refactor: <group> parses arguments with argparse`, one per group, and
  `fix: pack's summary cannot write invalid Turtle`.

## Verification

1. Every new test fails before its fix and passes after it. Record the failing run's output in
   the commit message body.
2. Full `pytest` passes; `ruff check src tests` is clean with `B` and `BLE`; pyright is clean on
   `src/jsk/graph/` in CI.
3. The Task 1 allowlist holds only modules with a stated reason, and none of them reads authored
   text.
4. The migration replay in Task 6 matches the counts.
5. On a scratch copy of the real workspace:
   - `jsk posting build --replace` on a sent application refuses and leaves its files alone
     (Task 4);
   - `jsk freeze` on an application with a cover letter runs the letter gate (Task 3).
6. Run the `code-review` skill at `high` on each phase's commits before starting the next phase,
   and fold in anything it confirms.
7. Record the line count of `src/jsk` before Phase 1 and after Phase 4.
