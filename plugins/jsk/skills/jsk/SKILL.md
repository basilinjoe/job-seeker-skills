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

A career knowledge base kept in **one store, `career/store/`**, read and written only through `jsk`
and validated on every load, plus a toolchain that renders verified, ATS-safe resumes from it.
Interview someone once; regenerate resumes, tailored variants and interview briefs forever after.

**The knowledge base is the source of truth. A resume is one rendering of it.**

```
career/store/ + a selection  ->  .tex -> .pdf   (the deliverable)
  career_apply   resume_select
```

**Never hand-author a `.tex`.** Select, validate, render every format from the selection — two
hand-built documents stop agreeing the moment one is edited.

| Thing | Is | Written by |
|---|---|---|
| `career/store/` | the career and its history; each application's advert, requirements, review, assessment, selection and timeline | `jsk` only |
| `applications/<stem>/` | what was rendered: the `.pdf` and the `.tex` | `resume_ship` |

An application made from files (`posting.md`, `decisions.txt`, `gaps.txt`, `resume.json`) keeps
them; the tools refuse it, and its commands retire in 6.0. `app_list` and `jsk kb check` name the
unsent ones: send each first, or drop it.
`applications/` is the directory beside `career/` — resolve it to an absolute path, never the
working directory.

## The `jsk` tools

