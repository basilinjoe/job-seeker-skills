#!/usr/bin/env python3
"""Create an empty OKF career bundle skeleton.

Usage: python3 init_bundle.py <path> --name "Full Name"

Creates directories, index files, and seed rule files. Standard library only.
Populate the concepts afterwards by interviewing the person.
"""
import os, sys, argparse, datetime

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
 "resume-generation":"Rules governing how this bundle renders into a resume.",
 "tailoring":"Turning a job description into a targeted resume.",
 "tailoring/targets":"Captured job descriptions.",
 "tailoring/applications":"Submissions, evidence selected, and outcomes.",
}

def fm(t, title, desc, ts, extra=""):
    return f'---\ntype: {t}\ntitle: "{title}"\ndescription: "{desc}"\ntimestamp: {ts}\n{extra}---\n\n'

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
        with open(os.path.join(root, d, "index.md"), "w", encoding="utf-8") as f:
            f.write(fm("Index", slug, BLURB.get(d, slug), ts) + "Empty. Add concepts here.\n")

    with open(os.path.join(root, "index.md"), "w", encoding="utf-8") as f:
        f.write(fm("Index", f"{name} - Career Knowledge Bundle",
                   "Portable career knowledge base: roles, projects, evidence and resume rules.", ts))
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

The `career-okf` skill has six modes. Say what you want; it routes.

| Mode | Use when |
|---|---|
| `setup` | First time, or importing an old resume |
| `braindump` | You have something to say about your work |
| `resume` | You need a resume — two verified variants plus plain text |
| `tailor` | You have a specific job description |
| `refresh` | Periodic top-up: what changed, what numbers moved |
| `gaps` | Resolve unanswered questions and unverified claims |

# Rhythm

Something ships -> `braindump`, five minutes, while you remember the details.
Every quarter -> `refresh`. Before applying -> `gaps`, then `resume`. Specific role -> `tailor`.

# Tools

```bash
python3 framework/validate_bundle.py .              # bundle well-formed? (needs pyyaml)
python3 framework/check_ats.py resume.docx          # presentation variant
python3 framework/check_ats.py resume.docx --strict # ATS-maximal variant
```
""")

    with open(os.path.join(root, "log.md"), "w", encoding="utf-8") as f:
        f.write(fm("Log", "Bundle change log", "Chronological history of this bundle.", ts))
        f.write(f"# {today} - Bundle created\n\nSkeleton generated. Concepts not yet populated.\n")

    with open(os.path.join(root, "framework", "capability-vocabulary.md"), "w", encoding="utf-8") as f:
        f.write(fm("Vocabulary", "Capability vocabulary",
                   "Canonical capability values. Reuse these; a synonym breaks job matching.", ts))
        f.write("""`capabilities` is the primary axis for matching a job description to evidence, and it compares as
exact strings. Check here before inventing a value; add new values in the same edit.

# Architecture & design

# Engineering & delivery

# Leadership & engagement
""")

    with open(os.path.join(root, "resume-generation", "open-questions.md"), "w", encoding="utf-8") as f:
        f.write(fm("Open Questions", "Verify before publishing",
                   "Unresolved facts, missing metrics and inferred claims requiring confirmation.",
                   ts, "status: needs-verification\n"))
        f.write("# Blocking\n\n# Missing metrics\n\n# Not yet explored\n")

    print(f"created bundle at {root}")
    print("next: seed the rule files in resume-generation/, then interview to populate concepts")
    return 0

if __name__ == "__main__":
    sys.exit(main())
