---
name: jsk
description: >-
  Use when the user wants to write, rebuild, update or tailor a resume or CV; capture work history,
  projects or accomplishments; record something they shipped; prepare a job application or paste a
  job description; check whether a resume will survive applicant tracking systems (ATS); resolve
  gaps or missing metrics in their career records; says their resume is outdated or vague; describes
  their work in long unstructured messages; wants a periodic career review; or asks about a career
  bundle, OKF, brag document or resume framework.
license: MIT
---

# Job Seeker Skill

A career knowledge base as a folder of linked Markdown files with YAML frontmatter — the
**Open Knowledge Format** — plus tooling to render verified, ATS-safe resumes from it.

Interview someone **once**, then regenerate resumes, tailored variants, LinkedIn copy and interview
briefs forever without re-interviewing them.

**The bundle is the source of truth. A resume is one rendering of it.**

Rendering goes through JSON, always:

```
bundle (Markdown)  ->  resume.json (URS)  ->  .tex -> .pdf   (the deliverable)
                                          \-> .txt          (paste-in boxes)
```

The PDF is the only rendered deliverable. `--ats-max` chooses which variant it holds - presentation
or ATS-maximal - rather than producing a second file.

**Never hand-author a `.tex`.** Build the URS record, validate it, render every format
from it. *Two hand-built documents stop agreeing the moment one is edited — silently, usually in the
copy that gets sent.* `references/urs-spec.md` has the format, `references/mode-resume.md` the
procedure.

## One source, and what compiles from it

**The bundle is the only thing anyone edits.** Everything a tool reads is built from it:

| Thing | Is | Made by |
|---|---|---|
| the bundle — `projects/`, `roles/`, `achievements/`, … | the source of truth, hand-written Markdown | the person |
| the record | the bundle as URS, in memory, in under a second | `okf compile` |
| `<slug>.posting.md` | the advertisement verbatim, plus its requirements in frontmatter | `jsk-tailor-analyst` |
| `<slug>.gaps.md` | verdicts, shortfalls and the question queue, written to be read aloud | `jsk-tailor-analyst` |
| `<slug>.view.md` | which evidence appears, in what order, and the prose retuned for this posting | `jsk-resume-author` |

The record is **compiled, never transcribed**. Every field in it is a frontmatter key or a table
cell, so a model reading them across adds no judgement — and a transcription that can drift is what
checksums, conformance levels and a reconcile pass all used to police.

**The gaps close before the resume is written**: assess, ask the queue, write the answers into the
concepts, recompile. Only then does `jsk-resume-author` write the view, once.
`references/mode-tailor.md` has the procedure.

### Never `Write` or `Edit` a file inside a bundle

**Every change you make to a bundle is an `okf` command** — the list under *Scripts* below, and
`references/write-commands.md` for the rules. A bundle write is a several-file transaction; written
by hand, four of the five files were checked by nothing, so *a half-finished write could go green*.

**If a change cannot be expressed as a command, report that and stop** — a blocked write is a
missing verb worth reporting, and a hand-edit is a bundle nobody can trust.

This binds you, never the person: a hand-edited concept is a valid concept.

## Modes

Route on what the user asked for. If they passed an argument (`braindump`, `resume`, `tailor`,
`ship`, `refresh`, `gaps`, `setup`, `pipeline`), use it. Otherwise infer from their message.

| Mode | Trigger | Read |
|---|---|---|
| **setup** | no bundle exists, or "set this up" | `references/mode-setup.md` |
| **braindump** | telling you about their work; long unstructured messages | `references/mode-braindump.md` |
| **resume** | "build my resume", "is this ATS-safe" | `references/mode-resume.md` |
| **tailor** | pasted a job description or a URL; "customise for this role" | `references/mode-tailor.md` |
| **ship** | a record is finished and needs rendering, checking, freezing and logging | `references/mode-ship.md` |
| **refresh** | "update my bundle", quarterly review, got promoted | `references/mode-refresh.md` |
| **gaps** | "what's missing", "resume feels vague", verify before applying | `references/mode-gaps.md` |
| **pipeline** | "what do I chase", "where are my applications", weekly review | `references/mode-pipeline.md` |

Ambiguous? Ask which they want rather than guessing — the modes do genuinely different things.

## Always do this first

**Find the bundle.** Search the working directory and any connected folder for a directory
containing both `projects/` and `resume-generation/`, or matching `*-okf`, or a zip with `okf` in
the name. Read its `index.md` then `log.md` — they orient you.

**Check its revision.** `index.md` carries `okf_bundle:`. Absent, or below the current
revision, means the bundle predates the current layout:

```bash
okf migrate <bundle>
```

Report mode writes nothing. Say what it found and **offer** the `--apply` run — never migrate
unasked, because it writes into their record. An older bundle still works, so this is a suggestion
and never a blocker. Where the migration says something needs a person, that goes on the list for
gaps mode rather than being filled in for them.

Sessions do not share state. Never assume a bundle exists because one was created before.

**No bundle?** Switch to setup mode — unless they asked for something you can deliver anyway. If
someone wants a resume right now, build the resume, then offer to capture it as a bundle. Setup
should never block the actual ask.

