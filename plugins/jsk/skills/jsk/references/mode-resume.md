# Mode: resume

Render the knowledge base into verified files. Read `references/ats-rules.md`,
`references/writing-rules.md`, `references/urs-spec.md` and the structure rules at the foot of this
file first — or the person's own `rules/*.md` beside their knowledge base if present, which wins.

## The pipeline is JSON-first

**Never author a `.tex` by hand.** Write the URS record, then render from it:

```
user-knowledgebase.md  ->  resume.json (URS)  ->  render plan  ->  .tex -> .pdf   (the deliverable)
                                                               \-> .txt          (paste-in boxes)
```

The reason is not tidiness. Two hand-built documents have to agree about every date, every bullet and
every number, and they stop agreeing the moment one is edited — usually silently, usually in the copy
that gets sent. One record with two emitters cannot drift, because no emitter decides what the
document says. `jsk/urs/plan.py` makes every content decision exactly once; the emitters only choose
markup.

There used to be a third and fourth file: a presentation `.docx` and an ATS-maximal `.docx`. They
went because the same argument applied one level up. The fitter measured the `.docx` through
LibreOffice while the PDF was what got sent, the two disagreed, and a resume reported as two pages
shipped as three. **`--ats-max` now chooses which variant the single PDF holds** rather than adding a
second file.

For a general rebuild, save the record as `resume.json` beside the knowledge base. For an
application, it belongs in that application's directory — `references/kb-spec.md` has the layout.

A month later the question is never "what did the resume look like", it is "what did it claim, and
where did that come from". The record answers that, which is why an application's copy is **frozen**:
the knowledge base keeps moving, and a record that pointed at a moving source could not say what was
sent.

## Output

| File | For |
|---|---|
| `resume.json` | The record every other file is rendered from |
| `<Name>_Resume.pdf` | Humans — referrals, direct email, interviews |
| `<Name>_Resume.tex` | What the PDF is compiled from; the prose gate and the fitter both read it |
| `<Name>_Resume_ATS.txt` | Paste-in boxes |

With `--ats-max` the first two become `<Name>_Resume_ATS.pdf` and `<Name>_Resume_ATS.tex` — the same
two files in the other variant, never four files.

## Handover is a shared procedure

Steps 5 onward — validate, render, the four gates, fit to budget, file it — are the same actions
`mode-tailor.md` ends with, and they live in `references/mode-ship.md`. They are written out below
too, because this mode is usable on its own; when the two disagree, `mode-ship.md` is the one being
maintained.

## Build order

1. **Read `user-knowledgebase.md` — the whole file.** It is one document and it is meant to be read
   whole. `## Open questions` matters as much as `## Projects`: you need to know what is unresolved
   before you publish it.

2. **Rank evidence** by `strength`, `recency` and fit to their stated target.

3. **Write the summary as a claim**, per `writing-rules.md`.

4. **Write `resume.json`.** This is where the authoring happens, and the only place it happens.

   The record used to be compiled from a folder of concepts, so this step was a mapping and not a
   judgement. It is neither now — you are writing it — which raises the stakes on every rule below
   and is why step 5 exists.

   - **Copy the shape from `references/urs-spec.md`**, and from the shipped example. Only the keys
     the renderer knows are read; `jsk validate` fails an unrecognised top-level key, because a key
     nothing reads is a section that renders as nothing and the mistake is invisible in the PDF.
   - Every bullet is an `Achievement` with `text`, `provenance` and — whenever the prose carries a
     number — `metrics` mirroring the row in the knowledge base's `## Metrics` table. The record gate
     fails a bullet whose numbers appear in no metric, which is the check that stops a rewritten
     bullet from quietly inflating a figure.
   - `provenance.status` copies straight across from the knowledge base. Anything `inferred` stays
     `inferred`; the view's `provenance_floor` then keeps it out of the document until they confirm
     it. **Do not launder a status while transcribing** — this is the one mistake in this mode that
     nothing downstream can detect.
   - One employer with several roles is **one** `engagement` with several `positions`. Do not repeat
     the employer as separate engagements — the promotion story is the point.
   - Declare the region profile on each view: `urs:profile:au/1`, `in/1`, `ae/1`, or omit it for the
     region-neutral default. This is what decides whether a photograph, a date of birth, referees, a
     declaration block or a salary expectation are emitted, and getting it wrong is not a formatting
     error — a date of birth on an Australian application is a liability, and its absence on a Gulf
     one reads as an incomplete file.
   - **One view per variant.** A view **selects**: it references ids, orders them, redacts. It never
     contains content text, and `jsk validate` rejects it if it does.

   A general rebuild wants the simplest possible view — the whole record, presentation profile, no
   provenance floor:

   ```json
   "views": [{
     "id": "view_default",
     "format_profile": "presentation",
     "narrative": "nar_default",
     "budget": {"pages": 2}
   }]
   ```

   **If they need a selection** — a floor, a redaction, a region profile, a chosen subset — then what
   they are describing is a target, even an informal one, and it belongs in `mode-tailor.md` with a
   posting written first.

