# job-seeker-skills

Claude skills for job seekers. Currently ships one plugin: **Career OKF**.

## Career OKF

Most resume tools start from a blank page every time. This one keeps your career in a portable
knowledge base — a folder of linked Markdown files in
[Open Knowledge Format](https://openknowledgeformat.com/) — and treats a resume as one *rendering*
of it.

Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.

### What makes it different

**Resumes are verified, not assumed.** `check_ats.py` inspects the generated `.docx` for the things
that make applicant tracking systems silently mangle a resume: tables, text boxes, header/footer
content, section words that appear in prose but never in a heading, any leftover bracketed
placeholder, an unparseable phone number, arrow glyphs that fuse job titles when stripped. A resume
that fails the checker is not delivered.

**Two variants, because readability and parsing conflict.** A presentation variant for humans, an
ATS-maximal variant for portals, plus plain text for paste-in boxes.

**Every fact carries provenance.** `confirmed` (you said it), `inferred` (written for you, needs
sign-off), `needs-verification` (a known gap). Nothing inferred reaches a resume unconfirmed.

**Tailoring is selection, never invention.** Job descriptions are scored against structured metadata
on each project, and the tool tells you where you fall short instead of flattering you.

### Install

As a plugin, via marketplace:

```
/plugin marketplace add basilinjoe/job-seeker-skills
/plugin install career-okf@job-seeker-skills
```

Or copy the skill directly into Claude Code:

```bash
git clone https://github.com/basilinjoe/job-seeker-skills.git
cp -r job-seeker-skills/plugins/career-okf/skills/career-okf ~/.claude/skills/
```

On Windows (PowerShell):

```powershell
git clone https://github.com/basilinjoe/job-seeker-skills.git
Copy-Item -Recurse job-seeker-skills\plugins\career-okf\skills\career-okf $env:USERPROFILE\.claude\skills\
```

Works in Claude Code and Claude Cowork.

### Use

Describe what you want; the skill routes to the right mode.

| Mode | When |
|---|---|
| `setup` | First run, or importing an existing resume |
| `braindump` | You have something to say about your work |
| `resume` | You need a resume — two verified variants plus plain text |
| `tailor` | You have a specific job description |
| `refresh` | Periodic top-up: what changed, what numbers moved |
| `gaps` | Resolve unanswered questions and unverified claims |

```
/career-okf setup
/career-okf tailor      # then paste the job description
```

**Suggested rhythm.** Something ships → `braindump`, five minutes, while you remember the details.
Every quarter → `refresh`. Before applying → `gaps`, then `resume`. Specific role → `tailor`.

### Bundle layout

```
career-okf/
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
translation layer. Keep it in a repo you control so it outlives any single tool.

### Scripts

The skill runs these for you. To run them yourself, from the skill directory:

```bash
python3 scripts/init_bundle.py ./my-career --name "Your Name"   # scaffold
python3 scripts/validate_bundle.py ./my-career                  # needs pyyaml
python3 scripts/check_ats.py resume.docx                        # presentation variant
python3 scripts/check_ats.py resume.docx --strict               # ATS-maximal variant
python3 scripts/check_prose.py resume.docx                      # the writing rules
python3 scripts/fit_pages.py resume.docx --target-pages 2       # needs LibreOffice + pymupdf
```

`check_prose.py` is the sibling gate. `check_ats.py` verifies a document parses; this verifies it
reads — third person, unresolved placeholders, sentences that stop before their object, phrases that
read as junior, bullets repeated across projects, and bullets that clear their throat before the
verb. A resume in the third person is not a parsing defect, so nothing was catching it.

`fit_pages.py` renders the document, measures which block spilled and how much room the page
actually had, then applies density levers in a fixed order — spacing, bullet spacing, margins, font
size — stopping at the 10pt / 0.5" floors instead of crossing them. If two pages are unreachable
without a breach it exits non-zero and says so, because the remedy then is to cut evidence, not to
shrink type.

`check_ats.py` and `init_bundle.py` are standard library only. On Windows use `python` or `py -3`
in place of `python3`.

### Tests

```bash
python -m unittest discover -s tests
```

Standard library `unittest`; fixtures are generated into temp directories, nothing is committed.
Every test pins a specific documented rule — the checker is the gate, so it does not go unchecked.

## Licence

MIT
