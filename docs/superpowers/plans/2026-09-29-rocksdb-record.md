# The record in RocksDB - implementation plan

**Spec:** none. This plan and its Rulings are the spec. The decision is the user's (2026-09-29):
the career record stops being Turtle files and lives in a persistent Oxigraph store (RocksDB),
read and written only through jsk. Git history, diffs, hand edits and plain text as the record
were each weighed and explicitly declined as requirements; this plan does not reopen them.

**Out of scope, next plan:** the MCP server (`jsk mcp`). It is a thin layer over the functions
this plan leaves behind, and it is planned after this one ships green so that a failure can be
blamed on one change, not two.

## Context

### What changes

Today every command parses `career/kb.ttl`, `career/log.ttl` and every
`applications/*/{posting,application,gaps}.ttl` into an in-memory `pyoxigraph.Store`
(`graph/store.py:load`), derives types and paths, runs every rule, and answers. Every write
builds the new file text, re-runs `load(root, texts={...})` over it to validate it, and then
`record.commit` stages and renames two files, with hash, shadow copy and torn/hand-edited
detection to cover what two renames cannot make atomic.

After this plan the same records are named graphs in one RocksDB store at `career/store/`.
A command opens it, copies the record graphs into the same in-memory store it builds today,
and everything downstream of `load()` - `rules.py`, `queries.py`, `match.py`, `select.py`,
`timeline.py`, the resume builder, the gates - is unchanged. A write is one SPARQL update:
every graph it touches changes, or none does.

### What was measured (pyoxigraph 0.5.11, Windows 11, this machine)

Run from the session scratchpad (`probe.py`, `db_sketch.py`) before this plan was written.

