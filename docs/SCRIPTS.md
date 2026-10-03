# Commands

The skill runs these for you. This page is for running them yourself.

It is all one command. `pip install 'jsk-resume[all]'` puts `jsk` on your PATH; `python3 -m jsk` is
the same entry point where it is importable but not on PATH, and on Windows use `python` or `py -3`
in place of `python3`.

Every command is `jsk <noun> <verb>`: the noun is what you work on, the verb what you do to it.
There are six nouns - `kb`, `posting`, `tailor`, `resume`, `letter`, `app` - and `jsk doctor`
and `jsk mcp` beside them. `jsk --help` lists the nouns, `jsk <noun> --help` a noun's verbs, and
`jsk <noun> <verb> --help` one verb's flags. This page has one section per noun and, under it, one
per verb. `jsk` is the only door: the `python -m jsk.<module>` paths of earlier releases are
retired, and each one prints the command that replaced it and exits 2.

**The career is in `career/store/`**, the graph record: named graphs in one Oxigraph store -
`kb`, `log`, and each application's `posting`, `review`, `gaps`, `resume` and `application` -
read and written only through `jsk`, and validated on every run. `jsk kb` changes it (through
changesets) and reads it back, `jsk tailor match` ranks it against a posting, `jsk app freeze` and
`jsk app event` record what was sent and what came back. The renders are files in
`applications/<dir>/`. A resume is built from the career and a selection - the bullets chosen for
one posting, by id, and its settings: the `resume` graph, written by `jsk mcp`'s `resume_select`.
An application made from files also keeps its documents there - `posting.md`, `decisions.txt`,
`gaps.txt`, and a short `resume.json` that `jsk kb export` writes and `jsk resume check` checks
against the career. The rendering half carries either to a document somebody can send.

## The whole surface

```bash
jsk doctor                       # what works on this machine
jsk kb new ./my-career --name "Your Name"  # career/store/ with the career and its log, at r1
jsk kb apply changes.trig        # change the graph record; `jsk kb --help` lists the rest
jsk tailor match applications/<dir>  # a posting against the career, through the vocabulary
jsk tailor prepare applications/<dir> --draft-gaps   # the match and everything an assessment reads
jsk resume check resume.json    # the record gate
jsk kb export --from-match applications/<dir> --out applications/<dir>/resume.json
jsk resume render resume.json --out . --pdf
jsk resume check resume.pdf     # both document gates, one pass
jsk letter check cover-letter.txt --record resume.json   # a cover letter's words and numbers
jsk resume check .              # record, parse, prose and layout gates
jsk resume fit resume.tex --target-pages 2
jsk resume preview resume.json --out ./looks
jsk resume ship resume.json --out .   # validate, render, gate
jsk app freeze applications/<dir> --submitted 2026-09-08 --channel "Workday portal"
jsk app event applications/<dir> screen-scheduled --date 2026-09-15   # what happened next
jsk app drop applications/<dir> --reason "role filled"   # set an unsent one aside
jsk mcp                          # the career and its applications as MCP tools, over stdio
```

Each verb runs in the same interpreter as `jsk` itself. None of them spawns a Python child: that
cost a start-up and a fresh import per call, which was most of the wall time of checking a render.
The one exception is `jsk doctor`'s end-to-end run, which spawns `python -m jsk <noun> <verb>` on
purpose — proving that entry point works from cold is what it is for.

## Exit codes

Uniform across every subcommand:

| Code | Means |
|---|---|
| `0` | passed |
| `1` | failed — a real finding, or a dependency missing that makes the answer unknowable |
| `2` | you called it wrong — bad usage, or a file that is not there |

Nothing here passes quietly when it could not do its job. A page count nobody measured is a page
count nobody knows.

## Retiring in 6.0

The commands that serve only applications made from files (`posting.md`, `decisions.txt`,
`gaps.txt`, `resume.json`) retire in 6.0
(`docs/superpowers/plans/2026-10-03-retire-file-pipeline.md`). In 5.x each still works, and prints
one added line first when used in its file form - to stderr under `--json`, so the JSON still
parses:

```
WARN  jsk posting build serves applications made from files and retires in 6.0 - finish this application or drop it
      fix: the posting_decide and posting_complete tools (jsk mcp)
```

| Retires | Serves only | Replacement |
|---|---|---|
| `jsk posting fetch URL D` | `posting.md` | `posting_capture(app, url=)` |
| `jsk posting extract D` | `posting.md` | `app_show(app, part="lines")` |
| `jsk posting build D [decisions]` | `decisions.txt` | `posting_decide`, `posting_complete` |
| `jsk tailor prepare D [--draft-gaps]` | `gaps.txt` digest/draft | `assessment_derive` |
| `jsk tailor match D [--gaps F \| --draft-gaps F]` | `gaps.txt` | `assessment_derive`, `assessment_review`, `assessment_complete` |
| `jsk kb export --from-match D --out R.json`, `--ranked --out R.json` | `resume.json` | `resume_select(target, mode)` |
| `jsk resume check\|render\|preview\|ship <resume.json>` | `resume.json` | the same verbs on `<stem>` / `resumes/<name>` |
| `jsk kb confirm --summary\|--headline <resume.json>` | `resume.json` | `career_confirm(target, block)` / `--summary <stem>` |
| `jsk letter check L --record <resume.json>` | `resume.json` | `letter_check(letter, record=<stem>)` / `--record <stem>` |
| `jsk app freeze D` on a file-made application | `resume.json` | `app_freeze` on a graph-native one |

The `app_freeze` tool on a file-made application, and `letter_check` with a `resume.json`, carry
the same WARN as a finding. An application made from files that is not sent - its folder holds one
of those files, its posting has no advert lines, and it was never frozen - has nothing to finish it
after 6.0. `jsk kb check` names each (`file-made-unsent`), the `app_list` tool marks it
`unsent: true` with the note, and `jsk doctor` counts them in an `info` line. Send each with this
CLI before upgrading, or drop it with `jsk app drop applications/<stem>` (below), which 6.0 keeps.
A frozen one stays readable in 6.0.

## `jsk doctor`

```bash
jsk doctor                 # verifies end to end
jsk doctor --quick         # skip the render
jsk doctor --json          # machine-readable
jsk doctor --kb PATH       # check a specific workspace, the folder holding career/store/
```

