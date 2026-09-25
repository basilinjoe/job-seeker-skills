# Export from a match: `jsk kb export --urs --from-match <posting.ttl>`

**Status:** approved design, 2026-09-25. Extends P8 (record export) of
`docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md`.
**Builds on:** `jsk match` (`docs/superpowers/specs/2026-09-24-graph-match-design.md`) and
`jsk kb export --urs --select` (`src/jsk/graph/export.py`).

## What it delivers

Once `posting.ttl` exists, everything between it and the words of the resume is computed: which
projects appear, which bullets and in what order, the order of the skills, and the gaps the
selection could not close. Today `jsk-resume-author` makes those choices by hand from the match and
an allocation table in its prose; after this, the export makes them and the author only writes.

**Deterministic:** the same workspace, posting, `--cover` and `--today` give byte-identical JSON
and the same report lines.

**Not deterministic, and not attempted:** `posting.ttl` itself (the analyst reads the advert), what
an `ambiguous` or `candidate` requirement means (a person says, with `j:concept`), new or reworded
bullets, and the retuned narrative. Those stay with the analyst, the conversation and the author.

**Success:** every rule below is proven by a test that breaks when the rule does; the output of
`--from-match` passes `jsk validate`; the author agent's token ceiling falls.

## Rulings

1. **Tag-only is a gap.** A project that tags a concept (`j:uses`) with no bullet showing it does
   not carry the requirement for the export. It is reported, not refused.
2. **Enforced in the export only.** `jsk match` output does not change: the analyst still sees tags
   as leads worth asking about.
3. **One new module**, `src/jsk/graph/select.py`, a pure function over the store and `queries.py`;
   `export.urs()` takes its result. Not a `jsk match --select` (loses order), not a match that
   writes the record (mixes assessment with choice).
4. **The cover beats the allocation table.** A requirement the export claims to cover always has a
   selected bullet showing it, even past the band's cap.
5. **The export never writes `gaps.md`.** It prints `GAP` lines; the author copies them.

## 1. Which projects

**Evidenced carriers.** For each requirement `jsk match` resolves and matches, restrict its
`carriers` to projects where `Q.evidence(store, project, concept) == "confirmed"`: a live, confirmed
bullet `j:shows` the concept or something that counts as it, without an implies edge. Confirmed,
not merely present, because the view keeps `provenance_floor: confirmed` and an unconfirmed bullet
would be withheld at render. A carrier the filter drops becomes a gap:

- `tag-only`: `Q.evidence` returned `tag`.
- `unconfirmed`: `Q.evidence` returned `unconfirmed`; the gap names the bullets to confirm.

**Rank and cover again, over the filtered matches,** with `Q.rank` and `Q.cover` unchanged.
`--cover N` passes through, default 3 (`match.COVER`).

**The selection, in order:**

1. Every project in the evidenced cover.
2. Then the evidenced ranking, in order, taking only projects that carry at least one required or
   preferred requirement with evidence, until eight projects are selected in total. A strong
   project the posting asks nothing of is not selected: its score is strength, not fit.
3. When no cover fits the budget (`Q.cover` returns `None`), select by step 2 alone. The export does
   not fail.

**Uncovered.** A required requirement that no selected project carries with evidence is an
`uncovered` gap, whether nothing carries it (`missing`, `near`) or its carriers were not selected -
unless it already has a `tag-only`, `unconfirmed` or `unresolved` line, which says more.

A selected project's **position** is its place among the selected projects in evidenced score
order, 1-based; cover projects sit where their score puts them.

**Additions.** `--select` combines with `--from-match` and adds its ids after the scored projects,
in the order given, unscored: the author's way to keep a project for chronology. Ids already
selected are not duplicated.

**Unresolved requirements.** A required or preferred requirement whose state is `ambiguous` or
`candidate` is an `unresolved` gap; nothing is guessed for it.

Engagements and roles come from `urs()` as today: every role at an employer whose project is
selected.

## 2. Which bullets, and how many

**Candidates:** live bullets of the project with `j:provenance j:confirmed`. Nothing below the floor
is selected.

**Score** of a bullet:

- +3 for each required requirement, +1 for each preferred, whose resolved concept it `j:shows`
  through a `j:derived` path with `j:implied false` (the test `Q.evidence` uses);
- +1 when it `j:cites` a metric that has a current version (export drops a metric with none, so
  citing only such a metric earns nothing).

**Order:** score descending, then `j:rank` ascending, then id.

**Cover first.** Each required requirement in the evidenced cover is assigned to the
highest-positioned cover project carrying it. For each cover project, pick bullets greedily until
every requirement assigned to it is shown by a picked bullet: at each step the bullet showing the
most still-unshown assigned requirements, ties by the order above. This may exceed the band.

**Then the band** fills the rest, from the remaining candidates in order:

| Position | Bullets |
|---|---|
| 1-2 | up to 5 with score above 0; fewer than 3 scoring, fill to 3 with the lowest `j:rank` |
| 3-5 | up to 2 with score above 0; none scoring, fill to 1 |
| 6-8, or a cover project past 8 | 1 |
| `--select prj_` addition | 1, the lowest `j:rank` |
| `--select ach_` addition | exactly those named |

Caps count bullets already picked for the cover. A project with fewer candidates than its band gets
what it has.

**Render order** within a project is the pick set sorted by the order above; that is the view's
`achievements` order. Engagement order stays chronological, as `export.view()` writes it.

**Pages** are not the selection's concern: `budget.pages` stays 2 and fitting stays the renderer's.
No bullet is cut to fit.

## 3. Skill order

Skills are display entries (`name`, `category`, `alias`), not concepts, so they match by label. A
skill **matches** a requirement when `O.norm` of its name or any alias equals `O.norm` of a label of
the requirement's resolved concept, or of the requirement's `j:asked`.

The view's `skills` lists every live skill id, in three groups:

1. matching a required requirement;
2. matching a preferred requirement;
3. the rest.

Within a group: by the first requirement matched, in `Q.requirements` order (by requirement id),
then by `export.skills()` order (category, rank, name). The renderer's ten-row cap is unchanged; the
matched skills come first, so they are what it keeps.

## 4. Report

Gaps print in the report stream the export already uses for `WARN` and `NOTE` (stdout with `--out`,
stderr without), one line each, after any `WARN`:

```
GAP   tag-only    TypeScript (required): prj_portal tags c:typescript; no bullet shows it
GAP   unconfirmed Kafka (required): ach_clinical_events_cut_latency shows it, inferred - confirm it
GAP   uncovered   Terraform (required): nothing carries it
GAP   unresolved  BFF (required): ambiguous - c:bff or c:backend_for_frontend
```

Kinds: `tag-only`, `unconfirmed`, `uncovered`, `unresolved`. One line per requirement and kind; a
requirement carried by one project with evidence is not a `tag-only` gap because another project
only tags it. Lines sort by necessity (required first), then kind in the order above, then
requirement id. Gaps do not change the exit code.

## 5. Interface

```
jsk kb export --urs --from-match <applications/<dir>/posting.ttl> [--cover N] [--today YYYY-MM-DD]
              [--select <id>...] [--out FILE]
```

- The posting path is checked with `match.workspace_of`; a path outside `applications/<dir>/` is a
  usage error (exit 2), as in `jsk match`.
- Failures that block are the export's (the career) plus `match.blocks` for the posting's own
  directory: a posting that does not load refuses the export.
- `--cover` and `--today` are `--from-match` only; given without it, a usage error.
- `--today` defaults to today and feeds the ranking's recency, as in `jsk match`.
- Everything else (`--out` never overwrites, the gate-failure `WARN`, the loose-project `NOTE`) is
  unchanged.

**Code:**

- `src/jsk/graph/select.py`: `select(store, post, today, budget, extra=()) -> Selection` with
  `projects` (ordered iris), `bullets` ({project iri: ordered achievement iris}), `skills` (ordered
  iris) and `gaps` (ordered `Gap(kind, requirement, necessity, detail)`). Imports `queries`; no CLI.
- `src/jsk/graph/export.py`: `urs(store, select=None, today=None, selection=None)`. With a
  selection, the experience is the selection's projects and bullets, and `view()` writes its bullet
  order into `include` and its skill ids into `skills`. Without one, behaviour is unchanged.
- `src/jsk/graph/kbcli.py`: parse the flags, load and check the posting, call `select`, print the
  `GAP` lines.

## 6. Plugin

`plugins/jsk/agents/jsk-resume-author.md`: draft with `--from-match` instead of assembling
`--select`; the allocation table and the choosing prose go, since the export applies them. The
author keeps the words, the narrative, a reorder it states the reason for, `--select` for
chronology, and copying each `GAP` line into `gaps.md`'s "Where this falls short".
`tests/test_budget.py`: lower the author's ceiling, with the measured count in the comment.

## 7. Tests

`tests/test_select.py`, on a small fixture workspace:

- a tag-only concept is a `tag-only` gap, and its project does not count toward the cover;
- an inferred bullet is an `unconfirmed` gap naming it;
- a strong project carrying nothing is not selected;
- the cover beats the band: a cover project at position 7 carrying two required concepts shown by
  different bullets gets two;
- band fill at positions 1-2, including filler to 3;
- `--select` additions, `prj_` and `ach_`, and no duplicates;
- no cover within the budget still exports, with `uncovered` gaps;
- skill order: required, then preferred, then the rest;
- determinism: two runs, byte-identical JSON;
- the `--from-match` output passes `jsk validate`;
- CLI: a posting outside `applications/<dir>/` exits 2; `--cover` without `--from-match` exits 2.

## Out of scope

`jsk match` output and its tests, the renderer and gates, `src/jsk/urs/resolve.py`, the narrative,
and page fitting.
