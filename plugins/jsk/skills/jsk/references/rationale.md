# Rationale

Why the rules in `SKILL.md` are what they are. **Load this when you need to explain a rule to
someone**, or when someone pushes back on one. You do not need it to follow the rules.

Every item here is a failure that actually happened.

## Why every document is rendered from the career

Two hand-built documents have to agree about every date, bullet and number. They stop agreeing the
moment one is edited — silently, usually in the copy that gets sent. One career with several emitters
cannot drift, because no emitter decides what the document says.

The builder reads `career/kb.ttl` and the short `resume.json` once — selection, ordering, provenance
filtering, region, ASCII folding, date formatting — into a plan, and the emitters translate that plan
into markup without deciding anything.

It is also what makes a resume answerable a year later. `jsk freeze` records the bullets that
rendered and the metric versions they cite, so "what did this application claim, and where did that
come from" has an answer.

**How to say it to someone:** *"If I build the PDF and the plain-text copy separately, they agree
today and disagree in a month. Building both from one career means they can't."*

## Why five gates and not one

**A checker verifies that a document parses, not that it is correct.**

The parse gate passed all three of these, correctly, because all three were outside its scope:

1. A resume whose bullets rendered as **tofu boxes** — the glyphs were valid, the font could not draw
   them. Visual.
2. A resume whose headings **silently resolved to a different font**. Also visual. Also invisible to
   a parser.
3. A resume written **in the third person**. Not a parsing defect at all.

The first two are why the render gate exists: somebody has to look at the page. The third is why the
prose gate exists. The record gate checks, before anything renders, that `resume.json` names only
live entries and that every number in a chosen bullet is a current metric's.

**How to say it to someone:** *"The ATS checker tells you a robot can read it. It can't tell you the
letters showed up, or that it reads like someone else wrote it about you."*

## Why a missing renderer means "unverified" rather than "fine"

A page count nobody measured is a page count nobody knows. If no TeX engine is present, no one has
looked at a rendered page, so the render gate did not run — it did not pass.

An unverified resume the person knows about is fine. One they think was checked is not.

So `jsk render --pdf` **exits non-zero** when no PDF came out, and `jsk doctor` reports a missing
engine as BLOCKED rather than a gap. A warning that does not change the exit code is a warning
nothing acts on.

## Why tailoring is selection and never invention

A tailored resume is a *selection*: `resume.json` names evidence by id and orders it. Its one piece
of prose is the summary; a bullet is in the career or nowhere, and the record gate fails an id the
career does not hold.

The consequence is structural rather than disciplinary. A posting the career has no evidence for
produces *nothing to point at* — not a plausible new bullet. The system cannot invent even if asked,
which is a stronger guarantee than an instruction not to.

**How to say it to someone:** *"Tailoring reorders and hides. If the job wants something you haven't
done, it shows up as a gap, not as a sentence."*

## Why every numeral must trace to a metric

Every numeral in a chosen bullet must appear in the current version of a metric it cites, or `jsk
validate` fails `resume.json` before anything renders.

It catches a bullet being rewritten for flow and the figure quietly moving with it — 30% becoming 40%
because the sentence scanned better.

## Why two variants, but only one file

Readability and machine-parsing conflict. A layout that reads well for a human uses the constructs
that make parsers drop content; a layout that parses perfectly looks flat. One document cannot be
optimal for both readers.

So there are two variants, but one rendered document: `--ats-max` chooses which one the PDF holds, at
the moment you know who is receiving it. Shipping several artefacts per application once meant the
fitter measured one file while another went out, and a resume reported as two pages shipped as
three. **A gate that measures a document nobody sends is not a gate.**

## Why we do not optimise for the ranker

The parse rules look like ATS optimisation and are not. They exist so a document arrives intact:
a table that fragments a bullet, a ligature that eats a word, a header that gets discarded with the
phone number in it. Every one of them is about **not losing content**.

Nothing here tries to raise a score. Hidden keyword blocks, invisible type and term-stuffing all fail
in the same way: they work on the machine and then the document reaches a person. Resume-score tools
fail differently — they score against a model of a parser rather than the parser the employer runs,
so the number moves for reasons unrelated to the work, and people rewrite good bullets to chase it.

**How to say it to someone:** *"A hidden keyword block is a lie told to a machine that a human then
reads back to you in the interview."*

## Why provenance is tracked on every claim

You will often write better prose than the person spoke. That is useful. But reasoning you supplied
is yours until they agree with it.

The danger is precisely that it reads well — plausible, well-written, and indefensible when an
interviewer asks a follow-up. `inferred` is the flag that stops a well-written sentence from becoming
an ambush in an interview.

## Why a new schema rather than JSON Resume

JSON Resume is a JSON container around unstructured prose:

- A bullet is a bare string, so **nothing can verify a metric**.
- Nothing carries an id, so **tailoring means copy-and-mutate**, and the copies drift.
- Nothing carries provenance, so **"I measured this" and "a model wrote this" look identical**.
- A promotion has to be modelled as **two duplicate employers**.

The career is a graph instead: a bullet carries an id and a provenance and cites a metric version,
and a promotion is two roles at one employer.

## Why `jsk fit` refuses rather than shrinking further

It applies density levers in a fixed order — spacing, bullet spacing, margins, font size — and stops
at the 10pt and 0.5" floors.

Below those floors a document is not two pages, it is two pages nobody will read. When the target is
unreachable without a breach, the remedy is to cut evidence. That is a decision for the person whose
evidence it is, so the command exits non-zero and says so instead of making it for them.

## Why the knowledge base never carries copies of the tooling

The toolchain stays with the skill, so everybody gets the current version. A career folder carrying
its own copy gets the version that existed the day it was created, and a rule nobody checks stops
being true.

## Why the log records corrections rather than editing silently

A knowledge base that hides its errors cannot be trusted. If a claim was downgraded, the downgrade is
the useful information — it tells the person what they can and cannot say in an interview, and it
tells the next session not to re-derive the same mistake.
