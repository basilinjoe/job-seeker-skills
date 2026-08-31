# Writing to a bundle

Typed commands that change a bundle, so the files a change implies are derived rather than
remembered.

`references/bundle-spec.md` says what a concept must look like. This says how to write one
without hand-authoring it — and, just as importantly, where the commands stop and a person
takes over.

**Every change to a bundle is one of these commands.** Not `Write`, not `Edit`. If a change
cannot be expressed here, that is a missing verb: report it and stop, rather than hand-editing
around it. A blocked write is a bug report; a hand-edit is a bundle nobody can trust.

## Why not just write the file

A braindump write is a five-file transaction instructed in one sentence: the concept,
`projects/index.md`, a link from the role concept, numbers in `achievements/metrics.md`, a
line in `log.md`. Nothing made those atomic, nothing checked four of them, and the failure
modes were all of one kind — the mechanical half of a concept, written from memory. A
misspelt key, a capability synonym, a `role:` naming a stem that does not exist, an index
entry omitted. *A half-finished write can go green.*

So the mechanical half is derived. What is left for a model to do is the part only it can do:
decide what the sentence says.

## The shape of every command

```
okf <noun> <verb> --bundle <dir> [flags]
```

Four flags are on every one of them:

| Flag | Does |
|---|---|
| `--bundle DIR` | required; the bundle's root — the folder holding `projects/` and `roles/` |
| `--dry-run` | decides everything, writes nothing. Use it first when you are unsure |
| `--json` | prints the files changed, the files removed, and every id written or minted |
| `--set KEY=VALUE` | an extension key, repeatable — for a key the format does not model |

`--json` is how you learn an id you did not already know: a command that mints one reports it,
so there is no `list` verb and no need to reopen the file.

Exit codes are the same everywhere in this skill: `0` did it, `1` refused, `2` called wrong.
**Every refusal names its cause and ends in a `fix:` line.** Read it; it is the whole of what
the command has to say.

## The catalogue

| | |
|---|---|
| `project` `role` `org` `education` | `add` · `set` · `retire` · `rm` |
| `bullet` `skill` `credential` | `add` · `set` · `rm` · `mv` |
| `metric` | `add` · `set` |
| `capability` | `add` |
| `question` | `add` · `resolve` |
| `log` | *(the noun is the verb)* |
| `reindex` | *(the noun is the verb)* |
| `posting` | `add` · `requirement add` |
| `gaps` | `write` |
| `view` | `create` · `set` · `include` |
| `application` | `file` · `event` |

`okf <noun>` lists that noun's verbs and their flags. `okf <noun> <verb> --help` is the
authoritative flag list — this page explains the ones with a rule behind them.

## The career concepts

```bash
okf project add --bundle <dir> \
  --title "Care Platform Rebuild" \
  --description "Rebuilt the claims pipeline." \
  --role staff-engineer-acme \
  --strength 5 --recency 2026 --seniority architecture-ownership \
  --domain healthcare --capability event-driven-architecture \
  --headline-metric "claim latency 4.2s to 380ms" \
  --status confirmed --body -
```

The body arrives on stdin with `--body -`. Frontmatter is mechanical and belongs in flags;
prose is prose.

**`--slug` is optional and derived from the title.** `"Care Platform Rebuild"` becomes
`care-platform-rebuild.md`.

**Repeatable flags are singular:** `--domain`, `--capability`, `--technology`, `--industry`.
Repeats are dropped and the order you gave is kept, because the first term is the one you led
with and a person reads these too.

### `--status` defaults differ between `add` and `set`, and both defaults are the point

`add` defaults to `confirmed`: a person just told you about the work. **`set` re-stamps
`inferred`** unless you pass `--status confirmed` explicitly.

That is deliberate and it is the rule most worth understanding. Change half a sentence of a
`confirmed` claim and the status now asserts that a person signed off on text that no longer
exists. So confirmation is something you have to ask for, rather than something a claim
inherits by nobody touching that line.

**If you wrote it rather than heard it, pass `--status inferred`.** A concept written from
your own reconstruction and stamped `confirmed` has laundered an inference into a fact, and no
gate downstream can tell: `provenance_floor` is enforced against what the frontmatter says,
not against who typed it.

### `set` changes what it was asked to change and nothing else

Frontmatter is spliced key by key, so every untouched key keeps its quoting, its order, its
comments and the file's line endings. Where a key cannot be spliced unambiguously — it appears
twice, its value is written over several lines, the block uses a YAML anchor — the command
**refuses and names the file and line** rather than reflowing somebody's file. A tool that
mangles a file once is a tool nobody runs again.

