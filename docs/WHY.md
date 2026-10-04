# Why it works this way

Every design decision here has a failure behind it. This document is the reasoning; you can use the
plugin without reading a word of it.

## The knowledge base is the source of truth

Most resume tools start from a blank page every time. This one keeps your whole career in one
record and treats a resume as one *rendering* of it.

Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.

The record is `career/store/`: one graph store in your workspace, read and written only through
`jsk`. It is yours - a folder on your disk, not a service - and `jsk kb dump` writes all of it out
as plain TriG text whenever you want a copy another tool can read. Back the workspace up; what
outlives any single tool, this one included, is the dump.

## One graph, kept in one store

The career is a graph - every organisation, role, project, bullet, metric and question is a node
with an id, and every "this bullet is about that project" or "this number is that metric" is an
edge. Every record is a named graph in one Oxigraph store (RocksDB on disk) at `career/store/`:
`kb` for the career, `log` for its history, and for each application `applications/<stem>/`'s
`posting` (the advert as numbered lines, and its requirements), `review`, `gaps`, `resume` (the
selection) and, once sent, `application`. The only files beside them are what was rendered and sent
- the PDF and the `.tex` - because those are documents, not the record. An application made from
files before 6.0 keeps its `posting.md` and the rest; if it was sent, its quotes are still checked
against that `posting.md`, and if not, `career_check` names it for jsk 5.1.0 or `app_drop`.

You read the career with `career_view`, which prints it as Markdown in the order the knowledge base
always had: Identity, Positioning, Work authorization and languages, Vocabulary, Organisations,
Roles, Projects, Metrics, Skills, Education, Certifications, Open source, Open questions. `jsk kb
show <id>` prints entries as Turtle, bullets under their project and versions under their metric,
prose in `"""` blocks - the shape a changeset is drafted in:

```turtle
k:prj_clinical_events j:name "Clinical event platform" ;
    j:position k:pos_meridian_principal ;
    j:strength 5 ; j:recency 2025 ; j:seniority j:architecture-ownership ;
    j:uses c:event-driven-architecture, c:kafka ;
    j:headlineMetric k:met_event_latency ;
    j:problem """Clinical events took up to five minutes to reach the wards, and nurses
learned to phone the lab instead.""" ;
    j:provenance j:confirmed .

k:ach_clinical_events_cut_latency j:project k:prj_clinical_events ; j:rank 1 ;
    j:text "Cut p95 clinical event latency from 5 minutes to under 1 second." ;
    j:cites k:met_event_latency ; j:shows c:kafka ;
    j:provenance j:confirmed .
```

**It is validated every time it is loaded.** Every `jsk` command that reads the career copies
every record graph out of the store into an in-memory graph, adds the shipped vocabulary, and runs
every rule over it before doing anything else: a bullet citing a metric that does not exist, a role
pointing at an organisation that does not exist, a confirmed entry with no answer behind it, a date
that does not parse. The store can only hold what passed - but a new release's rules must still
reach an old record, and loading is where they do. A finding names the graph (`kb`,
`applications/acme-sre/posting`) and the entry's id. A far larger career than anyone has - three
hundred projects of three bullets each and a hundred applications, about sixteen thousand triples -
read out of the store and validated in 441-519 ms on a Windows desktop, where the same workspace
parsed from its files took 580 ms on the same machine; `tests/test_graph_budget.py` fails past 1.2
seconds, so there is no reason to check less than everything.

**Every write goes through one gate.** `career_apply` and `career_confirm`, and the `career_pack` and `career_merge` changesets applied through
`career_apply`,
the posting, review, assessment and selection tools, `app_freeze` and `app_event` all end
in the same function: it writes every
graph the change touches in one update - all of them or none - and refreshes `.jsk/backup.trig`.
Every write to the career gets a log entry, in the same update; `app_freeze`, `app_event` and the
application tools write only an application's graphs and add none, because the log is the
career's history; the one-time import adds one entry of its own (`by load`). A writing command
takes the writer's turn (`career/store.lock`) before it reads the record, so what it validates is
what it writes over. Two writers queue rather than one being turned away: the second prints
`waiting for another jsk write to finish`, goes when the first is done, and reads what the first
left. If the first changed nothing the second's changeset names, the second still applies; if it
did, the second is refused, naming the ids.
Readers do not queue behind a writing command, but each read waits for any single write's
open-update-close in progress (`career/store.access`, shared by readers, exclusive to a write):
a read-only open while another process writes is undefined behaviour in the store.

