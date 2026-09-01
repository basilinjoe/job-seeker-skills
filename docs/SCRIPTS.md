# Scripts

The skill runs these for you. This page is for running them yourself.

It is all one command. `pip install 'jsk-okf[all]'` puts `okf` on your PATH; `python3 -m jsk_okf` is
the same entry point where it is importable but not on PATH, and on Windows use `python` or `py -3`
in place of `python3`.

Every subcommand below also exists as a module you can run or import directly —
`python3 -m jsk_okf.check_ats resume.pdf`, `from jsk_okf.okf_compile import load`. The headings name
both. Fifteen loose scripts under the skill directory is what this used to be; there is no path to
get right any more.

## The whole surface

```bash
okf doctor                  # what works on this machine
okf new ./my-career --name "Your Name"
okf project add --bundle ./my-career --title "…" --role … # write a concept
okf compile ./my-career     # the bundle as the record
okf validate resume.json         # a record
okf validate acme.posting.json  # or a posting
okf validate acme.gaps.json     # or an assessment
okf validate ./my-career        # or a bundle - it dispatches
okf render resume.json --out . --pdf
okf check resume.pdf        # both document gates, one pass
okf gates . --view view_acme --bundle ./my-career  # all three mechanical gates
okf score record.json acme.posting.json
okf fit resume.tex --target-pages 2
okf preview resume.json --out ./looks
okf migrate ./my-career          # report; --apply to write
okf pipeline ./my-career         # the week's board
```

Each read subcommand reaches the module documented below it with the same arguments and the same
exit code, so everything on this page is true through `okf`. Some are called in this interpreter and
some in a child one; that is an implementation detail and never changes a verdict.

The write subcommands have no separate module of their own. The write layer is a package,
`jsk_okf/authoring/`, and `okf` is how it is called.

### Writing to a bundle

Sixteen nouns, each with its own verbs. Every one takes `--bundle DIR`, `--dry-run`, `--json` and
`--set key=value`, and each derives the files a change implies — the directory index entry, the
`log.md` row, the vocabulary term — rather than leaving them to be remembered.

```bash
okf project add|set|retire|rm     --bundle ./my-career [...]
okf role add|set|retire|rm        --bundle ./my-career [...]
okf org add|set|retire|rm         --bundle ./my-career [...]
okf education add|set|retire|rm   --bundle ./my-career [...]
okf bullet add|set|rm|mv          --bundle ./my-career [...]
okf skill add|set|rm|mv           --bundle ./my-career [...]
okf credential add|set|rm|mv      --bundle ./my-career [...]
okf metric add|set                --bundle ./my-career [...]
okf capability add                --bundle ./my-career --term … --theme …
okf question add|resolve          --bundle ./my-career [...]
okf log                           --bundle ./my-career --message "…"
okf reindex                       --bundle ./my-career
okf posting add                   --bundle ./my-career [...]
okf posting requirement add       --bundle ./my-career [...]
okf gaps write                    --bundle ./my-career [...]
okf view create|set|include       --bundle ./my-career [...]
okf application file|event        --bundle ./my-career [...]
```

Three things about them are worth knowing before you read the reference:

- **The refusals are the product.** `project add --role X` refuses when `roles/X.md` does not
  exist, and that one is load-bearing: no gate reports a dangling role, `okf_compile.py` refuses on
  one, and `okf score` compiles — so without the check a bad reference surfaces as a crash in the
  middle of a tailoring run rather than as a red line at ship time. `bullet add --metric M` refuses
  a metric that is not a row in `achievements/metrics.md`, for the same class of reason.
- **A `set` re-stamps `status: inferred`** unless `--status confirmed` is passed. Change half a
  sentence of a confirmed claim and the status would otherwise assert that somebody signed off on
  text that no longer exists.
- **Ids get written down.** Any bullet, skill or credential mutation first materialises the ids the
  compile was deriving from position, so a view that names one cannot be silently repointed by a
  later insertion above it.

`plugins/jsk/skills/jsk/references/write-commands.md` has the whole surface, the publish order and
the boundary.

Three read subcommands also do more than forward:


- `okf check` runs the parse gate *and* the prose gate on one file, and keeps going after the first
  one fails, because a document with parse problems usually has prose problems too. It exits with the
  worse of the two codes, and reminds you that the record and render gates are separate.
  `--only parse` or `--only prose` runs one of them — for re-checking a single file after a single
  repair, which is the call that used to have to reach past `okf` to `check_ats.py` directly. A
  single-gate run never closes by saying both passed; it names the three gates that did not run.