**A bundle's own rules win.** If `resume-generation/*.md` exists in their bundle, it takes precedence
over `references/` here. These files are optional and hand-created — setup does not scaffold them, so
absent just means "use the defaults". When one does exist, somebody customised it deliberately and
their edits should stick.

## Shared references

Load as needed rather than upfront:

| File | Holds |
|---|---|
| `references/bundle-spec.md` | directory layout, frontmatter schema, selection keys, concept types |
| `references/writing-rules.md` | X-Y-Z bullets, verb accuracy, phrases that damage seniority |
| `references/ats-rules.md` | hard rules, the two-variant strategy, keyword placement |
| `references/urs-spec.md` | the shape the record compiles to, and the region profiles a view renders through |
| `references/view-format.md` | the other half of that spec: every key a view may carry, and the rule that it may carry no prose |
| `references/write-commands.md` | **the only way to change a bundle**: every noun and verb, the files one write implies, the refusals, and where the commands stop |
| `references/rationale.md` | why the rules are what they are — read it when you need to *explain* one |

## The `okf` command

Everything this skill runs is one command, `okf`, from the `jsk-okf` package. There is no longer
a path to get right. **Run `okf --version` before the first call in a session.** If the command is
not found, `python3 -m jsk_okf` is the same entry point (`python` or `py -3` on Windows). If neither
resolves, say so and stop — nothing here can run, and guessing at a path fails quietly.

| Command | Does | Needs |
|---|---|---|
| `okf doctor [--quick]` | what this machine can do, and what each gap disables; `--quick` skips the end-to-end render | — |
| `okf new <path> --name "Their Name"` | creates an empty bundle skeleton | — |
| `okf <noun> <verb> --bundle DIR [...]` | **every change to a bundle** — the nouns listed below | `pyyaml` to read back |
| `okf validate <bundle> [--scope SUBDIR] [--exclude-archive] [--max-findings N]` | bundle is well-formed | `pyyaml` |
| `okf validate <resume.json> [--strict] [--level N] [--max-findings N]` | the record is coherent, carries evidence, and lost nothing in compilation, before anything renders | — |
| `okf migrate <bundle> [--apply]` | brings an older bundle up to the current layout; reports what it cannot establish rather than guessing | — |
| `okf pipeline <bundle> [--all] [--company N] [--as-of D] [--top N] [--json]` | what the job search needs from you this week, derived from the application timelines | `pyyaml` |
| `okf check <file> [--strict] [--only parse\|prose]` | both document gates on one file, or one of them — `--only parse` for the PDF and the `.txt`, `--only prose` for the `.tex` | `pymupdf` for a PDF |
| `okf compile <bundle> [--view ID] [--no-views] [--compact] [--for score]` | the bundle as the record everything downstream reads — the concepts only, never the frozen archive | — |
| `okf gates <out-dir> --view ID [--bundle DIR] [--pages N] [--json]` | the record, parse and prose gates in one process, each one's output verbatim; never the render gate | `pyyaml`, `pymupdf` for a PDF |
| `okf score <bundle> <posting.md>` | ranks the projects against the posting's requirements | — |
| `okf render <bundle \| resume.json> --out DIR --view ID [--pdf] [--ats-max] [--template N]` | one record to `.tex`/PDF plus `.txt`; `--view` is required wherever the record holds more than one | TeX engine for the PDF |
| `okf preview <resume.json> --out DIR` | the same record in every template, with page counts, so the look is chosen by looking | TeX engine, `pymupdf` for thumbnails |
| `okf fit <resume.tex> --target-pages 2` | fits the render to a page budget without breaching the floors | TeX engine, `pymupdf` |

`okf --help` is the whole surface — read it rather than guessing at a flag.

### The write commands

Each takes `--bundle DIR`, `--dry-run`, `--json`, `--set key=value`. `okf <noun>` lists its verbs;
`references/write-commands.md` has the rules.

- `okf project` · `okf role` · `okf org` · `okf education` — `add|set|retire|rm`
- `okf bullet` · `okf skill` · `okf credential` — `add|set|rm|mv` — the claims inside a concept
- `okf metric add|set` · `okf capability add` · `okf question add|resolve` · `okf log` · `okf reindex`
- `okf posting add` · `okf posting requirement add` · `okf gaps write` · `okf view create|set|include`
- `okf application file` · `okf application event`

- **`retire` keeps the concept** and stops the compile emitting it; **`rm` deletes** and refuses
  while anything still references it.
- **Ids are written down.** A claim mutation first materialises the ids the compile derived from
  position, so a view naming one cannot be repointed by a later insertion.
- **A refusal names its cause and ends in `fix:`.** Read it rather than retrying.

**`compile` narrows what it emits, never what it reads.** `--compact` drops the indentation;
`--for score` emits projects with only the keys a ranking runs on. Together they take an agent's
record read from 32,190 bytes to 12,840 — but `--for score` drops the achievement prose with them,
so it belongs to a caller that ranks projects and never to one that writes bullets.

