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
   +--> emit_latex.py  -->  .tex  -->  .pdf
   +--> emit_docx.py   -->  presentation .docx + ATS-maximal .docx
   +--> emit_text.py   -->  .txt
```

**The narrow waist is the design.** Every content decision happens once, in the plan. The emitters
translate a resolved plan into markup and decide nothing. That is what guarantees the `.docx` and the
PDF cannot say different things — neither of them chose what to say.

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

## Repo layout

```
.claude-plugin/marketplace.json     marketplace manifest (carries a version)
docs/                               this directory — human-facing documentation
plugins/career-okf/
  .claude-plugin/plugin.json        plugin manifest (carries a version)
  commands/                         slash commands
    setup.md                        the four-phase setup procedure
    braindump|resume|tailor|...     thin delegations into the skill's modes
  skills/career-okf/
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
    scripts/                        the nine tools, plus the urs/ package
      okf.py                        one entry point that forwards to the nine
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
| Bundle layout | `scripts/init_bundle.py` | `scripts/validate_bundle.py`, `references/bundle-spec.md` |
| How postings are scored | `scripts/score_projects.py` | `references/target-template.md` |
| A mode's procedure | `references/mode-<name>.md` | the routing table in `SKILL.md` |
| Add a mode | a new `references/mode-<name>.md` | routing table in `SKILL.md`, a `commands/<name>.md` |

## What is frozen

This is a published plugin. Three surfaces may not move without a major version and a migration
story:

1. **Script names and CLI flags.** `check_ats.py`, `--strict`, `--level N` and the rest are public
   API — they appear in shell histories, in README examples, and in bundles that copied them.
   Internals are free; the invocation surface is not.
2. **Bundle layout on disk.** Renaming `projects/` breaks every bundle already in existence.
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

Deliberately close to zero. `preflight.py`, `validate_urs.py`, `render_resume.py`, `check_ats.py`,
`check_prose.py` and `init_bundle.py` run on a bare Python — `preflight.py` especially, because a
preflight that needs installing first is not a preflight.

| Optional | Unlocks |
|---|---|
| `pyyaml` | reading the bundle at all: `validate_bundle.py`, `score_projects.py` |
| `jsonschema` | full schema validation in `validate_urs.py` (structural rules run without it) |
| a TeX engine | the PDF, and therefore the render gate |
| LibreOffice + `pymupdf` | page measurement in `fit_pages.py` |

Anything that cannot run reports loudly and exits non-zero rather than passing quietly.

## Releasing

The version lives in **two** files and they must agree:

- `plugins/career-okf/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Before tagging: run the tests, run `preflight.py --verify`, and check that every internal doc link
still resolves.

---

Next: [Why it works this way](WHY.md) · [Scripts](SCRIPTS.md)
