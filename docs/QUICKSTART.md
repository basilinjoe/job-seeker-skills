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

**Already have a `user-knowledgebase.md`** from an earlier version? Setup finds it, and `jsk doctor`
names it as a gap. Move it across once:

```bash
jsk migrate ./my-career/user-knowledgebase.md --dry-run   # every file it would write, printed
jsk migrate ./my-career/user-knowledgebase.md             # career/kb.ttl and log.ttl, at r1
```

It refuses unless the new record reads back as exactly what the Markdown held, and it deletes
nothing - `user-knowledgebase.md`, `log.md` and every application stay where they are. Each
unsent `resume.json` is shortened to the new format and put through the record gate against the new
career, so you see at once anything it chose that the career does not back. `jsk migrate` is in this release only.

## 3. Answer the questions

Setup interviews you. Ramble — unstructured is fine, and it is easier to structure your answers than
to make you produce structure. It will push you for numbers roughly twice per accomplishment, and let
go if you do not have them.

What you say goes into your record as changesets: the skill drafts one, `jsk kb apply` checks and
writes it and prints the diff, and everything you said is marked *inferred* until you confirm it.
When the skill reads a line back and you say "yes, that's right - 800 ms before, 200 after", it runs
`jsk kb confirm` with your words.

## 4. You now have two things

**`career/kb.ttl`** — your whole career in one file, yours, readable in any editor. Put the folder
in Git (`jsk new` writes the `.gitattributes` that keeps it LF). It is the source of truth from here
on: identity, roles, projects, every verified number, the vocabulary you are matched on. Beside it,
`career/log.ttl` records every change. `jsk kb view` prints the whole career as Markdown to read.

**A resume** — a PDF and a plain-text copy for paste-in boxes, both rendered from the same career, so
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
jsk ship applications/<stem>/resume.json --out applications/<stem>
jsk freeze applications/<stem> --submitted 2026-09-08 --channel "Workday portal"
```

`jsk ship` checks `resume.json` against your career first - every id live, every number traced to
a current metric - and renders nothing if that fails, then renders the PDF and checks it and the plain text, printing every
verdict. It reports the page count but leaves the last check to you: open the PDF and read every
page. `jsk freeze` refuses until the checks pass, then records in `application.ttl` what was sent,
when, and which bullets rendered and the metric versions they cite, and names the directory after the
submission date. Use `--submitted false` for an application you worked through and decided not to
send. When something comes back, `/jsk:pipeline` records it - against the directory's new name,
which `jsk freeze` prints:

```bash
jsk event applications/2026-09-08-<stem> screen-scheduled --date 2026-09-15
jsk kb query pipeline            # every application's stage, and how long since
```

## The same, by hand

The skill runs all of this for you. Underneath, from nothing to a sent application:

```bash
jsk new ./my-career --name "Your Name"        # career/kb.ttl (empty) and log.ttl, at r1
cd my-career
jsk kb apply braindump.trig --dry-run         # what a changeset would change
jsk kb apply braindump.trig                   # ... written and logged, as r2
jsk kb confirm k:ach_payments_cut_settlement_latency --answer "Yes: 800 ms to 200, from Grafana."
jsk match applications/<stem>/posting.ttl     # the posting against the career, with the paths
jsk kb export --from-match applications/<stem>/posting.ttl --out applications/<stem>/resume.json
jsk ship applications/<stem>/resume.json --out applications/<stem>
jsk freeze applications/<stem> --submitted 2026-09-08 --channel "Workday portal"
jsk event applications/2026-09-08-<stem> screen-scheduled --date 2026-09-15   # freeze renamed it
```

A changeset is a small TriG file; [Commands](SCRIPTS.md#jsk-kb) has one that applies to a new
workspace as it stands. `posting.ttl` (what the posting asks for) and `resume.json` (the bullets chosen
for that application, by id) are what the tailoring step writes.

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
