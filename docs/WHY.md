# Why it works this way

Every design decision here has a failure behind it. This document is the reasoning; you can use the
plugin without reading a word of it.

## The knowledge base is the source of truth

Most resume tools start from a blank page every time. This one keeps your whole career in one file
and treats a resume as one *rendering* of it.

Interview once. Regenerate resumes, tailored variants, LinkedIn copy and interview briefs forever.

The file is `career/kb.ttl`: plain text, readable in any editor, versionable in Git, readable by AI
tools without a translation layer. Keep it in a repo you control so it outlives any single tool,
including this one.

## One graph, laid out as one file

`career/kb.ttl` is a graph - every organisation, role, project, bullet, metric and question is a
node with an id, and every "this bullet is about that project" or "this number is that metric" is
an edge. It is also one file, written in the order the Markdown knowledge base always had:
Identity, Positioning, Work authorization and languages, Vocabulary, Organisations, Roles,
Projects, Metrics, Skills, Education, Certifications, Open source, Open questions. Every section
banner is always there, empty or not. A project's bullets sit under the project; a metric's
versions sit under the metric; prose is written as prose, in `"""` blocks, never reflowed. There
are no blank nodes and no `a j:Class` lines - an id's prefix (`prj_`, `ach_`, `met_`) says what it
is. You can open it and read your career from top to bottom, the way you could before.

