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

Both variants ship as **one PDF**. `--ats-max` on `/jsk:tailor` chooses which variant that PDF
holds; it never produces a second file. One posting in, one PDF out.

When unsure what an employer runs, send ATS-maximal. A plain resume that parses beats a beautiful one
that arrives fragmented.

## Hard rules — both variants

- **No tables**, including for layout or skills grids. Use tab stops or plain paragraphs.
- **No text boxes, shapes, SmartArt, charts or images.**
- **No multi-column layouts.**
- **Nothing in headers or footers** — many parsers discard them, and contact details are the worst
  thing to lose.

  Those four are now **guaranteed rather than checked.** One LaTeX emitter produces every render
  and it cannot express any of them, so `check_ats.py` stopped looking per render and a golden-file
  test on `emit_latex.py` guards it instead. Keep the rules written down: they are why the renders
  look the way they do, and the first person to add a two-column layout will come here first.

  There are five **visual templates** (`--template`, see `templates.md`), and the guarantee covers
  all of them: the package list is pinned, no template can load anything that draws a box, and the
  golden-file test runs against every template rather than against one. Colour, typeface and rule
  weight are the only things a template moves.

- **Colour is safe; a glyph change is not.** Colour lives in a PDF's graphics state and never in its
  text layer, so a parser reading a navy heading reads the heading. That makes the four coloured
  templates exactly as parseable as the ink-only one, and `tests/test_themes.py` proves it by
  extracting from all five compiled PDFs and comparing.

  What is *not* safe is anything that changes the characters themselves. `\MakeUppercase` on the
  **name** did — the text layer said `PRIYA RAMAN` where every other template said `Priya Raman`,
  on the one field an ATS extracts by heuristic rather than matches against a known word. It is
  gone from the templates. Uppercase *section headings* stay: a heading is matched, `check_ats.py`
  lowercases first, and the same argument does not carry. Letterspacing is out for the same reason
  — it sets each character as its own glyph, and `SUMMARY` extracts as `S U M M A R Y`.

- **`.pdf`**, from `render_resume.py --pdf`. This reverses the older rule, which said `.docx` and
  not `.pdf`. The rule was right for its time and wrong by the end: a `.docx` and a PDF built from
  one record disagreed about page count, only the `.docx` was ever measured, and the file being
  measured was not the file being sent. Modern portals — Workday, Greenhouse, Lever, Ashby — parse
  PDF text without complaint. **If a posting names a format, follow the posting**; a portal that
  demands `.docx` is a portal to submit to by hand.
- **A text layer, not a picture of one.** The one genuinely new PDF hazard: a PDF whose fonts are
  not embedded, or that is a scan, extracts as nothing at all. `check_ats.py` fails on it.
- **No ligatures in the ATS-maximal render.** T1 Computer Modern turns `fi` into U+FB01 and `ffi`
  into U+FB03 — one codepoint each — so a parser reading "efficiency" gets a word that is not there.
  `emit_latex.py` breaks the pairs for the ASCII variants. This never showed up under `.docx`,
  because nothing ever looked at a rendered page.
- **Section headings must contain the literal words** Summary, Skills, Experience, Education. A
  heading like "Core Competencies" is invisible to a parser matching on "Skills".
- **Bullet markers a parser maps:** `•` in the presentation render, `-` in the ATS-maximal one.
  A PDF carries no list *structure* — the marker is a glyph in the text layer whatever produced it —
  so the old rule about real numbering versus a typed glyph no longer has anything to distinguish.
  What is left is the choice of glyph, and a decorative one breaks the line.
- **Dates as `Mon YYYY`** with a plain hyphen: `Jun 2025 - Present`.
- **No bracketed placeholders.** `[X%]` or `[NUMBER]` shipping in a resume is worse than omitting
  the number. Any `[` in the finished text fails the check — a bracket in a resume is almost always
  a leftover.

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

## What this does not do

Every rule above exists so a parser does not **lose** content. None of it exists to move a document
up a ranking, and the difference is the whole boundary of this skill.

Out of scope, and declined when asked for:

- **Hidden text.** White or near-invisible type, keyword blocks behind an image, terms sized to
  nothing, a keyword layer under the visible one. It is a lie told to a machine that a human then
  reads back in the interview.
- **Keyword injection.** A term the person cannot defend, whatever it does to a match rate. Mirroring
  a posting's exact wording for work they actually did is the rule above; adding Kubernetes because
  the posting says Kubernetes is not.
- **Resume-score tools.** They score a document against a *model* of a parser, not the parser the
  employer runs, and the number moves for reasons that have nothing to do with the work. The four
  gates in `SKILL.md` answer questions that can actually be answered.

The document is built for a person reading it in six seconds. The parse rules exist so that document
reaches them intact — that is all they are for.

## What check_ats.py verifies

It reads the `.pdf` (text via `pymupdf`) or the `.txt`. The seven structural checks it used to run
over `word/document.xml` are gone with the format that could express them — see the note under the
hard rules above.

First, that the deliverable is readable at all:

| Signal | Meaning |
|---|---|
| almost no extractable text | a scan, or fonts that are not embedded — unreadable to every parser |
| no embedded fonts | warns: extraction may vary between parsers |

Then on extracted text:

- The words summary / skills / experience / education each appear **in a heading** — a paragraph
  styled `Heading*`, or short and unpunctuated. The word buried in a summary sentence does not
  count; that is the whole point of the rule.
- A parseable email, and a phone number with at least eight digits that is not a year range.
- No `[...]` span and no stray `[` anywhere.
- Bullet markers are `•` or `-`, the two the templates emit and every parser maps. A decorative
  glyph fails. In a `.docx` this rule asked whether the bullet had been *typed* instead of being
  real list numbering; a PDF has no list structure to compare against, so the question became which
  glyph rather than whether one was typed.
- At least four `Mon YYYY` dates; arrow glyphs absent — warn normally, fail under `--strict`.
- The font-name allowlist is gone. One template chooses the typeface, and a LaTeX PDF embeds Latin
  Modern, which no list of Office fonts would have contained: the check would have warned on every
  correct render and caught no incorrect one. Extractability replaced it, which is what the name
  check was a proxy for.

Under `--strict` additionally: no non-ASCII at all (fails), plain hyphens in date ranges (fails),
and role lines that appear not to name an employer (warns — the heuristic is too rough to block on).

Malformed input never crashes: a file that is not a readable `.pdf` reports a failure like any
other finding. A `.docx` is rejected — it is no longer a deliverable, and a gate that quietly
accepted one would be checking a file nobody sends.

Print `FAIL n WARN n`, then each finding, then `PASS - safe to send` or
`DO NOT SEND - fix the failures above`. Exit non-zero on failure.
