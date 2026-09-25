# Architecture

For anyone editing this repo. If you only want to *use* the plugin, read
[Quickstart](QUICKSTART.md) instead.

## The one-way pipeline

```
career/kb.ttl  (the graph record: one Turtle file, fixed sections, validated on every load)
   |
   |  changed through `jsk kb apply` changesets, read by id with `jsk kb show`,
   |  matched against a posting.ttl by `jsk match` - the person in the loop throughout
   |
   +---------------------+
   |                     |  resume.json  (the short file, one per application: bullet ids in
   |                     |  order, skills, format, region, budgets, floor, a summary - no copy
   |                     |  of the career; `jsk kb export` writes it, `jsk validate` gates it)
   v                     v
resume/build.py builds the plan exactly once:
   selection, ordering, provenance filtering, region, ASCII folding, date formatting
   v
render plan
   |
   +--> emit_latex.py  -->  .tex  -->  .pdf   (the deliverable; --ats-max picks the variant)
   +--> emit_text.py   -->  .txt          (paste-in boxes)
```

**The render plan is the narrow waist.** Every content decision happens once, in the builder. The
emitters translate a finished plan into markup and decide nothing. That is what guarantees the PDF
and the plain text cannot say different things — neither of them chose what to say.

`resume.json` used to be the waist: a URS record, a full copy of the career written out per
application, with an 11KB specification of its own. The emitters never read it - they read the
plan - so the copy went (2026-09-25, `docs/superpowers/specs/2026-09-25-short-resume-json-design.md`).
The career and the short file build the plan directly, and nothing between them is a format.
`references/resume-format.md` is the short file's every key.

The same argument applies one level up, which is why there is one rendered deliverable: the thing
`jsk fit` measures is the thing that gets sent. A `.docx` measured through LibreOffice beside the
PDF once reported two pages for a resume that shipped as three.

If you find yourself making a content decision inside an emitter, it belongs in the builder. If you
find yourself making a formatting decision inside the builder, it belongs in an emitter.

### The commands over it

```
jsk new       PATH --name NAME                     career/kb.ttl and log.ttl at r1, applications/
jsk kb        apply changes.trig                   the career changed: validated, written, logged
jsk match     applications/D/posting.ttl           the posting against the career, with the paths
jsk kb        export --from-match P --out R.json   the short resume.json, chosen from the match
jsk validate  resume.json                          the record gate - before anything renders
jsk render    resume.json --out D --pdf            .tex, .pdf, .txt
jsk gates     D                                    record, parse and prose gates over that render
jsk ship      resume.json --out D                  the gates above and the render, in order, in one process
jsk freeze    D --submitted DATE --channel TEXT    application.ttl, once the gates pass
jsk event     D KIND --date DATE                   what came back, added to application.ttl
```

`jsk ship <resume.json> --out DIR [--ats-max] [--template N] [--pages N] [--json]` is the path a
finished resume takes. The record gate runs first, and a failure stops it: nothing renders, because
a render of a resume that failed would be a document nobody should read. Then `render --pdf`, then the parse and prose gates over the output directory,
each step's output printed verbatim. It exits 0 only if every step passed. With `--pages` it reports
the measured page count and never fails on it — `jsk fit` owns that verdict and is the only thing
that can act on it. It closes by saying the render gate is still open, because a person reading the
PDF is the one gate no command can run. It refuses in a frozen application (`application.ttl`
beside the file or in `--out`): re-rendering would overwrite what was sent.