### What the store costs

The career used to be `career/kb.ttl` and `career/log.ttl`, plain Turtle files laid out to be read
top to bottom, with every application's graphs as `.ttl` files beside it. Moving them into a store
was the project owner's decision (2026-09-29), and git history, diffs, hand edits and plain text as
the record were each weighed and given up for it. What went with them:

- **No text to open.** There is no file to read in an editor. `career_view` prints the whole career
  as Markdown; `career_show` prints entries as Turtle; `jsk kb dump` writes everything out as TriG.
  Each is a command to run, not a file that is simply there.
- **No hand edits.** Fixing a typo is a changeset through `career_apply`, never a save in an
  editor. A person who could once correct their own record by opening it now needs `jsk` to.
- **No git history of the record.** A store's files are not text a diff can read, so `git log` on
  the workspace no longer says what changed in the career. `career_log` does - every revision, its
  day, the command, its summary and the ids it minted and touched - but only inside jsk.
- **A format tied to one library.** The files under `career/store/` are RocksDB as the pinned
  pyoxigraph writes it, and a later version may not open them. The escape hatch is the dump: raising
  the pin means `jsk kb dump --out record.trig` with the old version, then, with the new one, `jsk
  kb load record.trig --root <a new empty folder>` (or move `career/store/` aside and load with
  `--root .`), and copy the `applications/<dir>` folders across - their documents are files, not
  the record. jsk also overwrites `.jsk/backup.trig` after every write, so a store that will not
  open can be loaded again from it the same way.
- **Numbers are kept by value.** The store keeps `8.40` as `8.4` and `007` as `7`, so there is no
  parsed text left to recover the original spelling from. Rather than change a number silently, a
  changeset or a dump that holds one the store would rewrite is refused (`write
  8.4`); the one-time import of a workspace of files rewrites each one and lists it. A grade whose
  zeros matter (`3.80`) is written as a string.

### What the store buys

- **Atomic writes across graphs.** One change - a confirm, a freeze, a posting rebuilt with its
  assessment - updates every graph it touches in one transaction. With files, `apply` wrote
  `kb.ttl` and then `log.ttl`, and a crash between the two renames left them disagreeing; a hash, a
  shadow copy and a `torn` state existed only to notice that afterwards.
