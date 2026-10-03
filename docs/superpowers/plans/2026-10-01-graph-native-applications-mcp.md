# Graph-native applications over MCP - implementation plan

## Status (2026-10-02)

Built on `feat/graph-native-mcp`, P0-P7:

- P0 measured (results below its section) - f7ecff2.
- P1 the render leaves a `.pdf` and a `.tex`; no `gaps.md` - 269e476, 7165507, merged 62d69f3.
- P2 the ontology and the domain - 5e2d2f8, merged 97c58de.
- P3a posting, review and assessment use cases - aea72f1, merged 4ae5e1e; P3b the selection
  and resume by target - 20df7b4, merged 47a7b66.
- P4 `jsk mcp` - 2afc098, merged b54fd37; the resume tools wired - 2bccf16.
- P5 freeze, letter, doctor for graph-native applications; the CI package job's retired
  `jsk new` - a030f25, merged bb997b0.
- P6 the plugin over the tools, 5.0.0 - 102b09b, merged (after bb997b0); CLAUDE.md - ac96ccc.
- P7 replay on a scratch copy of the real workspace (both postings, the "no" answering the
  second, a ship fitted to two pages, a held-back freeze, legacy unchanged), a code review and
  a prose review; their defects fixed in the commits after ac96ccc.

Not yet done: Verification 3 - a live `/jsk:tailor` in Claude Code with the plugin installed
from this tree (`install-local`), reading the analyst's transcript for tool calls only.

### Amendments made while building (2026-10-02)

- **Ruling 4:** `ReviewRow`'s reason is `j:shortfall`, not `j:reason` - every class already has
  `j:reason` for a retirement.
- **Ruling 9:** there is no `missing` verdict. An absence sets the requirement's match state
  to `missing` and its verdict to `unsatisfied` (an implicit one stays unassessed). A
  confirmed "no" on a concept also denies every concept that counts as it (the match's own
  closure): "never worked in financial services" answers a posting asking for insurance. A
  narrower "no" never denies a broader concept.
- **Ruling 8:** `j:Absence` sits in the career's "Open questions" section, not a new one - a
  new heading would print in every career and change every hash.
- **Ruling 14:** the read cache keys on the store's files (name, size, mtime) and
  `.jsk/backup.trig`, plus the server's own write counter - `tests/test_db.py` forbids any
  module but `db.py` opening the store, so the revision cannot be read separately.
- **Ruling 21:** the letter check takes a graph-native application through its existing
  `--record` flag (`--record <stem>`); no `--app` flag was added.
- **A held-back freeze is frozen too:** every tool refuses an application whose application
  graph exists, sent or held back, as `ship_target`'s `frozen_refusal` always did.
