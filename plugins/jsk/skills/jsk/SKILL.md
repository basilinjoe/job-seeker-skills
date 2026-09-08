---
name: jsk
description: >-
  Use when the user wants to write, rebuild, update or tailor a resume or CV; capture work history,
  projects or accomplishments; record something they shipped; prepare a job application or paste a
  job description; check whether a resume will survive applicant tracking systems (ATS); resolve
  gaps or missing metrics in their career records; says their resume is outdated or vague; describes
  their work in long unstructured messages; wants a periodic career review; or asks about a career
  knowledge base, brag document or resume framework.
license: MIT
---

# Job Seeker Skill

A career knowledge base in **one Markdown file** — `user-knowledgebase.md` — plus tooling to render
verified, ATS-safe resumes from it.

Interview someone **once**, then regenerate resumes, tailored variants, LinkedIn copy and interview
briefs forever without re-interviewing them.

**The knowledge base is the source of truth. A resume is one rendering of it.**

Rendering goes through JSON, always:

```
user-knowledgebase.md  ->  resume.json (URS)  ->  .tex -> .pdf   (the deliverable)
   you read it            you write it        \-> .txt          (paste-in boxes)
```

The PDF is the only rendered deliverable. `--ats-max` chooses which variant it holds — presentation
or ATS-maximal — rather than producing a second file.

**Never hand-author a `.tex`.** Build the URS record, validate it, render every format from it.
*Two hand-built documents stop agreeing the moment one is edited — silently, usually in the copy
that gets sent.* `references/urs-spec.md` has the format, `references/mode-resume.md` the procedure.

## One file, and what comes out of it

| Thing | Is | Written by |
|---|---|---|
| `user-knowledgebase.md` | the source of truth, hand-written Markdown | the person, and you |
| `applications/<stem>/posting.md` | the advertisement verbatim, plus its requirements | `jsk-tailor-analyst` |
| `applications/<stem>/gaps.md` | verdicts, shortfalls and the question queue, written to be read aloud | `jsk-tailor-analyst` |
| `applications/<stem>/resume.json` | the URS record: which evidence appears, in what order, and the prose retuned for this posting | `jsk-resume-author` |
| `applications/<stem>/*.pdf` | the deliverable | `jsk render` |

**The gaps close before the resume is written**: assess, ask the queue, write the answers into the
knowledge base, then write the record. `references/mode-tailor.md` has the procedure.

### Edit the file directly

**There is no write layer.** No command per noun, no transaction, no refusals — a write to one file
either happened or did not, which is the whole reason the file is one file. Use `Read`, `Edit` and
`Write` the way you would on any other document.

What the write commands used to enforce is now three habits and one gate:

- **Read the section before you write into it.** A section you have not read is one you are about to
  duplicate.
- **Grep a distinctive phrase before you add anything.** People re-tell the same work months apart
  in different words, and neither telling mentions the other. Two concepts for one project is the
  failure that costs most later: the ranking sees two weak projects where there was one strong one,
  and the bullets are split across both so neither reads as evidence.
- **Stamp what you inferred.** Nothing else can tell the difference afterwards.
- **`jsk validate` on the record**, before anything renders. That is where a structural mistake is
  still cheap.

`references/kb-spec.md` has the headings, the block shapes and the id conventions.

## Modes

Route on what the user asked for. If they passed an argument (`braindump`, `resume`, `tailor`,
`ship`, `refresh`, `gaps`, `setup`, `pipeline`), use it. Otherwise infer from their message.

| Mode | Trigger | Read |
|---|---|---|
| **setup** | no knowledge base exists, or "set this up" | `references/mode-setup.md` |
| **braindump** | telling you about their work; long unstructured messages | `references/mode-braindump.md` |
| **resume** | "build my resume", "is this ATS-safe" | `references/mode-resume.md` |
| **tailor** | pasted a job description or a URL; "customise for this role" | `references/mode-tailor.md` |
| **ship** | a record is finished and needs rendering, checking, freezing and logging | `references/mode-ship.md` |
| **refresh** | "update my knowledge base", quarterly review, got promoted | `references/mode-refresh.md` |
| **gaps** | "what's missing", "resume feels vague", verify before applying | `references/mode-gaps.md` |
| **pipeline** | "what do I chase", "where are my applications", weekly review | `references/mode-pipeline.md` |

Ambiguous? Ask which they want rather than guessing — the modes do genuinely different things.

## Always do this first

**Find the knowledge base.** Search the working directory and any connected folder for
`user-knowledgebase.md`. Read it — the whole thing. It is one file and it is meant to be read whole;
skimming it is how a project gets recorded twice.

`jsk doctor` reports the path it found, if you would rather ask than search.

**An older bundle?** A directory holding `projects/` and `resume-generation/` is the previous
format — a folder of linked concepts. There is no migration command, because the migration is
reading it and writing the new file. `references/mode-setup.md` has the procedure. **Offer it; never
run it unasked.** Keep the old directory until they confirm the new file is complete.

