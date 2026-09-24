# Commands

The skill runs these for you. This page is for running them yourself.

It is all one command. `pip install 'jsk-resume[all]'` puts `jsk` on your PATH; `python3 -m jsk` is
the same entry point where it is importable but not on PATH, and on Windows use `python` or `py -3`
in place of `python3`.

Every subcommand below also exists as a module you can run or import directly —
`python3 -m jsk.gates.check_ats resume.pdf`, `from jsk.urs import plan`. The headings name both.

**Nothing here reads `user-knowledgebase.md`.** That file is Markdown a person and the skill edit
with ordinary tools; this toolchain starts at the URS record written out of it, and carries it to a
document somebody can send.

## The whole surface

```bash
jsk doctor                       # what works on this machine
jsk new ./my-career --name "Your Name"
jsk index user-knowledgebase.md --rank applications/<dir>/posting.md
jsk match applications/<dir>/posting.ttl   # the same question, over the graph record
jsk kb apply changes.trig        # change the graph record; `jsk kb --help` lists the rest
jsk validate resume.json         # the record gate
jsk render resume.json --out . --view view_default --pdf
jsk check resume.pdf             # both document gates, one pass
jsk gates .                      # all three mechanical gates
jsk fit resume.tex --target-pages 2
jsk preview resume.json --out ./looks
jsk ship resume.json --out . --view view_default   # validate, render, gate
jsk freeze applications/<dir> --submitted 2026-09-08 --channel "Workday portal"
```

Each subcommand calls the module documented below it, in the same interpreter, with the same
arguments and the same exit code, so everything on this page is true through `jsk`. None of them
spawns a Python child: that cost a start-up and a fresh import per call, which was most of the wall
time of `jsk check`. The one exception is `jsk doctor`'s end-to-end run, which runs each module as
`python -m` on purpose — proving that entry point works from cold is what it is for.

## Exit codes

Uniform across every subcommand:

| Code | Means |
|---|---|
| `0` | passed |
| `1` | failed — a real finding, or a dependency missing that makes the answer unknowable |
| `2` | you called it wrong — bad usage, or a file that is not there |

Nothing here passes quietly when it could not do its job. A page count nobody measured is a page
count nobody knows.

## Start here

### `jsk doctor`

The `jsk.preflight` module.

```bash
jsk doctor                 # verifies end to end
jsk doctor --quick         # skip the render
jsk doctor --json          # machine-readable
jsk doctor --kb PATH       # check a specific user-knowledgebase.md
```

Bare `jsk doctor` renders the shipped example document and runs the parse and prose gates on the
result, so a pass means the pipeline genuinely works here rather than looking like it should.

Verdicts: `READY` · `READY, with gaps` · `BLOCKED` (the install is broken) · `BROKEN` (the toolchain
is present but failed its own gates — that is a bug in the skill, not in your setup).

Gaps are reported by what they *disable*, not by package name. Runs on a bare Python: a preflight
that needs installing first is not a preflight.

Without `--kb` it searches for `user-knowledgebase.md` three directories down. Searching by filename
rather than by a directory shape is deliberate — a bundle used to be recognised by the folders inside
it, so a half-created one was invisible here and reported as absent while the person was looking
straight at it.

### `jsk new`

The `jsk.kb` module.

```bash
jsk new ./my-career --name "Your Name"
jsk new ./my-career --name "Your Name" --force   # overwrite an existing file
```

Writes `user-knowledgebase.md` with every heading present and empty, plus `log.md` and an
`applications/` directory beside it. No dependencies. It refuses rather than overwriting, because the
file it would replace is somebody's career; `--force` replaces the knowledge base but never an
existing `log.md`.

What each heading is for is written into the file itself, as HTML comments beneath each one.
Guidance in a template a person is looking at gets read; guidance in a specification they have to go
and find does not.

### `jsk index`

The `jsk.kbindex` module.

```bash
jsk index user-knowledgebase.md                          # the overview
jsk index user-knowledgebase.md --rank posting.md        # plus the ranking and coverage
jsk index user-knowledgebase.md --rank posting.md --today 2026-09-23   # replay a past run
```

