# Mode: ship

Render a record, put it through the four gates, freeze the application, log it.

Factored out of `mode-tailor.md` because `mode-resume.md` needs the same actions and was repeating
them. Reached by `/jsk:ship`, or read inline at the end of either mode.

## What it needs

A `resume.json` that validates, and the view to render. Everything else has a default.

```
/jsk:ship <applications/<stem>/resume.json> [--template NAME] [--ats-max] [--pages N]
```

**Nothing here decides what the document says.** If a gate fails, the defect is repaired in the
record — and in `user-knowledgebase.md` if that is where it came from — and re-rendered. Never
patched into the `.tex`, never worked around by loosening a check. *Editing the render puts the
record and the document out of step, which is the failure this whole pipeline exists to prevent.*

## 1. The record gate, before anything renders

```bash
jsk validate applications/<stem>/resume.json
```

It checks the record: the shape the renderer reads, ids that resolve, coherent periods, every view
reference pointing at something, every numeral tracing to a metric, nothing unconfirmed sitting under
a `provenance_floor: confirmed`.

It also checks the things absence hides. **Coverage**: a project the record rates `strength: 4` or
better with no achievements fails, because a project called resume-worthy that has nothing to quote
is a gap someone pays for later, mid-tailoring. Below that it warns. **Shape**: an unrecognised
top-level key fails, and a record with no views or no experience fails — every other check here
iterates a list, and an empty list satisfies all of them.

That last one matters more than it used to. The record was compiled once; now it is written by hand,
so `engagements:` misspelt renders a resume with no jobs on it and the mistake is invisible in the
PDF precisely because the section is simply not there.

A defect in the record becomes a defect in every format rendered from it. This runs first for that
reason, and a failure stops here.

**Expect it to fail on freshly authored prose**, and do not route around it. `jsk-resume-author`
marks everything it wrote `inferred`, and a view with `provenance_floor: confirmed` will not render
it. That is the guardrail working: go back and get confirm-correct-or-cut on each clause.

## 2. Render