Sessions do not share state. Never assume a knowledge base exists because one was created before.

**None at all?** Switch to setup mode — unless they asked for something you can deliver anyway. If
someone wants a resume right now, build the resume, then offer to capture it. Setup should never
block the actual ask.

**Their own rules win.** If the knowledge base's folder holds `rules/*.md`, those take precedence
over `references/` here. These files are optional and hand-created — setup does not scaffold them,
so absent just means "use the defaults". When one does exist, somebody customised it deliberately
and their edits should stick.

## Shared references

Load as needed rather than upfront:

| File | Holds |
|---|---|
| `references/kb-spec.md` | **the format**: every heading, the block shapes, ids, provenance, and what `applications/` holds |
| `references/writing-rules.md` | X-Y-Z bullets, verb accuracy, phrases that damage seniority |
| `references/ats-rules.md` | hard rules, the two-variant strategy, keyword placement |
| `references/urs-spec.md` | the record you write, and the region profiles a view renders through |
| `references/view-format.md` | every key a view may carry, and the rule that it may carry no prose |
| `references/rationale.md` | why the rules are what they are — read it when you need to *explain* one |

## The `jsk` command

Everything this skill runs is one command, `jsk`, from the `jsk-resume` package. **Run
`jsk --version` before the first call in a session.** If the command is not found,
`python3 -m jsk` is the same entry point (`python` or `py -3` on Windows). If neither resolves, say
so and stop — nothing here can run, and guessing at a path fails quietly.

| Command | Does | Needs |
|---|---|---|
| `jsk doctor [--quick]` | what this machine can do, and what each gap disables; `--quick` skips the end-to-end render | — |
| `jsk new <path> --name "Their Name"` | writes an empty `user-knowledgebase.md` and `applications/` | — |
| `jsk validate <resume.json> [--strict] [--max-findings N]` | the record gate: coherent, evidenced, and shaped the way the renderer reads | — |
| `jsk render <resume.json> --out DIR --view ID [--pdf] [--ats-max] [--template N]` | one record to `.tex`/PDF plus `.txt` | TeX engine for the PDF |
| `jsk preview <resume.json> --out DIR` | the same record in every template, with page counts, so the look is chosen by looking | TeX engine, `pymupdf` |
| `jsk check <file> [--strict] [--only parse\|prose]` | both document gates on one file, or one of them — `--only parse` for the PDF and the `.txt`, `--only prose` for the `.tex` | `pymupdf` for a PDF |
| `jsk gates <out-dir> [--record R] [--pages N] [--json]` | the record, parse and prose gates in one process, each one's output verbatim; never the render gate | `pymupdf` for a PDF |
| `jsk fit <resume.tex> --target-pages 2` | fits the render to a page budget without breaching the floors | TeX engine, `pymupdf` |

`jsk --help` is the whole surface — read it rather than guessing at a flag.

**Nothing here reads `user-knowledgebase.md`.** That file is yours to read and edit; the toolchain
starts at the record you write from it. There is no compile step to run and no bundle to validate.

**`gates` is the mechanical gate invocations as one.** It prints each gate's output verbatim, treats
a missing input as `SKIPPED` **and** a failure, and never attempts the render gate, in `--json` no
less than in prose: a command that exited 0 having quietly skipped that one would be the most
dangerous thing here. `--record` defaults to `resume.json` beside the render, which is where the
skill writes it. `--pages N` reports the page count and never fails on it; `jsk fit` still owns that
verdict.

Exit codes are uniform: `0` passed, `1` failed, `2` called wrong. A TeX engine and `pymupdf` are
required, not optional: the PDF is the only rendered deliverable, so without them there is nothing
to send, nothing to check and nothing to measure. `jsk render --pdf` exits **non-zero** when no PDF
was produced, and the page count it prints is counted off that PDF rather than repeated back from
the view's budget — *because a page count nobody measured is a page count nobody knows.* Over budget
is named, not failed: `jsk fit` owns that verdict and is the command that can act on it. Everything
else runs on a bare Python.

The toolchain is the installed package, never a copy beside the knowledge base, so everyone gets the
current version. *A rule nobody checks stops being true.*

## Agents

Four parts of this work are read-heavy or mechanical and need nobody in the room. Delegate those and
keep the conversation for the judgment.

| Agent | Hand it | Get back |
|---|---|---|
| `jsk-verifier` | the rendered files, the page budget — when a gate has failed, or the render gate needs reading | every gate's verdict verbatim, and the section in which each defect is repaired |
| `jsk-kb-auditor` | the knowledge base path | what it is missing, and a prioritised queue with the questions written ready to ask |
| `jsk-tailor-analyst` | the posting file, the knowledge base path | the requirements written into the posting, the assessment, the ranking, the honest fit and the question queue |
| `jsk-resume-author` | the posting, the gaps, the knowledge base path | the URS record, every clause it authored quoted, and what it cut |

