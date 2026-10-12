# Onion architecture for `src/jsk`: dependencies point inward, and a test says so

**Status:** implemented, 2026-10-01, on feat/vocabulary-graph from `29e08fc` (this spec) onward.
Reviewed 2026-09-30 against the code through pyright; fixes folded in. Where the build departed
from a ruling, "As built" at the end says how and why.
**Builds on:** `docs/ARCHITECTURE.md` (the layering rules at :217-227 and "What is a package
here" at :376-404), `docs/WHY.md` (the `okf` table at :125-145), `docs/SCRIPTS.md:8-9` (module
paths are documented API until P5 drops them, Ruling 10), and `specs/2026-09-30-jsk-mcp-design.md` (a second driving adapter).
**Line numbers** are as of `4768473` on `feat/vocabulary-graph`.

## The goal

Every module in `src/jsk` sits in one of five rings, and an import may only point at its own
ring or one further in:

```
adapters        cli, mcp                     argv, stdout, exit codes, flag parsing
infra           oxigraph, files, tex, pdf,   everything that touches a disk, a process,
                posting sources, clock        the network, the engine or the clock
application     one use case per command      orchestrates domain + ports, returns a result
ports           Protocols                     what application and domain need from outside
domain          the record, matching,         pure: no files, no argv, no env, no clock,
                selection, gates' rules        no pyoxigraph Store (Ruling 2)
```

A stdlib test (`tests/test_layers.py`) walks every import, **lazy ones included**, and fails an
outward edge. Through P4 the CLI's output, exit codes and the `python -m jsk.<module>` paths do
not change. Then P5 makes the CLI `jsk <noun> <verb>` (Ruling 10) over the finished adapters,
and drops the module paths.

Three things this buys:

- **The six package cycles go.** Today `graph` imports `cli`, `render` imports `cli`, and graph,
  gates, posting and resume import each other in both directions. Lazy imports hide every one of
  them until run time.
- **Use cases stop printing.** Today every `main()` is a use case and a printer in one. That is
  why `cli.summary_lines` (cli.py:754-808, its regexes at :745-752) *regex-parses other modules' stdout* to build the
  `jsk gates` summary. With results returned as values, that parser and its failure mode go.
- **The MCP server and the CLI share one inward seam.** Neither has to know where the record
  lives.

**P0-P4 are not a rewrite and not a speed change.** Behaviour, finding ids and printed text stay
byte-identical. The suite is the arbiter: ARCHITECTURE.md:464-535 says "A failing test after a
refactor means the refactor was wrong", and those phases hold themselves to that.

**P5 is the one deliberate behaviour change, and it is confined to names.** Commands get new
names and old names are retired with a pointer. A line that names a command (a usage, a `fix:`,
a hint) names the new one. Every other byte a command prints, and every exit code, stays as it
was. The only tests that change in P5 are the ones that pin a command name or spawn a module path.

## How the current state was measured

The Python language server (pyright 1.1.414, `pyright-langserver --stdio`) returned the
document symbols of all 60 modules under `src/jsk`: 1,082 top-level symbols. For each one it also
returned every reference. From those references came **463 module-to-module edges**. Folding
the edges to packages gives:

```
jsk.cli     -> jsk, cliutil, gates, graph, render, resume
jsk.gates   -> cliutil, graph, render, resume
jsk.graph   -> cli, cliutil, gates, paths, posting, resume        <- cli: outward
jsk.kb      -> cliutil, gates, graph
jsk.posting -> cliutil, graph
jsk.render  -> cli, cliutil, graph, paths, resume                 <- cli: outward
jsk.resume  -> cliutil, graph, render

cycles:  cli <-> graph   cli <-> render   gates <-> graph
         graph <-> posting   graph <-> resume   render <-> resume
```

Four Sonnet agents then classified the modules, one area each: graph core, graph features and
posting, render/resume/gates, and the CLI with the project's constraints. Every edge this spec
calls a violation was checked against the LSP reference data. The symbols named are the ones the
language server reported:

| edge | symbols (from LSP references) | why it points the wrong way |
|---|---|---|
| `render/render_resume.py` → `cli.py` | `frozen_refusal` | a guard lives in the adapter |
| `render/preview_templates.py` → `cli.py` | `frozen_refusal` | same |
| `graph/kbcli.py` → `cli.py` | `frozen_refusal`, `refused`, `unloaded_refusal` | same, plus a printer |
| `graph/store.py` → `gates/report.py` | `Report`, `Report.fail`, `Report.warn` | the record builds a gate report |
| `graph/named.py` → `graph/kbcli.py` | `WORD` | a query imports the CLI module |
| `graph/io.py` → `graph/store.py` | `rel` | io ↔ store cycle |
| `graph/rules.py` → `graph/store.py` | `graph_iri` | rules ↔ store cycle |
| `graph/match.py` → `gates/numbers.py` | `untraced` | gates ↔ graph cycle |
| `graph/kbcli.py` → `gates/check_ats.py` | `read_pdf` | the kb reads PDFs through a gate |
| `graph/export.py` → `resume/build.py` | `MAX_SKILLS_PER_ROW` | graph ↔ resume cycle |
| `resume/short.py` → `graph/kbcli.py` | `find_root` | resume ↔ graph through the CLI module |
| `graph/postingbuild.py` → `graph/kbcli.py` | `find_root` (:88, :156) | a use case imports the CLI module |
| `graph/postingbuild.py` ↔ `posting.py` | `POSTING`, `Refused` / `build`, `extract` | graph ↔ posting cycle |

The rest of this spec rests on four more facts:

- **pyoxigraph runs through the logic, not just the store.** 24 modules import it. Term
  `isinstance` tests alone number 11 in `changeset.py`, 8 in `edit.py`, and 4 each in `writer.py`
  and `shapes.py`. About 60 `store.select(SPARQL)` call sites sit in rules, named, edit, merge,
  pack, queries, select, match, postingbuild, timeline and the record/letter gates.
- **The `Store` wraps the engine, and `load` is I/O.** `Store.ox` (store.py:57) holds a live
  `pyoxigraph.Store`. `select`, `narrow`, `derive_types` and `materialise_paths` call it
  directly, and no module outside store.py touches `.ox`. `store.load` (:234) creates
  `ox.Store()`, reads career/store/ through `record_graphs`, and parses files. The LSP counts 79
  references to it, from render_resume, short, timeline, match, prepare, postingbuild, legacy, kb
  and 14 sites in kbcli. `graph_name` → `file_name` → `spelled` (:121-163) reads directories on
  purpose, to match how a folder is spelled on disk. `graph_iri` (:186) hands off to
  `db.graph_iri`.
- **`cli.py` is about 45% orchestration.** Its non-CLI parts are `store_report` :192, the
  refusals (:237-331, plus `frozen_refusal` :828 and `freeze_refusal` :1023), `gate_results`, `ship_fit` :841 and `cmd_ship` :912, and `freeze_write`
  :1230 with its `os.rename` rollback. `graph/kbcli.py` (1,478 lines) holds the use case of every
  `jsk kb` verb inside its `cmd_*` functions.
- **No import-boundary test exists.** "preflight is stdlib only" and "every module keeps
  pyoxigraph inside its functions" (ARCHITECTURE.md:174-176) are prose. The one precedent is
  `TextIsReadInOnePlace` (tests/test_plugin_surface.py:680), an `ast` walk with a path-keyed
  allow-list.

## Rulings

### Ruling 1. Five rings, as packages under `jsk/`