- **No hand-edited or torn states.** Nothing outside jsk writes the store, so the states that
  covered a file changed behind jsk's back - `hand-edited`, `torn`, `unlogged` - and the `jsk kb
  adopt` and `jsk kb fmt` commands that answered them are gone. `out-of-sync` is left only for a
  store something outside jsk wrote, restored from the backup.
- **Queued writers.** Two sessions writing at once wait their turn instead of racing two renames.
- **One gate.** Every jsk write goes through the rules, the log and the lock. The way in from
  outside - `jsk kb load` of a dump - is refused when the dump's career is not what its log last
  hashed (`kbSha256`, the career as the writer lays it out), so an edited provenance or number
  does not slip in unlogged; `career_check` asks the same of the store itself.

### What the graph costs

Before the store, the graph record itself reversed a decision written down here, and those costs
are real still:

- **A dependency.** `pyoxigraph`, a graph engine, is now the one required package. It ships
  wheels for every platform jsk supports and has no dependencies of its own; the pin is one minor
  version, and raising it reruns the Windows and Linux CI jobs. A machine without it can still run
  the parse and prose gates over a render, and `jsk doctor` says what it lost - but it cannot read
  or change the career, or build a resume from it.
- **A syntax.** Turtle is not Markdown. `k:prj_x j:name "..." ;` is learnable in a sitting, but it
  is punctuation a changeset has to get right, and a missing `;` is a parse error. In Turtle the same
  career was about 1.17 times its tokens in Markdown (measured on the P0 sample). Agents
  read by id - `career_show`, the match - and never the whole record.
- **A write path.** Nobody edits the career directly; a *changeset* goes to `career_apply`, which
  merges it, validates the result and logs it. That is a command, a format, a log (`career_log`)
  and a set of refusals to learn - exactly the kind of layer this project once removed.

### Why the earlier decision was right, and why it no longer holds

Earlier versions kept the career as a graph of several hundred linked Markdown files, with a
compiler over them, a write command per noun (`okf`, about thirty commands) and a query layer to
read them back. That was taken out, and this page said why: that shape is right for a knowledge
base too large to hold in one context, and a career is not. One file needed no write transaction,
no cross-document ids, no compile. The cost - that nothing checked the file until a hand-written
`resume.json` reached the record gate - was accepted for a document the person could open, read
end to end and correct. That reasoning was sound for the question it answered, which was **size**.

The case now is not size. It is **guarantees** a single Markdown file cannot give and a model
cannot hold by itself. A simulation of twelve scenarios over the graph
(`docs/superpowers/experiments/2026-09-24-graph-simulation/`) showed them one by one:

- **Validation on every load.** A broken reference in Markdown is found when a resume fails - or
  never. In the graph it is found the next time anything runs.
- **One-way matching.** "Kubernetes" counts as "container orchestration"; the reverse does not. A
  model under pressure to fit a posting blurs that. A vocabulary of `isA`, `partOf` and `implies`
  edges, walked at most two hops and never across a `distinct` wall, does not: matching scored
  precision 1.000 and recall 0.958 against 0.792 and 0.792 for fuzzy string matching.
- **Versioned history.** A metric revised from 62% to 58% keeps both versions, dated; the version
  an application sent can never change, and `career_query("stale")` names every application that sent
  a number since replaced.
- **A record gate that joins by id.** A selection names career bullets by id, so "is every
  bullet one the career holds, live, under a project with a role, with numbers from the metric's
  current version" is a join, run inside `resume_check`, `resume_ship` and `app_freeze`. The
  simulation's seven planted defects were all caught - by the claims gate this replaced, when
  `resume.json` was still a full copy of the career and wording could drift from it. The selection
  holds no bullet's words now: one reworded for a posting is reworded in the career, where `career_apply`
  drops it to `inferred` and the render withholds it until `career_confirm` confirms the
  career's text.

None of those needs the career to be large. All of them need it to be structured data with ids.

### How each failure of the old write layer is answered

The `okf` layer failed in specific ways, and removing it was the right response to them. The
graph record keeps a write path, so each failure needs an answer:

| What went wrong with `okf` | How the graph record answers it |
|---|---|
| The skill named about thirty verbs, costing 5,128 tokens resident in every session | Three new top-level verbs: `kb`, `match`, `event`. Sub-verbs live in `--help` and in each refusal's `fix:` line, not in the skill's entry point |
| A missing verb meant hand-authoring the file; the CLI's coverage was the agent's ceiling | One generic `career_apply`, whose coverage is the **ontology**: anything the format can say, a changeset can say. `j:note` on every class is a relief valve for anything it cannot. There is no file to hand-author, so there is nothing to route around the verb to |
| Unsafe defaults: a `--status confirmed` flag; `--body -` reading stdin and hanging | There is no status flag. A changeset asserting `confirmed` is refused. Stdin (`-`) is refused. The only way to confirm is `career_confirm`, with the person's words logged |
| Cross-file atomicity was claimed and not real | Real now. Every write is one update of the store: the career, its log entry and any application graph it touches change together or not at all. The file record before it wrote `kb.ttl` then `log.ttl` and could only **detect** a write torn between them |
| Surgical writes were promised, and a person's file got redumped | There is no file layout to redump. `career_show` prints entries in one fixed shape, so what an agent reads is what it drafts against |
| This page said a person must be able to read and correct their record end to end | Read: `career_view` prints the whole career as Markdown to stdout, never a second copy that could drift. Correct: through a changeset, not by opening the record - the part of that promise the store gave up |

Three limits, stated rather than hidden. The store can be read only through `jsk`: a person
without it, or without pyoxigraph, has `.jsk/backup.trig` and nothing more readable. `jsk kb
confirm --answer` is an instruction with an audit trail, not a proof that anybody asked the
person. And the hash that refuses an edited dump is a gate against accidents and casual edits,
not against a determined person with the file: someone who edits a dump and recomputes its
`kbSha256` can still load it.

## Every document is rendered from the career, never hand-built

The LaTeX, the PDF and the plain text the gates read are all built from the career and a
[selection](../plugins/jsk/skills/jsk/references/resume-format.md) - resume.json's keys, kept in the
store since 6.0, naming the bullets chosen for one posting, by id, and its settings. Its one piece of prose is the summary.

Two hand-built documents have to agree about every date, bullet and number, and they stop agreeing
the moment one is edited; usually silently, usually in the copy that gets sent. One career with
several emitters cannot drift, because no emitter decides what the document says.

`resume.json` used to be a URS record: a 30-47KB copy of the career written out for each
application (ElevenLabs: 41KB, of which the view and the summary - all anyone authored - were 3KB).
The copy is what needed an 11KB format specification, a `--refresh` to re-read the career into it
after every confirm, and drift checks in a claims gate to notice when it had not been. The emitters
never read it - they read the render plan - so the copy went (2026-09-25): the career and the short
file build the plan directly, and a bullet confirmed or corrected in the career is on the next
render with nothing to update.

It is also what makes a resume answerable a year later. `app_freeze` records in the application's graph
which bullets rendered and which metric versions they cite, beside the PDF that was
sent, so "what did this application claim, and where did that come from" has an answer.

The plan is built once — selection, ordering, provenance filtering, region, ASCII folding, date
formatting — and the emitters translate it into markup without deciding anything. That split is
what guarantees the PDF and the text the gates read cannot say different things. That text is
never written to a file: the gates emit it from the plan in memory, so it cannot go missing or
stale beside the PDF.

## Four gates, not one

**A checker verifies that a document parses — not that it is correct.** That sentence is the whole
reason there are four gates.

The parse gate passed a resume whose bullets rendered as tofu boxes. It passed one whose headings
silently resolved to a theme font. It passed one written in the third person. All three correctly,
all three outside its scope. The first two are visual, and no text extraction can see them; the
third is why the prose gate exists at all.

| Gate | Question | How |
|---|---|---|
| Record | Does the selection name only live career entries, and does every number in a chosen bullet trace to a current metric? | `resume_check(<stem>)`, before anything renders |
| Parse | Will an ATS read this without mangling it? | `resume_check(only="parse")`, on the PDF |
| Prose | Does it obey the writing rules? | `resume_check(only="prose")`, on the `.tex` |
| Render | Does it *look* right, and is it *true*? | Open the PDF and read every page |

`resume_ship` runs the first three in one process — the record gate first, and nothing renders if it
fails — and exits 0 only if all of them passed. It then says, in its own
output, that the render gate has not been run, because no command can run it. A tool that exited
green without saying so would teach everyone who used it that the fourth gate is decorative.

Without a renderer, a resume is marked **unverified** rather than assumed fine. A page count nobody
measured is a page count nobody knows.

## What the parse gate actually looks for

The things that make applicant tracking systems silently mangle a resume: tables, text boxes,
header/footer content, section words that appear in prose but never in a heading, any leftover
bracketed placeholder, an unparseable phone number, and arrow glyphs that fuse two job titles into
one when the arrow is stripped. A resume that fails the checker is not delivered.

## What the prose gate catches that parsing cannot

Third person, unresolved placeholders, sentences that stop before their object, phrases that read as
junior, bullets repeated across projects, and bullets that clear their throat before reaching the
verb. A resume written in the third person is not a parsing defect, so nothing was catching it.

## Numbers are checked against the career

Every numeral in a chosen bullet must be in the *current* version of a metric the bullet cites in
the career, or the record gate fails before anything renders. A number the career has since revised
fails as superseded, and one no metric holds fails as untraced. It is the check that catches a
rewritten bullet quietly inflating a figure - and the one a model must not "fix" by changing the
number: on the ElevenLabs run "300-400 candidates" became "300-800" to match an unrelated metric.
An untraced number is a question for the person. `career_check` and the match run the same check
over the career's bullets, so the question is asked before a resume is written.

## Tailoring cannot invent, structurally

A tailored resume is a *selection*: it names evidence by id and orders it, and holds no
bullet's words. The record gate fails an id the career does not hold, so a posting the career has no
evidence for produces nothing to point at rather than a plausible new bullet.

A posting's requirements are built into its posting graph, each with the advert's own words as a
quote that is checked, verbatim, against the advert's stored line. The match joins them with the
career through the vocabulary and **shows the path behind every match** - which project holds the
concept, through which edge, how many hops, and whether a confirmed bullet shows it or only the
project's tags say so. A score nobody can recompute would be worse than no score, and that is the
whole reason the working is printed rather than the ranking asserted.

It reports what each project *failed* to match, and tells you where you fall short instead of
flattering you. Being flattered costs interviews.

## Agents work through typed tools, and their grants are the boundary

Since 5.0.0 the plugin's agents reach the record through `jsk mcp`, an MCP server the plugin starts,
instead of writing text files for the CLI to read and running `jsk` in a shell.

**Typed batches.** The analyst used to write `decisions.txt` and `gaps.txt` in a format of their own,
then run a command that parsed them and named every problem. Now it sends the same decisions as JSON
fields - a requirement row `{n, slug, asked, concepts}`, a drop `{n, reason}`, a verdict lowered with
its reason - in one call, and each row is checked against the stored advert line or the derived match
before anything is written. There is no format to get wrong, no shell quoting of an advert's
apostrophes, and no file left behind that disagrees with the graph. A model still writes only
decisions; code still writes every triple.

**Grants as boundaries.** Each agent's definition names the tools it may call, one by one. The
analyst holds the posting and assessment tools and nothing that writes the career, so "never touch
the career" stopped being only a sentence it was asked to obey: it has no way to. The author holds
`career_apply`, which writes only `inferred`, and no agent holds `career_confirm`, because a
confirmation carries the person's own words and only the conversation with them can supply those.
The grants hold because Claude Code holds a subagent to an explicit tool list (measured, 2026-10-02);
a wildcard or an omitted list would hand every agent every tool, which is why the tests forbid both.

## Two variants, because readability and parsing conflict

A presentation variant for humans, an ATS-maximal variant for portals. One document cannot be optimal for both readers, and pretending otherwise means quietly losing
one of them.

Each render's PDF holds one variant — `--ats-max` chooses which — rather than every render producing
both. A second PDF is a second thing to measure, and when the thing measured is not the thing sent,
a resume reported as two pages ships as three.

## Every fact carries provenance

`confirmed` (you said it), `inferred` (written for you, needs sign-off), `needs-verification` (a known
gap), `disputed`. Nothing inferred reaches a resume unconfirmed.

You will often be written better prose than you spoke; that is useful, but reasoning supplied on your
behalf is not yours until you agree with it. The danger is precisely that it reads well — plausible,
well-written, and indefensible when an interviewer asks a follow-up.

So the write path cannot confirm anything. A changed claim drops to `inferred` and gets a question;
`career_confirm` is the only way up, and it takes your answer in your words and keeps it in the log.

## The same career renders correctly in different markets

A region profile holds a market's conventions: paper size, page budget, the sections in order, and
whether a declaration or a work-rights line is rendered. India expects three pages, academic grades
on their own scale and a declaration block; Australia and the Gulf screen the right to work before
anything else. Australia, India and the UAE ship as profiles, and adding a market is a JSON file.
What the career does not hold is not rendered: a photograph, a date of birth or a nationality comes
back only when the ontology has a place for it.

## Why a graph instead of JSON Resume

JSON Resume is a JSON container around unstructured prose. A bullet is a bare string, so nothing can
verify a metric. Nothing carries an id, so tailoring means copy-and-mutate and the copies drift.
Nothing carries provenance, so "I measured this" and "a model wrote this" look identical. And a
promotion has to be modelled as two duplicate employers.

The career graph answers each: a bullet carries an id and a provenance and cites a metric
version, and a promotion is two roles at one employer.

## Fitting a page budget without lying about it

`resume_fit` renders the document, measures which block spilled and how much room the page actually
had, then applies density levers in a fixed order — spacing, bullet spacing, margins, font size —
stopping at the 10pt and 0.5" floors instead of crossing them. If two pages are unreachable without a
breach it exits non-zero and says so, because the remedy then is to cut evidence, not to shrink type.

---

Next: [Quickstart](QUICKSTART.md) · [Concepts](CONCEPTS.md) · [Architecture](ARCHITECTURE.md)