```turtle
# == Projects

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

**It is validated every time it is loaded.** Every `jsk` command that reads the career parses the
whole workspace - `kb.ttl`, `log.ttl`, every `posting.ttl` and `application.ttl` - into an
in-memory graph and runs every rule over it before doing anything else: a bullet citing a metric
that does not exist, a role pointing at an organisation that does not exist, a confirmed entry with
no answer behind it, a date that does not parse. A finding names the file and the line. About ten
thousand triples - four hundred projects and a hundred applications - load and validate in well
under a tenth of a second, so there is no reason to check less than everything.

**Hand edits are allowed.** Open the file, fix a typo, save it. The next load validates it like
anything else, and says `kb.ttl changed outside jsk kb apply`: `jsk kb adopt` logs the edit and
lists every provenance it raised - an entry moved to confirmed, a claim changed while confirmed -
because that is the one kind of hand edit worth looking at twice.

### What it costs

This reverses a decision written down here before, and the costs are real:

- **A dependency.** `pyoxigraph`, a graph engine, is now the one required package. It ships
  wheels for every platform jsk supports and has no dependencies of its own; the pin is one minor
  version, and raising it reruns the Windows and Linux CI jobs. A machine without it still renders
  and gates a resume from a `resume.json`, and `jsk doctor` says what it lost - but it cannot read
  or change the career.
- **A syntax.** Turtle is not Markdown. `k:prj_x j:name "..." ;` is learnable in a sitting, but it
  is punctuation a person has to get right, and a missing `;` is a parse error. The same career is
  about 1.17 times the tokens it was in Markdown (measured on the P0 sample, every section, after
  cutting the layout down to fit). That ratio is mostly what a person pays to read it end to end:
  agents read by id - `jsk kb show`, `jsk match` - and no longer read the whole file.
- **A write path.** Agents do not edit the file with a text editor; they write a *changeset* and
  `jsk kb apply` merges it, validates the result and logs it. That is a command, a format, a log
  file (`career/log.ttl`) and a set of refusals to learn - exactly the kind of layer this project
  once removed.

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
  an application sent can never change, and `jsk kb query stale` names every application that sent
  a number since replaced.
- **A claims gate.** Ids are shared between the career and every `resume.json`, so "is this
  record's bullet one the career holds, under the project the career puts it in, at no higher a
  provenance than the career gives it, with numbers from the metric's current version" is a join,
  run inside `jsk gates`, `jsk ship` and `jsk freeze`; an entry the career lacks counts as at most
  inferred. What it does not check is wording: a bullet reworded in the record keeps its id, and
  one that shares too few words with the career's text gets a `text-changed` WARN - a prompt to
  look, not a proof the new words were confirmed. The simulation's seven planted defects were all
  caught.

None of those needs the career to be large. All of them need it to be structured data with ids.

### How each failure of the old write layer is answered

The `okf` layer failed in specific ways, and removing it was the right response to them. The
graph record keeps a write path, so each failure needs an answer:

| What went wrong with `okf` | How the graph record answers it |
|---|---|
| The skill named about thirty verbs, costing 5,128 tokens resident in every session | Four new top-level verbs: `kb`, `match`, `event`, `migrate`. Sub-verbs live in `--help` and in each refusal's `fix:` line, not in the skill's entry point |
| A missing verb meant hand-authoring the file; the CLI's coverage was the agent's ceiling | One generic `jsk kb apply`, whose coverage is the **ontology**: anything the format can say, a changeset can say. `j:note` on every class is a relief valve for anything it cannot. Hand edits are legal and validated anyway |
| Unsafe defaults: a `--status confirmed` flag; `--body -` reading stdin and hanging | There is no status flag. A changeset asserting `confirmed` is refused. Stdin (`-`) is refused. The only way to confirm is `jsk kb confirm <id> --answer "..."`, with the person's words logged |
| Cross-file atomicity was claimed and not real | `apply` writes two files, `kb.ttl` then `log.ttl`, with the same revision and a hash in both. It cannot make that atomic, and says so: a write torn between them is **detected** on the next load, and `jsk kb adopt` records it |
| Surgical writes were promised, and a person's file got redumped | A canonical writer, gofmt's contract: `apply` refuses a file not already in the canonical layout ("run `jsk kb fmt`"), and a reformat is logged on its own - so a format change and a content change never share a diff |
| This page said a person must be able to read and correct their record end to end | `kb.ttl` is laid out as one readable file in the old section order, as above. `jsk kb view` renders it as Markdown to stdout - never a committed second copy that could drift from it |

Two limits, stated rather than hidden. Hand-edit detection is **detection, not prevention**: an
agent that edits `kb.ttl` directly is noticed on the next load and its edit listed, not stopped.
And `jsk kb confirm --answer` is an instruction with an audit trail, not a proof that anybody
asked the person.

### If you have a `user-knowledgebase.md`

`jsk migrate user-knowledgebase.md` moves it across once. It is refused unless the round trip holds -
the graph, written and parsed back, must read as exactly the entries the Markdown held - and it
deletes nothing. It exists for one release: the one after deletes it, along with the Markdown
reader. The old text of this page, and of every argument it made, is in git history.

## Every document is rendered from JSON, never hand-built

The career is written out as a [URS](../plugins/jsk/skills/jsk/references/urs-spec.md) record,
and the LaTeX, the PDF and the plain text are all emitted from that one file.

Two hand-built documents have to agree about every date, bullet and number, and they stop agreeing
the moment one is edited; usually silently, usually in the copy that gets sent. One record with
several emitters cannot drift, because no emitter decides what the document says.

It is also what makes a resume answerable a year later. The record carries the provenance of every
claim and the view that selected it, and `jsk freeze` records in `application.ttl` which bullets
and which metric versions it carried, so "what did this application claim, and where did that come
from" has an answer.

The render plan resolves the record once — selection, ordering, provenance filtering, profile
gating, ASCII folding, date formatting — and the emitters translate that plan into markup without
deciding anything. That split is what guarantees the PDF and the plain text cannot say different
things.

## Four gates, not one

**A checker verifies that a document parses — not that it is correct.** That sentence is the whole
reason there are four gates.

The parse gate passed a resume whose bullets rendered as tofu boxes. It passed one whose headings
silently resolved to a theme font. It passed one written in the third person. All three correctly,
all three outside its scope. The first two are visual, and no text extraction can see them; the
third is why the prose gate exists at all.

| Gate | Question | How |
|---|---|---|
| Record | Is the source coherent, does every number trace to a metric, and does every claim's id trace to the career? | `jsk validate`, then the claims gate, before anything renders |
| Parse | Will an ATS read this without mangling it? | `jsk check --only parse`, on the PDF |
| Prose | Does it obey the writing rules? | `jsk check --only prose`, on the `.tex` |
| Render | Does it *look* right, and is it *true*? | Open the PDF and read every page |

`jsk ship` runs the first three in one process — the record gate and the claims gate first, and
nothing renders if either fails — and exits 0 only if all of them passed. It then says, in its own
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

## Numbers are checked twice

Every numeral in a bullet must appear in a structured metric on that bullet, or the record gate
fails the record before anything renders. It is the check that catches a rewritten bullet quietly
inflating a figure.

That check reads the record against itself, and the record and its metrics are written together,
for one application - a rewritten clause agrees with its rewritten metric. So the claims gate
reads it against the career as well: each numeral has to be in the *current* version of a metric
the bullet cites in `kb.ttl`. A number the career has since revised fails as superseded, and one
the career never held fails as untraced.

## Tailoring cannot invent, structurally

A tailored resume is a *view*: it references evidence by id, orders it, and redacts. The validator
rejects free text inside a view, so a posting the record has no evidence for produces nothing to
point at rather than a plausible new bullet.

A posting's requirements are written into `posting.ttl`, each with the advert's own words as a
quote that is checked, verbatim, against the advert beside it. `jsk match` joins them with the
career through the vocabulary and **shows the path behind every match** - which project holds the
concept, through which edge, how many hops, and whether a confirmed bullet shows it or only the
project's tags say so. A score nobody can recompute would be worse than no score, and that is the
whole reason the working is printed rather than the ranking asserted.

It reports what each project *failed* to match, and tells you where you fall short instead of
flattering you. Being flattered costs interviews.

## Two variants, because readability and parsing conflict

A presentation variant for humans, an ATS-maximal variant for portals, plus plain text for paste-in
boxes. One document cannot be optimal for both readers, and pretending otherwise means quietly losing
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
`jsk kb confirm` is the only way up, and it takes your answer in your words and keeps it in the log.

## The same record renders correctly in different markets

A region profile decides what each market may and must not see. A photograph and date of birth are
conventional on a Gulf resume and a liability on an Australian one; India expects academic grades on a
CGPA scale, a father's name and a declaration block; the Gulf screens visa status and transferability
before anything else. Australia, India and the UAE ship as profiles, and adding a market is a JSON
file rather than a schema change.

## Why a new schema instead of JSON Resume

JSON Resume is a JSON container around unstructured prose. A bullet is a bare string, so nothing can
verify a metric. Nothing carries an id, so tailoring means copy-and-mutate and the copies drift.
Nothing carries provenance, so "I measured this" and "a model wrote this" look identical. And a
promotion has to be modelled as two duplicate employers.

URS keeps a mapping to JSON Resume at conformance level 0, so adopting it costs nothing and is
reversible.

## Fitting a page budget without lying about it

`jsk fit` renders the document, measures which block spilled and how much room the page actually
had, then applies density levers in a fixed order — spacing, bullet spacing, margins, font size —
stopping at the 10pt and 0.5" floors instead of crossing them. If two pages are unreachable without a
breach it exits non-zero and says so, because the remedy then is to cut evidence, not to shrink type.

---

Next: [Quickstart](QUICKSTART.md) · [Concepts](CONCEPTS.md) · [Architecture](ARCHITECTURE.md)
