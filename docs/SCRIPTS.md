# Commands

The skill runs these for you. This page is for running them yourself.

It is all one command. `pip install 'jsk-resume[all]'` puts `jsk` on your PATH; `python3 -m jsk` is
the same entry point where it is importable but not on PATH, and on Windows use `python` or `py -3`
in place of `python3`.

Every subcommand below also exists as a module you can run or import directly —
`python3 -m jsk.gates.check_ats resume.pdf`, `from jsk.urs import plan`. The headings name both.

**The career is `career/kb.ttl`**, the graph record: one Turtle file in the old knowledge base's
section order, loaded and validated on every run. `jsk kb` changes it (through changesets) and
reads it back, `jsk match` ranks it against a posting, `jsk freeze` and `jsk event` record what
was sent and what came back, and the claims gate checks each `resume.json` against it. The
rendering half starts at the URS record written out of it, and carries that to a document
somebody can send. **Only `jsk migrate` reads a `user-knowledgebase.md`** - once, to move it
across.

## The whole surface

```bash
jsk doctor                       # what works on this machine
jsk new ./my-career --name "Your Name"     # career/kb.ttl and its log, at r1
jsk kb apply changes.trig        # change the graph record; `jsk kb --help` lists the rest
jsk match applications/<dir>/posting.ttl   # a posting against the career, through the vocabulary
jsk migrate user-knowledgebase.md   # the Markdown knowledge base to career/kb.ttl, once
jsk validate resume.json         # the record gate
jsk render resume.json --out . --view view_default --pdf
jsk check resume.pdf             # both document gates, one pass
jsk gates .                      # record, claims, parse and prose gates
jsk fit resume.tex --target-pages 2
jsk preview resume.json --out ./looks
jsk ship resume.json --out . --view view_default   # validate, render, gate
jsk freeze applications/<dir> --submitted 2026-09-08 --channel "Workday portal"
jsk event applications/<dir> screen-scheduled --date 2026-09-15   # what happened next
```

Each subcommand calls the module documented below it, in the same interpreter, with the same
arguments and the same exit code, so everything on this page is true through `jsk`. None of them
spawns a Python child: that cost a start-up and a fresh import per call, which was most of the wall
time of `jsk check`. The one exception is `jsk doctor`'s end-to-end run, which runs each module as
`python -m` on purpose — proving that entry point works from cold is what it is for.

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

### `jsk doctor`

The `jsk.preflight` module.

```bash
jsk doctor                 # verifies end to end
jsk doctor --quick         # skip the render
jsk doctor --json          # machine-readable
jsk doctor --kb PATH       # check a specific career/kb.ttl, or the workspace holding it
```

Bare `jsk doctor` renders the shipped example document and runs the parse and prose gates on the
result, so a pass means the pipeline genuinely works here rather than looking like it should.

Verdicts: `READY` · `READY, with gaps` · `BLOCKED` (the install is broken) · `BROKEN` (the toolchain
is present but failed its own gates — that is a bug in the skill, not in your setup).

Gaps are reported by what they *disable*, not by package name. Runs on a bare Python: a preflight
that needs installing first is not a preflight.

Without `--kb` it searches three directories down for `career/kb.ttl` - a `kb.ttl` counts only
inside a folder named `career`, and dot folders (`.jsk/`, `.git/`) are never searched. Searching by
filename rather than by a directory shape is deliberate — a bundle used to be recognised by the
folders inside it, so a half-created one was invisible here and reported as absent while the person
was looking straight at it.

With no graph record but a `user-knowledgebase.md`, the knowledge-base line is a **gap**, not a
FAIL: `knowledge base at …/user-knowledgebase.md (Markdown, not migrated)`, naming
`jsk migrate <path>`. The render path starts at `resume.json` and still works on such a machine,
and blocking on the migration would hide every other finding behind it. `--json` reports the two
apart: `knowledge_base` is the graph record or `null`, `markdown_knowledge_base` the Markdown
file or `null`.

### `jsk new`

The `jsk.kb` module.

```bash
jsk new ./my-career --name "Your Name"
jsk new ./my-career --name "Your Name" --force   # start career/kb.ttl over from the empty record
```

Writes a graph workspace:

| Path | Is |
|---|---|
| `career/kb.ttl` | the empty record in the canonical layout: a header naming the person (`k:kb j:name`) and every section banner, `# == Identity` to `# == Open questions`, at `j:revision 1` |
| `career/log.ttl` | `k:rev_1`, `j:by j:new`, holding kb.ttl's hash |
| `applications/README.md` | what each application directory holds |
| `.gitattributes` | `*.ttl text eol=lf` and `*.trig text eol=lf`, added to whatever is there already |

