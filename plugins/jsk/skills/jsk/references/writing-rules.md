# Writing rules

## X-Y-Z

*Accomplished [X] as measured by [Y], by doing [Z].*

> Cut order-processing latency 62% (8.4s to 3.2s p95) by decomposing a monolithic service into six
> event-driven microservices on a message bus, serving 40K daily transactions.

Senior people rarely own revenue, so anchor Y on what they do move: latency, deployment time, defect
rate, release frequency, onboarding time, tenant count, users served, incidents avoided, cost.

**The Z position is where seniority shows.** It separates doing work from making a choice. Never drop
it.

## Verb accuracy

Match the verb to actual ownership. This survives reference checks; inflation does not.

| They said | Write |
|---|---|
| "designed and developed" | Architected and built |
| "supported in designing" | **Co-designed** |
| "I owned it end to end" | Owned |
| contributed within a team | Built / Implemented |

When you downgrade a verb, tell them why. It reads as care, not pedantry.

## Titles

An official title is evidence; it is not always information. "Member of Technical Staff",
"Client Success Associate", "Engineer IV" — each means something precise inside one company and
nothing outside it, and the reader is six seconds in.

**Bridge the gap in parentheses. Never by rewriting the title.**

| Official | Write |
|---|---|
| Member of Technical Staff | Member of Technical Staff (Full-Stack Engineer) |
| Client Success Associate | Client Success Associate (Account Manager) |
| Engineer IV | Engineer IV (Senior Backend Engineer) |
| Senior Engineer | Senior Engineer — leave it alone |

Three rules hold this honest:

- **The official title stays**, first and verbatim. It is what a reference check confirms, and
  replacing it turns a clarification into a discrepancy.
- **The gloss describes, it does not promote.** A Senior Engineer does not become "(Engineering
  Manager)" because the target role is a management one. If the functional title is a level up, that
  is not a title gap — it is a claim, and it needs the evidence any other claim needs.
- **Most titles need nothing.** Reach for this when someone outside that employer would have to
  guess. A gloss on a plain title reads as padding.

Record it as `functional_title` on the position — `urs-spec.md` — not by editing `title`.

## Cut on sight

- **"Gained experience in X" / "Acquired knowledge of Y"** — learning statements read as junior, and
  frequently understate someone who later mastered the thing. Someone who wrote "acquired knowledge
  of multi-tenant architecture" as a junior may have since architected multi-tenant platforms.
- "Responsible for" / "Worked on" / "Involved in" — activity, not achievement
- Bullets repeated across projects
- Unfinished sentences — real resumes contain these; read carefully
- Filler: "stayed current with industry trends", "passionate about technology"
- References, full home address, photo, date of birth, marital status

## Prefer

- **Name the anti-pattern removed, then the replacement.** "Replaced direct database coupling with
  publish/subscribe" beats "implemented a message bus" — it shows they diagnosed a structural
  problem.
- **Name the constraint before the solution.** Constraints are what make senior work hard; stating
  one signals they operate where requirements conflict.
- **State the why behind a mechanism** when you know it. Grounding retrieval in approved policy is a
  compliance mitigation, not a feature.
- **Approximate honestly.** "~50 tenants" beats omitting the number. Interviewers probe reasoning,
  not decimal places.

## Summaries

Open with a **claim their bullets prove**, not a job title restated. "Solution architect who builds
the platforms other teams build on" gives the reader a thesis. "Experienced architect with 11 years"
gives them nothing, and every competing resume opens that way.

Do not restate metrics that appear in bullets a few centimetres below. A number lands harder once.

A short list of hard constraints they have worked under — data-sovereignty law, multi-tenant SLAs,
offline-tolerant field operations — does more in one line than a paragraph of adjectives.
