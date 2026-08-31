# Architecture

For anyone editing this repo. If you only want to *use* the plugin, read
[Quickstart](QUICKSTART.md) instead.

## The one-way pipeline

```
bundle (Markdown + YAML frontmatter)
   |
   |  read by the skill, with the person in the loop
   v
resume.json  (URS record)
   |
   |  urs/plan.py resolves it exactly once:
   |  selection, ordering, provenance filtering,
   |  region gating, ASCII folding, date formatting
   v
render plan
   |
   +--> emit_latex.py  -->  .tex  -->  .pdf   (the deliverable; --ats-max picks the variant)
   +--> emit_text.py   -->  .txt          (paste-in boxes)
```

**The narrow waist is the design.** Every content decision happens once, in the plan. The emitters
translate a resolved plan into markup and decide nothing. That is what guarantees the PDF and the
plain text cannot say different things — neither of them chose what to say.

`emit_docx.py` used to sit alongside them and produced two more files. It went because the same
argument applies one level up: `fit_pages.py` measured the `.docx` through LibreOffice while the PDF
was what got sent, they disagreed, and a resume reported as two pages shipped as three. There is now
one rendered deliverable, and the thing measured is the thing sent.

If you find yourself making a content decision inside an emitter, it belongs in the plan. If you find
yourself making a formatting decision inside the plan, it belongs in an emitter.

### Inside the `urs` package

`plan.py` is a facade over a second seam:

| Module | Decides |
|---|---|
| `plan.py` | nothing — the public face. `from urs import plan`, `plan.build(...)` |
| `resolve.py` | *what* the document says: selection, ordering, provenance filtering, region gating |
| `formatting.py` | *how* one value reads: dates, grades, quantities, the fold to ASCII |
| `profiles.py` | region profile loading and the gate that applies it |
| `emit_*.py` | markup only |
| `themes.py` | *appearance* only: palette, typeface, rhythm. Below `emit_latex.py`, and it cannot reach the text |

`formatting.py` holds pure functions over single values — no view, no profile, no record — which is
what makes them testable in isolation. Import `plan`; the split is behind it.

## The agent boundary

Four tasks are delegated to subagents. The line between an agent and the main conversation is
**Write versus Edit**: an agent writes its own analysis, and only the conversation edits the person's
record. A `status` that flips without them saying so is the defect this framework exists to prevent.

| Agent | Has | Deliberately lacks |
|---|---|---|
| `jsk-verifier` | Bash, Read, Glob | Write and Edit — a defect is fixed in `resume.json` and re-rendered, never patched into the render |
| `jsk-bundle-auditor` | Read, Write, Glob, Grep, Bash | Edit — it writes an audit; a concept is the person's |
| `jsk-tailor-analyst` | Read, Write, Edit, Glob, Grep, Bash | nothing structural; it writes the posting's requirements and the assessment, never a concept |
| `jsk-resume-author` | Read, Write, Edit, Glob, Grep, Bash | nothing structural — and it is the one that writes prose |

`jsk-verifier` is the conditional one. `okf gates` runs the record, parse and prose gates in a single
process and prints each one's output verbatim, so a clean ship reads that rather than spawning an
agent to relay three checkers — and a script has no Write tool more thoroughly than an agent does.
What the agent is kept for is the half a command cannot do: reading a `FAIL` line back to the concept
it came from, and reading the PDF for the render gate.

`jsk-resume-author` is the exception worth understanding. It authors the narrative, the retuned
summary and the view, so restraint alone would not be enough. Everything it writes is marked
`inferred`, and a view with `provenance_floor: confirmed` means `validate_urs.py` refuses to render
it until a person has confirmed each clause. **The guarantee lives in the record gate, not in the
agent.**

Two consequences worth keeping in mind when editing them:

1. **A subagent's output never reaches the person.** Every agent is told to return checker verdicts
   and quoted claims verbatim, and every calling mode is told to relay rather than summarise. Break
   either half and the "show the output" rule quietly stops holding.
2. **Nothing may depend on an agent existing.** The mode files carry the full inline procedure, so
   the skill works unchanged in an environment with no subagents. An agent is a context optimisation,
   not a step.