Both record files come out of the same writer and the same kb.ttl-then-log.ttl commit every
`jsk kb` write uses, so the record is **clean at r1** and `jsk kb apply` works on it straight away:
writes refuse a record that is unlogged or hand-edited, and a workspace that started any other way
would first have to be adopted. The `.gitattributes` lines matter on Windows: a checkout that
turned kb.ttl's line endings to CRLF would change the bytes whose hash `log.ttl` holds.

The empty record holds no identity: `k:person` arrives with the first changeset, like any other
entry, as `j:inferred` with a question - the name on the command line says whose record this is,
not that anyone confirmed how it should head a resume. Needs pyoxigraph, a dependency of the
package.

It refuses (exit 1, nothing written) when `career/kb.ttl` exists, or when a `user-knowledgebase.md`
is in the folder and no `career/kb.ttl` is - that career is already written down, and
`jsk migrate` moves it across checked; `jsk new` would leave it behind, and migrate refuses once a
kb.ttl exists. `--force` overrides both. Over an existing record it starts over **as the next
revision** - kb.ttl becomes the empty record, `log.ttl` keeps every earlier entry and gains one by
`new`, and git holds the old text - and it is refused where a frozen application carried an entry
the empty record would not have, or where `log.ttl` does not parse.

Guidance that the Markdown template carried in HTML comments is not in kb.ttl: a comment is not
part of the graph, and `jsk kb fmt` and `adopt` refuse a file holding one. What each section holds
is the format reference's job (`references/kb-format.md` in the skill), and every refused write
names what it refused.

## The record

### `jsk match`

The `jsk.graph.match` module, over the queries in `jsk.graph.queries`.

```bash
jsk match applications/<dir>/posting.ttl                 # the four sections, as Markdown
jsk match applications/<dir>/posting.ttl --cover 2       # a cover of at most two projects
jsk match applications/<dir>/posting.ttl --json --today 2026-09-24
```

A posting's requirements joined with the career through the vocabulary - the shipped `jsk/data/vocabulary.ttl` and the knowledge base's own additions. Reads the
whole workspace the posting sits in (`career/kb.ttl`, `applications/*/`) and validates it first;
any FAIL is printed and nothing is matched. Needs pyoxigraph, a dependency of the package.

