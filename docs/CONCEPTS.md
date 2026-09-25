# Concepts

Everything Job Seeker Skill asks you to know, on one screen. You do not need this to use the plugin — setup
explains what it needs as it goes. Read it when a word turns up and you want it pinned down.

## The record

**Knowledge base** — `career/kb.ttl`, the graph record. One file holding your whole career in
fixed sections: identity, positioning, work authorization and languages, vocabulary,
organisations, roles, projects, metrics, skills, education, certifications, open source and open
questions. Every entry has an id - `prj_payments`, `ach_payments_cut_settlement_latency`,
`met_settlement` - and every link between entries is by id.
*Why it matters:* it is the source of truth. A resume is one rendering of it, not the original — and
it is laid out as one file you can read end to end and correct, which is what decides whether a
career record survives a year.

**Turtle** — the text format `kb.ttl` is written in: `k:prj_payments j:name "Payments platform" ;`.
No proprietary format anywhere. Any editor opens it, Git versions it, other AI tools read it, and
every graph library parses it.
*Why it matters:* it outlives any single tool, including this one - and, unlike Markdown, a
program can check it.

**Validated on load** — every `jsk` command that reads the career checks all of it first: every
id resolves, every bullet's metric exists, every date parses. A finding names the file and line.
*Why it matters:* a broken link is found the next time anything runs, not when a resume fails.

**Changeset** — how the career is changed: a small TriG file saying what to add, set, retire or
delete, handed to `jsk kb apply`. It is validated, merged, written in the one canonical layout,
and logged in `career/log.ttl`, with the diff printed. You can still edit `kb.ttl` by hand;
`jsk kb adopt` logs the edit.
*Why it matters:* every change is visible, reviewable and in the log - and a changeset cannot
confirm anything on your behalf.

**Log** — `career/log.ttl`: one entry per change, numbered (`r1`, `r2`, ...), each holding the
hash of the `kb.ttl` it wrote. A `kb.ttl` that no longer matches its last entry was edited by
hand, or a write was cut off halfway; either way the next load says so.

**Provenance status** — every claim carries one: `confirmed` (you said it), `inferred` (drafted for
you, not yet signed off), `needs-verification` (a known gap), `disputed`. Changing a claim drops it
to `inferred` and opens a question; `jsk kb confirm <id> --answer "..."` is the only way back up,
and it keeps your answer.
*Why it matters:* inferred text is the dangerous kind. It reads well, which is exactly why it must
never reach a resume before you agree with it.

**Vocabulary** — the concepts the career and postings are matched on: capabilities, domains,
technologies. `jsk` ships the technologies; your `kb.ttl` adds your own terms and how they relate -
`c:kafka` *is a* `c:event-driven-architecture`, `c:aged-care` is *part of* `c:healthcare`.
Matching follows those edges one way, at most two hops.
*Why it matters:* Kubernetes experience counts toward "container orchestration"; a mention of
container orchestration is not Kubernetes experience. A model fitting a posting blurs that; the
edges do not.

**Metric version** — a number, with where it came from and when it was true. `met_settlement.v1`
says 200 ms; a later measurement becomes `v2` rather than overwriting it.
*Why it matters:* an application that sent the old number still says what it sent, and
`jsk kb query stale` names every application that sent a number since revised.

**Application directory** — everything about one submission in one place:
`applications/<yyyy-mm-dd>-<company>-<role>/`, holding the advert (`posting.md`), what it asks for
(`posting.ttl`), the gap assessment, the record it rendered from, the files actually sent, and
`application.ttl`: what was sent, the bullets and metric versions it carried, and a timeline of what
came back.
*Why it matters:* it is frozen once the application goes out — `jsk freeze` refuses until the gates
pass, writes `application.ttl` and names the directory after the day it was sent; after that
`jsk event` adds what happened next, and nothing is edited. The career keeps moving, and an
application that pointed at a moving source could not answer what it was answering.

**Markdown knowledge base** — `user-knowledgebase.md`, what earlier versions kept the career in.
`jsk migrate` moves it to `career/kb.ttl` once, checking the round trip and deleting nothing. It
is available for this release only.

## The rendering

**URS (Universal Résumé Schema)** — the JSON written out of your knowledge base before any document
exists.
*Why it matters:* every output is emitted from this one record, so the PDF and the paste-in plain
text cannot say different things about a date or a number.

