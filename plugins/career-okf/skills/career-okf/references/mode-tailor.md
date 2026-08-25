# Mode: tailor

Score evidence against a specific posting, then generate. Read `references/mode-resume.md` for
generation and verification; this adds the selection logic in front.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` concept. If the posting wants something they have not done,
say so — do not manufacture a bullet. Anything `inferred` needs confirmation before it appears.

Not only ethics: someone who bluffs past a screen gets found out in the first technical conversation,
having burned both the opportunity and their credibility.

## Steps 1 and 2 delegate

Decomposing a posting and scoring a bundle against it is reading and arithmetic — hand both to
`career-okf-posting-analyst`, with the posting, the bundle path and this skill's directory. It writes
the target file, runs the scorer, and returns the ranking, the unmatched requirements and the PAUSE
flags below.

What it returns is not what the person sees. **Surface the top few and the surprises in chat
yourself**, in your own words, and act on the flags. Step 6 is yours and is not delegable.

The procedure is written out below because it is the same procedure inline, where no agent is
available.

## 1. Decompose the posting

Extract, in priority order: **required capabilities**, **required technologies**, **domain**,
**seniority signal**.

**Notice what it says twice.** Repetition marks the real priority, and it is often not the first
bullet. A posting mentioning stakeholder management in three places is telling you something the
responsibilities list buries.

Save to `tailoring/targets/<company>-<role>.md` with the posting pasted verbatim — listings get taken
down and they will want the text at interview. Use `references/target-template.md`: the requirement
sets go in the **frontmatter**, because that is what the scorer reads. A requirement written only in
prose does not participate in the ranking.

**Write the target file — posting, ranking and gaps — before generating anything.** Not the posting
now and the ranking later: the file is the checkpoint, and a checkpoint written after the work is
finished is a record, not a check. Step 2 fills its `# Evidence ranking` and `# Gaps` sections —
both from the scorer's unmatched lists — and both belong in the file before the first bullet is
written. Step 6 is where you *tell* them the gaps; this is where you *record* them.

## 2. Score every project

```bash
python3 <skill-dir>/scripts/score_projects.py <bundle> tailoring/targets/<company>-<role>.md
```

```
score =  capability_overlap x 3     # primary axis, a count
       + technology_overlap x 2     # a count
       + domain_match       x 2     # binary: any shared domain, or none
       + seniority_match    x 2     # 0.0-1.0, see the scale below
       + strength                   # 1-5
       + recency_bonus              # +2 within 3 years, +1 within 6
```

Overlap counts matching frontmatter array values, compared exactly against
`framework/capability-vocabulary.md`. Run the script rather than scoring by feel or writing a
throwaway scorer: a bespoke one re-declares the requirement sets in Python, they drift from the
frontmatter within the session, and the ranking stops being reproducible a month later.

**`seniority_match` is a graded scale**, not a yes/no: 1.0 at or above the level sought, decaying
linearly to 0.0 at `junior`. Evidence from a *more* senior engagement than the posting asks for is not
worth less — the penalty is for falling short, not for overshooting.

**`domain_match` is binary.** Any shared domain scores the full 2; none scores 0. Multiplying a count
would reward concepts that happen to carry more domain tags, which is a tagging artefact rather than
a signal.

**When the posting names no technologies at all** — common in enterprise architecture roles — leave
`required_technologies` empty. The term then contributes 0 to every project and cannot change the
ranking, which is the honest outcome. Do not quietly score against the stack the posting *implies*:
that invents a requirement and moves a x2 term. If it is worth exploring, pass
`--assume-technologies`, which labels the assumption in the output where a reader can see it.

**The unmatched list is as useful as the score.** A required capability a project does not carry is
either evidence that is genuinely absent or a project that is under-tagged. Those need opposite
responses and only the person whose work it was can tell you which — so show them.

### Save the ranking, surface the surprises, continue

**Do not block waiting for a reply**, and do not leave the ranking for the final response either.
Both readings fail: one stalls a job application on a question the person may answer tomorrow, and
the other delivers the table alongside the finished resume, after every generation decision has
already been taken. The correction window the ranking exists to create never opens.

Make the **artefact** the checkpoint instead:

```bash
python3 <skill-dir>/scripts/score_projects.py <bundle> <target.md> --markdown
```

Paste that under `# Evidence ranking` in the target file, then in chat surface the top few and
anything surprising — a project that moved a long way, a top rank you did not expect. Then carry on.
The reasoning is durably inspectable, they can correct it at any point, and nothing waits.