## Repo layout

```
.claude-plugin/marketplace.json     marketplace manifest (carries a version)
docs/                               this directory — human-facing documentation
plugins/jsk/
  .claude-plugin/plugin.json        plugin manifest (carries a version)
  commands/                         slash commands
    setup.md                        the four-phase setup procedure
    braindump|resume|tailor|...     thin delegations into the skill's modes
  agents/                           subagents the modes delegate to
    jsk-verifier.md                 interprets a failed gate against the record; not spawned by a clean ship
    jsk-bundle-auditor.md           reads the whole bundle, writes a posting-less audit
    jsk-tailor-analyst.md           reads a posting and the compiled record, writes the assessment
    jsk-resume-author.md            authors the tailored record: narrative, summary, view
  skills/jsk/
    SKILL.md                        the agent's entry point: routing + hard rules
    references/                     what the agent loads on demand
      README.md                     index of everything below
      mode-*.md                     one procedure per mode
      bundle-spec.md                bundle layout, frontmatter schema, selection keys
      urs-spec.md                   the shape the record compiles to, and the region profiles
      view-format.md                the other half of URS: every key a view may carry
      ats-rules.md                  hard rules, two-variant strategy, keyword placement
      writing-rules.md              X-Y-Z bullets, verb accuracy, phrases to cut
      rationale.md                  long-form reasoning, loaded to explain a rule
    schema/
      profiles/*.json               region profiles: default, au, in, ae
      profile.schema.json           what a region profile must contain
      example.resume.json           one complete worked record
    scripts/                        the thirteen tools, plus the urs/ package
      okf.py                        one entry point that forwards to the rest
      preview_templates.py          one record in every template, so the look is chosen by looking
      migrate_bundle.py             moves an older bundle to the current layout revision
      pipeline.py                   the weekly board, derived from application timelines
      pipeline_model.py             what a timeline event means - the only module that decides
tests/                              unittest: one file per script, plus the manifest surface
  fixtures.py                       temp bundles and records; nothing here is committed
```

## Where do I change X

| To change | Edit | And also |
|---|---|---|
| What the parse gate rejects | `scripts/check_ats.py` | `references/ats-rules.md`, `tests/test_check_ats.py` |
| What the prose gate rejects | `scripts/check_prose.py` | `references/writing-rules.md`, `tests/test_check_prose.py` |
| What makes a record invalid | `scripts/validate_urs.py` | `references/urs-spec.md`, `tests/test_validate_urs.py` |
| **What content is selected** | `scripts/urs/plan.py` | never an emitter |
| **How a document looks** | `scripts/urs/emit_*.py` | never `plan.py` |
| **A palette, typeface or rule** | `scripts/urs/themes.py` | `references/templates.md`, `tests/test_themes.py` |
| Support for a new market | `schema/profiles/<code>.json` | the region section of `references/urs-spec.md` |
| What a view may carry | `references/view-format.md` | `scripts/validate_urs.py`, `agents/jsk-resume-author.md` — never `references/urs-spec.md`, which defines no view key |
| Bundle layout | `scripts/init_bundle.py` | `scripts/validate_bundle.py`, `references/bundle-spec.md`, **a new revision in `migrate_bundle.py`** |
| What a migration does | `scripts/migrate_bundle.py` | `docs/SCRIPTS.md`, `tests/test_migrate_bundle.py` |
| **What a timeline event means** | `scripts/pipeline_model.py` | never in a caller — `pipeline.py`, `validate_bundle.py` and `migrate_bundle.py` all read it |
| How the record is built | `scripts/okf_compile.py` | `references/bundle-spec.md`, `tests/test_okf_compile.py` — and the render test, which is what a schema used to do |
| How postings are scored | `scripts/score_projects.py` | `agents/jsk-tailor-analyst.md` (it writes the requirements), `tests/test_score_projects.py` |
| A posting's or assessment's shape | `agents/jsk-tailor-analyst.md` | `references/mode-tailor.md` — the format is written out in the agent, so it is one place |
| A mode's procedure | `references/mode-<name>.md` | the routing table in `SKILL.md` |
| What an agent may do | `plugins/jsk/agents/<name>.md` | the delegation note in every mode that calls it, and the Agents table in `SKILL.md` |
| Add a mode | a new `references/mode-<name>.md` | routing table in `SKILL.md`, a `commands/<name>.md` |

