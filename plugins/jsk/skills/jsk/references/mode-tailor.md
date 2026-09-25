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

**Before the posting is written down:**

```bash
ls <workspace>/applications/ | grep -i "<company>"
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

Create `<workspace>/applications/<stem>/` and write `posting.md`: **the advertisement verbatim and
nothing else**, the URL on its first line. **Never paraphrase it** — the archive has to say what the
application was answering, and every requirement quotes it.

## 2. Assess

Send `jsk-tailor-analyst` the application directory. It writes `posting.ttl`, runs `jsk match`, and
writes `gaps.md` from the match. It never touches `career/kb.ttl`.

**Show them the assessment**, not a summary of it. **Stop before anything is authored** when: the
ranking is close between projects with materially different ownership verbs, a top-ranked project
carries unconfirmed content, eligibility fails, or the role may not be worth applying to at all.

## 3. Ask the whole queue at once

Present the ordered queue and take a bulk reply. Then go one at a time **only** for answers that came
back ambiguous, incomplete, or contradicting the career. **Offer the skip every round.**

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

New bullets it adds to the career arrive `inferred`, so a view with `provenance_floor: confirmed`
fails until a person confirms. **It quotes every clause back.** **Read those quotes to the person and
get confirm-correct-or-cut on each**, then `jsk kb confirm` the confirmed ids and flip them in the
record. This step is yours and is not delegable.

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
