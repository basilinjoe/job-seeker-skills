# Mode: ship

Render a selection, put it through the gates, freeze the application. Reached by `/jsk:ship`, or
read inline at the end of `mode-tailor.md` or `mode-resume.md`.

## What it needs

A selection that validates: an application's `<stem>`, or `resumes/<name>`. Everything else has a
default.

```
/jsk:ship <stem>|resumes/<name>|<resume.json> [--template NAME] [--ats-max] [--pages N]
```

`$ARGUMENTS` names it. Empty → `app_list()`, and ask which if more than one is unsent. A
`resume.json` is an application made from files: ship it with
`jsk resume ship <resume.json> --out <its directory>`; the rest is the same.

**Nothing here decides what the document says.** A gate failure is repaired in the career,
through `career_apply`, or in the selection's ids and settings (`resume_update`), then
re-rendered; never worked around by loosening a check.

## 1. Choose the variant and the look

**Pick `template` from the posting's field** and say which: software, data, security →
`circuit`; consulting, product, platform, engineering leadership → `meridian`; design, research →
`ember`; executive one-pagers → `atrium`; banking, law, government, academia → `monolith`, the
default. Every template extracts to the same text.

`ats_max` switches which variant the one PDF holds. Reach for it when the posting names a portal
known to parse badly (Workday, Taleo, SuccessFactors, Naukri) or the target is a form rather than a
person. **When in doubt, ATS-maximal.** It is longer by design, so it carries its own budget,
`ats_pages`. Do not cut evidence to force it onto the presentation budget.

## 2. Ship

`resume_ship(target=<stem>, template=…, ats_max=…, pages=…)`: the record gate (a failure stops
it; nothing renders), then the render into `applications/<stem>/`, the fit if it overran (§3),
the parse, prose and layout gates; `ok` only if every step passed, each step's output in `steps`.
Show it. It refuses in a frozen application.

**The record gate** fails an id the career lacks or has retired, a bullet whose project has no
role, and a number no current version of a metric the bullet cites holds (superseded: the metric
was revised — the bullet needs the new value, in the career); labels, "N years of X" and brackets
only warn.

**Unconfirmed prose does not fail anything.** Below the floor (`confirmed`, by default) `inferred`
content is dropped from the render; the only sign is a `withheld …` line. Every one is confirmed or
cut before the resume is handed over: confirm it in the career — `career_confirm(ids,
answer="…")`, new wording first through `career_apply`, never on the strength of the old text —
and re-ship. A summary or headline the selection holds: `career_confirm(target=<stem>,
block="summary"|"headline", answer="…")`. The terms gate only warns: a missing required term is a gap, not a
word to add.

## 3. Fit, if it overran

**Ship fits itself**, stopping at the floors (0.5in, 10pt), and gates the fitted
render. `fit: …, N pages` is done: 0.6in margins are a fit, not a compromise. Never re-run
`jsk resume fit`, `tectonic` or `jsk resume check <dir>` after it.

**Cut evidence only on `over by ~N lines at the floors`**: nothing was changed. Cut about N lines of
the lowest-ranked bullets from `bullets` (`resume_update`), telling the person why, and re-ship.

## 4. The render gate

Ship closes by saying the render gate was not run. The layout gate has measured tofu, the
fonts, stranded headings, the date column, the paper and the page count; open the PDF for the rest:

- [ ] It looks right as a whole
- [ ] The work-rights line where the region asks for one; the declaration on an Indian resume
- [ ] The prose, end to end: flag any verb that overstates ownership. Whether a bullet is true is
      theirs to confirm — call the resume **unverified** until they have read it

**`jsk-verifier`** is for a failed gate whose source you cannot see, or a second reading of the
render gate. Hand it the skill directory, the output directory, the page budget, the stem (or
`resume.json` path) and the workspace; it returns each verdict quoted and each defect traced to the id where it is fixed.
To re-check after one repair, `jsk resume check <dir>`, or `<file> --only parse|prose|layout` for
one gate.

## 5. Freeze the application

Only once every gate has passed.

`app_freeze(app=<stem>, submitted=<yyyy-mm-dd>|"false", channel="<Workday portal>", docs=…)`.

It re-runs the gates and refuses on a failure, or if the application is already frozen. It stores
the application: the posting, date, channel, documents, the selection's hash, the bullets that
rendered and the metric versions they cite — so `jsk kb query stale` can later name an application
that sent a number since revised — and a `submitted` event. It renames the directory to the
submitted date, moving its graphs in the same write — **use `renamed_to` from here on**. Then:

- **Stop changing that application.** The `.pdf`, the `.tex` and its graphs in the store are the
  archive — it must still say what the application was answering; the tools refuse a sent one.
- **Later events are `app_event`** (`mode-pipeline.md`), add-only.
- `submitted="false"` is for an application deliberately held back: no `submitted` event, and that
  is correct. **Never add a `submitted` event to clear a gap.**

Feedback as it arrives is a `note` event; patterns in which evidence gets traction belong back in
the positioning.
