# Mode: resume

Render the bundle into verified files. Read `references/ats-rules.md`, `references/writing-rules.md`,
`references/urs-spec.md` and the structure rules in `references/bundle-spec.md` first — or the
bundle's own `resume-generation/*` if present, which wins.

## The pipeline is JSON-first

**Never author a `.docx` or a `.tex` by hand.** Build the URS document, then render every format from
it:

```
bundle (Markdown)  ->  resume.json (URS)  ->  render plan  ->  .tex -> .pdf
                                                           \-> .docx  x2
                                                           \-> .txt
```

The reason is not tidiness. A hand-built presentation `.docx` and a hand-built ATS `.docx` are two
documents that have to agree about every date, every bullet and every number, and they stop agreeing
the moment one is edited — usually silently, usually in the copy that gets sent. One record with
three emitters cannot drift, because no emitter decides what the document says. `scripts/urs/plan.py`
makes every content decision exactly once; the emitters only choose markup.

The JSON is also the durable artefact. Save it — `resume-generation/resume.json` for a general
rebuild, `tailoring/applications/<company>-<role>.resume.json` for a tailored one. A month later the
question is never "what did the resume look like", it is "what did it claim, and where did that come
from", and only the record answers that.

## Output

| File | For |
|---|---|
| `resume.json` | The record every other file is rendered from |
| `<Name>_Resume.pdf` | Humans — referrals, direct email, interviews |
| `<Name>_Resume.docx` | Humans who want an editable file |
| `<Name>_Resume_ATS.docx` | Portals — Workday, Taleo, SuccessFactors, Naukri |
| `<Name>_Resume_ATS.txt` | Paste-in boxes |

## Build order

1. **Read** `profile/positioning.md`, `resume-generation/*`, all of `projects/`, and
   `open-questions.md` — you need to know what is unresolved before you publish it.

2. **Rank evidence** by `strength`, `recency` and fit to their stated target.

3. **Write the summary as a claim**, per `writing-rules.md`.

4. **Author `resume.json`.** This is where the writing happens, and the only place it happens.

   - Every bullet is an `Achievement` with `text`, `provenance` and — whenever the prose carries a
     number — `metrics` mirroring it. The validator fails a bullet whose numbers appear in no metric,
     which is the check that stops a rewritten bullet from quietly inflating a figure.
   - `provenance.status` copies straight across from the concept's frontmatter. Anything `inferred`
     stays `inferred`; the view's `provenance_floor` then keeps it out of the document until they
     confirm it. Do not launder a status while transcribing.
   - One employer with several roles is **one** `engagement` with several `positions`. Do not repeat
     the employer as separate engagements — the promotion story is the point.
   - Declare the region profile on each view: `urs:profile:au/1`, `in/1`, `ae/1`, or omit it for the
     region-neutral default. This is what decides whether a photograph, a date of birth, referees, a
     declaration block or a salary expectation are emitted, and getting it wrong is not a formatting
     error — a date of birth on an Australian application is a liability, and its absence on a Gulf
     one reads as an incomplete file.
   - Write one view per variant. A view **selects**: it references ids, orders them, redacts. It
     never contains content text, and the validator rejects it if it does.

5. **Validate before rendering — the gate in front of the gates:**

```bash
python3 <skill-dir>/scripts/validate_urs.py resume.json --level 2
```

   Nothing is rendered from a document that fails. A defect in the record becomes a defect in four
   files at once, and finding it in the `.docx` means finding it three files too late.

6. **Render every format from that one file:**

```bash
python3 <skill-dir>/scripts/render_resume.py resume.json --out . --view <view-id> --pdf
```

   That writes the `.tex`, compiles it if a TeX engine is present, and writes both `.docx` variants
   and the plain text. Read the warnings it prints: a withheld bullet, a field the region profile
   requires and the record does not have, a bracket that should not be in anyone's resume.

7. **Verify — not optional:**

   Hand steps 7 to 9 to `jsk-verifier` — it runs every gate, measures the fit, reads the PDF,
   and returns each verdict verbatim with the `resume.json` site for every defect. It cannot edit a
   document, which is the point. Run the commands inline where no agent is available; the procedure
   below is the same either way.

```bash
python3 <skill-dir>/scripts/check_ats.py <Name>_Resume.docx
python3 <skill-dir>/scripts/check_ats.py <Name>_Resume_ATS.docx --strict
python3 <skill-dir>/scripts/check_prose.py <Name>_Resume.docx
```

`<skill-dir>` is this skill's own directory — see the Scripts section of `SKILL.md`. On Windows use
`python` or `py -3`.

