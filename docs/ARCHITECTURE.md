# Architecture

For anyone editing this repo. If you only want to *use* the plugin, read
[Quickstart](QUICKSTART.md) instead.

## The one-way pipeline

```
career/store/  (the graph record: named graphs in one RocksDB store, validated on every load)
   |
   |  changed through `jsk kb apply` changesets, read by id with `jsk kb show`,
   |  matched against a posting graph by `jsk tailor match` - the person in the loop throughout
   |
   +---------------------+
   |                     |  resume.json  (the short file, one per application: bullet ids in
   |                     |  order, skills, format, region, budgets, floor, a summary - no copy
   |                     |  of the career; `jsk kb export` writes it, `jsk resume check` gates it)
   v                     v
domain/resume/plan.py builds the plan exactly once:
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
`jsk resume fit` measures is the thing that gets sent. A `.docx` measured through LibreOffice beside the
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
jsk tailor match D                 gaps graph        the overlay checked against the match and folded in;
        --gaps D/gaps.txt   gaps.md           an unfilled slot, or a raised verdict, is a FAIL
```

The graphs are `applications/<stem>/posting` and `applications/<stem>/gaps` in `career/store/`;
the text files sit in the application directory `D`. Every command takes `D`, never a file in it.

`decisions.txt` ([`domain/record/decisions.py`](../src/jsk/domain/record/decisions.py)) and
`gaps.txt` ([`domain/assessment/overlay.py`](../src/jsk/domain/assessment/overlay.py)) are the only two files the analyst
writes. Each holds only what code cannot know: which concept an advert means, and a verdict that
the triples read too generously. The rest is derived. The cost argument is measured: writing
the posting's Turtle by hand cost one run 26.5k output tokens, most of them ids and quotes copied
character by character, which are exactly what the checks then police. Both overlays are
re-derived on every run from the career as it stands, until the application graph records that
the application was sent. After that they are left as they were.

### The commands over it

```
jsk kb new         PATH --name NAME                   career/store/ with kb and log at r1, applications/
jsk kb apply       changes.trig                       the career changed: validated, written, logged
jsk posting        fetch URL D | extract D | build D  the advert, its lines, then the posting graph
jsk tailor prepare D [--draft-gaps]                   everything an assessment reads, in one digest
jsk tailor match   applications/D                     the posting against the career, with the paths
jsk kb export      --from-match D --out R.json        the short resume.json, chosen from the match
jsk resume check   resume.json                        the record gate - before anything renders
jsk resume render  resume.json --out D --pdf          .tex, .pdf, .txt
jsk resume check   D                                  record, parse, prose and layout gates over that render
jsk resume ship    resume.json --out D                the gates above and the render, in order, in one process
jsk letter check   LETTER --record R.json             a cover letter's length, prose and numbers
jsk app freeze     D --submitted DATE --channel TEXT  the application graph, once the gates pass
jsk app event      D KIND --date DATE                 what came back, added to the application graph
jsk kb dump        [--out F.trig] | load SRC          the whole record as TriG; a dump or a .ttl workspace in
```

`jsk resume ship <resume.json> --out DIR [--ats-max] [--template N] [--pages N] [--no-fit] [--json]` is the
path a finished resume takes. The record gate runs first, and a failure stops it: nothing renders, because
a render of a resume that failed would be a document nobody should read. Then `render --pdf`; then,
if the render is over its budget, `jsk resume fit`'s levers, the fitted `.tex` moved over the render's and
recompiled; then the parse, prose and layout gates over the output directory,
each step's output printed verbatim. It exits 0 only if every step passed. It reports the measured
page count and never fails on it: a render still over at the floors keeps its unfitted form and says
`over by ~N lines at the floors`, and what to cut is the author's call. It closes by saying the render gate is still open, because a person reading the
PDF is the one gate no command can run. It refuses in a frozen application (the file's directory, or
`--out`, is one the store holds an application graph for): re-rendering would overwrite what was sent.

