# A write layer for the bundle

**Status:** design, 2026-08-31
**Scope:** `jsk` internals. No change to what a resume says, and no change to what a
person may do with their own files.

Every tool in `scripts/` reads the bundle. Nothing writes it. The bundle is written by
hand — by the person in their editor, which is the point of the format, and by an agent
with `Write` and `Edit`, which is where the defects come from.

This document specifies `okf`'s write half: typed commands that create, amend, retire and
file the concepts, and become **the only path an agent has** to change a bundle.

## Problem

A braindump write is a five-file transaction instructed in one sentence
(`mode-braindump.md:46`):

> Then: update `projects/index.md`, link from the relevant role concept, add numbers to
> `achievements/metrics.md`, append to `log.md`, run the validator.

Nothing makes those five atomic, nothing checks four of them, and the agent must first read
`bundle-spec.md` (~5,330 tokens) plus "two existing project concepts" to learn the house style
it is about to imitate. The failure modes are all of one kind — the mechanical half of a
concept, written from memory:

| Written wrong | Caught by | When |
|---|---|---|
| `startDate:` for `start:` | a hand-written unknown-key check in `validate_urs.py` | next validate |
| a capability synonym | `validate_bundle.py`, only if the vocabulary file is populated | next validate |
| `role:` naming a stem that does not exist | the compile | next compile |
| a bullet naming a metric row that is not there | `okf_compile.Problem` | next compile |
| the `projects/index.md` entry, omitted | `validate_bundle.py` — **as a warning** | possibly never |
| an application's `../` paths, after filing | a broken link | next validate |

The last two are the shape of the whole problem: **a half-finished write can go green.**

### One defect found while specifying this

Bullet ids are positional. `okf_compile.py:363`:

```python
"id": fields.get("id") or f"ach_{slug(where)}_{n}",
```

A view names achievements by exactly that id — `"achievements": ["ach_latency", "ach_scale"]`
(`view-format.md:31`), resolved at `urs/resolve.py:111`. **Inserting a bullet renumbers every
bullet below it, and a view referencing `ach_projects_foo_3` starts pointing at a different
sentence.** The id still resolves, so `validate_urs.py` passes. It resolves to the wrong claim.

This is the archived-view defect again — *a view compiled from two files is a view nobody
chose* — except it fires on an ordinary edit rather than on a migration. It exists today,
independent of this CLI.

## What is not on the table

**No enforcement against people.** `okf` binds agents. A hand-edited concept stays a valid
concept, and every command tolerates whatever a person wrote. The format is sold on *any editor
opens it, Git versions it*; a lockfile, a checksum or a CLI-owned index would sell that for a
guarantee we can get another way.

**No generic patch verb.** No `--find/--replace`, no unified diff on stdin. That is the `Edit`
tool wearing a CLI hat: the agent still needs the file's exact current text, it can still match
the wrong occurrence, and nothing checks the result's shape. Ship one and every refusal below
leaks through it.

**No second definition of the format.** `schema.py` is the single machine-readable statement of
what a concept takes. A write layer with its own opinion is the transcription problem this
codebase deleted 100 KB of JSON Schema to escape.

**No full-bundle validation per write.** A compile of the measured 100-application bundle costs
~1,024 ms. Ten writes must not cost ten seconds; see *Validation cost* below.

**No git integration.** Commands do not stage or commit. Git is the undo for `rm`, and that is
all this design asks of it.

**No read verb.** `okf compile --dump-record` already carries every bullet with its id. A
second read path alongside it is a second thing that can disagree.

## The design

### Where it lives

```
scripts/
  okf.py               forwards `okf project|role|bullet|… <verb>` in
  authoring/
    schema.py          what each type takes, and what each value must satisfy  <- the only definition
    concept.py         read, splice and emit one concept file - surgically
    bookkeeping.py     the derived companions: index entries, role back-links, log rows
    stage.py           the transaction: stage -> validate -> commit, or nothing
    commands.py        one function per noun-verb, built from schema.py
```

The seam is the render pipeline's argument one level up:

```
command args ── schema.py validates ──►  a changeset, in memory
                                             |
                         stage.py: write temp, validate, commit
                                             |
                                         the bundle
```

