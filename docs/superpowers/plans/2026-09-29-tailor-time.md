# Tailor time - implementation plan

**Spec:** none. This plan and its Rulings are the spec. The evidence is the two runs profiled
below. The scripts that measured them are in `docs/superpowers/experiments/2026-09-29-tailor-time/`.

**Supersedes** `2026-09-27-tailor-cost.md`. None of that plan was built, because the RocksDB record
came first. Its findings still hold. Its Rulings 3, 4, 5, 7, 8, 9, 10 and 13 are carried forward
unchanged and cited here as TC-3 and so on. Ruling TC-1's heading rule was not enough: Ruling 1
below replaces it. TC-11 and TC-12 are restated.

## Context

### The two runs (2026-09-29, `C:\Projects\basilin-joe-resume`)

| | Arrow (`.docx`) | Schneider (URL, Playwright) |
|---|---|---|
| Wall time | 11.9 min | 11.7 min |
| of which the person answering | 1.4 min | 3.0 min |
| Main-thread turns | 38 | 39 |
| Main-thread cache reads / output | 3.51 M / 21.4k | 3.17 M / 19.9k |
| Main-thread context, first turn → last | 47k → 126k | 48k → 117k |
| Analyst: minutes, turns, cache reads | 2.0, 15, 0.34 M | 2.1, 14, 0.31 M |
| Author: minutes, turns, cache reads | 2.0, 15, 0.65 M | 1.1, 8, 0.27 M |

**The cost model is TC's:** cost ≈ turns × context. A main-thread turn averages about 92k tokens
of cache read, so **every main-thread turn removed saves about 90k tokens and 5–10 s.** The main
thread is about 80% of the tokens.

### Where the time went

1. **The page budget. Arrow: 3 min, 13 turns.** The first ship was 3 pages against 2.
   - The main thread shipped again only to grep out the withheld bullet.
   - It then ran `jsk fit` three times. Between runs it cut three confirmed bullets and moved
     skills by hand in inline Python, then ran `mv`, `tectonic` and `jsk gates` itself.
   - The first fit had already reached 2 pages at 0.60in margins, which is inside the 0.5in floor.
     The model read `floors respected: margins 0.6in` as the floor, and cut evidence it did not
     need to cut.
2. **Headings are still unseen. Both runs.** Both `posting.md` files are well formed: one item per
   line, with headings on their own lines. `jsk posting extract` still classed every line `other`.
   Two things caused it:
   - `advert_lines` joins every run of plain lines into one paragraph;
   - "Key Responsibilities" is not recognised as a heading.

   As a result, all 20 requirements came out `implicit` in both runs. Each analyst set `required`
   with `sed`, rebuilt with `--replace` and ran `tailor prepare` a second time. `asked` had to be
   a substring of a 500–600 character paragraph, which caused two more refusals.
3. **`posting build` stops at the first refusal.** Schneider needed 6 builds and Arrow 3. The
   `--near` hint cut the term: `domain: enterprise software` became `--near terprise software`,
   because `postingbuild.py:219` strips `curie[2:]` from a value that has no `c:`.
4. **`concepts --near` takes one term.** The analyst ran it 21 times in a shell loop, which took
   15–25 s.
5. **The author reads every project.** It ran `kb show <16 projects> --bullets` before the export,
   in both runs. The output was 42 KB, which was persisted and then read whole: about 11k tokens,
   re-read on every later turn.
6. **The skills are not capped.** Arrow rendered with rows of 15–18 skills, where 10 render
   (`MAX_SKILLS_PER_ROW`). Schneider exported about 110 skills and the main thread trimmed them by
   hand in two turns.
7. **The main thread records the answers itself: 5–7 turns per run.**
   - Arrow read 14k characters of `kb show` to draft `round1.trig`.
   - Schneider grepped and then `sed`-read `kb-format.md` to learn the changeset shape.

   This is TC-10's finding again.
8. **The main thread types the advert.** Writing `posting.md` cost 2.5k output tokens and 20 s. The
   `.docx` was unzipped with inline Python. careers.se.com answers curl with Akamai "Access
   Denied", so JSON-LD fetch (TC-12) would not have helped it.
9. **The first turn is 47k before any work.** The skill listing is 25k characters and a
   SessionStart hook adds 7.7k, both from plugins the resume workspace does not use. This is the
   person's configuration, not jsk: see Out of scope.

## Rulings

Each ruling says what it costs if it is wrong.

