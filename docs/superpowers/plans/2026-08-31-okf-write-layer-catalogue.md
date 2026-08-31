# The rest of the write catalogue

**Status:** plan, 2026-08-31
**Spec:** `docs/superpowers/specs/2026-08-31-okf-write-cli-design.md`
**Predecessor:** `2026-08-31-okf-write-layer-core.md` — the core, and `okf project add`

The core landed and one command sits on it. This plan lands the other forty-two, in the
spec's tranche order, and the two mitigations the spec promised alongside them.

## What the core does not yet have

Measured against the spec's catalogue before starting: 1 verb of 43.

| Missing | Blocks |
|---|---|
| a parser and emitter for `blocks()` body content | `bullet`, `skill`, `credential`, `metric` — 14 verbs |
| mapping values in the emitter | `posting` (`requirements[]`), `view` (`target`, `include[]`, `budget`) |
| schema entries beyond Project · Role · Organisation | `education`, and every tranche 2–3 type |
| deletes and binary copies in the changeset | `rm`, `application file` |
| index-entry removal, index repair | `rm`, `reindex` |

## Sequence

Each step is red-green-refactor at the unit, and each tranche is one commit. The 790
tests stay green throughout: none of this may change what a resume says.

1. **`authoring/body.py`** — parse and emit `blocks()` items and `#` sections. Mirrors
   `okf_compile.blocks()` exactly, including its non-fence-awareness: the compiler is
   the definition, and a writer that disagreed with it would write a claim the compile
   reads differently. Untouched items keep their bytes; a changed item is restated.
2. **`concept.py`** — mapping and list-of-mapping values, in block style. Needed by
   postings and views, and by nothing before them.
3. **`schema.py`** — `Education`, `Certification Status`, `Skill Set`, `Metric Set`,
   `Job Posting`, `Gap Assessment`, `View`, `Application`; the item schemas for bullets,
   skills and held credentials; the kinds those need. `View`'s key set comes from
   `validate_urs.VIEW_KEYS` rather than a second list.
4. **`bookkeeping.py`** — entry removal, index repair, the retire and remove log rows.
5. **`stage.py`** — staged deletes, staged binary copies. Same order guarantee.
6. **`career.py`** — `project|role|org|education` × `add|set|retire|rm`, generic over
   `schema.TYPES`.
7. **`claims.py`** — `bullet|skill|credential` × `add|set|rm|mv`, `metric add|set`,
   `<type> set --section`. Carries the id materialisation: any item mutation first
   writes down the id the compile was already deriving.
8. **`upkeep.py`** — `capability add`, `question add|resolve`, `log`, `reindex`.
9. **`tailoring.py`** — `posting add`, `posting requirement add`, `gaps write`,
   `view create|set|include`.
10. **`archive.py`** — `application file`, `application event`. The `../` rewrite.
11. **`commands.py` and `okf.py`** — one parser per noun, dispatch, `okf <noun>` wired.
12. **`validate_urs.py`** — warn when a view references an unmaterialised achievement id.
13. **Docs and enforcement** — `write-commands.md`, `SKILL.md`, the mode files, and the
    two agents dropping `Write`/`Edit` in the same commit that gives them commands.

## Decisions taken here, that the spec left open

**No `--new-organisation`.** The spec asked and answered "probably no": an organisation
is a concept with its own required keys where a capability is one line in a vocabulary.
`role add --organisation` refuses, and `okf org add` is one command away.

**Items are addressed by id, never by position.** `--index N` would reintroduce exactly
the fragility the materialisation exists to remove. `mv --to N` is the one place a
position appears, because reordering is the operation.

**A section is replaced when present and refused when absent**, with `--new-section` as
the resolution — the shape `--capability` / `--new-capability` already set.

**`question resolve` strikes the row and logs it.** The log is the bundle's record of
what changed; a resolved question kept in the file with a marker is a second place for
the same fact to be wrong.

**`reindex` adds missing entries and drops broken ones.** Both are mechanical. It is the
repair for the partial-publish gap `stage.py` documents, and dropping an entry whose
target is gone is only ever undoing that gap — `validate_bundle.py` already reports it
as an error.

## What landed

All 43 verbs, in one pass rather than four commits — the tranche order held as a build
order but the enforcement went in with the commands rather than after them, because the
two agents that lose `Write` have no other way to work once the mode files call verbs.

| | before | after |
|---|---|---|
| verbs | 1 of 43 | 43 |
| concept types the schema can write | 3 | 11 |
| `authoring/` | 5 modules, 2,116 lines | 13 modules, 8,139 lines |
| agents carrying `Write`/`Edit` over concepts | 2 | 0 |
| positional bullet ids under a live view | silent | refused, and warned about where a bundle still has them |
| a bundle buildable start to finish by command | no | yes, and asserted |

`tests/test_okf_write_surface.py` is the file that makes the headline claim checkable
rather than asserted. It holds the design's catalogue as data and fails if the parser and
the design disagree in either direction, and it builds one bundle from scaffold to filed
application entirely through commands — then puts it through `validate_bundle.py`,
`okf_compile.py` and `validate_urs.py`. That run is the design's actual promise: *the only
path an agent has to change a bundle.*

### Found while building

**`concept.py` had to grow a mapping emitter, and that was not in the plan's step 2 by
accident.** A posting's `requirements` and a view's `target`, `include` and `budget` are
mappings, and `scalar()` refuses one by design. Block style rather than flow, because a
view with six includes is one 300-character line in flow style - valid YAML that nobody
will edit by hand, in a format sold on any editor opening it. `set_structured` replaces
the key's whole measured extent, which is what makes a multi-line value amendable at all.

