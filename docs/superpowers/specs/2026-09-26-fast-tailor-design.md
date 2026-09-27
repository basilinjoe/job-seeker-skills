# Fast tailor: a posting to a shipped resume in under five minutes

**Status:** proposal, 2026-09-26. Not yet reviewed.
**Builds on:** `jsk match` (`2026-09-24-graph-match-design.md`), `jsk kb export --from-match`
(`2026-09-25-export-from-match-design.md`), the `jsk-tailor-analyst` and `jsk-resume-author`
agent definitions, and `references/mode-tailor.md`.

## The goal

From `/jsk:tailor <url>` to a gated PDF in **under five minutes of machine time**. The person's
time answering questions is not counted, but the run should ask them as early as possible so
their answering overlaps the machine's work.

## What the last run measured

The JumpCloud run (Staff SWE, PAM, 2026-09-26) is the baseline. Its timeline was reconstructed
from the session transcript and the analyst subagent's transcript.

| Phase | Wall time | What happened |
|---|---|---|
| Main session: skill load, procedure read, fetch, dispatch | 31s | `jsk posting fetch` itself took about 4s |
| Analyst: `kb path`, read posting, `query concepts` | 8s | tools |
| **Analyst: write `posting.ttl`** | **225s** | **one turn, 26.5k output tokens for a 15 KB file** |
| Analyst: fmt, check, 5 `advert-uncovered` WARNs, 5 edits, recheck | 55s | caused by a check bug (§0) |
| Analyst: match, evidence, person, 2× `kb show`, unconfirmed | 227s | tools about 2s each; the rest was silent reasoning (53s and 128s turns) |
| **Analyst: write `gaps.md`** | **105s** | **11.8k output tokens for a 17 KB file** |
| Analyst: reread, renumber, `--gaps` validation, 2 WARNs, fix, rerun | 41s | cleanup |
| **Analysis total** | **~11 min** | the run then stopped: the person answered "Stop here" |

Two figures set the budget:

- **Output speed is about 118 tokens per second.** Five minutes buys about **35k output tokens
  for the whole run**, reasoning included. The analyst alone used more than 40k.
- **Tool calls are not the cost.** Every `jsk` call returned in 1–3 seconds. The time goes to
  tokens the model writes, and to reasoning between calls.

**The principle that follows:** every token the model writes that code could write is time.
The model should decide; code should write.

### Why the output was so large

The posting has 5 qualification bullets and 10 responsibility bullets. The analyst produced
**41 requirements, all `j:required`**:

- **Lines were split finely.** "Core Tech Stack" became 6 requirements; the PAM line became 4.
- **Some requirements are duplicates.** ABP appears as both `abp_framework` and
  `dotnet_aspnet`; incident management as both `incident_management` and
  `oncall_participation`.
- **Internal tool names became requirements.** Origin CI, Kargo and WoK are JumpCloud tools
  nobody outside the company could have used.
- **Responsibilities were marked `required`.** The analyst definition says "when the advert does
  not say, `j:implicit`", and the coverage rule itself excludes responsibility sections as not
  asked of the person (`rules.py:197-204`). But the definition also says "every other line the
  advert asks gets one" (`jsk-tailor-analyst.md:73-75`), with no guidance on how finely to split
  a line or how to treat responsibilities.

Every requirement costs Turtle in `posting.ttl`, a row in `gaps.md` with a verdict and a
shortfall, and reasoning about both. The requirement count drives the run's length.

---

## §0. Fix first: the `advert-uncovered` punctuation bug

`uncovered()` (`src/jsk/graph/rules.py:257-258`) strips trailing punctuation from the advert
line but not from the quote:

```python
low = line.casefold().rstrip(".;, ")
if not any(q in low or low in q for q in said):
```

A quote of a bullet's body ending in a period ("12+ years … environments.") is then never
found in the stripped line, and the check warns although the line is covered. Reproduced: the
same quote passes without its final `.` and fails with it. Only qualification lines hit it,
because responsibility sections are not checked.

**Fix:** apply the same `rstrip(".;, ")` to each quote when `quotes` is built. **Test:** a
posting whose bullet is `- Experience: 12+ years of X.` with a requirement quoting `12+ years
of X.` raises no `advert-uncovered`.

This is small, certain, and costs about a minute on every run. §1A later removes the whole
class of failure, but the fix should land now.

---

## §1. Code writes the structure; the model only decides

### A. `jsk posting extract` and `jsk posting build`

**Problem.** Writing `posting.ttl` by hand means the model writes, for every requirement: the
subject id, four predicates, the `j:asked` term, and the full `j:quote` copied character for
character. Most of that is mechanical, and the verbatim copying is exactly what the checks
then police.

