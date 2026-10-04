# Concepts

Everything Job Seeker Skill asks you to know, on one screen. You do not need this to use the plugin — setup
explains what it needs as it goes. Read it when a word turns up and you want it pinned down.

## The record

**Knowledge base** — the career, the `kb` graph of the record. It holds your whole career in fixed
sections: identity, positioning, work authorization and languages, vocabulary, organisations,
roles, projects, metrics, skills, education, certifications, open source and open questions. Every
entry has an id - `prj_payments`, `ach_payments_cut_settlement_latency`, `met_settlement` - and
every link between entries is by id. `career_view` prints it as Markdown to read end to end.
*Why it matters:* it is the source of truth. A resume is one rendering of it, not the original.

**The store** — `career/store/`, where the record lives: the career, its log and each
application's graphs, as named graphs in one Oxigraph (RocksDB) store, read and written only
through `jsk`. It is not a text file: there is nothing to open in an editor, no hand edit, and no
git history of the record. `jsk kb dump` writes all of it out as TriG, and every write refreshes a
copy in `.jsk/backup.trig`.
*Why it matters:* every write lands whole - every graph it touches, or none - and goes through one
gate, so nothing can change the career without being validated and logged.

**Turtle** — the text format a changeset is written in, and the one `career_show` prints entries
in: `k:prj_payments j:name "Payments platform" ;`. Any graph library parses it.
*Why it matters:* unlike Markdown, a program can check it - and a dump in it outlives any single
tool, including this one.

**Validated on load** — every `jsk` command that reads the career checks all of it first: every
id resolves, every bullet's metric exists, every date parses. A finding names the graph and the
entry's id.
*Why it matters:* a broken link is found the next time anything runs, not when a resume fails.

**Changeset** — how the career is changed: a small TriG file you write (say
`changes/2026-09-08-payments.trig`) saying what to add, set, retire or delete, handed to `jsk kb
apply`. It is validated, merged, written to the store and logged, with the diff printed. Two
writes at once queue: the second waits its turn, and applies unless the first changed something it
names.
*Why it matters:* every change is visible, reviewable and in the log - and a changeset cannot
confirm anything on your behalf.

**Log** — the `log` graph: one entry per change, numbered (`r1`, `r2`, ...), with its day, the
command, its summary and the ids it touched. `career_log` prints it. It is written in the same
update as the change it records, so the two cannot disagree.

**Provenance status** — every claim carries one: `confirmed` (you said it), `inferred` (drafted for
you, not yet signed off), `needs-verification` (a known gap), `disputed`. Changing a claim drops it
to `inferred` and opens a question; `career_confirm` is the only way back up,
and it keeps your answer.
*Why it matters:* inferred text is the dangerous kind. It reads well, which is exactly why it must
never reach a resume before you agree with it.

**Vocabulary** — the concepts the career and postings are matched on: capabilities, domains,
technologies. `jsk` ships the technologies; your career adds your own terms and how they relate -
`c:kafka` *is a* `c:event-driven-architecture`, `c:aged-care` is *part of* `c:healthcare`.
Matching follows those edges one way, at most two hops. Capability edges are judgement, so none
ship in the vocabulary: `jsk kb pack capabilities` drafts a starter set as a changeset you read and
apply, and then it is yours. A tailoring answer that names a concept becomes one of its labels, so
the next posting is not asked again.
*Why it matters:* Kubernetes experience counts toward "container orchestration"; a mention of
container orchestration is not Kubernetes experience. A model fitting a posting blurs that; the
edges do not.

**Metric version** — a number, with where it came from and when it was true. `met_settlement.v1`
says 200 ms; a later measurement becomes `v2` rather than overwriting it.
*Why it matters:* an application that sent the old number still says what it sent, and
`career_query("stale")` names every application that sent a number since revised.

**Application** — one submission, named by its stem, `<yyyy-mm-dd>-<company>-<role>`. Since 5.0.0
it lives in the store as graphs: the advert as numbered lines and what it asks for (`posting`), the
analyst's review (`review`), the assessment (`gaps`), the bullets chosen (`resume`), and once sent,
`application` - what was sent, the bullets that rendered and the metric versions they cite, and a
timeline of what came back. Its directory, `applications/<stem>/`, holds only the files actually
sent: the PDF and the `.tex`. One made from files before 6.0 (`posting.md`, `decisions.txt`,
`gaps.txt`, `resume.json`) stays readable if it was frozen (sent or held back), and is named for
jsk 5.1.0 or `jsk app drop` if not.
*Why it matters:* it is frozen once the application goes out — `app_freeze` refuses until the gates
pass, records the application and names the directory after the day it was sent; after that
`app_event` adds what happened next, and nothing is edited. The career keeps moving, and an
application that pointed at a moving source could not answer what it was answering.