**Two keys in the wild disagree with the specification, and both are tolerated.**
`jsk-resume-author.md`'s own example view writes `target` as a bare stem where
`view-format.md` defines a mapping, and carries `include[].treatment`, which nothing
reads. Refusing either would refuse every view a real run has produced. `budget` also
takes `ats_maximal_pages`, which `urs/resolve.py:536` really does read - that one is a key
the schema would have been wrong to omit.

**A fresh bundle has nowhere to put a skill or a credential.** `init_bundle.py` scaffolds
`skills/index.md` and `education/index.md` and no concept beside them, and the catalogue
has no verb that creates a Skill Set or a Certification Status. So `skill add` and
`credential add` create the owning concept in the same changeset, which is the
`--new-capability` precedent: a claim with nowhere to live is not a claim.

**The read the design was sold on really is gone, and it was bigger than the design
thought.** `mode-braindump.md` opened its write section with *"Follow
references/bundle-spec.md. Read two existing project concepts first so you match house
style"*. Measured:

    before  SKILL 4,391 + braindump 956 + bundle-spec 6,453 = 11,800 tokens
    after   SKILL 4,825 + braindump 1,241                   =  6,066 tokens

A 49% cut on the braindump path. `bundle-spec.md` is 6,453 tokens rather than the
design's estimated 5,330, so the specification was more than half the cost of recording
one project. `TheWritePathReadsNoFormatSpecification` in `tests/test_budget.py` asserts
it is gone rather than merely discouraged - and its first version read
`mode-braindump.md`'s own disclaimer as the instruction it replaced, which is the one
failure mode such a check must not have.

**`SKILL.md` had to grow, and the budget test was right to say so.** The always-loaded
file must NAME the write nouns - `test_plugin_surface.py` asserts it, because an agent that
does not know a verb exists hand-authors the file instead. Both ceilings moved
deliberately, ~2%, with the reasoning recorded in `tests/test_budget.py`. `mode-ship.md`
paid most of it back by losing its by-hand filing procedure entirely, which is the trade
the design predicted: *bundle-spec.md stops being a mandated read on the write path.*

**`commands.main` takes the noun now.** It was `okf project`'s parser and is now the whole
write CLI, so two pre-existing tests that called `main(["add", ...])` needed the noun
prepended. Their assertions are untouched.

### Five defects in the shared layer, every one found by a caller

The verb modules were written against `schema.py`, `body.py`, `stage.py` and `common.py`
rather than alongside them, and that is what found these. All five are fixed, and each
now has a test, because *the claim that one file defines the format is worth nothing
unless it is checked against the things that actually read a bundle.*

| Found | Was |
|---|---|
| `schema.TYPES["View"]` took `tags` and `resource` from `COMMON` | Neither is in `validate_urs.VIEW_KEYS` nor stripped by `okf_compile.CONCEPT_KEYS`, so a view carrying one **fails the record gate on every run from the day it is written.** Now `VIEW_COMMON` |
| `include[].order` was kind `rank` | 1-5 only, so a view could not number its sixth engagement - and the refusal talked about flagship evidence, which is `strength`'s subject. Now its own kind |
| `body.parse` counted an entry with fields and no sentence | `blocks()` drops it and it consumes no position, so `common.item_ids` derived ids the compile never mints. Now `Block.claims()` names the compiler's view in one place |
| `stage.commit` could not stage a directory | `application file` had to `os.makedirs` before staging, putting part of its write outside the transaction - a `--dry-run` left a directory behind. Now `commit` makes each parent |
| `Application` modelled neither `company` nor `role` | `pipeline.py:55-56` reads both, and `--set company=Ashby` came back as a near-miss of `company_ref` - the escape hatch calling a real key a typo |

`tests/test_authoring_schema.py` is new and is the file that would have caught the first
two. It asserts the write schema against `validate_urs.VIEW_KEYS`, against the key tuples
`okf_compile` passes to `blocks()` **read out of the compiler's own source**, and against
the readers of every mapping-valued key. Two comments in `schema.py` had cited it by name
for hours before it existed, which is its own small lesson.

**The cost claim holds.** Measured on the machine this was built on: the interpreter floor
(`okf --help`) is 43 ms and `okf project add --dry-run` - which makes every decision the
real write makes and skips only the publish - is 41 ms, i.e. at the floor. The referential
checks stay local by construction. The two exceptions are stated rather than hidden: `rm`
walks the tree because it must know whether anything still points at what it is about to
delete, and career.py's author measured that honestly - 911 ms parsing every file's
frontmatter over 525 files, cut to 194 ms by a sound substring gate, of which 144 ms is
reading the files at all. `reindex` walks the tree because the tree is its subject.

**Two things in the wild were left alone deliberately.** `jsk-resume-author.md`'s example
view writes `target` as a bare stem where `view-format.md` defines a mapping, and carries
`include[].treatment`, which nothing reads. Both are tolerated rather than corrected,
because refusing either would refuse every view a real run has produced - the same
tolerance `okf_compile.py` extends to the `organization` spelling, and for the same
reason: this layer arrived after the bundles did.

## Stated limitations, carried forward

1. Cross-file atomicity is still not real. Ordering makes a partial failure repairable.
2. `body.py` mirrors the compiler's heading search, fences included. A concept with a
   fenced `# Bullets` example is read the same wrong way by both, which is the property
   that matters.
3. A bundle nobody writes to keeps positional ids. The `validate_urs` warning makes it
   visible; only a write fixes it.
