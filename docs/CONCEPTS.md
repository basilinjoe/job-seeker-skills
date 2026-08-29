# Concepts

Everything Job Seeker Skill asks you to know, on one screen. You do not need this to use the plugin — setup
explains what it needs as it goes. Read it when a word turns up and you want it pinned down.

## The record

**Bundle** — your career folder. Plain Markdown files with a bit of structured metadata at the top of
each. One file per project, per role, per achievement.
*Why it matters:* it is the source of truth. A resume is one rendering of it, not the original.

**OKF (Open Knowledge Format)** — the convention the bundle follows: linked Markdown files with YAML
frontmatter.
*Why it matters:* nothing proprietary. Any editor opens it, Git versions it, other AI tools read it.

**Provenance status** — every claim carries one: `confirmed` (you said it), `inferred` (drafted for
you, not yet signed off), `needs-verification` (a known gap).
*Why it matters:* inferred text is the dangerous kind. It reads well, which is exactly why it must
never reach a resume before you agree with it.

## The rendering

**URS (Universal Résumé Schema)** — the JSON your bundle compiles to before any document exists.
*Why it matters:* every output format is emitted from this one file, so the PDF and the Word document
cannot say different things about a date or a number.

**View** — a tailored resume, expressed as a selection: it references evidence by id, orders it, and
hides the rest.
*Why it matters:* the validator rejects free text inside a view. Tailoring can therefore emphasise,
but it structurally cannot invent.

**Record** — `resume-generation/record.json`, the standing URS transcription of the whole bundle.
*Why it matters:* the ranking, the gap analysis and the author all read it. When each read something
different, two of them could disagree about what your record held and nothing would have said so.

**UJD (Universal Job Description)** — the posting, as JSON. Every requirement carries whether it was
*required* or merely *preferred*, what the advertisement actually said, and the sentence it was read
from.
*Why it matters:* a flat list of keywords cannot say "a degree **and** six years, **or** a
postgraduate qualification". Flattened one way it scores a master's holder as unqualified; flattened
the other, a bare degree passes. Both are wrong, so the boolean structure is modelled.

**UGS (Universal Gap Schema)** — the join between a posting and your record: one verdict per
requirement, the evidence behind it, and how far short it falls on a *named* axis.
*Why it matters:* it distinguishes "you don't have it" from "you have it and never wrote it down"
from "you claimed it with nothing behind it". Those need opposite responses, and only the last one
ends an interview badly.

**Region profile** — a JSON file deciding what a given market may and must not show. Australia, India
and the UAE ship; the default forbids everything region-specific.
*Why it matters:* a photograph and date of birth are conventional on a Gulf resume and a liability on
an Australian one. Adding a market is a JSON file, not a schema change.

**Variant** — you get two resumes, because readability and machine-parsing genuinely conflict. A
*presentation* variant for humans, an *ATS-maximal* variant for job portals, plus plain text.
*Why it matters:* sending the pretty one into a portal is how good candidates vanish.

## The checking

**ATS (Applicant Tracking System)** — the software that reads your resume before a person does.

**Gate** — a check that must pass before a resume is handed over. There are four, and each answers a
different question:

| Gate | Asks |
|---|---|
| Record | Is the source coherent, and does every number trace to a real metric? |
| Parse | Will an ATS read this without mangling it? |
| Prose | Does the writing obey the rules? |
| Render | Does it *look* right, and is it *true*? |

*Why it matters:* passing one says nothing about the others. A checker verifies that a document
parses, not that it is correct — see [WHY.md](WHY.md) for the three real resumes that prove it.

**Unverified** — what a resume is called when no PDF renderer was available, so nobody has looked at
a rendered page.
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

Next: [Quickstart](QUICKSTART.md) · [Why it works this way](WHY.md) · [Scripts](SCRIPTS.md)