- `okf gates` runs the record, parse and prose gates over a whole rendered output directory in one
  process — the five invocations a hand-run verification used to make. It is documented in full
  below, beside the checkers it calls. `okf check` is unchanged and stays: it is the right thing for
  one file.
- `okf validate` sends a directory to `validate_bundle.py` and a `.json` file to `validate_urs.py`,
  both in this interpreter rather than a child one. `validate_bundle.py` ran its whole check at
  import and exited from module scope until it grew a `main(argv)`, which is why this dispatch alone
  used to spawn: 204 ms to 132 ms on a fresh bundle, medians of 11.
  A `.posting.json` or `.gaps.json` is refused by name: those are archived UJD and UGS documents
  from an application already sent, both formats are retired, and a frozen document is meant to be
  re-read by a person rather than re-checked by a tool.

## Exit codes

Uniform across every subcommand:

| Code | Means |
|---|---|
| `0` | passed |
| `1` | failed — a real finding, or a dependency missing that makes the answer unknowable |
| `2` | you called it wrong — bad usage, or a file that is not there |

Nothing here passes quietly when it could not do its job. A page count nobody measured is a page
count nobody knows.

## Start here

### `okf doctor`

The `preflight.py` module.

```bash
okf doctor                 # what works on this machine
okf doctor --verify        # prove it, end to end
okf doctor --json          # machine-readable
okf doctor --bundle PATH   # also check a bundle
```

`--verify` renders the shipped example document and runs the parse and prose gates on the result, so
a pass means the pipeline genuinely works here rather than looking like it should.

Verdicts: `READY` · `READY, with gaps` · `BLOCKED` (the install is broken) · `BROKEN` (the toolchain
is present but failed its own gates — that is a bug in the skill, not in your setup).

Gaps are reported by what they *disable*, not by package name. Runs on a bare Python: a preflight
that needs installing first is not a preflight.

### `okf new`

The `init_bundle.py` module.

```bash
okf new ./my-career --name "Your Name"
```

Creates an empty bundle skeleton. No dependencies.

## The record

### `okf compile`

The `okf_compile.py` module.

```bash
okf compile <bundle> --quiet
okf compile <bundle> --dump-record record.json
okf compile <bundle> --dump-record - --view view_acme
okf compile <bundle> --dump-record - --no-views
okf compile <bundle> --no-views --compact --dump-record record.json
okf compile <bundle> --no-views --for score --compact --dump-record record.json
```

Builds the record from the concepts, deterministically. Nothing is written unless `--dump-record`
asks for it, and what it writes is for reading rather than editing: the next compile overwrites
whatever you changed.

**It never reads `tailoring/applications/`.** The archive is frozen and nothing downstream compiles
from it — but the reason this is a rule rather than an optimisation is that a frozen
`<stem>.view.md` declares the same view id as the live working copy it was made from, and the
archived one won. A tailoring run rendered a selection made months earlier and nothing said so.
Skipping the archive also took a compile of a hundred-application bundle from 0.94s to 0.44s, which
is the smaller half of the argument.

`--view ID` is repeatable; `--no-views` emits none. Both affect only what is emitted — every concept
is still read. A bundle keeps one working view per target and retires none of them, so someone who
has answered a hundred postings compiles a hundred views: half of `record.json` by volume, in a file
several agents read on every run, and ninety-nine of them irrelevant to the application being worked
on. Scoring and the pipeline read no view at all. Narrowing to one took `record.json` from 64,263
bytes to 31,206.

**The default is still every view**, deliberately: `validate_urs.py <bundle>` checks all of them, and
a broken view nobody is rendering today is still a broken view. An unknown id fails and prints the
ids that are on disk, capped at eight. Passing `--view` and `--no-views` together is exit 2.

`--compact` writes the record without `indent=2` and changes nothing else — the same object, parsed
identically, a third smaller. On the hundred-application bundle, `--dump-record` fell from 32,190
bytes to 20,310. Whitespace no model needs, in a file several agents read on every run.

`--for score` emits each project with only the keys a ranking runs on — `id`, `title`,
`capabilities`, `technologies`, `domains`, `seniority`, `strength`, `period`, `engagement` — and
emits `narratives`, `education` and `credentials` empty. `projects[]` is 80% of the record and 61%
of that is achievement prose no scorer reads a word of; with `--compact` the record falls to 12,840
bytes, 60% off. `score_projects.py` ranks identically off it, which is the property that makes the
flag a saving rather than a different answer.

