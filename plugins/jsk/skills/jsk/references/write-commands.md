# Writing to a bundle

Typed commands that change a bundle, so the files a change implies are derived rather than
remembered.

`references/bundle-spec.md` says what a concept must look like. This says how to write one without
hand-authoring it — and, just as importantly, where the commands stop and a person takes over.

**One command exists today: `okf project add`.** Every other concept type is still hand-written
against `bundle-spec.md`. That is a real limit, not an omission from this page.

## Why not just write the file

`mode-braindump.md` asks for five things in one sentence: the concept, `projects/index.md`, a link
from the role concept, numbers in `achievements/metrics.md`, a line in `log.md`. Nothing made those
atomic, and the two most mechanical were the two most often forgotten.

`okf project add` derives those two and stages them beside the concept. *An index that does not
list a concept is invisible to the person browsing their own bundle, and a change with no log row
is a change nobody can date.*

## `okf project add`

```bash
python3 <skill-dir>/scripts/okf.py project add --bundle <bundle> \
  --title "Care Platform Rebuild" \
  --role staff-engineer-acme \
  --strength 5 --recency 2026 --seniority architecture-ownership \
  --domain healthcare \
  --capability event-driven-architecture \
  --headline-metric "cut claim latency 4.2s to 380ms" \
  --description "Rebuilt the claims pipeline." \
  --status inferred
```

| Flag | Takes |
|---|---|
| `--bundle` | required; the bundle's root |
| `--title` | required; the project's title |
| `--slug` | the file stem. Derived from `--title` when absent — `"Care Platform Rebuild"` becomes `care-platform-rebuild.md` |
| `--description` | one line, and it becomes the directory index entry's text |
| `--role` | required; the `roles/` concept stem this was done under |
| `--strength` | required; 1–5, where 5 is flagship evidence |
| `--recency` | required; the year the work was last touched |
| `--seniority` | required; one of the closed vocabulary in `bundle-spec.md` |
| `--domain` | required; repeatable |
| `--capability` | a term already in the vocabulary; repeatable. **One of these two is required** |
| `--new-capability` | a term to add to the vocabulary in this same change; repeatable, and needs `--theme` |
| `--theme` | the existing vocabulary heading `--new-capability` files under |
| `--technology` | repeatable |
| `--headline-metric` | the one number this project is for |
| `--status` | `confirmed` \| `inferred` \| `needs-verification` — **defaults to `confirmed`** |
| `--body` | the concept's prose; `-` reads stdin, and `-` is the default — **see the hang below** |
| `--set KEY=VALUE` | an extension key; repeatable |
| `--dry-run` | decide everything, write nothing |
| `--json` | print the files changed and the ids minted |

### A capability is required, and the command is stricter than the schema here

`--capability` or `--new-capability` — at least one. The schema tolerates an empty list because
`validate_bundle.py` does, so this is the command's own rule: *a project with no capabilities is
invisible to every job it actually matches*, because capabilities are what `okf score` ranks on.

### `--body` defaults to stdin, so close it or pass it

`--body` defaults to `-`, which **reads stdin to EOF**. Omit it with stdin still open and the
command waits forever, having written nothing — no output, no error, just a hang. Either pipe the
prose in:

```bash
echo "What this project was." | okf project add --bundle … --title … --capability …
```

…or close stdin when the concept's prose comes later: append `< /dev/null` (`< NUL` on a Windows
shell). A concept written with no body is perfectly valid — the frontmatter is what compiles — so
writing the row now and the prose in the next edit is a normal thing to do.

### `--status` defaults to `confirmed`, and that is a trap

The default is right for the common case — a person just told you about the work — and wrong in
exactly the case this framework exists to catch. **If you wrote it rather than heard it, pass
`--status inferred`.** A concept written from your own reconstruction and stamped `confirmed` has
laundered an inference into a fact, and no gate downstream can tell: `provenance_floor` is enforced
against what the frontmatter says, not against who typed it.

