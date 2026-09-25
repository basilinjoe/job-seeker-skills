# Plan: rewrite jsk around a graph-native record (Option C)

## Context

jsk keeps a career in one Markdown file (`user-knowledgebase.md`) that the model edits by hand; nothing validates it until a hand-written `resume.json` reaches the record gate. The graph simulation (`docs/superpowers/experiments/2026-09-24-graph-simulation/`, 12 scenarios, 7/7 mutations caught) showed six things a model cannot hold by itself — the same answer twice, one-way matching under pressure to fit, exact joins across postings, time (revised metrics, computed years), reading only what matters, questions tied to a named gap — and that a graph answers each deterministically (matching P 1.000 / R 0.958 vs fuzzy 0.792 / 0.792).

The user chose **Option C**: the record becomes graph-native **text** — Turtle/TriG files in git — loaded into **Oxigraph** in memory on every run and validated on every load. Existing Markdown KBs migrate **one way** (`jsk migrate`, round-trip proven; Markdown reader kept one release). **Hand edits are allowed and validated**; agents write through `jsk kb apply`.

**This reverses a recorded decision.** jsk built a write layer (`okf`, ~30 commands, dc248f4..2906f25) and designed a property-graph store (`git show e97e3ac^:docs/superpowers/specs/2026-09-01-okf-graph-store-design.md`), then removed both (819ae0b, 99b9185; `docs/WHY.md` L16-31: "right for a knowledge base too large to hold in one context. A career is not."). The case now is not size but **guarantees**: validation on every load, one-way matching, versioned history, a claims gate. Each old failure is answered below.

| okf failure | Answer |
|---|---|
| SKILL.md named ~30 verbs (5,128 resident tokens) | 4 new top-level verbs (`kb`, `match`, `event`, `migrate`); subverbs live in `--help` and FAIL/fix output, not SKILL.md |
| A missing verb = hand-authoring bypass; "CLI coverage is the agent's ceiling" | One generic `kb apply` whose coverage is the **ontology**, plus `j:note` on every class as a relief valve; hand edits are legal and validated anyway |
| Unsafe defaults (`--status confirmed`, stdin `--body -` hang) | No status flag exists; a changeset asserting confirmed is refused; `-` refused; confirm only via `kb confirm --answer` |
| Cross-file atomicity not real | apply writes 2 files (kb.ttl, then log.ttl) with a revision + hash in both; a torn write is **detected** on next load |
| "Surgical writes, never redump a person's file" | gofmt contract: canonical writer; apply refuses a non-canonical file ("run `jsk kb fmt`") so format and content never share a diff |
| WHY.md: a person must read and correct their record end to end | kb.ttl itself is laid out as one readable file in the old section order (banners, bullets under projects, `"""` prose, CURIEs, no blank nodes); `kb view` is stdout only, never a committed second copy |

## Architecture (decisions)

**Boundary unchanged:** `resume.json` stays the narrow waist. `src/jsk/urs/*`, `src/jsk/gates/validate_urs.py`, `check_ats.py`, `check_prose.py` and `jsk render/preview/fit/validate/check` do not change. Only `kbindex.py`, `kb.py`, `preflight.find_kb`, `cli.cmd_freeze` and the plugin text touch the KB today.

**Workspace layout**
- `career/kb.ttl` — whole career + the person's vocabulary additions. `career/log.ttl` — append-only audit log, written by apply.
- `applications/<dir>/posting.ttl` (structured requirements), `posting.md` (advert verbatim, no frontmatter), `gaps.md` (prose, unchanged), `resume.json`, renders, `application.ttl` (metadata, carried links, timeline events).
- Shipped vocabulary `src/jsk/data/vocabulary.ttl` (technologies only, no `implies`).
- `jsk new` writes `.gitattributes` with `*.ttl text eol=lf`.
- In memory: one named graph per file (errors name the file); derived triples in `j:derived`, never written; queries over the union graph.