**Requirements** puts each one in a bucket: `matched` (a project holds the concept, or a narrower
one within two hops - `via c:aks, 1 hop`), `near` (only an `implies` path, for a required one, or
only something broader), `missing`, `ambiguous` (the label names several concepts; the analyst
answers with `j:concept`), `candidate` (it names none), `implicit`. Evidence per project is
`confirmed` (a confirmed bullet shows it), `unconfirmed` or `tag` (only the project's tags say so).
**Ranking** scores by the table in `jsk-tailor-analyst.md` - required ×3, preferred ×1, strength
×2, recency +1 within three years and +0.5 at four to six, seniority +1 at or above the posting's -
the same arithmetic the retired `jsk index --rank` did, now over concepts rather than exact
strings. **Cover** is the smallest set of projects, at most `--cover` (default 3), carrying every
required requirement anything carries. **Questions** are derived from the gaps, never invented.

Exit 0 with the result - missing requirements included, since this is an assessment, not a gate;
1 when the workspace has a FAIL; 2 called wrong, or a path that is not
`applications/<dir>/posting.ttl`.

### `jsk kb`

The `jsk.graph.kbcli` module. One verb per operation on the graph record; `jsk kb --help` lists
them and `jsk kb <verb> --help` explains one. Every verb finds the workspace - the folder holding
`career/` - from the current directory, or takes `--root DIR`.

```bash
jsk kb apply changes.trig --dry-run      # the diff it would make, nothing written
jsk kb apply changes.trig                # merged, validated, written, logged
```

**`apply`** is how an agent changes `career/kb.ttl`: a changeset, in TriG, with four graphs. A
first braindump into the empty record `jsk new` writes (r1) - it applies as it stands:

```trig
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix op: <tag:jsk,2026:op#> .

op:changeset op:base 1 ; op:summary "Who she is, and the payments project, from the first braindump." .

op:add {
    k:person j:fullName "Priya Raman" ; j:email "priya@example.com" ; j:phone "+61 400 000 000" .
    k:org_meridian j:name "Meridian Health" ; j:relationship j:employer .
    k:pos_meridian_principal j:organisation k:org_meridian ;
        j:title "Principal Solution Architect" ;
        j:start "2023-07" ; j:state j:ongoing ; j:seniority j:architecture-ownership .
    k:prj_payments j:name "Payments platform" ; j:position k:pos_meridian_principal ;
        j:strength 4 ; j:recency 2025 ; j:uses c:kafka, c:payments ;
        j:headlineMetric k:met_settlement .
    [] j:project k:prj_payments ; j:rank 1 ;
        j:text "Cut settlement latency from 800 ms to 200 ms." ;
        j:cites k:met_settlement ; j:shows c:kafka .
    k:met_settlement j:subject "settlement latency" ; j:unit "ms" ; j:direction j:decrease .
    k:met_settlement.v1 j:of k:met_settlement ; j:baseline 800 ; j:value 200 ;
        j:confidence j:reported .
    c:payments a j:Domain ; j:label "payments" .
}
```

The other three graphs, against a record that has been growing for a while (the prefix block is
the same, and always all five lines):

```trig
@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix op: <tag:jsk,2026:op#> .

op:changeset op:base 7 ; op:summary "Tidying after the quarterly review." .
op:set    { k:prj_legacy j:strength 2 . }                     # replaces every value it names
op:retire { k:prj_intranet j:reason "Too old to earn a line." . }
op:delete { k:q_duplicate a op:Entry . k:ach_x j:shows c:java . }
```

`op:add` adds; a predicate that allows one value and already has one is refused - use `op:set`.
`op:set` replaces every value of each (entry, predicate) it names. `op:retire` dates the entry
today and keeps the reason. `op:delete` removes exact triples, or with `a op:Entry` the whole
entry - refused while anything points at it, since retiring is what keeps the history. `op:base`
is the log revision the changeset was drafted against: an entry changed after it is a conflict,
refused, to be re-read. The header's `op:summary` becomes the log entry's.

What apply does unasked: a new bullet (a `[]` with `j:project`) gets its id,
`ach_<project>_<three words of its text>`, never one the record has used. An entry whose claims
changed drops to `j:inferred`, and every entry left inferred gets a `q_` question unless one is
open. A metric version an application sent never changes: a new `j:value` becomes the next
version, and the one it replaces is closed. A changeset cannot confirm anything, cannot write
another file, cannot use blank nodes except for a new bullet, and cannot name a predicate the
ontology does not have (it suggests the nearest).

The record it would write is validated before anything is written, and so is the workspace
before it starts: a FAIL in the career, a hand edit not yet adopted, or a torn write refuses the
apply with the command that fixes it. Then `career/kb.ttl` is replaced, then `career/log.ttl`,
and a copy of what was written goes to `.jsk/kb.last.ttl` (a cache that ignores itself in git).
Two files cannot be replaced together atomically: a crash between them is detected on the next
load - `log-sync`, "the last write reached kb.ttl and not log.ttl" - not prevented. On Windows, a
file locked by an editor or a virus scanner is retried for about a second; if it stays locked
nothing is changed. Stdin (`-`) is refused: a pipe that never closes hangs the command.

```bash
jsk kb confirm k:ach_payments_cut_settlement_latency --answer "Yes: 800 ms before, 200 after, from the Grafana board."
jsk kb adopt                             # after a hand edit of kb.ttl
jsk kb fmt                               # after a jsk upgrade changed the layout
```

**`confirm`** is the only way an entry becomes `j:confirmed`, and it takes the person's answer in
their words: each id named is confirmed, every open question about it is answered today, and the
log entry keeps the answer beside the ids. An answer that says nothing - `yes`, `ok`,
`confirmed`, a placeholder - is refused, and one that reached the log by hand is flagged by
`answer-placeholder`. This is an instruction with an audit trail, not a proof that anyone asked.

**`adopt`** logs `kb.ttl` as it now is. Hand edits are legal; they are also invisible to the log
until adopted, so every write refuses until they are (`hand-edited`, a WARN, says so on every
load). Adopt lists every provenance the edit raised - an entry moved up to confirmed, added as
confirmed, or a claim changed while confirmed - comparing against `.jsk/kb.last.ttl`, the copy of
the last logged revision; without that copy it lists every confirmed entry. It also records a
torn write and a file restored on its own, and starts the log for a `kb.ttl` that has none.
Detection, not prevention: the edit already happened, and adopt makes it visible.

**`fmt`** rewrites a record file in the canonical layout: `kb.ttl` when none is named, logged on
its own (`by fmt`, the day unchanged) so no content change hides in a reformat. A `posting.ttl`
or `application.ttl` is rewritten in place, unlogged. Hand comments would be lost: `adopt` and
`fmt` refuse a file with any, listing them, unless `--drop-comments`.

```bash
jsk kb show prj_payments met_settlement  # the entries, and the op:base to draft against
jsk kb view --section Projects           # the career as Markdown, to read
jsk kb query unconfirmed --json          # open | unconfirmed | holds <concept> | stale
jsk kb query experience c:kubernetes     # | experience <concept> | pipeline
jsk kb check                             # every rule, the record's state, the layout
```

**`show`** prints entries exactly as their files hold them - a project with its bullets, a
metric with its versions, a concept from the vocabulary and from `kb.ttl` - under a first line
naming the revision to put in `op:base`. **`view`** is the whole career as Markdown in `kb.ttl`'s
section order, entries not confirmed and retired ones marked; it goes to stdout and never to a
file, so it cannot drift from the record. **`query`** answers a named question as a table or
`--json`: `open` questions, `unconfirmed` entries with the question open about each, the projects
that `holds` a concept (or one that counts as it, with the evidence), `stale` - applications
that sent a metric version since replaced - `experience` of a concept (the months the roles
behind the projects holding it cover, overlaps once: what the claims gate compares "N years
of X" against), and `pipeline`, each application's stage: the kind of its latest dated event,
the day, the days since, and any due date on it. A stage is never stored; it is this query.
**`check`** runs every rule over the workspace, says
where `kb.ttl` and `log.ttl` stand, and names files out of the canonical layout; exit 1 on a FAIL.

Exit 0 written, or nothing to change; 1 refused, with every reason; 2 called wrong.

### `jsk migrate`

The `jsk.migrate` module. Moves a Markdown knowledge base to the graph record, once.

```bash
jsk migrate ./my-career/user-knowledgebase.md --dry-run   # every file it would write, printed
jsk migrate ./my-career/user-knowledgebase.md             # written, logged as r1
```

The workspace is the folder holding `user-knowledgebase.md`. It writes `career/kb.ttl` and
`career/log.ttl` there - kb.ttl at `j:revision 1`, log.ttl's `k:rev_1` (`j:by j:migrate`) holding
its hash and `log.md`'s whole history as its note - so `jsk kb` reads the record as clean. Each
`applications/<dir>/` gets `posting.ttl` (the requirements, each with a `j:quote` of the advert's
words), `posting.md` rewritten as the advert alone, and `application.ttl` when `application.md`
exists: its frontmatter, its `# Timeline` rows as events, and `j:carried` links to the bullets its
`resume.json` sent. The old `posting.md` is kept whole as `posting.orig.md`. **Nothing is
deleted**: `user-knowledgebase.md`, `log.md`, `application.md`, `gaps.md` and `resume.json` stay.

Ids follow the ontology: `proj_` becomes `prj_`, `role_` `pos_`, `metric_` `met_`; a metric
becomes a `Metric` and its `.v1`. Enums take URS's values (`self-reported` is `reported`,
`work-visa` `employment-visa`), and the overloaded `status` splits into `j:provenance`,
`j:authorization` (work rights) and `j:credentialState` (certifications). A bullet takes the id a
`resume.json` already gave the same words, so the applications' links still join; otherwise one
is minted from its project and its words. An entry with no `status` is `j:inferred` - a migration
never raises a provenance. A value the ontology has no field for is kept as a `j:note` on its entry
and named in the output; an unknown section is kept word for word as a note on `k:kb`.

It refuses, writing nothing, when `career/kb.ttl` exists; when the file is not in the Markdown
format's shape (the old reader, `jsk.kbindex`, decides); when a required value is missing (a role
with no organisation, a metric whose value is not a number); when the new workspace would have a FAIL; or
when the round trip fails - the graph, written and parsed back, must read as exactly the entries
read from the Markdown, and the old reader's own view of the projects, roles, years of experience,
metrics and questions must match the same view of the graph. After writing it runs the claims
gate over every `resume.json`, where the install has it. Needs markdown-it-py and pyyaml (the
`migrate` extra).