Bare `jsk doctor` runs the record gate over the shipped example workspace (`jsk/data/example/`:
a small career and a short `resume.json`, shipped as files and imported with `jsk kb load` into a
temporary store first, as a person's workspace from before the store is), renders it and runs the parse and prose gates on
the result, so a pass means the pipeline genuinely works here rather than looking like it should.

Verdicts: `READY` · `READY, with gaps` · `BLOCKED` (the install is broken) · `BROKEN` (the toolchain
is present but failed its own gates — that is a bug in the skill, not in your setup).

Gaps are reported by what they *disable*, not by package name. Runs on a bare Python: a preflight
that needs installing first is not a preflight.

One line is neither a check nor a gap: whether the `mcp` extra is importable. It is marked `ok`
when it is, and `info` when it is not, with what that costs (`jsk mcp` cannot start) and its
install line, `pip install 'jsk-resume[mcp]'`. It never changes
the verdict or the exit code: the CLI does all of its work without the extra. `--json` lists it
under `extras`, apart from `checks`.

Without `--kb` it searches three directories down for a workspace, and dot folders (`.jsk/`,
`.git/`) are never searched. For the one it finds it reports the store: present, readable, its
revision, whether `.jsk/backup.trig` exists and at which revision, and - an `info` line, when
there are any - how many applications made from files are not sent (Retiring in 6.0). A `career/kb.ttl` with no
`career/store/` beside it is a workspace from before the store, reported with its fix, `jsk kb
load .`. Searching by name rather than by a directory shape is deliberate — a bundle used to be
recognised by the folders inside it, so a half-created one was invisible here and reported as
absent while the person was looking straight at it.

## `jsk kb`

The career record. One verb per operation on the graph record; `jsk kb --help` lists them and
`jsk kb <verb> --help` explains one. Every verb finds the workspace - the folder holding
`career/` - from the current directory, or takes `--root DIR`.

### `jsk kb new`

```bash
jsk kb new ./my-career --name "Your Name"
jsk kb new ./my-career --name "Your Name" --force   # start the career over from the empty record
```

Writes a graph workspace:

| Path | Is |
|---|---|
| `career/store/` | the store, holding the `kb` graph - the empty career: a header naming the person (`k:kb j:name`) at `j:revision 1` - and the `log` graph with `k:rev_1`, `j:by j:new` |
| `applications/README.md` | what each application directory holds |
| `.gitattributes` | `career/store/** binary`, added to one already there: git never rewrites the store's line ends |

After the first write there is also `.jsk/`, with `.jsk/backup.trig` in it. `.jsk/` ignores itself
for git, so a person who backs the workspace up with git commits a `jsk kb dump --out record.trig`
too: the store's own files are not text a diff can read, and the backup is not committed.

Both graphs go in through the same write gate every `jsk kb` write uses, in one update, so the
record is **clean at r1** and `jsk kb apply` works on it straight away. It needs pyoxigraph, a
dependency of the package, as every `jsk kb` verb does: without it there is no store to create.

The empty record holds no identity: `k:person` arrives with the first changeset, like any other
entry, as `j:inferred` with a question - the name on the command line says whose record this is,
not that anyone confirmed how it should head a resume.

It refuses (exit 1, nothing written) when the workspace already holds a record, and when it holds
`career/kb.ttl` and no store - that is a record from before the store, for `jsk kb load .`.
`--force` overrides the first. Over an existing record it starts over **as the next revision** -
the career becomes the empty record, the log keeps every earlier entry and gains one by `new`, and
the replaced career is written beside the store as `career/kb.r<N>.trig`, N its revision (then
`kb.r<N>-2.trig` if that name is taken - it never overwrites a file; it is a dump, which `jsk kb
load` reads into a new workspace, not the record). It is refused where a frozen application
carried an entry the empty record would not have. A changeset drafted before the start-over is
refused afterwards, whatever it names: its `op:base` is older than the newest `by new` entry.

What each section holds is the format reference's job (`references/kb-format.md` in the skill),
and every refused write names what it refused.

### `jsk kb apply`

```bash
jsk kb apply changes.trig --dry-run      # the diff it would make, nothing written
jsk kb apply changes.trig                # merged, validated, written, logged
```

**`apply`** is how an agent changes the career: a changeset, in TriG, with four graphs. A
changeset is input - a file you write, say `changes/2026-09-08-payments.trig` - never storage. A
first braindump into the empty record `jsk kb new` writes (r1) - it applies as it stands:

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
is the log revision the changeset was drafted against. A write since then that touched nothing the
changeset names does not stop it: it applies to the record as it now is, and every rule runs again.
An entry the changeset names that changed after `op:base` is a conflict, refused, naming the ids,
to be re-read. The header's `op:summary` becomes the log entry's.

A number is written as the store keeps it: an integer or decimal whose spelling the store would
rewrite (`8.40`, `007`, `+3`) is refused, with the fix naming the literal the store keeps - `write
8.4`, or for the decimal `8.0`, `write "8"^^xsd:decimal`. This is a refusal in `changeset.py`, not a
rule id; posting builds and dumps `jsk kb load` reads are held to it too. A grade whose zeros matter
(`3.80`) is a string, which `gradeValue` allows.

What apply does unasked: a new bullet (a `[]` with `j:project`) gets its id,
`ach_<project>_<three words of its text>`, never one the record has used. An entry whose claims
changed drops to `j:inferred`, and every entry left inferred gets a `q_` question unless one is
open. A metric version an application sent never changes: a new `j:value` becomes the next
version, and the one it replaces is closed. A changeset cannot confirm anything, cannot write
another file, cannot use blank nodes except for a new bullet, and cannot name a predicate the
ontology does not have (it suggests the nearest).

The command takes its **turn** before it reads the record: a writer that finds another jsk write
in progress prints `waiting for another jsk write to finish` and waits, in arrival order, rather
than being refused, and reads the record only once the one ahead of it has finished - so it
validates and applies to what that one left. There is no retry: a changeset naming an id that
write changed is refused, as above. The workspace is validated before the apply starts - a FAIL
in the career refuses it with the command that fixes it - and the record it would write before
anything is written. Then the career, its log entry and the revision go into the store in **one
update** - all of it lands or none does - and `.jsk/backup.trig` is overwritten with the whole
record as TriG (best effort; read only by `jsk kb load`). A process that dies holding its turn
gives it up with its file handle. Stdin (`-`) is refused: a pipe that never closes hangs the command.

### `jsk kb confirm` and `jsk kb log`

```bash
jsk kb confirm k:ach_payments_cut_settlement_latency --answer "Yes: 800 ms before, 200 after, from the Grafana board."
jsk kb log --last 5                      # the newest five revisions: day, command, summary, ids
```

**`confirm`** is the only way an entry becomes `j:confirmed`, and it takes the person's answer in
their words: each id named is confirmed, every open question about it is answered today, and the
log entry keeps the answer beside the ids. An answer that says nothing - `yes`, `ok`,
`confirmed`, a placeholder - is refused, and one that reached the log by hand is flagged by
`answer-placeholder`. This is an instruction with an audit trail, not a proof that anyone asked.

`--summary <resume.json>` and `--headline <resume.json>` confirm the file's own prose instead:
`resume.json` keeps the answer and the text's hash, and the career is not written or logged. The
headline is the posting's title as `jsk kb export --from-match` set it; it renders under the name
only once the person says it is a title they stand behind. Given a graph-native application's
`<stem>` or `resumes/<name>` in place of the file, the block is confirmed in its selection graph.

**`log`** is the history, newest first: each revision's number, day, the command that made it
(`apply`, `confirm`, `new`, ...), its summary, and the ids it minted and touched. `--last N`, the
newest N (default 10). It is how the history is read - there is no log file to open.

### `jsk kb show`, `view`, `query`, `pack`, `merge`, `check` and `path`

```bash
jsk kb show prj_payments met_settlement  # the entries, and the op:base to draft against
jsk kb view --section Projects           # the career as Markdown, to read
jsk kb query unconfirmed --json          # open | unconfirmed | holds <concept> | stale
jsk kb query experience c:kubernetes     # | experience <concept> | pipeline
jsk kb query evidence GraphQL "React Native" BFF  # each term: holders, then text naming it
jsk kb query person                      # location, work mode, rights to work, ongoing roles
jsk kb query concepts                    # every concept: labels, counts as, projects holding it
jsk kb query bare                        # the career's capabilities with no label and no isA/partOf
jsk kb pack capabilities --out pack.trig # the capability starter pack, drafted as a changeset
jsk kb merge c:a --into c:b --out m.trig # two concepts that are one, drafted as a changeset
jsk kb query similar "event pipeline Kafka"  # the closest live projects, words and concepts shared
jsk kb query duplicates                  # pairs of projects that look like one told twice
jsk kb query demand                      # | shortfalls | drops | outcomes | repeated | absences
jsk kb show prj_payments --bullets       # a project's name and bullets, without its notes
jsk kb path                              # the workspace, career/store/, applications/
jsk kb check                             # every rule, and the record's state
jsk kb check --only applications/<dir>   # that application's findings, and every FAIL anywhere
jsk kb query concepts --near "event mesh"  # what a term names, then the closest few concepts
```

**`pack`** and **`merge`** draft a changeset and never apply it: it is read with `apply --dry-run`
and applied like any other. `pack capabilities` offers `src/jsk/data/capabilities.ttl` - about 120
capabilities and domains, their labels and `isA` edges, never loaded as vocabulary, because an edge
between capabilities is a judgement the person answers for. It adds only what the record lacks and
reports what it skipped: a concept the record classes differently, a label that already names
another concept, an edge that would cross a `distinct` wall or loop. Run again after applying, it
has nothing to add. `merge c:a --into c:b` points every reference to `c:a` at `c:b`, moves its
labels and edges, and deletes `c:a` - retires it, when a posting's `j:concept` still names it. It
refuses a shipped concept, different classes and a `distinct` pair, and lists the bullets whose
`j:shows` it rewrites: they come back `inferred`, to be confirmed again. The `concepts-bare` WARN,
once per record, counts the capabilities `query bare` lists: they match only their exact id.

**`show`** prints entries as Turtle, each under the graph that holds it (`# kb`,
`# applications/<dir>/posting`) - a project with its bullets, a metric with its versions, a
concept from the vocabulary and from the career - under a first line naming the revision to put in
`op:base`. It is the shape a changeset is drafted in. **`view`** is the whole career as Markdown in
the career's section order, entries not confirmed and retired ones marked; it goes to stdout and
never to a file, so it cannot drift from the record. Together with `query` and `log` they are the
only way to read the record: nothing under `career/` is meant to be opened. **`query`** answers a named question as a table or
`--json`: `open` questions, `unconfirmed` entries with the question open about each, the projects
that `holds` a concept (or one that counts as it, with the evidence), `stale` - applications
that sent a metric version since replaced - `experience` of a concept (the months the roles
behind the projects holding it cover, overlaps once: what the record gate compares "N years
of X" against), and `pipeline`, each application's stage: the kind of its latest dated event,
the day, the days since, and any due date on it. A stage is never stored; it is this query.
Across applications: `demand` (each concept the postings ask for, how many require it, the
verdicts it got), `shortfalls` (concepts left unsatisfied, partial or unevidenced, with any
"no" the person gave), `drops` (why advert lines were left out, by reason), `outcomes`
(applications by assessed fit and stage), `repeated` (concepts asked about in more than one
application's questions) and `absences` (each "no": live, due a year after it was said, or
unconfirmed). `drops` and `repeated` read what only graph-native applications store.
**`check`** runs every rule over the workspace and says at
which revision the record stands; exit 1 on a FAIL. A finding names the graph (`kb`,
`applications/<dir>/posting`) and the entry's id - the record has no lines to number.
It also asks the record gate's number check of every live bullet and warns of each one it would
refuse in any `resume.json` that selected it, so it is fixed once rather than by each resume run.
And it asks that the career is what its log's newest entry hashed (`kbSha256`): a mismatch is a
FAIL, `the career is not what its log last recorded - written outside jsk`, restored from
`.jsk/backup.trig` into a new folder, or read with `jsk kb dump`. Only `check` asks it - it costs a
full write of the career, and every other command loads the record on every run.
Last, it names each application made from files and not sent, a WARN `file-made-unsent` with the
fix: send it with this 5.x CLI before upgrading to 6.0, or drop it: `jsk app drop applications/<stem>`
(see Retiring in 6.0 below, and `jsk app drop`).

**`path`** prints the workspace, `career/store/` and `applications/` as absolute paths - where
to run from and write to, never files to read. It needs nothing but the folders.

### `jsk kb dump` and `jsk kb load`

```bash
jsk kb dump --out record.trig                  # the whole record as TriG: a backup, or to move it
jsk kb load record.trig --root ../restored     # fill a new, empty folder from a dump or .jsk/backup.trig
jsk kb load .                                  # import a workspace still laid out as .ttl files, once
```

**`dump`** writes every record graph - the career, its log, every application's graphs, never
the vocabulary or anything derived - as TriG, to stdout or `--out`. The same record always dumps
to the same text. jsk writes one to `.jsk/backup.trig` after every write as well.

**`load`** fills an **empty** store, once, and refuses one that already holds a record. Pointed
at a folder with no `career/` yet by `--root`, it creates the store there; run in a folder that is
no workspace, without `--root`, it is exit 2, "no workspace here". From a dump it loads the record
as it was dumped - and refuses a dump that was edited: one holding a number in a spelling the
store would rewrite, named, or whose career is not what its log's newest entry hashed
(`kbSha256`) - a provenance raised, a number changed. Load an unedited dump, and change the record
through `jsk kb apply` once it is loaded. From a folder still laid out as files - `career/kb.ttl`,
`career/log.ttl`, `applications/*/posting.ttl`, `application.ttl`, `gaps.ttl`, the layout before
the store - it validates them exactly as the file loader always did and refuses on any FAIL,
prints every WARN, lists each number it rewrites to the store's spelling (`8.40` kept as `8.4`)
and, for a `kb.ttl` edited by hand since its last logged write, each entry the edit raised to
`confirmed` (against `.jsk/kb.last.ttl`, or says there is nothing to compare against). It adds
one log entry of its own, `by load`, holding the imported career's hash, and loads the lot in one
update. The files are left where they are, and jsk never reads them again; it says so once. Any
other command in a workspace with `career/kb.ttl` and no store refuses, naming `jsk kb load .`.

**Restoring, and moving to a new pyoxigraph.** Load into a new, empty folder: `jsk kb load
record.trig --root <new folder>` (or move `career/store/` aside first and run `jsk kb load
record.trig --root .`), then copy the `applications/<dir>` folders across - `posting.md`, the
renders and the rest are files beside the record, not in it, and the load names each one missing.
**The store's format is tied to the pyoxigraph version**, so raising the pin is `jsk kb dump` with
the old version, then that load with the new one - never an upgrade in place. A store that will
not open is restored the same way from `.jsk/backup.trig`.

### `jsk kb export`

```bash
jsk kb export --from-match applications/2026-09-08-ashby --out applications/2026-09-08-ashby/resume.json
jsk kb export --ranked --out resume.json
jsk kb export --select prj_payments ach_ledger_cut_close pos_lead --out resume.json
```

**`export`** writes the short `resume.json` - `"resume": 2`, the `bullets` chosen as `ach_` ids in
order, `roles` shown with no bullet, `skills`, the `region` when a profile ships for the person's
country, and `"pages": 2`. Nothing the career holds is copied: every render reads the words,
numbers and dates from the career as it stands, so a changeset applied or a bullet confirmed
afterwards is in the next render with nothing to update. `references/resume-format.md` in the
skill has every key. `--out` never replaces an existing file ("edit it, or delete it to start
again"); without it the file goes to stdout, the notes to stderr.

**`--from-match <app-dir>`** makes the selection from `jsk tailor match`, the same way for the same
posting every time; like `jsk tailor match`, it takes the application directory and refuses a
`posting.ttl` path. A project carries a requirement only when a live, confirmed bullet shows it, so a tag is not
enough. The export takes the smallest cover of the required requirements, then the rest of the
ranking that carries anything, up to eight projects. It scores each confirmed bullet by what it
shows (required ×3, preferred ×1, +1 for a metric with a current version) and gives positions 1-2
up to five bullets, 3-5 up to two, and the rest one. The cover's requirements always get a bullet,
even past that cap. Skills the posting names come first in `skills`. What the selection cannot
close prints as `GAP` lines for `gaps.txt`: `tag-only`, `unconfirmed` (naming the bullet to
confirm), `uncovered` and `unresolved`; a chosen project with no confirmed bullet is a `NOTE`.
`--select` adds bullets (placed by what they show) and roles, `--cover N` and `--today` are
`jsk tailor match`'s, and a failure in the posting's own directory refuses the export as it refuses the
match.

**`--ranked`** is the same selection with no posting, for a general rebuild, so the scorer rather
than the model chooses there too. Projects score 2 × `j:strength` plus the recency points, ties by
strength, recency and id, up to eight; each gets the same bands, a bullet citing a metric with a
current version scoring and the rest filling only to the band's floor, confirmed bullets only.
There are no `GAP` lines and no `skills`, so every skill renders in the builder's order. `--select`
adds to it and `--today` sets the date recency counts from; it and `--from-match` exclude each
other, and `--cover` is `--from-match`'s alone.

**`--select`** alone names what to show: `prj_` a project and every live bullet of it by `j:rank`,
`ach_` one bullet (narrowing its project to the bullets named), `pos_` a role with no bullet.
Projects follow by recency. With none of these flags, the whole career. Retired entries never come;
selecting one, an id the career lacks, or a metric is refused with the nearest id.

A bullet whose project names no role is left out with a `NOTE`: it would render under no employer.
A selection holding no bullet is refused, exit 1, and nothing is written. A career that fails its
rules is refused: the resume would carry the failures. Last, the record gate's number check runs
over the chosen bullets and prints each it refuses as a `WARN` - a number no current metric
version holds is in the career, not in anything authored, so it is a question for the person,
answered in the career before any word is retuned.

`--urs` and `--refresh` are gone with the full record, each a usage error saying so: the short file
is the one format, and it holds nothing to refresh. A full URS record from before is not converted:
export a short one in its place.

Exit 0 written; 1 refused, with every reason; 2 called wrong.

## `jsk tailor`

A posting against the record: what it asks for, what the career shows of it, and where it falls
short.

### `jsk tailor match`

```bash
jsk tailor match applications/<dir>            # the four sections, as Markdown
jsk tailor match applications/<dir> --cover 2  # a cover of at most two projects
jsk tailor match applications/<dir> --json --today 2026-09-24
jsk tailor match applications/<dir> --gaps applications/<dir>/gaps.txt  # check, write the gaps graph, print the assessment
```

A posting's requirements joined with the career through the vocabulary - the shipped `jsk/data/vocabulary.ttl` and the knowledge base's own additions. It takes the
application directory, as `jsk posting build` and `jsk app freeze` do; a path ending `posting.ttl` is
refused with the directory form in the fix. Loads the whole record and validates it first; any
FAIL is printed and nothing is matched. Needs pyoxigraph, a dependency of the package.

**Requirements** puts each one in a bucket: `matched` (a project holds the concept, or a narrower
one within two hops - `via c:aks, 1 hop`), `near` (only an `implies` path, for a required one, or
only something broader), `missing`, `ambiguous` (the label names several concepts; the analyst
answers with `j:concept`), `candidate` (it names none), `implicit`. A requirement naming several
`j:concept`s - the advert's alternatives - is met by any one of them. Evidence per project is
`confirmed` (a confirmed bullet shows it), `unconfirmed` or `tag` (only the project's tags say so).
Each requirement's **Verdict** follows from both: matched with a confirmed carrier `satisfied`,
matched on tags or unconfirmed bullets only `unevidenced`, `near` `partial`, `missing`
`unsatisfied`, `ambiguous` or `candidate` `indeterminate`, `implicit` `-` (not assessed).
**Ranking** scores by the table in `jsk-tailor-analyst.md` - required ×3, preferred ×1, strength
×2, recency +1 within three years and +0.5 at four to six, seniority +1 at or above the posting's -
the same arithmetic the retired `jsk index --rank` did, now over concepts rather than exact
strings. **Cover** is the smallest set of projects, at most `--cover` (default 3), carrying every
required requirement anything carries. **Questions** are derived from the gaps, never invented.

Exit 0 with the result - missing requirements included, since this is an assessment, not a gate;
1 when the workspace has a FAIL; 2 called wrong, or a path that is not an application directory
with a posting.

**The assessment** is two parts, each with one owner. The gaps graph (in the store, so SPARQL
reaches it) is written by code, and printed as what the person reads - no `gaps.md` is written:
derived from the match - per requirement the match's verdict, the projects behind it and a
one-line basis - with the analyst's `gaps.txt` folded in. `gaps.txt` holds only what the match
cannot know, one line each: `fit:`, `eligibility:`, `short:`, `surplus:` and `ask:` lines, and
rows `slug | verdict | reason`, paired to requirements by slug. A
satisfied requirement whose `asked` lists items (`Vector databases (Pinecone, Weaviate)`) that no
confirmed evidence bullet names is **flagged**, and its row must be answered `keep` or lowered.
Both are rebuilt on every run from the career as it stands; once the application graph records
a submission date, they are frozen.

**`--gaps <gaps.txt>`** prints no match: it checks the posting's own `gaps.txt`, then writes
the gaps graph and prints the assessment after its verdict line. It FAILs, and writes nothing, on a verdict above the match's (satisfied
> partial > unevidenced > unsatisfied; an `indeterminate` may become anything but satisfied or
partial), a lowering with no reason, a flagged row with no
row (once there is a gaps.txt - with none, the assessment marks it not yet reviewed), a slug that is not the posting's, and any `<!-- jsk: -->` slot still in the file. A row the
match has since moved WARNs, as do `keep` on a row no flag asks about now and a row restating
the match's verdict: each is the match's verdict already. Each row gets one finding at most. Lowering is always allowed; raising never is - when the match
under-reads, the career needs the tag or the confirmed bullet, made in the conversation. A
`gaps.md` is refused: it is an older assessment, and jsk reads none. Exit 1 on any FAIL, 0 otherwise.

**`--draft-gaps <gaps.txt>`** writes the gaps graph from the match alone and prints it, then drafts
`gaps.txt`, never over one already there: `fit:` at its default (poor when a required requirement
is unsatisfied, strong when every one is satisfied, else partial), the person's eligibility facts
as comments, a row slot for each flagged requirement, `decisions.txt`'s drops as comments, and the
match's questions as `ask:` lines - with a `<!-- jsk: -->` slot wherever judgement is needed.
`--gaps` then fails until every slot is filled.

Validation also WARNs `advert-uncovered`: a list item of four words or more, under a heading that
names requirements (requirements, qualifications, skills, experience, you'll bring, nice to have,
…), that no requirement of the posting quotes. Benefits and responsibilities lists are skipped, and
so are eligibility lines (work rights, visa, clearance, location, work mode), which belong in
gaps.txt's `eligibility:`.

### `jsk tailor prepare`

```bash
jsk tailor prepare applications/<dir>                  # the digest
jsk tailor prepare applications/<dir> --draft-gaps     # and draft gaps.txt with slots to fill
```

Everything an assessment reads, in one process and one digest, where the analyst used to make
about ten calls, each one a model turn. In order: the check, scoped to this application
plus every FAIL anywhere (as `jsk kb check --only`); the match as `jsk tailor match` prints it; `jsk kb
query evidence` for every `missing` and `candidate` term; `jsk kb query person`; the cover's
projects (at most three, or the top-ranked that carry a requirement), bullets only; and what those
projects hold unconfirmed; and the assessment - the gaps graph written on every run, with the
flagged rows and the counts by verdict, then the assessment printed under `== assessment`. Every section has a size cap and prints
`… N more cut` when it cuts. A `gaps.txt` the check refuses is reported there, not an exit 1:
the analyst may be halfway through it.

`--draft-gaps` also drafts `applications/<dir>/gaps.txt` as `jsk tailor match --draft-gaps` does, never
over one already there, and not for an application already sent. `--cover N` and `--today` are `jsk tailor match`'s.

Exit 0 digest printed; 1 a FAIL that stops the match (the career, the vocabulary or this
application's own directory - one in another application does not), printed before it stops;
2 called wrong, a `posting.ttl` path (it takes the directory), or no posting built for it yet.

## `jsk resume`

One application's `resume.json`, from the record gate through the render to the gates on the
document.

### `jsk resume check`

```bash
jsk resume check applications/<dir>/resume.json   # the record gate
jsk resume check resume.pdf                       # the parse and prose gates
jsk resume check <out-dir>                        # record, parse, prose and layout
jsk resume check <stem>|resumes/<name>            # the record gate, on its selection graph
```

One verb for every gate on a resume, which picks the gates from what it is given. A `.json` file
gets the record gate. A `.pdf` or `.tex` render, or a `.txt` named by hand,
gets the parse and prose gates, and `--only parse|prose|layout` narrows that to one. A directory gets the record, parse, prose and
layout gates over the render inside it. Each kind keeps its own flags - `--strict` and
`--max-findings` for a `resume.json`; `--strict` and `--only` (with `--record`, `--region` and
`--pages` for the layout gate) for a render; `--record`, `--pages`, `--json` and `--max-findings`
for a directory - and a flag that does not fit the target, such as `--pages` on a `.json`, is a
usage error, exit 2, that names the target kind. A cover letter is not a resume: it is
`jsk letter check`, and `--only letter` here points there.

#### A `resume.json`: the record gate

```bash
jsk resume check applications/<dir>/resume.json
jsk resume check resume.json --strict            # warnings become failures
jsk resume check resume.json --max-findings 0    # print every one
```

The **record gate**: a short `resume.json` and the career bullets it selects, before anything
renders. It finds the workspace from the file (`kbcli.find_root`, so a workspace named `career`
works) and loads it; a file outside any workspace is exit 2 naming where to keep it, and a legacy
URS record (`"urs"` key) is exit 2 naming `jsk kb export`, which writes a short one.

| Check | Severity |
|---|---|
| `career-invalid` - the career has a FAIL (`jsk kb check`) | FAIL |
| `career-unlogged` - the career and its log are out of sync: something outside jsk wrote the store. Restore it from the backup: `jsk kb load .jsk/backup.trig --root <new folder>` | FAIL |
| `career-missing` - the store holds no career to check against: `jsk kb new`, or `jsk kb load` | FAIL |
| shape - an unknown key, a wrong type, `resume` not 2, no `bullets`, a bad `format` or summary or headline `status`, an id with the wrong prefix, a duplicate | FAIL |
| ids - an id the career does not hold (with the nearest), a retired one (with its reason), a bullet whose project names no role, a `names` entry that is neither the skill's name nor one of its aliases | FAIL |
| `number-untraced` - a numeral in a chosen bullet is in no current version of a metric it cites | FAIL |
| `number-superseded` - it is only a replaced version's number; the line names the current one | FAIL |
| `label-unheld` - a vocabulary label in a bullet names a concept its project does not hold | WARN |
| `years-overstated` - "N years of X" in the headline, the summary (or the positioning in its place) or a bullet exceeds what the roles behind the projects holding X cover (`jsk kb query experience`) | WARN |
| `bracket` - a bracket in the summary or a bullet, almost always a leftover placeholder | WARN |

The number checks read ids and numbers; the label and years checks read prose, where a word may
or may not be a technology, so they warn. A label of three characters or fewer matches only as
written ("Go", never "go"); a longer one also with its first letter in the other case; the
longest label is read first, so ".NET Framework" is never read as ".NET". A shape FAIL stops the
id checks: until the shape is right the ids may not be lists of ids.

An untraced number is the one finding never to "fix" by changing the number: it is in the career, so
it is a question for the person, answered with `jsk kb apply` (the figure, cited from the bullet)
or by changing the words. `jsk kb check` and `jsk tailor match` ask the same of the career's bullets.

It replaced two gates. `validate_urs` checked a 30-47KB URS record against itself and the claims
gate checked that record against the career; most of what the two asked was whether the copy had
drifted, and with no copy there is nothing to drift. `jsk resume check` - on a `resume.json` or on
a directory - `jsk resume ship` and `jsk app freeze` all run this one.

A `.md` or a `.ttl` is exit 2 with the file to pass instead. A directory is not a `resume.json`:
it gets all four gates, below.

Exit 0 safe to render, 1 do not render it, 2 called wrong or no career to check against. Called
from code as `record.findings(doc, store, today=None) -> (fails, warns)`, `doc` a parsed short file
or a path, `store` `jsk.adapters.cli.compose.record.load(root)`.

#### A render: the parse and prose gates

Both document gates in one pass, on one file. Pass either sibling and the other is found beside it:
the parse gate reads what is actually sent — the PDF — while the prose gate reads the `.tex` it was
compiled from.

```bash
jsk resume check resume.pdf
jsk resume check resume.pdf --strict
```

A run with `--only` never closes by saying both passed. It names the three gates that did not.

##### `--only parse`

```bash
jsk resume check resume.pdf --only parse               # the rendered deliverable
jsk resume check pasted.txt --only parse --strict      # a .txt named by hand
```

The **parse gate**. Reads the PDF's text layer (or the plain text the plan emits, or a `.txt` named
by hand) for what makes applicant tracking systems mangle a resume: text that does not extract at
all, section words that appear in prose but never in a heading, leftover bracketed placeholders,
unparseable phone numbers, bullet glyphs a parser will not map, and arrow glyphs that fuse job
titles when stripped. A PDF whose `resume.json` is known - named to `jsk resume check <out-dir>
--record`, or sitting beside it - must also extract its bullets in the order of the plan's plain
text, or it fails: a parser reads the text layer as one stream and credits a bullet to the role line
above it there. The text is emitted in memory, so the rule cannot be skipped for a missing file.

The structural checks — tables, text boxes, header content, second columns — are gone. One LaTeX
template produces every render and cannot express any of them, so the check moved from the output to
a golden-file test on the template, where it is proved rather than sampled. Needs `pymupdf` for a
PDF; the plain-text path is standard library only.

##### `--only prose`

```bash
jsk resume check resume.tex --only prose
jsk resume check pasted.txt --only prose        # a .txt named by hand
```

The **prose gate** — the writing rules the parse gate cannot see. Third person, unresolved
placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
across projects, bullets that clear their throat before the verb. It reads the `.tex` rather than the
PDF, because a bullet is an unambiguous `\item` there and needs no library to find. No dependencies.

##### `--only layout`

```bash
jsk resume check resume.pdf --only layout --record resume.json
jsk resume check resume.pdf --only layout --region US --pages 2
```

The **layout gate** — what the render gate's checklist asked a model reading page images to see,
measured from the PDF instead. Each failure names its fix:

- **Tofu.** U+FFFD or a private-use codepoint in the text layer, or a Type3 font (the bitmap faces
  TeX falls back to without `lmodern`).
- **Type families.** One, or the body-and-heading pair a shipped template declares: `circuit` sets
  TeX Gyre Heros body with Adventor heads, `atrium` Pagella body with Heros heads. The checklist said
  "one family"; two templates were designed with two, so the check follows the templates. A third
  face, or a pair no template declares, is a substitution — a font package that is not installed.
- **A stranded heading.** A section title `build.py` writes that is the last text on its page.
- **The date column.** Every date range must end on the same right edge, within 1.5pt; every template
  right-aligns them with one `\hfill`, so the measured spread on our own renders is zero.
- **Paper.** Neither A4 nor Letter fails; so does the wrong one for the region (Letter for US and
  CA, A4 elsewhere).

The region and page budget come from the plan the record builds — `--record`, else a `resume.json`
beside the PDF; `--region` and `--pages` override. The page count is printed, never failed: `jsk
resume fit` owns that verdict. Without `pymupdf` it is `SKIPPED`, and a failure. `jsk resume check` on a
render never runs it unasked (it reads only the PDF); on a directory it does, and so does
`jsk resume ship`.

Not measured: a typed `•` — the template's bullet is the same codepoint in the same face, so nothing
in the text layer tells them apart — and whether it looks right as a whole, the work-rights line and
declaration, and whether it is true. Those stay a person's.

#### The terms gate

The **terms gate** runs on a directory, after the layout gate, when the record's own directory holds
a posting: the render's plain text, emitted in memory from the record's plan, against the posting's title and its required and preferred terms,
matched as strings, case aside, the way a recruiter's ATS search matches what they type. `jsk tailor
match` judges evidence by concept; this asks whether the posting's words reached the page.

- **The title** not on the page - set `headline` and confirm it with `--headline`.
- **A required term** not on the page.
- **Another name of its concept** on the page in its place - use the posting's word where it is
  true: a skill's alias in `names`, or a bullet reworded in the career.
- **The preferred terms** not on the page, in one line.
- **A term past five uses** - repetition a reader takes for stuffing.

Every finding is a warning and it exits 0: a missing term is often a gap the person has, and a gap
is never closed by a word on the page. A record with no posting beside it gets no terms gate.

#### A directory: all four gates

```bash
jsk resume check <out-dir>
jsk resume check <out-dir> --record applications/acme/resume.json --pages 2
jsk resume check <out-dir> --json
jsk resume check <out-dir> --max-findings 0
```

The record, parse, prose and layout gates over one rendered output directory, in **one process**. It is the
invocations a hand-run verification makes — the record gate on `resume.json`, the parse gate on
the PDF (held to the plain text's reading order) and again on the plain text with `--strict`
(emitted from the record's plan in memory; no `.txt` is written), the prose gate on the `.tex` — then the
layout gate on each PDF, handed the record. It imports the checkers rather than shelling out to them, and gives them the same
arguments, so the findings and the exit code are the ones those commands produce. That
equivalence is what it is tested on.

`check_ats.py` and `check_prose.py` grew a `main(argv)` entry point so it could: the same
arguments and the same output to the character as `--only parse` and `--only prose`, callable
without a subprocess. That entry point is load-bearing rather than incidental, so it is documented
here.

**`--record` defaults to `resume.json` in the output directory**, which is where the skill writes it
for an application. Named rather than searched: a directory holding two records has no way to say
which one the documents came from, and guessing would put a passing record gate against a resume it
never described.

Three properties, each of them an existing rule here rather than a new one:

- **Every gate's output is printed verbatim, never summarised.** The person should see the evidence
  rather than take anyone's word for it. The section headers match a render's check.
- **A missing input is `SKIPPED` and a failure.** A gate that did not run is not a gate that passed.
  Same behaviour and same wording as on a render. A path you *gave* that is not there is exit 2
  instead — omitting `--record` and mistyping it are different mistakes, and reporting them
  identically hides one. Both are non-zero.
- **It never attempts the render gate**, and closes with a line saying somebody has to open the PDF
  and read it. That gate is the one no command can have, and a command that exited 0 having silently
  skipped it would be the most dangerous thing in this directory.

`--pages N` reports and never fails. It measures the PDF and prints the renderer's own over-budget
line, reused rather than restated. Over budget is named rather than failed everywhere in this
pipeline, because `jsk resume fit` owns that verdict and is the command that can act on it.

`--max-findings N` caps how many findings each gate lists — the same flag name and the same default
as on a `resume.json`, because two gates that truncate differently are two gates people read differently.
The header counts stay true regardless: truncating a list is a reading aid, truncating a count is a
lie.

`--json` carries each checker's whole text in `gates[].output`, beside `gate`, `command`, `status`
and `exit`. It always includes a `render gate` entry with `status: "UNVERIFIED"` and `exit: null`,
so **the machine-readable form cannot report the render gate as passed either.** That is what makes
`--json` safe to consume here: it is the same evidence in a different envelope, never a summary.

The exit code is the worst gate's: `0` all passed, `1` any failed, `2` called wrong.

### `jsk resume render`

```bash
jsk resume render resume.json --out DIR
jsk resume render resume.json --out DIR --pdf
jsk resume render resume.json --out DIR --region au
jsk resume render resume.json --out DIR --pdf --ats-max
jsk resume render <stem> --pdf                  # a target: into applications/<stem>/
jsk resume render resumes/<name> --out DIR      # a general resume, rendered elsewhere
```

A target - an application's stem or `resumes/<name>` - renders its selection graph, into its own
directory unless `--out` names another (`jsk resume ship` keeps the target's own).

One `resume.json`, built with the career it sits in (`domain/resume/plan.py`), to `.tex` (and PDF with
`--pdf`). No `.txt` is written: the gates emit the plain text from the plan in memory, and
`--format txt` exits 2 saying so. A clean compile leaves the `.pdf` and the `.tex` and removes the
engine's `.log`, `.aux`, `.out`, `.fls` and `.fdb_latexmk`; a failed one keeps them and names the
`.log`. The PDF is the only rendered deliverable; `--ats-max` chooses which variant it
holds rather than adding a second file. A file that fails its shape or id checks, or sits outside a
workspace, is exit 2 with the fix; `jsk resume check resume.json` is the full gate. A `resume.json` is one resume,
so there is no `--view`.

| Flag | Does |
|---|---|
| `--out DIR` | where to write (default `.`) |
| `--pdf` | also run the TeX engine |
| `--region CODE` | apply a region profile over the file's `region` |
| `--profile PATH` | a profile file directly |
| `--format` | `all` (default) or `latex`; `txt` is retired and exits 2 |
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
nowhere. Over budget is named (`- OVER BUDGET, run jsk resume fit`) and not failed: `jsk resume fit` owns that
verdict, and it is the command that can do something about it. Without `pymupdf` the line says the
budget and says it was not measured, which is the honest version of the same sentence.

`--template` and `--ats-max` are different axes and compose. The variant decides what the document
says; the template decides how it looks. All five templates extract to identical text, so the choice
is about the reader and never about the parse. An unknown name is a usage error rather than a silent
fall back to the default, because a resume rendered in a template nobody chose is a resume nobody has
looked at — and it would look perfectly fine. See `references/templates.md`.

### `jsk resume preview`

```bash
jsk resume preview resume.json --out DIR
jsk resume preview resume.json --out DIR --only meridian,ember
jsk resume preview <stem>|resumes/<name> --out DIR
```

The same resume rendered in every template, with the page count for each, so the look is chosen by
looking. Writes `DIR/<template>.pdf` and `.tex`, plus a `.png` of the first page where `pymupdf` is
installed. The `.tex` files are written one after another; the TeX compiles run side by side, each in
its own scratch directory, and the report still lists the templates in their fixed order.

Density is the one difference between templates that is not a matter of taste: the same resume is
one page in a dense template and two in an airy one, and a two-page resume where a one-page resume
was available is a decision worth making on purpose.

| Flag | Does |
|---|---|
| `--out DIR` | required — previews are scratch, not deliverables |
| `--region CC` / `--ats-max` | passed straight through to the renderer |
| `--only A,B` | just these templates |

Exit 0 = every template rendered. Exit 1 = at least one did not, and that is reported rather than
worked around: a template that does not build is not a template, and the others may be about to
break too. Exit 2 = usage, or no TeX engine.

### `jsk resume fit`

```bash
jsk resume fit resume.tex --target-pages 2
jsk resume fit resume.tex --dry-run
jsk resume fit resume.tex --in-place
jsk resume fit resume.tex -o fitted.tex
```

Rewrites the density knobs in the `.tex`, recompiles, and measures the PDF that comes out. It applies
the levers in a fixed order — spacing, bullet spacing, margins, font size — stopping at the 10pt and
0.5" floors instead of crossing them. It is deterministic — a fixed plan, each step derived from the
original `.tex` — and writes one file, `<stem>-fitted.tex` (or `-o`, or `--in-place`), only when the
target is met. Its closing lines name every lever it moved and print each value beside its floor
(`margins 0.6in (floor 0.5in)`). If the target is unreachable without a breach it exits 1 with
`over by ~<n> lines at the floors`, because the remedy then is to cut evidence, not to shrink type.
`jsk resume ship` runs it on an overrun itself.

It used to measure a `.docx` through LibreOffice while the PDF was what got sent. The two disagreed,
and a resume this reported as two pages shipped as three — a gate passing on a document nobody was
sending. It now measures the artefact that goes out.

Needs a TeX engine and `pymupdf`.

### `jsk resume ship`

```bash
jsk resume ship <resume.json> --out DIR [--ats-max] [--template N] [--pages N] [--no-fit] [--json]
jsk resume ship <stem>|resumes/<name> [--ats-max] [--template N] [--pages N] [--no-fit] [--json]
```

A graph-native application (`<stem>`) or a general resume (`resumes/<name>`) ships from its
selection graph, with no `resume.json` and no `--out`: into `applications/<stem>/` or
`resumes/<name>/`, made by the render and left holding the `.pdf` and the `.tex`. A `resume.json`
inside a graph-native application is refused, naming the `resume_update` tool.

The commands a ship used to be, in one process and in order, each step's output printed
verbatim under its own `---` heading the way `jsk resume check` prints it over a directory:

1. **the record gate** — what `jsk resume check <resume.json>` runs. A failure stops here and **nothing
   is rendered**: a PDF made from a resume that failed its gate looks sendable and is not.
2. **the render** — what `jsk resume render <resume.json> --out DIR --pdf` runs, with `--ats-max` and
   `--template` passed through. A render that produced no PDF stops here.
3. **the fit**, only when the render is over its budget (`--pages N`, else the render's own:
   `ats_pages` under `--ats-max`) — what `jsk resume fit <tex> --target-pages N` runs. When the levers reach
   the budget inside the floors, the fitted `.tex` is moved over the render's and recompiled the way
   the render compiled it, and the step ends `fit: <levers>, <n> pages`. When they do not, it ends
   `over by ~<n> lines at the floors`, nothing is written, and the unfitted render is kept: cutting
   evidence is the author's call. `--no-fit` skips the step.
4. **the parse, prose and layout gates** — what `jsk resume check DIR --record <resume.json> [--pages N]`
   runs, less the record gate the first step has just run on the same file. After a fit they read
   the fitted render.

It refuses before any of them, exit 1, in a frozen application - the store holds an application
graph for the `resume.json`'s directory or `--out` - because re-rendering would overwrite what was sent (or, for
one held back with `--submitted false`, what was frozen); copy the application to a new dated directory to reuse
it. A graph-native application's fix names capturing its posting again under a new stem (`posting_capture`).

It closes with the same render-gate section `jsk resume check` on a directory does: **nobody has read the PDF**, and the
command says so rather than exiting 0 over it. When it stopped early that section says nothing was
rendered, instead of pointing at a PDF an earlier run left in `DIR`. The page count is reported —
the renderer's own line, and `--pages N`'s — and never failed, fitted or not: a render still over
at the floors is `OVER BUDGET` in the fit step, and exits as it would have before ship fitted.

Last of all, as under `jsk resume check` on a directory and `jsk app freeze`, an `=== summary` block: one line a step with
its status and the step's own `FAIL n   WARN n`, the render's page counts, the lines it withheld
below the floor, each named (`withheld 1 below the floor: ach_…`), the fit's last line, then the
verdict. Nothing in it is a new verdict - each count is
read back off the output above - and it is there so that the tail of a long ship still holds
every gate. `--json` has no summary; `steps[]` already is one.

Exit `0` only if every step passed, `1` on any failure, `2` called wrong. `--json` carries every
step in `steps[]` in the shape `jsk resume check --json` gives a directory, the render gate last and `UNVERIFIED`.

## `jsk letter`

A cover letter, beside the `resume.json` it goes out with - or, for a graph-native application,
beside the selection the store holds.

### `jsk letter check`

```bash
jsk letter check applications/<dir>/cover-letter.txt --record applications/<dir>/resume.json
jsk letter check applications/<stem>/cover-letter.txt --record <stem>   # a graph-native application
```

`--record` takes the `resume.json`, or a graph-native application's name (`<stem>` or
`applications/<stem>`, or its directory once a render has made it). For the name, the record is the
selection the store holds (`applications/<stem>/resume`) and the advert is the posting graph's
stored lines - there is no `posting.md` - so the number check and the quotation rule below read
those instead of files. A name with no selection stored exits 2, naming the `resume_select` tool.

The **letter check** — a cover letter (`.txt` or `.md`) against the resume it goes out beside. No
`jsk resume check` runs it: it checks another document, not the render.

- **Length.** Over 250 words fails. The body is counted: not the salutation line or anything above
  it, not the closing (`Sincerely,`, `Best regards,` ...) or anything under it.
- **Numbers.** Every numeral `numbers.numerals()` finds — so not a year, `p95` or `ISO 27001` — must
  be held by a current version of a metric cited by a bullet the resume renders (selected, and at or
  above its floor). Else it fails as `number-unconfirmed` when only a withheld or unconfirmed bullet
  states it, `number-superseded` when only a replaced version of a cited metric holds it, and
  `number-untraced` otherwise. "N years of X" is asked of the roles behind X, as the record gate
  does. A numeral inside quotation marks that `posting.md` beside `resume.json` holds verbatim -
  or, graph-native, one of the stored advert lines - is the posting's words and is skipped. Without `--record` the number check is SKIPPED, and fails.
- **Prose.** From the prose gate: placeholders, a sentence that stops before its object, the
  cut-on-sight phrases (a warning). Its own: enthusiasm padding — "passionate", "excited",
  "thrilled" — fails. The prose gate's resume-only rules do not apply: a letter is written in the
  first person, to someone, in sentences, not bullets.

Whether each sentence is true of the career is not checked; that would need a reader.

## `jsk app`

An application once it is sent: what went out, and what happened next - or, never sent, set aside.

### `jsk app freeze`

```bash
jsk app freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--doc FILE ...]
```

Freezes one `applications/<yyyy-mm-dd>-<company>-<role>/` directory the way `references/mode-ship.md`
describes: renames it to the day it was sent, if its leading date says otherwise, and records what
was sent as the application graph, `applications/<dir>/application` in the store, as
`jsk kb show k:app_acme_platform` prints it:

```turtle
k:app_acme_platform j:posting k:post_acme_platform ; j:view "resume" ;
    j:submitted "2026-09-08"^^xsd:date ; j:channel "Workday portal" ;
    j:document "Priya_Raman_Acme_Resume.pdf", "cover-letter.txt" ;
    j:recordSha256 "7bc8...9f9c" ;
    j:carried k:ach_events_latency, k:ach_events_team ;
    j:carriedVersion k:met_latency.v2, k:met_team.v1 .

k:evt_acme_platform_2026_09_08_submitted j:application k:app_acme_platform ;
    j:date "2026-09-08"^^xsd:date ; j:kind j:submitted ; j:channel "Workday portal" .
```

The id's stem is the posting's (`k:post_acme_platform` in the posting graph, which must be
there), and never changes when the directory is renamed. `recordSha256` is the frozen `resume.json`'s,
byte for byte. `carried` is every bullet that rendered - the plan's `sent`, so one withheld below
the floor is not carried - and `carriedVersion` is the current version, now, of every metric those
bullets cite. No copy of the content is written: the PDF and `.tex` beside it, and any letter,
are the words sent. That is what makes a later
revision visible: `jsk kb apply` never changes a sent version - a new number becomes the next
one - and `jsk kb query stale` names every application that sent the old. The graph is validated
with the whole record before anything is renamed or written, and goes in through the same write
gate as every other write. It adds no log entry: the log is the career's history, and the career
itself is never touched. A graph is named by its directory, so when the directory is renamed its
posting, assessment, review and selection graphs - whichever it holds - move to the new name in
the same update that writes the application graph - all of them land, or none does and the
directory is renamed back.

The documents are the `--doc` files, or every `.pdf` and every `.txt` letter in the
directory - the PDFs and the letters; a render writes no `.txt`, and the `<Name>_Resume_ATS.txt` an
earlier one left is not listed. The final path is printed.

A **graph-native application** (its posting graph holds the advert's lines) has no `resume.json`,
and one beside it is never read. Its record is the selection the store holds,
`applications/<dir>/resume`: `recordSha256` is the SHA-256 of that selection's canonical text
(`json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, UTF-8), and
`carried` is the plan built from it, as `jsk resume ship <stem>` built the render. The gates run
against the selection, a letter's with `--record <stem>`. The rename moves all five of its graphs -
`posting`, `review`, `gaps`, `resume` and the new `application` - in one update. After it, the
`resume_update`, `posting_decide` and every other writing tool refuse it as sent, and `jsk resume
ship <stem>` refuses the frozen directory. A held-back freeze (`--submitted false`) is refused
alike, the refusal saying it was frozen, not sent, and naming `posting_capture` under a new stem
as the way to reuse it. With no selection stored it refuses: `no resume stored for <dir>`, naming
the `resume_select` tool.

It refuses — exit 1, saying why, with nothing renamed and nothing written — when:

- **the application is already frozen** - the store holds its application graph, or the
  directory holds an `application.md` from before the graph record. A frozen application is
  never re-frozen; later events are `jsk app event`.
- **any mechanical gate fails.** It runs what `jsk resume check <app-dir> --record <app-dir>/resume.json`
  runs - the record gate first - in process, and prints it. A failing document is never frozen.
- a graph-native application has no selection stored (`no resume stored for <dir>`).
- no posting graph was built for it, there is nothing to list as documents, the renamed directory
  would land on one that already exists, or the application graph it would write does not validate.

`--submitted false` is for an application worked through and deliberately held back: it writes
`submitted false`, leaves the directory's name alone, and records **no `submitted` event** — an
accurate blank rather than a false green. It never touches the career.

### `jsk app event`

```bash
jsk app event applications/2026-09-08-acme-platform screen-scheduled --date 2026-09-15 --due 2026-09-18
jsk app event applications/2026-09-08-acme-platform rejected --date 2026-10-02 --channel email
jsk app event applications/2026-09-08-acme-platform note --date unknown --note "Recruiter said Q4."
```

Adds one event to a frozen application's graph: `k:evt_<stem>_<date>_<kind>`, with
`--channel`, `--note` and `--due` when given. The kind is the closed pipeline vocabulary -
`submitted`, `acknowledged`, `screen-scheduled`, `screen-done`, `interview-scheduled`,
`interview-done`, `onsite-scheduled`, `onsite-done`, `offer`, `offer-accepted`, `rejected`,
`withdrawn`, `no-response`, `offer-declined`, `follow-up-sent`, `note`, `referral`,
`recruiter-contact` - and a kind outside it is exit 2 with the nearest one suggested. The date is
`YYYY-MM-DD` or `unknown`: the day it happened (a `-scheduled` event's is the day it was booked; the
meeting is its `--due`). Both are printed back with weekday and distance - `recorded
screen-scheduled on 2026-09-22 (Tuesday, 4 days ago)` - so date arithmetic gone wrong shows as the
wrong weekday; a `--date` after today is a WARN. `--today` fixes the day, for tests.

Add-only: it never edits or removes an event. A second event of the same kind on the same day -
another note, a round-2 `interview-done`, a second `unknown`-dated contact - is minted
`k:evt_<stem>_<date>_<kind>_2`, then `_3`; only an
event identical to one already there (same kind, date, channel, note and due) is refused. The whole record is loaded with the
event in it and validated before anything is written, and the event goes in through the same write
gate as every other write. An application frozen as `application.md` is pointed at its
`# Timeline` table.

The stage is never stored: `jsk kb query pipeline` derives it from the latest dated event.

Exit 0 added, 1 refused, 2 called wrong.

### `jsk app drop`

```bash
jsk app drop applications/<stem> [--reason TEXT] [--dry-run] [--today YYYY-MM-DD]
```

Sets aside an application that was never frozen - made from files or graph-native - when it will
not be sent. It removes every graph the store holds for it (`posting`, `review`, `gaps`,
`resume`, whichever it has) in one update, after validating the workspace without them as every
writer validates; then it moves the folder, files intact, to `dropped/<stem>/` beside
`applications/` (`dropped/<stem>-2`, `-3` when that is taken) and writes a `DROPPED.txt` there
with the day, the `--reason` and the graphs removed. A graph-native application with no render
has no folder: its `dropped/<stem>/` holds the note alone. The stem alone works inside the
workspace. Out of `applications/`, nothing counts it again: `jsk kb check`'s `file-made-unsent`,
the `app_list` tool and `jsk doctor` stop naming it. Moving the folder back brings back the files,
not the graphs.

```
ok    removed applications/contoso-platform/posting from career/store/
ok    moved applications/contoso-platform/ -> dropped/contoso-platform/
ok    wrote dropped/contoso-platform/DROPPED.txt
dropped applications/contoso-platform - never frozen, so never sent; its files are in dropped/contoso-platform/
```

`--dry-run` prints the same lines as `would remove`, `would move` and `would write`, then
`dry run: nothing was written or moved`, and writes nothing.

It refuses - exit 1, `nothing was written or moved` - a **frozen application**, sent or held back
(`--submitted false`): that is the archive of what went out, and the fix is an event, `jsk app
event applications/<stem> withdrawn --date YYYY-MM-DD`. It refuses a removal the workspace would
not validate without. A path that is no application - no folder under `applications/` and no graph
for it - is exit 2. If the folder cannot be moved after the store was written, it says so (exit
1); running it again finds no graphs and moves what is left. It has no MCP tool: setting an
application aside is the person's decision. It is not a file verb, and 6.0 keeps it.

Exit 0 dropped or a dry run, 1 refused, 2 called wrong.

## `jsk mcp`

```bash
pip install 'jsk-resume[mcp]'
jsk mcp                          # serves until the client closes stdin
JSK_ROOT=~/my-career jsk mcp     # a workspace other than the one around the current directory
```

Serves the career and graph-native applications to an agent as MCP tools, over stdio - the
plugin starts it, one process per session. It takes no arguments. The workspace is `JSK_ROOT`
when set, else the one around the directory it started in; a call made with none answers with
the `jsk kb new` fix. Without the `mcp` extra it prints
`the MCP server needs the mcp extra: pip install 'jsk-resume[mcp]'` and exits 2.

Every result is JSON: `{"ok": true, "findings": [...], ...}`, or `{"ok": false, "findings":
[...]}` with each finding `{severity, text, fix}`. A refusal is its findings, never a traceback;
an unexpected error is one `FAIL` naming the tool, its traceback on the server's stderr, and the
server keeps serving. A write tool takes the writers' turn for that call alone, exactly as a
command does, so a tool write and a `jsk kb apply` in another shell queue for each other; nothing
is held between calls. Reads share one loaded record until the store on disk moves.

| Tool | Does | Wraps |
|---|---|---|
| `career_view(section?, offset?, limit?)` | the career as Markdown, paged (`next`) | `jsk kb view` |
| `career_show(ids, bullets?)` | entries as Turtle, with the revision for `op:base` | `jsk kb show` |
| `career_query(name, args?, offset?, limit?)` | any named query, rows as JSON, 50 a page with `total` and `next`; `concepts` with terms finds the nearest | `jsk kb query` |
| `career_log(last?)` | the history, newest first | `jsk kb log` |
| `career_preview(changeset)` | a TriG changeset dry-run: the diff, findings; nothing written | `jsk kb apply --dry-run` |
| `career_apply(changeset)` | apply it: validated, written, logged; new claims arrive inferred | `jsk kb apply` |
| `career_confirm(ids?, target?, block?, answer?, source?, quote?)` | confirm entries with the person's answer or a document's quote; or a selection's summary or headline, returning that block alone | `jsk kb confirm` |
| `app_list()` | every application and general resume: kind (`native` or `files`), posting state (`draft`, `complete`, or `built` from files), review state, stage | `jsk kb query pipeline` |
| `app_show(app, part, offset?, limit?)` | `posting`, `lines` (paged), `requirements`, `review`, `assessment`, `selection` | the graphs |
| `posting_capture(app, url? \| text?, company?, title?, captured?, replace?)` | an advert fetched or pasted, stored as a draft posting's lines | `jsk posting fetch` |
| `posting_decide(app, header?, requirements?, drops?, remove?)` | requirement rows and drops upserted, each checked against its line; a slug to remove that is not there is a FAIL | `jsk posting build`'s checks |
| `posting_complete(app)` | every qualification line used or dropped, the rules clean; `complete` | build's coverage check |
| `assessment_derive(app)` | match, fold the stored review, write the assessment; rows, fit, questions | `jsk tailor match` |
| `assessment_review(app, fit?, eligibility?, verdicts?, short?, surplus?, asks?)` | the review upserted, each verdict checked against the match; an ask's `about` (a requirement's slug) is kept, so its question carries that requirement's concepts | `--gaps` |
| `assessment_complete(app)` | every flag answered, no FAIL; the review `complete` | |
| `resume_select(target, mode, replace?)` | `from_match` or `ranked`; the selection stored | `jsk kb export` |
| `resume_update(target, bullets?, roles?, skills?, names?, format?, region?, pages?, ats_pages?, floor?, summary?, headline?)` | the selection changed; a changed summary or headline drops to inferred | `resume.json` edits |
| `resume_ship(target, ats_max?, template?, pages?, fit?)` | record gate, render, fit, gates into the directory; each step as JSON | `jsk resume ship` |
| `app_freeze(app, submitted, channel, docs?)` | every gate, then the application's record written and the directory renamed to the day sent (`submitted` is `YYYY-MM-DD` or `false`); `written`, `renamed_to`, `recordSha256`, `carried`, `documents` and each gate's step. A refusal writes nothing | `jsk app freeze` |
| `app_event(app, kind, date, channel?, due?, note?)` | one event added to a frozen application's record; the event, and its dates with their weekday | `jsk app event` |
| `letter_check(letter, record)` | a cover letter (a path in the workspace) against a stem's selection or a `resume.json`; the `verdict` line, each FAIL and WARN with its fix, and the output | `jsk letter check` |

