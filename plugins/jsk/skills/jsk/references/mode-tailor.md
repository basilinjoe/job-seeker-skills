# Mode: tailor

Match the career against a posting, close the gaps, then write the resume once.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` entry in the career. If the posting wants something
they have not done, say so — never manufacture a bullet: a bluff is found out in the first
technical conversation.

## The shape

```
posting_capture     the advert, as lines    ──►  posting      its requirements, each quoting a line
assessment_derive   requirements × career   ──►  assessment   verdicts, shortfalls, the question queue
answers             career_apply / confirm  ──►  selection    authored once, confirmed, shipped
```

Every step is a `jsk` tool; every part of the application is a graph in the store. Its stem,
`<yyyy-mm-dd>-<company>-<role>`, cannot be renamed until `app_freeze`; the first render
creates `<workspace>/applications/<stem>/`, for the renders and any cover letter. A file-made
unsent one (`app_list` marks it) is finished by jsk 5.1.0, or `app_drop`ped once the person agrees.

**Two agent passes, the person between.** One writes the assessment; one writes the resume
**last**, after the answers — never from a career you are about to change.

## 0. Have they been here before?

**First**, load the run's tools in one ToolSearch select: app_list, posting_capture, app_show,
career_query, career_show, career_preview, career_apply, career_confirm, assessment_derive,
assessment_review, assessment_complete, app_freeze, app_event. No `jsk --version` or `ls`: `app_list()`
proves the workspace and lists each application's stage. Applying twice is ordinary: a check,
not a prohibition. If one matches the company, **show them** the role, its stage and when, and
stop: **that decision is theirs and comes before the work.**

## 1. Capture the posting

`$ARGUMENTS` may hold a URL, the text, or a path. Name the stem from the URL's slug or the text,
or ask. **You capture**: the analyst captures only a board URL it is handed. Its result suffices;
do not read the lines. **Ashby, Greenhouse or Lever, or a file (`.docx`, `.html`, `.txt`): `posting_capture(app=<stem>,
url=<it>)`**, never through the context. **JavaScript-rendered career sites** (Workday,
SuccessFactors, iCIMS, Phenom `careers.<company>` portals) **go straight to a browser tool**: a
plain fetch sees an empty shell. Open the posting and save it, outside the application directory,
with `browser_run_code_unsafe`, which returns none of the page: `async p=>{const[d]=await
Promise.all([p.waitForEvent('download'),p.evaluate(()=>{const
a=document.createElement('a');a.href=URL.createObjectURL(new
Blob([document.documentElement.outerHTML]));a.download='p.html';a.click()})]);await
d.saveAs('<scratch>/posting.html')}`; capture that file. A failed fetch: say so and ask them
to paste it. Pasted: `posting_capture(app=<stem>, text=…)`, **the
advertisement verbatim and nothing else**; **never paraphrase it**.

## 1b. Triage

A bad fit shows in seconds; the assessment takes minutes. With the capture, run
`career_query("person")` and `career_query("evidence", [terms])`, 2–5 terms: the title's domain
first, then one per distinct required-qualification cluster (a posting's security pillar is one). **A title term `nothing`, or eligibility plainly failing: ask
whether to go on, before dispatching.** A doubt short of that, a whole required cluster `nothing`
included: dispatch the analyst in the background and ask at once; on "stop", stop the agent.

## 2. Assess

Send `jsk-tailor-analyst` the stem and the person facts triage read (location, work
authorisation), then stop: **its definition holds the procedure and the return: send no skill
directory, ask for no report.** It decides the requirements, derives the assessment and reviews
it, all through tools. It never touches the career. Never ask years the record's dates answer.

It returns the fit, what is blocking, and the assessment's Markdown. **Show them the assessment
whole**, no summary or rewrite, leading with the blocking line when there is one.
**Author nothing yet** when: the ranking is close between projects with materially different
ownership verbs, a top-ranked project carries unconfirmed content, eligibility fails, or the role
may not be worth applying to. That holds the resume back, not the turn. Declined:
`app_freeze(app, submitted="false", channel=<why>)`, no resume needed.
**Showing the assessment is never the last thing you do: go straight on to step 3 in the same
turn.** Ending the turn on printed questions is how a run stalls.

## 3. Ask the whole queue at once

**Ask with `AskUserQuestion`**, the assessment's questions in its order: four a call, a longer
queue several calls in the same turn.

- **A blocking question goes alone, first.** If the answer ends it ("I can't do Pacific hours"),
  say so, record it, and ask nothing else.
- **Every question gets real options**, 2–4. An inferred claim: quoted, with its source, and
  *Confirm* / *Correct it* / *Cut it*.
- **Never offer a bare "Yes"**: its detail then costs a whole round. Offer *No, none* and *Skip*,
  and end the question with what a yes types in *Other*: "what, where, roughly when"; for a number,
  "the figure, the project, and its source". An honest "~50 tenants" beats silence.
- **Offer the skip every round**, "Skip the rest?" when the queue is long.
- `header` is the id or topic in 12 characters or fewer: `GraphQL`, `ach_unitng`.

Then go one at a time, in plain chat, **only** for answers that came back ambiguous, incomplete,
or contradicting the career. Without `AskUserQuestion`, number the queue in chat and ask for a
bulk reply: the one time the turn ends on the questions.

### Answers go into the career

An answer changes **the career** — never the assessment or the selection, both downstream of it.

- **A round's corrections, new facts and noes are one changeset**, one `career_apply`, after
  `career_show(ids)` for the `op:base`. A corrected claim comes back `inferred`; confirm it next.
  A bullet's `j:shows` concept needs the project's `j:uses` (`shows-unheld` WARNs; the match
  counts only concepts the project uses). Its shape, so no reference is read:
  ```turtle
  @prefix j: <tag:jsk,2026:ns#> .
  @prefix k: <tag:jsk,2026:id/> .
  @prefix c: <tag:jsk,2026:concept/> .
  @prefix op: <tag:jsk,2026:op#> .
  @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
  op:changeset op:base 3 ; op:summary "Round 1 answers, Everforth." .
  op:add { k:prj_unitng j:uses c:azure-logic-apps .  c:azure-logic-apps a j:Technology .
           k:abs_kafka j:concept c:kafka ; j:said "2026-10-02"^^xsd:date ;
             j:answer "Never used Kafka." .
           [] j:project k:prj_unitng ; j:rank 4 ; j:text "Ran 40 flows on Logic Apps." ;
             j:shows c:azure-logic-apps . }
  op:set { k:ach_unitng_x j:text "The corrected words." . }
  ```
- **A "no"** ("never used Kafka") is a `k:abs_<concept>` as above, their words its `j:answer`;
  once confirmed, no later posting asks it again for a year.
- **A term they name** (`ambiguous`, `unknown-term`): if `asked` is a term, not a clause, the
  changeset labels the concept with it — `op:add { c:ai-agents j:label "autonomous agents" . }`
  — so no later posting asks again. A clause stays a concept on its row.
- **What they confirmed**, a "no" included: `career_confirm(answers=[{ids, answer}, …])`, every group in one
  call and one revision; it also answers their open questions. After a clean `career_preview` of the
  same changeset, `diff=false` on `career_apply` or `career_confirm` returns a short `summary`.
- **Unanswerable**: soften or cut the claim in the changeset; never leave it pending.

## 4. Another round only if a verdict moved

Revise the assessment **only when an answer changed what the career holds**. Re-derive with
`assessment_derive`: the stored review folds into the new match.

**Patch it yourself with `assessment_review` when every change is a row** — a lowered verdict, an
answered question struck from `asks` — then `assessment_complete`; it fails a verdict above the
match. **Send it back only when the fit could change or an answer needs a row the assessment
lacks**: `SendMessage` to the same agent with what changed.

The loop ends when they skip, when nothing is left worth asking, when a round produces no new
answerable question, or at three rounds (`--rounds N` in `$ARGUMENTS` overrides). **Say which reason.**

## 5. Author, once

`jsk-resume-author` writes the selection. **Resolve its paths first; it reads only what the prompt names:**

- the stem and the skill directory — absolute, forward slashes;
- the assessment, as `app_show(stem, "assessment")` last gave it;
- the rule files, absolute: `<skill>/references/writing-rules.md`, `ats-rules.md`, and the
  `## Structure rules for rendering` section of `mode-resume.md` (its line number), each replaced
  by `rules/<name>.md` beside `career/` where one exists (one `ls`).