1. **Headings and lines, as prototyped** (`heading_proto.py`, run on all 28 adverts). This replaces
   TC-1 and TC-2.
   - **A bare heading** is a line with no list marker, at most 6 words (counted as letter-initial
     tokens, so `&` and `:` do not count), and no `.`, `!`, `;` or `,` at the end. A closing `?` is
     allowed. The line must also either be in capitals and at least 2 words long, or match the
     heading vocabulary: `HEADING_ASKS`, `HEADING_DOES`, `HEADING_OFFERS`, `HEADING_NOT`,
     `about …`, `job description`, `overview` or `the role`.
   - **`HEADING_OFFERS` also takes** `what's in it for`, `rewards`, `why join`, `our values`,
     `our culture`, `about us` and `perks`.
   - **Under a qualification or responsibility heading, each line is its own item.** Lines are
     never joined there. A paragraph under an `offered` heading is skipped.
   - The replay counts (qual/resp/other):

     | Advert | Today | TC-1 alone | This ruling |
     |---|---|---|---|
     | Arrow | 0/0/8 | 2/3/2 | 14/24/2 |
     | Schneider | 1/0/22 | 3/1/2 | 24/10/2 |
     | Honeywell | 0/0/4 | 2/1/2 | 9/10/2 |

     No advert loses a qualification against TC-1. Optus's 11 lines under "What's in it for you?"
     are now skipped as benefits.
   - **Known miss:** Taskrabbit's tag list (`TypeScript`, `GraphQL`) reads as 5 qualifications.
     Each is a real ask.

   *If wrong:* a misread heading reclassifies the lines under it, and the replay shows which. The
   per-line rule is one branch.
2. **`posting build` reports every problem in one pass.** This is TC-6 as written, plus two
   changes:
   - the `--near` hint quotes the value as written, and a header `domain:` that is not a curie
     is refused as "not a concept (write `c:…` or leave it blank)";
   - `jsk kb query concepts --near` takes several terms, printing one table per term from one
     store load.

   *If wrong:* a flag.
3. **`jsk ship` fits the page budget itself.** This replaces TC-11 and adds to it.
   - When the render is over budget, `ship` runs `fit_pages.py`'s levers in order, stopping at
     the floors (10pt, 0.5in). It then recompiles and runs every gate on the fitted render, and
     prints the levers it applied.
   - **The floors are the only limit.** 0.6in margins are a fit, not a compromise.
   - When the floors are reached and the render is still over, `ship` prints how many lines are
     over, and nothing is cut. Cutting evidence is the author's call, with a reason.
   - `fit_pages.py` prints `margins 0.6in (floor 0.5in)`.
   - The ship summary names each withheld id.
   - `--no-fit` keeps today's behaviour.

   *If wrong:* the person wants wider margins, and that is a template floor, not a cut.
4. **The export does the author's survey.**
   - `jsk kb export --from-match` caps each skills row at `MAX_SKILLS_PER_ROW`, the posting's asks
     first. The overflow is still a WARN naming the row.
   - After `wrote`, the export prints each chosen bullet as `id | first 100 characters`.
   - The author exports first, then runs `kb show --bullets` only for the projects whose bullets
     it will reword or write. This replaces TC's Task 9 (`kb show --brief`).
   - When the author re-exports, it overwrites its own `resume.json` with `--replace`.

   *If wrong:* the author needs a project the export did not choose, and one `kb show` covers it.
5. **`jsk posting fetch` also takes a local file:** `.docx` (stdlib `zipfile`, one paragraph per
   `w:p`, list paragraphs as `- `), `.html` (through `html_to_text`) or `.txt`. It writes the
   same `posting.md`, which the main thread no longer types. No new verb: the argument is a path.
   For a portal only a browser can open, the main thread saves the page's HTML to a file and
   fetches that. Task 5 establishes whether the Playwright tools can write a file without the page
   passing through the context. If they cannot, the browser path stays as it is.
   *If wrong:* the model writes `posting.md` as today.
6. **Carried forward unchanged:** TC-3 (only qualification lines need a row), TC-4 (old postings
   warn more), TC-5 (no drops in the gaps files), TC-7 (`kb apply` takes `.ttl`, and `--quiet`),
   TC-8 (the brief), TC-9 (`effort: medium`, `omitClaudeMd`), TC-10 (the author takes the round
   after the answers) and TC-13 (model changes gated by evals).
7. **Out of scope:**
   - the person's answer time;
   - `/compact` inside a run;
   - a `jsk tailor triage` command, which would save about 2 turns and is not worth a verb;
   - the person's plugin set. For the resume workspace, the person can disable the plugins it does
     not use (engineering, anthropic-skills, the SessionStart hook) in
     `C:\Projects\basilin-joe-resume\.claude\settings.json`. That is about 8–10k tokens a turn, or
     about 350k a run. This plan recommends it and does not do it.

## Global constraints

- These are TC's, unchanged: no new top-level verb (`tests/test_plugin_surface.py`); budgets
  re-measured on every prompt change; replays only on a scratch copy of the real workspace; commit
  only the files a task names; never commit while a subagent works; `python -m pytest tests -q -n
  auto`, `python -m ruff check src tests`, and `pyright` on changed modules.