`commands.py` decides nothing. `concept.py` formats and does not judge. If you find yourself
validating inside a command it belongs in `schema.py`; if you find yourself formatting inside
`schema.py` it belongs in `concept.py`.

Where `schema.py` overlaps `validate_bundle.py` or `validate_urs.py`, the validators read from
it. A test asserts the three cannot disagree — the same structural move as splitting
`view-format.md` out of `urs-spec.md` rather than copying it.

### Surgical writes, never a redump

`pyyaml` reads the bundle today and nothing writes it back. Round-tripping a person's
hand-written frontmatter through `safe_load`/`dump` reflows their file, drops their comments
and requotes their strings. For a format whose promise is that any editor opens it, that is
hostile.

- **New concept:** generated from a canonical template. Entirely ours, so it can be exemplary.
- **Amendment:** parsed with `pyyaml` to *validate*, then written by splicing that key's lines
  in the raw text. Every untouched key keeps its quoting, order, comments and blank lines.
- **Refuse rather than reflow:** where a frontmatter block cannot be spliced unambiguously — a
  duplicated key, a multi-line value whose extent is unclear — the command fails and names the
  file and line for a person. A tool that mangles somebody's file once is a tool they never run
  again, and this design has bound them to nothing.

`pyyaml` becomes required **for writes only**. Reads are unchanged and `okf doctor` reports it.

### The claim is the atom

The body is not one blob, and it is not patchable by line. Every addressable unit in a bundle
carries a `status`. Change half a sentence of a `status: confirmed` bullet and the status now
asserts that a person signed off on text that no longer exists. **The CLI must know the claim
boundary in order to reset provenance across it, and a line-level patch by definition does
not.** The claim is the atom by necessity rather than by taste.

The format already provides the boundaries:

| Body kind | Where | Addressed by | Verbs |
|---|---|---|---|
| `blocks()` items | `# Bullets`, `# Skills`, `# Held` | item id | `bullet\|skill\|credential add\|set\|rm\|mv` |
| pipe-table rows | `achievements/metrics.md` | first column | `metric add\|set` |
| append-only rows | an application's `# Timeline` | — | `application event` — no `set`; a correction is a new row |
| vocabulary items | `framework/capability-vocabulary.md` | the backticked term | `capability add --theme` |
| free prose | `# The problem`, `# What I decided` | the heading | `<type> set --section "…" --body -` |

`blocks()` (`okf_compile.py:326`) is already one parser for all three authored blocks — *the one
shape in the bundle a script cannot derive, so it is written down plainly and parsed the same
way wherever it appears*. The write layer gets one emitter facing it, and the round trip is
testable as a property.

**The section is the floor and there is nothing below it.** Fixing a typo mid-paragraph means
restating the section, which the agent had to read anyway to know what to fix. A section too
large to restate is a section doing too much.

`set` on any claim re-stamps it `inferred` unless `--status confirmed` is passed explicitly.
Confirmation is then something the agent had to ask for, rather than something it inherits by
not touching a line.

### The bullet id fix, folded in

Any bullet mutation **first materialises explicit ids for every bullet in that concept** —
writing down the id the compile was already generating. That changes no meaning and leaves every
existing view reference pointing at the same sentence. Then it mutates. New bullets mint a
content-derived id (`ach_latency`), checked unique, never a positional one. After one write the
concept is immune.

No bundle revision: nothing about the on-disk shape changes, only whether an implicit value is
written down. There is deliberately **no migration**, so a bundle nobody writes to stays exposed.
The compensating control is a validator change rather than a migration: `validate_urs.py`
**warns when a view references an unmaterialised achievement id**, which makes the hole visible
on the next `okf validate` instead of on the next surprise.

### Atomicity, and its stated limit

Each command builds a changeset over N files, writes them all to temp, validates, and only then
commits. `os.replace` is atomic per file and **not across files**, so a crash mid-commit can
leave a partial write. That is a real limit, and stating it beats implying a transaction we do
not have.

The mitigation is ordering. **The concept commits first, its derived companions after**, so a
partial failure lands on the repairable side: a concept with no index entry, which
`validate_bundle.py` already reports as a warning and `okf reindex` rebuilds from the tree. The
reverse order leaves an index entry pointing at a file that never landed — a broken link, an
error, and nothing can regenerate the concept it wanted.

