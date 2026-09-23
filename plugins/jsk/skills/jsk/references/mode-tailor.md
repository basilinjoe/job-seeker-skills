# Mode: tailor

Read the knowledge base, close the gaps against a posting, then write the resume once.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` entry in `user-knowledgebase.md`. If the posting wants
something they have not done, say so — do not manufacture a bullet; someone who bluffs past a screen
is found out in the first technical conversation. Anything `inferred` needs confirmation before it
appears.

## The shape

```
posting.md              ──►  requirements[] in its own frontmatter
user-knowledgebase.md   ──►  jsk index --rank; only the ranges cited
      └───────────────────►  gaps.md     verdicts, shortfalls, the question queue
answers                 ──►  written back into user-knowledgebase.md
                                  └──►  resume.json, authored once, confirmed, shipped
```

Everything for one application lives in one directory:

```
applications/<yyyy-mm-dd>-<company>-<role>/
  posting.md  gaps.md  resume.json  application.md  <Name>_<Company>_Resume.{tex,pdf,txt}
```

Name it for the day it is being worked on; `jsk freeze` renames it if it is sent later.
`references/kb-spec.md` has what each file holds.

**Two agent passes, and the person in between.** One writes the assessment; one authors the record
after the questions are answered. The resume is written **last** — never from a knowledge base you
are about to change.

## 0. Have they been here before?

**Before the posting is written down and before the analyst runs:**

```bash
ls <path>/applications/ | grep -i "<company>"
```

Applying twice is ordinary, so this is a check, not a prohibition — a second round is only right on
purpose. If anything comes back, **read its `application.md` and show them** the role, the last
event in its timeline, and when. Then stop: **that decision is theirs and it comes before the work.**

Nothing back means nothing recorded, not never applied — if they think they have been here before,
that is a `pipeline` backlog item, not a reason to skip the round.

## 1. Get the posting

`$ARGUMENTS` may hold a URL, the text, or a path. **Fetch a URL yourself**; the analyst has no
network tools. **Career sites that render with JavaScript** (Workday, SuccessFactors, iCIMS,
Phenom-style `careers.<company>` portals) **go straight to a browser tool** when one is available: a
plain fetch of those sees an empty shell and can report a live posting as closed. Boards often refuse
(LinkedIn, most Workday tenants) — when a fetch fails, say what happened and ask them to paste it.
That is an ordinary outcome, not an error.

Create the application directory and write `posting.md` — **the advertisement verbatim in the body**,
frontmatter above it:

```markdown
---
company: "Acme Health"
title: "Platform Engineer"      # quoted: a title often holds a colon
url: https://…
seniority: platform-design
domains: [healthcare]
captured: 2026-09-08
requirements: []          # the analyst fills this
---

<the advertisement, verbatim, unedited>
```

Keep the URL either way. **Never paraphrase the advertisement** — the archive has to say what the
application was answering.

## 2. Assess

Send `jsk-tailor-analyst` the posting path and the knowledge base path. It writes the requirements
into the posting's frontmatter and the assessment into `gaps.md` beside it, and returns the ranking.

**Show them the assessment**, not a summary of it.

**Surface what came back in your own words**, and stop before anything is authored when: the ranking
is close between projects with materially different ownership verbs, a top-ranked project carries
unconfirmed content, eligibility fails, or the posting suggests the role may not be worth applying to
at all. That last decision is theirs and it comes before the work.

## 3. Ask the whole queue at once

Present the ordered queue and take a bulk reply. Then go one at a time **only** for answers that came
back ambiguous, incomplete, or that contradict the knowledge base. (A tailoring round is bounded and
every question names the requirement it closes; `/jsk:gaps` keeps one-at-a-time.)

**Offer the skip every round.** It is the ordinary exit, not a failure.

For a claim the knowledge base only infers, quote it exactly, say where it came from, and offer
confirm, correct, or cut. For a missing metric, prompt with where the number might live —
dashboards, billing, retros, release notes, incident reviews, promotion documents, a colleague.
An honest "~50 tenants" beats silence.

### Answers go into the knowledge base

An answer edits **`user-knowledgebase.md`** — the project's block, the metrics table, the role. Not
`gaps.md`, and never the record: both are downstream of it.

**Apply a round's answers in one pass**, not one `Edit` per change: list every old-to-new
replacement, write them into a script with the Write tool (a shell heredoc mangles backslashes), and
have it assert each old string occurs exactly once before replacing any.

**When they confirm a claim, change its `status` to `confirmed` and fill the `answered` date in
`## Open questions`** — a claim left `inferred` will refuse to render at step 5. A *corrected* claim
is `confirmed` too. Where they cannot answer, resolve the question as unavailable and **soften or cut
the claim**; never leave a row pending forever.