5. **Validate before rendering — the gate in front of the gates:**

```bash
jsk validate resume.json
```

   Nothing is rendered from a document that fails. A defect in the record becomes a defect in every
   file at once, and finding it in the PDF means finding it too late.

6. **Render every format from that one file:**

```bash
jsk render resume.json --out . --view <view-id> --pdf
```

   Add `--ats-max` for the ATS-maximal variant. That writes the `.tex`, compiles it to the PDF, and
   writes the plain text. **It exits non-zero if no PDF was produced** — a `.tex` nobody rendered is
   a resume nobody has looked at. Read the warnings it prints: a withheld bullet, a field the region
   profile requires and the record does not have, a bracket that should not be in anyone's resume.

   `--template NAME` chooses the look. The default, `monolith`, is ink-only and conservative; four
   others use colour and typography to build a stronger visual hierarchy. All five say the same
   words in the same order and extract to identical text, so this is a question about the reader,
   never about the parse. `--list-templates` describes them and `jsk preview` renders all five from
   the record — nobody picks a resume design from a sentence. See `templates.md`.

7. **Verify — not optional:**

   The three mechanical gates run as one command, and its output is what you show:

```bash
jsk gates . --pages N
```

   That is the record gate on `resume.json`, the parse gate on the PDF and again on the `.txt` with
   `--strict`, and the prose gate on the `.tex` and again on the `.txt` — five invocations in one
   process, each one's output printed verbatim. It finds the record as `resume.json` beside the
   render; `--record <path>` names one somewhere else. `--pages N` reports the count and never fails
   on it; step 8 is still what fixes an overrun. It never attempts the render gate and closes by
   saying so.

   The individual commands still work, and are the right thing for re-checking one file after one
   repair:

```bash
jsk check <Name>_Resume.pdf --only parse
jsk check <Name>_Resume_ATS.txt --only parse --strict
jsk check <Name>_Resume.tex --only prose
```

   A single-gate run never closes by saying both passed — it names the three gates that did not.

   **Hand it to `jsk-verifier` when a gate fails and you cannot see where the defect came from**, or
   when step 9 needs a second pair of eyes. It quotes every verdict and names the section each defect
   is repaired in, and it cannot edit a document, which is the point. A clean pass does not need it.

**These check different things.** The record gate verifies the record is *coherent and correctly
shaped*. The parse gate verifies the document *parses*: text that actually extracts, a heading a
parser can match on, a bullet glyph it recognises. The structural checks — no tables, no header
content, no second column — moved to a test on the LaTeX template, which cannot express any of them.
The prose gate verifies it *reads*: third person, placeholders, sentences that stop before their
object, phrases `writing-rules.md` says to cut, bullets repeated across projects. A third-person
bullet is not a parsing defect, so the parse gate passes it and is right to.

All must PASS. **Show the output** — the checker's own lines. An agent's summary of a checker is not
the checker, and the person is entitled to the evidence rather than a report of it. Fix and re-run
rather than explaining away a failure. Fix it *in `resume.json`* — and in `user-knowledgebase.md` if
the defect came from there — and re-render; editing the `.tex` puts the record and the document out
of step, which is the failure this pipeline exists to prevent.

8. **Fit to the page budget** — measure, do not guess:

```bash
jsk fit <Name>_Resume.tex --target-pages 2
```

It rewrites the `.tex`, recompiles it, counts, reports per-page fill, and — when the document runs
over — names the block that spilled and how much room the previous page actually had. Then it applies
density levers in a fixed order (inter-paragraph spacing, bullet spacing, margins, font size) and
**stops at the floors**: 10pt body, 0.5" margins. Never cross them by hand either; both read as
desperate and hurt parsing.

The budget itself comes from the view (`budget.pages`) or the region profile — two pages neutral,
three in India and the Gulf, up to four in Australia. Do not compress an Australian resume to a US
page count nobody asked for.