### Validation cost

`stage.py` validates **the changeset, not the bundle**. Schema checks come from `schema.py`;
referential checks are local by construction — `--role X` is a `stat` on one file, `--metric M`
parses one table, `--achievement ach_x` parses one concept's `# Bullets`. Nothing walks the tree.

A write therefore costs about the 109 ms interpreter floor. A full `okf validate` still runs
once at the end of a mode, exactly as the mode files already instruct. This continues Lever 1 of
the tailoring-cost design rather than undoing it.

## The catalogue

| Tranche | Commands |
|---|---|
| **1 — career concepts** | `project`, `role`, `org`, `education` — `add\|set\|retire\|rm`<br>`bullet`, `skill`, `credential` — `add\|set\|rm\|mv`<br>`metric add\|set` · `capability add --theme` · `question add\|resolve` · `log` · `reindex` |
| **2 — tailoring** | `posting add` · `posting requirement add` · `gaps write` · `view create\|set` · `view include` |
| **3 — archive** | `application file` · `application event` |

Cross-cutting on every write: `--bundle DIR`, `--dry-run`, `--json`, and `--set key=value` for
extension keys.

**`--json` reports every id the command wrote or minted**, alongside the files it touched. An
agent that added a bullet therefore knows its id without reopening the concept, which is why no
`ls` verb is needed: the only caller who needs an id it did not just mint reads the record.

```
okf project add \
  --title "Aged-care event platform" \
  --role lead-software-engineer-experion \
  --capability ai-platform-architecture --capability data-sovereignty \
  --technology azure-ai-foundry \
  --seniority architecture-ownership --strength 5 --recency 2026 \
  --status confirmed --body -
```

The body arrives on stdin. Frontmatter is mechanical and belongs in flags; prose is prose.

### Two verbs for removal, because they are different intents

`retire` sets `retired: <date>` and a reason. The concept stays on disk and in git, its links
keep resolving, and the compile stops emitting it. It is what `superseded_by:` already does for
a posting, generalised.

`rm` deletes, and **refuses while anything still references the concept** — a role link, a view
entry, an archived application — naming what. Git is the undo. It exists because people do
create genuine mistakes: a typo file, a duplicate from a bad braindump, test data.

Neither pretends to be the other, and neither is `log.md`'s business: a retirement is a fact
worth recording, so both append.

### The refusals are the product

A command that merely writes well-shaped YAML is worth little. What earns its place is what it
declines to do.

| Command | Refuses when | Without it |
|---|---|---|
| `project add --role X` | `roles/X.md` does not exist | a dangling relation the compile cannot place |
| `project add --capability foo` | `foo` is absent from the vocabulary | a synonym that silently breaks matching |
| `bullet add --metric M` | `M` is not a row in `metrics.md` | a `Problem` raised at the next compile |
| `view include --achievement ach_x` | `ach_x` does not resolve | caught after the view is written, if at all |
| `bullet rm` | a view references that bullet's id | a view resolving to nothing, or to its neighbour |
| `rm` (any) | anything still references it | a dangling reference |
| `application file` | the stem's year cannot be established | a guessed year, or a flat file |

`--capability foo` has a better resolution than a refusal: `--new-capability foo --theme "Data"`
adds it to `capability-vocabulary.md` **in the same changeset**. `bundle-spec.md` already says
"add new values there in the same edit" — this is the CLI enforcing a rule the spec could only
instruct.

### The command that pays for tranche 3

`okf application file <slug> --submitted 2026-08-26 --channel "Workday portal"` copies the
posting, gaps and view into `applications/<yyyy>/`, writes the `Application` frontmatter,
appends the timeline's first row, creates the year index, attributes the rendered documents —
and **rewrites every relative path that leaves the directory to gain exactly one `../`**.

`bundle-spec.md` enumerates that by hand for a human to follow. It is the fiddliest write in the
repo and the one with the least reason to be performed by a model.

## Enforcement

The driver is that agents write malformed concepts, so the design is only worth as much as the
change to what agents may do.

