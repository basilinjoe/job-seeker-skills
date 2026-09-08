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
jsk validate resume.json         # the record gate
jsk render resume.json --out . --view view_default --pdf
jsk check resume.pdf             # both document gates, one pass
jsk gates .                      # all three mechanical gates
jsk fit resume.tex --target-pages 2
jsk preview resume.json --out ./looks
```

Each subcommand reaches the module documented below it with the same arguments and the same exit
code, so everything on this page is true through `jsk`. Some are called in this interpreter and some
in a child one; that is an implementation detail and never changes a verdict.

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

Writes `user-knowledgebase.md` with every heading present and empty, plus an `applications/`
directory beside it. No dependencies. It refuses rather than overwriting, because the file it would
replace is somebody's career.

What each heading is for is written into the file itself, as HTML comments beneath each one.
Guidance in a template a person is looking at gets read; guidance in a specification they have to go
and find does not.

## The record

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
installed.

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

## What is not here any more

Twenty-odd subcommands left with the bundle format, and it is worth knowing what replaced each rather
than looking for the flag:

| Was | Now |
|---|---|
| `okf compile` | nothing. There is no folder of concepts to assemble; the skill writes the record. |
| `okf validate <bundle>` | nothing. The knowledge base is prose. `jsk validate` checks the record written from it. |
| `okf migrate` | reading the old bundle and writing the new file — see `references/mode-setup.md`. |
| `okf project\|role\|bullet\|metric …` (16 write nouns) | `Edit` on one Markdown file. |
| `okf search\|list\|show\|refs\|stats` | `grep`, on one Markdown file. |
| `okf pipeline` | reading `applications/*/application.md` — see `references/mode-pipeline.md`. |
| `okf score` | `jsk-tailor-analyst` ranks in the open and shows its working. |
| `okf application file\|event` | renaming a directory and appending a timeline row. |

Each of those was solving a problem the folder created. What has genuinely been lost is the
enforcement: a write command refused a `--role` naming no role, and nothing does now until
`jsk validate` runs over a record. That is the trade, and `references/kb-spec.md` is where the habits
that replace it are written down.

---

Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
