# ATS rules

## Two variants

Readability and machine parsing conflict: middle dots, em dashes and a collapsed employer block read
well and parse poorly; naming the employer on every role line parses perfectly and looks repetitive.

| Variant | Send to |
|---|---|
| **Presentation** | Humans — referrals, direct email, interviews |
| **ATS-maximal** | Portals — Workday, Taleo, SuccessFactors, Naukri, agencies |

Plus a **plain-text** file for portals with paste-in boxes.

Either variant ships as **one PDF**: `--ats-max` chooses which variant that PDF holds and never
produces a second file. When unsure what an employer runs, send ATS-maximal.

## Hard rules — both variants

- **No tables**, including for layout or skills grids. Use tab stops or plain paragraphs.
- **No text boxes, shapes, SmartArt, charts or images.**
- **No multi-column layouts.**
- **Nothing in headers or footers** — many parsers discard them, and contact details are the worst
  thing to lose.

  These four are guaranteed by the one LaTeX emitter, across all five visual templates
  (`templates.md`), and guarded by a golden-file test rather than checked per render. A template
  moves only colour, typeface and rule weight.

- **Colour is safe; a glyph change is not.** Colour never reaches the text layer. Anything that
  changes the characters does: no `\MakeUppercase` on the **name** (an ATS extracts the name by
  heuristic), no letterspacing (`SUMMARY` extracts as `S U M M A R Y`). Uppercase *section headings*
  are fine — headings are matched case-insensitively.
- **`.pdf`**, from `jsk render --pdf`. Workday, Greenhouse, Lever and Ashby parse PDF text. **If a
  posting names a format, follow the posting**; a portal that demands `.docx` is one to submit to by
  hand.
- **A text layer, not a picture of one.** A scan, or a PDF without embedded fonts, extracts as
  nothing. The parse gate fails it.
- **No ligatures in the ATS-maximal render.** Computer Modern turns `fi` into U+FB01 and `ffi` into
  U+FB03, so "efficiency" extracts as a word that is not there. The ASCII variants break the pairs;
  the parse gate fails a ligature under `--strict` and warns on the presentation render.
- **Section headings contain the literal words** Summary, Skills, Experience, Education. "Core
  Competencies" is invisible to a parser matching on "Skills".
- **Bullet markers:** `•` in the presentation render, `-` in the ATS-maximal one. A decorative glyph
  breaks the line.
- **Dates as `Mon YYYY`** with a plain hyphen: `Jun 2025 - Present`.
- **No bracketed placeholders.** `[X%]` or `[NUMBER]` is worse than omitting the number. Any `[` in
  the finished text fails the check.

## ATS-maximal additions

- **ASCII only.** Replace `·` with `|`, en/em dashes with `-`, arrows with a word.
- **Name the employer on every role line:** `Senior Architect, Acme Corp | Jun 2025 - Present`. This
  matters most for **one employer with many roles**, where a collapsed block risks every bullet being
  attributed to one undated role.
- **Label contact fields:** `Phone: ... | Email: ...`
- **Heading "Technical Skills"**, and outline levels on headings so structure-based parsers find
  sections.

## The arrow trap

`Engineer → Senior Engineer → Lead → Architect`: stripped of the glyph, four titles become one string
and a parser may extract a phantom title. Write it as a sentence:

> Promoted through four roles: Engineer, Senior Engineer, Lead, Architect.

## Keywords

Relevance scoring is largely term frequency against the posting. Mirror its **exact** wording — if it
says "Solution Architect", the summary contains that phrase, not only "solution architecture". Spell
out and abbreviate on first use: `Retrieval-Augmented Generation (RAG)`. Put the posting's stack row
second in the skills block, after the architecture row. Do not stuff; a human reads it next.

## What this does not do

These rules stop a parser **losing** content. None exist to move a document up a ranking. Declined
when asked for:

- **Hidden text.** White or near-invisible type, keywords behind an image, terms sized to nothing, a
  keyword layer under the visible one.
- **Keyword injection.** A term the person cannot defend. Mirroring the posting's wording for work
  they did is the rule above; adding Kubernetes because the posting says Kubernetes is not.
- **Resume-score tools.** They score against a *model* of a parser, not the one the employer runs.
  The four gates answer questions that can be answered.

## What the parse gate verifies

`jsk check` reads the `.pdf` (text via `pymupdf`) or the `.txt`. First, that it is readable:

| Signal | Meaning |
|---|---|
| almost no extractable text | a scan, or fonts that are not embedded — unreadable to every parser |
| no embedded fonts | warns: extraction may vary between parsers |

Then on extracted text:

- The words summary / skills / experience / education each appear **in a heading** — a short,
  unpunctuated line. The word inside a sentence does not count.
- A parseable email, and a phone number with at least eight digits that is not a year range.
- No `[...]` span and no stray `[` anywhere.
- Bullet markers are `•` or `-`; a decorative glyph fails.
- At least four `Mon YYYY` dates; arrow glyphs absent — warn normally, fail under `--strict`.

Under `--strict` additionally: no non-ASCII at all (fails), plain hyphens in date ranges (fails),
and role lines that appear not to name an employer (warns — the heuristic is too rough to block on).

Malformed input reports a failure, never a crash. A `.docx` is rejected — it is not a deliverable.

It prints `FAIL n WARN n`, then each finding, then `PASS - safe to send` or
`DO NOT SEND - fix the failures above`, and exits non-zero on failure.