**1. Tool grants.** `jsk-tailor-analyst` and `jsk-resume-author` carry `Read, Write, Edit, Glob,
Grep, Bash` today. Under this design everything they write is a command, so both drop to
`Read, Glob, Grep, Bash`. `jsk-bundle-auditor` keeps `Write` — it writes an audit, which is not
a concept. `jsk-verifier` is unchanged.

`ARCHITECTURE.md` already makes this argument for the verifier — *a script has no Write tool
more thoroughly than an agent does* — and the write layer extends it to the two agents that
matter most. **The anti-invention guarantee moves from an instruction into a tool grant.**

**2. A hard rule in `SKILL.md`.** Never `Write` or `Edit` a file inside a bundle. Every change
is an `okf` command.

**3. The mode files call commands.** `mode-braindump.md`, `mode-refresh.md`, `mode-gaps.md`,
`mode-tailor.md` and `mode-ship.md` replace their prose write instructions with invocations. The
"read two existing project concepts first so you match house style" step goes: house style
becomes structural, and `bundle-spec.md` stops being a mandated read on the write path.

**4. The missing-verb escape hatch, and what it must not be.** If the CLI cannot express
something, the agent **reports that and stops** — it does not fall back to `Edit`. A blocked
write is a bug report naming a missing verb, which is the signal this design needs to stay
honest. `--set key=value` covers extension keys so the hatch is rarely reached.

`ARCHITECTURE.md` says *nothing may depend on an agent existing*. Nothing here does: these are
scripts, and the modes carry the full inline procedure as they do now.

## Sequencing

Each tranche is a separate commit, and the order is by blast radius.

1. **The core** — `authoring/`, `schema.py`, atomic staging, `--dry-run`, `--json`. No commands
   yet. It lands with its own tests and changes no behaviour.
2. **Tranche 1** — career concepts, plus the bullet-id materialisation and the `validate_urs`
   warning. `mode-braindump.md` and `mode-refresh.md` move to commands.
3. **Tranche 2** — tailoring artefacts. `jsk-tailor-analyst` and `jsk-resume-author` lose
   `Write` and `Edit` in the same commit that gives them commands, never before.
4. **Tranche 3** — `application file` and `application event`. `mode-ship.md` moves last,
   because filing is the write with the most existing bundles behind it.

## Testing

The existing 542 tests stay green throughout. None of this may change what a resume says, so a
behavioural test that moves is a defect in the change.

| Claim | Test |
|---|---|
| One definition of the format | `schema.py`, `validate_bundle.py` and `validate_urs.py` do not each define an overlapping rule — the drift test, shaped like the `view-format.md` split |
| A write preserves a person's file | write a concept, hand-edit whitespace and comments into it, `set` one key, assert every other byte is unchanged |
| `blocks()` round-trips | parse → emit → parse is equal, over every authored block shape |
| **The id defect cannot recur** | a view referencing a positional id resolves to the same text after `bullet add` inserts above it |
| Each refusal fires | one test per row of the refusals table, asserting the exit code and the named cause |
| A partial commit lands repairable | inject a failure between commits; assert the concept exists and only the index is stale |
| `--dry-run` writes nothing | mtimes unchanged across the whole bundle |
| The read is actually gone | `tests/test_budget.py` gains the braindump path; `bundle-spec.md` is asserted absent from it |

## What success looks like

| | now | target |
|---|---|---|
| Files an agent hand-writes per braindump | 5 | 0 |
| Agents carrying `Write`/`Edit` over concepts | 2 | 0 |
| `bundle-spec.md` read to author a concept | ~5,330 tok | 0 |
| A half-finished write that validates green | possible | refused |
| Bullet ids renumbering under a live view | silent | impossible after one write |
| `application file` path rewriting | by hand, enumerated in prose | one command |
| Cost of a write | — | ~109 ms, the interpreter floor |

No change to any rendered resume, and no change to what a person may do with their own files.

## Stated limitations

1. **Cross-file atomicity is not real.** Ordering makes a partial failure repairable; it does not
   make it impossible.
2. **A bundle nobody writes to keeps positional bullet ids.** The `validate_urs` warning makes
   that visible; only a write fixes it.
3. **The CLI's coverage is the agent's ceiling.** A missing verb blocks a write rather than
   degrading to a hand-edit, by design. That is the correct failure, and it will be felt before
   tranche 3 lands.