**View** — a tailored resume, expressed as a selection: it references evidence by id, orders it, and
hides the rest.
*Why it matters:* the validator rejects free text inside a view. Tailoring can therefore emphasise,
but it structurally cannot invent.

**Record** — `resume.json`, the URS document written for one application. The skill writes it out
of your knowledge base, using the same ids, which is why `jsk validate` checks its shape and its
numbers and the claims gate checks it against `kb.ttl` before anything renders.
*Why it matters:* every output is emitted from it, so the PDF and the paste-in plain text cannot say
different things. And a key the renderer does not recognise is a section that renders as nothing —
invisible in the PDF, and only the record gate sees it.

**Posting** — the advertisement verbatim in `posting.md`, and its requirements in `posting.ttl`.
Each carries whether it was *required* or merely *preferred*, the term the advertisement actually
used, and a quote of the words it was read from - checked, verbatim, against the advert.
*Why it matters:* a flat list of keywords cannot say "a degree **and** six years, **or** a
postgraduate qualification". Flattened one way it scores a master's holder as unqualified; flattened
the other, a bare degree passes. Both are wrong, so the boolean structure is modelled.

**Assessment** — the join between a posting and your record, written to be read aloud: one verdict per
requirement, the evidence behind it, and how far short it falls on a *named* axis. `jsk match`
computes the join - which project holds each requirement, through which vocabulary edge - and the
assessment in `gaps.md` is written from it.
*Why it matters:* it distinguishes "you don't have it" from "you have it and never wrote it down"
from "you claimed it with nothing behind it". Those need opposite responses, and only the last one
ends an interview badly.

**Region profile** — a JSON file deciding what a given market may and must not show. Australia, India
and the UAE ship; the default forbids everything region-specific.
*Why it matters:* a photograph and date of birth are conventional on a Gulf resume and a liability on
an Australian one. Adding a market is a JSON file, not a schema change.

**Variant** — the PDF comes in two variants, because readability and machine-parsing genuinely
conflict: *presentation* for humans, *ATS-maximal* for job portals. Each render produces one of them
as the PDF, plus plain text; `--ats-max` picks the second.
*Why it matters:* sending the pretty one into a portal is how good candidates vanish.

## The checking

**ATS (Applicant Tracking System)** — the software that reads your resume before a person does.

**Gate** — a check that must pass before a resume is handed over. There are four, and each answers a
different question:

| Gate | Asks |
|---|---|
| Record | Is the source coherent, does every number trace to a real metric, and does every claim trace to your career? (`jsk validate`, then the claims gate) |
| Parse | Will an ATS read this without mangling it? |
| Prose | Does the writing obey the rules? |
| Render | Does it *look* right, and is it *true*? |

*Why it matters:* passing one says nothing about the others. A checker verifies that a document
parses, not that it is correct — see [WHY.md](WHY.md) for the three real resumes that prove it.
`jsk ship` runs the first three in one pass; the render gate is always a person reading the PDF.

**Claims gate** — the half of the record gate that reads the record against `career/kb.ttl`: a
bullet the career does not hold must be marked `inferred`; nothing may be more confirmed in the
record than in the career; every number must be in the current version of a metric the bullet
cites. It runs inside `jsk gates`, `jsk ship` and `jsk freeze`, and says `NOT RUN` where there is
no graph record yet.

**Unverified** — what a resume is called until somebody has read every rendered page, and what it
stays when no PDF renderer was available to produce one.
*Why it matters:* an unverified resume you know about is fine. One you think was checked is not.

## The modes

Eight things the skill can do. You do not have to pick — describe what you want and it routes.

| Mode | When |
|---|---|
| `setup` | First run, or importing an existing resume |
| `braindump` | You have something to say about your work |
| `resume` | You need a resume |
| `tailor` | You have a specific job posting — a loop that closes the gaps, then writes the resume |
| `ship` | A resume is finished and needs rendering, checking and filing |
| `refresh` | Periodic top-up |
| `gaps` | Resolve unanswered questions and unverified claims |
| `pipeline` | Work the applications you have out: what is overdue, what to close |

---

Next: [Quickstart](QUICKSTART.md) · [Why it works this way](WHY.md) · [Commands](SCRIPTS.md)