`app` is an application's stem (`applications/<stem>`); `target` is a stem or `resumes/<name>`.
The tools refuse an application made from files, naming the file verb that still works on it;
the file verbs refuse a graph-native one, naming the tool. `app_freeze`, `app_event` and
`letter_check` are the exceptions: like their commands, they take either kind.

The plugin (5.0.0) starts this server as `jsk`, so Claude Code names each tool
`mcp__plugin_jsk_graph__<tool>`. Each agent's `tools:` lists the ones it may call by name: the analyst
the career reads, `app_show`, `posting_*` and `assessment_*`; the author the career reads,
`career_preview`, `career_apply`, `app_show`, `resume_select` and `resume_update`; the extractor
the career reads and `career_preview`. No agent holds `career_confirm`: only the main session,
which talks to the person, confirms. No agent holds `app_freeze`, `app_event` or `letter_check`
either (2026-10-03): freezing and recording an event are the person's acts, done by the main
session.

What stays a command only: `jsk kb new`, `jsk doctor`, `jsk kb dump` and `load`, and `jsk
resume check`, `render`, `preview` and `fit` over a directory - a person's acts, or a
verifier's tracing.

Exit 0 when the client closes the session, 2 for arguments or a missing extra.

## What is not here any more

**The top-level commands and the module paths** - `new`, `match`, `validate`, `check`, `gates`,
`render`, `preview`, `fit`, `ship`, `event` and `freeze` as commands of their own, and the
`python -m jsk.<module>` path behind each subcommand - left on 2026-10-01 for `jsk <noun> <verb>`.
`new` is `jsk kb new`; `match` is `jsk tailor match`; `validate`, `check` and `gates` are all
`jsk resume check`, which picks the gates from its target; `check --only letter` is
`jsk letter check`; `render`, `preview`, `fit` and `ship` are `jsk resume`'s; `event` and `freeze`
are `jsk app`'s. The flags did not change. Each old command, and each module path, exits 2 naming
its replacement: none of them keeps running, because two names for one thing is what the change
removed. `python -m jsk` stays, for a machine without `jsk` on its PATH.

