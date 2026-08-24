# Mode: resume

Render the bundle into verified files. Read `references/ats-rules.md`, `references/writing-rules.md`
and the structure rules in `references/bundle-spec.md` first — or the bundle's own
`resume-generation/*` if present, which wins.

## Output

| File | For |
|---|---|
| `<Name>_Resume.docx` | Humans |
| `<Name>_Resume_ATS.docx` | Portals |
| `<Name>_Resume_ATS.txt` | Paste-in boxes |

## Build order

1. **Read** `profile/positioning.md`, `resume-generation/*`, all of `projects/`, and
   `open-questions.md` — you need to know what is unresolved before you publish it.

2. **Rank evidence** by `strength`, `recency` and fit to their stated target.

3. **Write the summary as a claim**, per `writing-rules.md`.

4. **Generate the presentation variant.**

5. **Generate the ATS variant** from the same content with the ATS-maximal transformations.

6. **Generate plain text** by extracting the ATS variant's paragraphs in order, prefixing list items
   with `- `.

7. **Verify — not optional:**

```bash
python3 <skill-dir>/scripts/check_ats.py <Name>_Resume.docx
python3 <skill-dir>/scripts/check_ats.py <Name>_Resume_ATS.docx --strict
python3 <skill-dir>/scripts/check_prose.py <Name>_Resume.docx
```

`<skill-dir>` is this skill's own directory — see the Scripts section of `SKILL.md`. On Windows use
`python` or `py -3`.

**These check different things.** `check_ats.py` verifies the document *parses*: no tables, no
header content, a heading a parser can match on. `check_prose.py` verifies it *reads*: third person,
placeholders, sentences that stop before their object, phrases `writing-rules.md` says to cut, bullets
repeated across projects. A third-person bullet is not a parsing defect, so `check_ats.py` passes it
and is right to.

Run `check_prose.py` on the plain-text variant too — it is generated from the same content, so a
defect in one is a defect in both.

All must PASS. **Show the output.** Fix and re-run rather than explaining away a failure.

8. **Fit to two pages** — measure, do not guess:

```bash
python3 <skill-dir>/scripts/fit_pages.py <Name>_Resume.docx --target-pages 2
```

It renders, counts, reports per-page fill, and — when the document runs over — names the block that
spilled and how much room the previous page actually had. Then it applies density levers in a fixed
order (inter-paragraph spacing, bullet spacing, margins, font size) and **stops at the floors**: 10pt
body, 0.5" margins. Never cross them by hand either; both read as desperate and hurt parsing.

**Trimming words rarely helps.** Cutting eight words from a bullet that wraps to six lines usually
still wraps to six lines. If the script exits non-zero, the budget is unreachable typographically and
the answer is to remove evidence — compress or cut the oldest, lowest-ranked roles per the treatment
table in `references/mode-tailor.md` — not to shrink type further.

Fitting changes layout, so re-run `check_ats.py` on the fitted file before step 9.

9. **Look at the render — the second gate, and not optional either.**

The checkers verify that a document parses and that its prose obeys the rules. Neither can see what
it *looks* like. Three defect classes have escaped them, all legitimately outside their scope:

| Defect | Checker verdict |
|---|---|
| Bullets rendering as tofu boxes — `U+F0B7` in a non-Symbol font | PASS |
| Headings in the theme font instead of the forced one — `w:asciiTheme` beats `w:ascii` | PASS, because the theme font was also a standard font |
| An orphaned heading, or a role split across a page break | PASS |

Convert to PDF and **look at every page**:

- [ ] Page count is what you intended
- [ ] Bullets are real glyphs, not boxes, and not a typed `•`
- [ ] One font family throughout — check headings against body, not just body against itself
- [ ] No heading stranded at the foot of a page with its content overleaf
- [ ] Dates aligned and consistently formatted
- [ ] Read the prose end to end. `check_prose.py` catches the mechanical defects; it cannot tell you
      that a bullet is true, or that a verb overstates what they actually owned

`fit_pages.py` already produced a PDF during step 8; open that one.

**No renderer available?** Say so and mark the resume **unverified**. Do not treat a passing
`check_ats.py` as sufficient — it is a different gate answering a different question. A geometric
estimate of page fill is a reasonable fallback, but label it an estimate: one such estimate read
~99% where the true value was ~94%. Sound, but pessimistic enough to prompt cuts nobody needed.

## Generating the .docx

Any method that produces clean OOXML is fine. Whatever you use, the output must satisfy
`check_ats.py` — that is the contract, not the tool.

If a `docx` library is unavailable, a `.docx` is a zip of XML and can be written with the standard
library alone. Keep the markup minimal: paragraphs, runs, a numbering definition for bullets, tab
stops for right-aligned dates. Minimal markup parses best anyway.

## Deliver

Present the files, say plainly which goes where, show the checker output. Then name what is still
weak — a missing certification, a thin metric, an unconfirmed claim. They can act on a known gap;
they cannot act on a compliment.
