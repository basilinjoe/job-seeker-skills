# Quickstart

From nothing to a verified resume. Ten minutes, most of it spent talking about your own work.

## 1. Install

The toolchain is a Python package, and the skill drives it:

```
pip install 'jsk-resume[all]'
```

`mcp` comes with the package (a required dependency since 6.0): the plugin starts `jsk mcp`, and
Claude and its agents read and write your record through that server's tools rather than through
files or commands. Restart Claude Code after installing it. Then the plugin:

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

What you say goes into your record as changesets: the skill drafts one, shows you the diff (`career_preview`), and writes it (`career_apply`)
once you agree; everything you said is marked *inferred* until you confirm it. When the skill reads
a line back and you say "yes, that's right - 800 ms before, 200 after", it calls `career_confirm`
with your words.

## 4. You now have two things

**Your career record** — your whole career in `career/store/`, a store in your own folder that
`jsk` reads and writes. It is the source of truth from here on: identity, roles, projects, every
verified number, the vocabulary you are matched on, and a log of every change. It is not a text
file to open in an editor: ask Claude to show it (`career_view` returns the whole career as Markdown, `career_log`
the history), or run `jsk kb dump` to write all of it out as text. Every change also refreshes a copy in
`.jsk/backup.trig`, so back up the folder and you have backed up the record.

**A resume** — a PDF, rendered from the career together with the plain text the checks read, so
the two cannot contradict each other. The PDF is the presentation variant for people unless you ask for
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

Since 5.0.0 an application lives in your record, not in files: the posting's lines, what it asks
for, the analyst's review, the assessment and the bullets chosen for it are all stored there, and
its folder under `applications/` holds only the PDF and `.tex` it rendered and any cover letter. A "no" you give ("never
used Kafka") is recorded too, so the next posting that asks gets your answer without asking you.

`/jsk:ship` is the end of that loop, and it is two steps: `resume_ship` (the same as running
`jsk resume ship <stem>` yourself), then `app_freeze` with the day you sent it and the channel
("Workday portal").

`resume_ship` checks the chosen bullets against your career first - every id live, every number traced to
a current metric - and renders nothing if that fails, then renders the PDF and checks it and its plain text, printing every
verdict. It reports the page count but leaves the last check to you: open the PDF and read every
page. `app_freeze` refuses until the checks pass, then records in your record what was sent,
when, and which bullets rendered and the metric versions they cite, and names the directory after the
submission date. Pass `submitted="false"` for an application you worked through and decided not to
send. When something comes back, `/jsk:pipeline` records it - against the directory's new name,
which `app_freeze` returns: it calls `app_event` (kind `screen-scheduled`, date `2026-09-15`), and
`career_query("pipeline")` shows every application's stage and how long since.

## What runs where

The skill drives all of this through `jsk mcp`'s tools; since 6.0 changing the career, capturing
a posting, choosing a resume, freezing and recording an event are tools only, with no shell verb.
The commands that remain:

```bash
jsk kb new ./my-career --name "Your Name"     # career/store/: an empty career and its log, at r1
cd my-career
jsk kb check                                  # every rule over the record
#   career_apply, posting_capture, posting_decide, assessment_derive, resume_select,
#   career_confirm ... (jsk mcp's tools, called by Claude)
jsk resume check <stem>                       # the record gate on the stored selection
jsk resume ship <stem>                        # rendered and gated into applications/<stem>/
jsk kb dump --out record.trig                 # the whole record as TriG, a backup
```

A changeset is TriG text passed to `career_apply`; [Commands](SCRIPTS.md#jsk-kb) has one that applies to a new
workspace as it stands. The tailoring step writes no file: the posting, review, assessment and
selection are graphs in the store. Until 6.0 an application could be made from files
(`posting.md`, `decisions.txt`, `gaps.txt`, `resume.json`); one left unsent is finished with jsk
5.1.0, or set aside with `jsk app drop`.

Already have a workspace from before the store, with `career/kb.ttl`? Run `jsk kb load .` in it,
once. It checks the files as before, lists every number it rewrites, and imports them; the files
stay where they are and are not read again.

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
