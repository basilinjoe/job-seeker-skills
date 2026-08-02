# ATS rules

## Two variants

Readability and machine parsing genuinely conflict. Middle dots, em dashes and a collapsed employer
block read beautifully and parse poorly. Naming the employer on every role line parses perfectly and
looks repetitive. You cannot optimise both in one document.

| Variant | Send to |
|---|---|
| **Presentation** | Humans — referrals, direct email, interviews |
| **ATS-maximal** | Portals — Workday, Taleo, SuccessFactors, Naukri, agencies |

Plus a **plain-text** file for portals with paste-in boxes.

When unsure what an employer runs, send ATS-maximal. A plain resume that parses beats a beautiful one
that arrives fragmented.

## Hard rules — both variants

- **No tables**, including for layout or skills grids. Use tab stops or plain paragraphs.
- **No text boxes, shapes, SmartArt, charts or images.**
- **No multi-column layouts.**
- **Nothing in headers or footers** — many parsers discard them, and contact details are the worst
  thing to lose.
- **`.docx`**, not `.pdf`, `.doc` or `.rtf`, unless the posting names a format.
- **Standard fonts:** Calibri, Arial, Helvetica, Georgia, Times New Roman.
- **Section headings must contain the literal words** Summary, Skills, Experience, Education. A
  heading like "Core Competencies" is invisible to a parser matching on "Skills".
- **Real bullet lists** via numbering definitions, never a typed `•` or `-`.
- **Dates as `Mon YYYY`** with a plain hyphen: `Jun 2025 - Present`.
- **No bracketed placeholders.** `[X%]` shipping in a resume is worse than omitting the number.
  Search the finished text for `[` before delivering.

## ATS-maximal additions

- **ASCII only.** Replace `·` with `|`, en/em dashes with `-`, arrows with a word. Non-ASCII is
  usually fine, but when stripped the surrounding text runs together.
- **Name the employer on every role line:** `Senior Architect, Acme Corp | Jun 2025 - Present`.
  Repetitive to a human, unambiguous to a machine. This matters most for **one employer with many
  roles** — the hardest shape for a parser, where a collapsed block risks every bullet being
  attributed to a single undated role.
- **Label contact fields:** `Phone: ... | Email: ...`
- **Heading "Technical Skills"**, and outline levels on headings so structure-based parsers find
  sections.

## The arrow trap

`Engineer → Senior Engineer → Lead → Architect` is the highest-risk element on an otherwise
well-designed resume. If the glyph is stripped, four job titles become one string and a parser may
extract a phantom title. Write it as a sentence:

> Promoted through four roles: Engineer, Senior Engineer, Lead, Architect.

## Keywords

Relevance scoring is largely term frequency against the posting. Mirror its **exact** wording — if it
says "Solution Architect", the summary should contain that phrase, not only "solution architecture".
Spell out and abbreviate on first use: `Retrieval-Augmented Generation (RAG)`. Put the posting's
stack row second in the skills block, right after the architecture row. Do not stuff; a human reads
it after the machine.

## What check_ats.py verifies

A `.docx` is a zip. Read `word/document.xml` and check:

| Signal | Meaning |
|---|---|
| `<w:tbl>` | table |
| `w:txbxContent` or `<v:shape` | text box |
| `word/media/` entries | images |
| `<w:drawing>` | drawing object |
| `diagrams` / `charts` parts | SmartArt or chart |
| non-empty `word/header*.xml` / `footer*.xml` | content parsers discard |
| `<w:cols w:num="2+">` | multi-column |

Then on extracted text: the words summary / skills / experience / education each appear; a parseable
email and phone are present; no bracketed placeholders; no literal bullet glyph starting a line; at
least four `Mon YYYY` dates; fonts in the standard set; arrow glyphs absent (warn normally, fail
under `--strict`).

Under `--strict` additionally: no non-ASCII at all, plain hyphens in date ranges, and role lines name
an employer.

Print `FAIL n WARN n`, then each finding, then `PASS - safe to send` or
`DO NOT SEND - fix the failures above`. Exit non-zero on failure.
