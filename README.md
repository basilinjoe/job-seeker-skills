# job-seeker-skills

Claude skills for job seekers. Currently ships one plugin: **Job Seeker Skill**.

## Job Seeker Skill

Most resume tools start from a blank page every time. This one keeps your career in **one Markdown
file you own** — `user-knowledgebase.md` — and treats a resume as one *rendering* of it.

**Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.**

Four things make it different:

- **Nothing is hand-built.** One JSON record is written from your knowledge base, and the PDF and the
  paste-in plain text are both emitted from it — so they cannot drift apart or contradict each other.
- **Gaps close first.** The posting, the gap assessment between it and your record, and the record
  that selects what renders all live in one directory per application. Tailoring closes the gaps
  first and writes the resume last — there is no reason to author a document from a record you are
  about to change.
- **Nothing is invented.** Tailoring is selection: a view references your evidence by id and reorders
  it. Every number in a bullet must trace to a recorded metric, or the record fails before anything
  renders.
- **Nothing is assumed.** Four checks run before a resume is handed over, and if no PDF renderer is
  available it is marked *unverified* rather than called fine.

### Install

The toolchain is a Python package, and the skill drives it:

```
pip install 'jsk-resume[all]'
```

Then the plugin:

```
/plugin marketplace add basilinjoe/job-seeker-skills
/plugin install jsk@job-seeker-skills
```

Then:

```
/jsk:setup
```

Setup checks what your machine can do, offers to close the gaps, creates your knowledge base, and
renders a real resume from it. It asks before installing anything.

Already have a resume? Point at it — it is the fastest starting point available:

```
/jsk:setup ./old-resume.docx
```

Works in Claude Code and Claude Cowork. Full instructions, including manual install, in the
[Quickstart](docs/QUICKSTART.md).

### Use

Describe what you want and the skill routes there by itself. Or say it directly:

| Command | When |
|---|---|
| `/jsk:setup` | First run, or importing an existing resume |
| `/jsk:braindump` | You have something to say about your work |
| `/jsk:resume` | You need a resume — one verified PDF plus plain text |
| `/jsk:tailor` | You have a specific job posting - a loop that closes the gaps, then writes the resume |
| `/jsk:ship` | A resume is finished and needs rendering, checking and filing — `jsk ship`, then `jsk freeze` |
| `/jsk:refresh` | Periodic top-up: what changed, what numbers moved |
| `/jsk:gaps` | Resolve unanswered questions and unverified claims |
| `/jsk:pipeline` | What to chase this week: what has gone quiet, what is overdue |

```
/jsk:tailor      # then paste the job posting, or give it the URL
```

**A rhythm that works.** Something ships → `braindump`, five minutes, while you still remember the
details. Every quarter → `refresh`. Before applying → `gaps`, then `resume`. A specific role →
`tailor`.

### Your career folder

```
career/
  user-knowledgebase.md     the whole career, under fixed headings
  applications/
    2026-09-08-acme-platform-engineer/
      posting.md            the advertisement, and what it asks for
      gaps.md               the assessment, and the question queue
      resume.json           the record this submission rendered from
      application.md        what was sent, and what came back
      Priya_Raman_Resume.{tex,pdf}
      Priya_Raman_Resume_ATS.txt
```

One file, and a frozen directory per application. `user-knowledgebase.md` holds identity,
positioning, organisations, roles, projects, metrics, skills, education, certifications, the open
questions and a log — each under a fixed heading, described in
[the format spec](plugins/jsk/skills/jsk/references/kb-spec.md). `jsk freeze` writes
`application.md` once the gates pass and names the directory after the day it was sent; from then on
it is an archive, and what came back is appended to its timeline.

A folder of linked concepts with a compiler over it is the right shape for a knowledge base too large
to hold in one context. A career is not. One file is readable end to end by the person whose career
it is, which is the property that actually decides whether a career record survives a year.

Plain Markdown: readable in any editor, versionable in Git, readable by AI tools without a
translation layer. Keep it in a repo you control so it outlives any single tool, including this one.

### Documentation

| | |
|---|---|
| [Quickstart](docs/QUICKSTART.md) | Install to first resume, ten minutes |
| [Concepts](docs/CONCEPTS.md) | The vocabulary, on one screen |
| [Why it works this way](docs/WHY.md) | The reasoning behind every design decision |
| [Commands](docs/SCRIPTS.md) | The `jsk` command: every subcommand, flags, dependencies, exit codes |
| [The knowledge base format](plugins/jsk/skills/jsk/references/kb-spec.md) | Every heading in `user-knowledgebase.md`, and what goes under it |
| [Architecture](docs/ARCHITECTURE.md) | For anyone editing this repo |
| [URS, explained](docs/urs-guide.md) | The résumé record format, walked through a real document |
| [URS spec](plugins/jsk/skills/jsk/references/urs-spec.md) | The normative definition of the record: every type, every MUST |
| [View format](plugins/jsk/skills/jsk/references/view-format.md) | The other half of that spec: every key a view may carry, and the rule that it may carry no prose |

### Tests

```bash
python -m pytest tests -n auto         # the whole suite in parallel, about two minutes
python -m pytest tests -q              # serially, about five
python -m unittest discover -s tests   # the same tests, with no pytest installed
```

Standard library `unittest`, run against `src/` directly — so the suite always tests the working
tree, never whatever `jsk-resume` happens to be installed. Install `.[dev]` first. Fixtures are
generated into temp directories, nothing is committed.
Every test pins a specific documented rule — the checker is the gate, so it does not go unchecked.
Most of the runtime is TeX: the render tests compile real PDFs, and they skip themselves rather than
fail where no TeX engine or `pymupdf` is installed.

## Licence

MIT