## What one run writes

Four files, at most, and the fourth only sometimes:

| File | Why |
|---|---|
| `projects/<slug>.md` | the concept — the authored half |
| `projects/index.md` | a `- [Title](slug.md) - description` entry |
| `framework/capability-vocabulary.md` | only with `--new-capability`, under the `--theme` heading |
| `log.md` | a `- Added projects/<slug>.md - Title` row, under the current date's entry |

`--json` names all of them, so a caller never has to guess:

```json
{
  "changed": ["…/projects/care-platform-rebuild.md", "…/projects/index.md",
              "…/framework/capability-vocabulary.md", "…/log.md"],
  "ids": {"project": "care-platform-rebuild"},
  "dry_run": true
}
```

### The order is the guarantee, and it is narrower than a transaction

Every file is written and fsynced beside its target before any of them is published, so a full
disk or a missing directory lands before anything is visible. But `os.replace` is atomic for one
file and nothing makes it atomic across four.

So the concept publishes **first** and its derived companions after, because **the concept is the
half that cannot be regenerated.** An index entry is derivable from the tree; a concept is
somebody's work. A crash mid-publish therefore loses the derivable half.

**That gap is silent.** `validate_bundle.py` exits 0 on a concept missing from its index — it
checks that an index exists and that its links resolve, never that it lists every concept beside
it. The reverse state is the loud one: `x projects/index.md: BROKEN LINK -> care-platform.md`. The
order deliberately trades a loud unfixable failure for a quiet fixable one. If a run dies mid-write,
check the index by eye.

## Three rules need the bundle in hand

`schema.py` judges values and never touches the filesystem, so these three live in the command
layer instead. They are the complete list:

| Rule | Why it is load-bearing |
|---|---|
| a `--capability` must appear in `framework/capability-vocabulary.md` | only enforced when that file lists any values; the fix is `--new-capability foo --theme "…"` |
| a Project's `--role` must name a concept in `roles/` | **no gate reports a dangling role.** `okf_compile.py` refuses on it, and `okf score` compiles — so this surfaces as a crash mid-tailoring, not as a red line at ship time |
| a Role's `organisation` must name a concept in `organisations/` | same class, same reason |

The referential pair is the expensive one to miss, which is why the check is here rather than left
to `validate_bundle.py` — which checks neither.

Every refusal names its fix and exits `1`. Exit codes are the same as everywhere else: `0` passed,
`1` refused, `2` called wrong.

Writing needs **no `pyyaml`** — emitting a concept and appending to an index are both text
operations, and the referential checks are a stat and one text parse. Only *reading* a concept back
needs it. So this runs wherever the rest of the skill's bare-Python scripts run.

A duplicate slug is refused rather than overwritten. Adding a project is not a reason to overwrite
somebody's file.

The checks are local by construction — `--role X` is one stat, `--capability c` parses one file —
so a write costs about the interpreter floor rather than the ~1s a full compile costs. Run
`okf validate <bundle>` once at the end of the mode, as the mode files already say.

## What it does not do

Neither a bug nor a plan; just the boundary, so nobody waits for a command that is not there.

- **No other concept type.** Roles, organisations, achievements, education and skills are
  hand-written against `bundle-spec.md`.
- **No editing.** `add` writes a new concept. Changing one is an ordinary file edit.
- **`achievements/metrics.md` is still yours**, and so is the backlink from the role concept. Those
  are two of the five things `mode-braindump.md` asks for, and they need judgement about where a
  number belongs.
- **No reindex.** Nothing repairs an index that lost its entry to a mid-publish crash.

## The two halves of the schema

`scripts/authoring/schema.py` is the only machine-readable statement of which keys a type takes and
what each value must satisfy. `bundle-spec.md` is its prose counterpart. **They are meant to be read
together, and a rule in one but not the other is a defect in whichever is missing it.**