Prose is addressed by heading:

```bash
okf project set --bundle <dir> --slug care-platform-rebuild \
  --section "What I decided" --body -
```

**The section is the floor and there is nothing below it.** Fixing a typo mid-paragraph means
restating the section, which you had to read anyway to know what to fix. A section too large to
restate is a section doing too much.

A section that is not there is refused, and the real headings are named — `--new-section`
writes one. A typo that silently created a second section would leave the real one holding the
prose a resume then renders.

`--unset <key>` deletes a key, and refuses to delete one the type requires.

### `retire` and `rm` are different intents

**`retire --reason "..."`** sets `retired:` and a reason. The concept stays on disk and in git,
its links keep resolving, and the compile stops emitting it. Use it for work that happened and
is no longer being claimed.

**`rm`** deletes — and **refuses while anything still references the concept**, naming what: a
`role:` or `organisation:` key, a markdown link, a view's `include[].ref`, an archived
application. It exists because people do create genuine mistakes: a typo file, a duplicate
from a bad braindump, test data. Git is the undo.

Both append to `log.md`. A retirement is a fact worth recording.

### Education keeps two of its facts in the body

`--institute` and `--period` are written as a labelled list in the body, not as frontmatter:

```markdown
- **Institute:** University of Somewhere
- **Period:** 2015 - 2018
```

That is where `okf_compile.py` reads them from. A key named in frontmatter that the compile
never reads is a value somebody wrote and no resume shows.

## The claims

A claim is the atom. Every addressable unit in a bundle carries a `status`, so a writer has to
know where a claim begins and ends in order to reset provenance across it — which is why there
is no line-level patch and never will be.

```bash
okf bullet add --bundle <dir> --project care-platform-rebuild \
  --text "Cut claim latency from 4.2s to 380ms." \
  --metric "Claim latency" --status confirmed
```

| Noun | Lives in | Block |
|---|---|---|
| `bullet` | `projects/<stem>.md` — `--project` | `# Bullets` |
| `skill` | `skills/<stem>.md` — `--concept`, default `competencies` | `# Skills` |
| `credential` | `education/<stem>.md` — `--concept` | `# Held` |

Bullets are projects' alone. `okf_compile.py` builds them from project concepts and nowhere
else, so a `# Bullets` block written into a Role compiles to nothing, silently — and
`bullet add --project` naming a role refuses.

Where the owning concept does not exist yet — a fresh bundle has no `skills/competencies.md` —
`skill add` and `credential add` create it in the same changeset, with its index entry. A claim
with nowhere to live is not a claim.

**Two `status` words meet on a credential, and they are different facts.** A `# Held` entry's own
`--status` is whether the certification is current (`active`, `expired`, `lapsed`, `in-progress`).
The *concept's* `status` is how well the bundle knows the claim, it is shared by every entry in that
file, and it is the one `provenance_floor` is enforced against — so it is what decides whether a
credential renders at all. `--concept-status` sets that one, and only when passed: a correction to
one entry's issuer must not silently demote the siblings nobody touched and make a resume quietly
shorter.

### Ids are written down, and that closes a real defect

`okf_compile.py` mints an id for a bullet that has none, from its **position**:
`ach_projects_care_platform_md_1`. Insert a bullet above it and every id below renumbers — so a
view naming `..._1` silently starts pointing at a different sentence. The id still resolves.
It resolves to the wrong claim.

**Any bullet, skill or credential mutation therefore materialises explicit ids for every item
in that block first** — writing down the id the compile was already deriving. That changes no
meaning and leaves every existing view reference pointing at the same sentence. Then it
mutates. After one write the concept is immune.

A new item mints a **content-derived** id — `ach_cut_claim_latency` — checked unique across the
bundle, never a positional one.

Two consequences worth knowing:

- **A bundle nobody writes to keeps its positional ids.** There is deliberately no migration.
  `okf validate` warns when a view references an unmaterialised id, so the hole is visible on
  the next validate rather than on the next surprise.
- **Items are addressed by id, never by position.** `--id ach_x` for `set` and `rm`. The one
  place a position appears is `mv --to N`, because reordering is the operation.

### `metric` is the number, once

```bash
okf metric add --bundle <dir> --name "Claim latency" \
  --value "4.2s to 380ms" --evidence care-platform-rebuild --source dashboard
```

A row in `achievements/metrics.md`. A bullet names the row rather than restating the number,
which is what stops a rewritten clause inflating it — "cut latency 62%" becoming "by over 60%"
becoming "by two thirds".

