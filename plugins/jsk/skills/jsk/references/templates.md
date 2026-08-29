# Templates

Five visual templates for the rendered PDF. `--template NAME` on `render_resume.py` picks one;
`--list-templates` prints them; `preview_templates.py` renders all five from one record so the
choice can be made by looking rather than by reading a sentence about it.

**A template changes how the resume looks and nothing else.** Every content decision was made in
`urs/resolve.py` before a template is consulted, and all five extract to the same text — the same
words, in the same order. `tests/test_themes.py` compiles all five and compares the extracted text
layers rather than taking the claim on trust.

## The catalogue

| Template | Look | Reach for it when |
|---|---|---|
| **`monolith`** *(default)* | Ink only, centred, full-width rules, Latin Modern | Banking, law, government, academia — anywhere restraint is the brand |
| **`meridian`** | Deep navy accent, left-aligned header, sans throughout | Consulting, product, platform and engineering leadership |
| **`ember`** | Warm serif, terracotta stub rules, centred | Design, brand, research, writing, senior individual contributors |
| **`circuit`** | Teal bars hung in the left margin, geometric heads, dense | Software, data, security, infrastructure |
| **`atrium`** | Hairlines, 1in margins, muted slate, maximum white space | Executive one-pagers and short senior resumes |

`monolith` is the default because colour should be opt-in: re-rendering a resume mid-search gives
you the document you had, not a redesign you did not ask for.

Density is the one difference that is not a matter of taste. The same record is one page in
`circuit` and two in `atrium`. `preview_templates.py` prints the page count for each, and a
two-page resume where a one-page resume was available is a decision worth making on purpose.

## Choosing

The templates say the same words in the same order. What differs is **which of those words a
reader sees first**, and the honest input to that choice is the employer, not the applicant's
taste. Send `monolith` when you do not know. Send the expressive ones when the reader's own
materials are expressive — a design studio's careers page tells you more than any rule here can.

None of this affects a parser. If the posting goes into a portal, the thing that matters is
`--ats-max`, which chooses the *variant*; the template is orthogonal and any of them is safe.

## What the design is doing

Recruiter eye-tracking is consistent about two things: the top third of page one takes most of the
attention, and what is left runs down the left edge. Roughly six items absorb most of a first
pass — name, current title, current employer, previous title, previous employer, dates. Every
template is built around those two facts.

- **The header block is the investment.** Name at display size, then the professional title at its
  own size and colour, then contact details a step *down* in size and in the muted grey. The title
  is one of the six; a phone number is not, and sizing them alike wastes the most valuable space
  on the page.
- **Section heads own the left edge.** They are the only element there, so size, weight and colour
  move together — a heading that is merely bigger reads as bigger text, not as a new section. In
  `circuit` the accent bar is hung in the margin with a zero-width box so the heading text still
  starts on the same vertical as every body line: an indented heading destroys the one edge the
  whole argument rests on.
- **Proximity carries the structure.** The gap above a section head is the largest in the document
  and always beats the gap between entries inside a section. Get that backwards and each heading
  looks attached to the section it just ended.
- **The accent has a budget of three text sites.** Typically the headline, the section heads and
  the skills labels. Rules and bullet markers are marks rather than text and are excluded — they
  guide without competing. More than three and the eye has no path, because everything is
  emphasised and so nothing is.
- **Employer bold, title italic, both in ink.** Weight separates the two anchors. Muting the title
  to grey is how a resume loses one of its six anchors while looking more designed.
- **One vertical rhythm unit per template.** Every gap is a multiple of it, so the spacing reads as
  intentional instead of as four numbers tuned by eye until they stopped looking wrong.
- **Ragged right** in four of the five. At a 6.5-inch measure, justification opens word gaps wide
  enough to read as rivers, and every extra millimetre between words costs a scan being done in
  seconds.

## What a template may not do

The structural rules in `ats-rules.md` are unchanged and unchangeable here: no second column, no
table, no text box, no image, no header or footer. No template loads a package that could draw
one, and the package list is pinned by a test.

Three further prohibitions are less obvious, and two of them were found by rendering and looking:

- **No letterspacing.** The standard way to get airy capitals sets each character as its own
  positioned glyph, so `SUMMARY` extracts as `S U M M A R Y` and the heading a parser matches on
  stops existing.
- **No uppercased name.** Two templates shipped `\MakeUppercase` on the name, because a heavy
  all-caps name is the strongest anchor available at the top of a page. It is also the one choice
  on this list a parser can see: it changes the glyphs, so the text layer said `PRIYA RAMAN` where
  every other template said `Priya Raman`. Uppercase *headings* are fine — a heading is matched
  against a known word and `check_ats.py` lowercases first. A name is not matched against
  anything; it is extracted, by a heuristic that expects a name to look like a name. The option is
  gone rather than discouraged.
- **No `microtype` protrusion.** It pushes punctuation past the margin, and a test measures that
  nothing does.

## Fonts

TeX Gyre (Termes, Pagella, Heros, Adventor) with Latin Modern as the floor. Every font package is
loaded inside `\IfFileExists`, so a thin TeX distribution substitutes Latin Modern and warns
rather than failing. A typeface is worth a package; it is not worth a build failure on someone
else's machine.

## Templates and the fitter

`fit_pages.py` shrinks the body copy and leaves the name and the section heads at full size. That
is not luck: display sizes are written unit-less — `\fontsize{24}{27}`, which LaTeX reads as points
just the same — specifically to keep them outside the regex the body-size lever matches. A fitter
that shrank the anchors along with the body would hold the page count and dismantle the hierarchy
the page count exists to protect, and it would do it silently.

The four density levers are still there in every template, written as multiples of that template's
rhythm unit. Fitting a resume works the same whichever one you chose.

## Adding one

`urs/themes.py`, one entry in `THEMES`. State only what the template's idea is; `_theme()` fills in
the rest. Then run the tests: contrast floors, the accent budget, the guarded font loads, the text
layer and the right margin are all checked for every template in the dictionary, so a new one is
covered the moment it exists.
