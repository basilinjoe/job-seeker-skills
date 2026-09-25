# Mode: resume

Render the knowledge base into verified files. Read `references/ats-rules.md`,
`references/writing-rules.md`, `references/urs-spec.md` and the structure rules at the foot of this
file first.

## Arguments

`$ARGUMENTS` may name a region profile (`au`, `in`, `ae`) or a view id. A region → use it and say why
it changes the document. Empty, and their location not obvious from the knowledge base → **ask before
rendering**: a photograph is conventional in one market and a liability in another. `--ats-max`
renders the PDF in the ATS-maximal variant instead of the presentation one.

## Output

For a general rebuild, save the record as `resume.json` in the workspace. For an
application, it belongs in that application's directory.

| File | For |
|---|---|
| `resume.json` | The record every other file is rendered from |
| `<Name>_Resume.pdf` | Humans — referrals, direct email, interviews |
| `<Name>_Resume.tex` | What the PDF is compiled from; the prose gate and the fitter both read it |
| `<Name>_Resume_ATS.txt` | Paste-in boxes |

With `--ats-max` the first two become `<Name>_Resume_ATS.pdf` and `<Name>_Resume_ATS.tex` — the same
two files in the other variant, never four.

## Build order

1. **Read the career whole** — `jsk kb view`, then `jsk kb query open` as much as the projects: know
   what is unresolved before you publish it.

2. **Rank evidence** by `j:strength`, `j:recency` and fit to their stated target.

3. **Write the summary as a claim**, per `writing-rules.md`.

4. **Draft `resume.json` from the career's bullets.** A new or reworded bullet goes into the career
   first — a changeset through `jsk kb apply`, which mints its id and marks it inferred; never a
   bullet only in the record. Then `jsk kb export --urs --select <ids> --out
   applications/<stem>/resume.json` writes the record: the career's own ids, provenance, periods
   and each metric's current version, one `engagement` per employer with its `positions`. It passes
   `jsk validate` and the claims gate as written — retune words and the view, never retype a status
   or a number. `view-format.md` has the view keys.
   - Declare the region profile on each view: `urs:profile:au/1`, `in/1`, `ae/1`, or omit it for the
     region-neutral default. It decides whether a photograph, date of birth, referees, a declaration
     block or a salary expectation are emitted.
   - **One view per variant.** A view selects: it references ids, orders them, redacts; it never
     contains content text.

   A general rebuild wants the simplest view — the whole record, presentation profile, no
   provenance floor:

   ```json
   "views": [{
     "id": "view_default",
     "format_profile": "presentation",
     "narrative": "nar_default",
     "budget": {"pages": 2}
   }]
   ```

   **If they need a selection** — a floor, a redaction, a region profile, a chosen subset — that is a
   target, even an informal one, and belongs in `mode-tailor.md` with a posting written first.

5. **Validate while you iterate** on the record — `jsk validate resume.json` — until it passes.

6. **Ship it** per steps 1–2 of `references/mode-ship.md`: `jsk ship resume.json --out . --view <id>`.

   - **Read the warnings the render prints**: a withheld bullet, a field the region profile requires
     and the record lacks, a bracket that should not be in anyone's resume.
   - **Choosing a look**: `jsk preview resume.json --out <dir>` renders every template from the
     record, and `jsk render --list-templates` describes them — nobody picks a design from a
     sentence.
   - **Re-checking one file after one repair**: `jsk check <Name>_Resume.pdf --only parse`,
     `jsk check <Name>_Resume_ATS.txt --only parse --strict`, `jsk check <Name>_Resume.tex --only
     prose`. A single-gate run names the gates it did not run.

7. **Fit to the budget** — measure, do not guess. The budget comes from the view (`budget.pages`) or
   the region profile: two pages neutral, three in India and the Gulf, up to four in Australia. Do
   not compress an Australian resume to a US page count nobody asked for.

   `jsk fit` applies density levers in a fixed order (inter-paragraph spacing, bullet spacing,
   margins, font size) and **stops at the floors**: 10pt body, 0.5" margins. Never cross them by
   hand either. **Trimming words rarely helps** — a bullet that wraps to six lines usually still does.
   If it exits non-zero, remove evidence from the *view*, which leaves it in the record and the
   knowledge base for the next posting. Fitting changes layout: re-run `jsk ship`.

   No renderer? A geometric estimate of page fill is a reasonable fallback, but label it an estimate
   (one read ~99% where the truth was ~94%).

8. **The render gate** — step 4 of `references/mode-ship.md`. A general rebuild is not frozen;
   freezing is for an application directory.

## Structure rules for rendering

```
Header               name | current title | years | location · phone · email · links
Professional Summary a claim their bullets prove, not a job title restated
Technical Skills     grouped; architecture-level first, then stacks
Professional Experience
Education            + certifications, languages, open source
```

**Recency gets the weight** — roughly 4:1 toward recent roles. Ten years' experience targeting a
senior role earns one or two lines for the first two years.

**Many roles at one employer:** one company block, a single progression line, achievements grouped by
scope era. (ATS-maximal reverses this — see `ats-rules.md`.)

**Bridge a title nobody outside that employer can place.** "Member of Technical Staff (Full-Stack
Engineer)" on the role line. The official title stays first and verbatim — see `writing-rules.md`,
which also says when to leave a title alone.

**Label domains inline on every project** — for one long tenure the main defence against "narrow
exposure".

**Platform above product.** If they built a platform and something on it, render them adjacent with
"(built on the platform above)".

**Two pages.** If content outgrows it, compress older roles rather than adding a page.

## If the tooling is missing

If the skill was installed as `SKILL.md` alone, write the record as URS anyway (`urs-spec.md`).
LaTeX can be written with the standard library and compiled by any engine; keep the preamble minimal
— `geometry` and `enumitem` are enough. Whatever you use, the output must satisfy the parse gate.

## Deliver

Present the files, say plainly which goes where, show the checker output. Then name what is still
weak — a missing certification, a thin metric, an unconfirmed claim.

Tell them the `resume.json` is theirs and worth keeping: it makes the next resume cheap, and records
where each claim came from.
