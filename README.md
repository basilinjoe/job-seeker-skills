# job-seeker-skills

Claude skills for job seekers. Currently ships one plugin: **Job Seeker Skill**.

## Job Seeker Skill

Most resume tools start from a blank page every time. This one keeps your career in **one file you
own** — `career/kb.ttl`, a graph laid out as one readable file and checked every time it is loaded
— and treats a resume as one *rendering* of it.

**Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.**

Five things make it different:

- **The career checks itself.** Every entry has an id and every link is by id, so a bullet citing a
  metric that does not exist, or a role at an employer that is not there, is found the next time
  anything runs. Changes go in through `jsk kb apply` - validated, written, logged, with the diff
  shown - and nothing can be marked confirmed except by your own answer.
- **Nothing is hand-built.** The PDF and the paste-in plain text are both built from your knowledge
  base and a short `resume.json` naming what this resume shows — so they cannot drift apart or
  contradict each other.
- **Gaps close first.** The posting, the gap assessment between it and your record, and the
  `resume.json` that selects what renders all live in one directory per application. Tailoring closes the gaps
  first and writes the resume last — there is no reason to author a document from a record you are
  about to change.
- **Nothing is invented.** Tailoring is selection: `resume.json` names your evidence by id and orders
  it, and holds no bullet's words — a reworded bullet goes into the career, where you confirm it.
  Every id must be live in your career and every number in a chosen bullet must trace to the current
  version of a recorded metric, or the resume fails before anything renders.
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

Already have a `user-knowledgebase.md` from an earlier version? `jsk migrate` moves it to
`career/kb.ttl` once, checks the round trip, and deletes nothing. It is in this release only.

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
my-career/                  `jsk new ./my-career --name "Your Name"` makes this
  career/
    kb.ttl                  the whole career, in fixed sections
    log.ttl                 every change to it, numbered, each with kb.ttl's hash
  applications/
    2026-09-08-acme-platform-engineer/
      posting.md            the advertisement, verbatim
      posting.ttl           what it asks for, each requirement quoting the advert
      gaps.md               the assessment, and the question queue
      resume.json           the bullets and settings this submission rendered from
      application.ttl       what was sent, what it carried, and what came back
      Priya_Raman_Resume.{tex,pdf}
      Priya_Raman_Resume_ATS.txt
  .gitattributes            keeps *.ttl and *.trig LF, so the hashes hold on Windows
```

One file for the career, and a frozen directory per application. `kb.ttl` holds identity,
positioning, work rights, vocabulary, organisations, roles, projects, metrics, skills, education,
certifications, open source and the open questions — each under a fixed banner, in the order the
format reference ([kb-format.md](plugins/jsk/skills/jsk/references/kb-format.md)) describes.
`jsk freeze` writes `application.ttl` once the gates pass and names the directory after the day it
was sent; from then on it is an archive, and `jsk event` adds what came back.

It is a graph - every entry an id, every link between entries by id - because that is what lets a
program check it on every load, match a posting one way through a vocabulary, keep every version of
a number, and join a resume back to the career it claims. It is laid out as one file, in the old
section order, because a career record survives a year only if the person whose career it is can
read it end to end and correct it. [Why it works this way](docs/WHY.md) has the whole argument,
including what it costs.

Plain text in Turtle: readable in any editor, versionable in Git, parsed by any graph library. Keep
it in a repo you control so it outlives any single tool, including this one.

### Documentation

| | |
|---|---|
| [Quickstart](docs/QUICKSTART.md) | Install to first resume, ten minutes |
| [Concepts](docs/CONCEPTS.md) | The vocabulary, on one screen |
| [Why it works this way](docs/WHY.md) | The reasoning behind every design decision |
| [Commands](docs/SCRIPTS.md) | The `jsk` command: every subcommand, flags, dependencies, exit codes |
| [The knowledge base format](plugins/jsk/skills/jsk/references/kb-format.md) | Every section, class and predicate of `career/kb.ttl`, and what goes in each |
| [Architecture](docs/ARCHITECTURE.md) | For anyone editing this repo |
| [The resume file](plugins/jsk/skills/jsk/references/resume-format.md) | `resume.json`: every key, and the rule that its only prose is the summary |

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