Those are **record** keys and not the concept keys of a project file — `title` is what
`build_projects` writes, and a concept's `recency:` compiles into `period`, a URS Period, which is
what the scorer actually reads. `engagement` is kept although the scorer never reads it, because
without it `engagements[].projects` points at projects the record no longer describes.

It implies nothing about views, so combine it with `--no-views`. **The projection is computed here
rather than by the caller**, so there is exactly one definition of what a scorer needs — a second
list of keys somewhere else is the transcription problem this format exists to avoid. `--for` takes
one value today, `score`; an unknown value is exit 2 listing the valid ones, because a profile name
that silently did nothing would read as a saving and be a missing field.

**Do not reach for `--for score` from anything that writes prose.** It drops exactly the achievement
text a bullet is retuned from, and a clause retuned from a record that does not hold it is a clause
written from scratch.

**The walk reads only what the record is built from.** Under `tailoring/` only `*.view.md` is
opened — a Job Posting and a Gap Assessment are parsed by nobody downstream — and when no view is
wanted at all, `tailoring/` is skipped entirely. On the hundred-application bundle that is 345
concepts parsed to build a record out of 41, down to 45:

| | before | after |
|---|---|---|
| `okf_compile <bundle>` | 973ms | 231ms |
| `okf_compile --no-views` | 1,124ms | 143ms |
| `okf_compile --no-views --for score --compact` | 1,089ms | 134ms |

The default record and the `--no-views` record are byte-identical before and after. The one input
whose record could change is a content concept filed under `tailoring/` and not named `*.view.md` —
a `type: Project` sitting there no longer reaches the record. No documented bundle shape puts one
there, and `bundle-spec.md` now says so plainly.

**`census()` does its own full walk, deliberately**, and did not get faster. It feeds
`validate_urs.py`'s conservation check, whose type map includes `View`: narrowing the shared walk
would have left the census reading zero Views on disk under `--no-views`, and the gate would have
cheerfully agreed that nothing had been dropped. That gate exists because a hardcoded `views: []`
went unnoticed for months. A slower census and an honest gate is the right way round.

### `okf validate`

The `validate_urs.py` module.

```bash
okf validate <bundle | resume.json>
okf validate <bundle | resume.json> --strict
okf validate <bundle | resume.json> --max-findings 0
```

The **record gate**. Run it before anything renders. Checks that the record is coherent and that
every numeral in a bullet traces to a structured metric on that bullet.

Two of its checks are about what is *not* there, because nothing else in the pipeline can see an
absence. **Coverage** fails a project rated `strength: 4` or better whose `# Bullets` block is
empty, and warns below that; it also warns where an employer has no evidence under it at all.
**Conservation** compares `okf_compile.census()` - what the bundle holds on disk - against what the
compiler emitted, and fails a concept type that produced an empty record key. Cardinality is not
asserted, because it is legitimately not 1:1 (9 Roles compile to 4 engagements, 1 Skill Set to 83
skills); only that a type present on disk produces something.

Conservation buys its honesty with a full walk of its own, which is why this gate went from 1,082ms
to 686ms rather than following the compile all the way down. **A census that sees only what the
compile chose to read cannot notice what the compile stopped reading**, and noticing that is the
entire job.

Conservation needs the bundle, so it is skipped when the target is an archived `resume.json`.
`--strict` promotes every warning to a failure.

`--max-findings N` prints at most N failures and N warnings, default 25, `0` for every one — the same
flag name, the same default and the same `... and N more` line as `validate_bundle.py`, because two
gates that truncate differently are two gates people read differently. On the bundle that prompted
it, the default took the gate's output from 42,425 characters to 2,252.

**The header always carries the true `FAIL n   WARN n`.** Truncating a list is a reading aid;
truncating a count is a lie, and a gate that under-reports its own findings is worse than one that
scrolls.

### `okf render`

The `render_resume.py` module.

```bash
okf render <bundle | resume.json> --out DIR --view view_au_default
okf render <bundle | resume.json> --out DIR --view view_acme --pdf
okf render <bundle | resume.json> --out DIR --view view_acme --region au
okf render <bundle | resume.json> --out DIR --view view_acme --pdf --ats-max
```

