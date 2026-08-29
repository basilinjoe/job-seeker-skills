# Mode: tailor

Close the gaps against a posting, then write the resume once.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` concept. If the posting wants something they have not done,
say so — do not manufacture a bullet. Anything `inferred` needs confirmation before it appears.

Not only ethics: someone who bluffs past a screen gets found out in the first technical conversation,
having burned both the opportunity and their credibility.

## The shape, and why gaps come first

```
posting  ──►  UJD        the requirement side, extracted rather than typed
bundle   ──►  URS        the evidence side, one standing record
UJD × URS ──► UGS        the join: verdicts, evidence, shortfalls, questions
answers  ──►  bundle     the record improves, and the round runs again
                └──► on any termination reason: author once, confirm, ship
```

The resume is written **last**. There is no reason to author a document from a record you are about
to change, and doing it at the end drops N−1 authoring passes from an N-round loop.

This is also the fix for the defect the old procedure had. It reported gaps at the final step, after
every generation decision had already been taken — so the correction window it existed to create
never opened.

## 0. Get the posting

`$ARGUMENTS` may hold a URL, the text, or a path. **Fetch a URL yourself**; the analyst has no network
tools. Job boards refuse often — LinkedIn and most Workday tenants sit behind a wall — so when a fetch
fails, say what happened and ask them to paste it. That is an ordinary outcome, not an error.

Keep the URL either way. It goes in `posting.url`, and the archive needs it.

## 1. Build the two documents

Both are read-heavy and neither needs anybody in the room, so delegate them.

| Agent | Writes | Then |
|---|---|---|
| `jsk-posting-analyst` | `tailoring/targets/<slug>.posting.json` | `validate_ujd.py --level 2 --bundle <bundle>` |
| `jsk-record-builder` | `resume-generation/record.json` | `validate_urs.py --level 2` |

`record.json` is the standing transcription of the bundle. It may already exist from a previous
session — pass it, and the builder updates it in place rather than re-deriving it. **Ids must not
change between rounds**: a gap document resolves its evidence against this file, so a renamed id
orphans every verdict from the round before while both documents still validate.

**Surface what came back in your own words.** The analyst's PAUSE flags are not advisory: stop and ask
before anything is authored when the ranking is close between projects with materially different
ownership verbs, when a top-ranked entity carries `inferred` content, when eligibility fails, or when
the posting suggests the role may not be worth applying to at all. That last decision is theirs and it
comes before the work.

## 2. The round

```bash
python3 <skill-dir>/scripts/score_projects.py <bundle>/resume-generation/record.json \
        tailoring/targets/<slug>.posting.json --markdown
```

**From round 2 on, pass the previous `.gaps.json`.** The analyst patches that document instead of
deriving a new one — same ids, only what the answers changed — which is what stops a three-round loop
from costing three times what one round costs.

Then `jsk-gap-analyst` writes `tailoring/targets/<slug>.gaps.json`, and:

```bash
python3 <skill-dir>/scripts/validate_ugs.py tailoring/targets/<slug>.gaps.json \
        --recompute --report --carry <previous.gaps.json>
