# Rationale

Why the rules in `SKILL.md` are what they are. **Load this when you need to explain a rule to
someone**, or when someone pushes back on one. You do not need it to follow the rules — `SKILL.md`
carries a compressed reason for each.

Every item here is a failure that actually happened.

## Why every document is rendered from JSON

Two hand-built documents have to agree about every date, bullet and number. They stop agreeing the
moment one is edited — silently, usually in the copy that gets sent. One record with several emitters
cannot drift, because no emitter decides what the document says.

`render_resume.py` resolves the record once — selection, ordering, provenance filtering, region
gating, ASCII folding, date formatting — and the three emitters translate that plan into markup
without deciding anything.

It is also what makes a resume answerable a year later. The record carries the provenance of every
claim and the view that selected it, so "what did this application claim, and where did that come
from" has an answer.

**How to say it to someone:** *"If I build the Word file and the PDF separately, they agree today and
disagree in a month. Building both from one record means they can't."*

## Why four gates and not one

**A checker verifies that a document parses, not that it is correct.** That sentence is the whole
reason there are four.

`check_ats.py` passed all three of these, correctly, because all three were outside its scope:

1. A resume whose bullets rendered as **tofu boxes** — the glyphs were valid, the font could not draw
   them. Visual. Cannot be linted out of the XML.
2. A resume whose headings **silently resolved to a theme font**. Also visual. Also invisible to a
   parser.
3. A resume written **in the third person**. Not a parsing defect at all — which is exactly why
   `check_prose.py` had to exist.

The first two are why the render gate exists: somebody has to look at the page. The third is why the
prose gate exists.

**How to say it to someone:** *"The ATS checker tells you a robot can read it. It can't tell you the
letters showed up, or that it reads like someone else wrote it about you."*

## Why a missing renderer means "unverified" rather than "fine"

A page count nobody measured is a page count nobody knows. If no TeX engine is present, no one has
looked at a rendered page, so the render gate did not run — it did not pass.

An unverified resume the person knows about is fine. One they think was checked is not. That is the
entire distinction, and it is worth being pedantic about.

## Why tailoring is selection and never invention

A tailored resume is a *view*: it references evidence by id, orders it, and redacts. The validator
rejects free text inside a view.

The consequence is structural rather than disciplinary. A posting the record has no evidence for
produces *nothing to point at* — not a plausible new bullet. The system cannot invent even if asked,
which is a stronger guarantee than an instruction not to.

**How to say it to someone:** *"Tailoring reorders and hides. If the job wants something you haven't
done, it shows up as a gap, not as a sentence."*

## Why every numeral must trace to a metric

Every numeral in a bullet must appear in a structured metric on that bullet, or `validate_urs.py`
fails the record before anything renders.

It catches the specific failure of a bullet being rewritten for flow and the figure quietly moving
with it — 30% becoming 40% because the sentence scanned better.

## Why two variants

Readability and machine-parsing genuinely conflict. A layout that reads well for a human uses the
constructs that make parsers drop content; a layout that parses perfectly looks flat.

One document cannot be optimal for both readers. Pretending otherwise means quietly losing one of
them, and you do not find out which.

## Why provenance is tracked on every claim

You will often write better prose than the person spoke. That is useful. But reasoning you supplied
is yours until they agree with it.

The danger is precisely that it reads well — plausible, well-written, and indefensible when an
interviewer asks a follow-up. `inferred` is not a filing detail; it is the flag that stops a
well-written sentence from becoming an ambush in an interview.

## Why a new schema rather than JSON Resume

JSON Resume is a JSON container around unstructured prose:

- A bullet is a bare string, so **nothing can verify a metric**.
- Nothing carries an id, so **tailoring means copy-and-mutate**, and the copies drift.
- Nothing carries provenance, so **"I measured this" and "a model wrote this" look identical**.
- A promotion has to be modelled as **two duplicate employers**.

URS keeps a mapping to JSON Resume at conformance level 0, so adopting it costs nothing and is
reversible.

## Why `fit_pages.py` refuses rather than shrinking further

It applies density levers in a fixed order — spacing, bullet spacing, margins, font size — and stops
at the 10pt and 0.5" floors.

Below those floors a document is not two pages, it is two pages nobody will read. When the target is
unreachable without a breach, the remedy is to cut evidence. That is a decision for the person whose
evidence it is, so the script exits non-zero and says so instead of making it for them.

## Why a bundle never carries copies of the scripts

The scripts stay with the skill, so every bundle gets the current version. A bundle carrying its own
copies gets the version that existed the day it was created, and a rule nobody checks stops being
true.

## Why the log records corrections rather than editing silently

A knowledge base that hides its errors cannot be trusted. If a claim was downgraded, the downgrade is
the useful information — it tells the person what they can and cannot say in an interview, and it
tells the next session not to re-derive the same mistake.
