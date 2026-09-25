# Remove URS: the resume is built from the career

**Status:** design, 2026-09-25. Supersedes the graph roadmap's "resume.json stays the narrow waist".

## Why

An application's `resume.json` is a 30–47KB URS record copied out of `career/kb.ttl`
(ElevenLabs: 41KB, of which the view and the summary - all anyone authors - are 3KB). The copy is
why the format has an 11KB spec written as a public standard nobody else reads, why agents read
and edit a file that is mostly the career, and why machinery exists only to keep a copy honest:
`--refresh`, alias dropping, hand-flipped provenance, the claims gate's drift checks, a record
gate that mostly checks the shape of a file a program wrote.

`kb.ttl` has been the truth since the graph rewrite. The emitters never read URS: they read the
render **plan** (`resolve.build`'s output). So URS can go entirely: the career and a short
per-application file build the plan, and nothing in between is a format.

```
today   kb.ttl ─export─► resume.json (URS, 41KB) ─resolve─► plan ─► .tex/.pdf/.txt
after   kb.ttl ─┐
                ├─ build ─► plan ─► .tex/.pdf/.txt        (emitters unchanged)
resume.json ────┘  (about 20 lines: what was chosen for this posting)
```

## The short file

`applications/<stem>/resume.json` (or `resume.json` at the workspace root for a general resume):

```json
{
  "resume": 2,
  "format": "presentation",
  "region": "in",
  "pages": 2,
  "ats_pages": 3,
  "floor": "confirmed",
  "summary": { "text": "Full-stack engineer who builds AI agents ...", "status": "inferred" },
  "bullets": ["ach_chloe_care_plan_directed_claude_code", "ach_mindbody_dahua_solo_designed_built"],
  "roles": ["pos_contract_backend"],
  "skills": ["skill_python", "skill_typescript", "skill_react"]
}
```

| key | required | meaning |
|---|---|---|
| `resume` | yes | `2`. |
| `bullets` | yes | `ach_` ids in render order within each role. Projects, roles, employers and their order follow from `kb.ttl`. |
| `format` | no | `presentation` (default) or `ats-maximal`. |
| `region` | no | a profile code; default the person's country, else `default`. |
| `pages`, `ats_pages` | no | page budgets; `pages` defaults to the profile's, then 2. |
| `floor` | no | provenance floor, default `confirmed`: a bullet or summary below it is withheld with a warning. |
| `summary` | no | `{text, status}`, status `inferred` or `confirmed`. Absent: the career's positioning. |
| `roles` | no | `pos_` ids shown with no bullet, for chronology. |
| `skills` | no | `skill_` ids in row order. Absent: every skill, as today. |

An unknown key fails. Every id must be live in `kb.ttl`. The summary is the only prose in the file.

## Components

### `jsk.resume.build` - career + short file → plan

Replaces `resolve.py`. Reads the store (`graph/store.py`) and the short file, returns the same
plan dict the emitters take today, plus `sent`: the bullet ids rendered, for freeze. Behaviour
kept, each reading the graph instead of URS:

- header: name, headline, location, contacts; the work-rights line when the profile asks for it
- summary: the file's, else the positioning; withheld below the floor
- skills rows: the file's ids (else all), grouped by category, deduped, ten a row with a warning
- experience: one entry per employer and kind of work (today's synthesised engagement), roles by
  date with functional titles, each bullet under its project's role, the kind word for contract,
  freelance, internship and volunteer work, the ATS variant's "Title, Org" role lines
- education with grade formatting; credentials; languages where the profile's sections list them
- the IN declaration; ASCII folding for `ats-maximal`; the bracket and withheld warnings; paper
  size by region; the page budget

Dropped, because `kb.ttl` holds no data for them: demographics, photo, referees, availability,
compensation, identity documents, related names, engagement location/summary/domains/via,
career breaks, in-progress credentials, view `redact`/`sections`/`locale`/`target`, and the
region profiles' `forbidden`/`expected`/private-field machinery. A feature comes back by adding
its data to the ontology first.

### Region profiles

`data/schema/profiles/*.json` shrink to what is read: `id`, `region` (paper size), `pages`,
`sections` (order, kb-fed keys only), `declaration`, `work_rights` (render the header line).

### The record gate - `jsk.gates.record`

Replaces `validate_urs.py` and `claims.py` with one gate over the short file and what it selects:

| check | severity |
|---|---|
| shape: unknown key, wrong type, `resume` not 2, no bullets | FAIL |
| an id `kb.ttl` does not hold, a retired one, a bullet whose project has no role | FAIL |
| a number in a selected bullet no current version of a metric it cites holds (untraced), or a replaced version's number (superseded) | FAIL |
| a vocabulary label in a bullet its project does not hold | WARN |
| "N years of X" in the headline, summary or a bullet beyond the roles behind X | WARN |
| a bracket in the summary or a bullet | WARN |

The number check is one function over graph bullets, returning structured results; `jsk kb
check` runs it over every live bullet, and `jsk match` over the posting's (replacing
`gate_failures` and the string parsing in `record_faults`). `Report`/`show` and the numeral
helpers move to `jsk/gates/report.py` and `jsk/gates/numbers.py`; `check_prose`, `store.py` and
`kb.py` import from there.

### Commands

- `jsk validate <resume.json>` runs the record gate.
- `jsk render <resume.json>` / `jsk preview` / `jsk ship <resume.json> --out DIR` find the
  workspace from the file (`kbcli.find_root`) and build. `--view` goes: a file is one resume.
  `jsk ship` runs record gate → render → document gates; there is no separate claims step.
  It refuses in a directory holding `application.ttl`.
- `jsk kb export --from-match <posting.ttl> [--select <ids>] --out <resume.json>` and
  `jsk kb export --select <ids> --out resume.json` write a short file. `--urs` and `--refresh` go.
- `jsk freeze` records `j:carried` / `j:carriedVersion` from the plan's `sent` ids and the short
  file's hash; no copy of the content is written - the PDF, `.txt` and `.tex` are the words sent.
- `jsk migrate` converts a legacy full record in an unfrozen application to a short file (its
  view's include order, skills, format, region, budget, floor, authored narrative). Frozen
  applications' records are left as they are and nothing reads them again.
- `jsk doctor`'s self-check renders a shipped example workspace (`data/example/`: a small
  `kb.ttl` and a short `resume.json`) instead of `example.resume.json`.

### Agents and docs

- `references/resume-format.md` (new, about 40 lines) is the short file's table and rules. It
  replaces `urs-spec.md` and `view-format.md`, both deleted. `docs/urs-guide.md` is deleted.
- `jsk-resume-author.md`: export the short file; reword bullets in the career; edit `bullets`
  order, `summary`, `pages`, `format`; `jsk validate`. Nothing to refresh.
- `mode-tailor.md`: after `jsk kb confirm`, nothing to update - the next ship builds from the
  career; a confirmed summary gets `"status": "confirmed"`.
- `mode-resume.md`, `mode-ship.md`, `mode-setup.md`, `SKILL.md`, `jsk-verifier.md`,
  `jsk-kb-auditor.md`, `commands/ship.md`, `README.md`, `docs/{SCRIPTS,ARCHITECTURE,WHY,CONCEPTS,
  QUICKSTART}.md`: the short file and the one gate where they describe the record.

## Rulings

1. **The plan is the boundary.** The emitters, templates and `jsk fit` are untouched; only what
   builds the plan changes. *If wrong:* nothing downstream moves, so the cost is in the builder.
2. **Renderer features with no data in `kb.ttl` are removed**, not carried as dead branches (the
   list above). *If wrong:* each comes back with its ontology data - AE postings would want
   nationality first.
3. **One record gate replaces the record and claims gates.** The drift checks have nothing to
   compare once there is no copy. *If wrong:* a check is one function to restore.
4. **The alias check goes.** Aliases never render; they only serve `jsk match`. *If wrong:* it
   comes back as a kb WARN.
5. **The file keeps the name `resume.json`**, marked `"resume": 2`.
6. **No legacy reading outside `jsk migrate`.** Unfrozen drafts are converted once; frozen ones
   are the archive and are never rendered again (the PDF is what was sent).
7. **One summary per file**; the career's positioning when absent.

## Order of work

1. **Foundation (one agent, first):** the short file's loader and shape check, the plan builder
   over the graph, a test helper that writes a small `kb.ttl` from Python, and the example
   workspace. Port the plan-level render tests to it.
2. **In parallel:** (a) the record gate + `numbers.py`/`report.py`, wired into validate, ship,
   gates, `kb check` and `match`; (b) export writing short files, freeze and timeline from
   `sent`, the ship guard; (c) migrate's conversion and doctor's example.
3. **Then:** delete `resolve.py`, `validate_urs.py`, `claims.py`, `export.urs`/`refresh`, the
   URS docs and their tests; rewrite agents and docs; re-measure the budget tests.
4. **Convert the real workspace's five unfrozen drafts** with `jsk migrate`, on a copy first.

## Testing

Plan-level tests (about 60 in `test_render_resume.py` and `test_themes.py`) move to the graph
helper and keep their assertions. URS structure tests (`test_validate_urs.py`, most of
`test_claims.py` and `test_graph_export.py`) are replaced by `test_record_gate.py` and
`test_build.py`, keeping every (b)-class case: numbers untraced and superseded, periods, labels,
years. File-based suites (`test_ship_freeze.py`, `test_cli.py`) switch to short files over
`claims_fixtures`. The ElevenLabs run's six untraced numbers become a record-gate test.
