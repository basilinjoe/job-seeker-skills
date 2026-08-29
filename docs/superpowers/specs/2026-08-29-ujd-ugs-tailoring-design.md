# Job Seeker Skill: tailoring as a gap-closing loop

**Date:** 2026-08-29
**Status:** implemented — see *Outcome* at the end

## Problem

The repo ships three standards. One of them is wired to anything.

`urs-v1.schema.json` has `validate_urs.py`, `render_resume.py` and the whole `urs/` emitter package
behind it. `ujd-v1.schema.json` and `ugs-v1.schema.json` are a specification plus a JSON Schema and
nothing else — a grep for `ujd|ugs` outside `references/` and `schema/` returns zero hits. The UJD
spec says as much itself: *"Wiring the scorer to read UJD directly is a separate decision,
deliberately not taken here."*

So the live tailoring path still runs on a hand-maintained Markdown file. `mode-tailor.md` writes
`tailoring/targets/<company>-<role>.md`, a human types requirement arrays into its frontmatter, and
`score_projects.py` reads them back with pyyaml. Three consequences:

| Today | What is lost |
|---|---|
| Requirements are **typed by hand** into four frontmatter arrays | `necessity` (must-have / preferred / implicit), boolean requirement groups, experience windows and provenance spans all exist in UJD and none survive the trip |
| Gaps are **prose** under a `# Gaps` heading | No typed verdict, no evidence pointer, no shortfall dimension, nothing a later session can re-check |
| Gap resolution **never loops back** | `mode-gaps.md` audits the bundle with no posting in view; `mode-tailor.md` reports gaps at step 6, *after* the resume is generated. The correction never reaches the record and the resume is never rebuilt from it |

The last one is the real defect. The skill already knows the right answer — `mode-tailor.md` step 6
says *"tell them where they fall short, every time, before they ask"* — but it says it at the end,
when every generation decision has already been taken. The correction window it exists to create
never opens.

## The shape

Tailoring becomes the loop the three standards were designed for:

```
posting  ──►  UJD          the requirement side, extracted not typed
bundle   ──►  URS          the evidence side, one standing record
UJD × URS ──► UGS          the join: verdicts, evidence, shortfalls, questions
answers  ──►  bundle       the record improves
                └──► reassess ──► repeat, or author the resume once and ship
```

**Gaps close before the resume is written.** There is no reason to author a document from a record
you are about to change, and doing it last drops N−1 authoring passes from an N-round loop.

### Decisions

| Decision | Choice | Rejected |
|---|---|---|
| The Job Target file | **Retired.** `.posting.json` is the only posting document; `target-template.md` is deleted | Keeping both — two documents stating the same requirements drift, which is the failure this whole plugin is built against |
| Bundle-wide gaps mode | **Kept**, re-expressed in UGS so both entry points share one format | Folding it into tailoring — you lose the "clean up my record before I apply anywhere" pass |
| Question scope | Posting-fit and record-quality questions **ranked in one queue** | Posting-fit only — an `inferred` claim in a top-ranked project reaches this resume and must be asked about now |
| Who assesses | **An agent writes the whole UGS**; a validator recomputes the arithmetic | A matcher script — exact-string matching calls `azure-ai-foundry` against "Azure integration services" `unsatisfied`, and cannot distinguish `unevidenced` from `satisfied` at all |
| Record side | **One document**, `resume-generation/record.json` | The bundle Markdown — UGS pins `subjects.record` to a URS document and `Evidence.record_id` to a URS id |
| Answering | **The whole queue at once**, clarified individually | One at a time, per `mode-gaps.md` — see *Answering* below |

### One producer, one independent auditor

The schema anticipates LLM assessment: `Method.kind` has an `llm` value, and `model_version` exists
"because the same nominal method changes behaviour between versions". So a model may own the
verdicts.

What it must **not** own is the arithmetic — boolean requirement groups, `score.components[]` and its
`formula`, and checksums. UGS design rule 8 refuses an
aggregate that cannot say how it was computed; a model emitting a number beside a formula string that
does not correspond satisfies the schema and defeats the rule.

The resolution is not two producers. It is one producer and an independent auditor:
`validate_ugs.py --recompute` re-derives every derivable field and **fails the document** when it
disagrees.