- **Code in this plan has been run.** Anything added to it must be run before it is committed
  (memory: plan code is unverified). Write any file with a backslash in it using the Write tool,
  never a heredoc: a heredoc turned `\b` into a backspace while this plan's prototype was being
  written.
- Paths have moved since TC:
  - `ship` is `cmd_ship` in `src/jsk/cli.py`;
  - the fitter is `src/jsk/render/fit_pages.py`;
  - the skills cap is `src/jsk/resume/build.py:56`;
  - the export is `src/jsk/graph/export.py`;
  - `--near` is at `src/jsk/graph/kbcli.py:973`.

## Build order

- **Phase 1**, Tasks 0–5, are independent code changes. Tasks 1, 2, 3 and 4 touch different
  modules and can run as parallel subagents once Task 0 is in. Base each worktree on this branch's
  HEAD, not `origin/main` (memory).
- **Phase 2**, Tasks 6–8, are prose and configuration. They wait for the Phase 1 replay, because
  they move the prompt budgets.
- **Phase 3** is TC's Tasks 10–12 (JSON-LD fetch, `posting extract --draft`, model evals), decided
  on Phase 2's numbers.

Expected savings, from the two runs:

| Task | Runs it would have saved | Per run |
|---|---|---|
| 3 ship fits | Arrow | ~13 main turns, ~3 min, ~1.1 M tokens |
| 1 headings | both | 2 analyst turns + a second prepare, ~20 s |
| 2 build, `--near` | both | 3–6 analyst turns, 20–40 s |
| 4 export | both | ~11k-token read, ~2 main turns (Schneider) |
| 5 fetch a file | Arrow | ~2.5k output tokens, ~30 s |
| 7 (TC-10) author takes the round | both | 5–7 main turns, ~0.5 M tokens |

---

### Task 0 - the profiler and the prototype, kept

- These files are already in `docs/superpowers/experiments/2026-09-29-tailor-time/`:
  - `session_profile.py`: per-turn timings, the tool-result sizes and token totals for a session
    and its subagents;
  - `heading_proto.py`: Ruling 1 against today's parser, over every `posting.md`.
- Make both take their paths from argv instead of the hard-coded ones. Add a `README.md` with the
  baseline table above and the command for each script.
- Commit: `docs: the session profiler and heading prototype behind the tailor-time plan`.

### Task 1 - headings and lines (Ruling 1, TC-3, TC-4)

- **Modify** `src/jsk/graph/rules.py`:
  - add `bare_heading`, `OFFERS_MORE` and the `TERMINAL` rule exactly as in `heading_proto.py`,
    and use `bare_heading` in `_heading`;
  - add the offered, section and `other` branches to `advert_lines`, with no joining under a
    qualification or responsibility heading;
  - update the docstring.
- **Modify** `src/jsk/graph/postingbuild.py` for TC-3: only qualification lines need a row. The
  `extract` header says `other and responsibility lines need no row`. With no `# ` title line,
  take the first line that is not the URL as the title.
