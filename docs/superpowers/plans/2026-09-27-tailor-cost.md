# Tailor cost - implementation plan

**Spec:** none. This plan and its Rulings are the spec. The evidence is the profile below,
measured on the real workspace's transcripts; the scripts that measured it are Task 0.

## Context

A tailoring run costs 1–3 M weighted tokens and 17–30 minutes of machine time, on top of however
long the person takes to answer. The Autodesk run (2026-09-27) took 140 minutes wall time, of which
124 were `AskUserQuestion` waiting on the person; its 17 machine minutes still cost 33k output
tokens and 8.0 M cache-read tokens.

**The cost model.** A turn re-reads the whole context, so cost ≈ turns × context. A large tool
result costs again on every later turn, and a retry costs a whole turn.

**Where it goes.** These are the six graph-era runs since 2026-09-25, weighted as input 1, cache
write 1.25, cache read 0.1, output 5. The weighting prices Opus and Sonnet the same, so the main
thread's real share is larger.

| Part | Share | Model | Turns per run | What drives it |
|---|---|---|---|---|
| Main thread | 49% | Opus | ~46 | context 28k → 150k; ~40 of 46 turns come after the person's answers |
| Resume author | 30% | Sonnet | 36 | `kb apply` 4.4 times per run (~5k characters each), `resume.json` re-read 3.2 times, `kb show` / `kb view` |
| Analyst | 21% | Sonnet | 28 | `kb query` ×7, `kb show`, `gaps.md` read twice |

**What each run pays for, and should not:**

