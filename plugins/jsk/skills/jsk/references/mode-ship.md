# Mode: ship

Render a record, put it through the four gates, freeze what it was answering, log it.

Factored out of `mode-tailor.md` because `mode-resume.md` needs the same three actions and was
repeating them. Reached by `/jsk:ship`, or read inline at the end of either mode.

## What it needs

A bundle that compiles, and the view to render. Everything else has a default.

```
/jsk:ship <view.md> [--template NAME] [--ats-max] [--pages N]
```

**Nothing here decides what the document says.** If a gate fails, the defect is repaired in the
record and re-rendered — never patched into the `.tex`, never worked around by loosening a check.
*Editing the render puts the record and the document out of step, which is the failure this whole
pipeline exists to prevent.*

## 1. The record gate, before anything renders

```bash
python3 <skill-dir>/scripts/validate_urs.py <bundle>
```

It compiles the bundle and checks the result: ids resolve, periods are coherent, every view
reference points at something, every numeral traces to a metric, nothing unconfirmed sits under a
`provenance_floor: confirmed`. A bundle that will not compile names the concept that is wrong.

A defect in the record becomes a defect in every format rendered from it. This runs first for that
reason, and a failure stops here.

**Expect it to fail on freshly authored prose**, and do not route around it. `jsk-resume-author`
marks everything it wrote `inferred`, and a view with `provenance_floor: confirmed` will not render
it. That is the guardrail working: go back and get confirm-correct-or-cut on each clause.

## 2. Render

```bash
python3 <skill-dir>/scripts/render_resume.py <bundle> --out . --view <id> --pdf
```

**The template defaults to the ink-only default**, and `--template NAME` is the only way to get
another. Let the employer choose it — a design studio's careers page argues for `ember`, a bank's for
the default. `templates.md` has the catalogue. The template decides how it looks; every one extracts
to the same text.

`--ats-max` is a separate axis and switches which variant the PDF holds — there is still one PDF.
Reach for it when the posting names a portal known to parse badly (Workday, Taleo, SuccessFactors,
Naukri) or when the target is a form rather than a person. The presentation variant is right for a
referral or a direct email. **When in doubt, ATS-maximal**: a plain resume that parses beats a
beautiful one that arrives fragmented.

The ATS-maximal render is deliberately longer — it repeats the employer on every role line and
expands the skills block with keyword aliases — so it carries its own budget,
`budget.ats_maximal_pages`. Do not cut evidence to force it onto the presentation variant's budget; a
parser does not care about length.

`render_resume.py --pdf` exits **non-zero** when no PDF was produced. *A page count nobody measured
is a page count nobody knows.*

## 3. Fit, if it overran

```bash
python3 <skill-dir>/scripts/fit_pages.py <resume>.tex --target-pages N
```

It fits to a budget without breaching the typographic floors, and exits non-zero if the target is
unreachable without one. **A breached floor is a rejection, not a compromise** — if it cannot fit,
cut evidence deliberately rather than shrinking the document until it stops being readable.

## 4. The four gates

Hand the rendered files, the view id and the page budget to **`jsk-verifier`**. It runs all four and
reports each verdict verbatim, and it deliberately has no Write tool.

| Gate | Question |
|---|---|
| **Record** | Is the source coherent, and does every number trace to a metric? |
| **Parse** | Will an ATS read this without mangling it? |
| **Prose** | Does it obey the writing rules? |
| **Render** | Does it *look* right, and is it *true*? |

**Passing one says nothing about the others.** A checker verifies that a document parses, not that it
is correct. `rationale.md` holds the three real resumes that passed the parse gate and should not
have.

**Show the output.** The person should see the evidence rather than take your word for it. Fix and
re-run; never explain away a failure.

The render gate is the one nobody else can run: open the PDF and read every page. If no PDF renderer
is available, say so and mark the resume **unverified** rather than treating a passing
`check_ats.py` as sufficient. *An unverified resume the person knows about is fine; one they think
was checked is not.*

## 5. Freeze the archive

Only once every gate has passed. **A failing document is never frozen** — an archive of something
that was not sendable is worse than no archive, because later it reads as though it was.

One submission is a set of files sharing a stem in `tailoring/applications/`:

| File | Is |
|---|---|
| `<slug>.md` | the log: what was sent, what was selected, what came back |
| `<slug>.posting.md` | the posting, frozen - the advertisement verbatim |
| `<slug>.gaps.md` | the assessment it was answering, frozen |
| `<slug>.view.md` | the view it rendered from |
| `<Name>_<Company>_Resume*.{pdf,tex,txt}` | the files actually sent |

Copy all three out of `tailoring/targets/`, and set `frozen: true` with the date on each. The files
in `targets/` stay editable — the same employer posts again, a listing is revised, an assessment is
re-run — and every one of those edits would silently rewrite what a past application appears to have
answered.

**The record is not copied, and does not need to be.** It compiles from concepts that are in git, so
the resume this application sent can be rebuilt from the commit it was sent at. That is a stronger
guarantee than a checksum over a copied file, and it costs nothing to keep.

Write the `Application` concept with its `# Timeline`, per `bundle-spec.md`. Frontmatter carries only
what was true at submission and never changes; the outcome is derived from the timeline, because a
status word and the prose beneath it stop agreeing the moment one is edited.

## 6. Log it

Append a dated entry to `log.md`. Record the submission in `tailoring/applications/`, including any
feedback that arrives later — after a handful of applications, patterns emerge about which evidence
gets traction, and that belongs back in the rules.
