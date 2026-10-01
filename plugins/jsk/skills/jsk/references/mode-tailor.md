# Mode: tailor

Match the career against a posting, close the gaps, then write the resume once.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` entry in the career. If the posting wants something
they have not done, say so — do not manufacture a bullet; someone who bluffs past a screen is found
out in the first technical conversation. A selection names career entries by id, so it cannot
hold what the career does not.

## The shape

```
posting_capture     the advert, as lines    ──►  posting      its requirements, each quoting a line
assessment_derive   requirements × career   ──►  assessment   verdicts, shortfalls, the question queue
answers             career_apply / confirm  ──►  selection    authored once, confirmed, shipped
```

Every step is a `jsk` tool, and every part of the application is a graph in the store. Its stem
is `<yyyy-mm-dd>-<company>-<role>`, named for the day it is worked on; the first render creates
`<workspace>/applications/<stem>/`, which holds the `.pdf` and `.tex` and nothing else, and
`jsk app freeze` renames it if sent later. An application made from files (`posting.md`,
`decisions.txt`) is finished on the commands it was started on: the tools refuse it, naming them.

**Two agent passes, and the person in between.** One writes the assessment; one writes the resume
after the questions are answered. The resume is written **last** — never from a career you are
about to change.

## 0. Have they been here before?

**Before the posting is captured**, `app_list()`: each application and its stage. Applying twice
is ordinary, so this is a check, not a prohibition. If one matches the company, **show them** the
role, its stage and when. Then stop: **that
decision is theirs and it comes before the work.** Nothing back means nothing recorded, not never
applied.

## 1. Capture the posting

`$ARGUMENTS` may hold a URL, the text, or a path. **You capture it**; the analyst has no network.
**Ashby, Greenhouse or Lever, or a file (`.docx`, `.html`, `.txt`): `posting_capture(app=<stem>,
url=<it>)`**, never through the context. **JavaScript-rendered career sites** (Workday,
SuccessFactors, iCIMS, Phenom `careers.<company>` portals) **go straight to a browser tool**: a
plain fetch sees an empty shell. Open the posting and save it, outside the application directory,
with `browser_run_code_unsafe`, which returns none of the page: `async p=>{const[d]=await
Promise.all([p.waitForEvent('download'),p.evaluate(()=>{const
a=document.createElement('a');a.href=URL.createObjectURL(new
Blob([document.documentElement.outerHTML]));a.download='p.html';a.click()})]);await
d.saveAs('<scratch>/posting.html')}`; capture that file. When a fetch fails, say so and ask them
to paste it — an ordinary outcome, not an error. Pasted: `posting_capture(text=…)`, **the
advertisement verbatim and nothing else**; **never paraphrase it**.

## 1b. Triage

A bad fit shows in two seconds; the assessment takes minutes. In one message with the capture and
step 0's calls, run `career_query("person")` and `career_query("evidence", [terms])`: the 2–5
load-bearing terms of the title and first qualifications, the title's domain first. **A title term
`nothing`, or eligibility plainly failing: ask whether to go on, before dispatching.** A doubt
short of that: dispatch the analyst in the background and ask at once; on "stop", stop the agent.

## 2. Assess

Send `jsk-tailor-analyst` the stem, and the posting facts worth flagging, then stop: **its
definition holds the procedure and the return, so do not send the skill directory or ask for a
report.** It decides the requirements, derives the assessment and reviews it, all through tools.
It never touches the career.

It returns the fit, what is blocking, and the assessment's Markdown. **Show them the assessment
whole**, not a summary of it and not a rewrite, leading with the blocking line when there is one.
**Author nothing yet** when: the ranking is close between projects with materially different
ownership verbs, a top-ranked project carries unconfirmed content, eligibility fails, or the role
may not be worth applying to at all. That holds the resume back; it does not end the turn.
**Showing the assessment is never the last thing you do: go straight on to step 3 in the same
turn.** Printing the questions as text and ending the turn is how a run stalls.

## 3. Ask the whole queue at once

**Ask with `AskUserQuestion`**, the assessment's questions in its order: four a call, a longer
queue several calls in the same turn.

- **A blocking question goes alone, first.** If the answer ends it ("I can't do Pacific hours"),
  say so, record it, and ask nothing else.
- **Every question gets real options**, 2–4 of them. An inferred claim: quoted, with where it came
  from, and *Confirm* / *Correct it* / *Cut it*.
- **Never offer a bare "Yes"**: its detail then costs a whole round. Offer *No, none* and *Skip*,
  and end the question with what a yes types in *Other*: "what, where, roughly when"; for a number,
  "the figure, the project, and its source" — dashboards, billing, retros, release notes, a
  colleague. An honest "~50 tenants" beats silence.
- **Offer the skip every round**, and "Skip the rest of these?" when the queue is long.
- `header` is the id or topic in 12 characters or fewer: `GraphQL`, `ach_unitng`.

Then go one at a time, in plain chat, **only** for answers that came back ambiguous, incomplete,
or contradicting the career. Where `AskUserQuestion` is not available, list the queue in chat
numbered, ask for a bulk reply, and that is the one time the turn ends on the questions.

### Answers go into the career

An answer changes **the career** — never the assessment or the selection, both downstream of it.

- **A round's corrections, new facts and noes are one changeset**, one `career_apply`, after
  `career_show(ids)` for the `op:base`. A corrected claim comes back `inferred`; confirm it next.
  Its shape, so no reference is read for it:
  ```turtle
  @prefix j: <tag:jsk,2026:ns#> .
  @prefix k: <tag:jsk,2026:id/> .
  @prefix c: <tag:jsk,2026:concept/> .
  @prefix op: <tag:jsk,2026:op#> .
  @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
  op:changeset op:base 3 ; op:summary "Round 1 answers, Everforth." .
  op:add { k:prj_unitng j:uses c:azure-logic-apps .  c:azure-logic-apps a j:Technology .
           k:abs_kafka j:concept c:kafka ; j:said "2026-10-02"^^xsd:date ;
             j:answer "Never used Kafka." . }
  op:set { k:ach_unitng_x j:text "The corrected words." . }
  ```
- **A "no"** ("never used Kafka") is a `k:abs_<concept>` as above, their words its `j:answer`;
  once confirmed, no later posting asks it again for a year.
- **A term they name** (`ambiguous`, `unknown-term`): if `asked` is a term, not a clause, the
  changeset labels the concept with it — `op:add { c:ai-agents j:label "autonomous agents" . }`
  — so no later posting asks again. A clause stays a concept on its row.
- **What they confirmed**, a "no" included: `career_confirm(ids, answer="their words")`, which also
  answers the open questions about them.
- **Unanswerable**: soften or cut the claim in the changeset; never leave it pending forever.

## 4. Another round only if a verdict moved

Revise the assessment **only when an answer changed what the career holds**. Re-derive with
`assessment_derive`: the stored review folds into the new match.

**Patch it yourself with `assessment_review` when every change is a row** — a lowered verdict, an
answered question struck from `asks` — then `assessment_complete`; it fails a verdict above the
match. **Send it back only when the fit could change or an answer needs a row the assessment
lacks**: `SendMessage` to the same agent with what changed.

The loop ends when they skip, when nothing is left worth asking, when a round produces no new
answerable question, or at three rounds (`--rounds N` in `$ARGUMENTS` overrides). **Say which reason
ended it.**

## 5. Author, once

`jsk-resume-author` writes the selection. **Resolve its paths before dispatching; it reads only
what the prompt names:**

- the stem and the skill directory — absolute, forward slashes;
- the assessment, as `app_show(stem, "assessment")` last gave it;
- the rule files, absolute: `<skill>/references/writing-rules.md`, `ats-rules.md`, and the
  `## Structure rules for rendering` section of `mode-resume.md` (its line number), each replaced
  by `rules/<name>.md` beside `career/` where one exists (one `ls`).

