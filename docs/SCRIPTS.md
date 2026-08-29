# Scripts

The skill runs these for you. This page is for running them yourself.

All twelve live in `plugins/jsk/skills/jsk/scripts/`. Paths below assume you are in that
directory. On Windows use `python` or `py -3` in place of `python3`.

## One entry point: `okf.py`

If you would rather not remember thirteen names:

```bash
python3 scripts/okf.py doctor                  # what works on this machine
python3 scripts/okf.py new ./my-career --name "Your Name"
python3 scripts/okf.py validate resume.json         # a record
python3 scripts/okf.py validate acme.posting.json  # or a posting
python3 scripts/okf.py validate acme.gaps.json     # or an assessment
python3 scripts/okf.py validate ./my-career        # or a bundle - it dispatches
python3 scripts/okf.py render resume.json --out . --pdf
python3 scripts/okf.py check resume.pdf        # both document gates, one pass
python3 scripts/okf.py score record.json acme.posting.json
python3 scripts/okf.py fit resume.tex --target-pages 2
```

Every subcommand forwards to the script below with the same arguments and the same exit code, so
everything documented here stays true through it. **The thirteen scripts remain the stable API** — this
is a convenience layer, not a replacement, and nothing that works today stops working.

Two subcommands do slightly more than forward:

- `okf check` runs the parse gate *and* the prose gate on one file, and keeps going after the first
  one fails, because a document with parse problems usually has prose problems too. It exits with the
  worse of the two codes, and reminds you that the record and render gates are separate.
- `okf validate` sends a directory to `validate_bundle.py` and a `.json` file to `validate_urs.py`.
  A `.posting.json` or `.gaps.json` is refused by name: those are archived UJD and UGS documents
  from an application already sent, both formats are retired, and a frozen document is meant to be
  re-read by a person rather than re-checked by a tool.

## Exit codes

Uniform across every script:

| Code | Means |
|---|---|
| `0` | passed |
| `1` | failed — a real finding, or a dependency missing that makes the answer unknowable |
| `2` | you called it wrong — bad usage, or a file that is not there |

A script never passes quietly when it could not do its job. A page count nobody measured is a page
count nobody knows.

## Start here

### `preflight.py`

```bash
python3 scripts/preflight.py                 # what works on this machine
python3 scripts/preflight.py --verify        # prove it, end to end
python3 scripts/preflight.py --json          # machine-readable
python3 scripts/preflight.py --bundle PATH   # also check a bundle
```

`--verify` renders the shipped example document and runs the parse and prose gates on the result, so
a pass means the pipeline genuinely works here rather than looking like it should.

Verdicts: `READY` · `READY, with gaps` · `BLOCKED` (the install is broken) · `BROKEN` (the toolchain
is present but failed its own gates — that is a bug in the skill, not in your setup).

Gaps are reported by what they *disable*, not by package name. Runs on a bare Python: a preflight
that needs installing first is not a preflight.

### `init_bundle.py`

```bash
python3 scripts/init_bundle.py ./my-career --name "Your Name"
```

Creates an empty bundle skeleton. No dependencies.

## The record

### `validate_urs.py`

```bash
python3 scripts/validate_urs.py <bundle | resume.json>
python3 scripts/validate_urs.py <bundle | resume.json> --level 2
python3 scripts/validate_urs.py <bundle | resume.json> --strict
```

The **record gate**. Run it before anything renders. Checks that the record is coherent and that
every numeral in a bullet traces to a structured metric on that bullet.

`--level N` asserts a conformance level (0, 1 or 2). Full JSON Schema validation runs additionally
when `jsonschema` happens to be installed; the structural rules run either way.

### `render_resume.py`

```bash
python3 scripts/render_resume.py <bundle | resume.json> --out DIR
python3 scripts/render_resume.py <bundle | resume.json> --out DIR --pdf
python3 scripts/render_resume.py <bundle | resume.json> --out DIR --view view_au_default
python3 scripts/render_resume.py <bundle | resume.json> --out DIR --region au
python3 scripts/render_resume.py <bundle | resume.json> --out DIR --pdf --ats-max
```