```

`--recompute` re-derives the group verdicts, the aggregate and both checksums, and fails the document
when they disagree with what the agent wrote. `--report` prints the readable checkpoint — the
requirement table, the shortfalls, the surplus and the question queue — which is what the retired Job
Target file used to be, except that it is rendered from the JSON and so cannot drift from it.

**Show them the report.** Not a summary of it.

## 3. Ask the whole queue at once

Present the ordered queue and take a bulk reply. Then go one at a time **only** for answers that came
back ambiguous, incomplete, or that contradict what the record already says.

This departs from `mode-gaps.md`'s standing rule — *"one question at a time… a list of fifteen gets
abandoned; one gets answered"* — and the departure is deliberate. That rule was written for an
open-ended bundle audit with no natural end. A tailoring round is bounded, ordered by priority, and
every question names the requirement it would close, so the person can see the whole cost of the round
before starting it. `/jsk:gaps` keeps one-at-a-time.

Order is `blocking → unmet-requirement → inferred-claim → missing-metric → unexplored`.

For an inferred claim, quote it exactly, say where it came from, and offer the exit:

> "On the care-plan project I wrote that policy grounding was there to stop hallucinated guidance
> reaching staff. You described the mechanism but not the reason — I supplied that. Is it right? If
> not, I'll cut the clause."

Confirm, correct, or delete. All three are fine. Leaving it as-is is not.

For a missing metric, prompt with where the number might live: monitoring dashboards, APM, cloud
billing, sprint retros, release notes, incident reviews, promotion documents, a colleague. **Ask
twice, then let go** — an honest "~50 tenants" beats silence, and a bullet permanently awaiting a
metric is a bullet nobody improved.

### Write each answer to both places

An answer updates the **bundle concept** and patches **`record.json`** in the same edit — flipping a
`status`, adding a metric, adding a capability. Both, every time. The reconcile pass in step 4 exists
because this is the one thing the arrangement can get wrong, and it reports divergence rather than
quietly fixing it.

## 4. Ending the round

The loop ends when **any** of these holds. `validate_ugs.py --report` computes the first three and
prints which one:

1. **`questions[]` is empty.** Nothing is worth asking.
2. **Every open question is `unexplored`** — territory never discussed. It improves the record in
   general, not this application, and belongs in `/jsk:gaps`.
3. **No new answerable question this round.** Every one is already carried as `deferred` or
   `unavailable`. Without this guard, a requirement nobody can close re-asks forever.
4. **Three rounds**, unless they asked for more.
5. **They skip.** Offer it every round. It is the ordinary exit, not a failure.

**Tell them which reason ended it.** "Nothing left to ask" and "you have hit the cap with four things
open" call for different next moves.

Then run `jsk-record-builder` once more to reconcile, and report any divergence it found.

## 5. Author, once

`jsk-resume-author` writes `tailoring/targets/<slug>.resume.json` — the narrative, the summary retuned
to this posting, and the view. It is the only agent that writes prose, and three things carry that:

- **Everything it authored is `inferred`**, and `provenance_floor: confirmed` on the view means
  `validate_urs.py` refuses to render it until a person confirms it. A failing render here is the
  guardrail working, not a problem to route around.
- **Every numeral must trace to a metric.** Tailoring is exactly when a rewritten clause inflates a
  number, and that check is what catches it.
- **It quotes every clause back**, with what it derived it from.

**Read those quotes to the person and get confirm-correct-or-cut on each**, then flip the confirmed
ones in the record. This step is yours and is not delegable.

**A view references content; it cannot contain it.** The validator rejects free text inside one. That
is the structural expression of the rule at the top of this file: a format where invention is
impossible beats a process where invention is merely discouraged. If the posting wants something the
record does not have, the view has nothing to point at — which is the honest outcome, and the thing
to say out loud.

Then re-run the recompute with the view in view, which is what populates `surface[]`:

```bash
python3 <skill-dir>/scripts/validate_ugs.py tailoring/targets/<slug>.gaps.json --recompute --report
```

A surface gap is *held in the record, absent from what is about to be sent* — a different failure from
not having the thing, with a much cheaper fix, and invisible to anyone reading only the rendered
document.

## 6. Ship

`/jsk:ship`, or `references/mode-ship.md` inline. It renders, runs all four gates through
`jsk-verifier`, freezes the archive and logs the submission. It never freezes a document that failed a
gate.

## 7. Tell them where they fall short

Every time, in chat, before they ask. By now this is a reading of the assessment rather than a
judgement you are forming:

> "Two gaps survived the rounds. They want direct people-management — you have technical leadership
> and mentoring evidence, but nothing on hiring or performance reviews. And they name Terraform
> throughout; your IaC evidence is all Bicep. The concepts transfer and you could say so in interview,
> but the resume can't claim Terraform depth you don't have."

A named gap can be prepared for, addressed in a cover letter, or used to decide the role is not worth
applying to. That decision is theirs and needs real information. If the fit is genuinely poor, say so.

## Cover letter, if asked

Under 250 words. Strongest capability match first. One concrete piece of evidence with its metric.
Address the obvious gap in one honest line rather than hoping nobody notices. No enthusiasm padding.

## Running it inline

Where agents are unavailable, the procedure is the same and the scripts are the same. What you lose is
the separation, not the method — so be stricter about the two places it matters: keep the
advertisement before you read anything out of it, and run `validate_ugs.py --recompute` rather than
trusting your own arithmetic.
