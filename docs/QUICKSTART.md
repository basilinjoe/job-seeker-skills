# Quickstart

From nothing to a verified resume. Ten minutes, most of it spent talking about your own work.

## 1. Install

The toolchain is a Python package, and the skill drives it:

```
pip install 'jsk-resume[all]'
```

Then the plugin:

```
/plugin marketplace add basilinjoe/job-seeker-skills
/plugin install jsk@job-seeker-skills
```

Or copy the skill straight in:

```bash
git clone https://github.com/basilinjoe/job-seeker-skills.git
cp -r job-seeker-skills/plugins/jsk/skills/jsk ~/.claude/skills/
```

PowerShell:

```powershell
git clone https://github.com/basilinjoe/job-seeker-skills.git
Copy-Item -Recurse job-seeker-skills\plugins\jsk\skills\jsk $env:USERPROFILE\.claude\skills\
```

## 2. Run setup

```
/jsk:setup
```

If you already have a resume, point at it — it is the fastest possible starting point:

```
/jsk:setup ./old-resume.docx
```

Setup checks what your machine can do, offers to close any gaps, creates your knowledge base, then
renders a real resume from it and checks it. It asks before installing anything.

## 3. Answer the questions

Setup interviews you. Ramble — unstructured is fine, and it is easier to structure your answers than
to make you produce structure. It will push you for numbers roughly twice per accomplishment, and let
go if you do not have them.

## 4. You now have two things

**`user-knowledgebase.md`** — one Markdown file, yours, readable in any editor. Put it in Git. It is
the source of truth from here on: identity, roles, projects, every verified number, and a log of what
changed. Everything else is rendered from it.

**A resume** — a PDF and a plain-text copy for paste-in boxes, both rendered from the same record, so
they cannot contradict each other. The PDF is the presentation variant for people unless you ask for
the ATS-maximal one, which is aimed at job portals that parse badly.

## What to do next

| When | Say |
|---|---|
| You shipped something | `/jsk:braindump` — five minutes, while you still remember the numbers |
| Every quarter | `/jsk:refresh` |
| Before applying | `/jsk:gaps`, then `/jsk:resume` |
| Once a week while job-hunting | `/jsk:pipeline` |
| A specific job posting | `/jsk:tailor`, with the URL or the description pasted |
| A resume that is ready to send | `/jsk:ship` |

`/jsk:tailor` is a loop rather than a single step. It reads the posting, works out what your record
answers and what it does not, and asks you about the gaps — then writes the resume once, at the end.
You can skip out of it at any round and take the record as it stands. It tells you where you fall
short against that posting either way, because being flattered costs interviews.

`/jsk:ship` is the end of that loop, and it is two commands:

```bash
jsk ship applications/<stem>/resume.json --out applications/<stem> --view <id>
jsk freeze applications/<stem> --submitted 2026-09-08 --channel "Workday portal"
```

`jsk ship` checks the record first and renders nothing if it fails, then renders the PDF and checks
it and the plain text, printing every verdict. It reports the page count but leaves the last check to
you: open the PDF and read every page. `jsk freeze` refuses until the checks pass, then records what
was sent and when in `application.md`, and names the directory after the submission date. Use
`--submitted false` for an application you worked through and decided not to send.

## If something looks wrong

```bash
jsk doctor
```

This renders the shipped example end to end and runs the checks on it, so a pass means the pipeline
genuinely works on your machine. It names any gap by what it costs you rather than by package name.

If `jsk` is not on your PATH, `python3 -m jsk doctor` is the same entry point. Use `python` or
`py -3` on Windows.

---

Next: [Concepts](CONCEPTS.md) for the vocabulary · [Why it works this way](WHY.md) for the reasoning