Exit 0 migrated (or would be); 1 refused, with every reason; 2 called wrong.

**`jsk migrate` is for one release.** The release after this one deletes it, with the Markdown
reader (`jsk/kbindex.py`) and the `migrate` and `index` extras. Migrate before upgrading past it; a
`user-knowledgebase.md` left after that stays readable by a person and by nothing in `jsk`.

### `jsk validate`

The `jsk.gates.validate_urs` module.

```bash
jsk validate resume.json
jsk validate resume.json --strict            # warnings become failures
jsk validate resume.json --max-findings 0    # print every one
```

The **record gate**, and the one that got more important. The record used to be compiled from a
folder of concepts, so a structural check here would only have been re-checking the compiler. It is
written by hand now, which puts this command between a slip in that writing and a resume somebody
sends.

What it checks:

- **Shape** — every top-level key is one the renderer knows, `urs` and `person` are present, and
  every list key holds a list. This is the check the hand-authoring brought back. `experience:`
  written where `engagements:` belongs renders a resume with no jobs on it, and the mistake is
  invisible in the PDF precisely because the section is simply not there.
- **Ids** resolve, and nothing references something that is not in the document.
- **Periods** are coherent — no end before its start, no ongoing role with an end date.
- **Metrics** — every numeral in a bullet appears in some metric. This is the check that stops a
  rewritten clause quietly inflating a number.