The plugin starts `jsk mcp` (`pip install 'jsk-resume[mcp]'`). Its tools —
`mcp__plugin_jsk_graph__` + `career_*`, `app_*`, `posting_*`, `assessment_*`, `resume_*`,
`letter_check` — take JSON and answer `ok` and findings, each with its fix. Prefer a tool to its
command. `career_confirm` (the person's words), `app_freeze`, `app_event` and `letter_check` are
yours, never an agent's.

## Modes

Route on the argument if one was passed, otherwise on the message. Ambiguous? Ask — the modes do
different things.

| Mode | Trigger | Read |
|---|---|---|
| **setup** | no knowledge base, or "set this up" | `references/mode-setup.md` |
| **braindump** | telling you about their work; long unstructured messages | `references/mode-braindump.md` |
| **resume** | "build my resume", "is this ATS-safe" | `references/mode-resume.md` |
| **tailor** | a job description or URL; "customise for this role" | `references/mode-tailor.md` |
| **ship** | a finished record needs rendering, gating, freezing | `references/mode-ship.md` |
| **refresh** | "update my knowledge base", quarterly review, got promoted | `references/mode-refresh.md` |
| **gaps** | "what's missing", "resume feels vague", verify before applying | `references/mode-gaps.md` |
| **pipeline** | "what do I chase", "where are my applications", weekly review | `references/mode-pipeline.md` |

## Every session, first

1. **Run `jsk --version`**. Not found → `python3 -m jsk` (`python` or `py -3` on Windows). Neither →
   say so and stop.
2. **Find the knowledge base** — `jsk doctor`, or search for `career/store/`. A `career/kb.ttl`
   with no store is a record from before it: `jsk kb load .`, once. Sessions share no state.
   None → setup, unless they asked for something deliverable: deliver it, then offer to capture it.
3. **`rules/writing-rules.md`, `ats-rules.md`, `structure-rules.md`** beside `career/` override
   their defaults.

## Changing the career

**One rule: `career_apply`, or change it with `jsk kb apply <changeset.trig>`**: a TriG changeset
of `op:add`, `op:set`, `op:retire`; `career_preview` (`--dry-run`) shows the diff. Read with
`career_show(ids)` (it gives the `op:base`), `career_view`, `career_query`, `career_log`, before
adding anything: people re-tell one project months apart in other words. **Confirm through
`career_confirm`. Confirm only with `jsk kb confirm <id> --answer "their words"` in a shell.** `references/kb-format.md` has the format, for a
changeset you are unsure of.

**Never open anything under `career/`** — only `jsk` reads the store. No pyoxigraph → draft the
changeset to a file for later.

## The `jsk` command

`jsk --help` and `jsk kb --help` are the full surface.

| Command | Does |
|---|---|
| `jsk doctor [--quick]` | what this machine can do and what each gap disables |
| `jsk kb new <path> --name "Name"` | an empty `career/store/` and `applications/` |
| `jsk kb apply\|confirm\|show\|view\|query\|log\|check\|path\|export\|pack\|merge` | the career, changed and read; `export` prints a selection, `pack` and `merge` vocabulary changesets |
| `jsk resume check <resume.json>\|<stem>\|<file>\|<out-dir>` | the record gate; parse and prose; all four over a directory |
| `jsk resume render <resume.json> --out DIR --pdf [--ats-max] [--template N]` | record to `.tex` and PDF |
| `jsk resume preview <resume.json> --out DIR` | every template, with page counts |
| `jsk resume ship <resume.json> --out DIR\|<stem> [--pages N]` | validate, render, fit an overrun, gates; stops at a failure |
| `jsk resume fit <resume.tex> --target-pages 2` | fits the render to a page budget |
| `jsk letter check <letter> --record R` | a cover letter's words and numbers |
| `jsk app freeze <app-dir> --submitted DATE\|false --channel TEXT` | records what was sent, if the gates pass |
| `jsk app event <app-dir> <kind> --date DATE` | a screen, an offer, a rejection |
| `jsk app drop <app-dir>` | sets an unsent one aside |
| `jsk mcp` | the career and graph-native applications as MCP tools, over stdio (`mcp` extra) |

Exit codes: `0` passed, `1` failed, `2` called wrong. A TeX engine and `pymupdf` are required — the
PDF is the only deliverable. A missing input is `SKIPPED` **and** a failure.

## Agents

| Agent | Hand it | Get back |
|---|---|---|
| `jsk-tailor-analyst` | the app's stem | the requirements, the match, the assessment and questions |
| `jsk-resume-author` | stem, assessment, skill directory | the selection, every authored clause quoted |
| `jsk-kb-auditor` | workspace | what is missing, as a prioritised question queue |
| `jsk-extractor` | workspace, a braindump or document in `sources/` | a previewed changeset, its inferred clauses quoted |
| `jsk-verifier` | a **failed** gate, or the render gate to read | each verdict verbatim, and the id to repair |

**They never interview**: confirming claims, choosing between close projects and telling someone
where they fall short stay with you and the person. Their output does not reach the person, so
**relay the evidence verbatim**. No agents available? Run the mode file's procedure inline.

## The gates

**Never hand over a resume you have not checked.** Passing one gate says nothing about the others.

| Gate | Question | How |
|---|---|---|
| **Record** | shaped right, every id live, every number traced to a metric? | `jsk resume check` on the `<stem>` or `.json` |
| **Parse** | will an ATS read it? | `jsk resume check` on the PDF; on the directory, its text `--strict` too |
| **Prose** | does it obey the writing rules? | `jsk resume check --only prose` on the `.tex` |
| **Layout** | tofu, fonts, stranded headings, dates, paper? | `jsk resume check --only layout` on the PDF |
| **Render** | does it look right, and is it true? | open every page of the PDF |

`jsk resume check <dir>` (or `ship`) runs all but the last. **Show the output**; fix and re-run, never explain
a failure away. The render gate is half yours: only the person can confirm it is true — until they
have, the resume is unverified. Repair a defect in the career or the selection and re-render; never the PDF.

## Provenance

Every claim carries one: `confirmed` (they said it, or a source document does), `inferred` (you
wrote it), or `needs-verification`.

- **Never let `inferred` content reach a resume unconfirmed.** It reads well and is indefensible in
  interview. A changed claim drops to `inferred` by itself.
- **Never invent a credential**, or call one "in progress", unless they said so.
- **Never hide text or add a term they cannot defend.** `references/ats-rules.md` has the boundary.

## Working with people

- **Let them ramble**, then structure it. Adapt the vocabulary to what they know.
- **Push for a number twice, then let go** — write the bullet true without it and leave the question
  open. Never leave a placeholder in a document they might send.
- **Say why**, flag every inference, and offer options with a recommendation.
- **Tell them where they fall short.** Being flattered costs interviews.

A file-made application: Keep `resume.json` inside the workspace, where it finds its career. Copy
only rendered files to an outputs folder (Cowork). Tell them the path.

## References, on demand

Formats: `kb-format.md` (the career), `resume-format.md` (`resume.json`). Rules: `writing-rules.md`,
`ats-rules.md`, `templates.md`. `rationale.md` explains why any rule exists, for when someone asks.