```
src/jsk/
  __init__.py  __main__.py  paths.py         stay: hatch version, `python -m jsk`, data anchor
  data/                                      stays (paths.SCHEMA_DIR, wheel, sdist)
  domain/
    naming.py        graph_iri (the body, not db's), name_of, short_name, app_graph, curie,
                     kind_of: string work only, no path touches the disk
    ontology.py      (from graph/)
    record/          state, store (the Store dataclass over a GraphEngine; narrow,
                     derive_types, materialise_paths), shapes, rules, changeset, edit,
                     merge, pack, decisions, writer, parsed, career, confirmation, provenance
    matching/        scoring, model, resolve, rank, cover, nearest, questions
    selection/       select
    assessment/      verdict, overlay (assessment.parse), derive, fold, triples
    posting/         boards, html_text, posting_md, build_rules, errors (Refused, POSTING)
    timeline/        events (event_quads, application_quads, submitted_day, when)
    resume/          plan (Builder), short (pure half), constants (PROVENANCE_RANK, ...)
    render/          formatting, themes, emit_text, emit_latex, fit_levers, page_report,
                     pdf_metadata (the one VARIANT_KEYWORD)
    gates/           report (Report), numbers, ats_rules, prose_rules, layout_rules
  ports/             record, queries, engine, codec, files, tex, pdf, posting_source,
                     profiles, clock, guards
  application/
    guards.py        frozen_refusal, unloaded_refusal, workspace_refusal (as data, not print)
    record/          load (store.load: repository + codec + engine, then the domain's
                     derive and rules), write (WriteLogged), apply, confirm, read verbs,
                     queries (named.py), pack, merge, store_status, scaffold (jsk new)
    tailor/          match_posting, check_gaps, draft_gaps, prepare, export, match_text
    posting/         fetch, extract, build
    timeline/        add_event, freeze
    render/          build_plan, load_resume, render_resume, fit_pages, preview_templates
    gates/           record, ats, prose, layout, letter, run_gates
    ship.py
  infra/
    oxigraph/        db (RocksDB, locks), engine, codec, queries, terms, backup
    files.py         read_text, atomic write, exclusive create, workspace walk, find_root,
                     graph_name, file_name, spelled, rel, inside (they read the disk)
    tex.py           (from render/tex.py)
    pdf.py           PyMuPdfInspector: every pymupdf call site, lazily imported
    posting_sources.py  urllib + docx
    profiles.py      the profile JSON under data/
    legacy_import.py (from graph/legacy.py)
  adapters/
    cli/             after P5, one module per noun (Ruling 10): main (the noun table and
                     RETIRED), doctor, kb (with `kb new`), posting, tailor, resume, letter,
                     app, plus dispatch (call_gate), presenters, cliutil. Through P4 they are
                     today's commands: kb (serving `jsk new` too), match, tailor, posting,
                     event, render, fit, preview, gates, ship, freeze
    mcp.py           when the MCP spec lands (Ruling 8)
```

`preflight.py` stays at `jsk/preflight.py` as an adapter (it runs processes and is stdlib-only by
design). From P5 it is reached only through `jsk doctor`. The tree follows the agents' proposals, with the names kept close to today's.
**The ring names are `domain`, `ports`, `application`, `infra` and `adapters`.** They are
settled for good, because `test_layers` and every import carry them.
**Why packages by ring first, subdomain second:** the dependency test in Ruling 7 has to map a
path to a ring with a prefix match, and a reviewer has to be able to tell the ring from the
import line.