One record to `.tex` (and PDF with `--pdf`) plus `.txt`. The PDF is the only rendered deliverable;
`--ats-max` chooses which variant it holds rather than adding a second file.

**`--view` is required wherever the record holds more than one**, and leaving it out is exit 2 with
the ids listed — usage, not failure, because nothing is wrong with the record and the missing thing
is the one decision only a person can make. A record holding exactly one view still renders without
it.

| Flag | Does |
|---|---|
| `--out DIR` | where to write (default `.`) |
| `--pdf` | also run the TeX engine |
| `--view ID` | which view to render — required where the record holds more than one |
| `--region CODE` | apply a region profile |
| `--profile PATH` | a profile file directly |
| `--format` | `all` (default), or one of `latex` / `txt` |
| `--ats-max` | render the PDF in the ATS-maximal variant (shorthand for `--profile ats-maximal`) |
| `--template NAME` | the visual template (default `monolith`) |
| `--list-templates` | print the templates with what each is for, and exit |
| `--name` | override the output filename stem |

**With `--pdf`, a run that produced no PDF exits 1** and says **UNVERIFIED**. It used to record the
failure as a passing note and exit 0, so a caller could ask for a PDF, be told in passing there wasn't
one, and still see success.

**The page count is measured off the PDF**, with `pymupdf`, and printed only with `--pdf`:

```
  pages  Priya_Raman_Resume.pdf: 1 page against a budget of 2
```

It used to print the budget alone, which is the number somebody asked for rather than the number they
got — the resume that prompted the fix rendered on one page against a budget of two and said so
nowhere. Over budget is named (`- OVER BUDGET, run fit_pages.py`) and not failed: `fit_pages.py` owns
that verdict, and it is the script that can do something about it. Without `pymupdf` the line says
the budget and says it was not measured, which is the honest version of the same sentence.

`--template` and `--ats-max` are different axes and compose. The variant decides what the document
says; the template decides how it looks. All five templates extract to identical text, so the choice
is about the reader and never about the parse. An unknown name is a usage error rather than a silent
fall back to the default, because a resume rendered in a template nobody chose is a resume nobody has
looked at — and it would look perfectly fine. See `references/templates.md`.

### `okf preview`

The `preview_templates.py` module.

```bash
okf preview resume.json --out DIR
okf preview resume.json --out DIR --view view_acme --only meridian,ember
```

The same record rendered in every template, with the page count for each, so the look is chosen by
looking. Writes `DIR/<template>.pdf` and `.tex`, plus a `.png` of the first page where `pymupdf` is
installed.

Density is the one difference between templates that is not a matter of taste: the same record is
one page in a dense template and two in an airy one, and a two-page resume where a one-page resume
was available is a decision worth making on purpose.

| Flag | Does |
|---|---|
| `--out DIR` | required — previews are scratch, not deliverables |
| `--view ID` / `--region CC` / `--ats-max` | passed straight through to `render_resume.py` |
| `--only A,B` | just these templates |

Exit 0 = every template rendered. Exit 1 = at least one did not, and that is reported rather than
worked around: a template that does not build is not a template, and the others may be about to
break too. Exit 2 = usage, or no TeX engine.

## The gates on the document

### `okf check --only parse`

The `check_ats.py` module.

```bash
okf check --only parse resume.pdf             # the rendered deliverable
okf check --only parse resume_ATS.txt --strict  # the ASCII variant
```

The **parse gate**. Reads the PDF's text layer (or the `.txt`) for what makes applicant tracking
systems mangle a resume: text that does not extract at all, section words that appear in prose but
never in a heading, leftover bracketed placeholders, unparseable phone numbers, bullet glyphs a
parser will not map, and arrow glyphs that fuse job titles when stripped.

The structural checks — tables, text boxes, header content, second columns — are gone. One LaTeX
template produces every render and cannot express any of them, so the check moved from the output to
a golden-file test on the template, where it is proved rather than sampled. Needs `pymupdf` for a
PDF; the `.txt` path is standard library only.

### `okf check --only prose`

The `check_prose.py` module.

```bash
okf check --only prose resume.tex
okf check --only prose resume_ATS.txt
```

The **prose gate** — the writing rules `check_ats.py` cannot see. Third person, unresolved
placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
across projects, bullets that clear their throat before the verb. It reads the `.tex` rather than the
PDF, because a bullet is an unambiguous `\item` there and needs no library to find. No dependencies.

### `okf gates`