One record to `.tex` (and PDF with `--pdf`) plus `.txt`. The PDF is the only rendered deliverable;
`--ats-max` chooses which variant it holds rather than adding a second file.

| Flag | Does |
|---|---|
| `--out DIR` | where to write (default `.`) |
| `--pdf` | also run the TeX engine |
| `--view ID` | render a tailored view |
| `--region CODE` | apply a region profile |
| `--profile PATH` | a profile file directly |
| `--format` | `all` (default), or one of `latex` / `txt` |
| `--ats-max` | render the PDF in the ATS-maximal variant (shorthand for `--profile ats-maximal`) |
| `--template NAME` | the visual template (default `monolith`) |
| `--list-templates` | print the templates with what each is for, and exit |
| `--name` | override the output filename stem |

**With `--pdf`, a run that produced no PDF exits 1** and says **UNVERIFIED**. It used to record the
failure as a passing note and exit 0, so a caller could ask for a PDF, be told in passing there wasn't
one, and still see success.

`--template` and `--ats-max` are different axes and compose. The variant decides what the document
says; the template decides how it looks. All five templates extract to identical text, so the choice
is about the reader and never about the parse. An unknown name is a usage error rather than a silent
fall back to the default, because a resume rendered in a template nobody chose is a resume nobody has
looked at — and it would look perfectly fine. See `references/templates.md`.

### `preview_templates.py`

```bash
python3 scripts/preview_templates.py resume.json --out DIR
python3 scripts/preview_templates.py resume.json --out DIR --view view_acme --only meridian,ember
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
| `--view ID` / `--region CC` / `--ats-max` | passed straight through to `render_resume.py` |
| `--only A,B` | just these templates |

Exit 0 = every template rendered. Exit 1 = at least one did not, and that is reported rather than
worked around: a template that does not build is not a template, and the others may be about to
break too. Exit 2 = usage, or no TeX engine.

## The gates on the document

### `check_ats.py`

```bash
python3 scripts/check_ats.py resume.pdf             # the rendered deliverable
python3 scripts/check_ats.py resume_ATS.txt --strict  # the ASCII variant
```

The **parse gate**. Reads the PDF's text layer (or the `.txt`) for what makes applicant tracking
systems mangle a resume: text that does not extract at all, section words that appear in prose but
never in a heading, leftover bracketed placeholders, unparseable phone numbers, bullet glyphs a
parser will not map, and arrow glyphs that fuse job titles when stripped.

The structural checks — tables, text boxes, header content, second columns — are gone. One LaTeX
template produces every render and cannot express any of them, so the check moved from the output to
a golden-file test on the template, where it is proved rather than sampled. Needs `pymupdf` for a
PDF; the `.txt` path is standard library only.

### `check_prose.py`

```bash
python3 scripts/check_prose.py resume.tex
python3 scripts/check_prose.py resume_ATS.txt
```

The **prose gate** — the writing rules `check_ats.py` cannot see. Third person, unresolved
placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
across projects, bullets that clear their throat before the verb. It reads the `.tex` rather than the
PDF, because a bullet is an unambiguous `\item` there and needs no library to find. No dependencies.

## The bundle

### `validate_bundle.py`

```bash
python3 scripts/validate_bundle.py ./my-career
```

Bundle is well-formed. Needs `pyyaml`. Run it after any change to the bundle.

### `migrate_bundle.py`

Brings a bundle built on an earlier layout up to the current one.

```bash
python3 migrate_bundle.py <bundle>            # report what would change
python3 migrate_bundle.py <bundle> --apply    # make the changes
```

`index.md` carries `okf_bundle:`, an integer layout revision. An absent stamp means revision 1,
because every bundle created before the stamp existed has no way to say so.

| Revision | Shape |
|---|---|
| 1 | applications point at a mutable target file via `target:` |
| 2 | the posting is frozen beside each application as `<stem>.target.md` |
| 3 | an application's outcome is derived from an append-only `# Timeline` |
| 4 | the posting is a UJD document, `<stem>.posting.json` — superseded by 5 |
| 5 | roles and projects carry their relations in frontmatter, and the posting is `<stem>.posting.md` again |