This **supersedes ARCHITECTURE.md:376-404** ("a package must be justified by its members
importing each other more than outward"). A ring is justified by the direction of its
dependencies. Inside a ring, a subpackage still has to pass the old test. That also settles
the question ARCHITECTURE.md:391-398 left open about `gates/`: the rules move to `domain/gates`
and the runners to `application/gates`.

### Ruling 2. pyoxigraph *terms* are domain values; the pyoxigraph *Store* is not

The domain may import `NamedNode`, `Literal`, `BlankNode`, `Triple`, `Quad` and `DefaultGraph`
from pyoxigraph, and nothing else. It may not import `Store`, `parse`, `serialize` or any
RocksDB entry point. It still imports lazily, inside functions (Ruling 6).

**Why:** WHY.md:125-130 took pyoxigraph as the one required dependency because the graph "is the
career itself, not a capability layered on top". The terms carry no I/O. Replacing them with own
types would mean converting at every boundary in about 15 modules and in the test fixtures
(`tests/storekit.py`, `graphgen.py`), with nothing gained that the other rulings do not already
give. Every real violation (a store opened, a file read, a query run) is still removed.

**The domain's `Store` holds a `GraphEngine`, not a `pyoxigraph.Store`.** Today `Store.ox` is
the engine itself (store.py:57), and `store.load` creates it. After P3, the field holds a
`GraphEngine` that `infra/oxigraph/engine.py` implements over `pyoxigraph.Store`.
`narrow`, `derive_types` and `materialise_paths` call the port's `contains`/`remove`/`add`/`update`,
and stay in `domain/record/store.py`. `load` moves to `application/record/load.py`. It gets the
record graphs from `RecordRepository` (today's `record_graphs`), the parsed files from the
codec, and a fresh engine from a factory the handler passes in. Then it calls the domain's
tier-1 rules, `narrow`, `derive_types`, tier-2 rules and `materialise_paths` in today's order.
Findings and their order stay the same.

**Rejected for now, not forever:** own frozen term types in `domain/terms.py` with the same
attributes, converted in `infra/oxigraph/terms.py`. That is P7, and optional.

### Ruling 3. Validation rules stay SPARQL; read queries become port methods

There are two kinds of SPARQL here, and they are treated differently.

- **Rule text** (`rules.RULES` :494-658, the shapes' tier-2 checks) is the domain stating its
  invariants in its own language, the same way `ontology.py` states the schema as data. It stays
  in `domain/record/rules.py` and runs through a narrow **`GraphEngine`** port (`select`,
  `update`, `add`, `remove`, `contains`). `Store.select` keeps its signature and hands the call
  to `GraphEngine.select`, so the ~60 call sites inside the record's own logic (edit, merge,
  pack, rules, named) do not change.
- **Read queries used by features** (queries.py's ~17 selects, select.py :88/97/109, the gates'
  record, letter and numbers selects, `match.result`'s header, postingbuild, and
  `timeline.sent_versions`) move behind a semantic **`RecordQueries`** port: `paths_to(concept)`,
  `live_projects()`, `requirements(post)`, `metric_facts()`, `holdings()` and so on. The query
  text moves to `infra/oxigraph/queries.py`. queries.py already says "SPARQL finds the
  paths; Python assembles the answer". This makes the split explicit.
- **`named.py`'s queries are the exception** (`open_questions`, `holdings`, `experience_of`, and
  the rest). They move to `application/record/queries.py` and keep calling `Store.select` with
  their SPARQL. `@query` registers each one as a `jsk kb query` verb, so the query text is the
  verb. Behind `RecordQueries`, every verb would be split across the port, the adapter and the
  registry, and no second engine would benefit.

**Why not one port for both:** the graph-core agent proposed keeping every select behind
`GraphEngine`, and the features agent proposed moving them all behind semantic methods. Rule text
that tests assert by id is domain content, and moving it into an adapter would put invariants
outside the domain. A feature's ad hoc projection is storage knowledge (`GRAPH j:derived`, `FILTER
NOT EXISTS {?x j:retired}`). The counts-as closure that `j:derived` holds (`store.derive_types`
:335, `materialise_paths` :348) is a domain rule. It stays in `domain/record/store.py`, and the
adapter only runs it.

### Ruling 4. Module paths hold as thin entry points until P5; `jsk.cli` holds for good

`python -m jsk.<module>` is public today. SCRIPTS.md:8-9 documents it, `preflight.verify`
(:331-376) spawns it, and tests run it. Through P4 these paths keep working as **entry-point
modules**: `jsk.cli`, `jsk.kb`, `jsk.posting`, `jsk.preflight`,
`jsk.gates.{check_ats,check_prose,layout,letter,record}`,
`jsk.render.{render_resume,fit_pages,preview_templates}`, `jsk.resume.{short,build}` and
`jsk.graph.{kbcli,match,prepare,timeline}`. Each becomes a few lines that call its adapter's
`main(argv)`, and `cli.SUBPACKAGE` keeps naming them. P5 deletes all of them except `jsk.cli`
(Ruling 10). No skill, agent or doc under `plugins/` uses a module path. Only the
`jsk` command is taught.

`jsk.cli` stays for two reasons. `pyproject.toml:47` points the `jsk` console script at
`jsk.cli:main_console`, and `test_graph_queue.py:3` runs `python -m jsk.cli`. An install made
before the move keeps a launcher that imports `jsk.cli`, so `jsk.cli` keeps `main` and
`main_console` for good. `pyproject.toml` still points at it.

**`preflight`'s lists are a separate matter.** `GRAPH_MODULES`, `GATE_MODULES` and
`RENDER_MODULES` (preflight.py:51-66) name about 40 modules, most of them internal
(`graph.store`, `graph.io`, `render.themes`, ...), and `jsk doctor` reports any missing one as
broken. Those names are the shims that P6 deletes. So P0 changes the lists: each one names that
area's entry points and its new ring packages (`jsk.domain.record`, ...). They stop naming
individual internal modules. From then on, a move never changes what doctor checks. P5 drops the
entry points from the lists, leaving only the ring packages.

Every other old path (`jsk.graph.store`, `jsk.graph.ontology`, `jsk.render.themes`, ...) becomes a
**re-export shim** for the length of the migration: `from new.place import name`, never a copy.
About 40 of the 61 test files import `jsk.graph.*` internals (~138 import statements). The shims
let those imports keep working. P6 deletes them area by area and rewrites the test imports.
Changing an import path is not a behaviour change, so this stays within ARCHITECTURE.md's rule
about editing tests.

**A shim does not carry a `mock.patch`.** `mock.patch.object(render_resume, "compile_pdf", fake)`
rebinds the name in `render_resume`'s namespace. Code that moved looks `compile_pdf` up in its
new module and never sees the fake. The test then runs real TeX, or passes without testing
anything. Patching an attribute of an object (`db.Writer.close`) is unaffected. Module-global
patches are what break, and today's are:

| target | tests |
|---|---|
| `render_resume.compile_pdf` | test_ship_freeze :88, :350, :1023, :1297; test_record_gate :409 |
| `fit_pages.compile_pdf`, `fit_pages.available_engine` | test_ship_freeze :351-352 |
| `preview_templates.compile_pdf`, `.available_engine` | test_cli :730-732 |
| `posting.fetch_json` | test_posting :207 |
| `postingbuild.triples` | test_posting_build :491 |
| `record.write_graphs` (`R`) | test_posting_build :313 |
| `record.state` (`R`) | test_record_gate :191 |
| `db.replace_graphs`, `db.dump_text`, `db.update_text` | appkit :103, test_db :209, test_graph_record :107 |
| `"jsk.graph.select.select"` | test_graph_match :413 |

**The rule:** the commit that moves a patched function either leaves it where it is, or turns
every test that patches it into an injected fake of its port, in the same commit. It never
relies on the shim. P0's `PatchesHitTheDefiningModule` test (see P0) enforces this.

**Module-level singletons move, never duplicate:** `db._HELD/_WRITING/_LOCKER`, kbcli's
`VERBS/FLAGS` registry, `named.QUERIES` (filled by `@query` at import), and `SHIPPED_VOCABULARY`.

### Ruling 5. Use cases return results; the CLI is the only printer

Each application use case returns a frozen dataclass (`WriteOutcome`, `MatchReport`, `GateResult`,
`RenderResult`, `FitResult`, `ShipResult`, ...) and raises domain errors that carry `.fix`. The
adapters format them. The first result types copy today's shapes exactly: `match.result`'s dict
stays a dict in the first pass because `--json` and the tests pin it.

- **The text is byte-identical.** Presenters in `adapters/cli/presenters.py` reproduce today's
  lines, including hints that name files (`render_resume.py:335-339`). The existing suite plus a
  replay (see Verification) is the check.
- **The in-process contract holds** (ARCHITECTURE.md:121-126). `call_gate` (cli.py:455-493)
  moves to `adapters/cli/dispatch.py` unchanged. It keeps catching `SystemExit` and `Exception`
  and keeps capturing stdout, so a gate's output is still its own.
- **`summary_lines` goes** once `run_gates` returns `GateResult`s with counts, pages and fit
  state as fields.
- **The turn stays in the adapter.** `R.turn(root)` is taken in `main` before any read today, and
  the CLI adapter keeps wrapping the whole use case in it.

### Ruling 6. Lazy imports stay the convention; the composition root is per command

pyoxigraph, pymupdf and the heavy modules are imported inside functions (ARCHITECTURE.md:174-176;
ruff PLC0415 is ignored on purpose), and startup is budgeted (`tests/test_budget.py`,
`test_graph_budget.py`). Each command handler in `adapters/cli/` builds its own adapters inside
the handler function. There is no top-level container. `jsk --help` and `jsk kb path` must still
import no pyoxigraph.

pymupdf stays optional. `PyMuPdfInspector.available()` reports it missing. Each caller keeps its
own policy for a missing library (fit exits, render says "not measured", layout prints SKIPPED,
check_ats prints NO PDF LIBRARY, preview skips), and that policy lives in the use case or
presenter, not the adapter. Tests that set `sys.modules["pymupdf"] = None` (test_layout.py:233,
:243; test_graph_kbcli.py:402) keep working.

### Ruling 7. `tests/test_layers.py` enforces the rings

The test is stdlib `unittest` plus `ast`, so it runs on bare Python and in the sdist job.

1. It walks `src/jsk/**/*.py`, collects every `Import`/`ImportFrom` node **including the ones in
   function bodies**, resolves relative imports, and maps each module to a ring by path prefix.
2. It fails any edge from an inner ring to an outer one.
3. It checks the forbidden imports per ring:
   - `domain`: no import of `os`, `sys`, `subprocess`, `shutil`, `glob`, `tempfile`, `pathlib`
     or `urllib`, and no pyoxigraph beyond Ruling 2's names. `datetime` may be imported: the
     domain parses dates (`shapes.real_date` uses `date.fromisoformat`).
   - `ports`: stdlib `typing` / `dataclasses` only.
3a. It checks forbidden **calls and attributes** in `domain`. An import walk cannot see these,
   so the test also walks `Call` and `Attribute` nodes. It fails on a call to the builtin `open`,
   on `date.today`, `datetime.now` and `datetime.utcnow` (by attribute name, whatever the
   receiver), and on any `.ox` attribute or `record_graphs` name. The P3 "done when" is this check
   passing with nothing listed in `KNOWN` for the domain.
   - `preflight` and `mcp`: stdlib only.
   - `domain/ontology.py` and `domain/matching/scoring.py`: no pyoxigraph at all.
4. **`KNOWN`** is an allow-list of today's violations, each with its file and symbol. It may only
   shrink. An inverse test fails when a listed edge no longer exists, so the list cannot go stale.
   This is the `TextIsReadInOnePlace.ALLOWED` pattern.

`test_graph_ontology.py:88` (a subprocess check of the import cost) stays as it is. **pyright's CI
gate** (test.yml:106, today `src/jsk/graph` only) widens to `src/jsk/domain src/jsk/ports
src/jsk/application` in the same commit that creates them. Otherwise the type gate silently checks
nothing. import-linter is not added: it is a new dev dependency, and the sdist job only has what
`dev` installs.

### Ruling 8. MCP is a second driving adapter, and either spec may land first

The MCP spec dispatches through `cli.main(["jsk", *argv])` in process (its Ruling 3) and tests
that "`mcp.py` reaches jsk only through" the CLI. That makes it indifferent to everything inside
the CLI, so the two specs share no design and only a conflict surface: `cli.py`'s `HANDLERS` and
`NO_RECORD`, and `db.idle()`.

- **If MCP lands first,** Phase 1 here moves `jsk/mcp.py` to `jsk/adapters/mcp.py` together with
  `cli.py`.
- **If this lands first,** MCP adds `adapters/mcp.py`, and `db.idle()` goes in
  `infra/oxigraph/db.py`.

`test_layers` gains one rule either way: `adapters.mcp` may import `adapters.cli`, the stdlib,
and `infra.oxigraph.db`, and from `db` only `idle`. The MCP spec (its line 536) reaches
jsk through `cli.main` and `db.idle`. `idle` is a read-only check that no turn is held, run
after each call, and wrapping it in the CLI would only hide where it comes from. MCP must not
call use cases directly. That would grow the surface an agent names per noun, which is the
`okf` lesson (WHY.md:125-145).

**P5 renames verbs in MCP's tool table.** The MCP spec's four tools are split by authority
(read, draft, write, gate), and each admits a fixed set of verbs (its Ruling 4). The tools stay
the same. Their verb sets take Ruling 10's names: `match` becomes `tailor match`, `validate`
becomes `resume check <.json>`, `check` and `gates` become `resume check <render|dir>`, and
`fit` becomes `resume fit`. `resume check` now covers both the `read` tool (a `.json` target)
and the `gate` tool (a render or a directory). The **target kind decides the tool**, the same way
a flag already decides it for `kb pack` / `kb merge` / `fit`. The verbs MCP does not serve (`kb
new`, `app event`, `app freeze`, `kb confirm`, `kb load`, `kb dump`) stay unserved. Whichever
spec lands second makes this rename in `mcp.TOOLS` and its test.

### Ruling 9. The clock is read once, at the edge

`datetime.date.today()` is called 18 times. It is a default in named.py :112 and :149, match
:362, prepare :76, postingbuild :128 and :263, resume/build :375, gates/letter :171, gates/record
:238, kb.py :167, and timeline :497 and :594. kbcli calls it six times (:172, :256, :704, :885,
:1104, :1244). Most of these functions already take `today`, and it becomes a required
parameter. Each command handler reads the `Clock` port once and passes the date down.

`numbers.untraced(store, bullets, today=None)` takes `today` and never reads it
(numbers.py:80-120): a version counts as current while it has no `j:validUntil`. The parameter
is dropped when `untraced` moves in P1, not made required.

### Ruling 10. The CLI is `jsk <noun> <verb>`, and `jsk` is its only door

Today there are 15 top-level commands and, beside them, about 16 `python -m` module paths. The
commands overlap. `new` sits apart from `kb`. Tailoring is split across `match`, `tailor
prepare` and `kb export --from-match`. Four commands gate a resume (`validate`, `check`, `gates`,
`ship`). A cover letter is checked through `check --only letter`, a flag of a command about
something else. P5 replaces all of it with one grammar:

```
jsk doctor                                   what works on this machine
jsk kb       new | apply | confirm | show | view | query | export | check | log | path
             | load | dump | pack | merge    the career record
jsk posting  fetch URL APP | extract APP | build APP
jsk tailor   match APP | prepare APP         a posting against the record
jsk resume   check TARGET | render RESUME | preview RESUME | fit TEX | ship RESUME
jsk letter   check LETTER --record R         a cover letter beside its resume.json
jsk app      event APP KIND --date D | freeze APP --submitted D|false --channel T
```

Every old command maps to exactly one new one:

| today | after P5 |
|---|---|
| `jsk new PATH --name N` | `jsk kb new PATH --name N` |
| `jsk match APP` | `jsk tailor match APP` |
| `jsk validate RESUME.json` | `jsk resume check RESUME.json` |
| `jsk check PDF [--strict] [--only parse\|prose\|layout]` | `jsk resume check PDF [--strict] [--only ...]` |
| `jsk check LETTER --only letter --record R` | `jsk letter check LETTER --record R` |
| `jsk gates DIR [--record R] [--pages N] [--json]` | `jsk resume check DIR [--record R] [--pages N] [--json]` |
| `jsk render`, `jsk preview`, `jsk fit`, `jsk ship` | `jsk resume render`, `preview`, `fit`, `ship` |
| `jsk event`, `jsk freeze` | `jsk app event`, `jsk app freeze` |
| `jsk kb ...`, `jsk posting ...`, `jsk tailor prepare`, `jsk doctor` | unchanged |

**`jsk resume check` picks its gates from what it is given**, which folds three commands into
one. A `.json` file gets the record gate (today's `validate`). A `.pdf`, `.tex` or `.txt` render
gets parse and prose (today's `check`), and `--only` still narrows that to one gate. A directory
gets record, parse, prose and layout over the render inside it (today's `gates`). A flag that
does not fit the target, such as `--pages` on a `.json`, is a usage error (exit 2) that names
the target kind. The gates, their findings and their exit codes stay as they are.

**Flags do not change.** Each verb keeps today's flags, with today's meanings. P5 renames
commands, not options.

**Old names are retired, not aliased.** Each moved command joins `cli.RETIRED`, the pattern
`index` and `migrate` already use (cli.py:1274-1282). It exits 2 and names the replacement:
`jsk validate was retired: it is jsk resume check now. fix:  jsk resume check resume.json`. Old
`jsk check --only letter` gets a pointer to `jsk letter check`. None of them keeps running,
because two names for one thing is what this ruling removes.

**`jsk` is the only door.** P5 deletes the `python -m jsk.<module>` entry points. What stays is
`jsk` (the console script, still `jsk.cli:main_console`), `python -m jsk` for a machine where
the console script is not on PATH, and `jsk.cli` itself (Ruling 4). `python -m jsk doctor`
replaces `python -m jsk.preflight`. It still runs on a machine without pyoxigraph, because
`adapters/cli/main.py` imports each noun's handler inside the dispatch (Ruling 6), and
`test_budget.py` holds that. `preflight.verify` spawns `python -m jsk <noun> <verb> --help`
instead of each module. `cli.SUBPACKAGE`, `module_for`, `WHOLE_ARGV` and `run_in_process` go,
because dispatch calls the adapters directly. `call_gate` stays for the one job left to it:
running a gate in process with its stdout captured.

**Each noun is one adapter module.** `adapters/cli/` becomes `main` (the noun table and
`RETIRED`), `doctor`, `kb`, `posting`, `tailor`, `resume`, `letter`, `app`, plus `dispatch`,
`presenters` and `cliutil`. `jsk <noun> --help` lists that noun's verbs, and `jsk --help` lists
the nouns.

**Why:** an agent reading a skill sees one rule, "the noun is what you work on, the verb is what
you do to it", and the surface it has to learn shrinks to seven nouns. That is the `okf` lesson
(WHY.md:125-145) applied to the CLI. Ruling 8 covers what the new names mean for the MCP spec's
verb table.

### Ruling 11. No module over 600 lines, no function over 80, and a test says so

Two source modules pass 1,000 lines: `graph/kbcli.py` (1,478) and `cli.py` (1,338). The next is
`rules.py` at 683. So do three test files: `test_ship_freeze.py` (1,343), `test_graph_kbcli.py`
(1,193) and `test_cli.py` (1,067). The size lives in a few functions as much as in the files.
Seventeen functions run to 80 lines or more. Most of the longest are use cases fused with their
printing: `cli.cmd_freeze` (198), `check_ats.main` (180), `render_resume.main` (163) and
`kbcli.cmd_export` (162). The exception is `postingbuild.built` (190), which is logic.

**The two big modules split along the lines P4 already cuts,** so each P4 area takes its own
piece out of them, and no separate phase is needed. The line spans are those at `4768473`:

`graph/kbcli.py` (1,478) becomes the package `adapters/cli/kb/`, one module per group of verbs,
with the logic moving inward:

| today (kbcli.py lines) | adapter module | what moves inward |
|---|---|---|
| `VERBS`, `FLAGS`, `verb`, `usage`, `main` (:51-64, :82, :1432-1474) | `kb/__init__.py`: the verb table and dispatch, about 80 lines | nothing |
| `refuse`, `show_findings`, `GUIDE` (:88-114) | `presenters.py` | nothing |
| `writable`…`changeset_text`, `write_logged` (:117-221) | `kb/write.py`: `apply` | `application/record/write.py` (`WriteLogged`) |
| `cmd_pack`, `cmd_merge`, `drafted`, `draft_out`, `logged_base` (:270-401) | `kb/draft.py`: `pack`, `merge` | `application/record/{pack,merge}.py` |
| `cmd_confirm` and its helpers (:404-707) | `kb/confirm.py` | the word and number matching (`unquoted_numbers`, `unquoted_words`, `stems`, `quoted_answer`, `document_text`) goes to `domain/record/confirmation.py`, and `confirm_summary` to `application/record/confirm.py` |
| `cmd_show`, `cmd_view`, `cmd_query`, `cmd_log`, `cmd_path`, `cmd_check`, `untraced_lines` (:710-804, :985-1155, :1397-1429) | `kb/read.py` | `application/record/{read,check,store_status}.py` |
| `cmd_export` (:809-970, 162 lines) | `kb/export.py` | `application/tailor/export.py`, split into choosing the bullets and writing the file |
| `cmd_load`, `cmd_dump` and the import checks `provenances`…`edited_dump` (:1158-1393) | `kb/load.py` | `application/record/{load_import,dump}.py`, and the hand-edit detection to `domain/record/provenance.py` |
| today's `jsk/kb.py` (`jsk new`) | `kb/new.py` | `application/record/scaffold.py` |
| `find_root` (:67-79) | none | `infra/files.py` (P1) |

`cli.py` (1,338) becomes the noun adapters of Ruling 10:

| today (cli.py lines) | goes to |
|---|---|
| `main`, `main_console`, `usage`, `HELP_ENDS_BEFORE`, `RETIRED`, `HANDLERS`, `SIMPLE` (:61-75, :1274-1334) | `adapters/cli/main.py`, about 100 lines, and `jsk/cli.py` keeps a three-line `main_console` (Ruling 4) |
| `SUBPACKAGE`, `module_for`, `WHOLE_ARGV`, `run_in_process`, `call_gate` (:122-173, :455-493) | `adapters/cli/dispatch.py`. P5 deletes everything in it except `call_gate` |
| `cmd_doctor`, `store_report` (:176-234) | `adapters/cli/doctor.py`, with `store_report` going to `application/record/store_status.py` |
| the refusals: `unloaded_`, `workspace_`, `record_`, `view_`, `frozen_`, `freeze_refusal` | `application/guards.py` (P1), with `refused` in `presenters.py` |
| `cmd_validate`, `cmd_check`, `cmd_gates`, and the gate plumbing (:84-108, :332-740) | `adapters/cli/resume/check.py`, with `gate_results`, `rendered_documents`, `strict_for` and `render_section` going to `application/gates/run_gates.py` |
| `summary_lines` and its regexes (:745-801) | deleted (Ruling 5) |
| `cmd_ship`, `ship_fit`, `not_rendered` (:810-1002) | `adapters/cli/resume/ship.py`, with the orchestration going to `application/ship.py` |
| `cmd_freeze` (:1030-1227, 198 lines), `freeze_write` | `adapters/cli/app/freeze.py` for its flags, `application/timeline/freeze.py` split into check, plan and write, and the rename-and-rollback going to `infra/files.py` behind `ApplicationFiles` |

A noun with several verbs is a package (`adapters/cli/kb/`, `resume/`, `app/`). A noun with one
or two verbs is a module (`posting.py`, `tailor.py`, `letter.py`, `doctor.py`).

**The three big test files split to match,** each into files named for the adapter or use case
they test. Their shared fixtures go into kits, the way `appkit.py`, `storekit.py` and
`careerkit.py` already hold fixtures:

| today | becomes |
|---|---|
| `test_ship_freeze.py` (1,343) | `test_resume_ship.py` (`Ship*` classes), `test_app_freeze.py` (`Freeze*`, `Stale`, `Untouched`), `test_app_event.py` (`Event`, 178 lines). `fake_compile`, `margin_compile`, `ShipCase`, `GraphCase` and `ShortCase` go to `tests/shipkit.py` |
| `test_graph_kbcli.py` (1,193) | `tests/kb/`, one file per adapter module: `test_write` (`Apply`), `test_confirm` (`Confirm`, `ConfirmFromSource`, `ConfirmSummary`), `test_read` (`Show`, `View`, `Query`, `Similar`, `Check`, `KbPath`, `Log`), `test_load` (`Load`, 201 lines), `test_dispatch` (`Dispatch`, `UnknownFlags`). `Workspace` goes to `storekit.py` |
| `test_cli.py` (1,067) | `test_resume_check.py` (`ValidateRouting`, `Check`, `CheckOnly`, `Gates*`), `test_dispatch.py` (`Usage`, `InProcessDispatch`, `PreviewInProcess`, `ParseFlags`), `test_tailor_match.py` (`Match`), `test_doctor.py` (`DoctorStore`, `UnloadedWorkspace`) |

A test that moves file keeps its class, its name and its assertions. Only its import lines and
its file change, so the parity promise holds.

**The guard, `tests/test_sizes.py`:** an `ast` walk, stdlib only, like `test_layers`. It fails
any module under `src/jsk` over **600** lines, any test file over **800**, and any function over
**80**. `SIZE_KNOWN` lists today's offenders by file and function, with their lengths. An entry
may only shrink, and the inverse test fails an entry that is already under its limit, which is
the `KNOWN` pattern of Ruling 7.

- **Removed by this spec:** `kbcli.py`, `cli.py` and the three test files. So are the use-case
  functions that P4 splits anyway: `cmd_freeze`, `cmd_export`, `cmd_confirm`, `cmd_ship`,
  `cmd_load`, and the `main()` of `check_ats`, `render_resume`, `fit_pages` and
  `preview_templates`.
- **Left listed, for later:** `rules.py` (683, of which the rule text at :494-658 is 165 lines
  of SPARQL), `timeline.py` (608), and the functions `postingbuild.built` (190),
  `edit.apply` (143), `prepare.prepare` (124), `merge.draft` (101), `select.select` (97),
  `check_prose.check` (94), `shapes.tier1` (90) and `preflight.gather` (90). They are logic,
  not a use case fused with its printing, and splitting them is a refactor of its own. The
  guard keeps them from growing until one is done.

## Phases

Each step is one commit and passes on its own: the full suite, ruff, pyright, and `test_layers`
with a shrinking `KNOWN`. The areas inside a phase are independent of each other, so separate
agents can take them. Never two on the same commit (memory:
`never-commit-while-subagent-works`).

### P0. The guard, before anything moves

- Add `tests/test_layers.py` with the ring map and `KNOWN` holding today's edges. Today every
  module maps to a legacy ring by its current package: `graph/*` counts as "unsorted", and
  "unsorted" may import anything except the adapters.
- Make the path-keyed structure tests follow moves. `TextIsReadInOnePlace.ALLOWED`,
  `every_module_is_named` and the `OnlyDbKnowsTheStore` allow-list (tests/test_db.py:417) look
  modules up by dotted name through the shims, not by file path.
- Add `PatchesHitTheDefiningModule` (Ruling 4). It is an `ast` walk over `tests/` that resolves
  each `mock.patch.object(<jsk module>, "<name>")` and `mock.patch("jsk.<dotted>")`, then imports
  the target. Where the patched attribute is a function or class, the test asserts that its
  `__module__` is the patched module, so a patch aimed at a shim fails at once. Today every
  target listed in Ruling 4 passes. A planted patch on a shim in a scratch copy has to fail it.
- Change `preflight`'s module lists to the entry points plus the package names (Ruling 4).
  `test_preflight.py` follows.
- Add `tests/test_sizes.py` (Ruling 11), with `SIZE_KNOWN` holding today's oversized modules,
  test files and functions at today's lengths.

This commit moves no source module.

### P1. Break the six cycles without moving a module

Each of these creates a small new module or moves one symbol, and the old name re-exports it:

| cycle | fix |
|---|---|
| graph, render → cli | `frozen_refusal` and `unloaded_refusal` go to `application/guards.py` and return lines. `cli.refused` stays in the CLI and prints them. |
| graph ↔ gates | `Store.report()` becomes `gates.report.report_of(store)`. `Report` and the pure half of numbers (`numerals`, `covered`, `quoted`, `SCALE`, `Fault`, and a new `trace(facts, bullets)` holding `untraced`'s loop) go to `domain/gates/`. `untraced(store, bullets)` and `facts(store)` stay in `gates/numbers.py` as the thin half that runs the SPARQL. `untraced` becomes `trace(facts(store), bullets)`, and every caller keeps it. In P3, `facts` becomes `RecordQueries.metric_facts()`. `check_ats.read_pdf` goes to `infra/pdf.py`. |
| graph ↔ resume | `MAX_SKILLS_PER_ROW` and `PROVENANCE_RANK` (duplicated in kbcli :1158) go to `domain/resume/constants.py`. `find_root` goes to `infra/files.py`, which fixes short → kbcli and postingbuild → kbcli together. |
| graph ↔ posting | `Refused` and `POSTING` go to `domain/posting/errors.py`. |
| render ↔ resume | `formatting` and `themes` go to `domain/render/`. `profiles.load` goes behind `ports.profiles`. |
| within graph | `domain/naming.py` takes `graph_iri` (its body, and `db.graph_iri` then imports it from naming), `short_name`, `app_graph`, `curie` and `kind_of`. `graph_name`, `file_name`, `spelled`, `rel` and `inside` read the disk, so they go to `infra/files.py`. Together these break io↔store and rules↔store. |
| within graph, continued | `WORD` leaves kbcli. The match/gaps constants (`RANK`, `RAISE_FIX`, `question_line`, `cover_lines`, `ranking_lines`) go to `domain/assessment/verdict.py` and `application/tailor/match_text.py`. |

**Done when** the LSP dump (or `test_layers`) shows no package cycle. `KNOWN` has then lost every
`→ cli` and every cycle edge.

### P2. Move the pure leaves into `domain/`

Move the modules that already pass the domain rule, with shims: ontology, writer, shapes,
decisions.parse, changeset (logic), edit, merge, pack (logic), scoring, assessment.parse,
resume/career, emit_text, emit_latex, and the pure halves of io (`Parsed`, `normalise`),
record (`State`, `entry`, `stamp`, `prepared`), short, fit_pages, and the gate rule sets
(check_ats's body :184-302 is extracted from `main` first).

**`canonical_numbers` is not pure.** It asks Oxigraph how a number is stored by round-tripping
it through a fresh `ox.Store()` (io.py:107-130). It goes to `infra/oxigraph/codec.py`
in P3, and `GraphCodec` exposes it. Its domain caller, `changeset.numbers_as_kept` (:108-118,
reached from `changeset.parse`), takes the function as a `canonical=` parameter. The use case
passes the codec's version, and tests pass the same one. P2 moves changeset with that one edge
in `KNOWN`, and P3 removes it. The other caller, `legacy.py`, is already infra.

### P3. Ports and infra adapters

Create `ports/` and move the I/O behind it:

- `db.py` goes to `infra/oxigraph/db.py`.
- `record.turn/write_graphs/backup` goes behind `RecordRepository`, and so does
  `store.record_graphs`.
- `Store.ox` becomes a `GraphEngine`, and `store.load` moves to `application/record/load.py`
  (Ruling 2). Its 79 references first go through a shim, then each P4 area switches its own.
- `io.read_text/parse/parse_text` goes to `files.py` and `codec.py`, and `canonical_numbers` to
  `codec.py` (see P2).
- `render/tex.py` becomes the `TexCompiler` adapter.
- The seven pymupdf sites become `PdfInspector`.
- posting's urllib and docx code becomes `PostingSource`, built on the existing `fetch(get=)`
  seam.
- `timeline.write_document` (the tmp file plus `os.replace` retry) becomes `ApplicationFiles`.
- The three file-reading rules in rules.py (:164-193, :355-369, :372-401) get their text from an
  `AdvertSource`, with finding ids unchanged.
- The feature selects move into `infra/oxigraph/queries.py` behind `RecordQueries`
  (Ruling 3).

The patched functions in Ruling 4's table fall under Ruling 4's rule. When `render/tex.py`
becomes `TexCompiler`, the `compile_pdf`/`available_engine` patches in test_ship_freeze,
test_record_gate and test_cli become an injected fake `TexCompiler` in the same commit. The
same goes for `db.*` with `RecordRepository`, `posting.fetch_json` with `PostingSource`, and
`record.write_graphs`/`record.state`. Or the function stays where it is until its area's P4
commit. `PatchesHitTheDefiningModule` fails any commit that does neither.

**Done when** no module under `jsk.domain` references `.ox`, `glob`, `os.listdir` or
`record_graphs`, and `KNOWN` lists no domain entry. `test_layers` (Ruling 7, 3a) asserts this,
so it keeps holding after P3.

### P4. Use cases, one area per agent

Every `main()` splits into an adapter that parses flags and prints, and a use case that returns a
result (Ruling 5). Each area takes its rows out of Ruling 11's two tables, so `cli.py` and
`kbcli.py` shrink with every area and are down to their dispatch by the end of P4. An area is done
when its functions and modules have left `SIZE_KNOWN`. Each area is one agent and a series of
commits:

1. **render**: `build_plan`, `load_resume`, `render_resume`, `fit_pages`, `preview_templates`.
   Preview calls the use case rather than capturing `render_resume.main`'s stdout
   (preview_templates.py:39).
2. **gates**: record, ats, prose, layout and letter, plus `run_gates`. `cli.summary_lines` retires.
3. **tailor and posting**: match, gaps build and draft, prepare, export, and posting
   fetch/extract/build. The `--cover` / `--today` parsing, done three times today, becomes one
   options type in the adapter.
4. **kb**, verb by verb: read-only verbs first (path, log, view, show, check, dump), then export,
   then pack and merge, then the writing verbs (apply, confirm, load) through one `WriteLogged`
   use case. kbcli.py shrinks to `adapters/cli/kb.py`. Today's `jsk/kb.py` (`jsk new`) joins
   it there as one more handler, and its scaffold becomes the `application/record/scaffold`
   use case. It writes through the same `RecordRepository` gate as every `jsk kb` write, as it
   already does through `record.write_graphs`. One module now answers to "kb". The commands
   don't change yet: `jsk new` stays `jsk new` until P5 makes it `jsk kb new`, and `cli.SIMPLE`'s
   `"new"` and `"kb"` entries point at the same adapter.
5. **timeline and ship**: `add_event` and `freeze`, with `freeze_write`'s rename-and-rollback
   behind `ApplicationFiles`. Then `ship.py` composes them.

### P5. The CLI becomes `jsk <noun> <verb>` (Ruling 10)

This is the one phase that changes behaviour, and only in names. Order of commits:

1. **The noun table.** `adapters/cli/main.py` dispatches `jsk <noun> <verb>` to the seven noun
   adapters. `RETIRED` gains every moved command with its replacement. `jsk --help` and
   `jsk <noun> --help` print the new grammar. `HELP_ENDS_BEFORE` and its test follow.
2. **`resume check` by target kind.** It takes one target and chooses the record gate, parse and
   prose, or all four. It rejects a flag that does not fit the target. `letter check` is split
   out of `--only letter`.
3. **The module paths go.** Ruling 4's entry points are deleted, apart from `jsk.cli`. So are
   `SUBPACKAGE`, `module_for`, `WHOLE_ARGV` and `run_in_process`. `preflight.verify` spawns
   `python -m jsk <noun> <verb> --help`. `preflight`'s lists keep only the ring packages.
4. **The text that names commands.** Every usage line, `fix:` line and hint in `src/` that names
   a moved command now names the new one. Nothing else in the output changes.
5. **Skills and docs.** About 750 mentions under `plugins/`, `README.md` and `docs/*.md` move to
   the new names. SCRIPTS.md stops documenting module paths and becomes the reference for
   `jsk <noun> <verb>`. `RetiredNamesAreNotTaught` (see Tests) fails any mention left behind.
6. **The tests that pin a name.** They are rewritten in the same commit as the change they pin,
   and in no other. Tests that spawn `python -m jsk.<module>` spawn `python -m jsk <noun> <verb>`
   instead.

Steps 1-4 are sequential, because all of them touch `adapters/cli/main.py`. Step 5 can go to
parallel agents, one per plugin directory, once step 4 has landed.

**Done when** `jsk --help` prints the seven nouns and `doctor`, every retired name exits 2 with
its replacement, no `python -m jsk.<module>` path except `jsk.cli` imports, and
`RetiredNamesAreNotTaught` passes. The replay (Verification) also passes: each old command's
output, run under its new name, is byte-identical apart from lines that name a command.

### P6. Retire the shims

One commit per area (render, gates, tailor and posting, kb, timeline and ship). Each commit
rewrites that area's test imports to the new paths, deletes its non-public shims (P5 already
deleted the entry points), and removes its entries from `KNOWN`. The same commit splits that
area's share of the three big test files (Ruling 11's third table) and moves their fixtures into
the kits. The split is a move: no assertion changes. The last area's commit takes the three
files off `SIZE_KNOWN`. No module-attribute patch is left to
convert by now. Each one became a fake when its target moved (Ruling 4). `KNOWN` becomes empty only in the last commit. Until then every entry
still in it names an edge that really exists, and the inverse test checks that. The last
commit also updates ARCHITECTURE.md: the module list that `every_module_is_named` checks, the
dispatcher line at :294, and the replaced package rule at :376-404. SCRIPTS.md and `preflight`'s
lists already changed in P0 and P5.

### P7. Optional: own term types

Only if a reason appears (a second engine, or a domain test that should not need pyoxigraph).
Ruling 2's alternative.

## Tests

- **`tests/test_layers.py`** (Ruling 7): the ring rule, the per-ring forbidden imports, the
  domain's forbidden calls and attributes, and `KNOWN` with its inverse. It also covers MCP's rule
  once `adapters/mcp.py` exists.
- **`PatchesHitTheDefiningModule`** (P0, Ruling 4): every `mock.patch` of a jsk module-global
  names the module that defines it.
- **`tests/test_sizes.py`** (P0, Ruling 11): modules at most 600 lines, test files at most 800,
  functions at most 80, and `SIZE_KNOWN` with its inverse. A planted 81-line function in a
  scratch copy has to fail it.
- **The test split loses nothing** (P6): the test ids that `pytest --collect-only -q` reports
  before and after each split are the same set, apart from the module part of each id.
- **Entry points:** through P4, one spawn per Ruling 4 entry point, `jsk.cli` included, each
  asserting that `--help` or its usage exits as it does today. From P5, one spawn per noun-verb
  pair (`python -m jsk <noun> <verb> --help`), plus `jsk.cli:main_console`.
- **The grammar (P5):** every row of Ruling 10's mapping table is a test. The old command exits
  2 and names the new one, and the new one runs. `resume check` gets one test per target kind,
  and one per flag that does not fit a target.
- **`RetiredNamesAreNotTaught` (P5):** a walk over `plugins/`, `README.md`, `docs/*.md` and the
  strings in `src/` that fails on any `jsk <retired>` and any `python -m jsk.<module>`, with an
  allow-list for the `RETIRED` table itself and the history in `docs/superpowers/`. A planted
  `jsk validate` in a scratch copy of a skill has to fail it.
- **Parity:** the existing suite unchanged through P0-P4. It pins finding ids, printed text, exit
  codes, `cli.SIMPLE`/`HANDLERS`/`HELP_ENDS_BEFORE`, `--json` shapes, and `python -m` spawns. In
  P5 a test changes only where it pins a command name or a module path.
- **Import cost:** `test_budget.py` and `test_graph_budget.py` unchanged. Add one assertion that
  `import jsk.adapters.cli` loads no pyoxigraph.
- **Per-use-case unit tests with fake ports** land with each P4 area. They add to the parity
  suite and replace none of it.
- **Doctor:** `test_preflight.py` plus a run of `jsk doctor` on a bare venv (no pymupdf) after
  P3, after P5 (as `python -m jsk doctor` too, with no pyoxigraph installed), and after P6.

## Risks

- **Moving a module breaks `jsk doctor` on real machines.** `preflight`'s lists name about 40
  internal modules today, and doctor reports any missing one as broken. P0 cuts the lists down to
  the entry points and ring packages, P5 down to the ring packages alone, and a test spawns each
  noun-verb pair.
- **A skill still teaches an old name.** An agent that runs `jsk validate` gets exit 2 and a
  pointer, not a wrong result, so the failure is loud. `RetiredNamesAreNotTaught` catches the
  mention before release, including in agent definitions and mode files.
- **Someone's script calls `python -m jsk.gates.check_ats`.** It breaks with P5, on purpose.
  The module no longer exists, and there is no pointer, because only `jsk` can print one. The
  release notes name the replacement for each module path. No skill or doc in this repo uses
  them.
- **Bootstrapping without pyoxigraph.** `python -m jsk.preflight` ran on a bare machine. Its
  replacement, `python -m jsk doctor`, has to as well. Ruling 6's lazy dispatch and
  `test_budget.py` hold it, and Doctor (Tests) runs it on a venv without pyoxigraph.
- **A stale `jsk` launcher.** An install made before the move has a console script that imports
  `jsk.cli:main_console`. Ruling 4 keeps `jsk.cli` as an entry point for good.
- **A lazy import hides an outward edge.** All four `→ cli` edges are lazy today. `test_layers`
  reads function bodies. A lint that only reads top-level imports would pass them.
- **A patch lands on a shim**, and a test runs real TeX or passes without testing anything. A
  shim re-exports the object, but `mock.patch.object(old_module, "fn")` rebinds only the old
  module's name, and moved code never looks there. Re-exporting cannot fix this. Ruling 4's rule
  can (move the function and its fakes together), and `PatchesHitTheDefiningModule` enforces it.
- **A "pure" function hides an engine.** `canonical_numbers` round-trips through `ox.Store()`,
  and `graph_name` lists directories. `test_layers`' call and attribute check (Ruling 7, 3a)
  catches the next one the moment it enters `domain/`.
- **A guard test encodes the hole** (memory: `guard-tests-can-encode-the-hole`). Read
  `test_layers`'s own fixtures: a planted outward import in a scratch copy has to fail it.
- **Text drift when printing moves to presenters.** Parity tests catch what they pin. The replay
  below catches what they don't.
- **Two agents in one file.** kbcli.py and cli.py are touched by several P1 fixes. P1 runs
  sequentially. P4's areas all take pieces out of those same two files (Ruling 11), so P4
  areas run in parallel only in separate worktrees, reset to `HEAD` first (memory:
  `worktree-isolation-bases-on-main`). They merge one at a time, and the removal of each area's
  rows from `cli.py` and `kbcli.py` is the conflict to expect.
- **A test lost in a split.** Moving 3,600 lines of tests by hand can drop a class. The
  collect-only comparison (Tests) catches it.
- **The MCP spec lands in between** and touches `cli.py` and `db.py`. Ruling 8 sets out both
  orders.

## Verification (after P1, P4, P5 and P6)

1. `pytest tests -n auto`, `ruff check`, and `pyright` on the widened paths.
2. **Re-run the LSP dump** used in "How the current state was measured". Expect zero package
   cycles, and every edge pointing inward by the ring map.
3. **Replay the real workspace** (`C:\Projects\basilin-joe-resume\career`) **on a scratch copy
   only**: `jsk doctor`, `jsk kb check`, `jsk match`, `jsk tailor prepare`, `jsk ship`, and
   `jsk gates`. Diff stdout and exit codes against the same commands at `4768473`. The expected
   diff is empty. From P5 on, run each command under its new name (`jsk tailor match`, `jsk
   resume ship`, `jsk resume check DIR`). The expected diff is then only the lines that name a
   command.
4. `jsk doctor` in a venv with only the required dependency installed.

## Open questions

None. Every question the first draft raised is settled in a ruling or a phase.

## As built

What the implementation did differently from the rulings above, and why. Everything not
listed here was built as written.

**The old paths during the migration (Ruling 4).** A module that moved whole left an alias at
its old path - `sys.modules[__name__] = <the moved module>` - not a `from new import name`
re-export. The old path and the new one were then the same module object, so a test's
`mock.patch.object(old_module, "fn")` patched the code where it ran, and the patch problem
Ruling 4 describes could not arise for a whole move. A module that split kept its old path as a
binding module: it re-exported the moved names and kept today's signatures, passing the real
ports in. test_layers ignores aliases and fails any source module that imports through one, so
only the tests used old paths. P6 deleted both kinds.

**The patch guard (P0).** "Assert the patched attribute's `__module__` is the patched module"
fails on today's own working patches: `preview_templates` calls `compile_pdf` through its own
namespace though `tex` defines it. tests/test_patches.py checks what a patch needs instead -
that some code looks the name up through the patched module at call time (a bare name inside
it, `module.name` elsewhere, or a `from module import name` run inside a function).

**P1's cuts.** Three things the package view missed:
- kbcli.py was the cause of three of the six cycles (graph -> cli, gates, resume). It moved whole
  to adapters/cli/kb.py first, and P4 split it into the adapters/cli/kb/ package.
- `show` prints, so it went to cliutil with the adapters, not to domain/gates/report.py with
  `Report`.
- numbers.py split into the comparison (domain/gates/numbers.py, a new `trace(facts, bullets)`)
  and the career read (application/gates/numbers.py), so the domain never held SPARQL.

**Rings and rules (Ruling 7).**
- The domain may import `urllib.parse`: quoting a graph name for an IRI is string work.
- A port may import `datetime`: the Clock names a date.
- Until P6, the cycle check ran over the unsorted packages only, because a ring cannot sit in a
  cycle without an outward edge, which is failed on its own. Once every module sat in a ring,
  P6 deleted the check and KNOWN_CYCLES rather than keep an empty set: the outward-edge check
  already fails a cycle between rings. Five cycles between subpackages of a single ring remain
  and are not guarded: adapters.cli and jsk.cli, application.gates and application.record,
  domain.record and domain.resume, infra.files and infra.oxigraph, infra.legacy_import and
  infra.workspace.
- The test split kept flat file names (`test_kb_write.py`, not `tests/kb/`), because
  test_patches reads only `tests/*.py` and a subdirectory's patches would have gone unchecked.

**More ports than Ruling 1 listed.** WorkspaceSource (what a load reads), AdvertSource (the
tier-2 rules' posting.md and decisions.txt), RenderOutputs (a render's files and scratch
directories) and ApplicationRecords (an application's stored graphs) each came out of a module
that turned out to read the disk.

**The composition root (Ruling 6).** No top-level container, as ruled. The bindings the old paths
held - the real store, engine, queries and TeX compiler handed to each use case - became
adapters/cli/compose/, one module per area. A module per area rather than per command keeps a
binding shared by three commands in one place. render, fit and preview each have their own,
because a test that patches the render's compile_pdf must not patch the fit's.

**The clock (Ruling 9).** No Clock implementation was written. Each adapter calls
`datetime.date.today()` once, at the edge, and passes the day down. A one-method infra class
would have added nothing. `today` also came off `untraced` and off every helper that only
passed it on, `record.check.check` among them. The record queries that need a date are
marked `dated=True` and take it from the kb adapter.

**P5's grammar (Ruling 10).**
- `resume check` decides by target kind as follows:
  - a directory, or a nameless path with no extension, gets all four gates;
  - a `.json`, `.md` or `.ttl` gets the record gate, so a kb.ttl or user-knowledgebase.md still
    gets its `jsk kb check` pointer;
  - anything else is a render.
- A flag that does not fit the target is exit 2. So `--json` on a render, which the old `jsk check`
  ignored, is now an error.
- A retired name prints two lines (`it is X now.`, then `fix:  X args`), the style `index` and
  `migrate` already used.
- Between P5 and P6, each `python -m jsk.<module>` path printed one line naming its replacement
  and exited 2, where a bare removal of its main block would have exited 0 having done nothing.
  P6 deleted the modules, and they now fail with "No module named". Only `jsk.cli` and
  `python -m jsk` remain.
- The changes a person sees beyond names:
  - doctor's `modules (n/n)` line, and its package detail paths, which now name the rings;
  - a new record's first log entry says "Created by jsk kb new";
  - hints that named a script (`run fit_pages.py`) name the command.

**Dispatch (Ruling 10).** SUBPACKAGE is gone; adapters/cli/dispatch.py maps each command's
script name to its adapter (ADAPTERS) and still imports it by name through call_gate. Two
tests pin call_gate's containment of an adapter that cannot be imported or that raises,
which a direct call would not exercise.

**`jsk tailor prepare`.** It now collects every section before printing. On a crash
mid-digest, the sections before the crash are no longer printed above the traceback. No
normal path's output changed.

**Ruling 11's "left for later".** Five functions stay over 80 lines and listed in SIZE_KNOWN:
`edit.apply` (143), `merge.draft` (101), `select.select` (97), `shapes.tier1` (90) and
`preflight.gather` (90). The others the ruling named left SIZE_KNOWN on the way:
`postingbuild.built` and `prepare.prepare` split in P4, and `rules.py` and `timeline.py`
split in P3.

**How it was built.** P2 onward ran as parallel agents, each in its own git worktree, each
area's branch merged one at a time. Each agent replayed its commands against the code before
its change and reported every difference; those reports are where the departures above were
caught.