**`gates` is the five mechanical gate invocations as one**, at about 0.6x the wall clock — four
interpreter starts saved — calling the same checkers with the same arguments. It prints each gate's
output verbatim, treats a missing input as `SKIPPED` **and** a failure, and never attempts the render
gate, in `--json` no less than in prose: a command that exited 0 having quietly skipped that one
would be the most dangerous thing here. `--pages N` reports the page count and never fails on it;
`okf fit` still owns that verdict.

Exit codes are uniform: `0` passed, `1` failed, `2` called wrong. A TeX engine and `pymupdf` are
required, not optional: the PDF is the only rendered deliverable, so without them there is nothing to
send, nothing to check and nothing to measure. `okf render --pdf` exits **non-zero** when no PDF
was produced, and the page count it prints is counted off that PDF rather than repeated back from the
view's budget — *because a page count nobody measured is a page count nobody knows.* Over budget is
named, not failed: `okf fit` owns that verdict and is the command that can act on it. Everything
else runs on a bare Python.

The scripts stay with the skill and a bundle never carries copies, so every bundle gets the current
version. If they are genuinely missing — the skill was installed as `SKILL.md` alone — write them
into the bundle's `framework/` from the specifications in `references/ats-rules.md` and
`references/bundle-spec.md`. *A rule nobody checks stops being true.*

## Agents

Four parts of this work are read-heavy or mechanical and need nobody in the room. Delegate those and
keep the conversation for the judgment.

| Agent | Hand it | Get back |
|---|---|---|
| `jsk-verifier` | the rendered files, the view id, the page budget — when a gate has failed, or the render gate needs reading | every gate's verdict verbatim, and the concept in which each defect is repaired |
| `jsk-bundle-auditor` | the bundle path | what the bundle is missing, and a prioritised queue with the questions written ready to ask |
| `jsk-tailor-analyst` | the posting file, the bundle path | the requirements written into the posting, the assessment, the ranking, the honest fit and the question queue |
| `jsk-resume-author` | the posting, the gaps, the bundle path | the view, every clause it authored quoted, and what it cut |

**They never interview.** Confirming an `inferred` claim, choosing between two close-ranked projects,
and telling someone where they fall short all stay here, with the person present.

`jsk-resume-author` is the one that writes prose, and everything it authors arrives marked `inferred`.
A view with `provenance_floor: confirmed` will not render it until the person has confirmed each
clause — so the rule is enforced by the record gate rather than by the agent's restraint.

Their output does not reach the person, so **relay the evidence rather than summarising it.** A
checker's verdict line, shown, is evidence; your description of it is not.

Nothing depends on them. Where agents are unavailable, run the same procedure inline — the mode files
hold it either way.

## The verification gates

**Never hand over a resume you have not checked.** There are four gates, they answer different
questions, and **passing one says nothing about the others** — *a checker verifies that a document
parses, not that it is correct.*

| Gate | Question | How |
|---|---|---|
| **Record** | Is the source coherent, and does every number trace to a metric? | `okf validate resume.json`, before anything renders |
| **Parse** | Will an ATS read this without mangling it? | `okf check` on the rendered `.pdf`, and `--strict` on the `.txt` (or on an ATS-maximal PDF) |
| **Prose** | Does it obey the writing rules? | `okf check --only prose` on the `.tex` and on the plain text |
| **Render** | Does it *look* right, and is it *true*? | Convert to PDF and look at every page |

The first three run together as `okf gates <out-dir> --view ID`. The fourth is a person opening
the PDF, and no command claims it.

All gates must pass. Show the output — the person should see the evidence rather than take your word
for it. Fix and re-run; never explain away a failure.

`jsk-verifier` is for a gate that failed and a failure that needs tracing back to the concept it came
from. A clean ship runs `okf gates` and reads the output rather than spawning it — relaying three
checkers is work a command does more cheaply, while turning a `FAIL` line into a repair site is work
an agent does better. It has no way to edit a document, which is deliberate: a defect is repaired in
the concept and re-rendered, never patched into the PDF.

**If no PDF renderer is available**, say so and mark the resume unverified rather than treating a
passing the parse gate as sufficient. *An unverified resume the person knows about is fine; one they
think was checked is not.*

Run `okf validate <bundle>` after any change to the bundle.

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

**`add` defaults to `--status confirmed`; `set` re-stamps `inferred`.** Pass `--status inferred` on
an `add` for anything you reconstructed rather than heard: a concept you wrote and stamped
`confirmed` has laundered your inference into a fact, and nothing downstream can tell —
`provenance_floor` is enforced against what the frontmatter says, not against who typed it. The
`set` default is that rule from the other side, so confirmation is something you asked them for
rather than something a claim inherits by nobody touching that line.

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

Append a dated `log.md` entry after every session. When you find your own earlier mistake, record the
correction rather than editing silently — *a knowledge base that hides its errors cannot be trusted.*

## Portability

Works in Claude Code and Cowork. Use ordinary file tools and paths; do not assume either environment.
In Cowork, save deliverables to the outputs folder and present them. In Claude Code, write beside the
bundle and tell them the path. Prefer the bundle living in a folder the person controls — ideally
version-controlled — so it outlives any single session.
