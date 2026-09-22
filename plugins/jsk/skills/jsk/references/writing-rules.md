# Writing rules

## X-Y-Z

*Accomplished [X] as measured by [Y], by doing [Z].*

> Cut order-processing latency 62% (8.4s to 3.2s p95) by decomposing a monolithic service into six
> event-driven microservices on a message bus, serving 40K daily transactions.

Senior people rarely own revenue, so anchor Y on what they do move: latency, deployment time, defect
rate, release frequency, onboarding time, tenant count, users served, incidents avoided, cost.

**Z is where seniority shows** — the choice, not just the work. Never drop it.

## Verb accuracy

Match the verb to actual ownership; it survives reference checks.

| They said | Write |
|---|---|
| "designed and developed" | Architected and built |
| "supported in designing" | **Co-designed** |
| "I owned it end to end" | Owned |
| contributed within a team | Built / Implemented |

When you downgrade a verb, tell them why.

## Titles

**Bridge an internal-only title in parentheses. Never rewrite the title.**

| Official | Write |
|---|---|
| Member of Technical Staff | Member of Technical Staff (Full-Stack Engineer) |
| Client Success Associate | Client Success Associate (Account Manager) |
| Engineer IV | Engineer IV (Senior Backend Engineer) |
| Senior Engineer | Senior Engineer — leave it alone |

- **The official title stays**, first and verbatim — it is what a reference check confirms.
- **The gloss describes, it does not promote.** A functional title a level up is a claim, and needs
  the evidence any claim needs.
- **Most titles need nothing.** Gloss only where an outsider would have to guess.

Record it as `functional_title` on the position (`urs-spec.md`), not by editing `title`.

## Cut on sight

- **"Gained experience in X" / "Acquired knowledge of Y"** — reads as junior, and often understates
  someone who later mastered the thing.
- "Responsible for" / "Worked on" / "Involved in" — activity, not achievement
- Bullets repeated across projects
- Unfinished sentences — real resumes contain these; read carefully
- Filler: "stayed current with industry trends", "passionate about technology"
- References, full home address, photo, date of birth, marital status

## Prefer

- **Name the anti-pattern removed, then the replacement.** "Replaced direct database coupling with
  publish/subscribe" beats "implemented a message bus".
- **Name the constraint before the solution.**
- **State the why behind a mechanism** when you know it. Grounding retrieval in approved policy is a
  compliance mitigation, not a feature.
- **Approximate honestly.** "~50 tenants" beats omitting the number.

## Summaries

Open with a **claim their bullets prove**, not a job title restated. "Solution architect who builds
the platforms other teams build on" is a thesis; "Experienced architect with 11 years" is not.

Do not restate metrics that appear in the bullets below.

A short list of hard constraints they have worked under — data-sovereignty law, multi-tenant SLAs,
offline-tolerant field operations — does more in one line than a paragraph of adjectives.