| Field | Re-derived from |
|---|---|
| `group_assessments[].verdict`, `branches[]`, `closest_branch` | UJD `requirement_groups` + member verdicts, as `all`/`any`/`at-least`, nesting preserved |
| `score.components[]` | the assessments each names in `of` |
| `score.aggregate.value` | the stated `formula` over `components_included` — recomputed, not trusted |
| `subjects.*.checksum` | sha256 of both subject documents as read |
| `score.eligibility_excluded` | must be `true`, and no eligibility requirement may appear in any `of` |

## Architecture

```
  URL ──► main thread (WebFetch) ──► posting text + url
                                        │
                                        ▼
              jsk-posting-analyst ──►  <slug>.posting.json          (UJD L2)   ── once
                                        │ validate_ujd.py
              jsk-record-builder (bundle) ──► resume-generation/record.json   ── once
                   URS entities only — no view, no narrative, no new prose
                   │ validate_urs.py --level 2
  ┌────────────────┴──────────────────────────────────────────────────────┐
  │  THE ROUND — no agent runs twice over unchanged input                 │
  │                                                                       │
  │   score_projects.py record.json <slug>.posting.json    (ranking)      │
  │              │                                                        │
  │              ▼                                                        │
  │   jsk-gap-analyst (UJD × record.json + previous gaps.json)            │
  │        └──►  <slug>.gaps.json                       (UGS L2)          │
  │              verdicts · evidence + spans · typed shortfalls           │
  │              counterfactuals · groups · surplus · score · questions[] │
  │              │                                                        │
  │              ▼                                                        │
  │   validate_ugs.py --recompute --report                                │
  │              │                                                        │
  │              ▼                                                        │
  │   conversation: the whole queue at once, clarify individually         │
  │        └──► bundle concepts updated  AND  record.json patched         │
  └──────────────┬────────────────────────────────┬──────────────────────┘
        new answerable questions            none left, or user skips
        AND under the round cap                    │
                                                   ▼
              jsk-record-builder, reconcile pass ──► record.json
                   │  reports any drift between the bundle and the patches
                   ▼
              jsk-resume-author (record.json + UJD + gaps + ranking + bundle rules)
                   └──►  <slug>.resume.json    narrative · retuned summary · view
                         everything authored marked provenance: inferred
                         │ validate_urs.py --level 2
                         ▼
              conversation confirms each authored clause ──► status: confirmed
                         │
                         ▼
              jsk-resume-author writes surface[] for what its view cut
                   └──► validate_ugs.py --recompute enforces the obligation
                         │
                         ▼
              /jsk:ship ──► render · four gates · freeze the archive triple
```

### `record.json` — the standing record

`resume-generation/record.json` is new, and it fills a hole this design found: **the bundle has never
had a standing URS record**, only per-rebuild outputs. `mode-resume.md` authors one each time and
`bundle-spec.md` names it only as an application artefact.

Everything downstream now reads it — the scorer, the gap analyst, the author — so the ranking and the
verdicts cannot disagree about what the record contains. Under the old split they could, and nothing
would have said so. It is **derived and never hand-edited**: an edit there would be a claim with no
concept behind it.

This is also what makes `score_projects.py` standard-library-only. URS `projects[]` already carries
`strength`, `seniority`, `domains`, `capabilities` and `technologies` (`urs-v1.schema.json:491-499`),
so the Markdown frontmatter reader and the pyyaml dependency both go.

### Transcription runs twice, not per round

A gap answer is written into the bundle concept *and* patched into `record.json` in the same edit —
flipping a `status`, adding a metric, adding a capability are all small targeted changes.
`jsk-record-builder` therefore runs once at the start and once to reconcile before authoring. Two
passes regardless of round count.

**Id stability is its hard constraint.** `validate_ugs.py` cross-resolves every `evidence[].record_id`
against this file, so an id that changes between rounds silently orphans the previous round's
verdicts. The builder derives ids from concept filenames and updates the previous `record.json` in
place rather than re-deriving it. This is the cost of doing transcription with a model rather than a
fixed mapping, and it is why the id-stability check is a named verification step.

### `surface[]` is an obligation, not a derivation

*Corrected during implementation. The design assumed this field could be computed; it cannot.*

A `SurfaceGap` carries a `term`, the `aliases_available` the record uses instead of the posting's
word, and a `remedy` — the record says "security governance" where the posting says "data residency".
Those are vocabulary judgements, and no set difference produces them.

