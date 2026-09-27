# Fast tailor — implementation plan

**Spec:** `docs/superpowers/specs/2026-09-26-fast-tailor-design.md` (§7 steps 1–5; step 6 "measure, then
decide E/F/K" is out of scope).
**On approval:** copy this plan to `docs/superpowers/plans/2026-09-27-fast-tailor.md` and work from there.

## Context

The JumpCloud tailoring run took ~11 minutes of machine time to reach its first question, and the
answer was "Stop here". Almost all of that time was output tokens: 26.5k to hand-write `posting.ttl`
(41 over-split requirements) and 11.8k to rewrite `gaps.md`, most of which transcribes what
`jsk match` already printed. Tool calls cost 1–3 s each. The fix follows one principle: **the model
decides, code writes.** The target is under 5 minutes end to end, and 35 s on a posting that fails
triage.

## Rulings (the spec's open questions, plus calls it leaves implicit)

Each ruling says what it costs if it turns out wrong.

1. **Decisions file: `|`-separated, not whitespace columns.** `asked` can be several words ("primary
   technical anchor"), so whitespace columns cannot parse it. JSON lines cost about 2× the tokens.
   A row is `n | slug | asked | concepts | need`: concepts are comma-separated or `-`, and `need` may
   be left blank to take the default. A drop is `n | - | <reason>`. Lines starting with `#` are
   comments. The file is `applications/<stem>/decisions.txt`. *If wrong:* a parser swap inside
   `build`; nothing else reads the file except the drop list in the gaps draft.
2. **A responsibility line defaults to `implicit`.** Promoting it to `required` WARNs unless the
   line has `REQUIRED_WORDS`. It is not refused. *If wrong:* making it a refusal is one line.
3. **The soft cap is 20 and fixed.** *If wrong:* one constant.
4. **`prepare` is a command** (`jsk tailor prepare`), because one turn instead of ten is the point.
   *If wrong:* a new top-level subcommand to maintain; the docs-surface tests pin it.
5. **Not every line has to appear in the decisions file.** Qualification and responsibility lines
   must be used or dropped with a reason. `other` lines (prose, text before the first heading) and
   `elig`-flagged lines may go unmentioned, otherwise every paragraph would need a drop row. List
   items under a benefits, perks or compensation heading are not extracted at all.
6. **Default `need` for a qualification line:** `preferred` when its heading or the line itself is
   optional-worded (nice to have, bonus, preferred, desirable, a plus), otherwise `required`. An
   `other` line defaults to `implicit`.
7. **`build` never overwrites `posting.ttl` without `--replace`.** The analyst passes `--replace`
   when it rebuilds after the match, for example to add a `j:concept` to an ambiguous term. A
   hand-reviewed legacy posting.ttl therefore cannot be clobbered by accident.
8. **Drop reasons reach the person** through `gaps.md`'s `# New terms`, filled in by the draft from
   `decisions.txt`, e.g. `- **Origin CI, Kargo, WoK** — dropped: internal tooling`. They never go in
   posting.ttl.
9. **Implicit rows are drafted as `indeterminate`**, with the Shortfall "implicit — the match does
   not assess it". `check_gaps` accepts any verdict when the default is None. *If wrong:* the
   person sees one extra word per implicit row.
10. **Label-in-line proposals (§1B) match whole labels as contiguous words.** A label of two
    characters or fewer ("Go", "R") matches case-sensitively as written, so "go" in prose never
    proposes c:golang. A label that sits inside a longer matched label is suppressed ("Azure" inside
    "Azure DevOps"). Retired concepts are never proposed. *If wrong:* noisier proposals, which the
    model removes; the match's `candidate` bucket is still the safety net.
11. **The seniority hint** is a small title-word table: principal/staff/architect →
    architecture-ownership, lead/manager → team-leadership, senior → hands-on-senior,
    junior/graduate → junior, otherwise none. It is printed as a hint only.
12. **§3H (parallel calls) and §3I (background dispatch while asking)** ship with §3G, all as
    mode-tailor.md text. They are free, and they sit in the same paragraph as G.

## Global constraints

- `asked_lines()` output must not change. The existing `AdvertCoverage` tests pin it.
- `jsk match`'s printed and JSON output does not change. `--draft-gaps` and `--gaps` are additive.
- `posting.py` stays urllib-only at import. `extract` and `build` live in a new graph module,
  imported lazily inside `posting.main`.
- Keep the literals `tests/test_budget.py:303-315` asserts in the analyst file. It must stay under
  its token ceiling (2300); if the rewrite is shorter, lower the ceiling to fit.
- Commit only the files a task names, never `git add -A` (the tree holds the user's `pyproject.toml`,
  `uv.lock` and `.claude/`). Never commit while a subagent is working.
- Tests are unittest style, run with `python -m pytest tests -q -n auto`; lint with
  `python -m ruff check src tests`.
- After each task, run `pyright <each new or changed module>` (the CLI at
  `C:\Users\basil\.local\bin\pyright.exe`). This session has no LSP tool, so the CLI stands in for
  it and catches wrong imports and signature mismatches from subagents. Fix new errors only; the
  existing baseline is not in scope.
- Execute every regex written here before trusting it (memory: plan code is unverified).

## Build order and parallelism

Task 1 lands alone. Task 2 (docs only) can go any time. **Task 3 is the shared foundation: build it
first, in the main session.** Then Tasks 4, 5 and 6 fan out to subagents: each gets its own new
module and test file, pointed at the interface contract in Task 3. Task 6 calls Task 5's
`draft_gaps()` through the fixed signature, and merges after Task 5. Task 7 comes last.

---

### Task 1 — §0: the `advert-uncovered` punctuation bug

- **Modify** `src/jsk/graph/rules.py:243` to strip each quote as the line is stripped:
  `quotes[...].append(squash(v(r, "q") or "").casefold().rstrip(".;, "))`.
  Reproduced before planning: the bullet `- Experience: 12+ years of … experience.` quoted as
  `12+ years of … experience.` gives old `False`, new `True`.
- **Test** in `tests/test_graph_rules.py` class `AdvertCoverage`: a bullet with a label prefix and a
  trailing period, quoted without the prefix and with the period, raises no `advert-uncovered`.
- Commit: `fix: a quote ending in a full stop covers its advert line`.

### Task 2 — §3G/H/I: triage in `mode-tailor.md`

- **Modify** `plugins/jsk/skills/jsk/references/mode-tailor.md`: add a new `## 1b. Triage` between
  `## 1. Get the posting` (L47) and `## 2. Assess` (L60):
  1. Pick 2–5 load-bearing terms from the title and the first qualification lines, the title's
     domain first.
  2. In one message, run `jsk kb query evidence <terms>`, `jsk kb query person` and the
     duplicate-application check (H: independent calls go together; move the §0 check's calls into
     that same message).
  3. If a title term comes back `nothing`, or eligibility plainly fails, ask whether to continue,
     naming what is missing, **before** dispatching.
  4. I: if triage passes with a doubt, dispatch the analyst in the background and ask at the same
     time; on "stop", stop the agent.
- Keep §3's one-round rule (J) as it is.
- **Re-measure** the `mode-tailor.md` budget entries in `tests/test_budget.py`.
- Commit: `docs: triage a posting before the analyst runs`.

### Task 3 — foundation: advert lines, labels in a line, `concepts --near`

**Interface contract.** This is written once, and every later task depends on it.

- `rules.advert_lines(advert) -> list[AdvertLine]`, where
  `AdvertLine(n: int, section: "qualification"|"responsibility"|"other", text: str (squashed),
  optional: bool, elig: bool)`, numbered from 1 in order.
  - It is a refactor of the `asked_lines` loop.
  - A heading matching `HEADING_ASKS` and not `HEADING_NOT` opens `qualification`, with
    `optional` set if the heading matches `nice to have|bonus|preferred|desirable`.
  - `responsibilit\w*|what you('ll| will) do` opens `responsibility`.
  - `benefits|perks|we offer|compensation|salary` suppresses its list items.
  - Non-item prose paragraphs, and items before any heading, are `other`.
  - It skips the posting.md URL line and the `# title` line.
  - `optional` is also true when `OPTIONAL_WORDS` matches the line.
  - `elig` means `ELIGIBILITY.search(text)`.
- `asked_lines(advert)` becomes
  `[l.text for l in advert_lines(advert) if l.section == "qualification" and len(l.text.split()) >= 4 and not l.elig]`,
  with byte-identical results. Existing tests plus a new equality test over every `posting.md`
  fixture in `tests/` prove it.
- `queries.labels_in(store) -> Callable[[str], tuple[iri]]` returns the concepts whose whole label
  appears in a line, per Ruling 10. It builds on `labels()`-style SPARQL and on the retired-concept
  filter as `nearest()` does it (`queries.py:336-339`).
- `named.concept_list(store, near=None)`: with `near`, the rows are limited to
  `resolve(...)`'s exact concepts plus `queries.nearest(store, limit=5)(near)`, in that order.
  `kbcli.cmd_query` takes `--near TERM`, and only for `concepts`; otherwise it is a usage error.
- **Tests:** `tests/test_advert_lines.py` (sections, numbering, benefits suppressed, wrapped items,
  optional headings, the asked_lines equality) and additions to the existing query tests for
  `labels_in` and `--near`.
- Commit: `feat: the advert's lines by section, and the concepts named in each`.

### Task 4 — §1A/B: `jsk posting extract` and `jsk posting build` (subagent)

- **Create** `src/jsk/graph/postingbuild.py`, and **Test** `tests/test_posting_build.py`.
  **Modify** `src/jsk/posting.py`: `main` branches on `fetch | extract | build`, `USAGE` and the
  docstring are updated, and the new module is imported lazily.
- `extract(app_dir) -> str` prints the header: `# <title> at <company>`, `post: post_<stem with - as _>`,
  `url:`, `captured: <today>` and the seniority hint (Ruling 11). Company and title come from
  posting.md's `# ` line and the first fact. Then comes one row per `AdvertLine`: `n  section  flag
  line`, with the flag `elig` or `opt`, followed by `  concepts: c:a, c:b` from `labels_in`. The
  workspace is found by `kbcli.find_root(app_dir)`.
- `build(app_dir, decisions_path, replace=False) -> (path, n_requirements, warnings)` raises
  `Refused(message, fix)` and **refuses** on:
  - an unknown `n`;
  - an `asked` not in its line (casefolded and squashed);
  - a concept not in `queries.concepts(store)`, or a retired one;
  - a duplicate slug, or a bad `need`;
  - a qualification or responsibility line neither used nor dropped;
  - an existing posting.ttl without `replace`.

  The header keys `company`, `title`, `url`, `seniority`, `domain` and `captured` are read from
  `key: value` lines at the top of decisions.txt, and `extract` prints them ready to copy. The
  build writes `req_<poststem>_<slug>`, with `j:quote` set to **the extracted line's text** and
  `need` defaulted per Rulings 2 and 6. Output goes through `writer.write(quads, "posting")`, which
  gives the canonical layout.
- It **WARNs** (printed, exit 0) on more than 20 requirements, and on a responsibility promoted to
  `required` without `REQUIRED_WORDS`.
- **Key tests:**
  - A built posting.ttl loads with zero `quote-verbatim`, `advert-uncovered` and
    `necessity-wording` findings.
  - A line split into 3 requirements gives 3 quotes of the same line.
  - Each refusal has its own test.
  - `--replace` is required to overwrite.
  - Re-running build gives byte-identical output.
- Commit: `feat: jsk posting extract and build — code writes posting.ttl, the model decides`.

### Task 5 — §1C: `jsk match --draft-gaps` and the marker check (subagent)

- **Create** `src/jsk/graph/gapsdraft.py`, and **Test** `tests/test_gaps_draft.py`.
  **Modify** `src/jsk/graph/match.py`: add the `--draft-gaps F` flag (it refuses an existing F), the
  marker check in `report_gaps`, and the docstring.
- `draft_gaps(r, store, post, today, advert_path) -> str` fills in:
  - the frontmatter, with a `fit` slot;
  - `# Eligibility`, with a slot listing the `named.person` rows and the posting's `elig` lines;
  - the Requirements table, built from `r["requirements"]`: the match's verdict, the Evidence ids of
    confirmed carriers (all carriers with their evidence kind when `unevidenced`), a
    `<!-- jsk: shortfall -->` marker on every row that is not `satisfied`, and implicit rows per
    Ruling 9;
  - `# Ranking` as `match.markdown` prints it (reuse its row formatting; do not duplicate it);
  - slots for "Where this falls short" and "Surplus";
  - `# New terms`, from the `candidate` requirements plus the drops in `decisions.txt` if present;
  - `# Questions`, in the order blocking, unmet, unconfirmed, missing metric, unexplored, with a
    reword slot.
- **Marker check:** before the `rows is None` return, every line containing `<!-- jsk:` is
  `FAIL  line N: unfilled slot`, with the fix `fill it, or delete the slot`. It also catches the
  `<!-- jsk: shortfall -->` text that would otherwise pass as a non-empty Shortfall.
- **Key tests:**
  - A fresh draft run through `--gaps` FAILs once per marker.
  - The same draft with every slot filled passes with 0 FAIL and 0 WARN. Rows cannot drift from
    the requirement ids.
  - Drops from `decisions.txt` appear under New terms.
- Commit: `feat: jsk match --draft-gaps — code writes gaps.md, the model fills the slots`.

### Task 6 — §2D: `jsk kb check --only` and `jsk tailor prepare` (subagent, merges after Task 5)

- **Modify** `src/jsk/graph/kbcli.py` `cmd_check`: add `--only PATH`, normalised with
  `S.file_name`. It keeps findings whose `file` starts with PATH, plus every FAIL anywhere. The
  canonical-layout loop is restricted to files under PATH, and the untraced-number WARNs are
  omitted. Build the filtered report with `S.Store(root, findings=...).report()`, as
  `match.py:415` does.
- **Create** `src/jsk/graph/prepare.py`, and **Test** `tests/test_tailor_prepare.py`. **Modify**
  `src/jsk/cli.py` (`SIMPLE["tailor"]`, the `SUBPACKAGE` entry, and a docstring line
  `jsk tailor prepare APP`).
- `jsk tailor prepare APP [--draft-gaps] [--cover N] [--today D]` runs in one process and prints one
  digest, in this order:
  1. fmt (writer round-trip) of posting.ttl;
  2. the scoped check (stop on a blocking FAIL, using `match.blocks`);
  3. `match.markdown(result(...))`;
  4. `evidence_for` over the `asked` of every missing and candidate requirement;
  5. `person`;
  6. `with_children` / `entry_text` bullets for the Cover projects, capped at 3 projects;
  7. `unconfirmed`, filtered to entries of those projects;
  8. with `--draft-gaps`, `draft_gaps(...)` written to `APP/gaps.md`.

  Each section has a line cap and prints `… N more cut` when it truncates.
- **Key tests:**
  - The digest carries every section header in order.
  - A FAIL in another application does not stop prepare; a FAIL in its own directory does.
  - `--only` hides another application's WARNs.
  - The caps print their cut lines.
- Commit: `feat: jsk tailor prepare — the evidence phase in one call`.

### Task 7 — the analyst's procedure, the docs surface, and the full suite

- **Rewrite** `plugins/jsk/agents/jsk-tailor-analyst.md` §1 to §3 as: `jsk posting extract` →
  write `decisions.txt` → `jsk posting build` → `jsk tailor prepare --draft-gaps` → fill the slots
  with `Edit` → `jsk match … --gaps`. Add the §1A splitting rules:
  - one term the match can score per requirement;
  - alternatives stay one requirement;
  - company-internal names are dropped with a reason;
  - one ask in two lines is one requirement, quoting the qualification line;
  - the soft cap is 20.

  Remove the hand-written Turtle example and the "read the whole concept list" step (replace it
  with `concepts --near`). Keep the budget-asserted literals.
- **Docs surface:**
  - `docs/SCRIPTS.md` gets `jsk tailor`, plus the `posting extract|build`, `match --draft-gaps` and
    `kb check --only` entries;
  - `plugins/jsk/skills/jsk/SKILL.md` gets a `tailor` row in the command table (L85-97);
  - the `mode-tailor.md` §2 dispatch text names the new flow.
- **Re-measure** the `tests/test_budget.py` ceilings.
- **Run** `python -m ruff check src tests`, then `python -m pytest tests -q -rs -n auto`, then
  `python -m pytest tests/test_graph_budget.py -q -rs -s`.
- Commit: `docs: the analyst decides, code writes`.

## Verification

1. The full suite and ruff are green, including `tests/test_plugin_surface.py` (the new `tailor`
   subcommand in the help text, SCRIPTS.md and SKILL.md).
2. **Corpus replay.** This is manual, on a scratch copy of the user's workspace, never the live
   one. Pick JumpCloud plus one more application from `career/applications/`. For each, run
   `jsk posting extract`, write decisions.txt, run `jsk posting build --replace` into the copy, then
   `jsk tailor prepare --draft-gaps`. Compare with the hand-reviewed posting.ttl and gaps.md on:
   - requirement count (JumpCloud should drop from 41 to 20 or fewer);
   - concepts chosen;
   - verdicts;
   - zero `quote-verbatim` and `advert-uncovered` findings.
3. **Timed end-to-end run.** Run `/jsk:tailor <url>` on a fresh posting, and time the phases from
   the transcripts as in the spec's §"What the last run measured". The target is about 4 min end to
   end; a triage failure should take about 35 s.