## The rendering

**Selection** — one resume's choices: the bullets chosen, by id, in order, and settings - format,
region, page budgets, the provenance floor, and the prose, a summary and a headline. It is a graph in
the store (`resume_select` makes it from the match, `resume_update` changes it), with the keys a
`resume.json` file held until 6.0. Names, dates, bullet text and
metrics are read from the career every time it is built, so a bullet confirmed or corrected in the
career is in the next render with nothing to update here.
*Why it matters:* a selection that holds no bullet's words cannot invent one. Tailoring can
emphasise, but a posting the career has no evidence for produces nothing to point at. And every
output is built from the same career, so the PDF and the text the checks read cannot say
different things about a date or a number.

**Posting** — the advertisement verbatim, stored as numbered lines, and its requirements in the
posting graph, each pointing at its line.
Each carries whether it was *required* or merely *preferred*, the term the advertisement actually
used, and a quote of the words it was read from - checked, verbatim, against the advert.
*Why it matters:* a flat list of keywords cannot say "a degree **and** six years, **or** a
postgraduate qualification". Flattened one way it scores a master's holder as unqualified; flattened
the other, a bare degree passes. Both are wrong, so the boolean structure is modelled.

**Assessment** — the join between a posting and your record, written to be read aloud: one verdict per
requirement, the evidence behind it, and how far short it falls on a *named* axis. The match
(`assessment_derive`) computes the join - which project holds each requirement, through which vocabulary edge - and the
assessment is derived from it: the gaps graph, written by code, with the analyst's review holding
only what the join cannot know - a verdict lowered, and why. A "no" you have confirmed ("never used
Kafka") answers a requirement by itself, with no question, for a year (an **absence**).
*Why it matters:* it distinguishes "you don't have it" from "you have it and never wrote it down"
from "you claimed it with nothing behind it". Those need opposite responses, and only the last one
ends an interview badly.

**Region profile** — a JSON file holding a market's conventions: paper size, page budget, the
sections in order, whether a declaration or a work-rights line is rendered. Australia, India and the
UAE ship, and a default.
*Why it matters:* India expects three pages and a declaration; Australia and the Gulf ask whether you
may work there. Adding a market is a JSON file, not a schema change.

**Variant** — the PDF comes in two variants, because readability and machine-parsing genuinely
conflict: *presentation* for humans, *ATS-maximal* for job portals. Each render produces one of them
as the PDF; `--ats-max` picks the second. The gates also read the plan's plain text, in memory.
*Why it matters:* sending the pretty one into a portal is how good candidates vanish.

## The checking

**ATS (Applicant Tracking System)** — the software that reads your resume before a person does.

**Gate** — a check that must pass before a resume is handed over. There are four, and each answers a
different question:

| Gate | Asks |
|---|---|
| Record | Does the selection name only live career entries, and does every number in a chosen bullet trace to a current metric? (`jsk resume check <stem>`) |
| Parse | Will an ATS read this without mangling it? |
| Prose | Does the writing obey the rules? |
| Render | Does it *look* right, and is it *true*? |

*Why it matters:* passing one says nothing about the others. A checker verifies that a document
parses, not that it is correct — see [WHY.md](WHY.md) for the three real resumes that prove it.
`jsk resume ship` runs the first three in one pass; the render gate is always a person reading the PDF.

**Record gate** — `jsk resume check` on a target, over its selection and the career bullets it selects: the
selection's shape; an id the career does not hold, has retired, or a bullet whose project has no role; a number
no current version of a metric the bullet cites holds; a career that does not validate; and a
career out of sync with its log - written outside jsk, restored from `.jsk/backup.trig`. It runs
first inside `jsk resume check` on a directory, `jsk resume ship` and `app_freeze`.

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

Next: [Quickstart](QUICKSTART.md) · [Why it works this way](WHY.md) · [Commands](SCRIPTS.md) · [The ontology in full](ONTOLOGY.md)