- **Tests** go in `tests/test_advert_lines.py`:
  - every case in the prototype's heading table: the headings `HOW WE WORK`, `Key
    Responsibilities`, `What's in it for me?`, `Experiences & Exposure : Nice to have` and `Job
    description`; and the non-headings `AWS`, `Position Overview`, `Technical Expertise` and `Big
    picture thinking.`;
  - one-per-line items under a heading staying separate;
  - a benefits paragraph being skipped.

  Update the `AdvertCoverage` and `test_posting_build.py` expectations that move, with a comment
  naming this plan.
- **Replay:** run `jsk posting extract` over all 28 adverts on the scratch copy. The counts must
  equal the prototype's. Record Arrow, Schneider and Honeywell in the commit message.
- Commit: `fix: bare headings, and one item per line under a section`.

### Task 2 - `posting build` reports everything; `--near` takes several terms (Ruling 2)

- **Modify** `src/jsk/graph/postingbuild.py` `build`: collect the refusals and raise one `Refused`
  holding all of them, each with its line and `fix:`. A `decisions.py` parse error stays single.
  Refuse a header `domain:` without `c:` in words, and quote the value as written in the `--near`
  hint.
- **Modify** `src/jsk/posting.py` to print every problem.
- **Modify** `src/jsk/graph/kbcli.py` `concepts --near`: take one or more terms, with one table per
  term, headed `== <term>`.
- **Modify** `plugins/jsk/agents/jsk-tailor-analyst.md` §1: one `--near` call with every term.
- **Tests:**
  - Schneider's refusals in one run (a bad seniority, `domain: enterprise software`, and an
    `asked` that is not verbatim) give three problems, and the hint names `enterprise software`
    whole;
  - `--near a b` prints two tables.
- Commit: `fix: posting build names every problem at once; concepts --near takes several terms`.

### Task 3 - `ship` fits itself (Ruling 3)

- **Read** `fit_pages.py` and `cmd_ship` first. Write down in the task what each lever changes,
  and that the fitter is deterministic and writes only `-fitted.tex`. If it is not safe to run
  unattended, stop and bring it back as a question.
- **Modify** `cmd_ship`. When the render is over budget and `--no-fit` is not given:
  - fit;
  - move the fitted `.tex` over the original;
  - recompile with the same engine;
  - run every gate on the result;
  - print `fit: <levers>, <n> pages`.

  If the floors are reached and the render is still over, print `over by ~<n> lines at the
  floors`, keep the unfitted render, and leave the page gate's verdict as today.
- **Modify** the ship summary line `withheld N below the floor` to name each id.
- **Modify** `fit_pages.py`'s last lines to print each value with its floor.
- **Modify** `references/mode-ship.md` §3: `ship` fits itself. Cut evidence only on `over by … at
  the floors`, with a reason.
- **Tests:**
  - a 3-page fixture with a 2-page budget comes back at 2 pages, having printed its levers;
  - `--no-fit` keeps 3 pages;
  - a fixture that cannot fit prints the line count and changes nothing;
  - the withheld ids are named.
- Commit: `feat: jsk ship fits the page budget itself`.

### Task 4 - the export does the survey (Ruling 4)

- **Modify** `src/jsk/graph/export.py`:
  - cap each skills row at `MAX_SKILLS_PER_ROW` (import it from `resume/build.py`), with the
    posting's asks first;
  - print `id | text[:100]` for each chosen bullet;
  - let `--replace` overwrite an existing `--out`.
- **Modify** `plugins/jsk/agents/jsk-resume-author.md` "Read what the posting selects": export
  first, then `kb show --bullets` only for the projects it will reword or write.
- **Tests:**
  - a fixture career with 15 skills in one row exports 10, the asked ones first;
  - the bullet lines print;
  - `--replace` overwrites and the default refuses.

  Re-measure the author budget.
- Commit: `feat: export caps the skills, lists what it chose, and the author surveys from it`.

### Task 5 - `posting fetch` takes a file (Ruling 5)

- **Modify** `src/jsk/posting.py` `fetch`: a path that exists is read locally. `.docx` goes through
  `zipfile` and `word/document.xml`: one line per `w:p`, `- ` for `w:numPr` paragraphs, `## ` for
  `Heading*` styles. `.html` goes through `html_to_text`, and `.txt` is taken as it is. The first
  line is `Source: <file name>`.
- **Check** whether `mcp__plugin_playwright_playwright__browser_run_code_unsafe` can write
  `page.content()` to a path. Record the answer in `mode-tailor.md` §1: save, then fetch the file,
  or keep today's copy.
- **Modify** `references/mode-tailor.md` §1: a file argument goes to `jsk posting fetch <file>
  <app-dir>`, never through the context.
- **Tests:** a fixture `.docx` built in the test with `zipfile`, holding a heading style, a
  numbered paragraph and a plain paragraph; and an `.html` file with `<h2>` and `<li>`. Run
  `extract` on each result and check the sections.
- Commit: `feat: posting fetch reads a .docx, .html or .txt file`.

**Phase 1 replay.** On the scratch copy, replay Arrow and Schneider end to end from their original
inputs, with a scripted person giving the same answers. Profile each with `session_profile.py`,
and write the table into this plan before Phase 2.

---

### Task 6 - TC Task 1: agent configuration (TC-9)

This is TC's Task 1 as written. Record the first-turn context of each agent before and after.

### Task 7 - TC Task 7: the author takes the round after the answers (TC-10)

This is TC's Task 7 as written. The evidence is here: Arrow's `round1.trig` and Schneider's
`kb-format.md` reads. With it, the main thread's steps after the answers become: dispatch the
author, ask its clauses, send the confirmations, show the ship summary.

### Task 8 - TC Tasks 4, 5 and 6: gaps drops, `kb apply .ttl --quiet`, the brief (TC-5, TC-7, TC-8)

These are TC's tasks as written. Here `gaps.md` was 7.5k–8.5k characters, not TC's 20k, so
measure the brief's saving before keeping the `mode-tailor.md` change.

**Phase 2 replay,** as for Phase 1. The target is at most 20 main-thread turns and at most 1.2 M
main-thread cache reads per run, on the same two postings.

## Verification

1. After each task: the suite, ruff, pyright and the budgets are green.
2. **Corpus replay:** `jsk posting extract` over all 28 adverts gives the prototype's counts. No
   advert loses a qualification against today without a line in the commit saying why.
3. **Measured:** the Phase 1 and Phase 2 replays against the baseline table, as turns, cache
   reads, output and machine minutes per part.
4. **One live `/jsk:tailor`** on a fresh posting after Phase 2, profiled from its transcript.
