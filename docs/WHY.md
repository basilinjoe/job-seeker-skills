# Why it works this way

Every design decision here has a failure behind it. This document is the reasoning; you can use the
plugin without reading a word of it.

## The knowledge base is the source of truth

Most resume tools start from a blank page every time. This one keeps your career in one Markdown
file and treats a resume as one *rendering* of it.

Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.

`user-knowledgebase.md` is plain Markdown: readable in any editor, versionable in Git, readable by AI
tools without a translation layer. Keep it in a repo you control so it outlives any single tool,
including this one.

## One file, not a folder of concepts

This was a graph — several hundred linked Markdown concepts, with a compiler over them, a write
command per noun, a query layer to read them back and a migration tool to move between layouts. That
shape is right for a knowledge base too large to hold in one context. **A career is not.**

One file changes what the rules have to be. There is no write transaction to make atomic, because a
write to one file either happened or did not. There is no id to resolve across documents, because
everything an id could point at is a heading away. There is no compile, because the reader is a model
that can hold all of it.

What it costs is the guarantees a compiler gave for free — a write command refused a `role:` naming
no role, and nothing does now until the record gate runs. That is a real trade, and the record gate
got stricter to catch what it can. What it buys is a document the person whose career it is can open,
read end to end, and correct. That is the property that actually decides whether a career record
survives a year, and no amount of referential integrity substitutes for it.

## Every document is rendered from JSON, never hand-built

The knowledge base is written out as a [URS](../plugins/jsk/skills/jsk/references/urs-spec.md)
record, and the LaTeX, the PDF and the plain text are all emitted from that one file.

Two hand-built documents have to agree about every date, bullet and number, and they stop agreeing
the moment one is edited; usually silently, usually in the copy that gets sent. One record with
several emitters cannot drift, because no emitter decides what the document says.

It is also what makes a resume answerable a year later. The record carries the provenance of every
claim and the view that selected it, so "what did this application claim, and where did that come
from" has an answer.

`render_resume.py` resolves the record once — selection, ordering, provenance filtering, profile
gating, ASCII folding, date formatting — and the emitters translate that plan into markup without
deciding anything. That split is what guarantees the PDF and the plain text cannot say different
things.

## Four gates, not one

**A checker verifies that a document parses — not that it is correct.** That sentence is the whole
reason there are four gates.

`check_ats.py` passed a resume whose bullets rendered as tofu boxes. It passed one whose headings
silently resolved to a theme font. It passed one written in the third person. All three correctly,
all three outside its scope. The first two are visual and cannot be linted out of the XML; the third
is why `check_prose.py` exists at all.

| Gate | Question | How |
|---|---|---|
| Record | Is the source coherent, and does every number trace to a metric? | `validate_urs.py`, before anything renders |
| Parse | Will an ATS read this without mangling it? | `check_ats.py` |
| Prose | Does it obey the writing rules? | `check_prose.py` |
| Render | Does it *look* right, and is it *true*? | Convert to PDF and look at every page |

Without a renderer, a resume is marked **unverified** rather than assumed fine. A page count nobody
measured is a page count nobody knows.

## What the parse gate actually looks for

The things that make applicant tracking systems silently mangle a resume: tables, text boxes,
header/footer content, section words that appear in prose but never in a heading, any leftover
bracketed placeholder, an unparseable phone number, and arrow glyphs that fuse two job titles into
one when the arrow is stripped. A resume that fails the checker is not delivered.

## What the prose gate catches that parsing cannot

Third person, unresolved placeholders, sentences that stop before their object, phrases that read as
junior, bullets repeated across projects, and bullets that clear their throat before reaching the
verb. A resume written in the third person is not a parsing defect, so nothing was catching it.

## Numbers are checked against their metrics

Every numeral in a bullet must appear in a structured metric on that bullet, or `validate_urs.py`
fails the record before anything renders. It is the check that catches a rewritten bullet quietly
inflating a figure.

## Tailoring cannot invent, structurally

A tailored resume is a *view*: it references evidence by id, orders it, and redacts. The validator
rejects free text inside a view, so a posting the record has no evidence for produces nothing to
point at rather than a plausible new bullet.

Job descriptions are ranked against structured metadata on each project — capabilities, technologies
and domains, compared as exact strings — using requirements read from the posting's own frontmatter.
So the document you review is the one that produced the ranking.

A script did that arithmetic while the career was a folder of concepts to be compiled. `jsk-tailor-analyst`
does it now and **shows the terms behind every number**: which requirements each project matched and
which it missed, in a table beside the assessment. A score nobody can recompute would be worse than
no score, and that is the whole reason the working is written down rather than the ranking asserted.

Either way it reports what each project *failed* to match, and tells you where you fall short instead
of flattering you. Being flattered costs interviews.

## Two variants, because readability and parsing conflict

A presentation variant for humans, an ATS-maximal variant for portals, plus plain text for paste-in
boxes. One document cannot be optimal for both readers, and pretending otherwise means quietly losing
one of them.

## Every fact carries provenance

`confirmed` (you said it), `inferred` (written for you, needs sign-off), `needs-verification` (a known
gap). Nothing inferred reaches a resume unconfirmed.

You will often be written better prose than you spoke; that is useful, but reasoning supplied on your
behalf is not yours until you agree with it. The danger is precisely that it reads well — plausible,
well-written, and indefensible when an interviewer asks a follow-up.

## The same record renders correctly in different markets

A region profile decides what each market may and must not see. A photograph and date of birth are
conventional on a Gulf resume and a liability on an Australian one; India expects academic grades on a
CGPA scale, a father's name and a declaration block; the Gulf screens visa status and transferability
before anything else. Australia, India and the UAE ship as profiles, and adding a market is a JSON
file rather than a schema change.

## Why a new schema instead of JSON Resume

JSON Resume is a JSON container around unstructured prose. A bullet is a bare string, so nothing can
verify a metric. Nothing carries an id, so tailoring means copy-and-mutate and the copies drift.
Nothing carries provenance, so "I measured this" and "a model wrote this" look identical. And a
promotion has to be modelled as two duplicate employers.

URS keeps a mapping to JSON Resume at conformance level 0, so adopting it costs nothing and is
reversible.

## Fitting a page budget without lying about it

`fit_pages.py` renders the document, measures which block spilled and how much room the page actually
had, then applies density levers in a fixed order — spacing, bullet spacing, margins, font size —
stopping at the 10pt and 0.5" floors instead of crossing them. If two pages are unreachable without a
breach it exits non-zero and says so, because the remedy then is to cut evidence, not to shrink type.

---

Next: [Quickstart](QUICKSTART.md) · [Concepts](CONCEPTS.md) · [Architecture](ARCHITECTURE.md)