- **Provenance** — nothing below a view's `provenance_floor` reaches that view.
- **Views** carry no free text and no key the renderer does not know.
- **Coverage** — a project rated `strength: 4` or better with no evidence fails; below that it warns.
- **Renderable at all** — a record with no views, or with neither engagements nor projects, fails.
  Every other check iterates a list, and an empty list satisfies all of them.

A directory is exit 2 with the file to pass instead, and so is a `.md` — failing on a JSON parse
error would tell somebody their record is malformed when what happened is that the bundle format
went away.

### The claims gate

The `jsk.gates.claims` module. No verb of its own: `jsk gates`, `jsk ship` and `jsk freeze` run
it after the record gate whenever the record sits in a workspace whose career is the graph
record (`career/kb.ttl`, found by walking up from the record).

```bash
python -m jsk.gates.claims applications/<dir>/resume.json
python -m jsk.gates.claims resume.json --root ./my-career --max-findings 0
```

The record gate checks a record against itself: a numeral in a bullet has to appear in one of
that bullet's own metrics. But the record and its metrics are both written by hand for one
application, and a rewritten clause agrees with its rewritten metric and with nothing the person
confirmed. This gate checks the record against the career. Ids are shared (`prj_`, `ach_`,
`met_`, `org_`, `pos_`, ...), so every check is a join:

| # | Check | Severity |
|---|---|---|
| 1 | `absent-confirmed` - an achievement `kb.ttl` does not hold is anything above `inferred` in the record | FAIL |
| 2 | `provenance-raised` - any id the two share is more confirmed in the record than in `kb.ttl` | FAIL |
| 3 | `number-superseded` / `number-untraced` - a numeral in a bullet is in no current version of a metric the bullet cites in `kb.ttl` (or names by `"id": "met_x"` in its `metrics`); superseded when an older, closed version has it | FAIL |
| 4 | `label-unheld` - a vocabulary label in a bullet names a concept its project does not hold (tags, domains, what its live bullets show, and what those count as without an `implies`) | WARN |
| 5 | `alias-unheld` - a skill's name or alias names a concept no project holds | WARN |
| 6 | `years-overstated` - "N years of X" in the headline, a narrative or a bullet exceeds what the roles behind the projects holding X cover (`jsk kb query experience`) | WARN |

1-3 read ids and numbers. 4-6 read prose, where a word may or may not be a technology, so they
warn until they have been measured at zero false positives on real records. A label of three
characters or fewer matches only as written ("Go", never "go"); a longer one also with its
first letter in the other case; the longest label is read first, so ".NET Framework" is never
read as ".NET". An alias that names no concept is not a claim this gate can read and is left
alone.

It will not check against a career it cannot trust: a `career/kb.ttl` with a FAIL, or one that
is not what `log.ttl` last recorded (a hand edit not yet adopted could have raised the very
provenance check 2 compares against) is one FAIL naming `jsk kb check` or `jsk kb adopt`.

Where there is no `career/kb.ttl` - a workspace still on `user-knowledgebase.md` - the gates say
`NOT RUN` under a `claims gate` heading, with exit `null` in `--json`: not a pass, and not a
failure either, or no Markdown workspace could ship until it migrated. Exit 0 every claim
traces, 1 a FAIL, 2 called wrong or no `career/kb.ttl`.

Called from code as `claims.check(record, store, today=None) -> validate_urs.Report`, where
`record` is a resume.json path or its parsed dict and `store` is `jsk.graph.store.load(root)`;
`claims.findings(...)` returns the same as `Finding` objects with the check's name.

### `jsk render`

The `jsk.urs.render_resume` module.

```bash
jsk render resume.json --out DIR --view view_au_default
jsk render resume.json --out DIR --view view_acme --pdf
jsk render resume.json --out DIR --view view_acme --region au
jsk render resume.json --out DIR --view view_acme --pdf --ats-max
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
failure as a passing note and exit 0, so a caller could ask for a PDF, be told in passing there
wasn't one, and still see success.

**The page count is measured off the PDF**, with `pymupdf`, and printed only with `--pdf`:

```
  pages  Priya_Raman_Resume.pdf: 1 page against a budget of 2