**Package `src/jsk/graph/`**
- `ontology.py` — classes, predicates (order, datatype, cardinality, id prefix, `claim=True/False`), enums as data. Single definition of the format; a test asserts the format reference lists every predicate.
- `io.py` — parse Turtle/TriG via pyoxigraph; map a shape failure's subject to file:line by scanning `^k:<id>\b`; CRLF-normalise.
- `writer.py` — own canonical Turtle writer (~250 lines): fixed prefix block, section banners in kb-spec order, subjects by class then natural key (roles by start desc, projects under role, bullets by `j:rank`, versions under metric), predicates in ontology order, `"""` literals with correct escaping, values never reflowed. pyoxigraph only parses/queries.
- `shapes.py` — tier 1 generated from ontology (closed predicates, required, cardinality, datatype, enum, prefix); tier 2 SPARQL SELECT rows `(rule_id, severity, sparql→?focus ?detail, fix)` for cross-node rules (dangling refs, bullet's metric exists, counts-as cycle, path across a `distinct` wall, frozen metric version mutated, retired target referenced). Output via `validate_urs.Report`/`show()`: `FAIL file:line id — … / fix: …`.
- `store.py` — load + validate + materialise counts-as closure (graphsim `materialise_paths`), hash check against log.ttl.
- `queries.py` — named queries ported from graphsim: `resolve`, `match`, `evidence`, `cover`, `questions`, `experience`, `stale`, `inconsistent`, `demand`, `pipeline`.

**Model**
- Ids shared with URS: `org_ pos_ prj_ ach_ skill_ cred_ edu_ q_ met_`; concepts `c:<slug>`. Bullet ids `ach_<prj-stem>_<2-4 content words>`, minted by apply if absent, never reused, positional (`_\d+$`) refused. Shared ids make the claims gate a join.
- Provenance node-level, no RDF-star: `j:provenance` ∈ PROVENANCE_RANK values (confirmed/inferred/needs-verification/disputed); overloaded `status` split into `j:credentialState`, `j:authorization`; enums use URS values (`reported`, `employment-visa`).
- Tag vs evidence: project `j:uses` = tag; bullet `j:shows` = evidence.
- Prose `j:problem/j:decision/j:outcome` literals, `claim=False` (editing never resets provenance, never used by the gate).
- Versioned metrics: `k:met_x` + `k:met_x.v1…` (value, baseline, confidence, source, validFrom, validUntil, provenance). Setting a value creates a version and closes the old; versions linked from any application are immutable.
- Vocabulary rules from `docs/superpowers/specs/2026-09-24-vocabulary-graph-design.md`: labels (normalised), isA/partOf/implies counts-as one-way, hop limit 2 constant, implies never carries required, `distinct` wall, `former` labels, ambiguous labels asked, 5 buckets (matched / near / missing / ambiguous / candidate).

**Write path — `jsk kb <subverb>`** (one `HANDLERS` entry)
- `apply <changeset.trig>`: TriG with reserved graphs `op:set` (replace values of (s,p)), `op:add`, `op:retire` (`j:reason`), `op:delete` (refused while referenced), optional `op:base "rN"` (refuse if any touched (s,p) changed since rN). Steps: parse → refuse forbidden (confirmed provenance, `j:derived`, blank nodes, unknown predicate + difflib suggestion) → merge → claim predicate changed ⇒ `inferred` + auto `Question` → validate whole graph → canonical write to temp → parse own output → `os.replace` kb.ttl then log.ttl (retry on Windows lock; `.bak` until success) → print unified diff + ids touched/minted. `--dry-run` = diff only.
- `confirm <id> --answer "…"` (only way to confirm; logged with answer; `kb check` flags empty/placeholder answers — an instruction plus audit trail, stated as such).
- `show <ids>`, `query <name> [args]`, `view` (stdout Markdown), `check`, `fmt`, `adopt` (logs a hand edit, lists every provenance upgrade it contains).
- Hand-edit detection: log.ttl's last entry stores sha256 of canonical kb.ttl; mismatch on load prints `NOTE kb.ttl changed outside jsk kb apply since rN`.

**Other verbs**
- `jsk match <posting.ttl>` replaces `jsk index --rank`: buckets, paths, scores (reuse `kbindex.WEIGHTS`, `recency_points`, `SENIORITY`), set cover, derived questions; posting.ttl requirements carry `j:quote` checked verbatim against posting.md and a necessity-wording flag.
- `jsk event <app-dir> <kind> --date …` — add-only `j:Event` (closed vocabulary from `mode-pipeline.md`); stage/staleness stay queries.
- Claims gate `src/jsk/gates/claims.py`, run inside `gates`/`ship`/`freeze` when a KB is found (no verb): (1) achievement absent from KB ⇒ must be `inferred`; (2) record provenance above KB's ⇒ FAIL; (3) every numeral (`numerals()`/`covered()`) in the metric's current version, else superseded/untraced; (4) vocabulary label names a concept not held by the source project; (5) skill aliases held; (6) "N years of X" vs `experience()`. 1-3 FAIL from day one; 4-6 WARN until measured at zero false positives on real records.
- Freeze writes `application.ttl` (company, title, view, submitted, channel, documents, sha256 of resume.json, `j:carried` achievement→bullet→metric-version links). No content copies — the frozen resume.json is the copy.

## Phases (each its own spec → plan → implementation, each ships green)

**P0 Spike (throwaway, `docs/superpowers/experiments/`)** — pin pyoxigraph minor; wheels Win/Linux py3.10-3.14; parse-error positions; confirm serializer is non-canonical; `use_default_graph_as_union`; load+validate+materialise+import time for 5k triples + 100 applications; hand-migrate one real KB and measure kb.ttl vs .md tokens. **Exit:** numbers in P1 spec; if kb.ttl > 1.6× .md tokens, revisit layout first. Also commit the untracked graph-simulation experiment; mark `docs/superpowers/plans/2026-09-24-vocabulary-graph.md` and its spec superseded.

**P1 Packaging + graph core** — `src/jsk/graph/{ontology,io,writer,shapes,store}.py`; `pyproject.toml` (`dependencies=["pyoxigraph>=X.Y,<X.Y+1"]`, `requires-python>=3.10`, rewritten "deliberately empty" comment); `src/jsk/preflight.py` (MIN_PYTHON, lazy pyoxigraph Check, MODULES, REQUIRED); CI 3.10 + 3.13 + a Windows job. Reuse `KBError` pattern, `validate_urs.Report/show`. Tests `tests/test_graph_io.py`, `tests/test_graph_shapes.py`: round-trip + byte idempotence (fixture + seeded generator), escaping cases, CRLF, one test per shape rule naming file:line, mutation test over shapes. **Exit:** hand-written kb.ttl fixture loads, validates, round-trips; no CLI change.

**P2 Vocabulary + match** — `src/jsk/data/vocabulary.ttl`, `src/jsk/graph/queries.py`, `jsk match`. Port graphsim S0-S7, S11 as tests + mutation test; shipped-vocab rule test. Add `match` to SKILL.md, `cli.py` docstring/SIMPLE, `docs/SCRIPTS.md`. **Exit:** scenarios pass via the command.

**P3 Write path** — `jsk kb apply|confirm|show|query|view|check|fmt|adopt`. Tests: one per refusal; confirm-by-changeset refused; torn write detected; hand edit detected/adopted with upgrades listed; `--dry-run` touches no mtime; `-` refused; Windows lock retry; metric versioning; `op:base` conflict. **Exit:** scripted braindump (project + bullets + metric + vocab term) → valid kb.ttl with correct diff.

**P4 Migration** — `src/jsk/migrate.py`, `jsk migrate <user-knowledgebase.md>`: kb.md→kb.ttl (rename `proj_→prj_`, `role_→pos_`, enum map, mint bullet ids reusing ids from existing resume.json when text matches), log.md→log.ttl, posting.md→posting.ttl+advert, application.md→application.ttl (timeline table + carried links from resume.json). Reuse `kbindex.read_kb`, `projects_of`, `experience`, `read_posting`, `frontmatter`. Round-trip: normalised `read_kb` dict == graph→dict projection, else refuse; never deletes .md; refuses if kb.ttl exists; then runs the claims gate over every existing resume.json and lists new failures. Old extras renamed `[migrate]`. Tests `tests/test_migrate.py` over `fixtures.kb_text` + an every-section KB. **Exit:** a real KB migrates with round-trip passing.

**P5 Claims gate + freeze + events** — `src/jsk/gates/claims.py`; `cli.py` `gate_results`/`cmd_ship`/`cmd_gates`/`cmd_freeze` gain the claims step; freeze's KB check → `career/kb.ttl`, writes `application.ttl`; `jsk event`. Reuse `numerals`, `covered`, `metric_values`, `call_gate`, `print_results`. Tests: graphsim S8/S9 fixtures; update `tests/test_ship_freeze.py`. **Exit:** checks 1-3 FAIL, 4-6 WARN.

**P6 Plugin rewrite** — `plugins/jsk/skills/jsk/SKILL.md` (drop "Editing the knowledge base" habits; one rule: change via `kb apply`, read via `kb show/view`, hand edits adopted; rows for kb/match/event/migrate; net-zero ≤2,268 tokens), all `references/mode-*.md` (grep/sed/Edit → apply/query/event; mode-tailor shrinks via `jsk match`), agents (analyst writes posting.ttl + gaps.md, "Never touch `career/kb.ttl`"; author reads `jsk match` then `jsk kb show <ids>`; auditor uses `kb check`/`query`; verifier names repair sites by id), `references/kb-spec.md` → `references/kb-format.md`. `tests/test_budget.py`: move ceilings deliberately with measured comments (kb-format new ceiling; author set should fall — lower it; keep kb-format off mandated write paths); `tests/test_plugin_surface.py` phrase assertions and "writer banners ↔ kb-format" replace "template headings ↔ kb-spec". Commands in `plugins/jsk/commands/*` keep shims. **Exit:** all budgets pass; each moved ceiling has a measured comment.

**P7 Docs + deprecation** — rewrite `docs/WHY.md` ("One graph, laid out as one file", with the new cost stated), `docs/ARCHITECTURE.md` "What is frozen", `docs/CONCEPTS.md`, `docs/QUICKSTART.md`, `docs/SCRIPTS.md`, README; `src/jsk/kb.py` scaffolds kb.ttl/log.ttl/.gitattributes; `preflight.find_kb` finds `career/kb.ttl` and points a `user-knowledgebase.md` at `jsk migrate`; `index` leaves SIMPLE. **Release N+1:** delete `kbindex.py`, `tests/test_kbindex.py`, `[index]/[migrate]` extras, `jsk migrate`.

**P8 (optional) Record export** — `jsk kb export --urs --select <ids>`: draft resume.json with exact ids, provenance and metrics, removing hand transcription (main source of record defects); the author only retunes text and the view.
  *Built (2026-09-25), `src/jsk/graph/export.py`. Rulings:* `--select` takes `prj_`/`ach_`/`pos_` and narrows only the experience - the person, skills, education, credentials and positioning always come across whole (short, and the view decides what renders); an employer always brings every role held there (a promotion history is never halved); a named bullet narrows its project to the named bullets; a metric is exported at its current version only, and one with none is left off so its number fails the gates rather than travelling; one draft view `view_draft` at `provenance_floor: confirmed`; `--out` never replaces a file; a career with a FAIL is refused, a hand-edited one is not (export only reads). Engagement ids are `eng_<org slug>`, suffixed by kind only when one employer has two kinds of work.

## Risks

| Risk | De-risked by |
|---|---|
| pyoxigraph wheel/API breaks (LadybugDB precedent) | P0 pin after spike; Windows CI job; raising the pin reruns both platforms |
| Turtle too costly/unreadable, breaking WHY.md | P0 token ratio + a real migrated file shown to the person before P1 |
| Writer bug corrupts a record | P1 round-trip/idempotence properties; apply re-parses and validates its own output before replacing; `.bak` |
| Migration loses data | P4 mandatory round-trip equality; .md never deleted; claims gate rerun on old records |
| Agents route around apply | P3 hash detection + `adopt` listing provenance upgrades (detection, not prevention — stated) |
| Claims-gate false positives | P5 ships 4-6 as WARN, promote after measuring |
| Token budgets have no headroom (SKILL+tailor+ship 5,985/6,000) | P6 after `match` shrinks mode-tailor; every ceiling move measured and commented |
| No pip in a sandboxed session | doctor reports "career writes and matching unavailable"; SKILL.md: draft a changeset for later apply, never edit kb.ttl blind |
| Python 3.8/3.9 users | floor stated in P1; both EOL, never tested |

## Verification (end to end, after P5; again after P6)

1. `python -m pytest tests -q -n auto` and `python -m ruff check src tests` green on Windows and in Docker `python:3.10-slim`.
2. `jsk doctor` shows the pyoxigraph check `ok`.
3. `jsk migrate` a fixture Markdown KB with applications → round-trip passes; `jsk kb check` clean; `git diff` of a second `jsk kb fmt` empty (idempotent).
4. Scripted braindump changeset via `jsk kb apply` → diff printed, log.ttl revision incremented; a hand edit to kb.ttl → `NOTE … changed outside` then `jsk kb adopt`.
5. `jsk match` on the graphsim postings reproduces S0-S7, S11 outputs.
6. Draft `resume.json` with the graphsim S8 defects → `jsk ship` stops at the claims gate with the 7 flags; a clean record ships and `jsk freeze` writes `application.ttl` with carried links; `jsk event` appends; `jsk kb query pipeline` derives the stage.
7. Revise a metric via apply → `jsk kb query stale` lists applications that sent the old version (S9).
8. `tests/test_budget.py` and `tests/test_plugin_surface.py` pass with measured ceiling comments.

## Next step on approval

Start P0 (spike), then brainstorm → spec → writing-plans for P1. Each phase gets its own spec and plan under `docs/superpowers/`.