What **is** derivable is the obligation. `validate_ugs.py --recompute` fails a gap document where a
`satisfied` or `partial` assessment's evidence lies entirely outside the rendered view and no
`surface[]` entry reports it. The entries themselves are written by `jsk-resume-author`, which is the
step that knows what it cut to fit the page budget — so the knowledge is already there and no extra
agent pass is needed.

Either way they are uncomputable before a view exists, since a keyword is always missing *from*
something. And they are worth finding: their `counterfactual.kind` is `surface-existing`, "the
cheapest fix there is".

## Termination

A loop that ends only when the user says so keeps asking after it has stopped being useful. The round
ends and authoring begins when **any** of these holds — the first three without asking:

1. **`questions[]` is empty.** Nothing is worth asking.
2. **Every remaining question is `unexplored`** — territory never discussed. It improves the record in
   general, not this application, and belongs in `/jsk:gaps`.
3. **No *new* answerable question appeared this round.** Every question is one already carried with
   `resolution: deferred` or `unavailable`. The anti-spin guard: without it, a requirement nobody can
   close re-asks forever.
4. **The round cap is reached** — three by default, `--rounds N` to change it.
5. **The user skips.** Available every round; the ordinary exit, not a failure.

Reasons 1–3 are properties of the UGS document, so `validate_ugs.py --report` computes them and the
mode file reads the verdict. The person is told *which* reason ended the loop — "nothing left to ask"
and "you hit the cap with four things open" call for different next moves.

## Answering

Present the **whole ordered queue at once**, accept a bulk reply, then go one at a time only for
answers that came back ambiguous, incomplete, or that contradict the record.

This departs from `mode-gaps.md`'s standing rule — *"one question at a time… a list of fifteen gets
abandoned; one gets answered"* — and the rewrite says so rather than quietly dropping it. That rule
was written for an open-ended bundle audit with no natural end. A tailoring round is bounded, ordered
by `priority`, and every question names the requirement it would close, so the person can see the
whole cost of the round before starting it. The bundle-wide `/jsk:gaps` path keeps one-at-a-time.

## The agents

Four, one per document, and the division is by what each is allowed to write.

| Agent | Runs | Writes | Never |
|---|---|---|---|
| `jsk-posting-analyst` | once | `<slug>.posting.json` (UJD L2) | fetches — the main thread has WebFetch |
| `jsk-record-builder` | twice | `record.json` (URS entities) | a view, a narrative, or any new prose |
| `jsk-gap-analyst` | per round | `<slug>.gaps.json` (UGS L2) | `surface[]` — no view exists during a round |
| `jsk-resume-author` | once | `<slug>.resume.json`, plus the `surface[]` entries for what it cut | reads bundle concepts for evidence |

`jsk-resume-author` writes prose, which the other three do not, and that is the one place this design
trusts a model with something a person has to defend in an interview. Three existing guardrails carry
the weight, so the risk lands on the record gate rather than on the agent's judgment:

1. **Everything it authors is marked `provenance.status: inferred`** unless it is a verbatim lift from
   a `confirmed` concept. With `provenance_floor: confirmed` on the view, `validate_urs.py` blocks it
   from rendering until a person confirms it. The standing rule — inferred content never reaches a
   resume unconfirmed — becomes structural rather than remembered.
2. **The numeral rule already exists.** `validate_urs.py` fails any document where a numeral in a
   bullet appears in no metric. Tailoring is exactly when a rewritten clause inflates a number, and
   this is the check that catches it.
3. **It returns every authored clause quoted**, with what it was derived from, so the main thread
   reads them back for confirm-correct-or-cut rather than paraphrasing.

`SKILL.md`'s agent rule — *"they read and report; they never interview and they never decide"* — stops
being true as written and is replaced with the honest version: agents never interview, and anything an
agent authored arrives marked `inferred` and is confirmed with the person before it can render.

## UGS 1.1

Two changes to `ugs-v1.schema.json`. Both are widenings; every 1.0 document stays valid. The `$id`
(`https://openresume.dev/ugs/v1/gaps.schema.json`) is unpublished, so the file is edited in place.

1. **`Subjects.required` becomes `["record"]`.** A bundle-wide audit has no posting.
   `ugs-v1.schema.json:139` currently requires both, which makes the `/jsk:gaps` document invalid
   before it is written. `meta.purpose: "self-assessment"` already exists for exactly this case.
