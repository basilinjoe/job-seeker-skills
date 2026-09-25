# Mode: ship

Render a record, put it through the gates, freeze the application. Reached by `/jsk:ship`, or read
inline at the end of `mode-tailor.md` or `mode-resume.md`.

## What it needs

A `resume.json` that validates, and the view to render. Everything else has a default.

```
/jsk:ship <applications/<stem>/resume.json> [--view ID] [--template NAME] [--ats-max] [--pages N]
```

`$ARGUMENTS` names the record. Empty → look for `applications/*/resume.json` and any `resume.json`
in the workspace, and ask which if there is more than one.

**Nothing here decides what the document says.** A gate failure is repaired in the record — and in
`career/kb.ttl`, through `jsk kb apply`, if it came from there — then re-rendered; never worked
around by loosening a check.

## 1. Choose the variant and the look

**The template defaults to the ink-only default** (`monolith`); `--template NAME` is the only way to
get another. Let the employer choose — a design studio's careers page argues for `ember`, a bank's
for the default. `templates.md` has the catalogue; every template extracts to the same text.

`--ats-max` switches which variant the one PDF holds. Reach for it when the posting names a portal
known to parse badly (Workday, Taleo, SuccessFactors, Naukri) or the target is a form rather than a
person. **When in doubt, ATS-maximal.** It is longer by design, so it carries its own budget,
`budget.ats_maximal_pages`. Do not cut evidence to force it onto the presentation budget.

## 2. Ship

```bash
jsk ship applications/<stem>/resume.json --out applications/<stem> --view <id> [--ats-max] [--template NAME] [--pages N]
```

One process: the record gate, then the claims gate (either failing stops it, nothing renders), then
`render --pdf`, then the parse and prose gates, each step's output printed verbatim. Exit 0 only if
every step passed. Show that output.

**Unconfirmed prose does not fail anything.** Everything `jsk-resume-author` wrote is `inferred`;
a view with `provenance_floor: confirmed` drops it from the render, and the only sign is a
`withheld …` warning line. Every one is confirmed or cut before the resume is handed over: get
confirm-correct-or-cut on each clause, `jsk kb confirm <ids> --answer "…"`, flip them in the record,
re-ship. Confirm confirms the career's text, so reworded wording goes into the career first
(`jsk kb apply`) — never on the strength of the old text.

**The claims gate** joins the record with `career/kb.ttl` by id: an entry the career lacks is at
most `inferred`; nothing may be more confirmed than the career holds it; a bullet under another
project fails (`project-moved`); every number must be in the current version of a metric the
bullet cites (`number-superseded` means a revised metric — use the new value). Wording that drifted
from the career's only warns (`text-changed`), as do labels, aliases and "N years of X".

**`NOT RUN`** in a graph workspace means the record sits outside it — the gate looks for
`career/kb.ttl` above `resume.json` — and `jsk ship` still exits 0. Move `resume.json` into
`applications/<stem>/` and re-run; never freeze or hand over a `NOT RUN`.

## 3. Fit, if it overran

`jsk ship` reports the measured page count and never fails on it — `jsk fit` owns that verdict:

```bash
jsk fit applications/<stem>/<Name>_Resume.tex --target-pages N
```

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
- [ ] The prose, end to end: whether a bullet is true is theirs to confirm — call the resume
      **unverified** until they have read it

**`jsk-verifier`** is for a failed gate whose source you cannot see, or a second reading of the
render gate. Hand it the output directory, the page budget, the record path and the workspace; it
returns each verdict quoted and each defect traced to the id where it is fixed. To re-check one gate
after one repair, `jsk gates <dir>` or `jsk check <file> --only parse|prose`.

## 5. Freeze the application

Only once every gate has passed — a `NOT RUN` has not.

```bash
jsk freeze applications/<stem> --submitted <yyyy-mm-dd>|false --channel "<Workday portal>" [--view ID] [--doc FILE ...]
```

It re-runs the gates and refuses on a failure, or if `application.ttl` exists. It writes
`application.ttl`: the posting, view, date, channel, documents, the `resume.json` hash, the bullets
carried and the metric versions they cite — so `jsk kb query stale` can later name an application
that sent a number since revised — and a `submitted` event. It renames the directory to the
submitted date. Then:

- **Stop editing that directory.** `posting.md`, `posting.ttl`, `gaps.md` and `resume.json` are the
  archive — it must still say what the application was answering.
- **Later events are `jsk event <app-dir> <kind> --date …`** (`mode-pipeline.md`), add-only.
- `--submitted false` is for an application deliberately held back: no `submitted` event, and that
  is correct. **Never add a `submitted` event to clear a gap.**

Feedback as it arrives is a `note` event; patterns in which evidence gets traction belong back in
the positioning.
