# Mode: tailor

Read the knowledge base, close the gaps against a posting, then write the resume once.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` entry in `user-knowledgebase.md`. If the posting wants
something they have not done, say so — do not manufacture a bullet. Anything `inferred` needs
confirmation before it appears.

Not only ethics: someone who bluffs past a screen gets found out in the first technical
conversation, having burned both the opportunity and their credibility.

## The shape

```
posting.md              ──►  requirements[] in its own frontmatter
user-knowledgebase.md   ──►  read whole, once
      └───────────────────►  gaps.md     verdicts, shortfalls, the question queue
answers                 ──►  written back into user-knowledgebase.md
                                  └──►  resume.json, authored once, confirmed, shipped
```

Everything for one application lives in one directory:

```
applications/<yyyy-mm-dd>-<company>-<role>/
  posting.md  gaps.md  resume.json  application.md  <Name>_<Company>_Resume.{tex,pdf,txt}
```

Name it for the day it is being worked on; if it is held back and sent later, rename the directory
then. `references/kb-spec.md` has what each file holds.

**Two agent passes, and the person in between.** One reads the posting and the knowledge base and
writes the assessment; one authors the record after the questions are answered.

The resume is written **last**. There is no reason to author a document from a knowledge base you
are about to change, and doing it at the end drops every wasted authoring pass.

## 0. Have they been here before?

**Before the posting is written down and before the analyst runs:**

```bash
ls <path>/applications/ | grep -i "<company>"
```

Applying twice is ordinary, and that is exactly why this is a check rather than a prohibition: the
second round is often the right move, and it is only ever the right move on purpose. Over a
hundred-application search the mistake this catches is mundane and expensive — a company applied to
eleven weeks ago, a screen that went quiet and was never closed out, a second application landing on
the desk of a recruiter who already has one. None of that is visible in the posting, and by the time
it surfaces the round has been paid for.

If anything comes back, **read its `application.md` and show them**: the role it was for, the last
event in its timeline, and when. Then stop. A rejection two years old, a screen that went silent last
month and a live application to a different team at the same employer are three different situations
and only one person can tell them apart. **That decision is theirs and it comes before the work**,
the same as the fit verdict at step 2.

Nothing back means nothing recorded, which is not quite the same as never applied — if they think
they have been here before, that is a `pipeline` backlog item, not a reason to skip the round.

## 1. Get the posting

`$ARGUMENTS` may hold a URL, the text, or a path. **Fetch a URL yourself**; the analyst has no
network tools. Job boards refuse often — LinkedIn and most Workday tenants sit behind a wall — so
when a fetch fails, say what happened and ask them to paste it. That is an ordinary outcome, not an
error.

Create the application directory and write `posting.md` — **the advertisement verbatim in the body**,
frontmatter above it:

```markdown
---
company: Acme Health
title: Platform Engineer
url: https://…
seniority: platform-design
domains: [healthcare]
captured: 2026-09-08
requirements: []          # the analyst fills this
---

<the advertisement, verbatim, unedited>
```

Keep the URL either way; the archive needs it. **Never paraphrase the advertisement.** It is the
thing a person re-reads and the thing the archive has to keep — a summary of a posting cannot answer
what an application was answering.

## 2. Assess

Send `jsk-tailor-analyst` the posting path and the knowledge base path. It writes the requirements
into the posting's frontmatter and the assessment into `gaps.md` beside it, and returns the ranking.

**Show them the assessment.** Not a summary of it. It is written to be read aloud, which is the whole
reason it is Markdown and not a document with a schema.

**Surface what came back in your own words**, and stop before anything is authored when: the ranking
is close between projects with materially different ownership verbs, a top-ranked project carries
unconfirmed content, eligibility fails, or the posting suggests the role may not be worth applying to
at all. That last decision is theirs and it comes before the work.

## 3. Ask the whole queue at once

Present the ordered queue and take a bulk reply. Then go one at a time **only** for answers that came
back ambiguous, incomplete, or that contradict what the knowledge base already says.

This departs from `mode-gaps.md`'s standing rule — *"one question at a time… a list of fifteen gets
abandoned; one gets answered"* — and the departure is deliberate. That rule was written for an
open-ended audit with no natural end. A tailoring round is bounded, ordered by priority, and every
question names the requirement it would close, so the person can see the whole cost before starting
it. `/jsk:gaps` keeps one-at-a-time.

**Offer the skip.** It is the ordinary exit, not a failure.

For a claim the knowledge base only infers, quote it exactly, say where it came from, and offer
confirm, correct, or cut. For a missing metric, prompt with where the number might live —
dashboards, billing, retros, release notes, incident reviews, promotion documents, a colleague.
**Ask twice, then let go**: an honest "~50 tenants" beats silence, and a bullet permanently awaiting
a number is a bullet nobody improved.

### Answers go into the knowledge base

An answer edits **`user-knowledgebase.md`** — the project's block, the metrics table, the role. Not
`gaps.md`, and never the record: those are downstream of it. One place, because there is only one
source.

Ordinary `Edit` calls, and one rule that is now entirely yours to keep: **when they confirm a claim,
change its `status` to `confirmed` and fill the `answered` date in `## Open questions`.** Nothing
does it for you, and a claim left `inferred` after they confirmed it will refuse to render at step 5
for a reason that no longer exists.