2. **`Question.priority` gains `unmet-requirement`**, ordered second, after `blocking`. The existing
   enum is record-quality only (`blocking`, `inferred-claim`, `missing-metric`, `unexplored`) and has
   no value for "the posting wants X and the record has nothing". Named `unmet-requirement` rather
   than `unevidenced-requirement` so it does not collide with the `unevidenced` **verdict**, which
   means the opposite thing: the record claims it with nothing behind it.

## Bundle revision 4

- `tailoring/targets/` holds `<slug>.posting.json` and `<slug>.gaps.json`
- the application file set gains `.posting.json` and `.gaps.json`, loses `.target.md`
- `resume-generation/record.json` is new, and derived

`migrate_bundle.py` gains an r3→r4 plan converting each `targets/*.md` to a Level 0 UJD: frontmatter
arrays become `requirements[]`, the pasted posting becomes `source.raw_text`. **`necessity` is not
recoverable** from the old shape — everything becomes `must-have` and is flagged, exactly as the UJD
spec's own schema.org mapping table says. `validate_bundle.py` warns on an older revision and never
fails it.

## `/jsk:ship`

The handover factored out of `mode-tailor.md` so it is callable, since `mode-resume.md` needs the same
three actions and currently repeats them.

`/jsk:ship <record.json> [--view ID] [--template NAME] [--ats-max] [--pages N]`:

1. `validate_urs.py --level 2` — never render from a record that fails
2. `render_resume.py --out . --view ID --pdf`, plus `--ats-max`/`--template` when passed. **Template
   defaults to the ink-only default**; `--template` is the only way to get another
3. `fit_pages.py --target-pages N` when the render overruns its budget
4. **`jsk-verifier`** for the four gates — it exists, reports every verdict verbatim and deliberately
   has no Write tool. Reused, not reimplemented
5. freeze the archive triple into `tailoring/applications/`, write the `Application` concept
6. append the dated `log.md` entry

A gate failure stops at step 4 and reports. It never freezes a failing document and never edits a
render to make a gate pass. A **command** rather than an agent because steps 5 and 6 write into the
person's record and step 4's output must reach them verbatim — both things the repo keeps out of
agents.

## Out of scope

- **The `<company>-<role>` stem collides** the second time a company posts the same role.
  `mode-tailor.md` already names this defect; changing the stem ripples through `pipeline.py` and the
  `Application` concept, and it is orthogonal to the schema work.
- **UJD ingestion from ATS feeds** — Greenhouse, Lever, Workday, Ashby, Indeed XML, the LinkedIn feed.
  The UJD spec records all of these as unresearched and writes no mapping; nothing here changes that.
- Any change to `render_resume.py`, the `urs/` emitters, the templates, or the four gates themselves.

## Work

| Stage | Contents |
|---|---|
| 1 | UGS 1.1 · `validate_ujd.py` · `validate_ugs.py` (`--recompute`, `--report`, `--carry`) · tests |
| 2 | `score_projects.py` rewired to `record.json` + `.posting.json`, pyyaml dropped · `okf.py` dispatch |
| 3 | Bundle revision 4 · `migrate_bundle.py` r3→r4 · `init_bundle.py` |
| 4 | `jsk-posting-analyst` rewritten · `jsk-record-builder`, `jsk-gap-analyst`, `jsk-resume-author` new · `jsk-bundle-auditor` updated |
| 5 | `mode-tailor.md` rewritten · `mode-gaps.md` updated · `mode-ship.md` + `commands/ship.md` new · `target-template.md` deleted · `SKILL.md` |
| 6 | `ARCHITECTURE.md` · `SCRIPTS.md` · `CONCEPTS.md` · `QUICKSTART.md` |

## Verification

The checks that would catch a wrong implementation. All five are `validate_ugs.py` failures,
deliberately — they are the things an LLM-written document can get wrong while still validating
against the schema.

- **Tamper.** Hand-edit `score.aggregate.value` and re-run `--recompute`. Must fail, or the aggregate
  is a number nothing verified and design rule 8 is decorative.
- **Group.** The degree-vs-postgraduate case from `ugs-spec.md` must resolve `satisfied` via the
  postgraduate arm — not two misses, not a bare-bachelor's pass.
- **Checksum.** Edit the `.posting.json` after assessment. The gap document must fail, so an edited
  posting cannot silently keep an old verdict.
- **Eligibility.** An eligibility requirement id in a `score.components[].of` array must fail.
- **Premature surface.** A `surface[]` entry in a mid-round document with no `subjects.record.view`
  must fail — nothing has been sent, so nothing can be missing from it.