**`bullet add --metric M` refuses when `M` is not a row in that table.** Without it the mistake
surfaces as a crash in the middle of the next compile.

## Housekeeping

```bash
okf capability add --bundle <dir> --term data-sovereignty --theme "Architecture & design"
okf question add --bundle <dir> --text "What was the team size?" --section Blocking
okf question resolve --bundle <dir> --match "team size" --answer "Six engineers."
okf log --bundle <dir> --message "Reviewed the whole bundle with them."
okf reindex --bundle <dir>
```

**`capability add`** is the standalone form of what `project add --new-capability` does inline.
Capabilities are the primary matching axis and compare as exact strings, so this file is the
one place a synonym can silently break every future ranking. A term that is not lowercase and
hyphenated is refused, because that is the shape `validate_bundle.py` can read back.

**`question resolve`** strikes the row and records the resolution in `log.md`. It refuses a
match that hits nothing, and refuses one that hits more than one, listing what matched. The log
is the bundle's record of what changed; a resolved question kept in the file with a marker
would be a second place for the same fact to be wrong.

**`reindex`** is the repair for one specific gap, described under *the order guarantee* below:
it adds the index row a torn write never wrote, and drops a row whose target no longer exists.
It never reorders, retitles or rewrites a row that is fine — those are the author's.

## Tailoring

```bash
okf posting add --bundle <dir> --company Ashby --title "Staff Software Engineer" \
  --slug ashby-staff --seniority platform-design --domain saas \
  --body -                                       # the advertisement, verbatim, on stdin

okf posting requirement add --bundle <dir> --posting ashby-staff \
  --value event-driven-architecture --kind capability --necessity required \
  --label "own the event pipeline end to end"

okf gaps write --bundle <dir> --posting ashby-staff --fit partial --body -

okf view create --bundle <dir> --posting ashby-staff \
  --format-profile ats-maximal --pages 2 --ats-max-pages 3
okf view include --bundle <dir> --view ashby-staff --ref prj_care_platform_rebuild \
  --order 1 --achievement ach_cut_claim_latency
```

The three files share a stem and sit in `tailoring/targets/`. `validate_bundle.py` makes a
`.gaps.md` or `.view.md` with no `.posting.md` beside it a hard error, so `gaps write` and
`view create` refuse without one.

**`--slug` is worth passing on `posting add`**, because every command after it names that stem.
Derived, it is `<company>-<title>` slugged — `ashby-staff-software-engineer`, which is correct
and long. The stem also becomes the application's, after the date.

**`value` is vocabulary and `label` is the advertisement.** The score matches `value` as an
exact string, so a synonym scores as absent evidence. `label` keeps the posting's own phrasing,
because that is what belongs in prose later.

**`--necessity` is required and never defaulted.** A posting that says "expert in Terraform"
and one that says "Terraform a plus" are different postings. `score_projects.py` excludes
`implicit` by default, so a requirement invented as `required` makes a good fit look like a bad
one — and defaulting the flag would be the command inventing exactly that.

**A view selects; it must not contain content.** That is the normative rule that earns the
format its existence: tailoring becomes auditable by construction, and "the model embellished
my resume" becomes structurally impossible rather than something you hope did not happen. So
`view include --achievement ach_x` **refuses an id that does not resolve**, and every free-text
extension is refused at the top level — extensions belong under `x`.

Within an include entry the `achievements` order is meaningful and is preserved exactly as
passed: that is how a bullet earns the top of a role. The entry's own `order` is read and then
overridden, because engagements always render by date.

`--pages` and `--ats-max-pages` are two budgets, not one. The ATS-maximal variant is deliberately
longer — it repeats the employer on every role line and expands the skills block with aliases — so
it carries its own budget rather than cutting evidence to satisfy a constraint a parser does not
have.

## The archive

```bash
okf application file ashby-staff --bundle <dir> \
  --submitted 2026-08-26 --channel "Workday portal" \
  --document out/Test_Person_Ashby_Resume.pdf

okf application event 2026-08-26-ashby-staff --bundle <dir> \
  --date 2026-09-11 --event screen-scheduled --channel email \
  --note "Phone screen 2026-09-15" --due 2026-09-15
```

`application file` is the fiddliest write in the repo and the one with the least reason to be
performed by a model. One run copies the posting, gaps and view into
`tailoring/applications/<yyyy>/`, freezes each copy with `frozen: true` and its date, writes
the `Application` frontmatter, appends the timeline's first row, creates the year index,
attributes the documents actually sent — and **rewrites every relative path that leaves the
directory to gain exactly one `../`**, because the frozen copies sit one directory deeper than
the working ones.

