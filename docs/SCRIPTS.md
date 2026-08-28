# Scripts

The skill runs these for you. This page is for running them yourself.

All eleven live in `plugins/jsk/skills/jsk/scripts/`. Paths below assume you are in that
directory. On Windows use `python` or `py -3` in place of `python3`.

## One entry point: `okf.py`

If you would rather not remember eleven names:

```bash
python3 scripts/okf.py doctor                  # what works on this machine
python3 scripts/okf.py new ./my-career --name "Your Name"
python3 scripts/okf.py validate resume.json    # a record
python3 scripts/okf.py validate ./my-career    # or a bundle - it dispatches
python3 scripts/okf.py render resume.json --out . --pdf
python3 scripts/okf.py check resume.docx       # both document gates, one pass
python3 scripts/okf.py score ./my-career target.md
python3 scripts/okf.py fit resume.docx --target-pages 2
```

Every subcommand forwards to the script below with the same arguments and the same exit code, so
everything documented here stays true through it. **The eleven scripts remain the stable API** — this
is a convenience layer, not a replacement, and nothing that works today stops working.

Two subcommands do slightly more than forward:

- `okf check` runs the parse gate *and* the prose gate on one file, and keeps going after the first
  one fails, because a document with parse problems usually has prose problems too. It exits with the
  worse of the two codes, and reminds you that the record and render gates are separate.
- `okf validate` looks at the target: a `.json` goes to `validate_urs.py`, a directory to
  `validate_bundle.py`.

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
python3 scripts/validate_urs.py resume.json
python3 scripts/validate_urs.py resume.json --level 2
python3 scripts/validate_urs.py resume.json --strict
```

The **record gate**. Run it before anything renders. Checks that the record is coherent and that
every numeral in a bullet traces to a structured metric on that bullet.

`--level N` asserts a conformance level (0, 1 or 2). Full JSON Schema validation runs additionally
when `jsonschema` happens to be installed; the structural rules run either way.

### `render_resume.py`

```bash
python3 scripts/render_resume.py resume.json --out DIR
python3 scripts/render_resume.py resume.json --out DIR --pdf
python3 scripts/render_resume.py resume.json --out DIR --view view_au_default
python3 scripts/render_resume.py resume.json --out DIR --region au
python3 scripts/render_resume.py resume.json --out DIR --format docx
```

One record to `.tex` (and PDF with `--pdf`), both `.docx` variants and `.txt`.

| Flag | Does |
|---|---|
| `--out DIR` | where to write (default `.`) |
| `--pdf` | also run the TeX engine |
| `--view ID` | render a tailored view |
| `--region CODE` | apply a region profile |
| `--profile PATH` | a profile file directly |
| `--format` | `all` (default), or one of `tex` / `docx` / `txt` |
| `--name` | override the output filename stem |

Without a TeX engine it writes the `.tex` and reports the resume **unverified** rather than implying a
PDF nobody rendered.

## The gates on the document

### `check_ats.py`

```bash
python3 scripts/check_ats.py resume.docx            # presentation variant
python3 scripts/check_ats.py resume.docx --strict   # ATS-maximal variant
```

The **parse gate**. Inspects the generated `.docx` for what makes applicant tracking systems mangle a
resume: tables, text boxes, header/footer content, section words that appear in prose but never in a
heading, leftover bracketed placeholders, unparseable phone numbers, and arrow glyphs that fuse job
titles when stripped. No dependencies.

### `check_prose.py`

```bash
python3 scripts/check_prose.py resume.docx
```

The **prose gate** — the writing rules `check_ats.py` cannot see. Third person, unresolved
placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
across projects, bullets that clear their throat before the verb. No dependencies.

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
python3 scripts/score_projects.py ./my-career target.md
python3 scripts/score_projects.py ./my-career target.md --markdown
python3 scripts/score_projects.py ./my-career target.md --as-of 2026
python3 scripts/score_projects.py ./my-career target.md --assume-technologies "python,aws"
```

Ranks projects against a posting, reading its requirements from the target file's own frontmatter — so
the document you review is the one that produced the ranking. Reports what each project *failed* to
match. Needs `pyyaml`.

## Fitting

### `fit_pages.py`

```bash
python3 scripts/fit_pages.py resume.docx --target-pages 2
python3 scripts/fit_pages.py resume.docx --dry-run
python3 scripts/fit_pages.py resume.docx --in-place
python3 scripts/fit_pages.py resume.docx -o fitted.docx
python3 scripts/fit_pages.py resume.docx --renderer /path/to/soffice
```

Renders, measures which block spilled, then applies density levers in a fixed order — spacing, bullet
spacing, margins, font size — stopping at the 10pt and 0.5" floors instead of crossing them. If the
target is unreachable without a breach it exits non-zero, because the remedy then is to cut evidence,
not to shrink type.

Needs LibreOffice and `pymupdf`. This and the PDF step of `render_resume.py` are the only parts with
external dependencies.

---

Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