**These check different things.** `validate_urs.py` verifies the *record* is coherent. `check_ats.py`
verifies the document *parses*: no tables, no header content, a heading a parser can match on.
`check_prose.py` verifies it *reads*: third person, placeholders, sentences that stop before their
object, phrases `writing-rules.md` says to cut, bullets repeated across projects. A third-person
bullet is not a parsing defect, so `check_ats.py` passes it and is right to.

Run `check_prose.py` on the plain-text variant too — same record, so a defect in one is a defect in
both.

All must PASS. **Show the output** — the checker's own lines. An agent's summary of a checker is not
the checker, and the person is entitled to the evidence rather than a report of it. Fix and re-run
rather than explaining away a failure. Fix it *in `resume.json`* and re-render; editing the `.docx`
puts the record and the document out of step, which is the failure this pipeline exists to prevent.

8. **Fit to the page budget** — measure, do not guess:

```bash
python3 <skill-dir>/scripts/fit_pages.py <Name>_Resume.docx --target-pages 2
```

It renders, counts, reports per-page fill, and — when the document runs over — names the block that
spilled and how much room the previous page actually had. Then it applies density levers in a fixed
order (inter-paragraph spacing, bullet spacing, margins, font size) and **stops at the floors**: 10pt
body, 0.5" margins. Never cross them by hand either; both read as desperate and hurt parsing.

The budget itself comes from the view (`budget.pages`) or the region profile — two pages neutral,
three in India and the Gulf, up to four in Australia. Do not compress an Australian resume to a US
page count nobody asked for.

**Trimming words rarely helps.** Cutting eight words from a bullet that wraps to six lines usually
still wraps to six lines. If the script exits non-zero, the budget is unreachable typographically and
the answer is to remove evidence — drop bullets from the view, per the treatment table in
`references/mode-tailor.md` — not to shrink type further. Removing them from the *view* leaves them in
the record, which is the point: next month's posting may want exactly what this one did not.

Fitting changes layout, so re-run `check_ats.py` on the fitted file before step 9.

9. **Look at the render — the last gate, and not optional either.** `jsk-verifier` reads the
   PDF as part of its run; if you are working inline, open it yourself. Nobody signs this one off
   from a checker's exit code.

The checkers verify that a record is coherent, that a document parses, and that its prose obeys the
rules. None of them can see what it *looks* like. Three defect classes have escaped them, all
legitimately outside their scope:

| Defect | Checker verdict |
|---|---|
| Bullets rendering as tofu boxes — `U+F0B7` in a non-Symbol font | PASS |
| Headings in the theme font instead of the forced one — `w:asciiTheme` beats `w:ascii` | PASS, because the theme font was also a standard font |
| An orphaned heading, or a role split across a page break | PASS |

The emitter avoids the first two by construction — the bullet glyph is `U+2022` in Calibri, and
`w:asciiTheme` is never written — but avoiding a defect by construction is a claim, and the render is
where claims get checked.

Open the PDF and **look at every page**:

- [ ] Page count is what the view asked for
- [ ] Bullets are real glyphs, not boxes, and not a typed `•`
- [ ] One font family throughout — check headings against body, not just body against itself
- [ ] No heading stranded at the foot of a page with its content overleaf
- [ ] Dates aligned and consistently formatted
- [ ] The region profile did what you intended: no photograph or date of birth on an Australian
      resume, no missing nationality on a Gulf one
- [ ] Read the prose end to end. `check_prose.py` catches the mechanical defects; it cannot tell you
      that a bullet is true, or that a verb overstates what they actually owned

`render_resume.py --pdf` produces the PDF from LaTeX; `fit_pages.py` produces one from the `.docx`.
Look at both if you changed the fit — they are different documents.

**No renderer available?** Say so and mark the resume **unverified**. `render_resume.py` reports it in
those words when it finds no TeX engine; pass that on rather than quietly delivering a `.tex`. Do not
treat a passing `check_ats.py` as sufficient — it is a different gate answering a different question.
A geometric estimate of page fill is a reasonable fallback, but label it an estimate: one such
estimate read ~99% where the true value was ~94%. Sound, but pessimistic enough to prompt cuts nobody
needed.

## If the scripts are missing

If the skill was installed as `SKILL.md` alone, write the record as URS anyway — the format is
specified in `references/urs-spec.md` and the schema in `schema/urs-v1.schema.json`. A `.docx` is a
zip of XML and can be written with the standard library; keep the markup minimal — paragraphs, runs, a
numbering definition for bullets, tab stops for right-aligned dates. Minimal markup parses best
anyway. Whatever you use, the output must satisfy `check_ats.py`: that is the contract, not the tool.

## Deliver

Present the files, say plainly which goes where, show the checker output. Then name what is still
weak — a missing certification, a thin metric, an unconfirmed claim. They can act on a known gap;
they cannot act on a compliment.

Tell them the `resume.json` is theirs and worth keeping. It is the file that makes the next resume
cheap, and the only one that records where each claim came from.