Needs markdown-it-py and pyyaml (`pip install markdown-it-py pyyaml`, the `index` extra); without
them it exits 1 saying so. Prints, never writes. Every section and entry with its line range; each project's strength,
recency, seniority, status and tags; roles with their dates and the years they cover, overlaps
counted once; the vocabulary, skills with aliases, metric ids and the unanswered questions. About a
seventh of the file it describes. It is generated each time because line numbers move on every edit.

`--rank` scores every project against the posting's `requirements` by the table in
`jsk-tailor-analyst.md`: required ×3, preferred ×1, strength ×2, recency +1 within three years and
+0.5 at four to six, seniority +1 at or above the posting's (the eight levels, most senior first).
Matches are exact strings against `capabilities` and `technologies`. A **Coverage** table follows:
which projects carry each requirement's term, and which terms the vocabulary does not have.

Exit 1 when the file is not in the shape `kb-spec.md` describes — a project with no `yaml` block, a
nested value in a flat block, a strength outside 1–5 — naming the entry. A project that failed to
parse quietly would score as absent evidence on every posting.

## The record

### `jsk match`

The `jsk.graph.match` module, over the queries in `jsk.graph.queries`.

```bash
jsk match applications/<dir>/posting.ttl                 # the four sections, as Markdown
jsk match applications/<dir>/posting.ttl --cover 2       # a cover of at most two projects
jsk match applications/<dir>/posting.ttl --json --today 2026-09-24
```

The graph record's `jsk index --rank`: a posting's requirements joined with the career through the
vocabulary - the shipped `jsk/data/vocabulary.ttl` and the knowledge base's own additions. Reads the
whole workspace the posting sits in (`career/kb.ttl`, `applications/*/`) and validates it first;
any FAIL is printed and nothing is matched. Needs pyoxigraph, a dependency of the package.