`jsk freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--doc FILE ...]` is the last
step. It refuses unless the mechanical gates pass and no application archive exists yet, then
writes `application.ttl` — what was sent, the `resume.json` hash, the bullets that rendered (the
plan's `sent`) and the metric versions they cite — and renames the directory to the submitted date.
No copy of the content is written: the PDF, `.txt` and `.tex` beside it are the words sent. After that the directory is
an archive: later events are added with `jsk event`, never edited. A workspace still on
`user-knowledgebase.md` is refused until it migrates.

Every subcommand runs **in process**. `cli.py` imports the module behind it and calls its `main()`
with the same arguments, so the output and the exit code are the module's own and nothing is
paraphrased on the way through. One interpreter per invocation is what lets `jsk ship` be a single
command rather than four start-ups; `call_gate()` turns the two failures an in-process call adds — a
module that will not import, and one that raises where it should have returned a verdict — into a
reported failure instead of a traceback.

### Inside the `resume` package

| Module | Decides |
|---|---|
| `short.py` | the short file: `read` (refuses a legacy URS record, naming `jsk migrate`), `workspace` (by `kbcli.find_root`, never `dirname`), `shape` and `ids` - the FAIL lines the record gate and the builder share |
| `career.py` | reading the career graph: `Career`, employers and their roles by date, periods. Shared with export, select and match |
| `build.py` | *what* the document says: `build(store, doc)` returns the plan; `from_path(path)` reads, checks and builds |

### The render plan

The one internal format, and what every emitter, `themes.py` and `jsk fit` read. A dict:

| key | holds |
|---|---|
| `view` | `"resume"` - kept for the emitters' file naming |
| `format` | `presentation` or `ats-maximal` |
| `profile`, `region`, `pages` | the region profile's id, the region (paper size), the page budget |
| `name`, `headline`, `header_lines` | the header, as finished strings |
| `sections` | in the profile's order, each `{"kind", "heading", ...}`: `text` (`paragraphs`), `rows` (`rows` of `{label, items}`), `entries` (each `{org_line, org_right, roles: [{left, right, bullets}], lines, bullets}`), `lines` (`lines`); the declaration is a `lines` section with no heading |
| `warnings` | withheld lines, brackets, a skills row cut at its limit - printed by `jsk render` as `warn` lines |
| `sent` | the `ach_` ids that rendered, in order - what `jsk freeze` records as carried |

Every string in it is final: folded to ASCII for `ats-maximal`, dates formatted, below-floor lines
already dropped. A new section kind is a builder method and a branch in each emitter; a key the
emitters do not read is dead.

### Inside the `urs` package

The renderer: everything after the plan, and the three CLIs.

| Module | Decides |
|---|---|
| `formatting.py` | *how* one value reads: dates, grades, quantities, the fold to ASCII |
| `profiles.py` | region profile loading |
| `emit_*.py` | markup only |
| `themes.py` | *appearance* only: palette, typeface, rhythm. Below `emit_latex.py`, and it cannot reach the text |
| `render_resume.py` · `preview_templates.py` · `fit_pages.py` | the CLIs — `jsk render`, `jsk preview`, `jsk fit`. They orchestrate the modules above and decide nothing themselves |

`render_resume.py` reaches the career only through `resume.build`, lazily. `formatting.py` holds
pure functions over single values — no profile, no career — which is what makes them testable in
isolation.

### Inside the `graph` package

The career record. It reads and writes Turtle files and never renders anything; the rendering half
never imports it. Every module keeps `pyoxigraph` inside its functions, so importing the package
costs nothing on a machine without the engine and `jsk doctor` can report on it.

| Module | Decides |
|---|---|
| `ontology.py` | **the format**: every class, predicate, cardinality, datatype, enum and section, as data. Standard library only. The single definition - the writer, the rules and the format reference all follow it |
| `io.py` | parsing Turtle and TriG, CRLF normalised, a file's sha256, and a failure's file:line |
| `writer.py` | the one canonical layout: prefix block, section banners, subjects by class then natural key, predicates in ontology order, `"""` prose never reflowed. pyoxigraph parses and queries; it never writes a record |
| `shapes.py` · `rules.py` | tier 1, generated from the ontology (closed predicates, required, cardinality, datatype, enum, id prefix); tier 2, the cross-node rules, each a SPARQL query with a fix, each with a mutation test |
| `store.py` | a workspace in memory: one named graph per file, derived triples in `j:derived`, every rule run on every load |
| `record.py` | kb.ttl and log.ttl kept in step: revision, hash, `state` (clean, hand-edited, torn, ...), `prepare` and `commit` |
| `changeset.py` · `edit.py` · `kbcli.py` | `jsk kb`: a changeset read and refused or merged, and every verb over the record |
| `queries.py` · `named.py` · `match.py` | the vocabulary and the named questions; `jsk match` |
| `view.py` · `timeline.py` | `jsk kb view`; `jsk freeze`'s application.ttl and `jsk event` |

**Its boundaries.** A write to `career/kb.ttl` goes only through `record.prepare` and
`record.commit`, after the would-be workspace validates - `kbcli.write_logged`, `jsk new` and
`jsk migrate` are the three callers, and all three write r1 or the next revision with a log entry.
Outward it has three edges, all lazy: `gates.report` for `Report` and `show` (one way to print a
finding), `gates.numbers` for the untraced-number check `jsk kb check` and `jsk match` run over the
career's bullets, and `resume.career` for `Career` (export, select, match). Inward, `resume/` builds
from the store, `gates/record.py` reads it and `cli.py` finds the workspace with `kbcli.find_root`.
Nothing in `urs/` imports it, and nothing in it imports `urs/`.

## The agent boundary

Four tasks are delegated to subagents, and the line between them is what each may write.

| Agent | Has | Deliberately lacks |
|---|---|---|
| `jsk-verifier` | Bash, Read, Glob | Write and Edit — a defect is fixed in the career or `resume.json` and re-rendered, never patched into the render |
| `jsk-kb-auditor` | Read, Write, Glob, Grep, Bash | Edit — it writes an audit from `jsk kb check` and `jsk kb query`; the career is the person's |
| `jsk-tailor-analyst` | Read, Write, Edit, Glob, Grep, Bash | nothing, and that is worth reading below |
| `jsk-resume-author` | Read, Write, Edit, Glob, Grep, Bash | nothing — it is the one that writes prose |

**For the two authoring agents the anti-invention guarantee is not a tool grant.** Both hold Edit,
and what holds them is partly what their files say and partly what the write path refuses:

- `jsk-tailor-analyst` writes `posting.ttl` and the assessment, and **never touches
  `career/kb.ttl`**. That boundary is prose, and `tests/test_plugin_surface.py` asserts the
  sentence is still in the file, which is the most a test can do about a rule of that kind - but a
  hand edit to kb.ttl is also detected on the next load and must be adopted, with every provenance
  it raised listed, before anything can write the record again.
- `jsk-resume-author` reads `jsk match` and `jsk kb show <ids>`, and bullets it writes for the
  career go in through a changeset — they belong in the project they are about, so the next
  application can reuse them. What holds it is not a tool grant: `jsk kb apply` makes every new or
  changed claim `j:inferred` and refuses a changeset asserting `confirmed`; the short file's `floor`
  (`confirmed` by default) means the builder withholds each unconfirmed clause - it prints a
  `withheld` warning rather than failing, so the mode files make every warning a confirm-or-cut
  before hand-over; and `resume.json` holds ids, never a bullet's words, so the record gate fails a
  bullet the career does not hold.
  **The guarantee lives in the gates, not in the agent.**

That asymmetry is the design. Where a rule can be enforced by a gate, it is; where it cannot, it is
stated as plainly as possible and the test checks that the statement survives.

`jsk-verifier` is the conditional one. `jsk ship` and `jsk gates` run the record, parse and
prose gates in a single process and print each one's output verbatim, so a clean ship reads that rather
than spawning an agent to relay three checkers — and a command has no Write tool more thoroughly than
an agent does.
What the agent is kept for is the half a command cannot do: reading a `FAIL` line back to the section
it came from, and reading the PDF for the render gate.

Two consequences worth keeping in mind when editing them:

1. **A subagent's output never reaches the person.** Every agent is told to return checker verdicts
   and quoted claims verbatim, and every calling mode is told to relay rather than summarise. Break
   either half and the "show the output" rule quietly stops holding.
2. **Nothing may depend on an agent existing.** The mode files carry the full inline procedure, so
   the skill works unchanged in an environment with no subagents. An agent is a context optimisation,
   not a step.

## Repo layout

```
pyproject.toml                      the jsk-resume package: deps, console script, ruff, pytest
.claude-plugin/marketplace.json     marketplace manifest (carries a version)
docs/                               this directory - human-facing documentation
src/jsk/                            THE CLI. one installed package, `jsk` on the command line
  __init__.py                       __version__
  __main__.py                       `python -m jsk`, the same entry point as `jsk`
  cli.py                            the dispatcher: fourteen subcommands, each run in process
  cliutil.py                        one contract for --help across the hand-rolled entry points
  paths.py                          where the packaged schema lives - stated once
  kb.py                             `jsk new` - scaffolds career/kb.ttl, log.ttl at r1, applications/
  migrate.py                        `jsk migrate` - user-knowledgebase.md to the graph, once (until 5.0)
  kbindex.py                        the Markdown reader migrate uses; deleted in release 5.0
  graph/                            the career record: see "Inside the graph package"
    ontology.py                     the format, as data     writer.py     the canonical layout
    io.py  store.py  record.py      parse, load and validate, kb.ttl and log.ttl in step
    shapes.py  rules.py             tier 1 and tier 2 rules
    changeset.py  edit.py  kbcli.py `jsk kb`
    queries.py  named.py  match.py  the vocabulary, named queries, `jsk match`
    select.py  export.py            what a match selects; `jsk kb export` writes the short file
    view.py  timeline.py            `jsk kb view`; application.ttl and `jsk event`
  resume/                           career + resume.json -> the render plan
    short.py                        the short file: read, shape, ids, its workspace
    career.py                       the career graph as the builder, export and match read it
    build.py                        every content decision, made exactly once
  urs/                              plan -> document, and the three CLIs that drive it
    formatting.py                   *how* one value reads      profiles.py   region profiles
    themes.py                       appearance only            tex.py        the engine
    emit_latex.py  emit_text.py     markup only
    render_resume.py                `jsk render` - one resume to .tex/PDF plus .txt
    preview_templates.py            `jsk preview` - every template, so the look is chosen by looking
    fit_pages.py                    `jsk fit` - fits a render to a page budget
  gates/                            the mechanical gates `jsk gates` runs
    record.py                       the record gate - resume.json and the bullets it selects
    numbers.py  report.py           the untraced-number check; one way to print a finding
    check_ats.py                    the parse gate        check_prose.py    the prose gate
  preflight.py                      `jsk doctor`: what this machine can do
  data/vocabulary.ttl               the shipped technology vocabulary (labels, isA, partOf)
  data/example/                     a small career/kb.ttl and a short resume.json: doctor renders it
  data/schema/                      package data, reached through paths.py
    profiles/*.json                 region profiles: default, au, in, ae
    profile.schema.json             what a region profile must contain
plugins/jsk/                        THE SKILL. markdown only - it ships no code
  .claude-plugin/plugin.json        plugin manifest (carries a version)
  commands/                         slash commands
    setup.md                        the four-phase setup procedure
    braindump|resume|tailor|...     thin delegations into the skill's modes
  agents/                           subagents the modes delegate to
    jsk-verifier.md                 interprets a failed gate against the career and resume.json
    jsk-kb-auditor.md               checks and queries the career, writes a posting-less audit
    jsk-tailor-analyst.md           writes posting.ttl and gaps.md from a posting and `jsk match`
    jsk-resume-author.md            bullets into the career, then exports resume.json and its summary
  skills/jsk/
    SKILL.md                        the agent's entry point: routing + hard rules
    references/                     what the agent loads on demand
      README.md                     index of everything below
      mode-*.md                     one procedure per mode
      kb-format.md                  the graph record: every section, class and predicate, and applications/
      resume-format.md              the short resume.json: every key, and the export and gate
      ats-rules.md                  hard rules, two-variant strategy, keyword placement
      writing-rules.md              X-Y-Z bullets, verb accuracy, phrases to cut
      templates.md                  the five visual templates
      rationale.md                  long-form reasoning, loaded to explain a rule
tests/                              unittest: one file per module, plus the manifest surface
  fixtures.py                       the path setup, and helpers every suite shares
  careerkit.py                      a workspace per test: claims_fixtures, edited, with a short file
  graph_fixtures/                   a valid graph workspace: kb.ttl at r2, log.ttl, one application
  kb2_template.md                   the Markdown template `jsk new` used to write, for migrate's tests
```

**The code and the skill are two artefacts.** `src/jsk/` is a Python package installed from PyPI as
`jsk-resume`; `plugins/jsk/` is markdown that calls `jsk`.

**The package owns the career record; the skill writes changesets and short files.** Every write
to `career/kb.ttl` goes through `jsk kb` (or `jsk new` and `jsk migrate`, which write r1), and every
load validates it. The skill exports each `resume.json` from the career and edits its order,
summary and settings, which is why the record gate runs before anything renders: it is the last
point at which a mistake is still cheap.

## What is a package here, and what is not

Three subpackages, and each was measured before it was made. The test is whether the members
import *each other* more than they import outward — a group whose members share no edges is a folder
with a theme, not a module.

| Group | Edges crossing the boundary | Edges inside | Verdict |
|---|---|---|---|
| `urs/` — rendering, preview, page fitter, over the plan→document pipeline | **2**, lazy: the schema path, and `render_resume` reaching `resume.build` | many | **made** |
| `gates/` — record, parse, prose | lazy: the record gate reads `graph/` and `resume.short` | 3 | **made** |
| `graph/` — the career record, from format to queries | 3, lazy (see "Inside the graph package") | many | **made** |
| `resume/` — the short file, the career as read for a resume, the plan builder | about eleven, into `graph/` and `urs/` | 3 | **made as the seam**, not by this test: it is the one place the career meets the renderer, and keeping that join in one package is what keeps `graph/` and `urs/` from importing each other |

The reason for measuring applies to anything proposed here: four modules that all operate on the same
noun and never import each other would gain a boundary crossing per edge and buy nothing but a
directory named after what they have in common.

`cli.SUBPACKAGE` is the one map from a documented script name to where its module lives, and
`tests/fixtures.load_script` reads that map rather than keeping a second copy.

## Where do I change X

| To change | Edit | And also |
|---|---|---|
| What the parse gate rejects | `src/jsk/gates/check_ats.py` | `references/ats-rules.md`, `tests/test_check_ats.py` |
| What the prose gate rejects | `src/jsk/gates/check_prose.py` | `references/writing-rules.md`, `tests/test_check_prose.py` |
| What makes a `resume.json` fail | `src/jsk/gates/record.py`, `src/jsk/resume/short.py` (shape, ids) | `references/resume-format.md`, `tests/test_record_gate.py`, `tests/test_short.py` |
| A key in `resume.json` | `short.KEYS` in `src/jsk/resume/short.py` | `references/resume-format.md`, `build.py`, `migrate.shorten`, `export.short_file` |
| **What content is selected** | `src/jsk/resume/build.py` | never an emitter; `tests/test_build.py` |
| **How a document looks** | `src/jsk/urs/emit_*.py` | never `build.py` |
| **A palette, typeface or rule** | `src/jsk/urs/themes.py` | `references/templates.md`, `tests/test_themes.py` |
| Support for a new market | `data/schema/profiles/<code>.json` | `profile.schema.json`, `region` in `references/resume-format.md` |
| **The career record's format** | `src/jsk/graph/ontology.py` | `references/kb-format.md` — the ontology is the format and the reference is its prose; a class, predicate or section in one and not the other is a defect. The writer and the tier-1 rules follow the ontology by themselves |
| A rule across entries | `src/jsk/graph/rules.py` | a mutation in `tests/test_graph_rules.py` — a rule with no mutation fails the suite |
| The shipped vocabulary | `src/jsk/data/vocabulary.ttl` | technologies only, no `implies`; `tests/test_graph_vocabulary.py` |
| What `jsk new` scaffolds | `src/jsk/kb.py` | `tests/test_kb_new.py`, `references/mode-setup.md` |
| A posting's or assessment's shape | `Posting` and `Requirement` in `ontology.py`, `agents/jsk-tailor-analyst.md` | `references/mode-tailor.md` |
| How postings are ranked | `src/jsk/graph/queries.py` | the weighting table in `agents/jsk-tailor-analyst.md`; the weights live in `src/jsk/graph/scoring.py` |
| What the record gate checks | `src/jsk/gates/record.py`, `numbers.py` | `docs/SCRIPTS.md`'s table of its checks, `tests/test_record_gate.py` |
| A mode's procedure | `references/mode-<name>.md` | the routing table in `SKILL.md` |
| What an agent may do | `plugins/jsk/agents/<name>.md` | the delegation note in every mode that calls it, and the Agents table in `SKILL.md` |
| Add a mode | a new `references/mode-<name>.md` | routing table in `SKILL.md`, a `commands/<name>.md` |
| A subcommand | `src/jsk/cli.py` | the help docstring in the same file, the command table in `SKILL.md`, `docs/SCRIPTS.md` — all three pinned by `tests/test_plugin_surface.py` |

## What is frozen

This is a published plugin. Three surfaces may not move without a major version and a migration
story:

1. **The `jsk` command surface.** Subcommand names and flags — `jsk check --strict`,
   `jsk ship --ats-max`, `jsk kb apply --dry-run` and the rest — are public API. They appear in shell
   histories, in README examples, and in every mode file. Module names inside the package are free;
   the invocation surface is not.

   Version 4.0 replaced the `okf` command and its bundle format outright, with no compatibility shim:
   a shim over a per-noun write command would have to write into a file whose shape it cannot know.
   The graph record retires one subcommand the same way, with a pointer rather than a shim:
   `jsk index` read `user-knowledgebase.md` and now exits 2 naming `jsk match`, `jsk kb view` and
   `jsk migrate`. The short file retired flags the same way: `--urs` and `--refresh` on `jsk kb
   export` are usage errors naming what replaced them, and `--view` is gone from `render`, `ship`,
   `gates` and `freeze` - a `resume.json` is one resume.

2. **The short file's shape and gate behaviour.** `resume.json` is `"resume": 2` and exactly the
   keys `references/resume-format.md` lists; an unknown key fails. It is **no longer the narrow
   waist** - the render plan is, and the plan is internal. The one break was deliberate: a legacy
   URS record is read only by `jsk migrate`, which shortens it once in an unfrozen application; a
   frozen application's record is the archive of what was sent and is never rendered again - its
   PDF is what was sent. A gate keeps failing on exactly what it fails on today.

3. **The career record's format.** `career/kb.ttl` is the person's file, and it outlives any one
   release. `ontology.FORMAT` is the format revision every kb.ttl carries (`j:format 3`); the
   section order in `ontology.SECTIONS["kb"]` is the order the Markdown headings always had, and it
   does not change. Adding an optional predicate or an enum value is compatible - a file written
   before it still loads. Renaming or removing one, or making one required, is a new format revision
   with a migration, and the writer's layout moving is a `jsk kb fmt`, logged on its own, never a
   silent rewrite. `career/log.ttl` is append-only: nothing rewrites an entry, and `jsk new --force`
   starts the record over as the next revision rather than a new log.

**The graph package and its boundaries** are what hold the third one: every write to `kb.ttl`
goes through `record.prepare`/`record.commit` after the would-be workspace validates, and the
package never imports `urs/` nor is imported by it. See "Inside the graph package" above.

A Markdown knowledge base moves across with `jsk migrate`, once, round-trip checked, deleting
nothing. **It exists for one release.** The next deletes `jsk migrate`, `kbindex.py`,
`tests/test_kbindex.py` and the `[index]`/`[migrate]` extras; nothing outside migrate imports `kbindex` (the weights,
`SENIORITY` and `experience` live in `graph/scoring.py`, and a test holds the graph package to
that). A bundle from a version before 4.0 has one route: read it whole and build the record from it
with `jsk new` and changesets - and a changeset cannot confirm, so it carries `needs-verification` and
`disputed` as the bundle held them and everything else arrives `inferred`; `jsk kb confirm <ids>
--answer` then raises what the bundle held confirmed, the answer naming the bundle file, so the log
says where each confirmation came from. `references/mode-setup.md` states the same route, and it is
a conversation rather than a command because every relation the old format left in prose is a
judgement a script would only guess at.

One more, discovered the hard way: **the tests assert on output text.** Some 200 `assertIn` calls
check strings like `PASS - safe to send` and `DO NOT SEND`. You may *add* lines to a command's
output. Rewording an existing verdict line breaks tests, and those tests are the gate on the gate.

## Tests

```bash
python -m pytest tests -n auto             # the whole suite in parallel
python -m pytest tests -q                  # serially; what CI would do without xdist
python -m pytest tests/test_themes.py -q   # one file, while you are working on it
python -m unittest discover -s tests       # the same tests, with no pytest installed
```

`tests/fixtures.py` puts `src/` on the path itself and passes it to every child interpreter it
spawns, so no install is needed and the suite always tests the working tree rather than whatever
`jsk-resume` happens to be on the machine. That second part matters more than it looks.

**"Runs on a bare Python" is true of the suite as well as the toolchain.** Only the TeX-engine and
`pymupdf` tests skip themselves; everything else runs anywhere.

The tests are standard-library `unittest` and import nothing from pytest; pytest is simply the
pleasanter way to run a subset and read a failure. Either command works from anywhere — every path
in `tests/fixtures.py` is resolved from the test file's own location, not from the working directory.

Most of the runtime is TeX: the tests that dominate the clock compile real PDFs and extract their
text layers, because the claim they check — five templates, one document — cannot be checked any
other way. Where a TeX engine or `pymupdf` is absent those tests skip themselves, so a bare-Python
run finishes in seconds on fewer assertions rather than failing on the machine's setup.

Short files and edited careers are built into temp directories by `tests/careerkit.py`; the
committed fixtures are workspaces (`tests/graph_fixtures/`, `tests/match_fixtures/`,
`tests/claims_fixtures/`) that tests copy before they change anything. Every test pins a specific documented rule — the checker is the
gate, so it does not go unchecked.

`tests/test_budget.py` and `tests/test_plugin_surface.py` are the two that read the markdown rather
than the code, and they are what stops the skill and the CLI drifting apart. The first caps what a
mode costs to read; the second asserts that every subcommand `jsk` dispatches is named in `SKILL.md`
and `docs/SCRIPTS.md`, and that the agent boundary above is still written in the agent files.

A failing test after a refactor means the refactor was wrong. Do not edit a test to accommodate a
change in behaviour unless the behaviour change is the point and it is written down.

## Dependencies

Deliberately close to zero. **`pyproject.toml` declares one as required: `pyoxigraph`**, the graph
engine that parses, validates and queries `career/kb.ttl` - the career itself, not a capability
layered on top, and the cost [WHY.md](WHY.md) states for choosing a graph. It is pinned to one
minor version, ships wheels for every supported platform, and has no dependencies of its own. It is
imported inside functions only, so `jsk doctor` stays standard-library and reports its absence
("cannot read or validate the graph record") rather than failing to start. `pymupdf` is an
optional extra, imported at the point of use.

```bash
pip install jsk-resume              # the graph record, the record gate, prose gate, .txt parse gate
pip install 'jsk-resume[all]'       # + pymupdf, and the Markdown reader for jsk migrate
pip install -e '.[dev]'             # the above plus pytest, pytest-xdist, ruff
```

The `migrate` extra (markdown-it-py, pyyaml; `index` is its alias) reads a `user-knowledgebase.md`
for `jsk migrate`, and goes with it in release 5.0.

Two things are optional to install and required to ship:

| Required | Why |
|---|---|
| a TeX engine | the PDF is the only rendered deliverable; without one there is nothing to send |
| `pymupdf` | without it the parse gate and the page budget are both unverifiable |

`jsk doctor` reports their absence as BLOCKED rather than as a gap.

**A dependency has to be imported by something.** One that is declared, reported by `jsk doctor` as
a capability and never actually used is worse than none, because it teaches people the report is
decorative — which is how `jsonschema` left the list: there was no JSON Schema for it to
validate against.

Anything that cannot run reports loudly and exits non-zero rather than passing quietly - `SKIPPED`,
a failure. There is no exception any more: a `resume.json` outside a workspace has no career to
build from, so the record gate and the render both refuse it (exit 2), naming `career/kb.ttl` as
the fix. The claims gate's `NOT RUN`, which exited 0 there, went with the claims gate.

## Releasing

There are **two release trains** since the code left the skill, and they version independently.

The **plugin** version lives in two files and they must agree — `tests/test_plugin_surface.py`
asserts it:

- `plugins/jsk/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

The **CLI** version is `__version__` in `src/jsk/__init__.py`, which `pyproject.toml` reads through
`[tool.hatch.version]`. `jsk --version` and `jsk doctor` both report it.

```bash
python -m build          # wheel + sdist into dist/
```

Tag them distinctly — `cli-vX.Y.Z` and `plugin-vX.Y.Z` — or the history stops being readable.

Before tagging: run the tests, run `jsk doctor` (the verifying form, not `--quick`), and check that
every internal doc link still resolves.

**The version skew this introduces is real and is not yet handled.** A plugin against an install
with no `jsk` command at all fails loudly. The subtler case — a subcommand or flag the installed CLI
does not have, such as `jsk ship` on an older install — fails mid-session on a usage error. The fix
is a floor the skill states and `jsk doctor --require X.Y` enforces; it is not built.

---

Next: [Why it works this way](WHY.md) · [Commands](SCRIPTS.md)
