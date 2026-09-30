# Architecture

For anyone editing this repo. If you only want to *use* the plugin, read
[Quickstart](QUICKSTART.md) instead.

## The one-way pipeline

```
career/store/  (the graph record: named graphs in one RocksDB store, validated on every load)
   |
   |  changed through `jsk kb apply` changesets, read by id with `jsk kb show`,
   |  matched against a posting graph by `jsk match` - the person in the loop throughout
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

### The tailoring pipeline

The second pipeline runs before the first: a posting turned into requirements, joined with the
career, and assessed. It follows the same rule as the render plan. **A model writes only
decisions, as short text files. Code writes every graph and every rendered page from them.**

```
jsk posting fetch URL D     posting.md        the advert, verbatim - public board JSON, no browser
        |
jsk posting extract D       (printed)         every advert line numbered, sectioned, with its concepts
        |
        |   the analyst writes decisions.txt: one row per requirement, or a drop with a reason
        v
jsk posting build D         posting graph     each quote IS the extracted line, so it cannot drift;
        |                                     every qualification line is used or dropped
        v
jsk tailor prepare D        gaps graph        the match, evidence, the person, the cover - one digest;
        --draft-gaps        gaps.md           the assessment derived from the match (gapsderive);
        |                   gaps.txt          a draft overlay, a <!-- jsk: --> slot per judgement
        |
        |   the analyst edits gaps.txt: lowers a verdict with a reason, fit, eligibility, the asks
        v
jsk match D                 gaps graph        the overlay checked against the match and folded in;
        --gaps D/gaps.txt   gaps.md           an unfilled slot, or a raised verdict, is a FAIL