Bullets it adds or rewords arrive `inferred`; the render drops them below the floor as
`withheld …` warnings, each confirmed or cut before hand-over. **It quotes every clause back.**
**Read those quotes to the person and get confirm-correct-or-cut on each**, then `career_confirm`
with their words and one changeset for the corrections. Confirm confirms the career's current
text, never on the strength of the old text. The summary: `career_confirm(target=<stem>,
block="summary", answer=…)`, the posting's title as headline with `block="headline"`. Shortfalls it
returns go into the review (`short`). Then `jsk resume check <stem>`, the record gate. This step is
yours and is not delegable.

**A selection references content; it cannot contain it.** If the posting wants something the career does
not have, say so out loud.

## 6. Ship

Follow `references/mode-ship.md`: `resume_ship`, the render gate, `jsk app freeze`. A failed gate
freezes nothing.

## 7. Tell them where they fall short

Every time, in chat, before they ask:

> "Two gaps survived. They want direct people-management — you have technical leadership and
> mentoring evidence, but nothing on hiring. And they name Terraform throughout; your IaC evidence is
> all Bicep. The resume can't claim Terraform depth you don't have."

If the fit is genuinely poor, say so.

## Cover letter, if asked

Under 250 words: best match first, one metric, the gap in a line. Write
`applications/<stem>/cover-letter.txt`; show `jsk letter check <it> --app <stem>` passing.

## Running it inline

Without agents, the procedure is the same: capture the advertisement before you read anything out
of it, and trust the tools' verdicts over your own reading.