**Design.** Split the step into three parts: code extracts, the model decides, code writes.

**1. `jsk posting extract APP` lists the advert's asks.** It prints every candidate line,
numbered, with its section and a flag:

```
# Staff Software Engineer, PAM / PWM - India at JumpCloud
# seniority hint: staff -> architecture-ownership
n   section         flag   line
1   responsibility         Architectural Ownership: Own the end-to-end technical vision and ...
...
15  qualification          Experience: 12+ years of progressive software development experience, ...
17  qualification          Core Tech Stack: Advanced proficiency in C#, .NET (ABP framework), Go, ...
21  other           elig   To be considered for a role at JumpCloud, you will be required to ...
```

- **It reuses `asked_lines()`**, widened to return responsibility items too, each tagged with
  its section.
- **It flags eligibility** with the existing `ELIGIBILITY` pattern.
- **It lists concepts whose labels appear in each line (see §1B)**, so the model rarely needs
  the 18 KB concept list.
- **Prose paragraphs** that are not list items are listed under `other`, so an ask buried in a
  paragraph is still visible.

**2. The model writes a decisions file**, one line per requirement:

```
# n  slug              asked                         concept          need
17   csharp            C#                            c:csharp         required
17   golang            Go                            c:golang         required
17   grpc              gRPC                          -                required
18   pam_tools         CyberArk, BeyondTrust, Vault  -                required
12   -                 (drop: internal tooling - Origin CI, Kargo, WoK)
2    anchor_squads     primary technical anchor      c:cross-team-influence  implicit
21   -                 (eligibility)
```

A line may yield several requirements; a line may be dropped only with a stated reason. At
about 20 tokens a row, 41 rows is roughly 1k tokens, against 26.5k last time.

**3. `jsk posting build APP DECISIONS` writes `posting.ttl`** in canonical layout:

- **`j:quote` is the extracted line itself**, never model text, so `quote-verbatim` and
  `advert-uncovered` cannot fail by construction.
- **It refuses** an `asked` that does not appear in its line (case-insensitive), a concept that
  does not exist, and an unused line with no drop reason.
- **It defaults `need` from the section.** A qualification line is `required` unless the line
  carries optional wording (`OPTIONAL_WORDS`). A responsibility line is `implicit`. The model
  may override; an override that promotes a responsibility to `required` needs required wording
  in the line (`REQUIRED_WORDS`), or the build WARNs. This enforces "never promote a guess to
  required" in code instead of prose.

**Rules for splitting, stated in the analyst definition:**

- One requirement per term the match can score: a technology, a practice, a capability.
- Alternatives ("AWS/GCP") stay one requirement with a concept each, as now.
- Company-internal names (tools, frameworks nobody outside could have used) are dropped with a
  reason. They are still listed in `gaps.md` under "New terms" if the person might know an
  equivalent.
- The same ask in two lines is one requirement, quoting the qualification line.
- **A soft cap of 20 requirements.** The build WARNs past it: the posting is being over-split,
  or it really is that long and the person should hear so.

**Expected saving:** about 3.5 minutes, plus the 55-second fix-and-recheck loop.

### B. Code proposes the concepts

**Problem.** The analyst reads every concept (`jsk kb query concepts`, 18 KB) and reasons
through the mapping for all 41 requirements.

**Design.** The label and alias index `match` already uses is run over each extracted line.
`extract` prints the concepts found in the line, and the model accepts, removes or adds. For a
term the index does not recognise, the model asks `jsk kb query concepts --near <term>` for the
nearest few instead of reading the whole list. The existing `candidate` bucket of `match`
already reports new terms, so a wrong "no concept" costs nothing: the match reports the term.

**Expected saving:** most of the reasoning inside the 225-second turn, and the 18 KB read.

### C. `jsk match --draft-gaps`: code writes gaps.md, the model writes the prose

**Problem.** Most of `gaps.md` is a transcription of what `jsk match` already printed: the
requirements table with default verdicts and evidence ids, the Ranking, the Cover, and the
match's questions. The model rewrote all of it (11.8k tokens) and then had to fix the rows the
validator could not tie back to a requirement.

**Design.** `jsk match POSTING.ttl --draft-gaps GAPS.md` writes the file with every mechanical
part filled in and a marked slot wherever judgement is needed:

```markdown
---
type: Gap Assessment
posting: posting.ttl
assessed: 2026-09-26
fit: <!-- jsk: strong | partial | poor -->
---

# Eligibility

<!-- jsk: judge against these facts
  location: Kochi, Kerala, IN (confirmed)
  work authorization: <each row of `jsk kb query person`, with its provenance>
  advert: "Bangalore, India - Remote"; "speak and write in English fluently" -->

# Requirements

| Requirement | Need | Verdict | Evidence | Shortfall |
|---|---|---|---|---|
| C# | required | satisfied | prj_unitng | |
| gRPC | required | unsatisfied | | <!-- jsk: shortfall --> |
...

# Ranking
<as printed>

# Where this falls short
<!-- jsk: the unmet and partial requirements that matter, most load-bearing first -->

# Surplus worth knowing about
<!-- jsk: optional -->

# New terms
- **ABP Framework** — `candidate`: no concept holds it.

# Questions
<the match's questions, in the order blocking, unmet, unconfirmed, missing metric, unexplored>
<!-- jsk: reword each to be said aloud; add from `jsk kb query unconfirmed` -->
```

The model fills the slots with `Edit`, and may lower a verdict with a reason. `--gaps`
validation refuses a file that still holds a `<!-- jsk:` marker, so an unfilled slot is a FAIL,
not something the reader finds.

**Expected saving:** about 1.5 minutes of writing, plus the 41-second cleanup loop, since rows
come from the requirement ids and cannot drift from them.

---

## §2. Fewer model turns

### D. `jsk tailor prepare APP`: one digest instead of ten calls

**Problem.** Between writing `posting.ttl` and writing `gaps.md` the analyst made about ten tool
calls. Each costs a model turn, and the turns carried long silent reasoning (53s, 128s).

**Design.** One command, in one process, printing one compact digest:

1. `jsk kb fmt` on `posting.ttl`.
2. **A check scoped to this application.** Last run's full check printed 40 KB of warnings from
   other applications. `jsk kb check --only applications/<stem>` (new) reports only findings
   whose file is under that path, plus any FAIL anywhere (a FAIL still stops the match).
3. `jsk match`, as printed.
4. `jsk kb query evidence` for every `missing` and `candidate` term, in one call.
5. `jsk kb query person`.
6. `jsk kb show --bullets` for the top-ranked projects the Cover names, capped at a fixed number.
7. `jsk kb query unconfirmed`, limited to entries those projects hold.
8. With `--draft-gaps`, the draft of §1C.

Every section has a size cap and says when it was cut. The analyst's procedure becomes:
`extract` → decisions → `build` → `prepare --draft-gaps` → fill slots → `match --gaps`. That is
about six turns in place of about twenty.

**Expected saving:** most of the 227-second evidence phase.

### E. Less reasoning where the work is now a form

Once §1 and §2 exist, the analyst's work is filling in a form with judgement, not designing
the form. Options, to measure rather than assume:

- **Lower reasoning effort** for the analyst, if agent frontmatter supports setting it.
  Otherwise, say in the definition that the decisions file and the slots are the whole output.
- **Split by model:** Haiku 4.5 for the decisions file (concept mapping and splitting, with §1B's
  proposals in front of it), Sonnet for the gaps prose. It has to be checked against a corpus
  first (§6).

### F. Run the analysis inline for short postings

The subagent starts cold: its definition, the posting and the concept list are a 14k-token cache
write before it does anything, and its report has to be relayed back. Once the model's part is
small, the main session, which already holds the posting, may be faster doing it itself.
`mode-tailor.md` already has "Running it inline". Keep the subagent for long postings, where
keeping the main context clean matters. Decide by measurement, not now.

---

## §3. Stop early, overlap the rest

### G. Triage before the analyst runs

**Problem.** The JumpCloud run spent 11 minutes to reach the question "you have nothing on PAM,
continue?", and the answer was "Stop here". `jsk kb query evidence PAM CyberArk SCIM …` answers
that in 2 seconds.

**Design.** A new step in `mode-tailor.md` between "Get the posting" and "Assess":