**Do pause before generating** in these cases, where being wrong is expensive enough to be worth the
wait:

- The ranking is **close between projects with materially different ownership verbs** — "architected"
  against "contributed to" is not a detail that can be fixed after the fact
- A top-ranked concept carries **`status: inferred`** content that would reach the resume. The
  provenance rule already requires confirmation; this is where it lands
- The gap analysis suggests **the role may not be worth applying to at all**. That decision is theirs
  and it comes before the work, not after it

## 3. Allocate two pages

| Rank | Treatment |
|---|---|
| 1-2 | Full treatment, 3-5 bullets, lead the section |
| 3-5 | One or two bullets each |
| 6-8 | Compressed, shared role headers |
| 9+ | Cut, or one line if chronology needs it |

**Chronology still governs order.** A high-scoring old project earns more bullets, not an earlier
position. Reordering roles by relevance reads as concealment and breaks date parsing.

**Score governs allocation, and a recency ratio is a default rather than a constraint.**
`bundle-spec.md` weights roughly 4:1 toward recent roles, and a bundle's own
`resume-generation/structure-rules.md` may set its own ratio. When the posting's best-matching
evidence sits mid-career, those two rules pull against each other — and the resolution is that the
ratio yields. It exists to stop a resume dwelling on work from a decade ago for no reason; it is not
a reason to bury the evidence this particular posting is asking for. Say in chat when you have
departed from the ratio and why, so the decision is visible rather than felt.

## 4. Retune the top

Summary: keep the opening claim, swap evidence clauses for the posting's top two capabilities, mirror
its exact vocabulary. Skills: move the matching stack row to second position.

## 5. Generate, verify, log

**Tailoring is a view, not a new document.** Add one to `resume.json` naming the evidence the ranking
chose, and render from it:

```json
{ "id": "view_acme_principal",
  "format_profile": "ats-maximal",
  "region_profile": "urs:profile:au/1",
  "target": { "title": "Principal Solution Architect", "ref": "tailoring/targets/acme.md" },
  "narrative": "nar_acme",
  "include": [
    { "ref": "eng_meridian", "order": 1, "achievements": ["ach_latency", "ach_consolidate"] },
    { "ref": "eng_northbridge", "order": 2, "treatment": "brief" }
  ],
  "provenance_floor": "confirmed",
  "budget": { "pages": 2 } }
```

```bash
python3 <skill-dir>/scripts/validate_urs.py resume.json
python3 <skill-dir>/scripts/render_resume.py resume.json --out . --view view_acme_principal --pdf
```

**A view references content; it cannot contain it.** The validator rejects free text inside one. That
is the structural expression of the rule at the top of this file: a tailored resume is a selection
over evidence that already existed, and a format where invention is impossible beats a process where
invention is merely discouraged. If the posting wants something the record does not have, the view has
nothing to point at — which is the honest outcome, and the thing to tell them in step 6.

Retuned prose — a summary written for this posting, a bullet re-emphasised — is a **new narrative or a
new achievement in the record**, with its own `provenance`. Written there, it is reviewable, reusable
and attributable. Written into the view, it would be none of those, which is why it is rejected.

Save the tailored record as `tailoring/applications/<company>-<role>.resume.json`. Every previous
application then remains reproducible: same record, same view, same output, a year later.

Then the gates. `check_ats.py` PASSes on both variants — plain and `--strict` — and `check_prose.py`
PASSes on the presentation variant and the plain text. Tailoring rewrites bullets against a posting,
which is exactly when a rewritten clause loses its object or slips into the third person, so the prose
gate matters more here than in a straight rebuild. And because a rewritten bullet is where a number
drifts, `validate_urs.py` re-checks every numeral against its metric before anything renders.

Log the submission in `tailoring/applications/` — including any feedback received later. After a
handful of applications, patterns emerge about which evidence gets traction, and that belongs back in
the rules.

## 6. Tell them where they fall short

Every time, in chat, before they ask.

> "Two gaps. They want direct people-management — you have technical leadership and mentoring
> evidence, but nothing on hiring or performance reviews. And they name Terraform throughout; your
> IaC evidence is all Bicep. The concepts transfer and you could say so in interview, but the resume
> can't claim Terraform depth you don't have."

A named gap can be prepared for, addressed in a cover letter, or used to decide the role is not worth
applying to. That decision is theirs and needs real information. If the fit is genuinely poor, say so.

## Cover letter, if asked

Under 250 words. Strongest capability match first. One concrete piece of evidence with its metric.
Address the obvious gap in one honest line rather than hoping nobody notices. No enthusiasm padding.
