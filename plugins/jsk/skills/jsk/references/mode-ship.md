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
okf validate <bundle>
```

It compiles the bundle and checks the result: ids resolve, periods are coherent, every view
reference points at something, every numeral traces to a metric, nothing unconfirmed sits under a
`provenance_floor: confirmed`. A bundle that will not compile names the concept that is wrong.

It also checks the two things absence hides. **Coverage**: a project the bundle rates `strength: 4`
or better with nothing in its `# Bullets` block fails, because a project called resume-worthy that
has nothing to quote is a gap someone pays for later, mid-tailoring. Below that it warns.
**Conservation**: a concept type sitting on disk that compiles to an empty record key fails - every
other check here iterates that key, and an empty list satisfies all of them.

A defect in the record becomes a defect in every format rendered from it. This runs first for that
reason, and a failure stops here.

**Expect it to fail on freshly authored prose**, and do not route around it. `jsk-resume-author`
marks everything it wrote `inferred`, and a view with `provenance_floor: confirmed` will not render
it. That is the guardrail working: go back and get confirm-correct-or-cut on each clause.

## 2. Render

```bash
okf render <bundle> --out . --view <id> --pdf
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

`render_resume.py --pdf` exits **non-zero** when no PDF was produced, and the page count it prints is
counted off the PDF rather than repeated back from the view's budget. It used to print the budget
under the word "pages", so a two-page budget that rendered three pages reported two. *A page count
nobody measured is a page count nobody knows.*

## 3. Fit, if it overran

```bash
okf fit <resume>.tex --target-pages N
```

It fits to a budget without breaching the typographic floors, and exits non-zero if the target is
unreachable without one. **A breached floor is a rejection, not a compromise** — if it cannot fit,
cut evidence deliberately rather than shrinking the document until it stops being readable.

## 4. The four gates

Three of them are mechanical. One command runs all three:

```bash
okf gates . --view <id> --bundle <bundle> --pages N
```

The first argument is the directory the render wrote into. It runs the record, parse and prose gates
in a single process, prints each one's output verbatim, and exits with the worst verdict of the
three. **A missing input is `SKIPPED` and a failure** — a gate that did not run is not a gate that
passed, and this is the same wording `okf check` has always used for the same reason. A path you
gave that is not there is exit 2 instead, because forgetting `--bundle` and mistyping it are
different mistakes and reporting them identically hides one.

**`--pages N` reports; it does not fit, and it never changes the exit code.** It measures the PDF
and prints `render_resume.py`'s own over-budget line. Over budget is named rather than failed here
as everywhere else in this pipeline: `fit_pages.py` owns that verdict, because it is the script that
can act on it. Step 3 is still where an overrun is fixed.

**`--view ID` is required and does no work.** The record gate takes a bundle and the document gates
take files named after the person, so nothing in the run depends on it — but this output is archived
beside the application as evidence, and nothing else in the output directory records which view was
gated. It is there to stamp the evidence, and it should not be removed as dead weight later.

| Gate | Question | Run by |
|---|---|---|
| **Record** | Is the source coherent, and does every number trace to a metric? | `okf gates`, via `validate_urs.py <bundle>` |
| **Parse** | Will an ATS read this without mangling it? | `okf gates`, via `check_ats.py` on the PDF and `--strict` on the `.txt` |
| **Prose** | Does it obey the writing rules? | `okf gates`, via `check_prose.py` on the `.tex` and the `.txt` |
| **Render** | Does it *look* right, and is it *true*? | **you**, by opening the PDF |

This was five separate invocations; as one command it runs in about **0.6x** the wall clock — what
is saved is exactly four interpreter starts. What remains is the compile and the `pymupdf` import,
and neither goes away without a cache, which this pipeline does not have and does not want. It
imports the same checkers and gives them the same arguments, so the verdicts are the ones you would
get by running the five by hand — that equivalence is what the command is tested on, and each script
named above still runs on its own if you want to re-check one after a repair.

The record gate runs here as well as at step 1, and both are wanted: step 1 stops a defective record
before anything renders, this one asks the bundle as it stands after whatever the render and the fit
made you change.

**Passing one says nothing about the others.** A checker verifies that a document parses, not that it
is correct. `rationale.md` holds the three real resumes that passed the parse gate and should not
have.

**Show the output.** The person should see the evidence rather than take your word for it. Fix and
re-run; never explain away a failure.

**`okf gates` never attempts the render gate**, and its closing line says so. A script can tell you
the text extracts, not that the bullets are real glyphs rather than tofu boxes, that one font family
runs throughout, or that a verb overstates what the person actually did — and a command that exited
0 having quietly skipped that would be the most dangerous thing in this pipeline.

So it stays yours: open the PDF and read every page. If no PDF renderer is available, say so and mark
the resume **unverified** rather than treating a passing `check_ats.py` as sufficient. *An unverified
resume the person knows about is fine; one they think was checked is not.*

### `jsk-verifier`, when a gate fails and the failure needs reading against the record

A clean ship no longer spawns it, and that is not a demotion. Running three checkers and relaying
their output verbatim is work a command does better: no subagent context, no relay to be summarised
in, no chance of five commands being run as four.

Interpreting a failure is the other kind of work, and it is still the agent's. A `FAIL` line names a
symptom in a rendered file; the repair site is a concept — the project file, a row in
`achievements/metrics.md`, the view. Hand it the output directory, the view id, the page budget and
the bundle path, and it comes back with each verdict quoted and each defect traced to where it is
fixed. It still has no Write tool, which is exactly why it can be trusted with that job.

Reach for it when a gate fails and you cannot see where the defect came from, or when the render
gate needs a second reading. Do not reach for it to re-run what `okf gates` has already run and
shown you.

## 5. Freeze the archive

Only once every gate has passed. **A failing document is never frozen** — an archive of something
that was not sendable is worse than no archive, because later it reads as though it was.

**One command does the whole of it**, and it is the write with the least reason to be performed by a
model:

```bash
okf application file <slug> --bundle <bundle> \
  --submitted <yyyy-mm-dd> --channel "Workday portal" \
  --document <out-dir>/<Name>_<Company>_Resume.pdf \
  --document <out-dir>/<Name>_<Company>_Resume_ATS.txt