- **The server is named `graph`, not `jsk`** (2026-10-03, the user's call): a plugin's tools
  are `mcp__plugin_<plugin>_<server>__<tool>`, and `jsk`/`jsk` read `mcp__plugin_jsk_jsk__`.
- **A selection ships only with a summary.** The strict parse gate wants a summary heading,
  so the author sets one and the session confirms it before `resume_ship`.
- **Ruling 21 (2026-10-03):** freeze, event and letter check are tools too (`app_freeze`,
  `app_event`, `letter_check`), granted to no agent; twenty-one tools in all.

**Spec:** none. This plan and its Rulings are the spec. The decisions are the user's
(2026-10-01), made in one conversation:

- An application directory holds what was sent - the `.pdf` and the `.tex`, plus a cover
  letter's `.txt` when there is one - and nothing else. `<Name>_Resume_ATS.txt` is dropped.
- Everything else the pipeline knows about an application lives in the store, as structure
  that can be queried, not as files and not as opaque text.
- Agents write to the graph and query the graph. They do it through an MCP server, not by
  writing files for the CLI to read.
- **New applications only.** No migration: an application already on disk keeps working on
  the file path it was made on, untouched.
- A gap the person has already answered should be answerable again without asking them.

**Supersedes:** `2026-09-30-jsk-mcp-design.md` (a thinner MCP over the file pipeline), and
Ruling 5 of `2026-09-29-rocksdb-record.md` ("`posting.md`, `decisions.txt`, `gaps.txt`,
`gaps.md`, `resume.json` ... stay files"), for applications this plan creates. Ruling 7 of that
plan stands: the MCP server is not a long-running owner of the store.

**Kept, unchanged:** a model writes only decisions and code writes every triple; every write is
validated before it lands, through the one write gate (`infra/oxigraph/record.py`); new claims
arrive `j:inferred` and only a confirm with the person's answer raises them; a verdict can be
lowered, never raised; the render plan is the narrow waist; the onion rings.

## Context

### What an application is today

```
D/posting.md      fetch, or the session by hand    read by extract, build, the tier-2 rules, letter gate
D/decisions.txt   the analyst                       -> posting graph (requirements); drops stay in the file
D/gaps.txt        --draft-gaps, then the analyst    -> gaps graph (folded with the match, rewritten each run)
D/gaps.md         check_gaps                        read by nobody in code; the analyst returns its path
D/resume.json     kb export, the author, confirm    the selection, the summary/headline and their confirmation
D/<Name>_Resume.{pdf,tex,log}, <Name>_Resume_ATS.txt   render
```

### What the graph does not hold today (measured, 2026-10-01)

| Fact | Where it lives now |
|---|---|
| Every advert line but the quoted ones | `posting.md` only |
| Drops (advert line + reason) | `decisions.txt` only (`rules.dropped_lines`, `check_gaps:211`, `draft_gaps:39`) |
| The analyst's review, between runs | `gaps.txt` only - a posting rebuild writes `{"gaps": None}` (`build.py:335`) |
| The question queue | one `TEXT` block, `j:questions` |
| The selection, its order, settings, summary, headline and their confirmation | `resume.json` only; the application graph gets an unordered `carried` and a hash at freeze |
| A "no" the person gave ("never used Kafka") | nowhere - the next posting asks again |

### What already helps

- `tests/test_layers.py` already rings `jsk.mcp` as an adapter and holds
  `jsk.adapters.mcp` (the package `__init__`) to the standard library (`STDLIB_ONLY`, :47), so
  the server's entry point can report a missing SDK without importing it.
- `adapters/cli/compose/` has no argparse, printing or exit codes: an MCP adapter can bind
  through it. Its three leaks are `Reads.table` (presenters), `Folder.create` (`open()`), and
  the text-file reads, which are exactly the seams this plan replaces.
- Most use cases return structures (`Built`, `MatchReport.result`, `LoadedResume`,
  `RenderResult`, `ShipResult`, `FreezePlan`). Two return printable text: `extract` and
  `prepare` (`Digest`). Ship's ports capture CLI stdout (`adapters/cli/ship.py:84`).
- `plan.build(store, doc, ...)` takes `resume.json` as a plain dict. A selection read from the
  graph becomes the same dict, so the render plan, the emitters and the gates do not change.
- `fold.check`/`fold.fold` take an `Overlay` dataclass. An overlay built from triples
  instead of parsed from `gaps.txt` goes through the same checks unchanged.
- `write_application` (`records.py:295`) already validates a candidate as
  `load(root, graphs={...})` + `state.new_failures`. Every MCP write uses that pattern.
- `queries.py`'s `@query` registry: a new named query is one decorated function.

### Claude Code facts this relies on (docs, 2026-10-01; P0 measures the uncertain ones)

- A plugin bundles a server under `mcpServers` in `plugin.json` (or `.mcp.json` at the plugin
  root); it starts with the plugin, one process per session, shared by subagents.
- Tool names: `mcp__plugin_<plugin>_<server>__<tool>` - here `mcp__plugin_jsk_graph__<tool>`.
  Agent `tools:` and skill/command `allowed-tools` take that full name.
- Tool output: warning at 10k tokens, cut at 25k (`MAX_MCP_OUTPUT_TOKENS`); larger results
  are saved to a file and referenced.
- Tool search defers tool definitions until needed.
- **Uncertain:** whether a subagent with no `tools:` inherits MCP tools; wildcards in
  `tools:`; the default tool-call timeout (matters for `resume_ship`, which compiles TeX).

## Rulings

### The data model

1. **The advert is stored as lines.** New class `j:AdvertLine` in the posting graph,
   `k:line_<stem>_<n>`: `j:posting` (1), `j:n` (integer, 1), `j:section`
   (`qualification|responsibility|other`, 1), `j:text` (TEXT, 1), `j:optional` and
   `j:eligibility` (boolean, ?), `j:dropped` (STR, ?: the analyst's reason for leaving it out).
   The fields are `advert.AdvertLine`'s, computed by `advert_lines()` exactly as now. Concepts
   are **not** stored on a line: they depend on the vocabulary, which changes, so
   `posting_lines` computes them on read (`labels_in`), as `extract` does today.
2. **A requirement points at its line.** `Requirement` gains `j:line` (Ref `AdvertLine`, ?).
   `j:quote` stays and is still the line's text: a new tier-2 rule `quote-is-line` FAILs a
   requirement whose `j:quote` differs from its line's `j:text`. On a graph-native posting
   `quote-verbatim` reads the lines from the graph instead of `posting.md`.
3. **A posting has a state.** `Posting` gains `j:state` (`draft|complete`, ?; absent means a
   legacy file-built posting, which is complete). `j:advert` goes from `1` to `?`: relaxing a
   cardinality is an optional change, so `ontology.FORMAT` stays 3. A graph-native posting has
   no `j:advert`. `advert-uncovered` applies only to `complete` and legacy postings - a draft
   is allowed to be half-decided.
4. **The analyst's review is its own graph: `applications/<stem>/review`.** It is the overlay
   as triples and it survives what the gaps graph does not (a re-derivation, a posting
   rebuild). One `j:Review` (`k:rvw_<stem>`): `j:posting` (1), `j:fit` (?), `j:eligibility`
   (?), `j:state` (`draft|complete`, ?). Per requirement, `j:ReviewRow`
   (`k:rvr_<stem>_<slug>`): `j:review`, `j:requirement`, `j:verdict` (`keep` or a verdict),
   `j:reason` (?). Ordered items, `j:ReviewItem` (`k:rvi_<stem>_<kind>_<i>`): `j:review`,
   `j:kind` (`short|surplus|ask`), `j:position`, `j:text`, `j:about` (Ref `Requirement`, ?).
   Reading it back gives `overlay.Overlay`, and `fold.check`/`fold.fold` run unchanged.
5. **Questions are structured in the gaps graph.** The folded assessment writes one `j:Ask` per
   question (`k:ask_<stem>_<i>`): `j:assessment`, `j:position`, `j:question`,
   `j:requirement` (?), `j:concept` (*: the requirement's concepts, copied so a question is
   queryable by concept without a join). `j:questions` stops being written for graph-native
   applications; it stays in the ontology for legacy ones.
6. **A selection is a graph: `applications/<stem>/resume` or `resumes/<name>/resume`.** One
   `j:Selection` (`k:sel_app_<stem>` or `k:sel_cv_<name>`): `j:format`, `j:region`, `j:pages`,
   `j:atsPages`, `j:floor` (each ?, `resume.json`'s keys and defaults); `j:summaryText`,
   `j:summaryStatus`, `j:summaryAnswer`, `j:summarySha` and the same four for `headline`
   (each ?). Per item, `j:Pick` (`k:pck_<sel>_<kind>_<i>`): `j:selection`, `j:item` (Ref
   `Achievement|Position|Skill`), `j:position` (integer), `j:alias` (STR, ?: `names`).
   `selection.doc_of(graph)` returns the `resume.json` dict (`"resume": 2` and the same keys);
   `short.shape`/`short.ids` check it and `plan.build` renders it. `resume.json`'s keys stay the
   frozen interchange format; nothing writes the file for a graph-native application.
7. **`recordSha256` is the hash of the canonical selection.** For a graph-native application
   it is SHA-256 of `json.dumps(doc_of(graph), sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)` encoded UTF-8. The ontology's doc string says so. A legacy freeze still
   hashes its file.
8. **A "no" is a claim in the career.** New class `j:Absence` in `kb`, `claims=True`
   (`k:abs_<concept-local>`): `j:concept` (1), `j:said` (DATE, 1), `j:answer` (TEXT, 1: the
   person's words), plus the usual provenance. It arrives `j:inferred` through a changeset and
   counts only once `career_confirm` confirms it with the person's answer. It **lapses** 365
   days after `j:said` (a constant in `domain/record/absence.py`, not stored): a lapsed absence
   is ignored by the match and listed by `career_query("absences")` as due. A tier-2 WARN
   `absence-contradicted` fires when a live project holds the concept the absence denies (with
   its mutation in `test_graph_rules.py`).
9. **The match uses a confirmed, unlapsed absence.** In `derive`, a requirement whose concepts
   are all covered by such absences gets verdict `missing`, `j:basis` "said on <date>: <answer>",
   and no question. Its `j:Ask` is never written, so the same "no" is never asked twice. A
   requirement listing alternatives (`j:concept` any-of) is covered only when every
   alternative is denied.
10. **No new graph for the advert, no text blobs.** The five kinds of application graph are
    `posting`, `review`, `gaps`, `resume`, `application` - `review` and `resume` are new. They
    join `records.RECORD`, `ontology.SECTIONS`/`HEADS`/`FILE_KINDS`, `write_frozen`'s moves and
    `refuse_if_sent`. `resumes/<name>/resume` is new top-level naming in `db.py`'s graph names,
    `kb dump`/`kb load`, and `jsk kb new` (creates `resumes/`).

### Graph-native and legacy

11. **An application is graph-native when its posting graph holds `j:AdvertLine`s.**
    Everything it is - advert, requirements, drops, review, assessment, selection - is in the
    store. A legacy application (files) is untouched. The file verbs (`posting build` from
    `decisions.txt`, `tailor match --gaps`, `resume.json` paths) refuse a graph-native
    application, naming the tool; the MCP tools refuse a legacy one, naming the file verb. No
    application is ever both. The file path is not deleted by this plan; its retirement is a
    later plan's decision.
12. **A graph-native application is named by its stem.** Tools take `app: "<stem>"`
    (`applications/<stem>`); a general resume is `target: "resumes/<name>"`. The directory on
    disk is created by the first render and holds only what was rendered.

### The MCP server

13. **`jsk mcp` is an adapter beside the CLI.** `src/jsk/adapters/mcp/`: `__init__.py`
    (stdlib only - imports the SDK inside `main()`, and on `ImportError` prints
    `the MCP server needs the mcp extra: pip install 'jsk-resume[mcp]'` and exits 2),
    `server.py` (the tools), `schemas.py` (argument and result shapes), `session.py` (workspace
    and revision cache). It binds through `adapters/cli/compose/` and the use cases; it holds no
    logic a CLI test could not reach. The SDK is an optional extra, `mcp = ["mcp>=1.30,<2"]`
    (floor confirmed in P0), added to `dev` so CI tests it.
14. **No long-lived lock.** Each tool call that writes takes the writers' turn, loads, builds
    its candidate, validates it (`load(root, graphs=candidate)` + `new_failures`), writes
    through `records.write_app_graphs` or `record.commit`, and gives the turn up, exactly as a
    CLI command does. Reads are served from a loaded `Store` cached per `(root, revision)`;
    the server re-reads the revision on each call (one `read_only` open) and reloads when it has
    moved. Application graphs carry no revision, so the cache key also includes a counter the
    server bumps on its own application writes, and the store's file mtime for others'.
15. **The workspace is the session's.** `find_root(os.getcwd())` at start, overridable by
    `JSK_ROOT`. A tool call with no workspace returns the `jsk kb new` fix, never a traceback.
16. **Every result is JSON, every refusal is a finding.** A tool returns
    `{"ok": true, ...}` or `{"ok": false, "findings": [{"severity", "text", "fix"}]}` - the
    `(message, fix)` pairs `Refused.every` and the gates already produce. An unexpected
    exception becomes one `FAIL` finding naming the tool (the `call_gate()` precedent), logged
    to stderr with its traceback. Results that can be long (`career_view`, `posting_lines`)
    take `section`/`offset`/`limit` and stay under 10k tokens by default.
17. **Clock at the edge.** The server reads `datetime.date.today()` once per call in
    `server.py` and passes `today=` down, as the CLI does in `adapters/cli/options.py`.

### Tools (18) and who gets them

18. **The tool set.** Batches are JSON arrays; nothing an agent sends needs shell quoting.

| Tool | Does | Wraps |
|---|---|---|
| `career_view(section?)` | the career as Markdown | `kb view` |
| `career_show(ids, bullets?)` | entries as Turtle, with the `op:base` | `kb show` |
| `career_query(name, args?)` | any named query, rows as JSON | `kb query` |
| `career_log(last?)` | the history | `kb log` |
| `career_preview(changeset)` | a TriG changeset dry-run: the diff, findings | `kb apply --dry-run` |
| `career_apply(changeset)` | apply it (validate, write, log) | `kb apply` |
| `career_confirm(ids?, target?, block?, answer, source?, quote?)` | confirm entries, or a selection's summary/headline | `kb confirm` |
| `app_list()` | applications and resumes, their state and stage | `kb query pipeline` + states |
| `app_show(app, part)` | `posting`, `lines`, `requirements`, `review`, `assessment`, `selection` as JSON | new reads |
| `posting_capture(app, url? \| text?, company?, title?, captured?)` | fetch or take pasted text; store the lines; posting `draft` | `fetch` + `advert_lines` |
| `posting_decide(app, header?, requirements[], drops[], remove[])` | upsert rows and drops, checked per row | `build.requirements` checks |
| `posting_complete(app)` | every qualification line used or dropped; tier-2; `complete` | build's coverage check |
| `assessment_derive(app)` | match, derive, fold the stored review; write gaps; return rows, flags, questions | `match_posting` + `check_gaps.build` |
| `assessment_review(app, fit?, eligibility?, verdicts[], short[], surplus[], asks[])` | upsert the review, checked against the match per row | `fold.check` |
| `assessment_complete(app)` | no unreviewed flag, no FAIL; review `complete` | `fold.check(reviewed=True)` |
| `resume_select(target, mode, replace?)` | `from_match` or `ranked`; store the selection | `export.short` |
| `resume_update(target, bullets?, roles?, skills?, names?, format?, region?, pages?, ats_pages?, floor?, summary?, headline?)` | change the selection; a changed summary/headline text drops to `inferred` | `short.shape`/`ids` |
| `resume_ship(target, ats_max?, template?, pages?, fit?)` | record gate, render, fit, gates into the directory; steps as JSON | `application/ship.py` |

19. **Grants enforce the boundaries the prose states today.**

| Caller | Tools | Keeps |
|---|---|---|
| main session (`SKILL.md` and commands' `allowed-tools`) | all 18 | Bash (doctor, freeze, event, letter check) |
| `jsk-tailor-analyst` | `career_view/show/query`, `app_show`, `posting_*`, `assessment_*` | Read (references) - **no Write, Edit or Bash** |
| `jsk-resume-author` | `career_view/show/query`, `career_preview`, `career_apply`, `app_show`, `resume_select`, `resume_update` | Read |
| `jsk-extractor` | `career_view/show/query`, `career_preview` | Read, Glob (sources) - no Write |
| `jsk-kb-auditor` | `career_*` reads, `app_list`, `app_show` | Read, Write (`audit.gaps.md`) |
| `jsk-verifier` | `career_show`, `app_show` | Bash, Read, Glob (`jsk resume check --only`) |

    `career_confirm` is granted to no agent: it carries the person's words, and only the main
    session talks to the person. `career_apply` writes only `j:inferred` (as `kb apply` does).
    The analyst can no longer touch the career because it has no tool that could - the
    sentence "**Never touch the career**" stays, and is now also true by construction.
20. **`resume_ship` reuses the CLI's ship ports.** It calls `application/ship.py` with the
    ports `adapters/cli/ship.py` binds (adapter to adapter is allowed), and returns each
    `GateStep` as `{name, passed, output}`. It honours `frozen_refusal`. If P0 measures a
    tool-call timeout shorter than a fitted ship (~30 s worst case on this machine), the tool
    runs `--no-fit` by default and says so.
21. **What stays CLI only:** `kb new`, `doctor`, `app freeze`, `app event`, `letter check`,
    `kb dump/load`, `resume check/render/preview/fit` over a directory. These are a person's
    acts or a verifier's tracing. `app freeze` and `letter check` learn to read a graph-native
    application (P5).
    *Amended 2026-10-03:* freeze, event and letter check are tools too - `app_freeze`,
    `app_event` and `letter_check`, each calling what its command calls - so the main session
    needs no shell for a jsk job. They are granted to no agent.

### The render

22. **A render leaves the `.pdf` and the `.tex`.** `compile_pdf` (`infra/tex.py:50-88`) deletes
    `.log`, `.aux`, `.out`, `.fls`, `.fdb_latexmk` for its stem after a clean compile and keeps
    them on a failed one, naming the log. `--keep-logs` stays so a failure has one.
23. **No `_ATS.txt`; its checks run over the text in memory.** `emit_text.emit(plan)` is the
    same plan as the `.tex`. The parse gate's strict ASCII pass and its reading-order rule
    (`ats.py:24-38`, today silently skipped when the file is missing) and the terms gate read
    that string; the prose gate already reads the `.tex`. `--format txt` exits 2. The gates
    still accept a `.txt` passed by hand: the cover letter is one. Freeze lists PDFs and letters.
24. **No `gaps.md`.** The assessment is `app_show(app, "assessment")` (and printed by the legacy
    `tailor match`). Nothing in code read it.

## Architecture

```
src/jsk/domain/posting/lines.py        NEW  AdvertLine <-> triples; lines_of(store, post)
src/jsk/domain/posting/decide.py            + drops on lines, j:line on requirements, j:state
src/jsk/domain/posting/rows.py         NEW  a requirement row / drop checked against the lines
                                            (build.requirements' checks, one row at a time)
src/jsk/domain/assessment/review.py    NEW  Overlay <-> review triples
src/jsk/domain/assessment/fold.py           + j:Ask nodes instead of j:questions (graph-native)
src/jsk/domain/assessment/derive.py         + absences -> missing, no question
src/jsk/domain/resume/selection.py     NEW  doc dict <-> selection triples; canonical(doc)
src/jsk/domain/record/absence.py       NEW  LAPSE_DAYS, live(absence, today)
src/jsk/domain/record/rules.py              + quote-is-line, absence-contradicted; quote-verbatim
                                              and advert-uncovered read lines; drafts skipped
src/jsk/domain/ontology.py                  + AdvertLine, Review, ReviewRow, ReviewItem, Ask,
                                              Selection, Pick, Absence; Requirement.line;
                                              Posting.state, advert ?; graph kinds review, resume
src/jsk/application/posting/capture.py NEW  posting_capture
src/jsk/application/posting/decide.py  NEW  posting_decide, posting_complete
src/jsk/application/tailor/review.py   NEW  assessment_review, assessment_complete
src/jsk/application/tailor/check_gaps.py    + overlay from the review graph for graph-native
src/jsk/application/render/selection.py NEW resume_select, resume_update, read_selection
src/jsk/application/record/queries.py       + demand, shortfalls, drops, outcomes, repeated, absences
src/jsk/application/timeline/records.py     + review, resume kinds; resumes/<name>
src/jsk/application/timeline/freeze.py      + graph-native: selection hash, no resume.json
src/jsk/infra/oxigraph/db.py                + resumes/<name>/resume graph names
src/jsk/infra/tex.py                        by-products removed on success
src/jsk/adapters/mcp/__init__.py       NEW  stdlib-only entry: main(), the extra's refusal
src/jsk/adapters/mcp/server.py         NEW  the 18 tools
src/jsk/adapters/mcp/schemas.py        NEW  argument and result shapes
src/jsk/adapters/mcp/session.py        NEW  workspace, revision cache, the clock per call
src/jsk/adapters/cli/main.py                + `jsk mcp` noun
plugins/jsk/.claude-plugin/plugin.json      + mcpServers.graph = {command: jsk, args: [mcp]}
```

Every new module gets its line in ARCHITECTURE.md's layout in the same commit
(`test_plugin_surface.ArchitectureNamesTheCode`), and the noun count sentence moves with `mcp`.

## Phases

Each phase ends green - `python -m pytest tests -n auto`, `python -m ruff check src tests`,
pyright on the rings - and is committed on its own. Tests follow CLAUDE.md: `unittest`,
classes named for the subject, methods that read as the rule, workspaces from `careerkit` in a
`TemporaryDirectory`, and **every new check gets a test that plants the violation**. Run
`findReferences` (LSP) before changing any function's signature.

### P0 - measure Claude Code before relying on it

In a scratch plugin with a three-tool stub server (Python, the `mcp` SDK), installed through
`install-local`'s route:

1. The tool names as Claude Code shows them (`mcp__plugin_jsk_graph__x`).
2. A plugin subagent with an explicit `tools:` list naming two of the three tools sees
   exactly those two. With `tools:` omitted - does it see all three? Does `mcp__plugin_jsk_graph__*`
   work in `tools:`?
3. A command's `allowed-tools` with MCP names.
4. The tool-call timeout: a tool that sleeps 10, 30, 60 s. Sets Ruling 20's default.
5. A 40k-token result: cut, or saved to a file.
6. The `mcp` SDK version that runs on Python 3.10 and 3.13, Windows and Linux; sets Ruling 13's
   pin.

Results go in this plan as an amendment before P4 starts. If (2) fails - subagents cannot be
held to a subset - Ruling 19 falls back to the prose boundaries and the tools' own semantics
(`career_apply` writes only `inferred`, `career_confirm` needs an answer). A server-side role
check is not possible: one server process serves the whole session and cannot tell which agent
called. The plan says so in an amendment rather than pretending the grants hold.

#### P0 results (2026-10-02, Claude Code 2.1.280, headless `claude -p --plugin-dir`, a stub plugin)

1. Tool names are `mcp__plugin_<plugin>_<server>__<tool>`: the stub's showed as
   `mcp__plugin_jskprobe_probe__alpha`. jsk's will be `mcp__plugin_jsk_graph__<tool>`.
2. **An explicit `tools:` list holds a plugin subagent to exactly those tools** - granted
   `alpha, beta`, the agent saw only those two (plus `SubagentHandback`). **No `tools:` line
   inherits every MCP tool** of the session. **`mcp__plugin_<p>_<s>__*` works** and grants the
   whole server. So Ruling 19 holds as written, and every agent must list its tools by name -
   never the wildcard, never an omitted `tools:`. P6 pins that.
3. A command's `allowed-tools` naming an MCP tool lets it call that tool with no other grant.
4. No tool-call timeout at 150 s (`sleep_for(150)` returned). Ruling 20's fallback is not needed:
   `resume_ship` fits by default.
5. A 200k-character result is refused inline and saved to `tool-results/...txt`, with an error
   naming the file. Ruling 16's default limits (under 10k tokens) stand.
6. `mcp` 1.30.0 installs on Python 3.12 here; it declares `Requires-Python >=3.10`. Pin
   `mcp>=1.30,<2`. `FastMCP` tools with typed parameters produce JSON schemas; a `dict` return
   arrives as JSON text content (not `structuredContent`) unless the return type is a typed
   model - tests read the text. In-process tests use
   `mcp.shared.memory.create_connected_server_and_client_session(server._mcp_server)`.

### P1 - the render leaves a `.pdf` and a `.tex` (all applications)

- Ruling 22 in `infra/tex.py`; tests with the faked compile (`shipkit`): clean run leaves no
  `.log`, failed run keeps it and the message names it.
- Ruling 23: `targets.py` drops `plaintext` from `all`; `--format txt` exits 2 naming the
  change; `ats.py` takes the plan's text (no `stream_of` file read); `strict_for` keys on the
  run, not `_ATS` in a name; `DOC_GATES`/`CHECK_GATES` drop `.txt`; terms gate over the same
  string. New planted test: a plan whose emitted text breaks reading order fails the parse gate
  with no `.txt` on disk.
- Ruling 24: `check_gaps` stops writing `gaps.md`; `tailor match` prints the assessment after
  its verdict lines (lines added, none reworded); `build.py:338` stops removing one.
- Tests changed on purpose (named here because they are the point): the six `.txt` tests in
  `test_render_resume.py`; `test_record_gate.py:432`; `test_resume_ship.py::
  test_a_failing_document_gate_fails_the_ship`; `test_preflight.py::
  test_verify_runs_the_pipeline_and_every_gate` (the step name stays); `test_resume_check.py`'s
  `GatesAgreement.five_commands` and the two count tests; `test_terms.py::Gate.run_gate`;
  `test_app_freeze.py`'s fixtures (`shipkit.py:173`); `gaps.md` assertions in
  `test_gaps_build.py` and `test_graph_match.py`.
- Prose that names the `.txt` or `gaps.md`: `mode-resume.md` output table, `jsk-verifier.md`,
  `SKILL.md`, `ats-rules.md`, `rationale.md`, `commands/resume.md`, the analyst's return line,
  the author's `gaps.md` read (now the printed assessment), README, ARCHITECTURE ("the PDF and
  the text the gates read cannot disagree"), SCRIPTS, CONCEPTS, QUICKSTART, WHY, CLAUDE.md:77.

P1 ships alone: it helps legacy applications too and depends on nothing below.

### P2 - the ontology and the domain

- `ontology.py`: Rulings 1-6, 8, 10. `kb-format.md` and `docs/ONTOLOGY.md` in the same commit
  (`TheSectionsAndTheFormatAgree` checks every kb/posting predicate is named in kb-format.md).
  `kb-format.md` is capped at 2000 (`test_budget.py:258`): the application classes go in
  `ONTOLOGY.md` in full and in `kb-format.md` as one line each.
- `domain/posting/lines.py`, `rows.py`; `decide.triples` extended; `domain/assessment/review.py`;
  `fold.triples` writes `j:Ask`; `domain/resume/selection.py` with `canonical(doc)`;
  `domain/record/absence.py`; `derive` takes absences.
- Rules: `quote-is-line` (FAIL), `absence-contradicted` (WARN), `quote-verbatim` and
  `advert-uncovered` read `j:AdvertLine`s when the posting has them, drafts skipped. Each new
  rule gets its `MUTATIONS` entry (`test_every_rule_has_a_mutation`) and its severity in
  `WARNS`.
- Round-trip tests, pure: `Overlay -> triples -> Overlay` equal; `doc -> triples -> doc`
  equal for every key in `short.KEYS` (summary/headline blocks included); `advert_lines ->
  triples -> lines` equal; `canonical(doc)` stable across key order.
- `derive` tests: one confirmed absence makes a requirement `missing` with the basis and no
  question; an inferred one does nothing; a lapsed one does nothing and is listed due; an
  any-of requirement with one alternative denied still asks.

### P3 - the use cases, without MCP

- `application/posting/capture.py`: `capture(root, stem, *, url|text, company, title, today,
  get, records)`. Fetch through the existing `infra/posting_sources` (or take `text`), build
  lines, write the posting graph `{Posting(draft), AdvertLine*}` under the turn. Refuses an
  existing posting graph unless `replace` (which also drops review and gaps, as a rebuild does
  today - Ruling 4's review survives only a *re*-derivation, not a new advert).
- `application/posting/decide.py`: `decide(root, stem, header, rows, drops, remove, today)` -
  each row checked by `rows.py` against the stored lines (line exists, asked in line, unique
  slug and asked, need valid, concepts known); the posting graph rewritten whole in one update;
  findings per row, nothing written if any FAIL. `complete(root, stem)` - coverage FAIL as
  `build.py:266-271`, then the full candidate validation (`load(graphs=)` + `new_failures`),
  then `j:state complete`.
- `application/tailor/review.py`: `review(root, stem, fit, eligibility, verdicts, short, surplus,
  asks)` - upsert into the review graph; each verdict checked by `fold.check` against the
  current derived match (raising FAILs at once). `complete(root, stem)` - `fold.check(...,
  reviewed=True)`, no FAIL, then `j:state complete`.
- `check_gaps.build`: for a graph-native application its `Folder` reads the overlay from the
  review graph and the drops from the lines; `gaps.txt` is never read. The posting rebuild's
  `{"gaps": None}` leaves `review` alone.
- `application/render/selection.py`: `select(root, target, mode, replace, today)` wraps
  `export.short` and writes the selection graph; `update(root, target, **fields)` - apply,
  `short.shape` + `short.ids`, a changed summary/headline text resets its status to
  `inferred` and drops its answer and sha; `read(root, target)` returns the dict.
- `confirm.confirm_summary` gains the graph-native branch (writes the selection graph); the
  file branch stays for legacy.
- `load_resume`, `build_plan`, `render_resume`, `ship`, `run_gates`, `layout`, `posting_terms`,
  `company_of`: accept a target (stem or `resumes/<name>`) as well as a path, getting the doc
  from `selection.read`. The path form is unchanged for legacy.
- Queries (Ruling 9's `absences` and the insights), each `(columns, rows)`:
  `demand` (concept, postings asking, required count, my verdicts), `shortfalls` (requirement
  concepts with verdict `missing`/`partial` across applications, live absences marked),
  `drops` (reasons grouped, with postings), `outcomes` (applications by fit and latest event
  kind), `repeated` (`j:Ask` concepts asked in more than one application), `absences`
  (live and due). `cmd_query`'s docstring list updated.
- Tests per use case with `careerkit`: the happy path; every refusal planted (an asked term not
  in its line, a duplicate slug, a raised verdict, an uncovered qualification line at
  `complete`, an unknown id in `resume_update`, a sent application); legacy refusal both ways
  (Ruling 11); `posting_capture` from pasted text with no network.

### P4 - the MCP adapter

- `adapters/mcp/` per Rulings 13-18; `jsk mcp` in the noun table (`main.py`), `SKILL.md`,
  `docs/SCRIPTS.md` (all pinned by `DocumentedSurface`), and the ARCHITECTURE noun count.
- `pyproject.toml`: `mcp` extra, and in `dev`. CI installs `.[dev]` already, so the Windows
  and Linux jobs run it. The `package` job adds `jsk mcp --help` from the wheel without the
  extra and asserts exit 2 with the install line.
- Tests (`tests/test_mcp_*.py`, `unittest`, skipped when `mcp` is not importable):
  - each tool called in-process through the SDK's in-memory client session (P0 confirms the
    API) against a `careerkit` workspace - result shapes, refusals as findings;
  - one stdio subprocess smoke test: start `python -m jsk mcp`, list tools, call `app_list`;
  - the cache: a CLI `kb apply` between two `career_view` calls is seen by the second;
  - concurrency: a tool write while a CLI writer holds the turn waits, then lands;
  - an exception inside a use case becomes one FAIL finding, and the server keeps serving;
  - the tool budget: the 18 definitions (names, descriptions, schemas) as `tools/list` returns
    them, bytes/4, under 4500 - a new cap in `test_budget.py`, measured when P4 lands and set
    with ~10% headroom.

### P5 - freeze, letter and doctor for graph-native applications

- `freeze.py`: graph-native branch - reads the selection, `recordSha256` per Ruling 7,
  `carried` from the plan's `sent`, documents are the PDFs and letters in `applications/<stem>/`;
  moves `posting`, `review`, `gaps`, `resume` with the application graph (`write_frozen`).
  Tests: a graph-native freeze lands, the directory renamed to its day, all five graphs moved;
  `resume_update` on it refused afterwards.
- `letter check LETTER --app <stem>`: the advert from the lines, the record from the selection.
- `jsk doctor` reports whether the `mcp` extra is importable (an INFO line, never a FAIL -
  the CLI works without it).

### P6 - the plugin

- `plugin.json`: `mcpServers` (`graph` → `jsk mcp`). Version bump to **5.0.0** in `plugin.json`,
  `marketplace.json` and `jsk.__version__` (`Manifests`): agents now need the extra.
- Agent frontmatter per Ruling 19 (full tool names, or the wildcard if P0 proved it).
- Agent bodies rewritten around tools:
  - analyst: `posting_capture` (when the session has not), `app_show(lines)`, one
    `posting_decide` batch, `posting_complete`, `assessment_derive`, one `assessment_review`
    batch, `assessment_complete`, return the assessment. Budget 1900 (`test_budget.py:87`);
    it should shrink - file paths, `--gaps` and the `decisions.txt` format leave it.
  - author: `resume_select(from_match)`, `career_show` for the bullets it will reword,
    `career_apply` for new bullets, `resume_update`. Bundle cap 5100.
  - extractor: `career_preview(changeset)` instead of writing `changes/*.trig` and
    `kb apply --dry-run`. Bundle cap 3400.
  - auditor, verifier: read tools; verifier keeps its CLI tracing.
- `mode-tailor.md`, `mode-ship.md`, `mode-resume.md`, `mode-gaps.md` (absences: how a "no"
  is recorded and confirmed), `mode-refresh.md` (due absences), `SKILL.md` (tools table,
  `allowed-tools`), `resume-format.md` (the keys, now the selection's), commands'
  `allowed-tools`. Caps: SKILL 2400, SKILL+tailor+ship 6300.
- Pinned strings that change on purpose, each named in the commit: `test_budget.py`'s author
  strings (`--out applications/<stem>/resume.json --replace`, "**Then edit only** `bullets`",
  "Do not read any other `resume.json`"), the analyst's "jsk tailor match applications/<stem>
  --gaps", mode-tailor's "Patch it yourself when every change is a row", and
  `test_plugin_surface.py:217` (analyst and author keep Bash - the analyst loses it). New pins
  replace them: the analyst's tools exclude Write, Edit, Bash and `career_apply`; no agent has
  `career_confirm`; the extractor has `career_preview` and not `career_apply`.
- `docs/ARCHITECTURE.md` (the tailoring pipeline section rewritten: tools write the graphs;
  the narrow waist unchanged), `SCRIPTS.md` (`jsk mcp` and the tool table), `CONCEPTS.md`,
  `WHY.md` (why MCP: typed batches, grants as boundaries), `README.md`, `QUICKSTART.md`.

### P7 - replay and review

- A **new** application end to end in a scratch copy of the real workspace
  (`C:\Projects\basilin-joe-resume\career`, never the original): capture a real posting,
  decide, complete, derive, review, answer one "no" and confirm it, select, ship, freeze. The
  directory holds `.pdf` and `.tex` only. Then a second posting asking the same concept:
  the absence answers it, no question. Then `career_query("demand"|"shortfalls"|"repeated")`.
- A legacy application in the same copy: tailor and ship on the file path, unchanged.
- Two reviews of the whole diff: code, and prose.

## Risks

- **P0 says subagents cannot be held to a tool subset.** Grants become advice; the boundary
  falls back to the prose and the tool semantics (`career_apply` writes only inferred,
  `career_confirm` needs an answer). The plan proceeds; Ruling 19 is amended to say so.
- **Two pipelines until legacy retires.** Ruling 11 keeps them apart by refusal both ways;
  every reader that branches (`check_gaps`, `freeze`, `confirm`, the gates) has a test per
  branch. The retirement is a later plan, with its own exit-2 messages.
- **The tool-call timeout vs TeX.** Ruling 20's fallback; `resume_ship` reports progress in its
  result, not by streaming.
- **The analyst's budget** - 5 tokens of headroom today. Moving to tools removes more than it
  adds; measure in P6, don't assume.
- **Absences are judgement.** A stale "no" hides a real skill. Lapse at 365 days, the
  contradiction WARN, `mode-refresh` listing due ones, and the confirm requirement bound it.
- **Cache staleness.** Ruling 14 keys on revision plus an application-write counter plus the
  store's mtime; the cross-process test in P4 pins it.
- **Hidden callers.** Lazy imports hide callers from `rg`; LSP `findReferences` before every
  signature change (CLAUDE.md), and the layers test catches any outward edge.

## Verification (after P4, again after P7)

1. `python -m pytest tests -n auto`, ruff, pyright on the rings, `test_graph_budget.py` alone.
2. CI green on Linux and Windows, with and without TeX; the `package` job's no-extra refusal.
3. `install-local`, restart Claude Code, `/jsk:tailor` on a new posting: the analyst's
   transcript shows tool calls only - no file written in the application directory.
4. P7's replay, both applications.
