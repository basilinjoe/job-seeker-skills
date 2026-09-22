# Mode: ship

Render a record, put it through the four gates, freeze the application, log it. Reached by
`/jsk:ship`, or read inline at the end of `mode-tailor.md` or `mode-resume.md`.

## What it needs

A `resume.json` that validates, and the view to render. Everything else has a default.

```
/jsk:ship <applications/<stem>/resume.json> [--template NAME] [--ats-max] [--pages N]
```

`$ARGUMENTS` names the record. Empty → look for `applications/*/resume.json` and any `resume.json`
beside the knowledge base, and ask which if there is more than one.

**Nothing here decides what the document says.** A gate failure is repaired in the record — and in
`user-knowledgebase.md` if it came from there — then re-rendered; never worked around by loosening a
check.

## 1. Choose the variant and the look

**The template defaults to the ink-only default** (`monolith`); `--template NAME` is the only way to
get another. Let the employer choose — a design studio's careers page argues for `ember`, a bank's
for the default. `templates.md` has the catalogue; every template extracts to the same text.

`--ats-max` switches which variant the one PDF holds. Reach for it when the posting names a portal
known to parse badly (Workday, Taleo, SuccessFactors, Naukri) or the target is a form rather than a
person; the presentation variant suits a referral or direct email. **When in doubt, ATS-maximal.**
It is longer by design — the employer on every role line, keyword aliases in skills — so it carries
its own budget, `budget.ats_maximal_pages`. Do not cut evidence to force it onto the presentation
budget.

## 2. Ship

```bash
jsk ship applications/<stem>/resume.json --out applications/<stem> --view <id> [--ats-max] [--template NAME] [--pages N]
```

One process: the record gate first (a failure stops it and nothing renders), then `render --pdf`,
then the three mechanical gates on the output directory, each step's output printed verbatim. Exit 0
only if every step passed. Show that output.

**Expect the record gate to fail on freshly authored prose.** `jsk-resume-author` marks everything
it wrote `inferred`, and a view with `provenance_floor: confirmed` will not render it. Go back and
get confirm-correct-or-cut on each clause.

The record gate also fails on what absence hides: a project rated `strength: 4` or better with no
achievements (below that it warns), an unrecognised top-level key, a record with no views or no
experience.

## 3. Fit, if it overran

`jsk ship` reports the measured page count and never fails on it — `jsk fit` owns that verdict:

```bash
jsk fit applications/<stem>/<Name>_Resume.tex --target-pages N
```

It fits without breaching the typographic floors and exits non-zero if the target is unreachable.
**A breached floor is a rejection, not a compromise** — cut evidence from the view instead. Then
re-run `jsk ship`.

## 4. The render gate

`jsk ship` closes by saying the render gate was not run. It is yours: open the PDF and look at every
page. The checkers pass tofu-box bullets, a heading in the wrong font and an orphaned heading, so
check:

- [ ] Page count is what the view asked for
- [ ] Bullets are real glyphs, not boxes, and not a typed `•`
- [ ] One font family throughout — headings against body, not just body against itself
- [ ] No heading stranded at the foot of a page with its content overleaf
- [ ] Dates aligned and consistently formatted
- [ ] The region profile did what you intended: no photograph or date of birth on an Australian
      resume, no missing nationality on a Gulf one
- [ ] The prose, end to end: whether a bullet is true, or a verb overstates what they owned, is
      theirs to confirm — report the half you checked and call the resume **unverified** until they
      have read it

**`jsk-verifier`** is for a gate that failed where you cannot see which section the defect came
from, or a second reading of the render gate — not for re-running what `jsk ship` already showed.
Hand it the output directory, the page budget, the record path and the knowledge base path; it
returns each verdict quoted and each defect traced to the section where it is fixed. To re-check one
gate after one repair, `jsk gates <dir>` or `jsk check <file> --only parse|prose`.

## 5. Freeze the application

Only once every gate has passed.

```bash
jsk freeze applications/<stem> --submitted <yyyy-mm-dd>|false --channel "<Workday portal>" [--view ID] [--doc FILE ...]
```

It refuses if `application.md` already exists or the mechanical gates fail. It reads company and
title from `posting.md`, the view from `--view` or the record's only view, and the documents from
`--doc` or every `.pdf`/`.txt` in the directory; writes `application.md` (frontmatter and a
`# Timeline` table with a `submitted` row); and renames the directory to the submitted date if it
differs. Then the rules it cannot enforce:

- **Stop editing that directory.** `posting.md`, `gaps.md` and `resume.json` are the archive — it
  must still say what the application was answering.
- **Later events are one appended row each**, and a correction is a new row, never an edit:

  ```markdown
  | 2026-09-11 | screen-scheduled | email | Phone screen 2026-09-15, 30 min | 2026-09-15 |
  ```

- **No `outcome:` key** — the outcome is read off the timeline.
- `--submitted false` is for an application worked through and deliberately held back: no
  `submitted` row, and that is correct. **Never write a `submitted` row to clear a gap** — every
  stage derived from the timeline afterwards is wrong.

## 6. Log it

Append a dated row to `## Log` in `user-knowledgebase.md` naming the company, the role and the view.
Record feedback in the application's timeline as it arrives — patterns in which evidence gets
traction belong back in the positioning.