One on the transcription:

- **Id stability.** Run `jsk-record-builder` twice over an unchanged bundle, carrying the first
  `record.json`. Every entity id must be identical, and the previous round's `.gaps.json` must still
  resolve.

Two on the authoring agent:

- **Unconfirmed prose.** Render a just-authored record before any confirmation pass.
  `validate_urs.py` must refuse it. If a PDF comes out, the `provenance_floor` is not doing its job
  and every later guarantee rests on nothing.
- **Numeral drift.** A number in a retuned bullet that appears in no metric must fail the record.

End to end: a posting URL in, two gap rounds answered in bulk, a skip on the third, one authoring pass
and `/jsk:ship`. No `.resume.json` may exist before the skip — if one does, the reorder did not take.
`jsk-record-builder` must have run exactly twice. And a posting the bundle already answers well must
end after **one** round without asking anything.

## Outcome

Implemented 2026-08-29, as designed, with five changes made during the build.

- **`surface[]` cannot be derived, only obligated.** The design said `--recompute` would compute it as
  a set difference. A `SurfaceGap` carries a `term`, `aliases_available` and a `remedy` — the record
  says "security governance" where the posting says "data residency" — and no set difference produces
  those. What shipped enforces the *obligation*: a `satisfied` assessment whose evidence lies entirely
  outside the rendered view and that nothing reports **fails** the document. `jsk-resume-author` writes
  the entries, because it is the step that knows what it cut. The design's conclusion — no second
  gap-analyst pass — survives for a different reason than the one given. The same correction removed
  `surplus[]` from the recompute table.

- **`score.components[]` is checked but not recomputed.** The spec blesses three different
  computations for a component's `value`: summed evidence credit for capability and technology, a
  group verdict for the qualification axis (its own text says summing the members "would score it 0.66
  and be wrong"), and seniority, which is computed from no assessments at all. One mechanical rule
  would reject correct documents. What is enforced instead is that `of` resolves, `normalized` is in
  range, and the aggregate built from them recomputes exactly — which is the number that could
  actually bias a decision.

- **Four defects in the shipped examples**, each the class of error its check exists for.
  `example.posting.json` claimed conformance 2 with no `source.raw_text` and four spanless
  extractions. `example.gaps.json` scored `cmp_capability` at 1.5 where its own `explanation` names
  credits summing to 1.2 — corrected, moving the aggregate 0.79 → 0.77; its `questions[]` ran
  `missing-metric` before `inferred-claim`; and it carried no checksums and no `Evidence.span`, so it
  reached level 1 while claiming 2. All four now validate at level 2.

- **A migration ordering bug**, found by a test rather than by reading. In a single r1 → r4 run,
  r3 → r4 listed `tailoring/applications/` before r1 → r2 had written the frozen `.target.md` it was
  about to create, because every change is planned before any is applied. Planned files are now
  threaded forward, so the oldest bundles are no longer the only ones whose archived posting stays
  Markdown.

- **One agent rule was stated too broadly.** A test asserted that `jsk-bundle-auditor` holds neither
  Write nor Edit. Emitting a UGS document needs Write. The rule worth keeping is the distinction
  between the two: a gap document is an agent's own output, a concept is the person's record, and a
  provenance status that flips without them saying so is the defect this framework exists to prevent.
  The test now asserts the verifier holds neither, and that an agent reporting on the record holds
  Write and never Edit.

- **The checksum could not hash the bytes on disk.** A Windows clone with
  `core.autocrlf=true` rewrites every LF to CRLF on checkout, which changed the hash of both shipped
  subject documents and failed the example gap analysis against itself. A line-ending conversion is
  not an edit to the posting in any sense a person would recognise, and the checksum exists to answer
  "was this document changed" — so it is taken over normalised line endings, with a `.gitattributes`
  pinning the repo's own JSON to LF as well. Two regression tests: a CRLF rewrite passes, a one-word
  content edit still fails.

462 tests pass, up from 350 on main. The shipped examples validate at conformance level 2 and preflight's
end-to-end check is green.

**Not done, and deliberately.** No fixture bundle exercises the full loop end to end — the four
agents are prose, so the loop's behaviour is asserted through the validators rather than by running
it. The manual walkthrough in *Verification* above is what closes that, and it needs a real bundle.
