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

`formatting.py` holds pure functions over single values — no view, no profile, no record — which is
what makes them testable in isolation. Import `plan`; the split is behind it.

## The agent boundary

Three tasks are delegated to subagents. The line between what an agent does and what the main
conversation does is the same line the pipeline draws elsewhere: **agents read, measure and report;
the conversation decides and writes.**

| Agent | Has | Deliberately lacks |
|---|---|---|
| `jsk-verifier` | Bash, Read, Glob | Write and Edit — a defect is fixed in `resume.json` and re-rendered, never patched into the render |
| `jsk-bundle-auditor` | Read, Glob, Grep, Bash | Write and Edit — a `status` flips only when the person says so |
| `jsk-posting-analyst` | Read, Write, Edit, Glob, Grep, Bash | nothing structural; it writes the target file, which is a checkpoint, and never `resume.json` |

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
    jsk-verifier.md                 runs the four gates on rendered files, reports verbatim
    jsk-bundle-auditor.md           reads the whole bundle, returns a prioritised gap queue
    jsk-posting-analyst.md          decomposes a posting, writes the target, runs the scorer
  skills/jsk/
    SKILL.md                        the agent's entry point: routing + hard rules
    references/                     what the agent loads on demand
      README.md                     index of everything below
      mode-*.md                     one procedure per mode
      bundle-spec.md                bundle layout, frontmatter schema, selection keys
      urs-spec.md                   the normative record format
      ats-rules.md                  hard rules, two-variant strategy, keyword placement
      writing-rules.md              X-Y-Z bullets, verb accuracy, phrases to cut
      target-template.md            Job Target frontmatter the scorer reads
      rationale.md                  long-form reasoning, loaded to explain a rule
    schema/
      urs-v1.schema.json            JSON Schema for the record
      profiles/*.json               region profiles: default, au, in, ae
      example.resume.json           a complete worked document
    scripts/                        the eleven tools, plus the urs/ package
      okf.py                        one entry point that forwards to the eleven
      migrate_bundle.py             moves an older bundle to the current layout revision
      pipeline.py                   the weekly board, derived from application timelines
      pipeline_model.py             what a timeline event means - the only module that decides
tests/                              unittest, one file per script
```

## Where do I change X

| To change | Edit | And also |
|---|---|---|
| What the parse gate rejects | `scripts/check_ats.py` | `references/ats-rules.md`, `tests/test_check_ats.py` |
| What the prose gate rejects | `scripts/check_prose.py` | `references/writing-rules.md`, `tests/test_check_prose.py` |
| What makes a record invalid | `scripts/validate_urs.py` | `schema/urs-v1.schema.json`, `references/urs-spec.md` |
| **What content is selected** | `scripts/urs/plan.py` | never an emitter |
| **How a document looks** | `scripts/urs/emit_*.py` | never `plan.py` |
| Support for a new market | `schema/profiles/<code>.json` | the region section of `references/urs-spec.md` |
| Bundle layout | `scripts/init_bundle.py` | `scripts/validate_bundle.py`, `references/bundle-spec.md`, **a new revision in `migrate_bundle.py`** |
| What a migration does | `scripts/migrate_bundle.py` | `docs/SCRIPTS.md`, `tests/test_migrate_bundle.py` |
| **What a timeline event means** | `scripts/pipeline_model.py` | never in a caller — `pipeline.py`, `validate_bundle.py` and `migrate_bundle.py` all read it |
| How postings are scored | `scripts/score_projects.py` | `references/target-template.md` |
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
   failing on the older shape. `BUNDLE_REVISION` in `init_bundle.py` must move in the same commit —
   new bundles are born current, and a bundle that lies about its revision is worse than one that
   carries no stamp at all.
3. **The URS schema and gate behaviour.** `urs-v1.schema.json` stays wire-compatible, and a gate
   keeps failing on exactly what it fails on today.

A fourth, discovered the hard way: **the tests assert on output text.** There are 108 `assertIn`
calls against strings like `PASS - safe to send` and `DO NOT SEND`. You may *add* lines to a script's
output. Rewording an existing verdict line breaks tests, and those tests are the gate on the gate.

## Tests

```bash
python -m unittest discover -s tests
```

Standard library `unittest`. Fixtures are generated into temp directories; nothing is committed.
Every test pins a specific documented rule — the checker is the gate, so it does not go unchecked.

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