```

It used to print the budget alone, which is the number somebody asked for rather than the number they
got — the resume that prompted the fix rendered on one page against a budget of two and said so
nowhere. Over budget is named (`- OVER BUDGET, run jsk fit`) and not failed: `jsk fit` owns that
verdict, and it is the command that can do something about it. Without `pymupdf` the line says the
budget and says it was not measured, which is the honest version of the same sentence.

`--template` and `--ats-max` are different axes and compose. The variant decides what the document
says; the template decides how it looks. All five templates extract to identical text, so the choice
is about the reader and never about the parse. An unknown name is a usage error rather than a silent
fall back to the default, because a resume rendered in a template nobody chose is a resume nobody has
looked at — and it would look perfectly fine. See `references/templates.md`.

### `jsk preview`

The `jsk.urs.preview_templates` module.

```bash
jsk preview resume.json --out DIR
jsk preview resume.json --out DIR --view view_acme --only meridian,ember
```

The same record rendered in every template, with the page count for each, so the look is chosen by
looking. Writes `DIR/<template>.pdf` and `.tex`, plus a `.png` of the first page where `pymupdf` is
installed. The `.tex` files are written one after another; the TeX compiles run side by side, each in
its own scratch directory, and the report still lists the templates in their fixed order.

Density is the one difference between templates that is not a matter of taste: the same record is
one page in a dense template and two in an airy one, and a two-page resume where a one-page resume
was available is a decision worth making on purpose.

| Flag | Does |
|---|---|
| `--out DIR` | required — previews are scratch, not deliverables |
| `--view ID` / `--region CC` / `--ats-max` | passed straight through to the renderer |
| `--only A,B` | just these templates |

Exit 0 = every template rendered. Exit 1 = at least one did not, and that is reported rather than
worked around: a template that does not build is not a template, and the others may be about to
break too. Exit 2 = usage, or no TeX engine.

## The gates on the document

### `jsk check --only parse`

The `jsk.gates.check_ats` module.

```bash
jsk check --only parse resume.pdf               # the rendered deliverable
jsk check --only parse resume_ATS.txt --strict  # the ASCII variant
```

The **parse gate**. Reads the PDF's text layer (or the `.txt`) for what makes applicant tracking
systems mangle a resume: text that does not extract at all, section words that appear in prose but
never in a heading, leftover bracketed placeholders, unparseable phone numbers, bullet glyphs a
parser will not map, and arrow glyphs that fuse job titles when stripped.

The structural checks — tables, text boxes, header content, second columns — are gone. One LaTeX
template produces every render and cannot express any of them, so the check moved from the output to
a golden-file test on the template, where it is proved rather than sampled. Needs `pymupdf` for a
PDF; the `.txt` path is standard library only.

### `jsk check --only prose`

The `jsk.gates.check_prose` module.

```bash
jsk check --only prose resume.tex
jsk check --only prose resume_ATS.txt
```

The **prose gate** — the writing rules the parse gate cannot see. Third person, unresolved
placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
across projects, bullets that clear their throat before the verb. It reads the `.tex` rather than the
PDF, because a bullet is an unambiguous `\item` there and needs no library to find. No dependencies.

### `jsk check`

Both document gates in one pass, on one file. Pass either sibling and the other is found beside it:
the parse gate reads what is actually sent — the PDF — while the prose gate reads the `.tex` it was
compiled from.

```bash
jsk check resume.pdf
jsk check resume.pdf --strict
```

A run with `--only` never closes by saying both passed. It names the three gates that did not.

### `jsk gates`

```bash
jsk gates <out-dir>
jsk gates <out-dir> --record applications/acme/resume.json --pages 2
jsk gates <out-dir> --view view_acme --json
jsk gates <out-dir> --max-findings 0
```

The record, parse and prose gates over one rendered output directory, in **one process** - and,
after the record gate, the claims gate, when the record sits in a graph workspace. It is the
five invocations a hand-run verification used to make — the record gate on `resume.json`, the parse
gate on the PDF and again on the `.txt` with `--strict`, the prose gate on the `.tex` and again on
the `.txt`. It imports the checkers rather than shelling out to them, and gives them the same
arguments, so the findings and the exit code are the ones the five commands produce. That
equivalence is what it is tested on.

`check_ats.py` and `check_prose.py` grew a `main(argv)` entry point so it could: same CLI, same
arguments, same output to the character, now callable without a subprocess. That entry point is
load-bearing rather than incidental, so it is documented here beside their CLIs.

**`--record` defaults to `resume.json` in the output directory**, which is where the skill writes it
for an application. Named rather than searched: a directory holding two records has no way to say
which one the documents came from, and guessing would put a passing record gate against a resume it
never described.

Three properties, each of them an existing rule here rather than a new one:

- **Every gate's output is printed verbatim, never summarised.** The person should see the evidence
  rather than take anyone's word for it. The section headers match `jsk check`.
- **A missing input is `SKIPPED` and a failure.** A gate that did not run is not a gate that passed.
  Same behaviour and same wording as `jsk check`. A path you *gave* that is not there is exit 2
  instead — omitting `--record` and mistyping it are different mistakes, and reporting them
  identically hides one. Both are non-zero.
- **It never attempts the render gate**, and closes with a line saying somebody has to open the PDF
  and read it. That gate is the one no command can have, and a command that exited 0 having silently
  skipped it would be the most dangerous thing in this directory.

`--view ID` is optional and does no work. The record names the view it was written for, so nothing
in the run reads the flag — it exists because this output is archived beside an application as
evidence, and passing it stamps which view was gated. It was *required* while a bundle held every
view and the command had no other way to know.

`--pages N` reports and never fails. It measures the PDF and prints the renderer's own over-budget
line, reused rather than restated. Over budget is named rather than failed everywhere in this
pipeline, because `jsk fit` owns that verdict and is the command that can act on it.

`--max-findings N` caps how many findings each gate lists — the same flag name and the same default
as `jsk validate`, because two gates that truncate differently are two gates people read differently.
The header counts stay true regardless: truncating a list is a reading aid, truncating a count is a
lie.

`--json` carries each checker's whole text in `gates[].output`, beside `gate`, `command`, `status`
and `exit`. It always includes a `render gate` entry with `status: "UNVERIFIED"` and `exit: null`,
so **the machine-readable form cannot report the render gate as passed either.** That is what makes
`--json` safe to consume here: it is the same evidence in a different envelope, never a summary.

The exit code is the worst gate's: `0` all passed, `1` any failed, `2` called wrong.

## Fitting

### `jsk fit`

The `jsk.urs.fit_pages` module.

```bash
jsk fit resume.tex --target-pages 2
jsk fit resume.tex --dry-run
jsk fit resume.tex --in-place
jsk fit resume.tex -o fitted.tex
```

Rewrites the density knobs in the `.tex`, recompiles, and measures the PDF that comes out. It applies
the levers in a fixed order — spacing, bullet spacing, margins, font size — stopping at the 10pt and
0.5" floors instead of crossing them. If the target is unreachable without a breach it exits
non-zero, because the remedy then is to cut evidence, not to shrink type.

It used to measure a `.docx` through LibreOffice while the PDF was what got sent. The two disagreed,
and a resume this reported as two pages shipped as three — a gate passing on a document nobody was
sending. It now measures the artefact that goes out.

Needs a TeX engine and `pymupdf`.

## Shipping

### `jsk ship`

```bash
jsk ship <resume.json> --out DIR --view ID [--ats-max] [--template N] [--pages N] [--json]
```

The commands a ship used to be, in one process and in order, each step's output printed
verbatim under its own `---` heading the way `jsk gates` prints it:

1. **the record gate** — what `jsk validate <resume.json>` runs. A failure stops here and **nothing
   is rendered**: a PDF made from a record that failed its gate looks sendable and is not.
2. **the claims gate** — the record joined with `career/kb.ttl` (see *The claims gate*). A FAIL
   stops here too, and nothing is rendered; with no graph record it says `NOT RUN` and the ship
   goes on.
3. **the render** — what `jsk render <resume.json> --out DIR --view ID --pdf` runs, with `--ats-max`
   and `--template` passed through. A render that produced no PDF stops here.
4. **the parse and prose gates** — what `jsk gates DIR --record <resume.json> [--pages N]` runs,
   less the record and claims gates the steps above have just run on the same file.

It closes with the same render-gate section `jsk gates` does: **nobody has read the PDF**, and the
command says so rather than exiting 0 over it. When it stopped early that section says nothing was
rendered, instead of pointing at a PDF an earlier run left in `DIR`. The page count is reported —
the renderer's own line, and `--pages N`'s — and never failed; `jsk fit` owns that verdict.

Exit `0` only if every step passed, `1` on any failure, `2` called wrong. `--json` carries every
step in `steps[]` in the `jsk gates` shape, the render gate last and `UNVERIFIED`.

### `jsk freeze`

```bash
jsk freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--view ID] [--doc FILE ...]
```

Freezes one `applications/<yyyy-mm-dd>-<company>-<role>/` directory the way `references/mode-ship.md`
describes: renames it to the day it was sent, if its leading date says otherwise, and writes what
was sent beside `posting.md`, `gaps.md` and `resume.json`. Which file depends on the workspace's
career record, found beside `applications/`.

**`career/kb.ttl` - the graph record.** It writes `application.ttl`:

```turtle
# == Application