Where they *correct* a claim rather than confirming it, the corrected text is `confirmed` too — they
just said it. Where they cannot answer, resolve the question as unavailable and **soften or cut the
claim**; a row pending forever is the state this framework exists to prevent.

## 4. A second round only if a verdict moved

Run the analyst again **only when an answer changed what the knowledge base holds** — a metric
arrived, an unevidenced claim got its evidence, a requirement that was indeterminate can now be
judged.

**Continue the same agent with `SendMessage`; do not spawn a second one.** It still holds the
posting, the knowledge base and the vocabulary — tens of kilobytes it would otherwise read again to
learn what it already knows. Send it what changed and which sections moved, and let it revise
`gaps.md` rather than re-derive it. A fresh agent is not merely slower: it re-reads a knowledge base
the answers have just changed and has no memory of which verdicts it had already settled, so it
re-opens them.

Only start a cold analyst if the first one is gone — the run was interrupted, or the session ended.
Then pass it the previous `gaps.md` so it revises rather than starting over.

Otherwise stop. A round that re-asks what was already answered is how a loop stops ending.

**Say why it ended.** "Nothing left worth asking" and "you skipped with four things open" call for
different next moves.

## 5. Author, once

`jsk-resume-author` writes `resume.json` — the URS record, including the view and the prose. Four
things carry that:

- **Everything it authors is `inferred`**, and `provenance_floor: confirmed` on the view means
  `jsk validate` refuses to render it until a person confirms. A failing record gate here is the
  guardrail working, not a problem to route around.
- **Every numeral must trace to a metric** in the knowledge base's `## Metrics` table. Tailoring is
  exactly when a rewritten clause inflates a number, and that check is what catches it.
- **The record is written by hand**, so it is checked more strictly than it used to be. `jsk
  validate` fails an unrecognised top-level key, because `experience:` written where `engagements:`
  belongs renders a resume with no jobs on it and the mistake is invisible in the PDF.
- **It quotes every clause back**, with what it derived it from.

**Read those quotes to the person and get confirm-correct-or-cut on each**, then flip the confirmed
ones — in the knowledge base first, then in the record. This step is yours and is not delegable.

**A view references content; it cannot contain it.** `jsk validate` rejects free text inside a view
and fails on a key it does not recognise. That is the structural expression of the rule at the top of
this file: a format where invention is impossible beats a process where invention is merely
discouraged. If the posting wants something the knowledge base does not have, the view has nothing to
point at — which is the honest outcome, and the thing to say out loud.

## 6. Ship

`/jsk:ship`, or `references/mode-ship.md` inline. It renders, runs the four gates, freezes the
application directory and logs the submission. It never freezes a document that failed a gate.

## 7. Tell them where they fall short

Every time, in chat, before they ask. By now this is a reading of the assessment rather than a
judgement you are forming:

> "Two gaps survived. They want direct people-management — you have technical leadership and
> mentoring evidence, but nothing on hiring or performance reviews. And they name Terraform
> throughout; your IaC evidence is all Bicep. The concepts transfer and you could say so in
> interview, but the resume can't claim Terraform depth you don't have."

A named gap can be prepared for, addressed in a cover letter, or used to decide the role is not worth
applying to. That decision is theirs and needs real information. If the fit is genuinely poor, say so.

## Cover letter, if asked

Under 250 words. Strongest capability match first. One concrete piece of evidence with its metric.
Address the obvious gap in one honest line rather than hoping nobody notices. No enthusiasm padding.

## Running it inline

Where agents are unavailable, the procedure is the same and the commands are the same. What you lose
is the separation, not the method — so be stricter about the two places it matters: keep the
advertisement before you read anything out of it, and run `jsk validate` rather than trusting your
own reading of the record.