## 4. Another round only if a verdict moved

Revise `gaps.md` **only when an answer changed what the knowledge base holds** — a metric arrived,
an unevidenced claim got its evidence, an indeterminate requirement can now be judged.

**Patch it yourself when every change is a row** — a verdict with its evidence or shortfall, a
project's matched terms and score (+3 a required term, +1 a preferred), an answered question struck
— in one scripted pass, as with the answers. A second analyst round costs minutes to rewrite what you
already know. **Send it back only when the fit could change or an answer needs a row the assessment
lacks**: `SendMessage` to the same agent with what changed; a cold one, handed the previous
`gaps.md`, only if that one is gone.

The loop ends when they skip, when nothing is left worth asking, when only `unexplored` questions
remain, when a round produces no new answerable question, or at three rounds (`--rounds N` in
`$ARGUMENTS` overrides the cap). Never re-ask what was already answered. **Say which reason ended
it** — "nothing left to ask" and "you hit the cap with four things open" call for different next
moves.

## 5. Author, once

`jsk-resume-author` writes `resume.json` — the URS record, including the view and the prose.
**Resolve its paths before dispatching; it reads only what the prompt names:**

- the posting, `gaps.md`, `user-knowledgebase.md`, and the skill directory — absolute paths;
- whichever of `rules/writing-rules.md`, `rules/ats-rules.md`, `rules/structure-rules.md` exist beside
  the knowledge base (one `ls`), or "no overrides";
- the example record: `python -c "from jsk.paths import EXAMPLE_RECORD; print(EXAMPLE_RECORD)"`.

What it writes:

- **Everything it authors is `inferred`**, so a view with `provenance_floor: confirmed` fails
  `jsk validate` until a person confirms. That is the guardrail working.
- **Every numeral must trace to a metric** in the knowledge base's `## Metrics` table — tailoring is
  when a rewritten clause inflates a number.
- **It quotes every clause back**, with what it derived it from.

**Read those quotes to the person and get confirm-correct-or-cut on each**, then flip the confirmed
ones — in the knowledge base first, then in the record. This step is yours and is not delegable.

**A view references content; it cannot contain it** — `jsk validate` rejects free text inside a
view. If the posting wants something the knowledge base does not have, the view has nothing to point
at: say so out loud.

## 6. Ship

Follow `references/mode-ship.md`: render, the four gates, `jsk freeze`, the `log.md` row. Nothing is
frozen that failed a gate.

## 7. Tell them where they fall short

Every time, in chat, before they ask — a reading of the assessment:

> "Two gaps survived. They want direct people-management — you have technical leadership and
> mentoring evidence, but nothing on hiring or performance reviews. And they name Terraform
> throughout; your IaC evidence is all Bicep. The concepts transfer and you could say so in
> interview, but the resume can't claim Terraform depth you don't have."

If the fit is genuinely poor, say so.

## Cover letter, if asked

Under 250 words. Strongest capability match first. One concrete piece of evidence with its metric.
Address the obvious gap in one honest line. No enthusiasm padding.

## Running it inline

Without agents, the procedure and commands are the same. Be stricter where the separation mattered:
keep the advertisement before you read anything out of it, and run `jsk validate` rather than
trusting your own reading of the record.