## What is frozen

This is a published plugin. Three surfaces may not move without a major version and a migration
story:

1. **Script names and CLI flags.** `check_ats.py`, `--strict`, `--level N` and the rest are public
   API — they appear in shell histories, in README examples, and in bundles that copied them.
   Internals are free; the invocation surface is not.
2. **Bundle layout on disk.** Renaming `projects/` breaks every bundle already in existence.
   Layout *additions* are allowed, but only behind a revision: bump `CURRENT_REVISION` in
   `migrate_bundle.py`, teach it the step, and keep `validate_bundle.py` **warning** rather than
   failing on the older shape. `BUNDLE_REVISION` in `init_bundle.py` and `CURRENT_BUNDLE_REVISION`
   in `validate_bundle.py` must move in the same commit — all three are pinned to each other by
   `tests/test_plugin_surface.py`, because new bundles are born current and a bundle that lies about
   its revision is worse than one that carries no stamp at all.
3. **The compiled record's shape and gate behaviour.** What `okf_compile.py` hands the renderer
   stays wire-compatible with an archived `resume.json`, and a gate keeps failing on exactly what
   it fails on today.

A fourth, discovered the hard way: **the tests assert on output text.** There are over 240 `assertIn`
calls against strings like `PASS - safe to send` and `DO NOT SEND`. You may *add* lines to a script's
output. Rewording an existing verdict line breaks tests, and those tests are the gate on the gate.

## Tests

```bash
python -m pytest tests -q                  # the whole suite, under two minutes
python -m pytest tests/test_themes.py -q   # one file, while you are working on it
python -m unittest discover -s tests       # the same tests, with no pytest installed
```

The tests are standard-library `unittest` and import nothing from pytest; pytest is simply the
pleasanter way to run a subset and read a failure. Either command works from anywhere — every path
in `tests/fixtures.py` is resolved from the test file's own location, not from the working
directory.

Most of that time is TeX — 542 tests, and the ones that dominate the clock compile real PDFs and
extract their text layers, because the claim they check — five templates, one document — cannot be
checked any other way. Where a TeX engine or `pymupdf` is absent those tests skip themselves, so a
bare-Python run finishes in seconds on fewer assertions rather than failing on the machine's setup.

Fixtures are built into temp directories by `tests/fixtures.py`; nothing is committed. Every test
pins a specific documented rule — the checker is the gate, so it does not go unchecked.

A failing test after a refactor means the refactor was wrong. Do not edit a test to accommodate a
change in behaviour unless the behaviour change is the point and it is written down.

## Dependencies

Deliberately close to zero. `preflight.py`, `validate_urs.py`, `render_resume.py`, `check_prose.py`
and `init_bundle.py` run on a bare Python — `preflight.py` especially, because a preflight that needs
installing first is not a preflight. `check_ats.py` does too when given the `.txt`; only reading a PDF
needs `pymupdf`.

| Optional | Unlocks |
|---|---|
| `pyyaml` | reading the bundle at all: `validate_bundle.py`, `score_projects.py` |
| `jsonschema` | full schema validation in `validate_urs.py` (structural rules run without it) |

| Required | Why |
|---|---|
| a TeX engine | the PDF is the only rendered deliverable; without one there is nothing to send |
| `pymupdf` | without it the parse gate and the page budget are both unverifiable |

A TeX engine and `pymupdf` were optional while the `.docx` was the portal artefact. `preflight.py`
now reports their absence as BLOCKED rather than a gap. LibreOffice left the list entirely: it
existed only to render the `.docx` for measurement.

Anything that cannot run reports loudly and exits non-zero rather than passing quietly.

## Releasing

The version lives in **two** files and they must agree:

- `plugins/jsk/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Before tagging: run the tests, run `preflight.py --verify`, and check that every internal doc link
still resolves.

---

Next: [Why it works this way](WHY.md) · [Scripts](SCRIPTS.md)
