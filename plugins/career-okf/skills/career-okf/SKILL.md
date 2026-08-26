---
name: career-okf
description: >-
  Use when the user wants to write, rebuild, update or tailor a resume or CV; capture work history,
  projects or accomplishments; record something they shipped; prepare a job application or paste a
  job description; check whether a resume will survive applicant tracking systems (ATS); resolve
  gaps or missing metrics in their career records; says their resume is outdated or vague; describes
  their work in long unstructured messages; wants a periodic career review; or asks about a career
  bundle, OKF, brag document or resume framework.
license: MIT
---

# Career OKF

A career knowledge base as a folder of linked Markdown files with YAML frontmatter — the
**Open Knowledge Format** — plus tooling to render verified, ATS-safe resumes from it.

Interview someone **once**, then regenerate resumes, tailored variants, LinkedIn copy and interview
briefs forever without re-interviewing them.

**The bundle is the source of truth. A resume is one rendering of it.**

Rendering goes through JSON, always:

```
bundle (Markdown)  ->  resume.json (URS)  ->  .tex -> .pdf
                                          \-> .docx  x2
                                          \-> .txt
```

**Never hand-author a `.docx` or a `.tex`.** Build the URS record, validate it, render every format
from it. *Two hand-built documents stop agreeing the moment one is edited — silently, usually in the
copy that gets sent.* `references/urs-spec.md` has the format, `references/mode-resume.md` the
procedure.

## Modes

Route on what the user asked for. If they passed an argument (`braindump`, `resume`, `tailor`,
`refresh`, `gaps`, `setup`), use it. Otherwise infer from their message.

| Mode | Trigger | Read |
|---|---|---|
| **setup** | no bundle exists, or "set this up" | `references/mode-setup.md` |
| **braindump** | telling you about their work; long unstructured messages | `references/mode-braindump.md` |
| **resume** | "build my resume", "is this ATS-safe" | `references/mode-resume.md` |
| **tailor** | pasted a job description; "customise for this role" | `references/mode-tailor.md` |
| **refresh** | "update my bundle", quarterly review, got promoted | `references/mode-refresh.md` |
| **gaps** | "what's missing", "resume feels vague", verify before applying | `references/mode-gaps.md` |

Ambiguous? Ask which they want rather than guessing — the modes do genuinely different things.

## Always do this first

**Find the bundle.** Search the working directory and any connected folder for a directory
containing both `projects/` and `resume-generation/`, or matching `*-okf`, or a zip with `okf` in
the name. Read its `index.md` then `log.md` — they orient you.

**Check its revision.** `index.md` carries `okf_bundle:`. Absent, or below the current
revision, means the bundle predates the current layout:

```bash
python3 <skill-dir>/scripts/migrate_bundle.py <bundle>
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
| `references/target-template.md` | the Job Target frontmatter the scorer reads |
| `references/urs-spec.md` | the JSON standard every document renders from, plus the region profiles |
| `references/rationale.md` | why the rules are what they are — read it when you need to *explain* one |

## Scripts

They live in `scripts/`, **relative to this skill's own directory** — the absolute path you were
given when this skill loaded, or `${CLAUDE_PLUGIN_ROOT}/skills/career-okf` in a plugin install.
Always invoke them by that absolute path. The working directory is the person's project, not the
skill, so a bare `scripts/…` will not resolve.

| Script | Does | Needs |
|---|---|---|
| `preflight.py [--verify]` | what this machine can do, and what each gap disables | — |
| `init_bundle.py <path> --name "Their Name"` | creates an empty bundle skeleton | — |
| `validate_bundle.py <bundle-path>` | bundle is well-formed | `pyyaml` |
| `migrate_bundle.py <bundle> [--apply]` | brings an older bundle up to the current layout; reports what it cannot establish rather than guessing | — |
| `check_ats.py resume.docx [--strict]` | a generated `.docx` is safe to send | — |
| `check_prose.py resume.docx` | the writing rules `check_ats.py` cannot see | — |
| `score_projects.py <bundle> <target.md>` | ranks projects against a posting, from the target's frontmatter | `pyyaml` |
| `validate_urs.py resume.json [--level N]` | the URS record is coherent before anything renders | — |
| `render_resume.py resume.json --out DIR [--view ID] [--pdf]` | one record to `.tex`/PDF, both `.docx` variants and `.txt` | TeX engine for the PDF |
| `fit_pages.py resume.docx --target-pages 2` | fits a render to a page budget without breaching the floors | LibreOffice, `pymupdf` |

```bash
python3 <skill-dir>/scripts/check_ats.py resume.docx --strict
```

Use `python` or `py -3` on Windows, where `python3` is usually absent.

Exit codes are uniform: `0` passed, `1` failed, `2` called wrong. `fit_pages.py` and the PDF step of
`render_resume.py` are the only parts with external dependencies; without them they report loudly and
exit non-zero rather than passing, *because a page count nobody measured is a page count nobody
knows.* Everything else runs on a bare Python.

The scripts stay with the skill and a bundle never carries copies, so every bundle gets the current
version. If they are genuinely missing — the skill was installed as `SKILL.md` alone — write them
into the bundle's `framework/` from the specifications in `references/ats-rules.md` and
`references/bundle-spec.md`. *A rule nobody checks stops being true.*

## Agents

Three parts of this work are read-heavy or mechanical and need nobody in the room. Delegate those and
keep the conversation for the judgment.

| Agent | Hand it | Get back |
|---|---|---|
| `career-okf-verifier` | the rendered files, the view id, the page budget | every gate's verdict verbatim, and where in `resume.json` each defect is repaired |
| `career-okf-bundle-auditor` | the bundle path | a prioritised gap queue, with the questions written ready to ask |
| `career-okf-posting-analyst` | a posting and the bundle | the target file written, the ranking, the unmatched requirements, and what to pause on |

They read and report; **they never interview and they never decide.** Confirming an `inferred` claim,
choosing between two close-ranked projects, and telling someone where they fall short all stay here,
with the person present.

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
| **Record** | Is the source coherent, and does every number trace to a metric? | `validate_urs.py` on `resume.json`, before anything renders |
| **Parse** | Will an ATS read this without mangling it? | `check_ats.py` on the presentation variant, `--strict` on the ATS-maximal one |
| **Prose** | Does it obey the writing rules? | `check_prose.py` on the presentation variant and the plain text |
| **Render** | Does it *look* right, and is it *true*? | Convert to PDF and look at every page |

All gates must pass. Show the output — the person should see the evidence rather than take your word
for it. Fix and re-run; never explain away a failure.

`career-okf-verifier` runs all four against files that already exist and reports what they said. It
has no way to edit a document, which is deliberate: a defect is repaired in `resume.json` and
re-rendered, never patched into the `.docx`.

**If no PDF renderer is available**, say so and mark the resume unverified rather than treating a
passing `check_ats.py` as sufficient. *An unverified resume the person knows about is fine; one they
think was checked is not.*

Run `validate_bundle.py` after any change to the bundle.

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

**Never invent a credential**, or claim one is "in progress", unless they said so.

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
