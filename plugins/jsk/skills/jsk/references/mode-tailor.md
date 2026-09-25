# Mode: tailor

Match the career against a posting, close the gaps, then write the resume once.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` entry in `career/kb.ttl`. If the posting wants something
they have not done, say so — do not manufacture a bullet; someone who bluffs past a screen is found
out in the first technical conversation. The claims gate refuses a record that claims more than the
career holds.

## The shape

```
posting.md     the advert, verbatim   ──►  posting.ttl  its requirements, each quoting it
jsk match      requirements × career  ──►  gaps.md      verdicts, shortfalls, the question queue
answers        jsk kb apply / confirm ──►  resume.json  authored once, confirmed, shipped
```

One directory per application:

```
applications/<yyyy-mm-dd>-<company>-<role>/
  posting.md  posting.ttl  gaps.md  resume.json  application.ttl  <Name>_<Company>_Resume.{tex,pdf,txt}
```

Name it for the day it is being worked on; `jsk freeze` renames it if it is sent later.

**Two agent passes, and the person in between.** One writes the assessment; one authors the record
after the questions are answered. The resume is written **last** — never from a career you are
about to change.

## 0. Have they been here before?

**Before the posting is written down**, Glob `<workspace>/applications/*<company>*`, then:

```bash
jsk kb query pipeline      # each sent application's stage, and when
```

Applying twice is ordinary, so this is a check, not a prohibition. If anything comes back, **show
them** the role, its stage and when. Then stop: **that decision is theirs and it comes before the
work.** Nothing back means nothing recorded, not never applied.

## 1. Get the posting

`$ARGUMENTS` may hold a URL, the text, or a path. **Fetch a URL yourself**; the analyst has no
network tools. **Career sites that render with JavaScript** (Workday, SuccessFactors, iCIMS,
Phenom-style `careers.<company>` portals) **go straight to a browser tool** when one is available: a
plain fetch sees an empty shell and can report a live posting as closed. When a fetch fails, say what
happened and ask them to paste it — an ordinary outcome, not an error.

Create `<workspace>/applications/<stem>/` and write `posting.md` **with the Write tool, never a
shell heredoc** (an advert's quotes and apostrophes break the shell): **the advertisement verbatim and
nothing else**, the URL on its first line. **Never paraphrase it** — the archive has to say what the
application was answering, and every requirement quotes it.

## 2. Assess

Send `jsk-tailor-analyst` the application directory and the workspace, both absolute, and the
`kb` path `jsk kb path` printed. Name it as that file's path, never as "the folder holding
career/kb.ttl": a workspace named `career` makes that phrase point at the wrong folder. Add the
posting facts worth flagging, then stop: **its definition holds the procedure and the return, so
do not send the skill directory or ask for a report.** It writes `posting.ttl`, runs `jsk match`,
and writes `gaps.md` from the match. It never touches `career/kb.ttl`.

It returns three lines: the fit, what is blocking, and the path to `gaps.md`. **Read `gaps.md` and
show them the assessment whole**, not a summary of it and not a rewrite, leading with the blocking
line when there is one. **Author nothing yet** when: the ranking is close between projects with
materially different ownership verbs, a top-ranked project carries unconfirmed content,
eligibility fails, or the role may not be worth applying to at all. That holds the resume back; it
does not end the turn. **Showing the assessment is never the last thing you do: go straight on to
step 3 in the same turn.** Printing the questions as text and ending the turn is how a run stalls.

## 3. Ask the whole queue at once

**Ask with `AskUserQuestion`**, the questions from `gaps.md` in its order. It takes four questions
a call, so a longer queue is several calls, one after another, in the same turn.

- **A blocking question goes alone, first.** If the answer ends it ("I can't do Pacific hours"),
  say so, record it, and ask nothing else.
- **Every question gets real options**, 2–4 of them. An inferred claim: *Confirm* / *Correct it* /
  *Cut it*, the claim quoted in the question.
- **Never offer a bare "Yes".** A "yes" to an exposure or metric question is useless without its
  detail, and asking for it costs a whole round. Offer *No, none* and *Skip*, and end the question
  with what a yes should say, typed in the tool's *Other*: "If yes, choose Other: what, where,
  roughly when." For a number: "…the figure, the project, and where it comes from."
- **Offer the skip every round**: a *Skip* option on each question, and one question can be
  "Skip the rest of these?" when the queue is long.
- `header` is the id or topic in 12 characters or fewer: `GraphQL`, `ach_unitng`.

Then go one at a time, in plain chat, **only** for answers that came back ambiguous, incomplete,
or contradicting the career. Where `AskUserQuestion` is not available, list the queue in chat
numbered, ask for a bulk reply, and that is the one time the turn ends on the questions.

For an inferred claim, quote it, say where it came from, and offer confirm, correct, or cut. For a
missing metric, prompt with where the number might live — dashboards, billing, retros, release
notes, incident reviews, promotion documents, a colleague. An honest "~50 tenants" beats silence.

### Answers go into the career

An answer changes **`career/kb.ttl`** — never `gaps.md` or the record, both downstream of it.

- **A round's corrections and new facts are one changeset**, one `jsk kb apply`, after
  `jsk kb show <ids>` for the `op:base`. A corrected claim comes back `inferred`; confirm it next.
- **What they confirmed**: `jsk kb confirm <ids> --answer "their words"`, which also answers the
  open questions about them.
- **Unanswerable**: soften or cut the claim in the changeset; never leave it pending forever.

## 4. Another round only if a verdict moved

Revise `gaps.md` **only when an answer changed what the career holds**. Re-run `jsk match`.

**Patch it yourself when every change is a row** — a verdict with its evidence, a ranking row from the
new match, an answered question struck. **Send it back only when the fit could change or an answer
needs a row the assessment lacks**: `SendMessage` to the same agent with what changed.

The loop ends when they skip, when nothing is left worth asking, when a round produces no new
answerable question, or at three rounds (`--rounds N` in `$ARGUMENTS` overrides). **Say which reason
ended it.**

## 5. Author, once

`jsk-resume-author` writes `resume.json`. **Resolve its paths before dispatching; it reads only what
the prompt names:**

- the application directory and the workspace — absolute paths;
- whichever of `rules/writing-rules.md`, `rules/ats-rules.md`, `rules/structure-rules.md` exist beside
  `career/` (one `ls`), or "no overrides";
- the example record: `python -c "from jsk.paths import EXAMPLE_RECORD; print(EXAMPLE_RECORD)"`.

Bullets it adds or rewords in the career arrive `inferred`, and a view with
`provenance_floor: confirmed` does not fail on them: the render drops them, shown only as `withheld …`
warnings, each confirmed or cut before the resume is handed over. **It quotes every clause back.**
**Read those quotes to the person and get confirm-correct-or-cut on each**, then
`jsk kb confirm <ids> --answer "…"` and flip them in the record. Confirm confirms the career's
current text: a bullet reworded only in the record stays `inferred` until its words are in the
career — never on the strength of the old text. This step is yours and is not delegable.

**A view references content; it cannot contain it.** If the posting wants something the career does
not have, say so out loud.

## 6. Ship

Follow `references/mode-ship.md`: `jsk ship`, the render gate, `jsk freeze`. Nothing is frozen that
failed a gate.

## 7. Tell them where they fall short

Every time, in chat, before they ask:

> "Two gaps survived. They want direct people-management — you have technical leadership and
> mentoring evidence, but nothing on hiring. And they name Terraform throughout; your IaC evidence is
> all Bicep. The resume can't claim Terraform depth you don't have."

If the fit is genuinely poor, say so.

## Cover letter, if asked

Under 250 words. Strongest match first. One concrete piece of evidence with its metric. The obvious
gap in one honest line. No enthusiasm padding.

## Running it inline

Without agents, the procedure and commands are the same: keep the advertisement before you read
anything out of it, and trust `jsk match` and `jsk validate` over your own reading.