Bullets it adds or rewords arrive `inferred`; the render drops them below the floor as
`withheld …` warnings, each confirmed or cut before hand-over. **It quotes every clause back.**
**Read those quotes to the person and get confirm-correct-or-cut on each**, then one `career_confirm(answers=[…])`
with their words and one changeset for the corrections. Confirm confirms the career's current
text, never on the strength of the old text. If the selection (`app_show(stem, "selection")`)
holds a summary, `career_confirm(target=<stem>, block="summary", answer=…)`; a headline, the same
with `block="headline"`. Shortfalls it returns go into the review (`short`), then
`assessment_complete`, then `resume_check(target=<stem>)`. Yours, not delegable.

**A selection references content; it cannot contain it.** Say out loud what the career lacks.

## 6. Ship

Follow `references/mode-ship.md`: `resume_ship`, the render gate, `app_freeze`. A failed gate
freezes nothing.

## 7. Tell them where they fall short

Every time, in chat, before they ask:

> "Two gaps survived: people-management (mentoring, nothing on hiring) and Terraform (your IaC is
> all Bicep). The resume can't claim depth you don't have."

A genuinely poor fit: say so.

## Cover letter, if asked

Under 250 words: best match first, one metric, the gap in a line, in
`applications/<stem>/cover-letter.txt`; show `letter_check(letter=<it>, record=<stem>)` passing.

## Running it inline

Without agents the procedure is the same; trust the tools' verdicts over your own reading.
