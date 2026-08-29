# Mode: tailor

Close the gaps against a posting, then write the resume once.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` concept. If the posting wants something they have not done,
say so — do not manufacture a bullet. Anything `inferred` needs confirmation before it appears.

Not only ethics: someone who bluffs past a screen gets found out in the first technical conversation,
having burned both the opportunity and their credibility.

## The shape

```
posting.md   ──►  requirements[] in its own frontmatter
bundle       ──►  the record, compiled in under a second
      └────────►  gaps.md     verdicts, shortfalls, the question queue
answers      ──►  the concepts, and the record recompiles
                        └──► author once, confirm, ship
```

**Two agent passes, and the person in between.** One reads the posting and the record and writes the
assessment; one authors the resume after the questions are answered. Everything else — the record, the
ranking, the checks — is a script, because none of it needs judgement.

The resume is written **last**. There is no reason to author a document from a record you are about to
change, and doing it at the end drops every wasted authoring pass.

## 0. Get the posting

`$ARGUMENTS` may hold a URL, the text, or a path. **Fetch a URL yourself**; the analyst has no network
tools. Job boards refuse often — LinkedIn and most Workday tenants sit behind a wall — so when a fetch
fails, say what happened and ask them to paste it. That is an ordinary outcome, not an error.

Write it to `tailoring/targets/<slug>.posting.md` with the advertisement verbatim in the body and the
URL in the frontmatter. Keep the URL either way; the archive needs it.

## 1. Assess

`jsk-tailor-analyst` writes the requirements into the posting's frontmatter and the assessment into
`tailoring/targets/<slug>.gaps.md`, and returns the ranking.

**Show them the assessment.** Not a summary of it. It is written to be read aloud, which is the whole
reason it is Markdown and not a document with a schema.

**Surface what came back in your own words**, and stop before anything is authored when: the ranking
is close between projects with materially different ownership verbs, a top-ranked project carries
unconfirmed content, eligibility fails, or the posting suggests the role may not be worth applying to
at all. That last decision is theirs and it comes before the work.

## 2. Ask the whole queue at once

Present the ordered queue and take a bulk reply. Then go one at a time **only** for answers that came
back ambiguous, incomplete, or that contradict what the record already says.

This departs from `mode-gaps.md`'s standing rule — *"one question at a time… a list of fifteen gets
abandoned; one gets answered"* — and the departure is deliberate. That rule was written for an
open-ended bundle audit with no natural end. A tailoring round is bounded, ordered by priority, and
every question names the requirement it would close, so the person can see the whole cost before
starting it. `/jsk:gaps` keeps one-at-a-time.

**Offer the skip.** It is the ordinary exit, not a failure.

For a claim the record only infers, quote it exactly, say where it came from, and offer confirm,
correct, or cut. For a missing metric, prompt with where the number might live — dashboards, billing,
retros, release notes, incident reviews, promotion documents, a colleague. **Ask twice, then let go**:
an honest "~50 tenants" beats silence, and a bullet permanently awaiting a number is a bullet nobody
improved.

### Answers go into the concepts

An answer edits **the concept it belongs to** — the project file, `achievements/metrics.md`, the role.
One place, because there is only one source now: the record recompiles from it. That is the whole
reason the old procedure's "write it to both places, then reconcile" step is gone, along with the class
of bug it existed to catch.

Then recompile, so everything after this reads the answers:

```bash
python3 <skill-dir>/scripts/okf_compile.py <bundle> --quiet
```

## 3. A second round only if a verdict moved

Run the analyst again **only when an answer changed what the record holds** — a metric arrived, an
unevidenced claim got its evidence, a requirement that was indeterminate can now be judged.

**Continue the same agent with `SendMessage`; do not spawn a second one.** It still holds the posting,
the record and the vocabulary — about 60 KB it would otherwise read again to learn what it already
knows. Send it what changed and which concepts moved, and let it revise `gaps.md` rather than
re-derive it. A fresh agent is not merely slower: it re-reads a record the answers have just changed
and has no memory of which verdicts it had already settled, so it re-opens them.

Only start a cold analyst if the first one is gone — the run was interrupted, or the session ended.
Then pass it the previous `gaps.md` so it revises rather than starting over.

Otherwise stop. A round that re-asks what was already answered is how a loop stops ending, and three
rounds of a document nobody's answers changed is where the old procedure spent most of its time.

**Say why it ended.** "Nothing left worth asking" and "you skipped with four things open" call for
different next moves.

## 4. Author, once

`jsk-resume-author` writes the view and the prose. Three things carry that:

- **Everything it authors is `inferred`**, and `provenance_floor: confirmed` on the view means
  `validate_urs.py` refuses to render it until a person confirms. A failing render here is the
  guardrail working, not a problem to route around.
- **Every numeral must trace to a metric** in `achievements/metrics.md`. Tailoring is exactly when a
  rewritten clause inflates a number, and that check is what catches it.
- **It quotes every clause back**, with what it derived it from.

**Read those quotes to the person and get confirm-correct-or-cut on each**, then flip the confirmed
ones. This step is yours and is not delegable.

**A view references content; it cannot contain it.** The validator rejects free text inside one and
fails on a key it does not recognise. That is the structural expression of the rule at the top of this
file: a format where invention is impossible beats a process where invention is merely discouraged. If
the posting wants something the record does not have, the view has nothing to point at — which is the
honest outcome, and the thing to say out loud.

## 5. Ship

`/jsk:ship`, or `references/mode-ship.md` inline. It renders, runs the four gates, freezes the archive
and logs the submission. It never freezes a document that failed a gate.

## 6. Tell them where they fall short

Every time, in chat, before they ask. By now this is a reading of the assessment rather than a
judgement you are forming:

> "Two gaps survived. They want direct people-management — you have technical leadership and mentoring
> evidence, but nothing on hiring or performance reviews. And they name Terraform throughout; your IaC
> evidence is all Bicep. The concepts transfer and you could say so in interview, but the resume can't
> claim Terraform depth you don't have."

A named gap can be prepared for, addressed in a cover letter, or used to decide the role is not worth
applying to. That decision is theirs and needs real information. If the fit is genuinely poor, say so.

## Cover letter, if asked

Under 250 words. Strongest capability match first. One concrete piece of evidence with its metric.
Address the obvious gap in one honest line rather than hoping nobody notices. No enthusiasm padding.

## Running it inline

Where agents are unavailable, the procedure is the same and the scripts are the same. What you lose is
the separation, not the method — so be stricter about the two places it matters: keep the
advertisement before you read anything out of it, and run the scripts rather than trusting your own
arithmetic.
