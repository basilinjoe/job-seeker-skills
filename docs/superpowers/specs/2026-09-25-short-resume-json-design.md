# resume.json holds only what was authored

**Status:** design, 2026-09-25. Supersedes the roadmap's "resume.json stays the narrow waist".

## Why

An application's `resume.json` is a 30–47KB copy of `career/kb.ttl` (ElevenLabs: 41KB, of which
the view and the summary - the only parts anyone authors - are 3KB). The copy is why the format
needs an 11KB spec, why agents read and edit a file that is mostly the career, and why a family of
machinery exists only to keep a copy honest: `--refresh`, alias dropping, hand-flipped provenance,
the claims gate's drift checks. `kb.ttl` has been the truth since the graph rewrite; the renderer
and the gates already take an in-memory dict, and `export.urs()` already builds it.

## The design

### The file

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
| `resume` | yes | `2`. Marks this shape; a legacy full record carries `urs` instead. |
| `bullets` | yes | `ach_` ids, render order. Their projects, roles and employers follow from `kb.ttl`. |
| `format` | no | `presentation` (default) or `ats-maximal`. |
| `region` | no | a profile code (`in`, `au`, `ae`, ...); default: the person's country, else the default profile. |
| `pages`, `ats_pages` | no | page budgets; `pages` defaults to 2. |
| `floor` | no | provenance floor; default `confirmed`. |
| `summary` | no | `{text, status}`, `status` `inferred` or `confirmed`; absent means the career's positioning. |
| `roles` | no | `pos_` ids to show with no bullet, for chronology. |
| `skills` | no | `skill_` ids, row order; absent means every skill, as today. |

An unknown key fails. Every id must be live in `kb.ttl`. Nothing else is in the file.

### Assembly

`src/jsk/graph/assemble.py`:

- `assemble(store, short, today) -> dict` - the full URS dict the renderer and gates read today.
  Bullets are grouped under their `kb.ttl` project in list order (a project's position is its
  first bullet's); `export.urs()` is driven with that `Selection` plus `roles`, so employers,
  roles, periods, metrics and provenance come out exactly as export writes them now. It adds one
  view, `view_resume`, from the file's settings, and the summary as `nar_summary`.
- `load_record(path) -> dict` - the one way a command opens a record. `resume: 2` → find the
  workspace (`kbcli.find_root`), load the store, assemble. `urs` → the legacy full record, as is.
  Anything else → a refusal naming the fix.

Every command that opens a record from disk calls `load_record`: `validate_urs.load_target`,
`claims.main`/`load_record`, `render_resume.main`, `cli.cmd_freeze`. `jsk ship`, `jsk gates`
and `jsk preview` pass paths to those, so they follow. The renderer, the emitters, the record
gate's checks and the claims gate's checks are unchanged: they see the dict they see today.

### The record gate on a short file

`jsk validate resume.json` checks the short file's shape and ids first (unknown key, a bullet not
an `ach_`, an id `kb.ttl` does not hold or retired, a bullet whose project has no role), then
runs the existing checks on the assembled dict. A number no metric backs is then a fault in
`kb.ttl` - which is what it always was.

### Writing it

- `jsk kb export --from-match <posting.ttl> [--select <ids>] --out <resume.json>` writes a short
  file: the selection's bullets and skills, the person's region, no summary.
- `jsk kb export --select <ids> --out resume.json` (a general resume) writes one the same way.
- `jsk kb export --upgrade <resume.json>` rewrites a legacy full record as a short file in place:
  the view's `include` order becomes `bullets`, its `skills`, `format_profile`, `region_profile`,
  `budget` and `provenance_floor` their keys, an authored narrative the `summary`. It replaces
  `--refresh`, which only existed to keep a copy current.
- `jsk kb export --urs [--select ...]` with no `--out` still prints a full record, for inspection.

### Freeze and ship

- `jsk freeze` reads the short file, assembles it for the carried bullets and metric versions
  (as now, from the dict), and hashes the short file's bytes into `recordSha256`. No assembled
  copy is written: the PDF, `.txt` and `.tex` are the words sent, `application.ttl` the carried
  ids and versions.
- `jsk ship` refuses in a directory that holds `application.ttl`: re-rendering a frozen
  application from today's career would overwrite the PDF that was sent.
- `--view` becomes optional for a record with one view (every short file; most legacy ones).

### Agents and docs

- `references/resume-format.md` (new, about 40 lines): the table above, the normative rule (no
  content text but the summary), and the three export commands. It replaces `view-format.md`.
  `urs-spec.md` stays as the internal reference for the assembled shape; no agent is sent to it.
- `jsk-resume-author.md`: export the short file; reword bullets in the career first; edit
  `bullets` order, `summary`, `pages`, `format`; `jsk validate`. The export/refresh/record-reading
  paragraphs go.
- `mode-tailor.md` step 5: after `jsk kb confirm`, nothing to bring up to date - the next ship
  assembles from the career; a confirmed summary gets `"status": "confirmed"`.
- `mode-resume.md`, `mode-ship.md`, `mode-setup.md`, `SKILL.md`, `jsk-verifier.md`,
  `docs/SCRIPTS.md`, `docs/ARCHITECTURE.md`: the short file where they describe the record.

## Rulings

1. **The name stays `resume.json`**, the shape marked by `"resume": 2`. Renaming would touch
   every doc and command for no reader's benefit. *If wrong:* a rename later is mechanical.
2. **Legacy full records keep working everywhere** - the four frozen ones, the five unfrozen
   drafts, `example.resume.json` (doctor's self-check) and the test fixtures - so the renderer's
   and validator's tests stand. *If wrong:* the legacy path is one branch in `load_record`,
   removable once nothing carries `urs`.
3. **`--upgrade` replaces `--refresh`.** *If wrong:* you keep a mode for maintaining copies.
4. **The claims gate is not trimmed now.** It runs on the assembled dict; most checks become
   trivially true, and the years check on the summary still matters. Trimming is a later cleanup.
5. **Dropped from the authored surface:** view `redact`, `sections`, `locale`, `label`, `target`,
   `include[].order`, several views per file. Nothing exported writes them; a legacy record keeps
   them. *If wrong:* each is one optional key.
6. **One summary per file**, `nar_summary`; the career's positioning when absent.

## Out of scope

Pruning the URS in-memory shape (approach A), trimming the claims gate, converting the real
workspace's drafts (run `--upgrade` on them when wanted).

## Testing

`tests/test_assemble.py`: assemble a short file over `claims_fixtures` and compare with
today's export for the same selection; every shape and id refusal; legacy passthrough; order of
bullets, projects, roles; summary absent and present. The file-based suites (`test_ship_freeze`
`GraphCase`, `test_cli` gates, `test_graph_export` `Command`) gain short-file cases; `Refresh`
becomes `Upgrade`. Budget tests re-measure the author and main-thread reading.