```bash
okf gates <out-dir> --view <id>
okf gates <out-dir> --view <id> --bundle ./my-career --pages 2
okf gates <out-dir> --view <id> --json
okf gates <out-dir> --view <id> --max-findings 0
```

The record, parse and prose gates over one rendered output directory, in **one process**. It is the
five invocations a hand-run verification used to make — `validate_urs.py` on the bundle,
`check_ats.py` on the PDF and again on the `.txt` with `--strict`, `check_prose.py` on the `.tex`
and again on the `.txt`. It imports the checkers rather than shelling out to them, and gives them
the same arguments, so the findings and the exit code are the ones the five commands produce. That
equivalence is what it is tested on.

`check_ats.py` and `check_prose.py` grew a `main(argv)` entry point so it could: same CLI, same
arguments, same output to the character, now callable without a subprocess. That entry point is
load-bearing rather than incidental, so it is documented here beside their CLIs.

What it saves is exactly four interpreter starts — about **0.6x** the wall clock:

| | five commands | `okf gates` |
|---|---|---|
| 100-posting bundle | 723ms | 461ms |
| ordinary bundle | 643ms | 381ms |

What remains is the compile and the `pymupdf` import, and neither goes without a cache. There is no
cache here and there is not going to be one: a copy of something that can disagree with its source
is where every defect the 2.2.0 audit found came from. Read the ratio rather than the milliseconds —
the absolutes move with the machine.

The record gate is run against the **bundle**, which is what `--bundle` names. Not a dumped
`record.json`: `validate_urs.py` runs its conservation check only on the bundle path, so pointing it
at a record file would look like a pure speedup and quietly remove a gate — on the measured bundle,
75 failures reported instead of 376.

Three properties, each of them an existing rule here rather than a new one:

- **Every gate's output is printed verbatim, never summarised.** The person should see the evidence
  rather than take anyone's word for it. The section headers match `okf check`.
- **A missing input is `SKIPPED` and a failure.** A gate that did not run is not a gate that passed.
  Same behaviour and same wording as `okf check`. A path you *gave* that is not there is exit 2
  instead — omitting `--bundle` and mistyping it are different mistakes, and reporting them
  identically hides one. Both are non-zero.
- **It never attempts the render gate**, and closes with a line saying somebody has to open the PDF
  and read it. That gate is the one no command can have, and a command that exited 0 having silently
  skipped it would be the most dangerous thing in this directory.

`--view ID` is required and does no work. The record gate takes a bundle and the document gates take
files named after the person, so nothing in the run reads it — it is required because this output is
archived beside an application as evidence and nothing else in the output directory records which
view was gated. Do not remove it later as dead weight.

`--pages N` reports and never fails. It measures the PDF and prints `render_resume.py`'s own
over-budget line, reused rather than restated. Over budget is named rather than failed everywhere in
this pipeline, because `fit_pages.py` owns that verdict and is the script that can act on it.

`--max-findings N` caps how many findings each gate lists — the same flag name and the same default
as `validate_urs.py` and `validate_bundle.py`, because two gates that truncate differently are two
gates people read differently. The header counts stay true regardless: truncating a list is a
reading aid, truncating a count is a lie.

`--json` carries each checker's whole text in `gates[].output`, beside `gate`, `command`, `status`
and `exit`. It always includes a `render gate` entry with `status: "UNVERIFIED"` and `exit: null`,
so **the machine-readable form cannot report the render gate as passed either.** That is what makes
`--json` safe to consume here: it is the same evidence in a different envelope, never a summary.

The exit code is the worst gate's: `0` all passed, `1` any failed, `2` called wrong.

## The bundle

### `okf validate`

The `validate_bundle.py` module.

```bash
okf validate ./my-career
okf validate ./my-career --scope projects        # only that subtree
okf validate ./my-career --exclude-archive       # skip the frozen archive
okf validate ./my-career --max-findings 0        # print every one
```

Bundle is well-formed. Needs `pyyaml`. Run it after any change to the bundle.

It also checks the **tailoring layout**, which the link checker cannot see: a link only breaks when
its target is missing, and what goes wrong in `tailoring/` is the opposite — a file that is there and
should not be, or a companion the layout requires and nobody wrote. It reports a working posting
superseded by a `.posting.md` and not marked, an assessment or view with no posting beside it, an
application naming a frozen input that does not exist, an application that cannot name what it
answered or rendered from, a `.resume.json` copied beside an application, and a stem that is not
`<yyyy-mm-dd>-<company>-<role>`. From revision 7 it also reports an application still sitting
directly in `tailoring/applications/` and a subdirectory there that is not a year — both meaning the
migration was never run. Below revision 7 neither fires, because the flat shape is correct there.