**`jsk index`** read `user-knowledgebase.md`: an overview with line ranges, and `--rank` against
a posting's frontmatter. The career is a graph record now - `jsk tailor match` ranks it against a
posting, `jsk kb view` and `jsk kb show` read it - and `jsk index` says so and exits 2.

**`jsk migrate`** moved a `user-knowledgebase.md` to `career/kb.ttl`, once. The Markdown knowledge
base is no longer read: `jsk migrate` says so, naming `jsk kb new PATH --name NAME` to start a
record. A frozen `application.md` is still honoured as frozen.

**The record as `.ttl` files** - `career/kb.ttl`, `career/log.ttl` and each application's
`posting.ttl`, `application.ttl` and `gaps.ttl` - left on 2026-09-29 for `career/store/`. With the
files went `jsk kb adopt` (log a hand edit), `jsk kb fmt` (restore the canonical layout), the
`hand-edited`, `torn` and `unlogged` states of a stored record, and `.jsk/kb.last.ttl`: there is
no file to edit by hand, no layout to restore and no second file to tear. (Each log entry still
carries `kbSha256`, the hash of the career as the writer lays it out; `jsk kb load` of a dump and `jsk kb check` check it.) So did git
diffs of the record and opening it in an editor - `jsk kb view`, `show`, `log` and `dump` read it
instead ([WHY.md](WHY.md) says what that cost). `jsk kb load .` imports such a workspace, once.

**The URS record** - the full `resume.json` copied out of the career, with its views, its 11KB
specification and its claims gate - left on 2026-09-25. The short file names what one resume
shows and the career supplies the rest; a full record is refused, naming `jsk kb export` to write
a short one, and a frozen application keeps its own as the archive of what was sent. `--view` went from `render`,
`preview`, `gates`, `ship` and `freeze`, and `--urs` and `--refresh` from `jsk kb export`.

The `okf` commands left with the bundle format, in 4.0. The graph record brings back a write path -
see [WHY.md](WHY.md) for why that is not the same decision made twice - but one generic verb,
`jsk kb apply`, whose coverage is the ontology, not a command per noun.

---

Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