1. From the title and the first qualification lines, pick the 2–5 load-bearing terms (the
   title's domain first).
2. Run `jsk kb query evidence <terms>` and `jsk kb query person` in one message.
3. **If a title term comes back `nothing`**, or eligibility plainly fails, ask the person whether
   to continue, stating what is missing, before dispatching.

It could become `jsk tailor triage APP --terms …`, but the two existing queries are enough to
start. JumpCloud would have stopped about 35 seconds in.

### H. Run independent steps at once

The fetch, `query person`, the duplicate-application check and `query unconfirmed` do not depend
on each other. The main session should issue them in one message. This saves little on its own,
but it is free.

### I. Ask while the analyst works

When triage passes but raises a doubt, dispatch the analyst **in the background** and ask the
triage question at the same time. If the person says stop, stop the agent. If they say go, the
analysis is already under way. The person's answer then overlaps the machine's work instead of
following it.

### J. One round of questions

Already the rule ("Ask the whole queue at once", `mode-tailor.md` §3). Keep it. One
AskUserQuestion call carries up to 4 questions; a longer queue goes in as few calls as possible,
blocking questions first.

---

## §4. The resume stage

### K. What is left for the resume author

Selection is already code: `jsk kb export --from-match` chooses projects, bullets, order and
skills (`2026-09-25-export-from-match-design.md`). What the author still writes:

- one changeset of reworded or new bullets;
- the retuned summary;
- the quotes read back to the person.

To keep that inside the budget:

- **Reword only where the posting's own words fit better**, and only among the bullets the
  export selected. Say in the definition that a bullet that already scores stays as it is.
- **Pass the author the digest §2D already made**, so it does not re-read what the analyst read.
  The definition already forbids re-running `match`; it could also take the `kb show` output
  from `prepare` instead of calling it again.
- **`jsk ship`** is deterministic. Its time (render plus gates) has not been measured on this
  machine and should be before it is budgeted.

---

## §5. The budget

Machine time only; the person's answering is excluded. **These are estimates** from last run's
token counts and tool timings, not measurements.

| Step | Last run | Target | From |
|---|---|---|---|
| Fetch, triage, parallel queries | 31s | ~30s | G, H |
| Requirements (`extract` → decisions → `build`) | 280s | ~40s | 0, A, B, E |
| Evidence digest (`prepare`) | 227s | ~15s | D |
| `gaps.md` (draft, fill slots, validate) | 146s | ~50s | C |
| Resume author (changeset, export, summary, validate) | not reached | ~60s | K |
| Ship (render, gates, freeze) | not reached | ~30s, unmeasured | — |
| **Total** | **~11 min, analysis only** | **~4 min, end to end** | |

On a posting that fails triage the run takes about 35 seconds.

---

## §6. Risks and how to check them

- **Extraction misses an ask.** An ask written as a paragraph, or under an odd heading, may not
  be a list item. Mitigation: `extract` lists `other` lines too. The decisions file may add a
  requirement from any line, and the quote is still the extracted line, so it stays verbatim.
- **Coarser requirements match less.** Merging duplicates and dropping internal tools must not
  hide a real ask. Mitigation: every drop carries a reason that appears in `gaps.md`, so the
  person sees what was dropped.
- **Slots filled badly.** Moving the prose into slots could make `gaps.md` terser than the person
  needs. Mitigation: the slot text says what each section is for, the same as the current
  template does.
- **Haiku maps concepts wrongly.** Measure before adopting (E).

**A regression corpus exists.** The postings already under `career/applications/` (JumpCloud,
Nagarro, Qatar Airways and the rest) each have a hand-reviewed `posting.ttl` and `gaps.md`.
Replaying the new procedure over them compares:

- requirement counts;
- concepts chosen;
- verdicts;
- wall time per phase.

Wall time comes from the transcripts: the timeline method used for this document (timestamps
and per-turn output tokens from the session and subagent `.jsonl` files) could become a small
script under `docs/superpowers/experiments/`.

---

## §7. Order of work

1. **§0, the punctuation bug**, with its test. Minutes; lands on its own.
2. **§3G, triage**, as a change to `mode-tailor.md` only. No code. It stops a bad fit in 35
   seconds from the next run on.
3. **§1A and §1B, `posting extract` and `posting build`**, plus the splitting rules in the
   analyst definition. The largest saving, and it removes a whole class of check failure.
4. **§1C, `--draft-gaps`**, and the marker check in `--gaps` validation.
5. **§2D, `tailor prepare`**, including `kb check --only`.
6. Measure against the corpus. Then decide E (effort and model), F (inline or subagent) and K
   (the author's inputs) from the numbers.

## Open questions

- **Decisions file format.** Whitespace columns (short, but a model can misalign them) or JSON
  lines (longer, unambiguous)? The build validates either; it only affects how many tokens the
  model spends.
- **Does a responsibility line ever deserve `required`?** "You will own on-call" is a condition
  of the job, not a skill. The proposal defaults it to `implicit` and WARNs on promotion; it
  could be stricter.
- **Is 20 the right soft cap**, or should it scale with the number of qualification lines?
- **Should `prepare` exist as a command, or only as a documented sequence?** A command is faster
  (one turn) but is one more surface to maintain.
