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

A career knowledge base in **one Markdown file**, `user-knowledgebase.md`, plus a toolchain that
renders verified, ATS-safe resumes from it. Interview someone once; regenerate resumes, tailored
variants and interview briefs from the file forever after.

**The knowledge base is the source of truth. A resume is one rendering of it.**

```
user-knowledgebase.md  ->  resume.json (URS)  ->  .tex -> .pdf   (the deliverable)
   you read and edit it     you write it        \-> .txt          (paste-in boxes)
```

**Never hand-author a `.tex`.** Write the URS record, validate it, render every format from it —
two hand-built documents stop agreeing the moment one is edited.

| Thing | Is | Written by |
|---|---|---|
| `user-knowledgebase.md` | the source of truth | the person, and you |
| `applications/<stem>/posting.md` | the advertisement verbatim, plus its requirements | `jsk-tailor-analyst` |
| `applications/<stem>/gaps.md` | verdicts, shortfalls and the question queue | `jsk-tailor-analyst` |
| `applications/<stem>/resume.json` | the URS record for this posting | `jsk-resume-author` |
| `applications/<stem>/application.md` | what was sent, and its timeline | `jsk freeze` |

`applications/` is the directory beside `user-knowledgebase.md` — resolve it to an absolute path,
never the working directory.

## Modes

Route on the argument if one was passed, otherwise on the message. Ambiguous? Ask — the modes do
different things.

| Mode | Trigger | Read |
|---|---|---|
| **setup** | no knowledge base, an older bundle, or "set this up" | `references/mode-setup.md` |
| **braindump** | telling you about their work; long unstructured messages | `references/mode-braindump.md` |
| **resume** | "build my resume", "is this ATS-safe" | `references/mode-resume.md` |
| **tailor** | a job description or URL; "customise for this role" | `references/mode-tailor.md` |
| **ship** | a finished record needs rendering, gating, freezing and logging | `references/mode-ship.md` |
| **refresh** | "update my knowledge base", quarterly review, got promoted | `references/mode-refresh.md` |
| **gaps** | "what's missing", "resume feels vague", verify before applying | `references/mode-gaps.md` |
| **pipeline** | "what do I chase", "where are my applications", weekly review | `references/mode-pipeline.md` |

## Every session, first

1. **Find the knowledge base** — search the working directory and connected folders for
   `user-knowledgebase.md`, or run `jsk doctor`. Sessions share no state; never assume one exists.
   Read it **whole**: skimming is how a project gets recorded twice.
2. **None?** Switch to setup — unless they asked for something deliverable anyway. Deliver it first,
   then offer to capture it. Setup never blocks the actual ask.
3. **A `projects/` + `resume-generation/` directory** is the old bundle format. Offer the migration in
   `references/mode-setup.md`; never run it unasked.
4. **`rules/*.md` beside the knowledge base** override `references/` here.
5. **Run `jsk --version`** before the first call. Not found → `python3 -m jsk` (`python` or `py -3`
   on Windows). Neither → say so and stop.

## Editing the knowledge base

There is no write layer: use `Read`, `Edit` and `Write` on the file. Three habits carry what a write
command would have enforced:

- **Read the section before writing into it.**
- **Grep a distinctive phrase before adding anything.** People re-tell the same work months apart in
  different words; two entries for one project split its evidence so neither reads as strong.
- **Stamp what you inferred** (see Provenance).

`references/kb-spec.md` has the headings, block shapes and ids — for cases the mode file does not
already cover.

## The `jsk` command

It never edits `user-knowledgebase.md`; `jsk --help` is the full surface.