| Flag | Does |
|---|---|
| `--scope SUBDIR` | validate one bundle-relative subtree, so a change to `projects/` is checked in a fraction of the time |
| `--exclude-archive` | skip `tailoring/applications/`, which at a hundred applications is most of the files and none of the ones you just edited |
| `--max-findings N` | print at most N errors and N warnings, default 25; `0` prints every one |

**A finding on a frozen copy is a warning, not an error.** `<stem>.posting.md`, `<stem>.gaps.md`,
`<stem>.view.md` and the r2-era `<stem>.target.md` may not be edited — `bundle-spec.md` says so, and
an archive that can be edited is not an archive. An error in one is therefore a red nobody is
permitted to clear, and *a gate that cannot go green is a gate people stop running*. The
application's own `<stem>.md` stays an error: its `# Timeline` is appended to for as long as the
process is live, so anything wrong in it is something somebody can fix.

`--max-findings` exists because the first run against a large real bundle produced several hundred
lines and the first error — the one that caused the rest — scrolled away. It caps warnings as well as
errors, and the count of what was withheld is always printed: a truncated report that does not say it
is truncated is worse than a long one. `--scope` reports what it could not cover for the same reason.
A run that checked a tenth of the bundle and looks like a clean one is the failure both of these
flags are built to avoid.

### `okf migrate`

The `migrate_bundle.py` module.

Brings a bundle built on an earlier layout up to the current one.

```bash
okf migrate <bundle>            # report what would change
okf migrate <bundle> --apply    # make the changes
```

`index.md` carries `okf_bundle:`, an integer layout revision. An absent stamp means revision 1,
because every bundle created before the stamp existed has no way to say so.

| Revision | Shape |
|---|---|
| 1 | applications point at a mutable target file via `target:` |
| 2 | the posting is frozen beside each application as `<stem>.target.md` |
| 3 | an application's outcome is derived from an append-only `# Timeline` |
| 4 | the posting is a UJD document, `<stem>.posting.json` — superseded by 5 |
| 5 | roles and projects carry their relations in frontmatter, and the posting is `<stem>.posting.md` again |
| 6 | the working posting r5 replaced is marked `superseded_by:`, and every live reference points at the posting |
| 7 | the archive is partitioned by submission year — `tailoring/applications/<yyyy>/` |

Revisions 4 and 5 collapse into one step. A bundle below either converts its postings straight to
Markdown, because running revision 4's step first would write a document whose only reader was
deleted along with the format. A posting already frozen beside a sent application is left exactly
as it is.

Revision 6 cleans up after 5. That step converted every working posting to `<stem>.posting.md` and
left the source alone, which was right — deleting somebody's only copy of an advertisement is not a
trade a migration gets to make — but it could not say so on the file, so a migrated bundle held two
documents per job and the indexes still pointed at the retired one. Revision 6 writes
`superseded_by:` onto the source and moves every live reference to the posting. It still deletes
nothing.

Revision 7 files the archive by year. Four Markdown files and the documents sent, per submission, is
several hundred files in one directory at a hundred applications, and nothing there can be found by
looking. The step reads the year off the stem, falls back to the `submitted:` date where the stem
predates that convention, and puts anything it cannot date in `undated/` — reported, never guessed.
It writes the `index.md` for each year directory as it goes. A moved file is one directory deeper, so
every relative path in it that leaves its own directory gains one `../`; the companions sharing its
stem are beside it and are untouched. It does not partition by outcome, and `bundle-spec.md` says
why: the outcome is derived from the timeline and has to stay derived.

The sent documents are the hard part, because `<Name>_<Company>_Resume.pdf` shares no stem with the
application it belongs to and no key in the `Application` concept names it. Three signals are tried,
strongest first: the filename carries an application's stem, the application's log links to the file,
or there is only one application it could possibly belong to. Anything still unclaimed is **left where it is
and reported** for hand-filing. A resume filed under the wrong application is a worse record than one
nobody moved, and company names in a filename are exactly close enough to make that mistake
plausible.

