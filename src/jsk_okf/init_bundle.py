#!/usr/bin/env python3
"""Create an empty OKF career bundle skeleton.

Usage: python3 init_bundle.py <path> --name "Full Name"

On Windows use `python` or `py -3` in place of `python3`.

Creates directories and index files. Standard library only. The scripts and rule
files stay with the jsk skill; this only creates the bundle. Populate the
concepts afterwards by interviewing the person.
"""
import os, sys, argparse, datetime


from . import pipeline_model
from .authoring import concept

BUNDLE_REVISION = 7   # keep in step with CURRENT_REVISION in migrate_bundle.py

DIRS = ["profile","organisations","roles","projects","achievements","skills","education",
        "open-source","sources","framework","resume-generation","tailoring",
        "tailoring/targets","tailoring/applications"]

BLURB = {
 "profile":"Identity, positioning, career progression and communication preferences.",
 "organisations":"One concept per employer.",
 "roles":"One concept per job title held.",
 "projects":"One concept per engagement or product. This is the evidence a resume is built from.",
 "achievements":"Collected quantified outcomes.",
 "skills":"Grouped competency taxonomy used as the keyword block.",
 "education":"Degrees and certification status.",
 "open-source":"Public code and independent projects.",
 "sources":"Archived source documents and interview records.",
 "framework":"Schema, vocabularies, templates and scripts for extending this bundle.",
 "resume-generation":"Rules governing how this bundle renders into a resume, plus "
                     "record.json - the standing URS transcription everything else reads.",
 "tailoring":"Turning a job description into a targeted resume.",
 "tailoring/targets":"Captured job postings, and the gap analysis of each against "
                     "your record.",
 "tailoring/applications":"Submissions, evidence selected, and outcomes, in one "
                          "directory per submission year.",
}

# What the archive looks like once something has been sent. Written into the index
# rather than mkdir'd as an empty `<year>/`: a year directory with nothing in it is a
# directory git will not even carry, and it would claim an application that never was.
APPLICATIONS_INDEX = """# Layout

One directory per submission year, created the first time something is sent that year:

```
2026/
  index.md
  2026-03-04-acme-engineer.md          the log: what was sent, what came back
  2026-03-04-acme-engineer.posting.md  the advertisement, frozen
  2026-03-04-acme-engineer.gaps.md     the assessment it answered, frozen
  2026-03-04-acme-engineer.view.md     the view it rendered from
  Your_Name_Acme_Resume.pdf            the files actually sent
```

The year is what the archive partitions on because it is immutable and already in the
stem. An outcome is not: it is derived from the application's `# Timeline`.

# Years
"""

