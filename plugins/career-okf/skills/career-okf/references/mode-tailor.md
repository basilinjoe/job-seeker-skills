# Mode: tailor

Score evidence against a specific posting, then generate. Read `references/mode-resume.md` for
generation and verification; this adds the selection logic in front.

## The one rule

**Tailoring is selection and emphasis. It is never invention.**

Every claim must trace to a `confirmed` concept. If the posting wants something they have not done,
say so — do not manufacture a bullet. Anything `inferred` needs confirmation before it appears.

Not only ethics: someone who bluffs past a screen gets found out in the first technical conversation,
having burned both the opportunity and their credibility.

## 1. Decompose the posting

Extract, in priority order: **required capabilities**, **required technologies**, **domain**,
**seniority signal**.

**Notice what it says twice.** Repetition marks the real priority, and it is often not the first
bullet. A posting mentioning stakeholder management in three places is telling you something the
responsibilities list buries.

Save to `tailoring/targets/<company>-<role>.md` with the posting pasted verbatim — listings get taken
down and they will want the text at interview.

## 2. Score every project

```
score =  capability_overlap x 3     # primary axis
       + technology_overlap x 2
       + domain_match       x 2
       + seniority_match    x 2
       + strength                   # 1-5
       + recency_bonus              # +2 within 3 years, +1 within 6
```

Overlap counts matching frontmatter array values, compared exactly against
`framework/capability-vocabulary.md`.

**Show the ranked table before writing anything.** It makes your reasoning inspectable and lets them
correct you — they know which project was really the hard one.

## 3. Allocate two pages

| Rank | Treatment |
|---|---|
| 1-2 | Full treatment, 3-5 bullets, lead the section |
| 3-5 | One or two bullets each |
| 6-8 | Compressed, shared role headers |
| 9+ | Cut, or one line if chronology needs it |

**Chronology still governs order.** A high-scoring old project earns more bullets, not an earlier
position. Reordering roles by relevance reads as concealment and breaks date parsing.

## 4. Retune the top

Summary: keep the opening claim, swap evidence clauses for the posting's top two capabilities, mirror
its exact vocabulary. Skills: move the matching stack row to second position.

## 5. Generate, verify, log

Both variants plus plain text, both checkers PASS, then log the submission in
`tailoring/applications/` — including any feedback received later. After a handful of applications,
patterns emerge about which evidence gets traction, and that belongs back in the rules.

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
