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

Sessions do not share state. Never assume a bundle exists because one was created before.

**No bundle?** Switch to setup mode — unless they asked for something you can deliver anyway. If
someone wants a resume right now, build the resume, then offer to capture it as a bundle. Setup
should never block the actual ask.

**A bundle's own rules win.** If `resume-generation/*.md` exists in their bundle, it takes precedence
over `references/` here. These files are optional and hand-created — setup does not scaffold them,
so absent just means "use the defaults". When one does exist, somebody customised it deliberately
and their edits should stick.

## Shared references

Load as needed rather than upfront:

- `references/bundle-spec.md` — directory layout, frontmatter schema, selection keys, concept types
- `references/writing-rules.md` — X-Y-Z bullets, verb accuracy, phrases that damage seniority
- `references/ats-rules.md` — hard rules, the two-variant strategy, keyword placement

## Scripts

They live in `scripts/`, **relative to this skill's own directory** — the absolute path you were
given when this skill loaded, or `${CLAUDE_PLUGIN_ROOT}/skills/career-okf` in a plugin install.
Always invoke them by that absolute path. The working directory is the person's project, not the
skill, so a bare `scripts/…` will not resolve.

| Script | Does | Needs |
|---|---|---|
| `init_bundle.py <path> --name "Their Name"` | creates an empty bundle skeleton | — |
| `validate_bundle.py <bundle-path>` | bundle is well-formed | `pyyaml` |
| `check_ats.py resume.docx [--strict]` | a generated `.docx` is safe to send | — |
| `check_prose.py resume.docx` | the writing rules `check_ats.py` cannot see | — |
| `fit_pages.py resume.docx --target-pages 2` | fits a render to a page budget without breaching the floors | LibreOffice, `pymupdf` |

```bash
python3 <skill-dir>/scripts/check_ats.py resume.docx --strict
```

Use `python` or `py -3` on Windows, where `python3` is usually absent.

`fit_pages.py` is the only script with external dependencies. Without them it reports loudly and
exits non-zero rather than passing, because a page count nobody measured is a page count nobody
knows. Everything else runs on a bare Python.

The scripts stay with the skill and a bundle never carries copies, so every bundle gets the current
version. If they are genuinely missing — the skill was installed as `SKILL.md` alone — write them
into the bundle's `framework/` from the specifications in `references/ats-rules.md` and
`references/bundle-spec.md`. A rule nobody checks stops being true.

## The verification gate

**Never hand over a resume you have not checked.** Run `check_ats.py` on the presentation variant and
`--strict` on the ATS-maximal one. Both must PASS. Show the output — the person should see the
evidence rather than take your word for it. Fix and re-run; never explain away a failure.

Run `validate_bundle.py` after any change to the bundle.

## Provenance — the habit that makes this last

Every concept carries `status`:

- `confirmed` — they said it, or it is in a source document
- `inferred` — you wrote it while drafting; plausible but unverified
- `needs-verification` — a known gap

**Never let `inferred` content reach a resume without asking them to confirm it.** You will often
write better prose than they spoke; that is useful, but reasoning you supplied is yours until they
agree with it. The danger is precisely that it reads well — plausible, well-written, and indefensible
when an interviewer asks a follow-up.

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
correction rather than editing silently — a knowledge base that hides its errors cannot be trusted.

## Portability

Works in Claude Code and Cowork. Use ordinary file tools and paths; do not assume either environment.
In Cowork, save deliverables to the outputs folder and present them. In Claude Code, write beside the
bundle and tell them the path. Prefer the bundle living in a folder the person controls — ideally
version-controlled — so it outlives any single session.