**They never interview.** Confirming an `inferred` claim, choosing between two close-ranked projects,
and telling someone where they fall short all stay here, with the person present.

`jsk-resume-author` is the one that writes prose, and everything it authors arrives marked
`inferred`. A view with `provenance_floor: confirmed` will not render it until the person has
confirmed each clause — so the rule is enforced by the record gate rather than by the agent's
restraint.

Their output does not reach the person, so **relay the evidence rather than summarising it.** A
checker's verdict line, shown, is evidence; your description of it is not.

Nothing depends on them. Where agents are unavailable, run the same procedure inline — the mode
files hold it either way.

## The verification gates

**Never hand over a resume you have not checked.** There are four gates, they answer different
questions, and **passing one says nothing about the others** — *a checker verifies that a document
parses, not that it is correct.*

| Gate | Question | How |
|---|---|---|
| **Record** | Is the record coherent, shaped right, and does every number trace to a metric? | `jsk validate resume.json`, before anything renders |
| **Parse** | Will an ATS read this without mangling it? | `jsk check` on the rendered `.pdf`, and `--strict` on the `.txt` (or on an ATS-maximal PDF) |
| **Prose** | Does it obey the writing rules? | `jsk check --only prose` on the `.tex` and on the plain text |
| **Render** | Does it *look* right, and is it *true*? | Convert to PDF and look at every page |

The first three run together as `jsk gates <out-dir>`. The fourth is a person opening the PDF, and
it asks two questions: **you can check it looks right; only they can confirm it is true.** Reading
the layout leaves it half open — hand the PDF back naming what you could not check, and call the
resume unverified until they have.

**The record gate matters more than it used to.** Nothing compiles the record now; you write it. A
key the renderer does not recognise is a section that renders as nothing, and the mistake is
invisible in the PDF precisely because the section is simply not there. `jsk validate` is the only
thing that sees it.

All gates must pass. Show the output — the person should see the evidence rather than take your word
for it. Fix and re-run; never explain away a failure.

`jsk-verifier` is for a gate that failed and a failure that needs tracing back to the section it
came from. A clean ship runs `jsk gates` and reads the output rather than spawning it — relaying
three checkers is work a command does more cheaply, while turning a `FAIL` line into a repair site
is work an agent does better. It has no way to edit a document, which is deliberate: a defect is
repaired in the knowledge base and re-rendered, never patched into the PDF.

**If no PDF renderer is available**, say so and mark the resume unverified rather than treating
passing the parse gate as sufficient. *An unverified resume the person knows about is fine; one they
think was checked is not.*

`references/rationale.md` holds the three real resumes that passed the parse gate and should not
have. Read it when someone asks why there are four gates.

## Provenance — the habit that makes this last

Every concept carries `status`:

- `confirmed` — they said it, or it is in a source document
- `inferred` — you wrote it while drafting; plausible but unverified
- `needs-verification` — a known gap

**Never let `inferred` content reach a resume without asking them to confirm it.** *The danger is
precisely that it reads well — plausible, well-written, and indefensible when an interviewer asks a
follow-up.*

**Write `status: confirmed` only for what they actually said.** A concept you reconstructed and
stamped `confirmed` has laundered your inference into a fact, and nothing downstream can tell —
`provenance_floor` is enforced against what the file says, not against who typed it. There is no
command defaulting this for you any more, which makes it entirely your habit: **when you change a
claim's substance, drop it back to `inferred`** and put a row in `## Open questions`.

**Never invent a credential**, or claim one is "in progress", unless they said so.

**Never hide text in a resume**, and never add a term the person cannot defend in an interview.
The parse rules keep a document readable; they are not a ranking to game. Hidden keywords, invisible
type and resume-score tools are out of scope — `references/ats-rules.md` has the boundary and the
reasoning.

## Working with people

Adapt to what they know. Some will not know what YAML or an ATS is — explain briefly in plain terms
and never make the framework their problem. Others will want the schema. Read the cues.

- **Let them ramble.** People recall work in unstructured bursts. Take the whole thing, then
  structure it. Interrupting to impose format loses material.
- **Push for numbers, then let go.** Ask twice. If they do not have one, write the bullet true
  without it and log the gap. Never leave a placeholder in a document they might send.
- **Say why, not just what.** "I downgraded this to co-designed because you said you supported the
  design" teaches them something and lets them correct you.
- **Flag what you inferred.** Every time.
- **Offer options with a recommendation** rather than one take-it-or-leave-it draft.
- **Tell them where they fall short**, especially when tailoring. Being flattered costs interviews.

Append a dated row to `## Log` after every session. When you find your own earlier mistake, record
the correction rather than editing silently — *a knowledge base that hides its errors cannot be
trusted.*

## Portability

Works in Claude Code and Cowork. Use ordinary file tools and paths; do not assume either
environment. In Cowork, save deliverables to the outputs folder and present them. In Claude Code,
write beside the knowledge base and tell them the path. Prefer the file living in a folder the
person controls — ideally version-controlled — so it outlives any single session.