- **Headings go unseen.** In both runs that used the `decisions.txt` flow, all 98 advert lines were
  classified `other`, with no qualifications, no responsibilities, and a blank company and title.
  Stickermule came through `jsk posting fetch` (Ashby's `descriptionPlain`, headings in capitals).
  Autodesk was a browser copy (bare headings, one paragraph per item). Everything downstream then
  paid for it:
  - the analyst set every `need` by hand;
  - it wrote **55 drop rows** for headers, the job ID, boilerplate and salary text, none of which
    needed a row;
  - it spent 93 s + 40 s of hidden thinking before writing `decisions.txt`.
- **The gaps files are bloated.** The `gaps.txt` draft copies every drop in as a comment: 7.8k of
  its 13k characters. `gaps.md`'s New terms listed 54 dropped lines as "new terms".
- **Commands stop at the first error, and output is too long.**
  - `posting build` stops at the first error, so six errors meant six rebuilds at ~43k context
    each. Its fix hint also cut a term (`--near entic-ai-platform`).
  - `kb apply` refuses a `.ttl` changeset outright ("not a .trig file"), which cost a retry.
  - `ship` rendered four times at 3 pages against 2, with 12 skills-row overflow warnings, and
    `resume.json` was hand-edited with Python between renders.
- **The main thread carries what it could point at.** Every run `cat`s `gaps.md` (~20k
  characters) and `kb show`s 5–7 whole projects (up to 27k). All of it is re-read on every later
  turn.
- **Agents think without saying anything.** Agent turns of 40–154 s produced 2–3 visible output
  tokens.

**What Claude Code offers** (the docs, via the claude-code-guide agent). A plugin agent's
frontmatter takes `effort` (`low`…`max`), `model` (`haiku`/`sonnet`/`opus`/…), `omitClaudeMd`
and `experimental.cacheTtl`. A skill can run in a forked subagent (`context: fork`) and can set
`model` and `effort`. Extended thinking cannot be switched off for one agent; `effort` is the
lever. These are the docs' claims, not yet tried here: Task 1 records whether each one takes
effect.

## Rulings

Each ruling says what it costs if it turns out wrong.

1. **A bare heading is a heading.** `_heading` also accepts a line with no list marker, of at most
   6 words and no sentence ending (`[.!?;,]\Z`), when either:
   - it is in capitals and at least 2 words long (`HOW WE WORK`, but not `AWS`), or
   - it matches the heading vocabulary: `HEADING_ASKS`, `HEADING_DOES`, `HEADING_OFFERS`,
     `HEADING_NOT`, or `about …`.

   Prototyped on all 26 real adverts (the code is under Global constraints):
   - `Position Overview` and `The Ideal Candidate` stay prose.
   - **`asked_lines` changes, deliberately.** 16 adverts that showed no qualifications now do.

   *If wrong:* a misread heading reclassifies the lines under it. The fixtures and the corpus
   replay (Verification step 2) show which.
2. **A paragraph under a section heading is one of its items.** Under a qualification or
   responsibility heading, a prose paragraph is recorded in that section, not as `other`. Under an
   `offered` heading it is skipped, as a list item there is. Autodesk goes from 73 `other` lines to
   12 (31 qualifications, 21 responsibilities). *If wrong:* the old behaviour is one branch.
3. **Only qualification lines must be used or dropped.** This amends fast-tailor Ruling 5.
   Responsibility lines may go unmentioned: they default to `implicit`, which the match does not
   assess, so a drop row for one buys nothing. `other` lines never need a row, and `extract`'s
   header now says so. *If wrong:* a responsibility the analyst skipped is never quoted, which is
   what an implicit requirement already was.
4. **Old postings warn more, and that is correct.** More lines now read as qualifications, so
   `advert-uncovered` WARNs on some legacy `posting.ttl` files. Sent applications are frozen and
   are not rebuilt. *If wrong:* restrict the rule to postings built by `jsk posting build`, which
   is one check.
5. **Drops are for the analyst, not the person.**
   - The `gaps.txt` draft stops copying drops in.
   - `gaps.md`'s New terms lists `candidate` requirements plus drops of qualification lines only.
   - Drops stay in `decisions.txt`, where they already are.
   *If wrong:* a drop the person should see is one comment away.
6. **`posting build` reports every problem in one pass.** It collects every refusal it can find
   without the earlier ones fixed, prints each with its line, and exits 1 if any. A parse error in
   `decisions.txt` stays one message, because later lines cannot be trusted after it. The `--near`
   hint quotes the term as written.
7. **`kb apply` takes a `.ttl` changeset.** The extension check accepts `.trig` or `.ttl`, since the
   content is what gets parsed. `--quiet` prints the revision and the minted and touched ids
   without the diff. *If wrong:* one line.
8. **The main thread reads a brief, not `gaps.md`.**
   - `jsk tailor prepare` and `jsk match --gaps` end with a `== brief` section: fit, eligibility,
     blocking, the required rows that fall short, and the questions in asking order with the ids
     they close. It is capped at 2,500 characters.
   - `mode-tailor.md` has the main thread show the brief and link `gaps.md`, instead of showing
     `gaps.md` whole. That replaces the rule "show them the assessment whole".

   *If wrong:* the person wants it in chat. They can open the file, or the main thread reads it.
9. **`effort: medium` on the analyst and the author; `omitClaudeMd: true` on every plugin agent.**
   None of them needs the person's global CLAUDE.md. *If wrong:* a field the running version does
   not know is ignored, and Task 1 checks that it takes effect before counting it as a saving.
10. **The author takes over the round after the answers** (Phase 2). The main thread asks the
    questions and passes the answers **verbatim** to `jsk-resume-author`, which then:
    - writes the answers into the career (one changeset, then `kb confirm --answer "<their
      words>"`);
    - re-runs `--gaps`;
    - authors the resume;
    - returns the authored clauses to confirm.

    The main thread asks those. A `SendMessage` to the same agent then confirms them and ships.
    It is not a new agent: that would be new surface, and the author already holds the context. A
    subagent cannot ask the person, so it is never told to confirm anything the answers do not
    say. *If wrong:* the author prompt grows by about 400 tokens and its budget moves, measured.
11. **`jsk ship` fits the page budget itself** (Phase 2). When the render is over the budget,
    `ship` runs the existing fitter (`fit_pages.py`) and gates the fitted render, and it prints
    what it cut. The first step of the task is to read `fit_pages.py` and confirm it is safe to
    run unattended. The skills-row overflow becomes a WARN naming the row, and the author orders
    `skills` for this posting. *If wrong:* `--no-fit` restores today's behaviour.
12. **Structured adverts come first** (Phase 3). `jsk posting fetch` falls back, for any URL, to
    the page's schema.org `JobPosting` JSON-LD (title, hiring organisation, description HTML).
    Where the provider gives HTML, it prefers it to plain text and writes `<h1>`–`<h6>` and
    whole-paragraph `<strong>` as `## ` headings. *If wrong:* the browser path stays as the last
    resort.
13. **A model change is gated by evals.** `model: haiku` for the analyst, or `model: sonnet` in the
    skill's own frontmatter, ships only if a `claude plugin eval` suite built from the corpus runs
    no worse than today. Otherwise it waits. *If wrong:* it is one frontmatter line either way.
14. **Out of scope:** the person's own answer time, and `/compact` inside a run, which loses the
    ids the later steps need.

## Global constraints

- No new top-level verb. `tests/test_plugin_surface.py` pins the surface. The brief is a section
  of existing output, and `--quiet` and `--no-fit` are flags.
- Every prompt-file change re-measures `tests/test_budget.py`, and a ceiling moves only with a
  measured comment.
- Run every regex before trusting it (memory: plan code is unverified). The heading rule below
  was executed on all 26 real adverts before planning.
- Replay changes on a scratch copy of `C:\Projects\basilin-joe-resume\career`, never the live one.
  Delete `application.ttl` in the copy to exercise writes, since most of its applications are sent.
- Commit only the files a task names. Never commit while a subagent is working.
- Tests are unittest style: `python -m pytest tests -q -n auto`, `python -m ruff check src tests`,
  and `pyright` on each changed module.
- The heading rule as prototyped (`heading_proto2.py`). It replaces the `else` branch of
  `advert_lines`' paragraph handling and extends `_heading`:

  ```python
  TERMINAL = re.compile(r"[.!?;,]\Z")

  def bare_heading(text):
      words = text.split()
      if not words or len(words) > 6 or TERMINAL.search(text):
          return False
      letters = re.sub(r"[^A-Za-z]", "", text)
      if len(words) >= 2 and len(letters) >= 3 and letters.isupper():
          return True
      return bool(HEADING_ASKS.search(text) or HEADING_DOES.search(text)
                  or HEADING_OFFERS.search(text) or HEADING_NOT.search(text)
                  or re.match(r"(?i)about\b", text))

  # in advert_lines, where a paragraph is recorded:
          elif section == "offered":
              continue
          elif section in ("qualification", "responsibility"):
              found.append([section, squash(text), opt_heading, False])
              prose = True
          else:
              found.append(["other", squash(text), False, False])
              prose = True
  ```

  Results: `HOW WE WORK`, `Responsibilities`, `Minimum Qualifications` and `About Autodesk` are
  headings. `AWS`, `Kubernetes and Docker`, `Position Overview` and `Use AI aggressively.` are not.

## Build order

- **Task 0** lands first, so that every later change is measured.
- **Phase 1** (Tasks 1–6) is small and independent. Tasks 2, 3, 4 and 5 touch different modules
  and can run as parallel subagents after Task 2's interface is fixed; Task 1 and Task 6 are prose
  and configuration.
- **Phase 2** (Tasks 7–9) waits for Phase 1's measurement.
- **Phase 3** (Tasks 10–12) is decided on Phase 2's numbers.

---

### Task 0 - the profiler, kept

- **Create** `docs/superpowers/experiments/2026-09-27-tailor-cost/`, holding the session
  scratchpad's `run_profile.py`, `turns.py`, `results.py` and `corpus_profile.py`. They are
  generic: every path comes from argv. Add a `README.md` giving the weighting, the command for one
  session and for a whole project, and the six-run baseline table above.
- Commit: `docs: the transcript profiler behind the tailor-cost plan`.

### Task 1 - agent configuration (Ruling 9)

- **Modify** the frontmatter of `plugins/jsk/agents/jsk-tailor-analyst.md` and
  `jsk-resume-author.md`: add `effort: medium`. On all five agents, add `omitClaudeMd: true`.
- **Check** that `tests/test_plugin_surface.py` and `claude plugin details jsk` accept the fields.
- **Verify it took effect:** after reinstalling the plugin (uninstall, then install; the version is
  unchanged), dispatch the analyst once on a scratch application and confirm with Task 0's
  profiler:
  - that its first-turn context no longer includes CLAUDE.md (base context below ~13.8k);
  - that its hidden-thinking gaps shrink.

  Record both numbers in the commit message. If `effort` shows no effect, say so and keep it
  anyway: it costs nothing.
- Commit: `chore: the plugin agents think at medium effort and skip the person's CLAUDE.md`.

### Task 2 - headings (Rulings 1–4)

- **Modify** `src/jsk/graph/rules.py`: `_heading` gains `bare_heading`, and `advert_lines` gains
  the section-paragraph branch, both as in Global constraints. Update the `advert_lines` docstring.
- **Modify** `src/jsk/graph/postingbuild.py`: only `qualification` lines must be used or dropped
  (Ruling 3). The refusal names them; `extract`'s header line says `other and responsibility lines
  need no row`.
- **Modify** `src/jsk/graph/postingbuild.py` `advert_header`: with no `# ` title line, take the
  first non-URL line as the title, and leave company blank. That lands in the header `extract`
  prints, for the analyst to correct.
- **Tests:** `tests/test_advert_lines.py`:
  - a capitals heading; a bare `Responsibilities`;
  - paragraphs under `Minimum Qualifications` as qualifications, under `Benefits` skipped;
  - `AWS` and `Position Overview` staying prose.

  Update the `AdvertCoverage` tests whose expectations move (Ruling 4), with a comment naming this
  plan. Update `tests/test_posting_build.py` for Ruling 3.
- **Replay:** on the scratch corpus, run `jsk posting extract` on Autodesk and Stickermule and
  record the section counts in the commit. The expected counts are the prototype's.
- Commit: `fix: bare headings and paragraph items - an advert's sections without its markup`.

### Task 3 - `posting build` reports everything (Ruling 6)

- **Modify** `src/jsk/graph/postingbuild.py` `build`: collect the refusals into a list instead of
  raising at the first. `Refused` carries all of them: its message is the count, and each problem
  is followed by its own `fix:` line. The `decisions.py` parse error stays a single refusal. Fix
  the `--near` hint so it quotes the term as written.
- **Modify** `src/jsk/posting.py` to print every problem.
- **Tests:** a `decisions.txt` with a bad seniority, a non-concept domain and a non-verbatim
  `asked` gives three problems in one run. The `--near` hint names the whole term.
- Commit: `fix: posting build names every problem at once`.

### Task 4 - the gaps bloat (Ruling 5)

- **Modify** `src/jsk/graph/gapsdraft.py`: the draft drops its `dropped()` comment lines.
- **Modify** `src/jsk/graph/gapsbuild.py` `new_terms`: drops are shown only for lines `advert_lines`
  classes as `qualification`.
- **Tests:** update `tests/test_gaps_draft.py` (no drop comments) and `tests/test_gaps_build.py`
  (a boilerplate drop is not a new term; a qualification drop is).
- Commit: `fix: the gaps files carry no drops the person does not need`.

### Task 5 - `kb apply` takes `.ttl` and can be quiet (Ruling 7)

- **Modify** `src/jsk/graph/kbcli.py` `cmd_apply` (around line 231): accept `.trig` or `.ttl`, and
  add `--quiet`.
- **Tests:** a `.ttl` changeset applies. `--quiet` prints the revision and the ids, no diff.
- **Modify** `plugins/jsk/agents/jsk-resume-author.md`: apply with `--quiet` once the dry run has
  been read.
- Commit: `feat: kb apply takes a .ttl changeset, and --quiet`.

### Task 6 - the brief (Ruling 8)

- **Create** `brief(r, assessment)` in `src/jsk/graph/gapsbuild.py`, returning at most 2,500
  characters: fit, eligibility, blocking, the required rows short of `satisfied` with their
  shortfalls, and the questions numbered with the ids they close.
- **Modify** `src/jsk/graph/prepare.py` and `src/jsk/graph/match.py` (`show_build`) to print it
  after a successful build.
- **Modify** `plugins/jsk/skills/jsk/references/mode-tailor.md` §2: "show the brief and link
  `gaps.md`" replaces "show them the assessment whole". The analyst's return lines are unchanged.
- **Tests:** the brief is under the cap on the largest fixture, and holds the fit and every
  question id. Re-measure the budgets.
- Commit: `feat: a brief of the assessment, so the conversation carries 2k, not 20k`.

**Phase 1 measurement.** Replay the Autodesk posting end to end on the scratch corpus with a
scripted person (the same answers), and profile it with Task 0. Compare each part's weighted cost,
turns and machine minutes with the baseline table, and write the result into this plan before
Phase 2 starts.

---

### Task 7 - the author takes the round after the answers (Ruling 10)

- **Modify** `plugins/jsk/agents/jsk-resume-author.md`: add a first section, "The answers". It
  receives the person's answers verbatim with the question ids. It writes one changeset, then runs
  `kb confirm --answer` with their words, then `--gaps`, and **confirms only what an answer says**.
  After that the existing procedure runs. The return adds the clauses to confirm. On a
  `SendMessage` naming the confirmations, it runs `kb confirm`, then `jsk ship`, and returns the
  ship summary.
- **Modify** `mode-tailor.md` §3–§5: collect every answer, dispatch the author once, ask the
  author's clauses, then `SendMessage` the confirmations. Remove the main thread's changeset,
  confirm and ship steps.
- **Tests:** in `tests/test_budget.py`, the author ceiling (measured) and the main-thread ceiling,
  which should fall. In `tests/test_plugin_surface.py`, the sentence "confirms only what an answer
  says".
- Commit: `feat: the author applies the answers and ships; the conversation only asks`.

### Task 8 - `ship` fits itself (Ruling 11)

- **Read** `src/jsk/urs/fit_pages.py` and `cmd_ship` first, and write down in the task what the
  fitter changes and whether it is deterministic. If it is not safe to run unattended, stop and
  bring it back as a question.
- **Modify** `cmd_ship`: when over budget and without `--no-fit`, fit, re-render and gate the
  fitted document, and print what was cut. The skills-row overflow WARN names the row and the
  skills that fell off.
- **Tests:** a 3-page render with a 2-page budget comes back at 2 pages, having printed its cuts.
  `--no-fit` keeps 3.
- Commit: `feat: jsk ship fits the page budget itself`.

### Task 9 - `kb show --brief`

- **Modify** `jsk kb show` so `--brief` prints each project's name, its bullets' ids and first 80
  characters, and its metrics' current values.
- **Modify** `mode-tailor.md` and the author to use `--brief` for surveys, and the full show only
  for what they cite or rewrite.
- **Tests:** the brief of five fixture projects is under a third of the full show.
- Commit: `feat: kb show --brief`.

**Phase 2 measurement,** as for Phase 1. The target is main-thread Opus cache reads down by at
least 70% against the baseline.

---

### Task 10 - JSON-LD fetch (Ruling 12)

- **Modify** `src/jsk/posting.py`: when the URL matches no provider, fetch the page and read its
  `<script type="application/ld+json">` `JobPosting` (title, `hiringOrganization.name`,
  `description`). It is written through `posting_md`, with headings as `## `. Where the provider
  gives HTML, prefer it to plain text, and write `<h1>`–`<h6>` as headings.
- **Tests:** saved JSON-LD pages from Workday and SmartRecruiters (fixtures, no network), and an
  Ashby description with headings.
- Commit: `feat: posting fetch reads any page's JobPosting`.

### Task 11 - code drafts decisions.txt

- **Modify** `jsk posting extract` so `--draft` writes `decisions.txt`:
  - one row per qualification line that `labels_in` proposes concepts for, with the concepts
    proposed and a slug from the first label;
  - a `- | <reason>` slot for each other qualification line;
  - the header, filled.

  The analyst corrects it instead of writing it. Baseline: proposals exactly match the analyst on
  8 of 23 lines. Re-measure after Task 2 on the scratch corpus, and ship only if at least half the
  rows survive the analyst's corrections unchanged.
- Commit: `feat: posting extract --draft - the analyst corrects decisions.txt, it does not write it`.

### Task 12 - model trials behind evals (Ruling 13)

- **Create** a `claude plugin eval` suite from three replayed corpus postings. It grades that
  `decisions.txt` builds, that verdicts are lowered never raised, and that every question names an
  id.
- **Run** it with the analyst on `haiku`, then with the skill's frontmatter on `model: sonnet`.
  Adopt each only if it runs no worse than today.
- Commit: per trial adopted, with the eval result in the message.

## Verification

1. After each phase, the suite, ruff, pyright and the budgets are green.
2. **Corpus replay:** extract and build over all 26 adverts on the scratch copy. Record the section
   counts and the `advert-uncovered` WARNs before and after Task 2, and check no heading is
   misread.
3. **Measured against the baseline:** after each phase, one scripted Autodesk replay profiled with
   Task 0, reported as weighted cost per part, turns, and machine minutes.
4. **One live `/jsk:tailor`** on a fresh posting after Phase 2, timed from the transcript.