What counts as a live reference is deliberately narrow: path-valued frontmatter keys anywhere, and
Markdown links in an `index.md`. Prose elsewhere is left alone, because a link in a project file or
in `log.md` records what somebody wrote at the time, and the retired file still exists and now names
its successor. Archives are skipped outright, identified by position rather than by `frozen: true` —
the snapshots the r1 → r2 step wrote predate that key, so trusting it would rewrite the oldest
archives first.

Report mode **exits 1 when changes are pending**, which is what makes it usable as a check: an
out-of-date bundle is detectable without writing to it. `--apply` exits 0 only when nothing is left
for a person.

Nothing is deleted, and the run is idempotent. Where the migration cannot establish a fact — a
posting that was never captured, a snapshot taken months after the submission it belongs to — it
**reports the gap and marks what it wrote `needs-verification`** rather than filling it in. A
reconstructed posting that claims to be the original is precisely the failure the four gates exist to
prevent, and the tool is not exempt from its own rule.

Standard library only. Frontmatter is edited line by line rather than round-tripped through a YAML
parser, so comments, key order and quoting style survive and the change is legible in a diff.

### `okf pipeline`

The `pipeline.py` module.

What the job search needs from you this week, derived from every application's `# Timeline`.

```bash
okf pipeline <bundle>                   # what needs attention, most urgent first
okf pipeline <bundle> --all             # the full board, closed applications included
okf pipeline <bundle> --company NAME    # every application to one employer
okf pipeline <bundle> --as-of DATE      # compute against a date rather than today
okf pipeline <bundle> --markdown        # a table, to paste into a file
okf pipeline <bundle> --top 30          # rows per block, default 15
okf pipeline <bundle> --json            # the whole board, for something else to read
```

`--company` is the "have I burned this one already" query, matched as a case-insensitive substring.
`mode-tailor.md` runs it as its first step, before a posting is written down: over a long search,
finding out after the resume is written that this company was applied to eleven weeks ago is a round
paid for twice.

`--top` caps each block rather than the report, because the board is a list of what to do today and a
hundred-row block is a list nobody reads. The default is 15 and the count of what was withheld is
printed with it. `--all` and `--json` are unbounded: one of them is asking for everything, and the
other is not being read by a person.

**Exit 0 when nothing needs attention, 1 when something does**, 2 when called wrong — the same
convention as `migrate_bundle.py`'s dry run, and what makes it usable as a scheduled check.

`--as-of` exists for two reasons: deterministic tests, and answering "what did this look like when I
last checked". A report whose output depends on an unstated clock can neither be tested nor compared
with itself.

Decides nothing on its own. Stage, staleness and next action all come from `pipeline_model.py`, which
is also what `validate_bundle.py` checks against and what `migrate_bundle.py` writes — one module
decides what an event means, so the board and the application files cannot disagree.

Needs `pyyaml`.

### `okf score`

The `score_projects.py` module.

```bash
okf score record.json acme.posting.json
okf score record.json acme.posting.json --markdown
okf score record.json acme.posting.json --as-of 2026
okf score record.json acme.posting.json --include-implicit
okf score record.json acme.posting.json --assume-technologies "python,aws"
```

Ranks the record's `projects[]` against the posting's `requirements[]`. Both sides are JSON, and that
is the point: the scorer and the gap analysis read **the same record**, so a ranking and a verdict
cannot disagree about what the record contains. Reports what each project *failed* to match.

Requirements marked `implicit` — ones the posting never stated — are excluded by default and the
exclusion is printed. `--include-implicit` scores them and prints that instead. An inference that
moves a ×3 term is an invented requirement, so neither choice is made silently.

Standard library only.

## Fitting

### `okf fit`

The `fit_pages.py` module.

```bash
okf fit resume.tex --target-pages 2
okf fit resume.tex --dry-run
okf fit resume.tex --in-place
okf fit resume.tex -o fitted.tex
```

Rewrites the density knobs in the `.tex`, recompiles, and measures the PDF that comes out. It applies
the levers in a fixed order — spacing, bullet spacing, margins, font size — stopping at the 10pt and
0.5" floors instead of crossing them. If the target is unreachable without a breach it exits
non-zero, because the remedy then is to cut evidence, not to shrink type.

It used to measure a `.docx` through LibreOffice while the PDF was what got sent. The two disagreed,
and a resume this reported as two pages shipped as three — a gate passing on a document nobody was
sending. It now measures the artefact that goes out.

Needs a TeX engine and `pymupdf`.

---

Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
