# job-seeker-skills

Claude skills for job seekers. Currently ships one plugin: **Job Seeker Skill**.

## Job Seeker Skill

Most resume tools start from a blank page every time. This one keeps your career in a portable
knowledge base — a folder of plain Markdown files you own — and treats a resume as one *rendering*
of it.

**Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.**

Three things make it different:

- **Nothing is hand-built.** Your record compiles to JSON, and the PDF, both Word variants and the
  plain text are all emitted from that one file — so they cannot drift apart or contradict each other.
- **Nothing is invented.** Tailoring is selection: a view references your evidence by id and reorders
  it. Every number in a bullet must trace to a recorded metric, or the record fails before anything
  renders.
- **Nothing is assumed.** Four checks run before a resume is handed over, and if no PDF renderer is
  available it is marked *unverified* rather than called fine.

### Install

```
/plugin marketplace add basilinjoe/job-seeker-skills
/plugin install jsk@job-seeker-skills
```

Then:

```
/jsk:setup
```

Setup checks what your machine can do, offers to close the gaps, builds your career folder, and
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
| `/jsk:resume` | You need a resume — two verified variants plus plain text |
| `/jsk:tailor` | You have a specific job description |
| `/jsk:refresh` | Periodic top-up: what changed, what numbers moved |
| `/jsk:gaps` | Resolve unanswered questions and unverified claims |
| `/jsk:pipeline` | What to chase this week: what has gone quiet, what is overdue |

```
/jsk:tailor      # then paste the job description
```

**A rhythm that works.** Something ships → `braindump`, five minutes, while you still remember the
details. Every quarter → `refresh`. Before applying → `gaps`, then `resume`. A specific role →
`tailor`.

### Your career folder

```
career/
  index.md · getting-started.md · log.md
  profile/            identity · positioning · career-progression
  organisations/ · roles/
  projects/           one per engagement — the evidence
  achievements/       every verified number
  skills/ · education/ · open-source/ · sources/
  framework/          capability vocabulary · schema · templates
  resume-generation/  open-questions, plus optional rule overrides
  tailoring/          selection-method · targets/ · applications/
```

Plain Markdown: readable in any editor, versionable in Git, readable by AI tools without a
translation layer. Keep it in a repo you control so it outlives any single tool, including this one.

### Documentation

| | |
|---|---|
| [Quickstart](docs/QUICKSTART.md) | Install to first resume, ten minutes |
| [Concepts](docs/CONCEPTS.md) | The vocabulary, on one screen |
| [Why it works this way](docs/WHY.md) | The reasoning behind every design decision |
| [Scripts](docs/SCRIPTS.md) | The eleven tools: flags, dependencies, exit codes |
| [Architecture](docs/ARCHITECTURE.md) | For anyone editing this repo |
| [URS, explained](docs/urs-guide.md) | The résumé record format, walked through a real document |
| [URS spec](plugins/jsk/skills/jsk/references/urs-spec.md) | The normative definition: every type, every MUST |

### Tests

```bash
python -m unittest discover -s tests
```

Standard library `unittest`; fixtures are generated into temp directories, nothing is committed.
Every test pins a specific documented rule — the checker is the gate, so it does not go unchecked.

## Licence

MIT