k:app_acme_platform j:posting k:post_acme_platform ; j:view "view_acme_platform" ;
    j:submitted "2026-09-08"^^xsd:date ; j:channel "Workday portal" ;
    j:document "Priya_Raman_Acme_Resume.pdf", "Priya_Raman_Acme_Resume_ATS.txt" ;
    j:recordSha256 "7bc8...9f9c" ;
    j:carried k:ach_events_latency, k:ach_events_team ;
    j:carriedVersion k:met_latency.v2, k:met_team.v1 .

# == Timeline

k:evt_acme_platform_2026_09_08_submitted j:application k:app_acme_platform ;
    j:date "2026-09-08"^^xsd:date ; j:kind j:submitted ; j:channel "Workday portal" .
```

The id's stem is the posting's (`k:post_acme_platform` in `posting.ttl`, which must be there),
and never changes when the directory is renamed. `recordSha256` is the frozen `resume.json`'s,
byte for byte: the record is the copy, and nothing is copied out of it. `carried` is every bullet
the view rendered (its provenance floor, its include lists) that `kb.ttl` holds; `carriedVersion`
is the current version, now, of every metric those bullets cite. That is what makes a later
revision visible: `jsk kb apply` never changes a sent version - a new number becomes the next
one - and `jsk kb query stale` names every application that sent the old. The file is validated
with the whole workspace before anything is renamed or written, and is written canonically. It
is not logged in `log.ttl`, and `kb.ttl` is never touched.

**`user-knowledgebase.md` - a Markdown workspace, not yet migrated.** It writes `application.md`,
exactly as it always has, and the claims gate says `NOT RUN`:

```markdown
---
company: Acme Health
title: Platform Engineer
view: view_acme_platform
submitted: 2026-09-08
channel: Workday portal
documents:
  - Priya_Raman_Acme_Resume.pdf
  - Priya_Raman_Acme_Resume_ATS.txt