`jsk app freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--doc FILE ...]` is the last
step. It refuses unless the mechanical gates pass and no application graph exists yet, then
writes one — what was sent, the `resume.json` hash, the bullets that rendered (the
plan's `sent`) and the metric versions they cite — and renames the directory to the submitted date.
The application's posting and assessment graphs move to the new name in the same update that
writes its application graph; no log entry is added, since the log is the career's.
No copy of the content is written: the PDF, `.txt` and `.tex` beside it are the words sent. After that the directory is
an archive: later events are added with `jsk app event`, never edited.

Every verb runs **in process**. The dispatcher imports the adapter behind it and calls its `main()`
with the same arguments, so the output and the exit code are the module's own and nothing is
paraphrased on the way through. One interpreter per invocation is what lets `jsk resume ship` be a single
command rather than four start-ups; `call_gate()` turns the two failures an in-process call adds — a
module that will not import, and one that raises where it should have returned a verdict — into a
reported failure instead of a traceback.

### The resume, across the rings

| Module | Decides |
|---|---|
| `domain/resume/short.py` · `application/render/load_resume.py` | the short file: parsed (a legacy URS record refused, naming `jsk kb export`), its workspace (by `infra.files.find_root`, never `dirname`), `shape` and `ids` - the FAIL lines the record gate and the builder share |
| `domain/record/career.py` | reading the career graph: `Career`, employers and their roles by date, periods. Shared with export, select and match |
| `domain/resume/plan.py` | *what* the document says: `build(store, doc, ...)` returns the plan |
| `adapters/cli/compose/resume.py` | the file read from disk, its workspace found and its career loaded; `from_path(path)` reads, checks and builds under the shipped region profiles |

### The render plan

The one internal format, and what every emitter, `themes.py` and `jsk resume fit` read. A dict:

| key | holds |
|---|---|
| `view` | `"resume"` - kept for the emitters' file naming |
| `format` | `presentation` or `ats-maximal` |
| `profile`, `region`, `pages` | the region profile's id, the region (paper size), the page budget |
| `name`, `headline`, `header_lines` | the header, as finished strings |
| `sections` | in the profile's order, each `{"kind", "heading", ...}`: `text` (`paragraphs`), `rows` (`rows` of `{label, items}`), `entries` (each `{org_line, org_right, roles: [{left, right, bullets}], lines, bullets}`), `lines` (`lines`); the declaration is a `lines` section with no heading |
| `warnings` | withheld lines, brackets, a skills row cut at its limit - printed by `jsk resume render` as `warn` lines |
| `sent` | the `ach_` ids that rendered, in order - what `jsk app freeze` records as carried |

Every string in it is final: folded to ASCII for `ats-maximal`, dates formatted, below-floor lines
already dropped. A new section kind is a builder method and a branch in each emitter; a key the
emitters do not read is dead.

### The renderer, across the rings

Everything after the plan, and the three commands that drive it.

| Module | Decides |
|---|---|
| `domain/render/formatting.py` | *how* one value reads: dates, grades, quantities, the fold to ASCII |
| `infra/profiles.py` | region profile loading |
| `domain/render/emit_*.py` | markup only |
| `domain/render/themes.py` | *appearance* only: palette, typeface, rhythm. Below `emit_latex.py`, and it cannot reach the text |
| `application/render/` · `adapters/cli/{render,preview,fit}.py` | `jsk resume render`, `jsk resume preview`, `jsk resume fit`: the use cases orchestrate the modules above and decide nothing themselves; the adapters parse and print |
| `adapters/cli/compose/{render,preview,fit}.py` | each command's TeX engine, bound where a test's patch of `compile_pdf` reaches it |

The render reaches the career only through `compose.resume`, lazily. `formatting.py` holds
pure functions over single values — no profile, no career — which is what makes them testable in
isolation.

### The career record, across the rings

The career record keeps the record in `career/store/`, reads Turtle and TriG as input
(changesets, dumps, the vocabulary), and never renders anything; the rendering half never imports
it. It was the `graph/` package; its modules now sit in the rings (Ruling 1 of
docs/superpowers/specs/2026-09-30-onion-architecture-design.md), and `graph/` is gone. Every
module keeps `pyoxigraph` inside its functions, so importing one costs nothing on a machine
without the engine and `jsk doctor` can report on it.

| Module | Decides |
|---|---|
| `domain/ontology.py` | **the format**: every class, predicate, cardinality, datatype, enum and section, as data. Standard library only. The single definition - the writer, the rules and the format reference all follow it |
| `infra/files.py` · `infra/oxigraph/codec.py` | `read_text` (every text read: BOM, CRLF, cp1252 once) and parsing Turtle and TriG input - changesets, dumps, the vocabulary - with a parse failure's line |
| `domain/record/writer.py` | the entry printer `jsk kb show`, `pack` and `merge` use: subject blocks, a project with its bullets and a metric with its versions, predicates in ontology order, `"""` prose |
| `domain/record/shapes.py` · `rules.py` | tier 1, generated from the ontology (closed predicates, required, cardinality, datatype, enum, id prefix); tier 2, the cross-node rules, each a SPARQL query with a fix, each with a mutation test |
| `application/record/load.py` · `domain/record/store.py` | a workspace in memory: the record graphs copied out of the store (or a write's candidate graphs) plus the shipped vocabulary, derived triples in `j:derived`, every rule run on every load |
| `infra/oxigraph/db.py` | the record on disk: one RocksDB store per workspace at `career/store/`, a named graph per record, the writers' turn (a blocking OS lock), one update per write, dump and parse. The only module that opens the store |
| `infra/legacy_import.py` | a workspace still laid out as `.ttl` files, read once for `jsk kb load` - validated as before, numbers kept as the store keeps them and each rewrite reported |
| `infra/oxigraph/record.py` | **the write gate**: revision and log entry (`prepared`), `state` (clean, out-of-sync, missing - and, for the files the import reads, hand-edited, torn and unlogged), `turn` - the writer's turn, taken before a writing command reads the record, and before it asks whether a store exists - `unrecorded` (is the career what the log's newest `kbSha256` hashed: `jsk kb check` and a dump's load ask it) and `write_graphs`: every touched graph in one `db.replace_graphs`, then `.jsk/backup.trig`; a failure after the update landed is `Written`, never "nothing was changed". The only caller of `replace_graphs` |
| `domain/record/changeset.py` · `edit.py` · `adapters/cli/kb/` | `jsk kb`: a changeset read and refused or merged, and every verb over the record. `changeset.numbers_as_kept` refuses a number the store would rewrite (`8.40`) - in changesets, posting builds and dumps `jsk kb load` reads; not a rule id, since the import rewrites and lists them instead |
| `domain/record/pack.py` · `merge.py` | `jsk kb pack` (the capability starter pack) and `jsk kb merge` (two concepts that are one), each drafted as a changeset and never applied |
| `domain/matching/` · `application/record/queries.py` · `application/tailor/match_posting.py` | the vocabulary and the named questions; `jsk tailor match` |
| `domain/matching/scoring.py` | the numbers the match ranks by: seniority order, the requirement weights, recency points, months of experience. Standard library only |
| `domain/selection/select.py` · `application/tailor/export.py` | what a resume for one posting selects (projects, bullets, skill order) and `jsk kb export`, which writes it as the short file |
| `domain/posting/decide.py` · `application/posting/` | `decisions.txt` read; `jsk posting extract` and `build`, which write the posting graph from it |
| `application/tailor/prepare.py` | `jsk tailor prepare`: the check, the match, the evidence, the person and the cover, in one digest |
| `domain/assessment/` · `application/tailor/check_gaps.py` | the assessment: derived from the match with no model; the draft `gaps.txt`; `gaps.txt` read; the overlay checked, folded in, and written as the gaps graph and `gaps.md` |
| `domain/record/view.py` · `application/timeline/` | `jsk kb view`; `jsk app freeze`'s application graph and `jsk app event` |

The real ports are bound to these use cases in one place, the composition root
`adapters/cli/compose/`: the load over `career/store/` and the engine, the match and the
selection over the engine's feature reads, an application's folder and its graphs.

**Its boundaries.** Only `infra/oxigraph/db.py` opens `career/store/`, and only
`infra/oxigraph/record.py` calls `db.replace_graphs`; `tests/test_db.py` fails if anything else
does. So every write - `jsk kb`'s verbs, `jsk kb new`, the posting and gaps builds, `jsk app
freeze` and `jsk app event` - goes through `record.write_graphs` after the would-be record
validates, in one update of the store. A write to the career lands with its log entry in that
update; `jsk app freeze`, `jsk app event` and the builds write only an application's graphs and add
no entry, since the log is the career's history. The SPARQL queries are not storage access: they
ask a validated in-memory store about a career. Rule text and the named queries stay SPARQL over
`Store.select`; a feature's read is a `RecordQueries` method, its text in
`infra/oxigraph/queries.py`.

Which module may import which is the rings' rule, and `tests/test_layers.py` holds it: an import
points at its own ring or one further in. Nothing in the renderer imports the record's modules but
through the composition root's load, and nothing in them imports the renderer.

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
- `jsk-resume-author` reads `jsk tailor match` and `jsk kb show <ids>`, and bullets it writes for the
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

`jsk-verifier` is the conditional one. `jsk resume ship` and `jsk resume check` on a directory run the record, parse,
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
  cli.py                            the `jsk` console script's module: hands over to adapters/cli/main.py
  paths.py                          where the packaged schema lives - stated once
  preflight.py                      `jsk doctor`: what this machine can do
  domain/                           the innermost ring: no files, argv, environment or clock
    naming.py                       a record graph's short name and its IRI, the same in memory and on disk
    record/confirmation.py          what a confirmation's quote must share with its claim
    record/provenance.py            what a hand edit of the career raised, named for the import
    gates/numbers.py  report.py     numbers in prose and whether metrics hold them; a gate's findings
    gates/ats_rules.py              the parse gate's rules over extracted text and fonts
    gates/prose_rules.py            the prose gate's rules over a .tex's or .txt's paragraphs
    gates/layout_rules.py           the layout gate's rules over page sizes, line boxes and fonts
    gates/letter_rules.py           the letter check's rules over a letter's words: length, prose, quotes
    resume/constants.py             the provenance floor's ranks and a skills row's length
    resume/plan.py                  the render plan: every content decision, made exactly once
    resume/short.py                 a resume.json as data: parsed, its shape, its ids, its summary
    ontology.py  record/writer.py   the format, as data; the entry printer (moved from graph/)
    record/career.py                the career graph as the builder, export and match read it
    record/parsed.py                a Turtle or TriG text as parsed: quads, subject lines, comments
    record/state.py                 the career and its log in step: revision, state, stamp, entry
    record/store.py                 a loaded workspace: its graphs, findings and engine; the derivations
    record/decisions.py             decisions.txt's format and its parser: header, rows, drops
    record/rules.py                 tier 2: the rules over the whole workspace, as SPARQL rows
    record/changeset.py             a parsed changeset read, and what it may never say refused
    record/edit.py                  a changeset merged into the career, refused where the career says
    record/pack.py                  a starter pack's draft against the workspace, and its TriG
    record/merge.py                 two concepts that are one, drafted as a changeset
    matching/model.py               the match's values: requirement, resolution, match, row, question
    matching/resolve.py             a requirement resolved to concepts, carried by projects; evidence
    matching/rank.py  cover.py      the projects scored for a posting; the smallest set carrying it
    matching/nearest.py             the concepts nearest a label, and those an advert line names
    matching/questions.py           the questions a tailoring round asks of a match
    matching/report.py              a bucket's verdict, a missing metric's question, the FAILs that block
    selection/select.py             the projects, bullets, skills and gaps a resume selects
    posting/errors.py               posting.md's name, and how a posting step refuses
    timeline/errors.py              how a write to an application refuses: sent, locked, refused
    timeline/events.py              an application's graph and its events as triples; the dates they carry
    posting/boards.py               which job board a URL is on, and its answer as a posting
    posting/html_text.py            a board's or a saved page's HTML as text
    posting/posting_md.py           posting.md as jsk writes it
    posting/advert.py               an advert's text squashed, and its lines numbered by section
    posting/decide.py               decisions.txt's name, a title's seniority hint, posting.md's header, the posting's triples
    assessment/verdict.py           the order verdicts rank in, and why none is ever raised
    assessment/overlay.py           gaps.txt's format and its parser: the analyst's overlay
    assessment/derive.py            the gap assessment the match already knows, without a model
    assessment/fold.py              gaps.txt checked against the derived assessment and folded in; its triples
    assessment/draft.py             the gaps.txt draft: a slot wherever the analyst's judgement is needed
    render/formatting.py  themes.py how one value reads; appearance only (moved from render/)
    render/fit_levers.py            the page fitter's levers and floors over a .tex's text; page geometry read
    render/page_report.py           the line a render says about its pages, against the budget
    render/targets.py               which files a render writes, and what they are called
  ports/                            what the application needs from outside, as Protocols
    engine.py  record.py  codec.py  the graph engine; the record on disk; Turtle and TriG
    files.py  tex.py  pdf.py        authored texts and application files; the TeX engine; a PDF read
    posting_source.py  profiles.py  a job board's API; the region profiles
    clock.py  queries.py            today; the feature reads over a loaded record
    workspace.py                    a workspace as loading it needs it
    outputs.py                      the files a render writes, and its scratch directories
    advert.py                       an application's posting.md and decisions.txt, as the rules read them
    applications.py                 an application's folder and its record graphs in the store
  application/                      the use cases: each returns a result and prints nothing
    guards.py                       the refusals several commands share, returned as lines
    gates/__init__.py               the four mechanical gates, and the fifth, which a person runs
    gates/numbers.py                the untraced-number check over a loaded career
    tailor/match_text.py            the match as markdown; its sections, shared with the gaps draft
    tailor/match_posting.py         one application's posting matched against the career, as plain data
    tailor/check_gaps.py            gaps.txt checked, the assessment and gaps.md written from the match
    tailor/draft_gaps.py            the gaps.txt draft: the advert, the drops and the person read, the draft made
    tailor/prepare.py               the tailoring digest: the check, the match, the evidence, the assessment written
    posting/fetch.py                an advert from a job board or a file, written as posting.md
    posting/extract.py              the decisions.txt header and the advert's lines, numbered, for the analyst
    posting/build.py                decisions.txt checked against the advert and written as the posting graph
    gates/result.py                 what a gate returns: its findings, or why it stopped
    gates/ats.py                    the parse gate: a document's text extracted, then judged
    gates/prose.py                  the prose gate: a document's paragraphs read, then judged
    gates/layout.py                 the layout gate: a PDF's region and budget found, its lines judged
    gates/record.py                 the record gate: a resume.json's career loaded, every finding asked of it
    gates/letter.py                 the letter check: its length and prose judged, its numbers traced
    gates/run_gates.py              `jsk resume check DIR`: the four gates over a render, the render gate said last
    tailor/match_text.py            the match's sections as markdown, shared with the gaps draft
    tailor/export.py                `jsk kb export`: the bullets a resume.json shows chosen, the short file formed and written
    record/load.py                  loading a workspace: graphs into an engine, types derived, rules run
    record/refusals.py              how a use case over the record refuses: the errors the CLI prints
    record/read.py                  `jsk kb show`, `view` and `log`: entries by id, the career, the log
    record/queries.py               `jsk kb query`: the named queries, registered as the kb's read vocabulary
    record/holdings.py              what each live project holds; the months of experience behind a concept
    record/likeness.py              projects that look like one another, or like what some words describe
    record/check.py                 `jsk kb check`: every rule, the career's hash, the untraced numbers
    record/store_status.py          where a workspace's record is, and what is there instead
    record/dump.py                  `jsk kb dump`: the whole record as TriG
    record/pack.py  merge.py        `jsk kb pack` and `merge`: changesets drafted on the logged revision
    record/write.py                 WriteLogged, the gate every kb write goes through; `jsk kb apply`
    record/confirm.py               `jsk kb confirm`: the answer checked, the ids planned, the summary
    record/scaffold.py              `jsk kb new`: the empty record written, or a record started over
    record/load_import.py           `jsk kb load`: files or a dump read, validated, written once
    render/load_resume.py           a resume.json read, its workspace found, its career loaded, checked
    render/build_plan.py            a resume.json on disk to its render plan
    render/render_resume.py         one render: plans built, files written, the PDF compiled and measured
    render/fit_pages.py             a .tex fitted to its budget: each lever staged, compiled, measured
    render/preview_templates.py     one resume.json in every template, rendered once each and compiled at once
    timeline/freeze.py              an application frozen: checked, planned, gated, renamed to its day, written
    timeline/records.py             an application's record graphs: frozen, sent, written; the freeze sealed
    timeline/add_event.py           one event added to an application's record: minted, validated, written
    ship.py                         `jsk resume ship`: the record gate, render, fit and gates, stopping at a failure
  infra/                            what touches a disk, a process, the network or the engine
    files.py                        the workspace on disk: find_root; a document written atomically, or new
    workspace.py                    the workspace a load reads: career/store/, the files beside it, the vocabulary
    legacy_import.py                a workspace still laid out as .ttl files, read once for `jsk kb load`
    packs.py                        `jsk kb pack`'s starter packs on disk: where each is, and reading one
    pdf.py                          a rendered PDF's text and fonts, through pymupdf
    profiles.py                     the region profiles under data/ (moved from render/)
    oxigraph/codec.py               Turtle and TriG parsed through the engine; numbers as it keeps them
    oxigraph/db.py  record.py       the store on disk; the write gate every write goes through
    oxigraph/applications.py        an application's folder and its graphs in career/store/, read and written
    oxigraph/engine.py              the in-memory engine a loaded record runs on
    oxigraph/queries.py             the feature reads over a loaded record, as SPARQL
    tex.py                          the TeX engine a render's .tex is compiled with (moved from render/)
    posting_sources.py              a board's JSON over the network; a .docx, .html or text file
    outputs.py                      a render's files written, its scratch directories, a move
    documents.py                    what the gates judge, read leniently: a rendered .txt or .tex, a cover letter
  adapters/                         the driving side: argv parsed, a use case run, its result printed
    cli/main.py                     the dispatcher: seven nouns, each verb run in process, the retired names
    cli/dispatch.py                 a verb's adapter found (ADAPTERS) and its main() called, contained
    cli/doctor.py                   `jsk doctor`: the preflight, then the record's store
    cli/resume.py                   `jsk resume check`: the gates its target calls for, by its kind
    cli/render.py                   `jsk resume render`: its flags, the render run, what it wrote said
    cli/fit.py                      `jsk resume fit`: its flags, the fit run, each lever and the verdict said
    cli/preview.py                  `jsk resume preview`: its flags, every template previewed, the pages said
    cli/freeze.py                   `jsk app freeze`: its flags, the freeze run, its gates and what it wrote said
    cli/ship.py                     `jsk resume ship`: its flags and refusals, each step captured, the summary
    cli/event.py                    `jsk app event`: its flags, the clock read once, the event added and its dates said
    cli/match.py                    `jsk tailor match`: its flags, the match run and printed, or its assessment built
    cli/options.py                  --cover and --today, which the tailoring commands share, parsed once
    cli/tailor.py                   `jsk tailor prepare`: its flags, the digest run and printed section by section
    cli/posting.py                  `jsk posting`: fetch, extract or build run, what it wrote said
    cli/cliutil.py                  one contract for --help and flags across the commands; a finding list printed
    cli/presenters.py               what the kb verbs print alike: a refusal, findings, a usage error, a table
    cli/compose/__init__.py         the composition root: the real ports bound to the use cases, one module per area
    cli/compose/record.py           a workspace loaded over career/store/ and the engine; a changeset read
    cli/compose/match.py            the match and the selection, each asked of the engine's feature reads
    cli/compose/posting.py          `jsk posting`'s board API and file reader; extract and build's folder on disk, decisions.txt read
    cli/compose/timeline.py         an application's record bound to the store on disk: frozen, sent, the freeze
    cli/compose/tailor.py           the tailoring commands' ports bound: the digest's named reads, the short file, the assessment's folder
    cli/compose/resume.py           a resume.json read from disk, its workspace found, its career loaded, its plan built
    cli/compose/render.py           `jsk resume render`'s TeX engine and PDF reader; the posting's employer
    cli/compose/fit.py              `jsk resume fit`'s TeX engine, looked up where a test patches it
    cli/compose/preview.py          `jsk resume preview`'s TeX engine, looked up where a test patches it
    cli/compose/gates.py            the gates' career reads and its log's state bound; a resume.json's region and budget
    cli/kb/__init__.py              `jsk kb`: the verb table, its flags, and the dispatch
    cli/kb/read.py                  `jsk kb show`, `view`, `query`, `check`, `path` and `log`
    cli/kb/load.py                  `jsk kb load` and `dump`: the record in, and out as TriG
    cli/kb/write.py                 `jsk kb apply`, and the logged write's diff every writing verb prints
    cli/kb/new.py                   `jsk kb new`: its flags, the workspace scaffolded, what was written
    cli/kb/confirm.py               `jsk kb confirm`: its three forms, and what each confirmed
    cli/kb/draft.py                 `jsk kb pack` and `merge`: the drafted changeset printed or written
    cli/kb/export.py                `jsk kb export`: its flags, the choice's notes and gaps, the file
    cli/gates/__init__.py           the gates' commands, one module a gate
    cli/gates/present.py            the count line, findings and verdict every gate prints alike
    cli/gates/ats.py                the parse gate: its flags, the gate run, its verdict said
    cli/gates/prose.py              the prose gate: its flags, the gate run, its verdict said
    cli/gates/layout.py             the layout gate: its flags, the gate run, its verdict said
    cli/gates/record.py             the record gate (`jsk resume check` on a resume.json): its flags, the gate run, its verdict
    cli/gates/letter.py             the letter check: its flags, the check run, its verdict said
    cli/gates/short.py              the short file's own check of a resume.json: its shape and ids, PASS or FAIL
    cli/gates/check.py              `jsk resume check` on each target kind: each gate contained, the summary
    adverts.py                      an application's posting.md and decisions.txt, read from its folder
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
to `career/store/` goes through `record.write_graphs` (from `jsk kb`, `jsk kb new`, the posting
builds, `jsk app freeze` and `jsk app event`), and every load validates it. No agent reads a file under `career/`. The skill exports each `resume.json` from the career and edits its order,
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
| `render/`: rendering, preview and the page fitter, over the plan→document pipeline | **3**, all lazy and all from the two CLIs: `resume.build`, `resume.short`, `cli` (`frozen_refusal`) | 11 | **made**, and gone since: its modules are in the rings (see "The renderer, across the rings") |
| `gates/`: record, parse, prose, layout, letter | **11**: six `graph/` modules, three `resume/`, two `render/`. All lazy except `record.py`'s import of `graph.ontology`, which is standard library only | 10 | **failed the test** (below), and gone since: the rules are `domain/gates/`, the runners `application/gates/` (Ruling 1 of the onion design) |
| `graph/`: the career record, from format to assessment | **7** when measured | 202 | **made**, and gone since: its modules are in the rings (see "The career record, across the rings") |
| `resume/`: the short file, the career as read for a resume, the plan builder | **8**, into `graph/` and `render/` | 4 | **made as the seam**, not by this test: it is the one place the career meets the renderer, and keeping that join in one package is what keeps `graph/` and `render/` from importing each other. Gone since: its modules are in the rings (see "The resume, across the rings") |

`gates/` passed the test when it held three gates. The record gate and the letter check had
since grown into readers of the career, and between them they imported from eleven modules
outside the package, against ten imports among the gates themselves. The rings settled it: the
rules are `domain/gates/`, the use cases `application/gates/`, and the career's reads come in
through `adapters/cli/compose/gates.py`.

The reason for measuring applies to anything proposed here: four modules that all operate on the same
noun and never import each other would gain a boundary crossing per edge and buy nothing but a
directory named after what they have in common.

`dispatch.ADAPTERS` is the one map from a documented script name to the adapter that serves it,
and `tests/fixtures.load_script` reads that map rather than keeping a second copy.

## Where do I change X

| To change | Edit | And also |
|---|---|---|
| What the parse gate rejects | `src/jsk/domain/gates/ats_rules.py` | `references/ats-rules.md`, `tests/test_check_ats.py` |
| What the prose gate rejects | `src/jsk/domain/gates/prose_rules.py` | `references/writing-rules.md`, `tests/test_check_prose.py` |
| What the layout gate rejects | `src/jsk/domain/gates/layout_rules.py` | `docs/SCRIPTS.md`, `tests/test_layout.py` |
| What makes a `resume.json` fail | `src/jsk/application/gates/record.py`, `src/jsk/domain/resume/short.py` (shape, ids) | `references/resume-format.md`, `tests/test_record_gate.py`, `tests/test_short.py` |
| A key in `resume.json` | `short.KEYS` in `src/jsk/domain/resume/short.py` | `references/resume-format.md`, `domain/resume/plan.py`, `export.short_file` |
| **What content is selected** | `src/jsk/domain/resume/plan.py` | never an emitter; `tests/test_build.py` |
| **How a document looks** | `src/jsk/domain/render/emit_*.py` | never `plan.py` |
| **A palette, typeface or rule** | `src/jsk/domain/render/themes.py` | `references/templates.md`, `tests/test_themes.py` |
| Support for a new market | `data/schema/profiles/<code>.json` | `profile.schema.json`, `region` in `references/resume-format.md` |
| **The career record's format** | `src/jsk/domain/ontology.py` | `references/kb-format.md` and `docs/ONTOLOGY.md` — the ontology is the format and the reference is its prose; a class, predicate or section in one and not the other is a defect. The writer and the tier-1 rules follow the ontology by themselves |
| A rule across entries | `src/jsk/domain/record/rules.py` | a mutation in `tests/test_graph_rules.py` — a rule with no mutation fails the suite |
| The shipped vocabulary | `src/jsk/data/vocabulary.ttl` | technologies only, no `implies`; `tests/test_graph_vocabulary.py` |
| The capability starter pack | `src/jsk/data/capabilities.ttl`, `src/jsk/infra/packs.py`, `src/jsk/domain/record/pack.py` | applied to the career as a changeset, never loaded as vocabulary; `tests/test_graph_pack.py` |
| Where the record is stored, or how a write lands | `src/jsk/infra/oxigraph/db.py` (storage), `src/jsk/infra/oxigraph/record.py` (the write gate) | `tests/test_db.py`, which also fails a second module that opens the store or writes it |
| What `jsk kb new` scaffolds | `src/jsk/application/record/scaffold.py` | `tests/test_kb_new.py`, `references/mode-setup.md` |
| A posting's or assessment's shape | `Posting`, `Requirement`, `Assessment` and `Verdict` in `ontology.py` | `application/posting/build.py` and `application/tailor/check_gaps.py`, which write them; `references/mode-tailor.md`, `agents/jsk-tailor-analyst.md` |
| What the analyst may write | `domain/record/decisions.py` (`decisions.txt`), `domain/assessment/overlay.py` (`gaps.txt`) | the checks in `domain/posting/decide.py` and `domain/assessment/fold.py`; `agents/jsk-tailor-analyst.md` |
| How the career's projects are ranked for a posting | `rank` in `src/jsk/domain/matching/rank.py`; the weights in `src/jsk/domain/matching/scoring.py` | `cover` in `cover.py` beside it, and `src/jsk/domain/selection/select.py`, which keeps only confirmed evidence before choosing; `docs/ONTOLOGY.md` §11 |
| What the record gate checks | `src/jsk/application/gates/record.py`, `numbers.py` | `docs/SCRIPTS.md`'s table of its checks, `tests/test_record_gate.py` |
| A mode's procedure | `references/mode-<name>.md` | the routing table in `SKILL.md` |
| What an agent may do | `plugins/jsk/agents/<name>.md` | the delegation note in every mode that calls it, and the Agents table in `SKILL.md` |
| Add a mode | a new `references/mode-<name>.md` | routing table in `SKILL.md`, a `commands/<name>.md` |
| A noun or a verb | `src/jsk/adapters/cli/main.py` (the noun table) | the help docstring in the same file, the command table in `SKILL.md`, `docs/SCRIPTS.md` — all three pinned by `tests/test_plugin_surface.py` |

## What is frozen

This is a published plugin. Three surfaces may not move without a major version and a migration
story:

1. **The `jsk` command surface.** Nouns, verbs and flags — `jsk resume check --strict`,
   `jsk resume ship --ats-max`, `jsk kb apply --dry-run` and the rest — are public API. They appear in shell
   histories, in README examples, and in every mode file. Module names inside the package are free;
   the invocation surface is not.

   Version 4.0 replaced the `okf` command and its bundle format outright, with no compatibility shim:
   a shim over a per-noun write command would have to write into a file whose shape it cannot know.
   The graph record retires two subcommands the same way, with a pointer rather than a shim:
   `jsk index` read `user-knowledgebase.md` and now exits 2 naming `jsk tailor match` and `jsk kb view`;
   `jsk migrate` moved that file to the graph and now says the Markdown knowledge base is no longer
   read, naming `jsk kb new PATH --name NAME`. The short file retired flags the same way: `--urs` and `--refresh` on `jsk kb
   export` are usage errors naming what replaced them, and `--view` is gone from `render`, `ship`,
   `gates` and `freeze` - a `resume.json` is one resume. The store retired `jsk kb adopt` and
   `jsk kb fmt` outright - there is no hand edit to adopt and no file layout to restore - and
   `jsk tailor match`, `jsk kb export --from-match` and `jsk tailor prepare` take the application
   directory, refusing a `posting.ttl` path with the new form in the fix. The move to
   `jsk <noun> <verb>` retired every top-level command but `doctor`, `kb`, `posting` and `tailor`
   the same way, and the `python -m jsk.<module>` paths with them: each exits 2 naming its
   replacement, and no flag changed.

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
   entry, and `jsk kb new --force` keeps the old record as `career/kb.r<N>.trig` and starts over.

   The files under `career/store/` are **not** this surface: they are RocksDB as the pinned
   pyoxigraph writes it. The portable form is the TriG `jsk kb dump` writes and `jsk kb load`
   reads; raising the pyoxigraph pin is a dump with the old version and a load with the new one,
   and CI on Windows and Linux. A workspace still laid out as `.ttl` files (before the store) is
   imported once with `jsk kb load .`; any other command there refuses, naming that fix.

**The career record and its boundaries** are what hold the third one: every write goes through
`record.write_graphs` after the would-be record validates, and the record's modules never import
`render/`. See "The career record, across the rings" above.

A bundle from a version before 4.0 has one route: read it whole and build the record from it
with `jsk kb new` and changesets - and a changeset cannot confirm, so it carries `needs-verification` and
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
does not have, such as `jsk resume ship` on an older install — fails mid-session on a usage error. The fix
is a floor the skill states and `jsk doctor --require X.Y` enforces; it is not built.

---

Next: [Why it works this way](WHY.md) · [Commands](SCRIPTS.md)
