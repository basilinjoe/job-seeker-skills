# Remove URS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The resume is built from `career/kb.ttl` plus a ~20-line `resume.json`; the URS record, its spec, `resolve.py`, the record and claims gates as they are, and `export --urs/--refresh` are gone.

**Architecture:** A short file (`jsk.resume.short`) names what was chosen. A builder (`jsk.resume.build`) reads the graph store and the short file and returns the render plan the emitters already take - `emit_latex`, `emit_text`, `themes`, `fit_pages` do not change. One record gate (`jsk.gates.record`) replaces `validate_urs` + `claims`, over the short file and the bullets it selects.

**Tech Stack:** Python 3.10+, pyoxigraph (the store), unittest/pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-short-resume-json-design.md` - read it first; this plan argues from it.

## Global Constraints

- Worktree `C:/Projects/open-source/jsk-tailor-fixes`, branch `fix/tailor-run-waste`. Another session commits to `feat/vocabulary-graph` in `C:/Projects/open-source/job-seeker-skills` - never touch that checkout.
- One hard dependency: `pyoxigraph`. Everything else standard library.
- Run tests from the worktree root: `python -m pytest -q tests/<file>`; tests put the worktree's `src` first. The CLI against worktree code: `PYTHONPATH=src python -m jsk ...` (a bare `jsk` is another checkout).
- Files with backslashes (regexes, Turtle, LaTeX) are written with the Write/Edit tools, never a bash heredoc.
- Code comments and docstrings explain *why*, citing the run that exposed it, in the house voice (see `src/jsk/graph/export.py`). No new top-level `jsk` verbs.
- The short file's keys are exactly: `resume` (=2), `bullets`, `format`, `region`, `pages`, `ats_pages`, `floor`, `summary` (`{text, status}`), `roles`, `skills`.
- `tests/test_budget.py` ceilings move only with a measured comment.

## Review Focus

1. **A short file outside any workspace** (`jsk render ~/Downloads/resume.json`) - refuse with a fix naming `career/kb.ttl`, never a traceback. → Task 1 test.
2. **A bullet id retired after the file was written** - the record gate FAILs naming it and the fix (drop it or pick its replacement); render does not silently skip it. → Task 1 + Task 5 tests.
3. **A workspace named `career`** (`career/career/kb.ttl`) - the root is found by `kbcli.find_root`, never by `dirname`. → Task 1 test.
4. **Two bullets of one project with another project's bullet between them in `bullets`** - order within a role follows the list; roles and employers still by date. → Task 3 test.
5. **`jsk ship` in a frozen application** (`application.ttl` present) - refuses before rendering. → Task 6 test.

---

## File structure

| File | Responsibility |
|---|---|
| `src/jsk/resume/__init__.py` | package doc |
| `src/jsk/resume/short.py` | read a short file; its shape and id findings; find its workspace |
| `src/jsk/resume/build.py` | graph + short file → plan (replaces `urs/resolve.py`) |
| `src/jsk/resume/career.py` | graph reading shared by build and export: `Career`, employer grouping, periods (moved out of `graph/export.py`) |
| `src/jsk/gates/report.py` | `Report`, `show` (moved from `validate_urs.py`) |
| `src/jsk/gates/numbers.py` | `numerals`, `covered`, `SCALE` (moved) + `untraced(store, bullets, today)` |
| `src/jsk/gates/record.py` | the record gate: `findings(path_or_short, store, today)`, `main(argv)` |
| `src/jsk/urs/render_resume.py` | reads a short file, builds, emits (keeps its CLI) |
| `src/jsk/urs/profiles.py` | `load` + a slim `Profile` (no Gate) |
| `src/jsk/data/schema/profiles/*.json` | `id, region, label, pages, sections, declaration, work_rights` |
| `src/jsk/data/example/career/kb.ttl`, `src/jsk/data/example/resume.json` | doctor's self-check input |
| `src/jsk/graph/export.py` | writes a short file from a selection (URS writer removed) |
| `src/jsk/graph/timeline.py`, `src/jsk/cli.py` | freeze/ship/gates/validate over short files |
| `src/jsk/migrate.py` | converts legacy full records in unfrozen applications |
| `tests/careerkit.py` | test helper: a workspace from `claims_fixtures` with edits and a short file |
| deleted | `urs/resolve.py`, `urs/plan.py`, `gates/validate_urs.py`, `gates/claims.py`, `data/schema/example.resume.json`, `references/urs-spec.md`, `references/view-format.md`, `docs/urs-guide.md` |

---

## Phase 1 - Foundation (sequential; Tasks 1-4)

### Task 1: The short file

**Files:**
- Create: `src/jsk/resume/__init__.py`, `src/jsk/resume/short.py`, `tests/careerkit.py`, `tests/test_short.py`

**Interfaces:**
- Produces:
  - `short.KEYS: dict[str, type|tuple]`, `short.FORMATS = ("presentation", "ats-maximal")`, `short.STATUSES = ("confirmed", "inferred")`
  - `short.ShortError(Exception)` with `.fix: str`
  - `short.read(path) -> dict` - JSON with `"resume": 2`; raises `ShortError` for missing/unreadable/not JSON/legacy URS (`"urs"` key: fix = "convert it with `jsk migrate`")/wrong version.
  - `short.workspace(path) -> str` - `kbcli.find_root(dirname(abspath(path)))`; raises `ShortError("... is not inside a workspace", "keep resume.json under the folder holding career/kb.ttl")`.
  - `short.shape(doc) -> list[str]` - FAIL lines: unknown key, wrong type, empty/missing `bullets`, bad `format`, bad `summary.status`, ids with the wrong prefix (`ach_`/`pos_`/`skill_`), duplicates.
  - `short.ids(doc, store) -> list[str]` - FAIL lines: an id `kb.ttl` does not hold (with a close match), a retired one (with its reason), a bullet whose project has no `j:position`.
  - `careerkit.workspace(tmp, edits=(), short=None) -> (root, short_path)` copies `tests/claims_fixtures` to `tmp`, applies `(old, new)` text replacements to `career/kb.ttl`, writes `short` (a dict) to `applications/contoso-platform/resume.json` (removing the legacy one), returns paths. `careerkit.store(root)` loads it.

- [ ] **Step 1: Write the failing tests** (`tests/test_short.py`)

```python
import json, tempfile, unittest
from pathlib import Path
import careerkit
from jsk.resume import short

OK = {"resume": 2, "bullets": ["ach_events_latency", "ach_identity_sso"]}

class Read(unittest.TestCase):
    def test_a_short_file_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(tmp, short=OK)
            self.assertEqual(short.read(path)["bullets"], OK["bullets"])
            self.assertEqual(short.workspace(path), root)

    def test_a_legacy_record_points_at_migrate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json"); p.write_text(json.dumps({"urs": "1.0.0"}))
            with self.assertRaises(short.ShortError) as err:
                short.read(p)
            self.assertIn("jsk migrate", err.exception.fix)

    def test_outside_a_workspace_is_refused_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json"); p.write_text(json.dumps(OK))
            with self.assertRaises(short.ShortError) as err:
                short.workspace(p)
            self.assertIn("career/kb.ttl", err.exception.fix)

    def test_a_workspace_named_career_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(Path(tmp, "career"), short=OK)
            self.assertEqual(Path(short.workspace(path)), Path(root))

class Shape(unittest.TestCase):
    def check(self, **change):
        return short.shape({**OK, **change})

    def test_clean(self):
        self.assertEqual(short.shape(OK), [])

    def test_unknown_key(self):
        self.assertTrue(any("views" in f for f in self.check(views=[])))

    def test_no_bullets(self):
        self.assertTrue(self.check(bullets=[]))

    def test_bad_format_and_status(self):
        self.assertTrue(self.check(format="web"))
        self.assertTrue(self.check(summary={"text": "x", "status": "disputed"}))

    def test_wrong_prefix_and_duplicate(self):
        self.assertTrue(self.check(bullets=["prj_events"]))
        self.assertTrue(self.check(bullets=["ach_events_latency", "ach_events_latency"]))

class Ids(unittest.TestCase):
    def test_unknown_retired_and_roleless(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(tmp, short=OK)
            store = careerkit.store(root)
            self.assertEqual(short.ids(OK, store), [])
            self.assertTrue(any("did you mean" in f for f in
                                short.ids({**OK, "bullets": ["ach_events_latencyy"]}, store)))
```

Add the retired case once you know the fixture's text: `careerkit.workspace(tmp, edits=[(<ach_portal_frontend's provenance line>, <same + ' j:retired "2026-01-01"^^xsd:date ; j:reason "x" ;'>)])` - copy the exact edit pattern `tests/test_graph_match.py::edited` uses.

- [ ] **Step 2: Run to see them fail** - `python -m pytest -q tests/test_short.py` → ImportError.

- [ ] **Step 3: Implement** `short.py` (read/workspace/shape/ids as specified) and `careerkit.py`. `ids` uses `export.Career(store.graph(record.KB))` (moved to `resume/career.py` in Task 3 - import from wherever it lives then) and `difflib.get_close_matches` exactly as `export.chosen` does today (`src/jsk/graph/export.py:88-119`).

- [ ] **Step 4: Run** - `python -m pytest -q tests/test_short.py` → pass.

- [ ] **Step 5: Commit** - `feat: the short resume.json - read, shape, ids`.

### Task 2: The example workspace

**Files:**
- Create: `src/jsk/data/example/career/kb.ttl`, `src/jsk/data/example/career/log.ttl`, `src/jsk/data/example/resume.json`
- Modify: `src/jsk/paths.py` (`EXAMPLE_WORKSPACE`, `EXAMPLE_SHORT`; keep `EXAMPLE_RECORD` until Task 8)

**Interfaces:** Produces `paths.EXAMPLE_WORKSPACE`, `paths.EXAMPLE_SHORT` for preflight (Task 4) and render tests.

- [ ] **Step 1:** Build the example career from `example.resume.json`'s person (Priya Raman), engagements, projects, bullets, metrics, education, credentials, skills, work authorization and languages - as a kb.ttl that `jsk kb check` passes. Easiest route: write the Turtle by hand following `tests/claims_fixtures/career/kb.ttl`'s layout, then `PYTHONPATH=src python -m jsk kb fmt` it and generate `log.ttl` with `jsk kb adopt` (see `kbcli.cmd_adopt`). Keep the AU work-rights line and at least one bullet under each of two roles at one employer.
- [ ] **Step 2:** `resume.json`: `{"resume": 2, "region": "au", "bullets": [...every example bullet...], "skills": [...]}`.
- [ ] **Step 3:** Test in `tests/test_short.py`: `short.ids(read(EXAMPLE_SHORT), load(EXAMPLE_WORKSPACE)) == []` and `jsk kb check` exits 0 on it (`cli.main(["jsk","kb","check","--root",...])` or `kbcli.main` with cwd - follow `tests/test_graph_kbcli.py`).
- [ ] **Step 4:** Commit - `feat: an example workspace for doctor and the render tests`.

### Task 3: The builder

**Files:**
- Create: `src/jsk/resume/career.py`, `src/jsk/resume/build.py`, `tests/test_build.py`
- Modify: `src/jsk/graph/export.py` (import `Career`, `engagement_list`, `period`, `instant`, `local`, `enum`, `latest_first`, `metric` from `resume/career.py`; delete the moved definitions), `src/jsk/urs/profiles.py`, `src/jsk/data/schema/profiles/*.json`

**Interfaces:**
- Consumes: `short.read/workspace/shape/ids` (Task 1).
- Produces:
  - `build.build(store, doc, *, region=None, fmt=None, today=None) -> dict` - the plan: keys `view` (`"resume"`), `format`, `profile`, `region`, `pages`, `name`, `header_lines`, `headline`, `sections`, `warnings`, and new `sent: list[str]` (bullet ids rendered, in order). No `locale`, `target`, `photo`.
  - `build.from_path(path, *, region=None, fmt=None, today=None) -> (plan, root)` - read, workspace, `store.load(root)`, raise `short.ShortError` on shape/ids FAIL lines (joined), then `build`.
  - `profiles.load(ref) -> dict` with keys `id, region, label, pages, sections, declaration, work_rights`.

**What to port, and from where.** `build.py` is `urs/resolve.py` with each URS read replaced by a graph read through `Career` (`career.get(iri, pred)`, `career.all`, `career.live`). Keep every docstring and comment that still applies. Mapping:

| resolve.py | reads today | reads after |
|---|---|---|
| `header` :159-199 | `person.name.full/headline/location/contacts` | `k:person` `fullName`, `headline`, `city/region/country`, contacts per `export.CONTACTS` (export.py:24, 195-220). Drop `locality` and the `permits` calls. |
| `authorization_line` :201-228 | `work_authorization[]`, `gate.required` | only when `profile["work_rights"]`; live `WorkAuthorization`: `jurisdiction`, `kind`, `authorization` (`requires-sponsorship`), `validUntil` |
| `summary` :230-239 | view narrative | `doc["summary"]` if present (status for the floor), else `k:person j:positioning` with the person's provenance |
| `skills_section` :241-294 | view skills, doc skills | `doc["skills"]` ids → live `Skill` `name`, `category`; absent → every live skill sorted as `export.skills` sorts. Keep MAX_SKILLS_PER_ROW, dedupe, labels. |
| `experience` + `engagement_entry` + `place_bullets` :296-408 | engagements, positions, projects, view include | group `doc["bullets"]` by `j:project`; roles = each project's `j:position` + `doc["roles"]`; employers and their roles by `career.engagement_list(career, roles, projects)` (moved from export); every employer's live roles shown (promotion history whole, as export.py:172-179); bullets under their project's role in `doc["bullets"]` order; the kind word for contract/freelance/internship/volunteer. Drop location/via/domains/summary/career-break. |
| `keep` :137-144 | `provenance.status` | a bullet's/project's/education's/credential's `j:provenance` (enum local name); summary's status; floor from `doc["floor"]` |
| `education` :410-432 | education[] | live `Education`: `qualification`, `field`, `institution`, `start/end`, `gradeScheme/gradeValue` → `fmt_grade({"scheme":..,"value":..})` |
| `credentials` :434-452 | credentials[] | live `Credential`: `name`, `issuer`, `issued`; drop in-progress/attestation |
| `languages` :454-468 | languages[] | live `Language`: `language`, `native`, `level`; only when the profile's `sections` list `languages` |
| `declaration` :557-570 | city, `meta.updated` | city, `today` (default `datetime.date.today()`) |
| `build` :573-679 | views, profile, budget | no views: format = `fmt or doc.get("format","presentation")`; profile = `profiles.load(region or doc.get("region") or person country)`; pages = `doc["ats_pages"]` if ats-maximal, else `doc["pages"]`, else profile `pages`, else 2 |
| delete | `personal`, `logistics`, `referees`, `_present_paths`, `Gate`, `DEMONYM`, `ViewNotNamed` | - |

Profiles become (`in.json`): `{"id": "urs:profile:in/1", "region": "IN", "label": "India", "pages": 3, "sections": ["summary","skills","experience","education","credentials","languages"], "declaration": true, "work_rights": false}`; `au`/`ae` `work_rights: true`; `default` has no `declaration`. Rename the id prefix only if nothing else keys on it (grep `urs:profile:`) - otherwise keep it.

- [ ] **Step 1: Port the plan-level tests first.** Move each class listed as "plan" in the research (test_render_resume.py: Chronology, FunctionalTitles, AtsVariant, BulletsSitUnderTheirRole, SkillsBlock, Header, EmittersDoNotDiverge, PaperSize, TemplateCannotEmitAnAtsHazard, DateColumn :798, NoTemplateHyphenates, HeaderLinks :873/:880; test_themes.py's 7) into `tests/test_build.py`, building over `careerkit.workspace(...)` with `edits` instead of `urs_doc(...)`. Keep each assertion on plan/emitter output as it is. Add:

```python
def test_list_order_within_a_role_and_date_order_across_roles(self):
    # Review Focus 4: another project's bullet between two of one project's.
    doc = {"resume": 2, "bullets": ["ach_events_team", "ach_identity_sso", "ach_events_latency"]}
    plan = self.plan(doc)
    roles = [r for e in self.entries(plan) for r in e["roles"]]
    texts = [b for r in roles for b in r["bullets"]]
    self.assertLess(texts.index(self.text("ach_events_team")), texts.index(self.text("ach_events_latency")))

def test_sent_names_the_rendered_bullets_and_not_the_withheld(self):
    # ach_data_ingestion is j:inferred in claims_fixtures; the floor defaults to confirmed.
    doc = {"resume": 2, "bullets": ["ach_events_latency", "ach_data_ingestion"]}
    plan = self.plan(doc)
    self.assertEqual(plan["sent"], ["ach_events_latency"])
    self.assertTrue(any("withheld bullet ach_data_ingestion" in w for w in plan["warnings"]))
```

- [ ] **Step 2:** Run - fails (no `jsk.resume.build`).
- [ ] **Step 3:** Move the graph helpers to `resume/career.py`, write `build.py` by the table, slim `profiles.py`/the JSON.
- [ ] **Step 4:** `python -m pytest -q tests/test_build.py tests/test_short.py tests/test_graph_export.py tests/test_select.py` → pass.
- [ ] **Step 5:** Commit - `feat: build the render plan from the career`.

### Task 4: Render from a short file

**Files:** Modify `src/jsk/urs/render_resume.py`, `src/jsk/urs/preview_templates.py`, `src/jsk/preflight.py`; test `tests/test_build.py` (file-based part), `tests/test_preflight.py`.

**Interfaces:**
- Consumes: `build.from_path` (Task 3), `paths.EXAMPLE_SHORT` (Task 2).
- Produces: `render_resume.main(["render_resume.py", <short path>, "--out", DIR, "--pdf", "--ats-max"?, "--template"?, "--region"?])` - `--view` removed (a usage error names it: "a resume.json is one resume; drop --view"). File name from `plan["name"]` + `company_of(src)` as today. Prints `wrote  <file>` lines and warnings exactly as now (ship's summary parses them).

- [ ] Step 1: tests - the RenderedFiles/ThePdf/PageCount/DateColumn/HeaderLinks CLI cases from test_render_resume.py re-pointed at `careerkit` short files or `EXAMPLE_SHORT`; a short file outside a workspace exits 2 with the fix (Review Focus 1).
- [ ] Step 2: run → fail. Step 3: implement (`main` catches `ShortError` → print message + `fix:` → exit 2). preview passes paths through unchanged minus `--view`. preflight `verify()` renders `EXAMPLE_SHORT` and validates it with the record gate once Task 5 lands (until then, `short.shape` + `short.ids`).
- [ ] Step 4: run test_build, test_themes, test_check_ats, test_fit_pages, test_preflight → pass.
- [ ] Step 5: commit - `feat: render and preview take the short resume.json`.

## Phase 2 - In parallel (Tasks 5-7), each in its own worktree reset to the Phase 1 tip

### Task 5: The record gate

**Files:** Create `src/jsk/gates/report.py`, `src/jsk/gates/numbers.py`, `src/jsk/gates/record.py`, `tests/test_record_gate.py`. Modify `src/jsk/cli.py` (`cmd_validate`, `claims_step` removed, `gate_results`, `cmd_ship` steps), `src/jsk/gates/check_prose.py`, `src/jsk/graph/store.py`, `src/jsk/kb.py`, `src/jsk/graph/kbcli.py` (`cmd_check`), `src/jsk/graph/match.py` (`record_faults`, `faults_in`).

**Interfaces:**
- `report.Report`, `report.show` - moved verbatim from `validate_urs.py`.
- `numbers.numerals`, `numbers.covered`, `numbers.SCALE` - moved verbatim.
- `numbers.Fault(bullet: str, numbers: list[str], superseded: list[dict], cites: list[str])`; `numbers.untraced(store, bullets: list[str] (iris), today) -> list[Fault]` - claims.py check 3's logic (claims.py:229-276) over graph bullets: numerals in `j:text` not covered by the current versions of the metrics it `j:cites` (or its confirmed words), plus a closed version's number as superseded.
- `record.findings(doc, store, today) -> (fails: list[str], warns: list[str])`: `short.shape` + `short.ids` FAILs; `numbers.untraced` over `doc["bullets"]` as FAIL lines; WARNs: label-unheld (claims.py:356-381), years-overstated over headline/summary/bullets (claims.py:416-451), a bracket in the summary or a bullet.
- `record.main(argv)`: `jsk validate <resume.json>` prints like validate_urs did (`checking: resume.json`, `FAIL n WARN n`, `PASS - safe to render`), exit 1 on FAIL.
- `match.record_faults` calls `numbers.untraced` directly (no export, no regex over gate text); its question text (`fault_question`) unchanged.
- `kb check` warns `numbers.untraced` over every live bullet (replacing `gate_failures`).
- `jsk ship`: record gate → render → document gates. `jsk gates DIR [--record resume.json]` the same minus render.

- [ ] Step 1: tests - port test_validate_urs NumeralsMustBeBacked (7) and Periods (3 → a kb shape rule only if not already covered; else drop with a note), test_claims Numbers (5), Labels (4), S8Draft (6, rewritten as short files over edited fixtures), MatchAsks (2); plus the ElevenLabs case: a bullet "300-400 candidate drive" citing nothing FAILs naming both numbers; Review Focus 2 (a retired bullet FAILs with its reason).
- [ ] Step 2: run → fail. Step 3: implement; update importers of `Report/show/numerals` (`check_prose.py:31`, `store.py:72`, `kb.py:155`, `kbcli.py`, `match.py`, `timeline.py:136`).
- [ ] Step 4: run test_record_gate, test_graph_match, test_graph_kbcli, test_ship_freeze (ship part), test_cli (validate/gates) → pass.
- [ ] Step 5: commit - `feat: one record gate over the short file and the career`.

### Task 6: Export, freeze, ship

**Files:** Modify `src/jsk/graph/export.py`, `src/jsk/graph/kbcli.py` (`cmd_export`, `warn_draft`, `refreshed` removed), `src/jsk/graph/select.py` (`skill_order` without `export.skills`), `src/jsk/graph/timeline.py`, `src/jsk/cli.py` (`cmd_freeze`, `cmd_ship` guard and `--view`), `src/jsk/graph/ontology.py` (`Application.view` doc, `recordSha256` doc). Tests: `tests/test_graph_export.py` (rewritten), `tests/test_select.py` (Exported/Command), `tests/test_ship_freeze.py`.

**Interfaces:**
- `export.short_file(store, selection=None, select=None) -> dict` - `{"resume": 2, "bullets": [...], "roles": [...pos_ from select...], "skills": [...selection.skills...]}` (+ `region` when the person's country has a profile). Bullets in selection order (project by project, as `select.py` orders them); with `select` only, the named bullets and every live bullet of a named project by `j:rank`.
- `jsk kb export --from-match <posting.ttl> [--select ...] --out <resume.json>` and `jsk kb export --select ... --out <resume.json>`: write the short file (refuse an existing one: "edit it, or delete it to start again"), print the GAP/NOTE lines as now, then `numbers.untraced` over its bullets as WARN lines ("a question for the person"). No `--urs`, no `--refresh`; each is a usage error naming what replaced it.
- `timeline.freeze(root, app_dir, plan, short_bytes, submitted, channel, documents)` - `j:carried` from `plan["sent"]`, `j:carriedVersion` from those bullets' `j:cites` current versions, `recordSha256` of `short_bytes`, `j:view "resume"`.
- `cmd_freeze`: `build.from_path(app_dir/resume.json)`; no `--view`.
- `cmd_ship`: refuses when `<out or record dir>/application.ttl` exists: "frozen: <path> - re-rendering would overwrite what was sent" / fix "copy the application to a new dated directory to reuse it" (Review Focus 5). `--view` removed.

- [ ] Steps: tests first (export writes the short shape; freeze carries only rendered bullets - a withheld one is not carried; ship refuses when frozen), run → fail, implement, run test_graph_export/test_select/test_ship_freeze/test_graph_kbcli → pass, commit `feat: export writes the short file; freeze from what rendered`.

### Task 7: Migrate and doctor

**Files:** Modify `src/jsk/migrate.py`, `src/jsk/preflight.py`; tests `tests/test_migrate.py`, `tests/test_preflight.py`.

**Interfaces:**
- `migrate.shorten(record: dict) -> dict` - a legacy URS record → short file: its single (or `--view`-named) view's `include[].achievements` in order → `bullets` (only `ach_` the career holds), `skills`, `format_profile` → `format`, `region_profile` → `region` code, `budget.pages/ats_maximal_pages` → `pages/ats_pages`, `provenance_floor` → `floor`, its narrative other than `nar_positioning` → `summary`.
- `jsk migrate` (graph workspace): for each `applications/*/resume.json` with a `urs` key and **no** `application.ttl`, write the short file in place (the old one kept as `resume.urs.json` beside it, so nothing is lost) and print one line each. Frozen applications untouched. The markdown-migration path keeps reading old records for id reuse and carried links (`records_of`, `achievements`, `application()`), but `claims_gate` (migrate.py:2023-2048) is replaced by the record gate over the converted short files.
- preflight `verify()`: record gate + render on `EXAMPLE_SHORT`; step names in `tests/test_preflight.py:249` updated ("validate the example resume", "render the example to a PDF").

- [ ] Steps: tests first (a legacy record with a renamed view and an authored narrative shortens to the right keys; a frozen one is left alone; `resume.urs.json` is written), run → fail, implement, run test_migrate/test_preflight → pass, commit `feat: migrate shortens legacy records; doctor renders the example workspace`.

## Phase 3 - Cleanup (after 5-7 merge)

### Task 8: Delete URS

**Files:** Delete `src/jsk/urs/resolve.py`, `src/jsk/urs/plan.py`, `src/jsk/gates/validate_urs.py`, `src/jsk/gates/claims.py`, `src/jsk/data/schema/example.resume.json`, the URS parts of `src/jsk/graph/export.py` (`urs`, `refresh`, `gate_failures`, `skills`, `view`, `region`, `person`, ...), `tests/test_validate_urs.py`, `tests/test_claims.py`, the URS classes in `tests/test_render_resume.py` and `tests/test_graph_export.py`, `tests/fixtures.py`'s `urs_doc/write_urs/achievement/EXAMPLE_URS`, `tests/claims_fixtures/applications/contoso-platform/resume.json` (replaced by a short one). Modify `src/jsk/cli.py` (docstring, `record_refusal`), `src/jsk/paths.py`, `src/jsk/preflight.py` (`SCHEMA_FILES`, `URS_MODULES`), `pyproject.toml` package data.

- [ ] Step 1: `grep -rn "validate_urs\|claims\b\|resolve\|urs_doc\|EXAMPLE_RECORD\|EXAMPLE_URS\|export.urs\|--refresh\|--urs" src tests` → each hit removed or re-pointed.
- [ ] Step 2: full suite `python -m pytest -q -x` and `ruff check src tests` → pass.
- [ ] Step 3: commit - `refactor: remove URS`.

### Task 9: Agents and docs

**Files:** Create `plugins/jsk/skills/jsk/references/resume-format.md`. Delete `references/urs-spec.md`, `references/view-format.md`, `docs/urs-guide.md`. Modify `plugins/jsk/agents/jsk-resume-author.md`, `jsk-verifier.md`, `jsk-kb-auditor.md`, `plugins/jsk/commands/ship.md`, `plugins/jsk/skills/jsk/SKILL.md`, `references/{mode-tailor,mode-resume,mode-ship,mode-setup,README,templates,kb-format,rationale}.md`, `README.md`, `docs/{SCRIPTS,ARCHITECTURE,WHY,CONCEPTS,QUICKSTART}.md`; tests `tests/test_budget.py`, `tests/test_plugin_surface.py`.

- [ ] Step 1: `resume-format.md` - the spec's key table, "the summary is the only prose; a reworded bullet goes into the career", the export commands, `jsk validate`.
- [ ] Step 2: author agent - export the short file; edit `bullets` order, `summary`, `pages`, `format`; everything about refresh, views, include, `grep narratives`, the record's end goes. Budget test `test_the_resume_author_reads_the_view_half_of_the_record_spec` → measures author + resume-format + rules; lower the ceiling with the measured comment.
- [ ] Step 3: every other file per the spec's list; `--view` dropped from every `jsk ship`/`render`/`preview` example; "claims gate" wording → "record gate".
- [ ] Step 4: `python -m pytest -q tests/test_budget.py tests/test_plugin_surface.py` and full suite → pass; commit `docs: the short resume.json; no URS`.

### Task 10: The real workspace

- [ ] Step 1: copy `C:/Projects/basilin-joe-resume/career` to the session scratchpad; `PYTHONPATH=src python -m jsk migrate` there; the five unfrozen drafts shorten, the four frozen untouched.
- [ ] Step 2: in the copy, `jsk validate` + `jsk ship --out` on the ElevenLabs short file; compare the new `.txt` with the old render's `.txt` (`diff`) - differences are only the dropped features, each explained.
- [ ] Step 3: report the diff to the user; convert the real workspace only when they say so.