---

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2026-09-08 | submitted | Workday portal | | |
```

There, `company` and `title` come from the top-level lines of `posting.md`'s frontmatter. Never
both files: two archives of one submission are two chances to disagree, and `jsk migrate` turns
an `application.md` into an `application.ttl`.

Either way, the view is `--view`, or the record's only one; a record with several and no `--view`
is exit 2, naming them. The documents are the `--doc` files, or every `.pdf` and `.txt` in the
directory. The final path is printed.

It refuses — exit 1, saying why, with nothing renamed and nothing written — when:

- **`application.ttl` or `application.md` already exists.** A frozen application is never
  re-frozen; later events are `jsk event`, or one appended row each in `application.md`.
- **any mechanical gate fails.** It runs what `jsk gates <app-dir> --record <app-dir>/resume.json`
  runs - the claims gate included - in process, and prints it. A failing document is never frozen.
- `posting.ttl` is missing or holds no posting (graph), `posting.md` has no `company:` or `title:`
  (Markdown), there is nothing to list as documents, the renamed directory would land on one that
  already exists, or the `application.ttl` it would write does not validate.

`--submitted false` is for an application worked through and deliberately held back: it writes
`submitted false` (`submitted: false`), leaves the directory's name alone, and records **no
`submitted` event** (no row) — an accurate blank rather than a false green. It never touches the
career - `kb.ttl` and `log.ttl`, or `user-knowledgebase.md` and `log.md`; the log row stays the
skill's to write.

### `jsk event`

The `jsk.graph.timeline` module.

```bash
jsk event applications/2026-09-08-acme-platform screen-scheduled --date 2026-09-15 --due 2026-09-18
jsk event applications/2026-09-08-acme-platform rejected --date 2026-10-02 --channel email
jsk event applications/2026-09-08-acme-platform note --date unknown --note "Recruiter said Q4."
```

Adds one event to a frozen application's `application.ttl`: `k:evt_<stem>_<date>_<kind>`, with
`--channel`, `--note` and `--due` when given. The kind is the closed pipeline vocabulary -
`submitted`, `acknowledged`, `screen-scheduled`, `screen-done`, `interview-scheduled`,
`interview-done`, `onsite-scheduled`, `onsite-done`, `offer`, `offer-accepted`, `rejected`,
`withdrawn`, `no-response`, `offer-declined`, `follow-up-sent`, `note`, `referral`,
`recruiter-contact` - and a kind outside it is exit 2 with the nearest one suggested. The date is
`YYYY-MM-DD` or `unknown`.

Add-only: it never edits or removes an event, and the same kind on the same day is already
recorded, so it is refused (a `note` event says more). The whole workspace is loaded with the
event in it and validated before the file is replaced; a file with hand comments, or not in the
canonical layout, is refused until `jsk kb fmt <file>`, so the event is the only change in its
diff. An application frozen as `application.md` is pointed at its `# Timeline` table. Not logged
in `log.ttl`: the log is the career's.

The stage is never stored: `jsk kb query pipeline` derives it from the latest dated event.

Exit 0 added, 1 refused, 2 called wrong.

## What is not here any more

**`jsk index`** read `user-knowledgebase.md`: an overview with line ranges, and `--rank` against
a posting's frontmatter. The career is `career/kb.ttl` now - `jsk match` ranks it against a
`posting.ttl`, `jsk kb view` and `jsk kb show` read it - and `jsk index` says so and exits 2. Its
module, `jsk.kbindex`, stays one release because `jsk migrate` reads the Markdown with it.

The `okf` commands left with the bundle format, in 4.0. The graph record brings back a write path -
see [WHY.md](WHY.md) for why that is not the same decision made twice - but one generic verb,
`jsk kb apply`, whose coverage is the ontology, not a command per noun.

---

Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