def fm(t, title, desc, ts, extra=None):
    """The scaffolder's frontmatter. The emitter is the write layer's; this only
    orders the keys the scaffolder always writes ahead of the ones it sometimes
    does - the revision stamp on the root index, `status: needs-verification` on
    every concept a person still has to fill in.
    """
    keys = {"title": title, "description": desc, "timestamp": ts}
    keys.update(extra or {})
    return concept.frontmatter(t, keys) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--name", default="Your Name")
    a = ap.parse_args()
    root, name = a.path, a.name
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = ts[:10]

    if os.path.exists(root) and os.listdir(root):
        print(f"refusing to overwrite non-empty directory: {root}"); return 1

    for d in DIRS:
        os.makedirs(os.path.join(root, d), exist_ok=True)
        slug = d.split("/")[-1].replace("-", " ").title()
        body = (APPLICATIONS_INDEX if d == "tailoring/applications"
                else "Empty. Add concepts here.\n")
        with open(os.path.join(root, d, "index.md"), "w", encoding="utf-8") as f:
            f.write(fm("Index", slug, BLURB.get(d, slug), ts) + body)

    with open(os.path.join(root, "index.md"), "w", encoding="utf-8") as f:
        # The layout revision, stamped once, on the bundle root only. migrate_bundle.py
        # reads it to know what shape a bundle is in; an absent stamp means r1, because
        # every bundle created before the stamp existed predates it.
        f.write(fm("Index", f"{name} - Career Knowledge Bundle",
                   "Portable career knowledge base: roles, projects, evidence and resume rules.", ts,
                   extra={"okf_bundle": BUNDLE_REVISION}))
        f.write(f"""# Purpose

Everything needed to regenerate a resume, LinkedIn profile or interview brief for {name} without
starting over. **The bundle is the source of truth. A resume is one rendering of it.**

# Map

| Area | Entry |
|---|---|
| New here | [getting-started.md](getting-started.md) |
| Who they are, target role | [profile/](profile/index.md) |
| Employers | [organisations/](organisations/index.md) |
| Job titles held | [roles/](roles/index.md) |
| The evidence | [projects/](projects/index.md) |
| Verified numbers | [achievements/](achievements/index.md) |
| Skills taxonomy | [skills/](skills/index.md) |
| Education | [education/](education/index.md) |
| Public code | [open-source/](open-source/index.md) |
| Source documents | [sources/](sources/index.md) |
| Extending this bundle | [framework/](framework/index.md) |
| Rendering rules | [resume-generation/](resume-generation/index.md) |
| Targeting a job | [tailoring/](tailoring/index.md) |
| History | [log.md](log.md) |

# Provenance

Every concept carries `status`: `confirmed` (they said it, or it is in a source document),
`inferred` (written during drafting, unverified), or `needs-verification` (a known gap).

Nothing marked `inferred` should reach a resume without being confirmed first.
""")

    with open(os.path.join(root, "getting-started.md"), "w", encoding="utf-8") as f:
        f.write(fm("Guide", "Getting started", "What this bundle is and how to use it.", ts))
        f.write("""# What this is

A career knowledge base — facts, evidence and rules in one folder — so a resume can be regenerated
any time without starting over. Plain Markdown: readable in any editor, versionable in Git, readable
by AI tools with no translation layer.

# Using it

The `jsk` skill has seven modes. Say what you want; it routes.

| Mode | Use when |
|---|---|
| `setup` | First time, or importing an old resume |
| `braindump` | You have something to say about your work |
| `resume` | You need a resume — two verified variants plus plain text |
| `tailor` | You have a specific job description |
| `refresh` | Periodic top-up: what changed, what numbers moved |
| `gaps` | Resolve unanswered questions and unverified claims |
| `pipeline` | What to chase this week, and recording what has happened |

# Rhythm

Something ships -> `braindump`, five minutes, while you remember the details.
Every quarter -> `refresh`. Before applying -> `gaps`, then `resume`. Specific role -> `tailor`.
Once a week while job-hunting -> `pipeline`.

# Tools

Validation and ATS checking live with the `jsk` skill, not in this folder, so they
stay current as the skill improves. The normal route is simply to ask:

> "validate my bundle" — "check this resume is ATS-safe"

To run them yourself, use the `scripts/` directory inside the installed skill:

    python3 <jsk-skill>/scripts/validate_bundle.py .            # needs pyyaml
    python3 <jsk-skill>/scripts/check_ats.py resume.pdf         # the deliverable
    python3 <jsk-skill>/scripts/check_ats.py resume_ATS.txt --strict

On Windows use `python` or `py -3` in place of `python3`.

# Customising the rules

Rendering rules ship with the skill. If you want to override them for this bundle, create
`resume-generation/ats-rules.md`, `writing-rules.md` or `structure-rules.md` — the skill reads
yours in preference to its own. Nothing here is created for you, so an absent file simply means
"use the skill's defaults".
""")

    with open(os.path.join(root, "log.md"), "w", encoding="utf-8") as f:
        f.write(fm("Log", "Bundle change log", "Chronological history of this bundle.", ts))
        f.write(f"# {today} - Bundle created\n\nSkeleton generated. Concepts not yet populated.\n")

    with open(os.path.join(root, "framework", "capability-vocabulary.md"), "w", encoding="utf-8") as f:
        f.write(fm("Vocabulary", "Capability vocabulary",
                   "Canonical capability values. Reuse these; a synonym breaks job matching.", ts))
        f.write("""Capabilities are the primary axis for matching a job description to evidence, and they compare
as exact strings — a synonym silently breaks matching. Check here before inventing a value, and
add new values in the same edit that first uses them.

Add one Markdown list item per value, in backticks, under the theme headings below:

```
- `ai-platform-architecture`
- `data-sovereignty`
```

Only list items count as vocabulary; prose and the example above are ignored. While the headings
are empty, capability checking stays off.

# Architecture & design

# Engineering & delivery

# Leadership & engagement
""")

    # Ships full, unlike the capability vocabulary above, which ships empty and grows
    # with the person. These name a process the scripts reason about rather than
    # someone's own work, so the list is not theirs to invent.
    with open(os.path.join(root, "framework", "pipeline-vocabulary.md"), "w", encoding="utf-8") as f:
        f.write(pipeline_model.vocabulary_markdown(ts))

    # The two files without which a bundle compiles to nothing. Scaffolded empty and
    # marked needs-verification rather than left out: a bundle that validates clean and
    # renders a blank page sends someone all the way to the render before they find out
    # there was never anything to render, and an absent file gives setup mode nothing to
    # fill in - only something to invent. Every value here is blank for the same reason:
    # a placeholder headline would be compiled onto a resume as though somebody wrote it.
    with open(os.path.join(root, "profile", "identity.md"), "w", encoding="utf-8") as f:
        f.write(fm("Person", name, "", ts, {"status": "needs-verification"}))
        f.write("""# Contact

Fill each value in, then set `status: confirmed`. `description` in the frontmatter is
the headline a resume leads with - one line, what you do and at what level.

| Field | Value |
|---|---|
| Name | %s |
| Location | |
| Email | |
| Phone | |
| LinkedIn | |

# Never render

Anything below this heading is here so the bundle holds it, not so a resume prints it -
home address, date of birth, government identifiers. The compile reads the contact table
above and nothing else.
""" % name)

    with open(os.path.join(root, "achievements", "metrics.md"), "w", encoding="utf-8") as f:
        f.write(fm("Metric Set", "Verified numbers",
                   "Every quantified outcome, recorded once, with where it came from.",
                   ts, {"status": "needs-verification"}))
        f.write("""Each number lives here once and a resume bullet names the row rather than restating it.
That is what stops a rewritten clause inflating it - "cut latency 62%" becoming "by over
60%" becoming "by two thirds".

`Evidence` links the project concept the number came out of. `Source` is how it was
established: a dashboard, an invoice, a post-incident review, the person's own recall.

| Metric | Value | Evidence | Source |
|---|---|---|---|
""")

    with open(os.path.join(root, "resume-generation", "open-questions.md"), "w", encoding="utf-8") as f:
        f.write(fm("Open Questions", "Verify before publishing",
                   "Unresolved facts, missing metrics and inferred claims requiring confirmation.",
                   ts, {"status": "needs-verification"}))
        f.write("# Blocking\n\n# Missing metrics\n\n# Not yet explored\n")

    print(f"created bundle at {root}")
    print("next: interview to populate concepts, adding capability values to "
          "framework/capability-vocabulary.md as you go")
    return 0

if __name__ == "__main__":
    sys.exit(main())