| Command | Does |
|---|---|
| `jsk doctor [--quick]` | what this machine can do and what each gap disables |
| `jsk new <path> --name "Name"` | an empty `user-knowledgebase.md` and `applications/` |
| `jsk index <kb> [--rank <posting.md>]` | every entry with its lines, and the ranking |
| `jsk match <posting.ttl>` | a posting matched through the vocabulary |
| `jsk kb <verb>` | the graph record, changed and read |
| `jsk validate <resume.json>` | the record gate |
| `jsk render <resume.json> --out DIR --view ID --pdf [--ats-max] [--template N]` | record to `.tex`/PDF and `.txt` |
| `jsk preview <resume.json> --out DIR` | every template, with page counts |
| `jsk check <file> [--strict] [--only parse\|prose]` | the parse and prose gates on one file |
| `jsk gates <out-dir> [--record R] [--pages N]` | record, parse and prose gates together |
| `jsk ship <resume.json> --out DIR --view ID [--pages N]` | validate, render and gates; stops at the first failure |
| `jsk fit <resume.tex> --target-pages 2` | fits the render to a page budget |
| `jsk freeze <app-dir> --submitted DATE\|false --channel TEXT` | refuses unless the gates pass, then writes `application.md` |

Exit codes: `0` passed, `1` failed, `2` called wrong. A TeX engine and `pymupdf` are required — the
PDF is the only deliverable. A missing input is `SKIPPED` **and** a failure.

## Agents

| Agent | Hand it | Get back |
|---|---|---|
| `jsk-tailor-analyst` | posting, knowledge base path | requirements, ranking, `gaps.md` and its question queue |
| `jsk-resume-author` | posting, gaps, knowledge base path | `resume.json`, every authored clause quoted |
| `jsk-kb-auditor` | knowledge base path | what is missing, as a prioritised question queue |
| `jsk-verifier` | a **failed** gate, or the render gate to read | each verdict verbatim, and where the defect is repaired |

**They never interview**: confirming claims, choosing between close projects and telling someone
where they fall short stay with you and the person. Their output does not reach the person, so
**relay the evidence verbatim** rather than summarising it. No agents available? Run the mode file's
procedure inline.

## The four gates

**Never hand over a resume you have not checked.** Passing one gate says nothing about the others.

| Gate | Question | How |
|---|---|---|
| **Record** | coherent, shaped right, every number traced to a metric? | `jsk validate` — the only thing that sees a key the renderer ignores |
| **Parse** | will an ATS read it? | `jsk check` on the PDF; `--strict` on the `.txt` |
| **Prose** | does it obey the writing rules? | `jsk check --only prose` on the `.tex` |
| **Render** | does it look right, and is it true? | open every page of the PDF |

The first three are `jsk gates` (or `jsk ship`). **Show the output**; fix and re-run, never explain a
failure away. The render gate is half yours: you can check the layout, only the person can confirm
it is true — until they have, the resume is unverified. No PDF renderer → say so and mark it
unverified. Repair a defect in the knowledge base or record and re-render; never patch the PDF.

## Provenance

Every claim carries `status`: `confirmed` (they said it, or a source document does), `inferred`
(you wrote it), or `needs-verification` (a known gap).

- **Never let `inferred` content reach a resume unconfirmed.** It reads well and is indefensible in
  interview.
- **Write `confirmed` only for what they actually said.** When you change a claim's substance, drop
  it back to `inferred` and add a row to `## Open questions`.
- **Never invent a credential**, or call one "in progress", unless they said so.
- **Never hide text or add a term they cannot defend.** `references/ats-rules.md` has the boundary.

## Working with people

- **Let them ramble**, then structure it. Adapt the vocabulary to what they know.
- **Push for a number twice, then let go** — write the bullet true without it and log the gap. Never
  leave a placeholder in a document they might send.
- **Say why**, flag every inference, and offer options with a recommendation.
- **Tell them where they fall short.** Being flattered costs interviews.
- **Append a dated row to `log.md`**, beside the knowledge base, at the end of every session. Record your own earlier mistakes as
  corrections, never as edits.

Save deliverables beside the knowledge base (Claude Code) or in the outputs folder (Cowork), and
tell them the path.

## References, on demand

Formats: `kb-spec.md` (the knowledge base), `urs-spec.md` and `view-format.md` (the record, in two
halves). Rules: `writing-rules.md`, `ats-rules.md`, `templates.md`. `rationale.md` explains why any
rule exists, for when someone asks.