| Property | Result |
|---|---|
| Second `Store(path)` while a writer holds it | `OSError: ... LOCK: The process cannot access the file` - at once |
| `Store.read_only(path)` while a writer holds it | Works; sees committed data |
| Writer after the first process closes | Works |
| Multi-operation `update()` whose second op fails at run time (`CLEAR GRAPH` of a missing graph) | Raises; first op rolled back |
| Multi-graph `DROP` + `INSERT DATA` built from `str(term)` | Round-trips `"`, `\`, `\n`, tab, `é`, emoji, `}}`, `;.` exactly |
| `read_only` open + count, 16k quads | 44 ms |
| Copy 16k quads into an in-memory store | 130 ms |
| Writer open | 74 ms |
| TriG dump, 16k quads | 650 KB |
| **Typed literals** | **`"8.40"^^xsd:decimal` -> `8.4`; `"007"^^xsd:integer` -> `7`; `"1.0E3"^^xsd:double` -> `1000`.** Strings, dates, language tags unchanged |

The last row matters: `store.graph()` exists today *because* Oxigraph keeps numbers by value
(`store.py:57-58`). Metric `value`, `baseline` and `upper` are `xsd:decimal` claims
(`ontology.py:247-249`) and `gradeValue` may be one (`:273`). Once the store is the record there
is no parsed text to fall back on. Ruling 4 settles it.

## Rulings

1. **Validate on every load, as today.** No hand edits means the store can only hold what
   passed - but a new release's rules and vocabulary must still reach an old record, and loading
   is where they do. The 1.2 s budget in `tests/test_graph_budget.py` stays and now includes the
   copy out of RocksDB.
2. **One store per workspace, at `career/store/`.** Named graphs, IRIs under
   `tag:jsk,2026:graph/`: `kb`, `log`, `applications/<stem>/posting`,
   `applications/<stem>/application`, `applications/<stem>/gaps`. Findings name the graph by that
   short name (`kb`, `applications/acme-sre/posting`) and the entry by id; line numbers go.
   `store.file_name`/`graph_iri(file)` become graph names; the `file:` IRI scheme goes.
3. **The shipped vocabulary stays a file in the package** (`src/jsk/data/vocabulary.ttl`). It is
   code, not the record: it is loaded into the in-memory store each command, never persisted, so
   a release updates it. `narrow` (kb's `unlabel`/`unlink`) works on it exactly as now.
4. **Numbers are stored by value, and nothing is changed silently.** A new tier-1 rule,
   `non-canonical-number`, FAILs an integer or decimal whose lexical form Oxigraph would rewrite
   (`8.40`, `007`, `+3`), with the fix `write 8.4`. It runs on changesets, posting builds and
   `kb load` input - everything that still arrives as text. A grade whose zeros matter (`3.80`) is
   written as a string, which `gradeValue` already allows; the fix says so. The one-time import
   (Ruling 9) rewrites to canonical numbers and reports each one it rewrote.
5. **Turtle/TriG stays as input, never as storage.** Changesets (`changes/*.trig`) and
   `jsk kb load` dumps are read and parsed as today; nothing jsk writes to the record is a
   `.ttl` file. `posting.md`, `decisions.txt`, `gaps.txt`, `gaps.md`, `resume.json` and renders
   stay files in `applications/<stem>/`: they are documents, not the record.
6. **A write is one `update()`.** `db.replace_graphs` drops and re-inserts each touched graph in a
   single SPARQL update (measured atomic above). Revision and log entry go in the same update as
   the change. `op:base` stays: it is what refuses a changeset drafted against an older revision.
7. **Writers queue; nobody is refused for being second.** Readers open `read_only` and never
   wait. A write reads, builds and validates its candidate from a `read_only` snapshot, closes
   it, then takes its **turn**: a blocking OS lock on `career/store.lock` (`LockFileEx` on
   Windows, `flock` elsewhere; stdlib + ctypes, no package). The OS queues the waiters; a
   writer not granted at once prints "waiting for another jsk write to finish" and blocks.
   Inside its turn it opens the RocksDB writer, writes, and closes it before giving the turn
   up, so RocksDB's own LOCK is never contended. A process that dies holding the turn releases
   it with its handle. Measured in the scratchpad (`qlock.py`): four writers started 0.3 s apart,
   each holding 1 s, were granted in arrival order exactly 1.00 s apart; a holder killed
   mid-turn let the next in at once.
   **Rebase, not refuse, when the revision moved - and that is already `edit.py`.**
   `edit.apply` always applies to the *current* record, and `edit.base_conflicts` refuses only
   when a log entry after `op:base` touched or minted an id the changeset names. So under its
   turn a writer re-reads the revision: unchanged, it writes what it validated; moved (another
   write landed while it waited), it reloads and runs the same `edit.apply` + every rule again,
   inside its turn, then writes or refuses exactly as a fresh `apply` would. No new rebase
   code - one more call of the existing path, only on contention. The re-run rules catch the
   clashes that share no id (both minting one id, citing an entry the other retired). No long-running owner process
   (Oxigraph server, a session-long MCP handle): it would make the CLI and every other session
   route through it.
8. **Backup: `jsk kb dump` and `jsk kb load`, plus one automatic dump.** `dump` writes the record
   graphs as TriG (no derived graph, no vocabulary). `load` fills an *empty* store from one and
   refuses a non-empty store. After every successful write jsk overwrites `.jsk/backup.trig`
   (best effort, never read except by `load`): the store's format is tied to the pyoxigraph
   version, and this is what survives a pin bump or a corrupt store. Overrule this ruling to drop
   the automatic dump; `dump`/`load` stay either way.
9. **The Turtle workspace is imported, once, by `jsk kb load`.** `jsk migrate` (Markdown) is
   already gone (7cae43c), and real records exist as files - `C:\Projects\basilin-joe-resume\career`
   holds `career/kb.ttl`. So `jsk kb load` takes either a TriG dump or a workspace still laid out
   as files: it runs today's file loader over them (so they are validated exactly as now), refuses
   on any FAIL, rewrites non-canonical numbers (Ruling 4) with a line per rewrite, and fills an
   empty store in one update. The files are left where they are; `jsk` stops reading them and
   says so once (`career/kb.ttl is no longer read - the record is career/store/`). The file
   loader survives only as this importer's front end, and is deleted in release N+1 with it.
10. **Gone:** `jsk kb adopt`, `jsk kb fmt`, the `hand-edited`/`torn`/`out-of-sync`/`unlogged`
    states, `kbSha256`, `.jsk/kb.last.ttl`, `record.replace/staged/commit/shadow`, the canonical
    layout rules in `writer.py`, `jsk kb path`'s file lines. **New:** `jsk kb log [--last N]`
    (the agents that read `log.ttl` directly need it), `jsk kb dump`, `jsk kb load`.
11. **Commands that took a `.ttl` path take the application.** `jsk match APP`,
    `jsk kb export --from-match APP`, as `jsk posting build APP` and `jsk freeze APP` already do.
    A path ending `posting.ttl` is refused with the new form in the fix.
12. **`kb show` still prints Turtle.** It is how agents read entries and draft changesets, so it
    keeps printing entries in the familiar shape. What survives of `writer.py` is the printer
    that does that (subject blocks, `"""` prose), not the whole-file layout.
13. **Storage in one module, writes through one function; queries stay where they are.**
    `db.py` is the only code that knows the record is RocksDB: nothing else calls
    `pyoxigraph.Store(path)`, `Store.read_only` or updates the on-disk store. Every write goes
    through `record.commit` (turn, revision, rebase, log entry, `db.replace_graphs`, backup) -
    one gate, so no write can skip the log, the lock or the rules. The SPARQL queries are not
    storage access - they ask a validated in-memory `Store` about a career - and stay grouped by
    purpose (`queries`, `named`, `match`, `rules`); one CRUD module would couple every feature
    to storage and make nothing safer, since a read cannot hurt the record. A test (P1, beside
    `test_plugin_surface.py`) fails when a module other than `db.py` opens a store on disk or
    one other than `record.py` calls `db.replace_graphs`. The same layering makes `jsk mcp`
    (next plan) a sibling of `kbcli.py` over the same functions.

### Amendments made while building (2026-09-29)

- **The turn is taken before the command reads, not after it validates (Ruling 7).** A
  writing command runs whole inside its turn (`record.turn`, re-entrant), reading the store
  read-only as usual - nothing else can write while it is held. So a write queued behind
  another always loads, validates and applies to what that one left, and "the revision moved,
  reload" needs no code of its own: `edit.apply` and `base_conflicts` already do the rest.
  The price is a turn held for a command's whole run (well under a second on a real career)
  rather than ~100 ms; readers still never wait.
- **Readers do wait - for one write, not a command (Ruling 7's "readers never wait" was
  wrong).** pyoxigraph documents a read-only open while another process writes as undefined
  behaviour, and on Windows it is concrete: the reader's handle on CURRENT makes the writer's
  rename fail. A second lock, `career/store.access`, is held shared by every read and
  exclusively by a write for its open-update-close only, so a reader waits at most one
  write's worth (9d39cea; the race test in `tests/test_db.py` fails without it).
- **The RocksDB handle never leaves db.py.** pyoxigraph has no `close()`; a store closes
  when its last reference goes. Writers get a `db.Writer` that drops its store on leaving
  `db.writing`, so a caller's variable cannot keep RocksDB's lock past the turn.
- **`Parsed` stays the per-graph container** (`Store.parsed`, not a new `Store.graphs`): a
  stored graph is a `Parsed` with triples and no text, so tier 1 and every caller work
  unchanged. `kbSha256` stays (Ruling 10 listed it as gone): it is the hash of the career as
  the writer lays it out - the diff's text - and the ontology requires it.
- **Ruling 4's check lives in `changeset.py` (`numbers_as_kept`)**, where the plan's P3
  note put it, not as a tier-1 rule id: tier 1 also runs on the file workspace the import
  reads, and there the numbers are rewritten and reported, not refused.
- **A transitional dual mode.** A workspace without `career/store/` loads from its files
  until every area is converted; graphs take their short names in both modes. The final
  pass removes the file mode everywhere but the importer.

## Architecture

```
src/jsk/graph/db.py        NEW   the store on disk: open_reader, open_writer (lock retry), graph
                                 names <-> IRIs, graphs(db) -> {name: triples},
                                 replace_graphs(db, {name: triples|None}), dump, load
src/jsk/graph/store.py     load(root, graphs=None): record graphs from db (or `graphs`, the
                                 candidate a write validates) + vocabulary file -> in-memory
                                 store; narrow, derive, rules, paths as now
src/jsk/graph/record.py    revision + log entry only: state() is clean | missing | empty;
                                 prepare() returns {name: triples}; commit() -> db.replace_graphs
src/jsk/graph/io.py        parse_text stays (changesets, dumps, vocabulary); parse(path) of
                                 record files goes
src/jsk/graph/writer.py    shrinks to the entry printer kb show / pack / merge use
```

The seam every write already has - `S.load(root, texts={file: text})` then `R.commit` - becomes
`S.load(root, graphs={name: triples})` then `R.commit(root, {name: triples})`. There are nine
such call sites (`kbcli.py:167`, `kb.py:175`, `timeline.py:296`, `:451`, and the posting/gaps
builders); each changes in the same way.

`db.py`'s core, as run in the scratchpad (`db_sketch.py`, all checks passed):

```python
GRAPH = "tag:jsk,2026:graph/"
STORE_DIR = os.path.join("career", "store")
LOCK_WAIT = 5.0

def open_writer(root, wait=LOCK_WAIT):
    path = os.path.join(root, STORE_DIR)
    deadline = time.monotonic() + wait
    delay = 0.05
    while True:
        try:
            return ox.Store(path)
        except OSError as e:
            if "lock" not in str(e).lower() or time.monotonic() >= deadline:
                raise Busy("another jsk command is writing to the career") from None
            time.sleep(delay)
            delay = min(delay * 2, 0.5)

def replace_graphs(db, new):
    ops = []
    for name, triples in new.items():
        g = graph_node(name)
        ops.append(f"DROP SILENT GRAPH {g}")
        if triples:
            body = " .\n".join(f"{t.subject} {t.predicate} {t.object}" for t in triples)
            ops.append(f"INSERT DATA {{ GRAPH {g} {{ {body} }} }}")
    db.update(" ;\n".join(ops))
```

Two things to check when it lands, not settled by the sketch: that an `OSError` other than the
lock (a missing folder, a permissions error) is reported as itself rather than as `Busy` - the
sketch's `"lock" in str(e)` test is the part to test on Linux too, where the message differs;
and that `open_reader` on a missing store raises something `load` turns into "no career here -
`jsk new` or `jsk migrate`".

## Phases

Each phase ends green (`uv run pytest`, ruff) and is committed on its own.

### P1 - `db.py` and the tests that pin it

- `db.py` as above, plus `graphs`, `graph_node`, `name_of`, `dump(db, fh)`, `load_into(db, fh)`.
- `tests/test_db.py`: lock refused then granted (subprocess), reader alongside writer, atomic
  multi-graph update (runtime failure in the second op rolls back the first), escaping round
  trip (the sketch's string), drop graph, dump -> load into an empty store is identical,
  `load_into` refuses a non-empty store, a non-lock `OSError` is not `Busy`.
- Tier-1 rule `non-canonical-number` (Ruling 4) with its tests, before anything relies on it.

### P2 - load from the store

- `store.load(root, graphs=None)`: `db.graphs(open_reader(root))` for the record, vocabulary from
  its file, then the existing pipeline. `Store.parsed` becomes `Store.graphs` (`name -> triples`);
  `line_of` returns 0 and findings drop the line; `store.graph(name)` returns the triples.
- **No query is rewritten.** The ~58 SPARQL queries in 14 modules (`queries`, `named`,
  `select`, `match`, `rules`, ...) run over the same in-memory store `load()` builds today.
- The 59 `.parsed` / `store.graph(file)` / `line_of` / `file_of` uses in 16 files move to graph
  names (mechanical; `graph(name)` still returns triples).
- The three direct readers of a record file are rewritten: `store.py:139` (the loader itself),
  `timeline.py:138` (parses `application.ttl` itself - reads the loaded graph instead),
  `render_resume.py:67` (a regex over `posting.ttl`'s text for `j:company` - a SPARQL `SELECT`
  on the posting graph instead).
- The 11 `writer.write(...)` calls that serialise triples to save them (`record.py`, `kb.py`,
  `timeline.py`, `postingbuild.py`, `gapsbuild.py`) hand the triples to `R.commit` in P3/P4; the
  two text comparisons (`gapsbuild.py:341`, `timeline.py:431`) become set comparisons.
- **Test fixtures:** `tests/graph_fixtures/` stays as readable Turtle *sources*. A helper
  `seed(tmp_path, fixture)` parses them and fills a store with `replace_graphs`; every test that
  copies the fixture tree calls it instead. This keeps test content reviewable and changes only
  setup.
- `test_graph_budget.py` re-measured: the 16k-triple career from store to validated, budget
  1.2 s unchanged. The measured number goes in the comment.

### P3 - the write path

- `record.py` reduced to Ruling 10's remainder; `commit` = one `open_writer` + `replace_graphs`
  of kb and log + `.jsk/backup.trig`.
- `kbcli`: `write_logged`, `writable` (only `clean` and `empty` states remain), `apply`, `confirm`,
  `pack`, `merge` over graphs. `adopt`, `fmt` and their tests deleted. `path` prints the
  workspace and `applications/`. New `log`, `dump`, `load` verbs with `--help` text.
- `kb.py` (`jsk new`): creates `career/store/` holding kb and log at r1, and `applications/`.
- The Busy refusal wired into every writer, with a test that holds the lock in a subprocess.
- `db.write_turn(root)` (the `qlock.py` lock) and `R.commit(root, changeset, base)`: takes the
  turn, re-checks the revision, rebases or refuses (Ruling 7), writes, closes, releases.
- `edit.py`: logic unchanged; ~10 lines move from files to graph names - `log_entries` (73),
  `taken_ids` (89), `sent_elsewhere` (111), `referenced` (335), `apply` (173). The "git
  restored an older kb.ttl" reasoning in `taken_ids`/`sent_elsewhere` becomes "`jsk kb load`
  of an older backup"; the logic stays, since a restore can forget ids an application names.
- **`edit.apply` compares changeset triples with the record's as sets**, and the record now
  comes back canonical (`8.4`) while a changeset is parsed lexically (`8.40`): `8.40` on a
  metric at 8.4 would read as a changed claim (drop to inferred, a new version) and
  `op:delete ... 8.40` would find nothing. Ruling 4's rule must run in `changeset.py`, before
  `edit.apply`. Test: exactly that changeset is refused with the fix, and the record unchanged.
- **Before rebase is trusted:** a test over every writer (`apply`, `confirm`, `pack`/`merge`
  applied, posting/gaps builds, `freeze`, `event`) asserts its log entry's `touched` ∪ `minted`
  equals the set of subjects whose triples differ between the two revisions. If any writer
  under-reports, rebase would merge a real conflict silently; that is fixed first.
- Tests: four subprocess writers queue and all land, in order, as consecutive revisions;
  disjoint changesets drafted at one base both land; overlapping ones - the second refused,
  naming the id, store unchanged; a rebase that breaks a rule (citing a metric the first
  retired) refused by the rule; a holder killed mid-turn does not block the next; no command
  takes its turn before `S.load` has validated.

### P4 - applications in the store

- `postingbuild`, `gapsbuild`, `timeline` (`freeze`, `event`) write their graphs through
  `R.commit`-style single updates; the sent-is-frozen check reads the application graph.
- `match`, `tailor prepare`, `kb export --from-match`, `render_resume.company_of` take `APP`
  (Ruling 11); the old path form is refused with the fix.
- `posting build --replace` drops the posting and gaps graphs in the same update it writes the
  new one.

### P5 - import, doctor, backup

- `jsk kb load <workspace>` for a file-laid-out workspace (Ruling 9): the current `store.load`
  file path, kept as `graph/legacy.py`, feeds `replace_graphs`; canonical numbers with a line per
  rewrite; refuses a non-empty store and a workspace with any FAIL.
- Any command run in a workspace that has `career/kb.ttl` and no `career/store/` refuses with
  the fix `jsk kb load .`.
- `jsk doctor` reports the store: present, readable, revision, and whether `.jsk/backup.trig`
  exists.
- Replay: `jsk kb load` over a **scratch copy** of `C:\Projects\basilin-joe-resume\career`, then
  `kb check`, `kb view`, a `match` and a `ship` against it. Never the real folder.

### P6 - prose, agents and budgets

- `plugins/jsk/skills/jsk/SKILL.md` and references, `commands/setup.md`, the five agent
  definitions: `jsk kb path` file lines, direct reads of `kb.ttl`/`log.ttl` (auditor,
  resume-author) and `posting.ttl` paths replaced with `kb view`, `kb show`, `kb log` and `APP`.
  `adopt`/`fmt` removed everywhere.
- `docs/WHY.md` "The knowledge base is the source of truth" and "One graph, laid out as one file"
  rewritten for the store, including what it costs (no text to open, a version-tied format,
  the dump as the escape hatch); `ARCHITECTURE.md`, `SCRIPTS.md`, `CONCEPTS.md`, `ONTOLOGY.md`,
  `QUICKSTART.md`, `README.md`.
- `tests/test_budget.py` token budgets re-measured and moved deliberately, each with the measured
  number in its comment. `tests/test_plugin_surface.py` updated for the verb list.

### P7 - review and dead code

- One opus review of the diff (code), one of the prose; fix pass.
- Delete what nothing imports any more (`io.parse`, `store.workspace_files`, `record` file
  helpers, writer layout code). `grep -rn "kb\.ttl\|log\.ttl\|posting\.ttl\|application\.ttl\|
  gaps\.ttl" src plugins docs` returns only history and changelog lines.

## Risks

- **The store format is tied to pyoxigraph.** Mitigated by Ruling 8. Raising the pin is a
  deliberate step: `jsk kb dump` on the old version, bump, `jsk kb load` into a fresh store, and
  CI on Windows and Linux.
- **The turn lock is verified on Windows only.** The `flock` branch runs first in P1's tests on
  the Linux CI job. `open_writer`'s retry stays as a backstop for a RocksDB LOCK held by
  something outside jsk (a stray `pyoxigraph` session).
- **A hung writer blocks the queue.** A process that dies releases its turn; one that hangs
  inside it does not. The turn covers only open + update + close, so a hang there is a
  RocksDB fault; the waiting message names the lock file so a person can find the holder.
- **Test churn.** About 160 files mention a record file. `seed()` keeps most changes to setup
  lines; the tests of adopt, fmt, torn and hand-edited states are deleted, not ported.
- **A crash between the store update and `.jsk/backup.trig`** leaves the backup one revision
  behind. That is acceptable for a backup; `doctor` reports the backup's revision next to the
  store's.
- **No text to open.** A person who wants to read the whole career runs `jsk kb view`. That is
  the trade the user chose.

## Verification (after P5, again after P7)

1. `uv run pytest` and ruff clean; the Windows and Linux CI jobs green.
2. Three processes: `jsk kb apply` holding its turn while a second `apply` (disjoint, same base)
   waits, then rebases and lands as the next revision, and a `kb show` in a third answers at once.
3. Kill a `jsk kb apply` mid-write (a test hook between building the update and running it, and
   one inside it): the store is at the old revision or the new one, never between.
4. `jsk kb dump` -> `jsk new` elsewhere -> `jsk kb load` -> `jsk kb check`, `kb view` identical.
5. The P5 replay on a scratch copy: `kb load`, check, match, ship; the PDF and plain text are
   identical to what the file-based branch tip renders from the same `kb.ttl`, and `kb view`
   matches line for line (numbers aside, where Ruling 4's report lists each rewrite).