**Requirements** puts each one in a bucket: `matched` (a project holds the concept, or a narrower
one within two hops - `via c:aks, 1 hop`), `near` (only an `implies` path, for a required one, or
only something broader), `missing`, `ambiguous` (the label names several concepts; the analyst
answers with `j:concept`), `candidate` (it names none), `implicit`. Evidence per project is
`confirmed` (a confirmed bullet shows it), `unconfirmed` or `tag` (only the project's tags say so).
**Ranking** scores exactly as `jsk index --rank` does. **Cover** is the smallest set of projects,
at most `--cover` (default 3), carrying every required requirement anything carries. **Questions**
are derived from the gaps, never invented.

Exit 0 with the result - missing requirements included, since this is an assessment, not a gate;
1 when the workspace has a FAIL; 2 called wrong, or a path that is not
`applications/<dir>/posting.ttl`.

### `jsk kb`

The `jsk.graph.kbcli` module. One verb per operation on the graph record; `jsk kb --help` lists
them and `jsk kb <verb> --help` explains one. Every verb finds the workspace - the folder holding
`career/` - from the current directory, or takes `--root DIR`.

```bash
jsk kb apply changes.trig --dry-run      # the diff it would make, nothing written
jsk kb apply changes.trig                # merged, validated, written, logged
```

**`apply`** is how an agent changes `career/kb.ttl`: a changeset, in TriG, with four graphs.

```turtle
@prefix op: <tag:jsk,2026:op#> .
op:changeset op:base 7 ; op:summary "The payments project, from the braindump." .
op:add    { k:prj_payments j:name "Payments platform" ; j:strength 4 ; j:recency 2025 .
            [] j:project k:prj_payments ; j:rank 1 ; j:text "Cut settlement latency by 75%." . }
op:set    { k:prj_legacy j:strength 2 . }                     # replaces every value it names
op:retire { k:prj_intranet j:reason "Too old to earn a line." . }
op:delete { k:q_duplicate a op:Entry . k:ach_x j:shows c:java . }
```

`op:add` adds; a predicate that allows one value and already has one is refused - use `op:set`.
`op:set` replaces every value of each (entry, predicate) it names. `op:retire` dates the entry
today and keeps the reason. `op:delete` removes exact triples, or with `a op:Entry` the whole
entry - refused while anything points at it, since retiring is what keeps the history. `op:base`
is the log revision the changeset was drafted against: an entry changed after it is a conflict,
refused, to be re-read. The header's `op:summary` becomes the log entry's.

What apply does unasked: a new bullet (a `[]` with `j:project`) gets its id,
`ach_<project>_<three words of its text>`, never one the record has used. An entry whose claims
changed drops to `j:inferred`, and every entry left inferred gets a `q_` question unless one is
open. A metric version an application sent never changes: a new `j:value` becomes the next
version, and the one it replaces is closed. A changeset cannot confirm anything, cannot write
another file, cannot use blank nodes except for a new bullet, and cannot name a predicate the
ontology does not have (it suggests the nearest).

The record it would write is validated before anything is written, and so is the workspace
before it starts: a FAIL in the career, a hand edit not yet adopted, or a torn write refuses the
apply with the command that fixes it. Then `career/kb.ttl` is replaced, then `career/log.ttl`,
and a copy of what was written goes to `.jsk/kb.last.ttl` (a cache that ignores itself in git).
Two files cannot be replaced together atomically: a crash between them is detected on the next
load - `log-sync`, "the last write reached kb.ttl and not log.ttl" - not prevented. On Windows, a
file locked by an editor or a virus scanner is retried for about a second; if it stays locked
nothing is changed. Stdin (`-`) is refused: a pipe that never closes hangs the command.

```bash
jsk kb confirm k:ach_payments_cut_settlement_latency --answer "Yes: 800 ms before, 200 after, from the Grafana board."
jsk kb adopt                             # after a hand edit of kb.ttl
jsk kb fmt                               # after a jsk upgrade changed the layout
```

**`confirm`** is the only way an entry becomes `j:confirmed`, and it takes the person's answer in
their words: each id named is confirmed, every open question about it is answered today, and the
log entry keeps the answer beside the ids. An answer that says nothing - `yes`, `ok`,
`confirmed`, a placeholder - is refused, and one that reached the log by hand is flagged by
`answer-placeholder`. This is an instruction with an audit trail, not a proof that anyone asked.

**`adopt`** logs `kb.ttl` as it now is. Hand edits are legal; they are also invisible to the log
until adopted, so every write refuses until they are (`hand-edited`, a WARN, says so on every
load). Adopt lists every provenance the edit raised - an entry moved up to confirmed, added as
confirmed, or a claim changed while confirmed - comparing against `.jsk/kb.last.ttl`, the copy of
the last logged revision; without that copy it lists every confirmed entry. It also records a
torn write and a file restored on its own, and starts the log for a `kb.ttl` that has none.
Detection, not prevention: the edit already happened, and adopt makes it visible.

**`fmt`** rewrites a record file in the canonical layout: `kb.ttl` when none is named, logged on
its own (`by fmt`, the day unchanged) so no content change hides in a reformat. A `posting.ttl`
or `application.ttl` is rewritten in place, unlogged. Hand comments would be lost: `adopt` and
`fmt` refuse a file with any, listing them, unless `--drop-comments`.

Exit 0 written, or nothing to change; 1 refused, with every reason; 2 called wrong.

### `jsk validate`

The `jsk.gates.validate_urs` module.

```bash
jsk validate resume.json
jsk validate resume.json --strict            # warnings become failures
jsk validate resume.json --max-findings 0    # print every one
```

The **record gate**, and the one that got more important. The record used to be compiled from a
folder of concepts, so a structural check here would only have been re-checking the compiler. It is
written by hand now, which puts this command between a slip in that writing and a resume somebody
sends.

What it checks:

- **Shape** — every top-level key is one the renderer knows, `urs` and `person` are present, and
  every list key holds a list. This is the check the hand-authoring brought back. `experience:`
  written where `engagements:` belongs renders a resume with no jobs on it, and the mistake is
  invisible in the PDF precisely because the section is simply not there.
- **Ids** resolve, and nothing references something that is not in the document.
- **Periods** are coherent — no end before its start, no ongoing role with an end date.
- **Metrics** — every numeral in a bullet appears in some metric. This is the check that stops a
  rewritten clause quietly inflating a number.
- **Provenance** — nothing below a view's `provenance_floor` reaches that view.
- **Views** carry no free text and no key the renderer does not know.
- **Coverage** — a project rated `strength: 4` or better with no evidence fails; below that it warns.
- **Renderable at all** — a record with no views, or with neither engagements nor projects, fails.
  Every other check iterates a list, and an empty list satisfies all of them.

A directory is exit 2 with the file to pass instead, and so is a `.md` — failing on a JSON parse
error would tell somebody their record is malformed when what happened is that the bundle format
went away.

### `jsk render`

The `jsk.urs.render_resume` module.

```bash
jsk render resume.json --out DIR --view view_au_default
jsk render resume.json --out DIR --view view_acme --pdf
jsk render resume.json --out DIR --view view_acme --region au
jsk render resume.json --out DIR --view view_acme --pdf --ats-max
```

One record to `.tex` (and PDF with `--pdf`) plus `.txt`. The PDF is the only rendered deliverable;
`--ats-max` chooses which variant it holds rather than adding a second file.

**`--view` is required wherever the record holds more than one**, and leaving it out is exit 2 with
the ids listed — usage, not failure, because nothing is wrong with the record and the missing thing
is the one decision only a person can make. A record holding exactly one view still renders without
it.

| Flag | Does |
|---|---|
| `--out DIR` | where to write (default `.`) |
| `--pdf` | also run the TeX engine |
| `--view ID` | which view to render — required where the record holds more than one |
| `--region CODE` | apply a region profile |
| `--profile PATH` | a profile file directly |
| `--format` | `all` (default), or one of `latex` / `txt` |
| `--ats-max` | render the PDF in the ATS-maximal variant (shorthand for `--profile ats-maximal`) |
| `--template NAME` | the visual template (default `monolith`) |
| `--list-templates` | print the templates with what each is for, and exit |
| `--name` | override the output filename stem |

**With `--pdf`, a run that produced no PDF exits 1** and says **UNVERIFIED**. It used to record the
failure as a passing note and exit 0, so a caller could ask for a PDF, be told in passing there
wasn't one, and still see success.

**The page count is measured off the PDF**, with `pymupdf`, and printed only with `--pdf`:

```
  pages  Priya_Raman_Resume.pdf: 1 page against a budget of 2
```

It used to print the budget alone, which is the number somebody asked for rather than the number they
got — the resume that prompted the fix rendered on one page against a budget of two and said so
nowhere. Over budget is named (`- OVER BUDGET, run jsk fit`) and not failed: `jsk fit` owns that
verdict, and it is the command that can do something about it. Without `pymupdf` the line says the
budget and says it was not measured, which is the honest version of the same sentence.

`--template` and `--ats-max` are different axes and compose. The variant decides what the document
says; the template decides how it looks. All five templates extract to identical text, so the choice
is about the reader and never about the parse. An unknown name is a usage error rather than a silent
fall back to the default, because a resume rendered in a template nobody chose is a resume nobody has
looked at — and it would look perfectly fine. See `references/templates.md`.

### `jsk preview`

The `jsk.urs.preview_templates` module.

```bash
jsk preview resume.json --out DIR
jsk preview resume.json --out DIR --view view_acme --only meridian,ember
```

The same record rendered in every template, with the page count for each, so the look is chosen by
looking. Writes `DIR/<template>.pdf` and `.tex`, plus a `.png` of the first page where `pymupdf` is
installed. The `.tex` files are written one after another; the TeX compiles run side by side, each in
its own scratch directory, and the report still lists the templates in their fixed order.

Density is the one difference between templates that is not a matter of taste: the same record is
one page in a dense template and two in an airy one, and a two-page resume where a one-page resume
was available is a decision worth making on purpose.

| Flag | Does |
|---|---|
| `--out DIR` | required — previews are scratch, not deliverables |
| `--view ID` / `--region CC` / `--ats-max` | passed straight through to the renderer |
| `--only A,B` | just these templates |

Exit 0 = every template rendered. Exit 1 = at least one did not, and that is reported rather than
worked around: a template that does not build is not a template, and the others may be about to
break too. Exit 2 = usage, or no TeX engine.

## The gates on the document

### `jsk check --only parse`

The `jsk.gates.check_ats` module.

```bash
jsk check --only parse resume.pdf               # the rendered deliverable
jsk check --only parse resume_ATS.txt --strict  # the ASCII variant
```

The **parse gate**. Reads the PDF's text layer (or the `.txt`) for what makes applicant tracking
systems mangle a resume: text that does not extract at all, section words that appear in prose but
never in a heading, leftover bracketed placeholders, unparseable phone numbers, bullet glyphs a
parser will not map, and arrow glyphs that fuse job titles when stripped.

The structural checks — tables, text boxes, header content, second columns — are gone. One LaTeX
template produces every render and cannot express any of them, so the check moved from the output to
a golden-file test on the template, where it is proved rather than sampled. Needs `pymupdf` for a
PDF; the `.txt` path is standard library only.

### `jsk check --only prose`

The `jsk.gates.check_prose` module.

```bash
jsk check --only prose resume.tex
jsk check --only prose resume_ATS.txt
```

The **prose gate** — the writing rules the parse gate cannot see. Third person, unresolved
placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
across projects, bullets that clear their throat before the verb. It reads the `.tex` rather than the
PDF, because a bullet is an unambiguous `\item` there and needs no library to find. No dependencies.

### `jsk check`

Both document gates in one pass, on one file. Pass either sibling and the other is found beside it:
the parse gate reads what is actually sent — the PDF — while the prose gate reads the `.tex` it was
compiled from.

```bash
jsk check resume.pdf
jsk check resume.pdf --strict
```

A run with `--only` never closes by saying both passed. It names the three gates that did not.

### `jsk gates`

```bash
jsk gates <out-dir>
jsk gates <out-dir> --record applications/acme/resume.json --pages 2
jsk gates <out-dir> --view view_acme --json
jsk gates <out-dir> --max-findings 0
```

The record, parse and prose gates over one rendered output directory, in **one process**. It is the
five invocations a hand-run verification used to make — the record gate on `resume.json`, the parse
gate on the PDF and again on the `.txt` with `--strict`, the prose gate on the `.tex` and again on
the `.txt`. It imports the checkers rather than shelling out to them, and gives them the same
arguments, so the findings and the exit code are the ones the five commands produce. That
equivalence is what it is tested on.

`check_ats.py` and `check_prose.py` grew a `main(argv)` entry point so it could: same CLI, same
arguments, same output to the character, now callable without a subprocess. That entry point is
load-bearing rather than incidental, so it is documented here beside their CLIs.

**`--record` defaults to `resume.json` in the output directory**, which is where the skill writes it
for an application. Named rather than searched: a directory holding two records has no way to say
which one the documents came from, and guessing would put a passing record gate against a resume it
never described.

Three properties, each of them an existing rule here rather than a new one:

- **Every gate's output is printed verbatim, never summarised.** The person should see the evidence
  rather than take anyone's word for it. The section headers match `jsk check`.
- **A missing input is `SKIPPED` and a failure.** A gate that did not run is not a gate that passed.
  Same behaviour and same wording as `jsk check`. A path you *gave* that is not there is exit 2
  instead — omitting `--record` and mistyping it are different mistakes, and reporting them
  identically hides one. Both are non-zero.
- **It never attempts the render gate**, and closes with a line saying somebody has to open the PDF
  and read it. That gate is the one no command can have, and a command that exited 0 having silently
  skipped it would be the most dangerous thing in this directory.

`--view ID` is optional and does no work. The record names the view it was written for, so nothing
in the run reads the flag — it exists because this output is archived beside an application as
evidence, and passing it stamps which view was gated. It was *required* while a bundle held every
view and the command had no other way to know.

`--pages N` reports and never fails. It measures the PDF and prints the renderer's own over-budget
line, reused rather than restated. Over budget is named rather than failed everywhere in this
pipeline, because `jsk fit` owns that verdict and is the command that can act on it.

`--max-findings N` caps how many findings each gate lists — the same flag name and the same default
as `jsk validate`, because two gates that truncate differently are two gates people read differently.
The header counts stay true regardless: truncating a list is a reading aid, truncating a count is a
lie.

`--json` carries each checker's whole text in `gates[].output`, beside `gate`, `command`, `status`
and `exit`. It always includes a `render gate` entry with `status: "UNVERIFIED"` and `exit: null`,
so **the machine-readable form cannot report the render gate as passed either.** That is what makes
`--json` safe to consume here: it is the same evidence in a different envelope, never a summary.

The exit code is the worst gate's: `0` all passed, `1` any failed, `2` called wrong.

## Fitting

### `jsk fit`

The `jsk.urs.fit_pages` module.

```bash
jsk fit resume.tex --target-pages 2
jsk fit resume.tex --dry-run
jsk fit resume.tex --in-place
jsk fit resume.tex -o fitted.tex
```

Rewrites the density knobs in the `.tex`, recompiles, and measures the PDF that comes out. It applies
the levers in a fixed order — spacing, bullet spacing, margins, font size — stopping at the 10pt and
0.5" floors instead of crossing them. If the target is unreachable without a breach it exits
non-zero, because the remedy then is to cut evidence, not to shrink type.

It used to measure a `.docx` through LibreOffice while the PDF was what got sent. The two disagreed,
and a resume this reported as two pages shipped as three — a gate passing on a document nobody was
sending. It now measures the artefact that goes out.

Needs a TeX engine and `pymupdf`.

## Shipping

### `jsk ship`

```bash
jsk ship <resume.json> --out DIR --view ID [--ats-max] [--template N] [--pages N] [--json]
```

The three commands a ship used to be, in one process and in order, each step's output printed
verbatim under its own `---` heading the way `jsk gates` prints it:

1. **the record gate** — what `jsk validate <resume.json>` runs. A failure stops here and **nothing
   is rendered**: a PDF made from a record that failed its gate looks sendable and is not.
2. **the render** — what `jsk render <resume.json> --out DIR --view ID --pdf` runs, with `--ats-max`
   and `--template` passed through. A render that produced no PDF stops here.
3. **the parse and prose gates** — what `jsk gates DIR --record <resume.json> [--pages N]` runs,
   less the record gate step 1 has just run on the same file.

It closes with the same render-gate section `jsk gates` does: **nobody has read the PDF**, and the
command says so rather than exiting 0 over it. When it stopped early that section says nothing was
rendered, instead of pointing at a PDF an earlier run left in `DIR`. The page count is reported —
the renderer's own line, and `--pages N`'s — and never failed; `jsk fit` owns that verdict.

Exit `0` only if every step passed, `1` on any failure, `2` called wrong. `--json` carries every
step in `steps[]` in the `jsk gates` shape, the render gate last and `UNVERIFIED`.

### `jsk freeze`

```bash
jsk freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--view ID] [--doc FILE ...]
```

Freezes one `applications/<yyyy-mm-dd>-<company>-<role>/` directory the way `references/mode-ship.md`
describes: renames it to the day it was sent, if its leading date says otherwise, and writes
`application.md` beside `posting.md`, `gaps.md` and `resume.json`:

```markdown
---
company: Acme Health
title: Platform Engineer
view: view_acme_platform
submitted: 2026-09-08
channel: Workday portal
documents:
  - Priya_Raman_Acme_Resume.pdf
  - Priya_Raman_Acme_Resume_ATS.txt
---

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-09-08 | submitted | Workday portal | | |
```

`company` and `title` come from the top-level lines of `posting.md`'s frontmatter. The view is
`--view`, or the record's only one; a record with several and no `--view` is exit 2, naming them.
The documents are the `--doc` files, or every `.pdf` and `.txt` in the directory. The final path is
printed.

It refuses — exit 1, saying why, with nothing renamed and nothing written — when:

- **`application.md` already exists.** A frozen application is never re-frozen; later events are
  one appended row each, by hand.
- **any mechanical gate fails.** It runs what `jsk gates <app-dir> --record <app-dir>/resume.json`
  runs, in process, and prints it. A failing document is never frozen.
- `posting.md` has no `company:` or `title:`, there is nothing to list as documents, or the renamed
  directory would land on one that already exists.

`--submitted false` is for an application worked through and deliberately held back: it writes
`submitted: false`, leaves the directory's name alone, and the timeline has its header and **no
`submitted` row** — an accurate blank rather than a false green. It never touches
`user-knowledgebase.md` or `log.md`; the log row stays the skill's to write.

## What is not here any more

The `okf` commands left with the bundle format; what each one did is now an edit or a `grep` on
`user-knowledgebase.md`, `jsk validate` over the record written from it, or `jsk freeze`.

---

Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
