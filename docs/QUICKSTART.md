# Quickstart

From nothing to a verified resume. Ten minutes, most of it spent talking about your own work.

## 1. Install

```
/plugin marketplace add basilinjoe/job-seeker-skills
/plugin install career-okf@job-seeker-skills
```

Or copy the skill straight in:

```bash
git clone https://github.com/basilinjoe/job-seeker-skills.git
cp -r job-seeker-skills/plugins/career-okf/skills/career-okf ~/.claude/skills/
```

PowerShell:

```powershell
git clone https://github.com/basilinjoe/job-seeker-skills.git
Copy-Item -Recurse job-seeker-skills\plugins\career-okf\skills\career-okf $env:USERPROFILE\.claude\skills\
```

## 2. Run setup

```
/career-okf:setup
```

If you already have a resume, point at it — it is the fastest possible starting point:

```
/career-okf:setup ./old-resume.docx
```

Setup checks what your machine can do, offers to close any gaps, builds your career folder, then
renders a real resume from it and checks it. It asks before installing anything.

## 3. Answer the questions

Setup interviews you. Ramble — unstructured is fine, and it is easier to structure your answers than
to make you produce structure. It will push you for numbers roughly twice per accomplishment, and let
go if you do not have them.

## 4. You now have two things

**A career folder** — plain Markdown, yours, readable in any editor. Put it in Git. It is the source
of truth from here on.

**A resume** — actually three files: one formatted for humans, one stripped for job portals, and
plain text for paste-in boxes. All rendered from the same record, so they cannot contradict
each other.

## What to do next

| When | Say |
|---|---|
| You shipped something | `/career-okf:braindump` — five minutes, while you still remember the numbers |
| Every quarter | `/career-okf:refresh` |
| Before applying | `/career-okf:gaps`, then `/career-okf:resume` |
| Once a week while job-hunting | `/career-okf:pipeline` |
| A specific job posting | `/career-okf:tailor`, then paste the description |

## If something looks wrong

```bash
python3 plugins/career-okf/skills/career-okf/scripts/preflight.py --verify
```

This renders the shipped example end to end and runs the checks on it, so a pass means the pipeline
genuinely works on your machine. It names any gap by what it costs you rather than by package name.

Use `python` or `py -3` on Windows.

---

Next: [Concepts](CONCEPTS.md) for the vocabulary · [Why it works this way](WHY.md) for the reasoning
