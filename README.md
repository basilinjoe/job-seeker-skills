# job-seeker-skills

Claude skills for job seekers. Currently ships one plugin: **Career OKF**.

## Career OKF

Most resume tools start from a blank page every time. This one keeps your career in a portable
knowledge base — a folder of linked Markdown files in
[Open Knowledge Format](https://openknowledgeformat.com/) — and treats a resume as one *rendering*
of it.

Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.

### What makes it different

**Every document is rendered from JSON, never hand-built.** The bundle compiles to a
[URS](plugins/career-okf/skills/career-okf/references/urs-spec.md) record — a universal resume schema
this project defines — and the LaTeX/PDF, both `.docx` variants and the plain text are all emitted
from that one file. Two hand-built documents have to agree about every date, bullet and number, and
they stop agreeing the moment one is edited; usually silently, usually in the copy that gets sent.

**The same record renders correctly in different markets.** A region profile decides what each market
may and must not see: a photograph and date of birth are conventional on a Gulf resume and a liability
on an Australian one; India expects academic grades on a CGPA scale, a father's name and a declaration
block; the Gulf screens visa status and transferability before anything else. Australia, India and the
UAE ship as profiles, and adding a market is a JSON file rather than a schema change.

**Tailoring cannot invent, structurally.** A tailored resume is a *view*: it references evidence by
id, orders it, and redacts. The validator rejects free text inside a view, so a posting the record has
no evidence for produces nothing to point at rather than a plausible new bullet.

**Numbers are checked against their metrics.** Every numeral in a bullet must appear in a structured
metric on that bullet, or `validate_urs.py` fails the record before anything renders. It is the check
that catches a rewritten bullet quietly inflating a figure.

**Resumes are verified, not assumed.** `check_ats.py` inspects the generated `.docx` for the things
that make applicant tracking systems silently mangle a resume: tables, text boxes, header/footer
content, section words that appear in prose but never in a heading, any leftover bracketed
placeholder, an unparseable phone number, arrow glyphs that fuse job titles when stripped. A resume
that fails the checker is not delivered.

**Four gates, not one, because a checker verifies that a document parses — not that it is correct.**
Record (`validate_urs.py`), parse (`check_ats.py`), prose (`check_prose.py`), and render: convert to
PDF and look at every page.
Bullets that rendered as tofu boxes, headings that silently resolved to a theme font, and a bullet
written in the third person all passed the parse gate, correctly. Only the render gate sees the first
two. Without a renderer, a resume is marked unverified rather than assumed fine.

**Two variants, because readability and parsing conflict.** A presentation variant for humans, an
ATS-maximal variant for portals, plus plain text for paste-in boxes.

**Every fact carries provenance.** `confirmed` (you said it), `inferred` (written for you, needs
sign-off), `needs-verification` (a known gap). Nothing inferred reaches a resume unconfirmed.

**Tailoring is selection, never invention.** Job descriptions are scored against structured metadata
on each project by `score_projects.py`, which reads its requirements from the target file's own
frontmatter — so the document you review is the one that produced the ranking, and re-running it next
month gives the same answer. It reports what each project *failed* to match, and tells you where you
fall short instead of flattering you.

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

### The resume standard

`references/urs-spec.md` defines **URS**, a JSON standard for the career record, with the schema in
`schema/urs-v1.schema.json` and region profiles in `schema/profiles/`. It exists because JSON Resume
is a JSON container around unstructured prose: a bullet is a bare string, so nothing can verify a
metric; nothing carries an id, so tailoring means copy-and-mutate and the copies drift; nothing
carries provenance, so "I measured this" and "a model wrote this" look identical; and a promotion has
to be modelled as two duplicate employers.

URS keeps a mapping to JSON Resume at conformance level 0, so adopting it costs nothing and is
reversible. `schema/example.resume.json` is a complete worked document.

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
python3 scripts/validate_urs.py resume.json --level 2           # the record, before rendering
python3 scripts/render_resume.py resume.json --out . --pdf      # .tex/PDF + both .docx + .txt
python3 scripts/check_ats.py resume.docx                        # presentation variant
python3 scripts/check_ats.py resume.docx --strict               # ATS-maximal variant
python3 scripts/check_prose.py resume.docx                      # the writing rules
python3 scripts/score_projects.py ./my-career target.md         # needs pyyaml
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

`render_resume.py` resolves the record once — selection, ordering, provenance filtering, profile
gating, ASCII folding, date formatting — and the three emitters translate that plan into markup
without deciding anything. That split is what guarantees the `.docx` and the PDF cannot say different
things. Without a TeX engine it writes the `.tex` and reports the resume **unverified** rather than
implying a PDF nobody rendered.

`validate_urs.py`, `render_resume.py`, `check_ats.py` and `init_bundle.py` are standard library only
(`validate_urs.py` also checks the full JSON Schema when `jsonschema` happens to be installed). On Windows use `python` or `py -3`
in place of `python3`.

### Tests

```bash
python -m unittest discover -s tests
```

Standard library `unittest`; fixtures are generated into temp directories, nothing is committed.
Every test pins a specific documented rule — the checker is the gate, so it does not go unchecked.

## Licence

MIT