Everything about it that could be guessed is refused instead: a year that cannot be
established, a missing working file, a company with no concept, a stem already filed under that
date.

**An application that was never sent says so.** `--submitted false` writes `submitted: false`
and no `submitted` timeline row — the one exemption `validate_bundle.py` honours. Never write a
`submitted` row to clear that error: it trades an accurate red for a false green, and every
stage derived from that timeline afterwards is wrong.

**`application event` appends and never edits.** A correction is a new row, for the same reason
`log.md` records mistakes rather than hiding them. There is no `set` verb here and there must
not be one. The event must be in `framework/pipeline-vocabulary.md` — a synonym is a row that
stops counting, and the gate rejects it.

## What one run writes

A command writes the concept and derives its companions. For `project add`, four files at most:

| File | Why |
|---|---|
| `projects/<slug>.md` | the concept — the authored half |
| `projects/index.md` | a `- [Title](slug.md) - description` entry |
| `framework/capability-vocabulary.md` | only with `--new-capability`, under `--theme` |
| `log.md` | a row under the current date's entry |

`--json` names all of them, so a caller never has to guess.

## The order guarantee, and how narrow it is

Every file is written and fsynced beside its target before any of them is published, so a full
disk or a missing directory lands before anything is visible. But `os.replace` is atomic for
one file and nothing makes it atomic across four.

So **the concept publishes first and its derived companions after, because the concept is the
half that cannot be regenerated.** An index entry is derivable from the tree; a concept is
somebody's work. A crash mid-publish therefore loses the derivable half. Removals are published
after every write, for the same reason: a `rm` whose index rewrite fails must leave the concept
on disk.

**That gap is silent.** `validate_bundle.py` exits 0 on a concept missing from its index — it
checks that an index exists and that its links resolve, never that it lists every concept
beside it. The reverse state is the loud one. The order deliberately trades a loud unfixable
failure for a quiet fixable one, and `okf reindex` is the fix.

## Three rules need the bundle in hand

`schema.py` judges values and never touches the filesystem, so these three live in the command
layer instead. They are the complete list:

| Rule | Why it is load-bearing |
|---|---|
| a `--capability` must appear in `framework/capability-vocabulary.md` | only enforced when that file lists any values; the fix is `--new-capability foo --theme "…"` |
| a Project's `--role` must name a concept in `roles/` | **no gate reports a dangling role.** `okf_compile.py` refuses on it, and `okf score` compiles — so this surfaces as a crash mid-tailoring, not as a red line at ship time |
| a Role's `--organisation` must name a concept in `organisations/` | same class, same reason |

There is no `--new-organisation`. An organisation is a concept with its own required keys where
a capability is one line in a vocabulary — and `okf org add` is one command away.

## Cost

A write costs about the interpreter floor. The referential checks are local by construction: a
`--role` is one `stat`, a `--capability` parses one file, an `--achievement` reads one
directory. Nothing walks the tree except the two verbs whose subject is the tree — `rm`, which
must know whether anything still points at what it is about to delete, and `reindex`.

Run `okf validate <bundle>` once at the end of a mode, as the mode files already say. A full
compile is ~1 second on a hundred-application bundle; ten writes must not cost ten of those.

Writing needs **no `pyyaml`**. Reading a concept back — which `set`, `retire`, `rm` and every
item verb do — does. `okf doctor` reports whether it is there.

## What it does not do

Neither a bug nor a plan; just the boundary, so nobody waits for a command that is not there.

- **No generic patch verb.** No `--find/--replace`, no diff on stdin. That is the `Edit` tool
  wearing a CLI hat: it still needs the file's exact current text, it can still match the wrong
  occurrence, and nothing checks the result's shape. Every refusal on this page would leak
  through it.
- **No concept type outside the eleven.** `bundle-spec.md` lists twenty-six. A Positioning, a
  Source Interview, a Talk is hand-written — and a refusal will say so rather than guessing.
- **No git.** Commands do not stage or commit. Git is the undo for `rm`, and that is all this
  layer asks of it.
- **No cross-file transaction.** See the order guarantee above; ordering makes a partial
  failure repairable, not impossible.
- **No enforcement against people.** These commands bind agents. A hand-edited concept stays a
  valid concept, and every command tolerates whatever a person wrote. The format is sold on
  *any editor opens it, git versions it*.

## The two halves of the schema

`scripts/authoring/schema.py` is the only machine-readable statement of which keys a type takes
and what each value must satisfy. `bundle-spec.md` is its prose counterpart. **They are meant
to be read together, and a rule in one but not the other is a defect in whichever is missing
it.**