```

The graphs are `applications/<stem>/posting` and `applications/<stem>/gaps` in `career/store/`;
the text files sit in the application directory `D`. Every command takes `D`, never a file in it.

`decisions.txt` ([`graph/decisions.py`](../src/jsk/graph/decisions.py)) and `gaps.txt`
([`graph/assessment.py`](../src/jsk/graph/assessment.py)) are the only two files the analyst
writes. Each holds only what code cannot know: which concept an advert means, and a verdict that
the triples read too generously. The rest is derived. The cost argument is measured: writing
the posting's Turtle by hand cost one run 26.5k output tokens, most of them ids and quotes copied
character by character, which are exactly what the checks then police. Both overlays are
re-derived on every run from the career as it stands, until the application graph records that
the application was sent. After that they are left as they were.

### The commands over it

```
jsk new       PATH --name NAME                     career/store/ with kb and log at r1, applications/
jsk kb        apply changes.trig                   the career changed: validated, written, logged
jsk posting   fetch URL D | extract D | build D    the advert, its lines, then the posting graph
jsk tailor    prepare D [--draft-gaps]             everything an assessment reads, in one digest
jsk match     applications/D                       the posting against the career, with the paths
jsk kb        export --from-match D --out R.json   the short resume.json, chosen from the match
jsk validate  resume.json                          the record gate - before anything renders
jsk render    resume.json --out D --pdf            .tex, .pdf, .txt
jsk gates     D                                    record, parse, prose and layout gates over that render
jsk ship      resume.json --out D                  the gates above and the render, in order, in one process
jsk freeze    D --submitted DATE --channel TEXT    the application graph, once the gates pass
jsk event     D KIND --date DATE                   what came back, added to the application graph
jsk kb        dump [--out F.trig] | load SRC       the whole record as TriG; a dump or a .ttl workspace in
```

`jsk ship <resume.json> --out DIR [--ats-max] [--template N] [--pages N] [--no-fit] [--json]` is the
path a finished resume takes. The record gate runs first, and a failure stops it: nothing renders, because
a render of a resume that failed would be a document nobody should read. Then `render --pdf`; then,
if the render is over its budget, `jsk fit`'s levers, the fitted `.tex` moved over the render's and
recompiled; then the parse, prose and layout gates over the output directory,
each step's output printed verbatim. It exits 0 only if every step passed. It reports the measured
page count and never fails on it: a render still over at the floors keeps its unfitted form and says
`over by ~N lines at the floors`, and what to cut is the author's call. It closes by saying the render gate is still open, because a person reading the
PDF is the one gate no command can run. It refuses in a frozen application (the file's directory, or
`--out`, is one the store holds an application graph for): re-rendering would overwrite what was sent.

`jsk freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--doc FILE ...]` is the last
step. It refuses unless the mechanical gates pass and no application graph exists yet, then
writes one — what was sent, the `resume.json` hash, the bullets that rendered (the
plan's `sent`) and the metric versions they cite — and renames the directory to the submitted date.
The application's posting and assessment graphs move to the new name in the same update that
writes its application graph; no log entry is added, since the log is the career's.
No copy of the content is written: the PDF, `.txt` and `.tex` beside it are the words sent. After that the directory is
an archive: later events are added with `jsk event`, never edited.

Every subcommand runs **in process**. `cli.py` imports the module behind it and calls its `main()`
with the same arguments, so the output and the exit code are the module's own and nothing is
paraphrased on the way through. One interpreter per invocation is what lets `jsk ship` be a single
command rather than four start-ups; `call_gate()` turns the two failures an in-process call adds — a
module that will not import, and one that raises where it should have returned a verdict — into a
reported failure instead of a traceback.

### Inside the `resume` package

| Module | Decides |
|---|---|
| `short.py` | the short file: `read` (refuses a legacy URS record, naming `jsk kb export`), `workspace` (by `kbcli.find_root`, never `dirname`), `shape` and `ids` - the FAIL lines the record gate and the builder share |
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

### Inside the `render` package

The renderer: everything after the plan, and the three CLIs.

| Module | Decides |
|---|---|
| `formatting.py` | *how* one value reads: dates, grades, quantities, the fold to ASCII |
| `profiles.py` | region profile loading |
| `emit_*.py` | markup only |
| `themes.py` | *appearance* only: palette, typeface, rhythm. Below `emit_latex.py`, and it cannot reach the text |
| `render_resume.py` · `preview_templates.py` · `fit_pages.py` | the CLIs — `jsk render`, `jsk preview`, `jsk fit`. They orchestrate the modules above and decide nothing themselves |

`render_resume.py` reaches the career only through `resume.build` (and `resume.short` for the
short file's errors), lazily. `formatting.py` holds
pure functions over single values — no profile, no career — which is what makes them testable in
isolation.

### Inside the `graph` package

The career record. It keeps the record in `career/store/`, reads Turtle and TriG as input
(changesets, dumps, the vocabulary), and never renders anything; the rendering half never imports
it. Every module keeps `pyoxigraph` inside its functions, so importing the package
costs nothing on a machine without the engine and `jsk doctor` can report on it.

| Module | Decides |
|---|---|
| `ontology.py` | **the format**: every class, predicate, cardinality, datatype, enum and section, as data. Standard library only. The single definition - the writer, the rules and the format reference all follow it |
| `io.py` | `read_text` (every text read: BOM, CRLF, cp1252 once) and parsing Turtle and TriG input - changesets, dumps, the vocabulary - with a parse failure's line |
| `writer.py` | the entry printer `jsk kb show`, `pack` and `merge` use: subject blocks, a project with its bullets and a metric with its versions, predicates in ontology order, `"""` prose |
| `shapes.py` · `rules.py` | tier 1, generated from the ontology (closed predicates, required, cardinality, datatype, enum, id prefix); tier 2, the cross-node rules, each a SPARQL query with a fix, each with a mutation test |
| `store.py` | a workspace in memory: the record graphs copied out of the store (or a write's candidate graphs) plus the shipped vocabulary, derived triples in `j:derived`, every rule run on every load |
| `db.py` | the record on disk: one RocksDB store per workspace at `career/store/`, a named graph per record, the writers' turn (a blocking OS lock), one update per write, dump and parse. The only module that opens the store |
| `legacy.py` | a workspace still laid out as `.ttl` files, read once for `jsk kb load` - validated as before, numbers kept as the store keeps them and each rewrite reported |
| `record.py` | **the write gate**: revision and log entry (`prepared`), `state` (clean, out-of-sync, missing - and, for the files the import reads, hand-edited, torn and unlogged), `turn` - the writer's turn, taken before a writing command reads the record, and before it asks whether a store exists - `unrecorded` (is the career what the log's newest `kbSha256` hashed: `jsk kb check` and a dump's load ask it) and `write_graphs`: every touched graph in one `db.replace_graphs`, then `.jsk/backup.trig`; a failure after the update landed is `Written`, never "nothing was changed". The only caller of `replace_graphs` |
| `changeset.py` · `edit.py` · `kbcli.py` | `jsk kb`: a changeset read and refused or merged, and every verb over the record. `changeset.numbers_as_kept` refuses a number the store would rewrite (`8.40`) - in changesets, posting builds and dumps `jsk kb load` reads; not a rule id, since the import rewrites and lists them instead |
| `pack.py` · `merge.py` | `jsk kb pack` (the capability starter pack) and `jsk kb merge` (two concepts that are one), each drafted as a changeset and never applied |
| `queries.py` · `named.py` · `match.py` | the vocabulary and the named questions; `jsk match` |
| `scoring.py` | the numbers the match ranks by: seniority order, the requirement weights, recency points, months of experience. Standard library only |
| `select.py` · `export.py` | what a resume for one posting selects (projects, bullets, skill order) and `jsk kb export`, which writes it as the short file |
| `decisions.py` · `postingbuild.py` | `decisions.txt` read; `jsk posting extract` and `build`, which write the posting graph from it |
| `prepare.py` | `jsk tailor prepare`: the check, the match, the evidence, the person and the cover, in one digest |
| `gapsderive.py` · `gapsdraft.py` · `assessment.py` · `gapsbuild.py` | the assessment: derived from the match with no model; the draft `gaps.txt`; `gaps.txt` read; the overlay checked, folded in, and written as the gaps graph and `gaps.md` |
| `view.py` · `timeline.py` | `jsk kb view`; `jsk freeze`'s application graph and `jsk event` |

**Its boundaries.** Only `db.py` opens `career/store/`, and only `record.py` calls
`db.replace_graphs`; `tests/test_db.py` fails if anything else does. So every write - `jsk kb`'s
verbs, `jsk new`, the posting and gaps builds, `jsk freeze` and `jsk event` - goes through
`record.write_graphs` after the would-be record validates, in one update of the store. A write
to the career lands with its log entry in that update; `jsk freeze`, `jsk event` and the builds
write only an application's graphs and add no entry, since the log is the career's history.
The SPARQL queries are not storage access: they ask a validated in-memory store about a career,
and stay grouped by purpose (`queries`, `named`, `match`, `rules`).

Outward, the package reaches seven places beyond the shared helpers `cliutil` and `paths`:

| Target | For | From |
|---|---|---|
| `gates.report` | `Report` and `show`, the one way to print a finding | `store`, `kbcli`, `match` |
| `gates.numbers` | the untraced-number check `jsk kb check` and `jsk match` run over the career's bullets | `kbcli`, `match` |
| `gates.check_ats` | `read_pdf`, for `jsk kb confirm --source` given a PDF | `kbcli` |
| `resume.career` | `Career` | `export`, `select`, `match`, `kbcli` |
| `resume.short` | reading a `resume.json` | `kbcli` |
| `posting` | the advert's file name (`posting.md`) and `Refused` | `postingbuild` |
| `cli` | `frozen_refusal`: one wording for "this application is frozen" | `kbcli` |

All of them are lazy, inside the function that needs them, except three imports at the top of a
module: `export.py` (`paths`, `resume.career`) and `postingbuild.py` (`posting`). The `cli`
edge is the one upward edge: a library module importing the dispatcher. It stays lazy so it
cannot become an import cycle, and moving `frozen_refusal` down into a shared module would
remove it. `pyoxigraph` is imported only inside functions in every module.

Inward, `resume/` builds from the store, `gates/` reads it, and `cli.py` finds the workspace
with `kbcli.find_root`. Nothing in `render/` imports the graph package, and nothing in it imports
`render/`.

## The agent boundary

Five tasks are delegated to subagents, and the line between them is what each may write.

| Agent | Has | Deliberately lacks |
|---|---|---|
| `jsk-verifier` | Bash, Read, Glob | Write and Edit — a defect is fixed in the career or `resume.json` and re-rendered, never patched into the render |
| `jsk-kb-auditor` | Read, Write, Glob, Grep, Bash | Edit — it writes an audit from `jsk kb check` and `jsk kb query`; the career is the person's |
| `jsk-extractor` | Read, Write, Glob, Grep, Bash | Edit — it writes one changeset from a braindump or an imported document and only dry-runs it; the session shows the diff, applies and confirms |
| `jsk-tailor-analyst` | Read, Write, Edit, Glob, Grep, Bash | nothing, and that is worth reading below |
| `jsk-resume-author` | Read, Write, Edit, Glob, Grep, Bash | nothing — it is the one that writes prose |

**For the two authoring agents the anti-invention guarantee is not a tool grant.** Both hold Edit,
and what holds them is partly what their files say and partly what the write path refuses:

- `jsk-tailor-analyst` writes two text files, `decisions.txt` and `gaps.txt`. `jsk` turns them
  into the posting and gaps graphs and `gaps.md`, so most of what it could get wrong is refused by
  the write path, not by what its file says:
  - every requirement's quote *is* an extracted advert line;
  - every qualification line must be used or dropped with a reason;
  - a verdict can only be lowered from the match's, never raised, and a lowered one needs a
    reason.

  It **never touches the career**. That boundary is prose, and
  `tests/test_plugin_surface.py` asserts the sentence is still in the file, which is the most a
  test can do about a rule of that kind. There is no file for it to edit by hand: the career is
  in `career/store/`, and the only way in is `jsk kb`, whose every write is logged.
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

`jsk-verifier` is the conditional one. `jsk ship` and `jsk gates` run the record, parse,
prose and layout gates in a single process and print each one's output verbatim, so a clean ship reads that rather
than spawning an agent to relay four checkers — and a command has no Write tool more thoroughly than
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
  cli.py                            the dispatcher: fifteen subcommands, each run in process
  cliutil.py                        one contract for --help across the hand-rolled entry points
  paths.py                          where the packaged schema lives - stated once
  kb.py                             `jsk new` - scaffolds career/store/ (kb and log at r1), applications/
  posting.py                        `jsk posting` - fetch an advert from a public board; extract, build
  graph/                            the career record: see "Inside the graph package"
    ontology.py                     the format, as data     writer.py     the entry printer
    io.py  store.py  record.py      read and parse input, load and validate, the write gate
    db.py  legacy.py                the store on disk, and the one-time import from files
    shapes.py  rules.py             tier 1 and tier 2 rules
    changeset.py  edit.py  kbcli.py `jsk kb`
    pack.py  merge.py               `jsk kb pack` and `jsk kb merge`, drafted as changesets
    queries.py  named.py  match.py  the vocabulary, named queries, `jsk match`
    scoring.py                      the ranking's numbers; standard library only
    select.py  export.py            what a match selects; `jsk kb export` writes the short file
    decisions.py  postingbuild.py   decisions.txt; `jsk posting extract` and `build` -> the posting graph
    prepare.py                      `jsk tailor prepare` - one digest for the assessment
    gapsderive.py  gapsdraft.py     the assessment derived from the match; the gaps.txt draft
    assessment.py  gapsbuild.py     gaps.txt read; checked, folded in, the gaps graph and gaps.md written
    view.py  timeline.py            `jsk kb view`; the application graph and `jsk event`
  resume/                           career + resume.json -> the render plan
    short.py                        the short file: read, shape, ids, its workspace
    career.py                       the career graph as the builder, export and match read it
    build.py                        every content decision, made exactly once
  render/                           plan -> document, and the three CLIs that drive it
    formatting.py                   *how* one value reads      profiles.py   region profiles
    themes.py                       appearance only            tex.py        the engine
    emit_latex.py  emit_text.py     markup only
    render_resume.py                `jsk render` - one resume to .tex/PDF plus .txt
    preview_templates.py            `jsk preview` - every template, so the look is chosen by looking
    fit_pages.py                    `jsk fit` - fits a render to a page budget
  gates/                            the mechanical gates `jsk gates` and `jsk check` run
    record.py                       the record gate - resume.json and the bullets it selects
    numbers.py  report.py           the untraced-number check; one way to print a finding
    check_ats.py                    the parse gate        check_prose.py    the prose gate
    layout.py                       the layout gate - fonts, tofu, stranded headings, dates, paper
    letter.py                       the letter check - a cover letter's length, prose and numbers
  preflight.py                      `jsk doctor`: what this machine can do
  domain/                           the innermost ring: no files, argv, environment or clock
    naming.py                       a record graph's short name and its IRI, the same in memory and on disk
    record/confirmation.py          what a confirmation's quote must share with its claim
    gates/numbers.py  report.py     numbers in prose and whether metrics hold them; a gate's findings
    gates/ats_rules.py              the parse gate's rules over extracted text and fonts
    gates/prose_rules.py            the prose gate's rules over a .tex's or .txt's paragraphs
    gates/layout_rules.py           the layout gate's rules over page sizes, line boxes and fonts
    resume/constants.py             the provenance floor's ranks and a skills row's length
    ontology.py  record/writer.py   the format, as data; the entry printer (moved from graph/)
    record/career.py                the career graph as the builder, export and match read it
    record/parsed.py                a Turtle or TriG text as parsed: quads, subject lines, comments
    record/state.py                 the career and its log in step: revision, state, stamp, entry
    record/store.py                 a loaded workspace: its graphs, findings and engine; the derivations
    record/decisions.py             decisions.txt's format and its parser: header, rows, drops
    record/changeset.py             a parsed changeset read, and what it may never say refused
    record/edit.py                  a changeset merged into the career, refused where the career says
    record/pack.py                  a starter pack's draft against the workspace, and its TriG
    record/merge.py                 two concepts that are one, drafted as a changeset
    matching/model.py               the match's values: requirement, resolution, match, row, question
    matching/resolve.py             a requirement resolved to concepts, carried by projects; evidence
    matching/rank.py  cover.py      the projects scored for a posting; the smallest set carrying it
    matching/nearest.py             the concepts nearest a label, and those an advert line names
    matching/questions.py           the questions a tailoring round asks of a match
    selection/select.py             the projects, bullets, skills and gaps a resume selects
    posting/errors.py               posting.md's name, and how a posting step refuses
    posting/boards.py               which job board a URL is on, and its answer as a posting
    posting/html_text.py            a board's or a saved page's HTML as text
    posting/posting_md.py           posting.md as jsk writes it
    assessment/verdict.py           the order verdicts rank in, and why none is ever raised
    assessment/overlay.py           gaps.txt's format and its parser: the analyst's overlay
    assessment/derive.py            the gap assessment the match already knows, without a model
    render/formatting.py  themes.py how one value reads; appearance only (moved from render/)
  ports/                            what the application needs from outside, as Protocols
    engine.py  record.py  codec.py  the graph engine; the record on disk; Turtle and TriG
    files.py  tex.py  pdf.py        authored texts and application files; the TeX engine; a PDF read
    posting_source.py  profiles.py  a job board's API; the region profiles
    clock.py  queries.py            today; the feature reads over a loaded record
    workspace.py                    a workspace as loading it needs it
  application/                      the use cases: each returns a result and prints nothing
    guards.py                       the refusals several commands share, returned as lines
    gates/numbers.py                the untraced-number check over a loaded career
    tailor/match_text.py            the match's sections as markdown, shared with the gaps draft
    record/load.py                  loading a workspace: graphs into an engine, types derived, rules run
  infra/                            what touches a disk, a process, the network or the engine
    files.py                        the workspace on disk: find_root
    pdf.py                          a rendered PDF's text and fonts, through pymupdf
    profiles.py                     the region profiles under data/ (moved from render/)
    oxigraph/codec.py               Turtle and TriG parsed through the engine; numbers as it keeps them
    oxigraph/db.py  record.py       the store on disk; the write gate every write goes through
    oxigraph/engine.py              the in-memory engine a loaded record runs on
    oxigraph/queries.py             the feature reads over a loaded record, as SPARQL
    tex.py                          the TeX engine a render's .tex is compiled with (moved from render/)
    posting_sources.py              a board's JSON over the network; a .docx, .html or text file
  data/vocabulary.ttl               the shipped technology vocabulary (labels, former names,
                                    isA, partOf, distinct)
  data/capabilities.ttl             the capability starter pack `jsk kb pack` drafts; never loaded
  data/example/                     a small career as Turtle and a short resume.json: doctor renders it
  data/schema/                      package data, reached through paths.py
    profiles/*.json                 region profiles: default, au, in, ae
    profile.schema.json             what a region profile must contain
plugins/jsk/                        THE SKILL. markdown only - it ships no code
  .claude-plugin/plugin.json        plugin manifest (carries a version)
  commands/                         slash commands
    setup|braindump|resume|...      thin delegations into the skill's modes; each procedure
                                    lives in references/mode-<name>.md
  agents/                           subagents the modes delegate to
    jsk-verifier.md                 interprets a failed gate against the career and resume.json
    jsk-kb-auditor.md               checks and queries the career, writes a posting-less audit
    jsk-extractor.md                a braindump or imported document to one dry-run changeset
    jsk-tailor-analyst.md           writes decisions.txt and gaps.txt; jsk writes the rest
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
  storekit.py                       seed(): readable Turtle sources parsed into a workspace's store
  graph_fixtures/                   a valid graph workspace as those sources - kb at r2, its log, one
                                    application - kept as Turtle so a test's content stays reviewable
```

**The code and the skill are two artefacts.** `src/jsk/` is a Python package installed from PyPI as
`jsk-resume`; `plugins/jsk/` is markdown that calls `jsk`.

**The package owns the career record; the skill writes changesets and short files.** Every write
to `career/store/` goes through `record.write_graphs` (from `jsk kb`, `jsk new`, the posting
builds, `jsk freeze` and `jsk event`), and every load validates it. No agent reads a file under `career/`. The skill exports each `resume.json` from the career and edits its order,
summary and settings, which is why the record gate runs before anything renders: it is the last
point at which a mistake is still cheap.

## What is a package here, and what is not

There are four subpackages, and each was measured before it was made. The test is whether the
members import *each other* more than they import outward. A group whose members share no edges
is a folder with a theme, not a module.

The counts below were measured on 2026-09-28. "Targets" are the distinct modules outside the
package that it imports. "Inside" is the number of import statements between its own members.
Both leave out the shared helpers `cliutil` and `paths`, which every CLI module imports.

| Group | Targets outside | Imports inside | Verdict |
|---|---|---|---|
| `render/`: rendering, preview and the page fitter, over the plan→document pipeline | **3**, all lazy and all from the two CLIs: `resume.build`, `resume.short`, `cli` (`frozen_refusal`) | 11 | **made** |
| `gates/`: record, parse, prose, layout, letter | **11**: six `graph/` modules, three `resume/`, two `render/`. All lazy except `record.py`'s import of `graph.ontology`, which is standard library only | 10 | **fails the test today** (below) |
| `graph/`: the career record, from format to assessment | **7** (see "Inside the graph package") | 202 | **made** |
| `resume/`: the short file, the career as read for a resume, the plan builder | **8**, into `graph/` and `render/` | 4 | **made as the seam**, not by this test: it is the one place the career meets the renderer, and keeping that join in one package is what keeps `graph/` and `render/` from importing each other |

`gates/` passed the test when it held three gates. The record gate and the letter check have
since grown into readers of the career, and between them they import from eleven modules
outside the package, against ten imports among the gates themselves. The package is still the set `jsk gates` and
`jsk check` run, but by the rule above that is a theme, not a reason. The honest options are to
accept `gates/` as a named exception, like `resume/`, or to move the two career-reading gates
beside what they read. Neither has been decided.

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
| What the layout gate rejects | `src/jsk/gates/layout.py` | `docs/SCRIPTS.md`, `tests/test_layout.py` |
| What makes a `resume.json` fail | `src/jsk/gates/record.py`, `src/jsk/resume/short.py` (shape, ids) | `references/resume-format.md`, `tests/test_record_gate.py`, `tests/test_short.py` |
| A key in `resume.json` | `short.KEYS` in `src/jsk/resume/short.py` | `references/resume-format.md`, `build.py`, `export.short_file` |
| **What content is selected** | `src/jsk/resume/build.py` | never an emitter; `tests/test_build.py` |
| **How a document looks** | `src/jsk/render/emit_*.py` | never `build.py` |
| **A palette, typeface or rule** | `src/jsk/render/themes.py` | `references/templates.md`, `tests/test_themes.py` |
| Support for a new market | `data/schema/profiles/<code>.json` | `profile.schema.json`, `region` in `references/resume-format.md` |
| **The career record's format** | `src/jsk/graph/ontology.py` | `references/kb-format.md` and `docs/ONTOLOGY.md` — the ontology is the format and the reference is its prose; a class, predicate or section in one and not the other is a defect. The writer and the tier-1 rules follow the ontology by themselves |
| A rule across entries | `src/jsk/graph/rules.py` | a mutation in `tests/test_graph_rules.py` — a rule with no mutation fails the suite |
| The shipped vocabulary | `src/jsk/data/vocabulary.ttl` | technologies only, no `implies`; `tests/test_graph_vocabulary.py` |
| The capability starter pack | `src/jsk/data/capabilities.ttl`, `src/jsk/graph/pack.py` | applied to the career as a changeset, never loaded as vocabulary; `tests/test_graph_pack.py` |
| Where the record is stored, or how a write lands | `src/jsk/graph/db.py` (storage), `src/jsk/graph/record.py` (the write gate) | `tests/test_db.py`, which also fails a second module that opens the store or writes it |
| What `jsk new` scaffolds | `src/jsk/kb.py` | `tests/test_kb_new.py`, `references/mode-setup.md` |
| A posting's or assessment's shape | `Posting`, `Requirement`, `Assessment` and `Verdict` in `ontology.py` | `postingbuild.py` and `gapsbuild.py`, which write them; `references/mode-tailor.md`, `agents/jsk-tailor-analyst.md` |
| What the analyst may write | `graph/decisions.py` (`decisions.txt`), `graph/assessment.py` (`gaps.txt`) | the checks in `postingbuild.py` and `gapsbuild.py`; `agents/jsk-tailor-analyst.md` |
| How the career's projects are ranked for a posting | `rank` in `src/jsk/domain/matching/rank.py`; the weights in `src/jsk/domain/matching/scoring.py` | `cover` in `cover.py` beside it, and `src/jsk/domain/selection/select.py`, which keeps only confirmed evidence before choosing; `docs/ONTOLOGY.md` §11 |
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
   The graph record retires two subcommands the same way, with a pointer rather than a shim:
   `jsk index` read `user-knowledgebase.md` and now exits 2 naming `jsk match` and `jsk kb view`;
   `jsk migrate` moved that file to the graph and now says the Markdown knowledge base is no longer
   read, naming `jsk new PATH --name NAME`. The short file retired flags the same way: `--urs` and `--refresh` on `jsk kb
   export` are usage errors naming what replaced them, and `--view` is gone from `render`, `ship`,
   `gates` and `freeze` - a `resume.json` is one resume. The store retired `jsk kb adopt` and
   `jsk kb fmt` outright - there is no hand edit to adopt and no file layout to restore - and
   `jsk match`, `jsk kb export --from-match` and `jsk tailor prepare` take the application
   directory, refusing a `posting.ttl` path with the new form in the fix.

2. **The short file's shape and gate behaviour.** `resume.json` is `"resume": 2` and exactly the
   keys `references/resume-format.md` lists; an unknown key fails. It is **no longer the narrow
   waist** - the render plan is, and the plan is internal. The one break was deliberate: a legacy
   URS record is refused everywhere, naming `jsk kb export` to write a short one; a frozen
   application's record is the archive of what was sent and is never rendered again - its
   PDF is what was sent. A gate keeps failing on exactly what it fails on today.

3. **The career record's format.** The career is the person's record, and it outlives any one
   release. `ontology.FORMAT` is the format revision the career carries (`j:format 3`); the
   section order in `ontology.SECTIONS["kb"]` is the order the Markdown headings always had, and
   `jsk kb view` prints it; it does not change. Adding an optional predicate or an enum value is
   compatible - a record written before it still loads. Renaming or removing one, or making one
   required, is a new format revision with a migration. The log is append-only: nothing rewrites an
   entry, and `jsk new --force` keeps the old record as `career/kb.r<N>.trig` and starts over.

   The files under `career/store/` are **not** this surface: they are RocksDB as the pinned
   pyoxigraph writes it. The portable form is the TriG `jsk kb dump` writes and `jsk kb load`
   reads; raising the pyoxigraph pin is a dump with the old version and a load with the new one,
   and CI on Windows and Linux. A workspace still laid out as `.ttl` files (before the store) is
   imported once with `jsk kb load .`; any other command there refuses, naming that fix.

**The graph package and its boundaries** are what hold the third one: every write goes through
`record.write_graphs` after the would-be record validates, and the package never imports `render/` nor
is imported by it. See "Inside the graph package" above.

A bundle from a version before 4.0 has one route: read it whole and build the record from it
with `jsk new` and changesets - and a changeset cannot confirm, so it carries `needs-verification` and
`disputed` as the bundle held them and everything else arrives `inferred`; `jsk kb confirm <ids>
--source <bundle file> --quote "…"` then raises what the bundle held confirmed, checking the quote
is in the file and holds each number, so the log says where each confirmation came from. `references/mode-setup.md` states the same route, and it is
a conversation rather than a command because every relation the old format left in prose is a
judgement a script would only guess at.

One more, discovered the hard way: **the tests assert on output text.** Hundreds of `assertIn` calls
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
mode costs to read. The second asserts that every subcommand `jsk` dispatches is named in
`SKILL.md` and `docs/SCRIPTS.md`, that the agent boundary above is still written in the agent
files, and that this page names every module under `src/jsk/` and counts the subcommands
correctly. A new module with no line here fails the suite.

A failing test after a refactor means the refactor was wrong. Do not edit a test to accommodate a
change in behaviour unless the behaviour change is the point and it is written down.

## Dependencies

Deliberately close to zero. **`pyproject.toml` declares one as required: `pyoxigraph`**, the graph
engine that stores, validates and queries the career in `career/store/` - the career itself, not a
capability layered on top, and the cost [WHY.md](WHY.md) states for choosing a graph and then a
store. It is pinned to one minor version, because the store's on-disk format follows it, ships wheels for every supported platform, and has no dependencies of its own. It is
imported inside functions only, so `jsk doctor` stays standard-library and reports its absence
("cannot read or validate the graph record") rather than failing to start. `pymupdf` is an
optional extra, imported at the point of use.

```bash
pip install jsk-resume              # the graph record, the record gate, prose gate, .txt parse gate
pip install 'jsk-resume[all]'       # + pymupdf
pip install -e '.[dev]'             # the above plus pytest, pytest-xdist, ruff
```

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
build from, so the record gate and the render both refuse it (exit 2), naming the workspace as
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