**Trimming words rarely helps.** Cutting eight words from a bullet that wraps to six lines usually
still wraps to six lines. If the command exits non-zero, the budget is unreachable typographically
and the answer is to remove evidence — drop bullets from the view — not to shrink type further.
Removing them from the *view* leaves them in the record and in the knowledge base, which is the
point: next month's posting may want exactly what this one did not.

Fitting changes layout, so re-run the parse gate on the fitted file before step 9.

9. **Look at the render — the last gate, and not optional either.** No command attempts it, and
   `jsk gates` closes by saying so. Open the PDF and read every page, or hand it to `jsk-verifier`,
   which does. Nobody signs this one off from a checker's exit code.

   **Half of this gate is not yours to close.** The checklist below splits at the last item: you can
   settle page count, glyphs, fonts and orphans by looking, and `jsk-verifier` settles them the same
   way. Whether a bullet is *true*, and whether a verb matches what they actually owned, is theirs
   alone — you wrote some of those clauses, so you are the last one who should be attesting to them.
   Report the half you checked, name the half you could not, and say the resume is **unverified**
   until they have read it. An agent that reads the layout and reports "all four gates pass" has
   closed a gate nobody stood at.

The checkers verify that a record is coherent, that a document parses, and that its prose obeys the
rules. None of them can see what it *looks* like. Three defect classes have escaped them, all
legitimately outside their scope:

| Defect | Checker verdict |
|---|---|
| Bullets rendering as tofu boxes — `U+F0B7` in a non-Symbol font | PASS |
| Headings in the theme font instead of the forced one | PASS, because the theme font was also a standard font |
| An orphaned heading, or a role split across a page break | PASS |

The emitter avoids the first two by construction — but avoiding a defect by construction is a claim,
and the render is where claims get checked.

Open the PDF and **look at every page**:

- [ ] Page count is what the view asked for
- [ ] Bullets are real glyphs, not boxes, and not a typed `•`
- [ ] One font family throughout — check headings against body, not just body against itself
- [ ] No heading stranded at the foot of a page with its content overleaf
- [ ] Dates aligned and consistently formatted
- [ ] The region profile did what you intended: no photograph or date of birth on an Australian
      resume, no missing nationality on a Gulf one
- [ ] Read the prose end to end. The prose gate catches the mechanical defects; it cannot tell you
      that a bullet is true, or that a verb overstates what they actually owned

`jsk render --pdf` and `jsk fit` build the PDF the same way, from the same `.tex`, so the page count
you are shown is the page count of the file you send. That was not true before: the fitter measured a
`.docx` and the deliverable came from LaTeX, and they disagreed.

**After fitting, recompile and re-check.** `jsk fit` writes a `.tex`; render's compile runs over it,
then the parse gate on the new PDF. Fitting changes layout, and layout is what the render gate reads.

**No renderer available?** Say so and mark the resume **unverified**. `jsk render` reports it in those
words when it finds no TeX engine; pass that on rather than quietly delivering a `.tex`. Do not treat
a passing parse gate as sufficient — it is a different gate answering a different question. A
geometric estimate of page fill is a reasonable fallback, but label it an estimate: one such estimate
read ~99% where the true value was ~94%. Sound, but pessimistic enough to prompt cuts nobody needed.

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
scope era. Repeating the employer six times fragments the page and turns a promotion story into
clutter. (ATS-maximal reverses this — see `ats-rules.md`.)

**Bridge a title nobody outside that employer can place.** "Member of Technical Staff (Full-Stack
Engineer)" on the role line. The official title stays first and verbatim — see `writing-rules.md`,
which also says when to leave a title alone.

**Label domains inline on every project.** For one long tenure this is the main defence against
"narrow exposure", and it is free.

**Platform above product.** If they built a platform and something on it, render them adjacent with
"(built on the platform above)". It pre-empts a real doubt about platform architects who never
shipped on their own platform.

**Two pages.** If content outgrows it, compress older roles rather than adding a page.

## If the tooling is missing

If the skill was installed as `SKILL.md` alone, write the record as URS anyway — the format is
specified in `references/urs-spec.md`. LaTeX can be written with the standard library and compiled by
any engine; keep the preamble minimal — `geometry` and `enumitem` are enough, and a template that
needs more is a template that will not build on the machine you actually have. Whatever you use, the
output must satisfy the parse gate: that is the contract, not the tool.

## Deliver

Present the files, say plainly which goes where, show the checker output. Then name what is still
weak — a missing certification, a thin metric, an unconfirmed claim. They can act on a known gap;
they cannot act on a compliment.

Tell them the `resume.json` is theirs and worth keeping. It is the file that makes the next resume
cheap, and the only one that records where each claim came from.