Revisions 4 and 5 collapse into one step. A bundle below either converts its postings straight to
Markdown, because running revision 4's step first would write a document whose only reader was
deleted along with the format. A posting already frozen beside a sent application is left exactly
as it is.

Report mode **exits 1 when changes are pending**, which is what makes it usable as a check: an
out-of-date bundle is detectable without writing to it. `--apply` exits 0 only when nothing is left
for a person.

Nothing is deleted, and the run is idempotent. Where the migration cannot establish a fact — a
posting that was never captured, a snapshot taken months after the submission it belongs to — it
**reports the gap and marks what it wrote `needs-verification`** rather than filling it in. A
reconstructed posting that claims to be the original is precisely the failure the four gates exist to
prevent, and the tool is not exempt from its own rule.

Standard library only. Frontmatter is edited line by line rather than round-tripped through a YAML
parser, so comments, key order and quoting style survive and the change is legible in a diff.

### `pipeline.py`

What the job search needs from you this week, derived from every application's `# Timeline`.

```bash
python3 pipeline.py <bundle>                   # what needs attention, most urgent first
python3 pipeline.py <bundle> --all             # the full board, closed applications included
python3 pipeline.py <bundle> --company NAME    # every application to one employer
python3 pipeline.py <bundle> --as-of DATE      # compute against a date rather than today
python3 pipeline.py <bundle> --markdown        # a table, to paste into a file
```

**Exit 0 when nothing needs attention, 1 when something does**, 2 when called wrong — the same
convention as `migrate_bundle.py`'s dry run, and what makes it usable as a scheduled check.

`--as-of` exists for two reasons: deterministic tests, and answering "what did this look like when I
last checked". A report whose output depends on an unstated clock can neither be tested nor compared
with itself.

Decides nothing on its own. Stage, staleness and next action all come from `pipeline_model.py`, which
is also what `validate_bundle.py` checks against and what `migrate_bundle.py` writes — one module
decides what an event means, so the board and the application files cannot disagree.

Needs `pyyaml`.

### `score_projects.py`

```bash
python3 scripts/score_projects.py record.json acme.posting.json
python3 scripts/score_projects.py record.json acme.posting.json --markdown
python3 scripts/score_projects.py record.json acme.posting.json --as-of 2026
python3 scripts/score_projects.py record.json acme.posting.json --include-implicit
python3 scripts/score_projects.py record.json acme.posting.json --assume-technologies "python,aws"
```

Ranks the record's `projects[]` against the posting's `requirements[]`. Both sides are JSON, and that
is the point: the scorer and the gap analysis read **the same record**, so a ranking and a verdict
cannot disagree about what the record contains. Reports what each project *failed* to match.

Requirements marked `implicit` — ones the posting never stated — are excluded by default and the
exclusion is printed. `--include-implicit` scores them and prints that instead. An inference that
moves a ×3 term is an invented requirement, so neither choice is made silently.

Standard library only.

## Fitting

### `fit_pages.py`

```bash
python3 scripts/fit_pages.py resume.tex --target-pages 2
python3 scripts/fit_pages.py resume.tex --dry-run
python3 scripts/fit_pages.py resume.tex --in-place
python3 scripts/fit_pages.py resume.tex -o fitted.tex
```

Rewrites the density knobs in the `.tex`, recompiles, and measures the PDF that comes out. It applies
the levers in a fixed order — spacing, bullet spacing, margins, font size — stopping at the 10pt and
0.5" floors instead of crossing them. If the target is unreachable without a breach it exits
non-zero, because the remedy then is to cut evidence, not to shrink type.

It used to measure a `.docx` through LibreOffice while the PDF was what got sent. The two disagreed,
and a resume this reported as two pages shipped as three — a gate passing on a document nobody was
sending. It now measures the artefact that goes out.

Needs a TeX engine and `pymupdf`.

---

Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
