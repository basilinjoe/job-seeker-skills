# Templates

Five visual templates for the rendered PDF. `jsk render --template NAME` picks one;
`jsk render --list-templates` prints them; `jsk preview <resume.json> --out DIR` renders all five from
one `resume.json`, with page counts, so the choice is made by looking.

**A template changes how the resume looks and nothing else.** All content decisions are made before
a template is consulted, and all five extract to the same text in the same order
(`tests/test_themes.py` compares the extracted text layers).

## The catalogue

| Template | Look | Reach for it when |
|---|---|---|
| **`monolith`** *(default)* | Ink only, centred, full-width rules, Latin Modern | Banking, law, government, academia — anywhere restraint is the brand |
| **`meridian`** | Deep navy accent, left-aligned header, sans throughout | Consulting, product, platform and engineering leadership |
| **`ember`** | Warm serif, terracotta stub rules, centred | Design, brand, research, writing, senior individual contributors |
| **`circuit`** | Teal bars hung in the left margin, geometric heads, dense | Software, data, security, infrastructure |
| **`atrium`** | Hairlines, 1in margins, muted slate, maximum white space | Executive one-pagers and short senior resumes |

`monolith` is the default so colour is opt-in: a re-render mid-search gives back the document they
had.

Density differs: the same resume is one page in `circuit` and two in `atrium`. Choose a two-page
render over an available one-page one on purpose.

## Choosing

The honest input is the employer, not the applicant's taste. Send `monolith` when you do not know;
send an expressive one when the employer's own materials are expressive.

No template affects a parser. For a portal, what matters is `--ats-max`, which chooses the
*variant*; any template is safe.

## What the design is doing

The top third of page one takes most of a recruiter's attention, then the left edge; about six items
absorb the first pass — name, current title, current employer, previous title, previous employer,
dates. Every template is built around that.

- **The header block is the investment.** Name at display size, then the professional title at its
  own size and colour, then contact details a step *down* in size, in muted grey.
- **Section heads own the left edge.** Size, weight and colour move together. In `circuit` the accent
  bar hangs in the margin in a zero-width box so heading text starts on the same vertical as body
  lines.
- **Proximity carries the structure.** The gap above a section head is the largest in the document
  and always beats the gap between entries.
- **The accent has a budget of three text sites** — typically the headline, section heads and skills
  labels. Rules and bullet markers are excluded.
- **Employer bold, title italic, both in ink.** Never mute the title to grey.
- **One vertical rhythm unit per template.** Every gap is a multiple of it.
- **Ragged right** in four of the five: justification at a 6.5-inch measure opens rivers.

## What a template may not do

The structural rules in `ats-rules.md` apply unchanged: no second column, table, text box, image,
header or footer. No template loads a package that could draw one; the package list is pinned by a
test. Also:

- **No letterspacing** — `SUMMARY` extracts as `S U M M A R Y`.
- **No uppercased name** — it changes the extracted name, which a parser finds by heuristic.
  Uppercase *headings* are fine; headings are matched case-insensitively.
- **No `microtype` protrusion** — it pushes punctuation past the margin, and a test measures that
  nothing does.

## Fonts

TeX Gyre (Termes, Pagella, Heros, Adventor) with Latin Modern as the floor. Every font package loads
inside `\IfFileExists`, so a thin TeX distribution substitutes Latin Modern and warns rather than
failing.

## Templates and the fitter

`jsk fit` shrinks the body copy and leaves the name and section heads at full size: display sizes are
written unit-less (`\fontsize{24}{27}`) to stay outside the regex the body-size lever matches. The
four density levers exist in every template as multiples of its rhythm unit.

## Adding one

`urs/themes.py`, one entry in `THEMES`. State only the template's idea; `_theme()` fills in the rest.
The tests check contrast floors, the accent budget, guarded font loads, the text layer and the right
margin for every template in the dictionary.
