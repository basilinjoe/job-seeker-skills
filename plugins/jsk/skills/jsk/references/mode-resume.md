# Mode: resume

Render the knowledge base into verified files. Read `references/ats-rules.md`,
`references/writing-rules.md`, `references/resume-format.md` and the structure rules at the foot of
this file first.

## Arguments

`$ARGUMENTS` may name a region profile (`au`, `in`, `ae`). A region → use it and say why it changes
the document. Empty, and their location not obvious from the knowledge base → **ask before
rendering**: paper size, page budget, a declaration and a work-rights line differ by market.
`--ats-max` renders the PDF in the ATS-maximal variant instead of the presentation one.

## Output

For a general rebuild, `resume.json` sits at the workspace root. For an
application, it belongs in that application's directory.

| File | For |
|---|---|
| `resume.json` | The bullets and settings chosen; every file is built from it and `career/kb.ttl` |
| `<Name>_Resume.pdf` | Humans — referrals, direct email, interviews |
| `<Name>_Resume.tex` | What the PDF is compiled from; the prose gate and the fitter both read it |
| `<Name>_Resume_ATS.txt` | Paste-in boxes |

With `--ats-max` the same two files hold the other variant, never four — named for the recruiter who
reads them; the gates read the variant from the PDF. Beside a `posting.ttl`, `<Name>` gains the company.

## Build order

1. **Read the career whole** — `jsk kb view`, then `jsk kb query open` as much as the projects: know
   what is unresolved before you publish it.

2. **Rank evidence** by `j:strength`, `j:recency` and fit to their stated target.

3. **Write the summary as a claim**, per `writing-rules.md`.

4. **Export `resume.json` from the career's bullets.** A new or reworded bullet goes into the
   career first — a changeset through `jsk kb apply`, which mints its id and marks it inferred;
   `resume.json` never holds a bullet's words. Then `jsk kb export --select <ids> --out resume.json`
   (without `--select`, the whole career) writes the short file: the bullets by id, and settings.
   Edit only `bullets` order, `summary`, `region`, `pages`, `ats_pages` and `format`;
   `resume-format.md` has every key. Absent a `summary`, the career's positioning renders. Leave
   `floor` at `confirmed`, or unconfirmed prose ships.

   **If they need a selection** — a chosen subset for a kind of role — that is a target, even an informal
   one, and belongs in `mode-tailor.md` with a posting written first.

5. **Validate while you iterate** — `jsk validate resume.json` — until it passes.

6. **Ship it** per steps 1–2 of `references/mode-ship.md`: `jsk ship resume.json --out .`.

   - **Read the warnings the render prints**: a withheld bullet or summary, a skills row cut at its
     limit, a bracket that should not be in anyone's resume.
   - **Choosing a look**: `jsk preview resume.json --out <dir>` renders every template from the
     same file, and `jsk render --list-templates` describes them — nobody picks a design from a
     sentence.
   - **Re-checking one file after one repair**: `jsk check <Name>_Resume.pdf --only parse`,
     `jsk check <Name>_Resume_ATS.txt --only parse --strict`, `jsk check <Name>_Resume.tex --only
     prose`. A single-gate run names the gates it did not run.

7. **Fit to the budget** — measure, do not guess. The budget comes from `resume.json` (`pages`) or
   the region profile: two pages neutral, three in India and the Gulf, up to four in Australia. Do
   not compress an Australian resume to a US page count nobody asked for.

   `jsk fit` applies density levers in a fixed order (inter-paragraph spacing, bullet spacing,
   margins, font size) and **stops at the floors**: 10pt body, 0.5" margins. Never cross them by
   hand either. **Trimming words rarely helps** — a bullet that wraps to six lines usually still does.
   If it exits non-zero, remove a bullet from `resume.json`, which leaves it in the knowledge base
   for the next posting. Fitting changes layout: re-run `jsk ship`.

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

No `jsk`, or no TeX engine: say so and stop. Never hand-author a `.tex` in its place.

## Deliver

Present the files, say plainly which goes where, show the checker output. Then name what is still
weak — a missing certification, a thin metric, an unconfirmed claim.

Tell them the `resume.json` is theirs and worth keeping: it makes the next resume cheap, and names
each claim by its id in the career.