```

It copies the posting, the assessment and the view into that year's directory, freezes each copy,
writes the `Application` concept and its `# Timeline`, creates the year index, copies the documents
actually sent, appends to `log.md` - and **rewrites every relative path that leaves the directory to
gain exactly one `../`**, because the frozen copies sit one directory deeper than the working ones.

It refuses everything about that it would otherwise have to guess: a year it cannot establish, a
missing working file, a company with no concept, a stem already filed under that date.

`--submitted false` is for an application worked through and deliberately held back: it writes
`submitted: false` and no `submitted` row. **Never write a `submitted` row to clear a validator
error** - it trades an accurate red for a false green, and every stage derived from that timeline
afterwards is wrong.

Later events are one command each, append-only:

```bash
okf application event <stem> --bundle <bundle> \
  --date 2026-09-11 --event screen-scheduled --channel email --note "…" --due 2026-09-15
```

A correction is a new row. There is no `set` verb here, for the same reason `log.md` records mistakes
rather than hiding them.

One submission is a set of files sharing a stem — `<yyyy-mm-dd>-<company>-<role>`, because applying
twice to one posting is ordinary and the second round needs somewhere to go that is not on top of the
first. `bundle-spec.md`'s *Applications on disk* has the full shape; what matters here is why the
command does what it does.

**The freeze is what makes the archive answerable.** The files in `targets/` stay editable — the same
employer posts again, a listing is revised, an assessment is re-run — and every one of those edits
would silently rewrite what a past application appears to have answered. A year later the only
question anybody asks of a filed application is what it was answering, and an application whose
inputs are still moving cannot answer it.

**The record is not copied, and does not need to be.** It compiles from concepts that are in git, so
the resume this application sent can be rebuilt from the commit it was sent at — a stronger guarantee
than a checksum over a copied file, and it costs nothing to keep.

Frontmatter carries only what was true at submission and never changes. There is no `outcome:` key:
the outcome is derived from the timeline, because a status word and the prose beneath it stop agreeing
the moment one is edited.

## 6. Log it

`okf application file` appends its own row. Anything else worth recording is `okf log --message "…"`.
Append a dated entry to `log.md`. Record the submission in `tailoring/applications/<yyyy>/`,
including any feedback that arrives later — after a handful of applications, patterns emerge about
which evidence gets traction, and that belongs back in the rules.