```bash
jsk render applications/<stem>/resume.json --out applications/<stem> --view <id> --pdf
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

`jsk render --pdf` exits **non-zero** when no PDF was produced, and the page count it prints is
counted off the PDF rather than repeated back from the view's budget. It used to print the budget
under the word "pages", so a two-page budget that rendered three pages reported two. *A page count
nobody measured is a page count nobody knows.*

## 3. Fit, if it overran

```bash
jsk fit applications/<stem>/<Name>_Resume.tex --target-pages N
```

It fits to a budget without breaching the typographic floors, and exits non-zero if the target is
unreachable without one. **A breached floor is a rejection, not a compromise** — if it cannot fit,
cut evidence deliberately rather than shrinking the document until it stops being readable.

## 4. The four gates

Three of them are mechanical. One command runs all three:

```bash
jsk gates applications/<stem> --pages N
```

The first argument is the directory the render wrote into. It runs the record, parse and prose gates
in a single process, prints each one's output verbatim, and exits with the worst verdict of the
three. It finds the record as `resume.json` in that directory, which is where the skill writes it;
`--record <path>` names one somewhere else.

**A missing input is `SKIPPED` and a failure** — a gate that did not run is not a gate that passed,
and this is the same wording `jsk check` has always used for the same reason. A path you gave that is
not there is exit 2 instead, because forgetting `--record` and mistyping it are different mistakes
and reporting them identically hides one.

**`--pages N` reports; it does not fit, and it never changes the exit code.** It measures the PDF and
prints the render's own over-budget line. Over budget is named rather than failed here as everywhere
else in this pipeline: `jsk fit` owns that verdict, because it is the command that can act on it.
Step 3 is still where an overrun is fixed.

**`--view ID` is optional and does no work.** The record names the view it was written for, so
nothing in the run depends on the flag — but this output is archived beside the application as
evidence, and passing it stamps which view was gated. Worth passing for that reason and no other.

| Gate | Question | Run by |
|---|---|---|
| **Record** | Is the record coherent, and does every number trace to a metric? | `jsk gates`, via `validate_urs.py resume.json` |
| **Parse** | Will an ATS read this without mangling it? | `jsk gates`, via `check_ats.py` on the PDF and `--strict` on the `.txt` |
| **Prose** | Does it obey the writing rules? | `jsk gates`, via `check_prose.py` on the `.tex` and the `.txt` |
| **Render** | Does it *look* right, and is it *true*? | **you**, by opening the PDF |

It imports the same checkers and gives them the same arguments, so the verdicts are the ones you
would get by running the five by hand — that equivalence is what the command is tested on, and each
script named above still runs on its own if you want to re-check one after a repair.

The record gate runs here as well as at step 1, and both are wanted: step 1 stops a defective record
before anything renders, this one asks the record as it stands after whatever the render and the fit
made you change.

**Passing one says nothing about the others.** A checker verifies that a document parses, not that it
is correct. `rationale.md` holds the three real resumes that passed the parse gate and should not
have.

**Show the output.** The person should see the evidence rather than take your word for it. Fix and
re-run; never explain away a failure.

**`jsk gates` never attempts the render gate**, and its closing line says so. A command can tell you
the text extracts, not that the bullets are real glyphs rather than tofu boxes, that one font family
runs throughout, or that a verb overstates what the person actually did — and a command that exited 0
having quietly skipped that would be the most dangerous thing in this pipeline.

So it stays yours: open the PDF and read every page. If no PDF renderer is available, say so and mark
the resume **unverified** rather than treating a passing parse gate as sufficient. *An unverified
resume the person knows about is fine; one they think was checked is not.*

### `jsk-verifier`, when a gate fails and the failure needs reading against the record

A clean ship does not spawn it, and that is not a demotion. Running three checkers and relaying their
output verbatim is work a command does better: no subagent context, no relay to be summarised in, no
chance of five commands being run as four.

Interpreting a failure is the other kind of work, and it is still the agent's. A `FAIL` line names a
symptom in a rendered file; the repair site is a section — a project's bullets, a row in `##
Metrics`, the view inside the record. Hand it the output directory, the page budget and the paths to
the record and the knowledge base, and it comes back with each verdict quoted and each defect traced
to where it is fixed. It still has no Write tool, which is exactly why it can be trusted with that
job.

Reach for it when a gate fails and you cannot see where the defect came from, or when the render gate
needs a second reading. Do not reach for it to re-run what `jsk gates` has already run and shown you.

## 5. Freeze the application

Only once every gate has passed. **A failing document is never frozen** — an archive of something
that was not sendable is worse than no archive, because later it reads as though it was.

Everything for this submission is already in one directory. Freezing it is three edits and a rename:

1. **Rename the directory to the day it was sent** if that is not what it already says:
   `applications/<yyyy-mm-dd>-<company>-<role>/`. The date is in the name because applying twice is
   ordinary — a posting is re-advertised, a first attempt is superseded, a rejection is followed by a
   second round a year later. Without the date the second one has nowhere to go but on top of the
   first.
2. **Write `application.md`** beside the rest:

```markdown
---
company: Acme Health
title: Platform Engineer
view: view_acme_platform
submitted: 2026-09-08          # or `false` for one deliberately held back
channel: Workday portal
documents:
  - Priya_Raman_Acme_Resume.pdf
  - Priya_Raman_Acme_Resume_ATS.txt
---

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-09-08 | submitted | Workday | ATS variant uploaded, presentation copy to the referrer | |
```

3. **Stop editing everything in that directory.** `posting.md`, `gaps.md` and `resume.json` are the
   archive now. A year later the only question anybody asks of a filed application is what it was
   answering, and an application whose inputs are still moving cannot answer it.

Frontmatter carries only what was true at submission and never changes. **There is no `outcome:`
key**: the outcome is derived by reading the timeline, because a status word and the prose beneath it
stop agreeing the moment one is edited.

`submitted: false` is for an application worked through and deliberately held back — it means there
is no `submitted` row and that is correct. **Never write a `submitted` row to clear a gap in the
record**: it trades an accurate blank for a false green, and every stage derived from that timeline
afterwards is wrong.

Later events are one appended row each:

```markdown
| 2026-09-11 | screen-scheduled | email | Phone screen 2026-09-15, 30 min | 2026-09-15 |
```

A correction is a new row. Never edit one, for the same reason `## Log` records mistakes rather than
hiding them.

## 6. Log it

Append a dated row to `## Log` in `user-knowledgebase.md` naming the company, the role and the view.
Record feedback in the application's timeline as it arrives — after a handful of applications,
patterns emerge about which evidence gets traction, and that belongs back in the positioning.
