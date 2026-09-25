# Mode: ship

Render a `resume.json`, put it through the gates, freeze the application. Reached by `/jsk:ship`, or read
inline at the end of `mode-tailor.md` or `mode-resume.md`.

## What it needs

A `resume.json` that validates. Everything else has a default.

```
/jsk:ship <applications/<stem>/resume.json> [--template NAME] [--ats-max] [--pages N]
```

`$ARGUMENTS` names the file. Empty → look for `applications/*/resume.json` and any `resume.json` in
the workspace, and ask which if there is more than one.

**Nothing here decides what the document says.** A gate failure is repaired in `career/kb.ttl`,
through `jsk kb apply`, or in `resume.json`'s ids and settings, then re-rendered; never worked
around by loosening a check.

## 1. Choose the variant and the look

**Pick `--template` from the posting's field** and say which: software, data, security →
`circuit`; consulting, product, platform, engineering leadership → `meridian`; design, research →
`ember`; executive one-pagers → `atrium`; banking, law, government, academia → `monolith`, the
default. Every template extracts to the same text.

`--ats-max` switches which variant the one PDF holds. Reach for it when the posting names a portal
known to parse badly (Workday, Taleo, SuccessFactors, Naukri) or the target is a form rather than a
person. **When in doubt, ATS-maximal.** It is longer by design, so it carries its own budget,
`ats_pages`. Do not cut evidence to force it onto the presentation budget.

## 2. Ship

```bash
jsk ship applications/<stem>/resume.json --out applications/<stem> [--ats-max] [--template NAME] [--pages N]
```

One process: the record gate (a failure stops it; nothing renders), then `render --pdf`, then the
parse and prose gates, each step's output verbatim. Exit 0 only if every step passed. Show that
output. Read the `=== summary` it ends with; the sections above are its evidence. It refuses in a
frozen application.

**The record gate** fails an id the career lacks or has retired, a bullet whose project has no
role, and a number no current version of a metric the bullet cites holds (superseded: the metric
was revised — the bullet needs the new value, in the career); labels, "N years of X" and brackets
only warn.

**Unconfirmed prose does not fail anything.** Below the floor (`confirmed`, by default) `inferred`
content is dropped from the render; the only sign is a `withheld …` line. Every one is confirmed or
cut before the resume is handed over: confirm it in the career — `jsk kb confirm <ids> --answer
"…"`, reworded wording first through `jsk kb apply`, never on the strength of the old text — and
re-ship. A confirmed summary: set its `"status": "confirmed"` in `resume.json`.

## 3. Fit, if it overran

`jsk ship` reports the measured page count and never fails on it — `jsk fit` owns that verdict:

```bash
jsk fit applications/<stem>/<Name>_Resume.tex --target-pages N
```

**A breached floor is a rejection, not a compromise** — cut bullets from `resume.json` instead. Then
re-run `jsk ship`.

## 4. The render gate

`jsk ship` closes by saying the render gate was not run. It is yours: open the PDF and look at every
page. The checkers pass tofu-box bullets, a heading in the wrong font and an orphaned heading, so
check:

- [ ] Page count is what `resume.json` asked for
- [ ] Bullets are real glyphs, not boxes, and not a typed `•`
- [ ] One font family throughout — headings against body, not just body against itself
- [ ] No heading stranded at the foot of a page with its content overleaf
- [ ] Dates aligned and consistently formatted
- [ ] The region profile did what you intended: its paper size, the work-rights line where it
      asks for one, the declaration on an Indian resume
- [ ] The prose, end to end: whether a bullet is true is theirs to confirm — call the resume
      **unverified** until they have read it

**`jsk-verifier`** is for a failed gate whose source you cannot see, or a second reading of the
render gate. Hand it the output directory, the page budget, the `resume.json` path and the workspace; it
returns each verdict quoted and each defect traced to the id where it is fixed. To re-check one gate
after one repair, `jsk gates <dir>` or `jsk check <file> --only parse|prose`.

## 5. Freeze the application

Only once every gate has passed.

```bash
jsk freeze applications/<stem> --submitted <yyyy-mm-dd>|false --channel "<Workday portal>" [--doc FILE ...]
```

It re-runs the gates and refuses on a failure, or if `application.ttl` exists. It writes
`application.ttl`: the posting, date, channel, documents, the `resume.json` hash, the bullets
that rendered and the metric versions they cite — so `jsk kb query stale` can later name an application
that sent a number since revised — and a `submitted` event. It renames the directory to the
submitted date and prints the new path — **use that path from here on**, for `jsk event` too. Then:

- **Stop editing that directory.** `posting.md`, `posting.ttl`, `gaps.md` and `resume.json` are the
  archive — it must still say what the application was answering.
- **Later events are `jsk event <app-dir> <kind> --date …`** (`mode-pipeline.md`), add-only.
- `--submitted false` is for an application deliberately held back: no `submitted` event, and that
  is correct. **Never add a `submitted` event to clear a gap.**

Feedback as it arrives is a `note` event; patterns in which evidence gets traction belong back in
the positioning.
