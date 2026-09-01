"""Builders and helpers for the jsk-okf tests.

Standard library only, matching the package under test. Every artefact is written
to a caller-supplied temp directory, so nothing lands in the repo and .gitignore's
`*.pdf` rule never comes into it.

`src/` is put on the path here rather than requiring an install, so that
`python -m pytest tests` and `python -m unittest discover -s tests` both work from a
bare checkout - which is what ARCHITECTURE.md promises and what CI relies on.
"""
import importlib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
PACKAGE = "jsk_okf"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The modules the tests drive as commands. These are module names, not file paths: a
# module inside a package run as a loose file has no package context, so its own
# `from . import ...` fails on the way in. `run()` invokes them with `-m`.
SCRIPTS = REPO_ROOT / "src" / PACKAGE      # for tests that read a module's source text
CLI = f"{PACKAGE}.cli"
CHECK_ATS = f"{PACKAGE}.gates.check_ats"
VALIDATE_BUNDLE = f"{PACKAGE}.validate_bundle"
INIT_BUNDLE = f"{PACKAGE}.init_bundle"
MIGRATE_BUNDLE = f"{PACKAGE}.migrate_bundle"
PIPELINE = f"{PACKAGE}.pipeline"
PIPELINE_MODEL = f"{PACKAGE}.pipeline_model"
FIT_PAGES = f"{PACKAGE}.urs.fit_pages"
OKF_COMPILE = f"{PACKAGE}.okf_compile"


def load_script(name):
    """Import one of the package's modules, so its pure functions can be tested directly.

    This used to exec a loose file through `spec_from_file_location`, because the
    scripts were CLIs sitting outside any importable path. They are a package now, so
    an import is an import - and two modules reached the same way are the same object,
    which the file-loading version could not promise.

    A caller may name a module three ways: fully qualified, as a bare stem, or as the
    documented script filename that most of the codebase's comments still use. Which
    subpackage a filename lives in is `cli.SUBPACKAGE`'s answer and not a second copy
    here - that map is what `okf` itself dispatches on, so a module that moves without
    it being updated fails in the CLI before it fails in a test.
    """
    name = str(name)
    if not name.startswith(PACKAGE):
        from jsk_okf.cli import SUBPACKAGE          # noqa: PLC0415 - test helper
        stem = Path(name).stem
        where = SUBPACKAGE.get(f"{stem}.py")
        name = f"{PACKAGE}.{where}.{stem}" if where else f"{PACKAGE}.{stem}"
    return importlib.import_module(name)


def build_text(path, paragraphs=(), trailing=()):
    """Write the extracted-text form of a resume: one paragraph per line.

    This replaces build_docx. Both document gates now read text - check_ats.py
    from the PDF or the .txt, check_prose.py from the .tex or the .txt - so a
    fixture exercising a rule about what a document *says* no longer has to
    synthesise OOXML to say it. The seven rules that needed real OOXML were the
    structural ones, and those are gone: one LaTeX template cannot emit a table
    or a text box, so the check moved to a golden-file test on the template.
    """
    lines = [item if isinstance(item, str) else item[0] for item in paragraphs]
    lines.extend(trailing)
    with open(str(path), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return str(path)


def build_pdf(path, text_lines=(), blank=False):
    """A PDF written directly, for the rules that are about the PDF itself.

    `blank=True` produces a page with no text layer at all - a scan, as far as
    any parser is concerned - which is the case the extractability rule exists
    for and the one no .txt fixture can express.
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    if not blank:
        page.insert_text((72, 72), "\n".join(text_lines), fontsize=11)
    doc.save(str(path))
    doc.close()
    return str(path)


# A resume that satisfies every documented rule, in both normal and --strict mode.
# Guards against the fixes becoming so strict that legitimate documents are blocked.
CLEAN_RESUME = [
    "Jane Doe",
    "Phone: +61 400 123 456 | Email: jane.doe@example.com",
    "Professional Summary",
    "Solution architect who builds the platforms other teams build on.",
    "Technical Skills",
    "Azure, Bicep, Kubernetes, Terraform, Python",
    "Professional Experience",
    "Senior Architect, Acme Corp | Jun 2025 - Present",
    "Owned the migration to event-driven services across six delivery teams.",
    "Architect, Globex | Jan 2018 - May 2025",
    "Cut order-processing latency 62 percent by decomposing a monolithic service.",
    "Lead Engineer, Initech | Mar 2015 - Dec 2017",
    "Ran the delivery team through two platform rewrites.",
    "Education",
    "BSc Computer Science, University of Melbourne, 2014",
]


def resume_with(*replacements, base=None):
    """CLEAN_RESUME with `(old, new)` substitutions applied; new=None deletes the line."""
    lines = list(base if base is not None else CLEAN_RESUME)
    for old, new in replacements:
        idx = lines.index(old)
        if new is None:
            del lines[idx]
        else:
            lines[idx] = new
    return lines


def child_env():
    """An environment where the child interpreter can import the package.

    Without this every `run()` would need the package installed, and the promise that
    the suite works from a bare checkout would quietly stop being true - the tests
    would pass against whatever version happened to be installed instead of the one in
    the working tree, which is the worse of the two failures.
    """
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return env


def run(module, *args):
    """Run a module as the CLI does, in a child interpreter.

    Returns (exit_code, combined_output). `-m` rather than a file path, because these
    modules live in a package and their relative imports need the package context.
    """
    proc = subprocess.run(
        [sys.executable, "-m", str(module)] + [str(a) for a in args],
        capture_output=True, text=True, env=child_env(),
    )
    return proc.returncode, proc.stdout + proc.stderr


CONCEPT = """---
type: Project
title: "Acme - care coordination platform"
description: "Multi-tenant platform for aged-care providers."
tags: [healthcare, azure]
timestamp: 2026-01-01T00:00:00Z
status: confirmed
strength: 5
recency: 2026
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture, data-sovereignty]
technologies: [azure-ai-foundry, bicep]
headline_metric: "event latency 5 min to under 1 s"
---

# The problem

The legacy scheduler could not express care-plan constraints.
"""


def write_concept(bundle, name="care-platform.md", text=CONCEPT):
    path = Path(bundle) / "projects" / name
    path.write_text(text, encoding="utf-8")
    return path


# --- URS -------------------------------------------------------------------

# The skill still exists and still has references/ and its mode files; what moved out
# of it is the code and the schema. test_plugin_surface.py reads the skill, the tests
# below read the package.
PLUGIN = REPO_ROOT / "plugins" / "jsk"
SKILL_DIR = PLUGIN / "skills" / "jsk"
SCHEMA_DIR = SRC / PACKAGE / "data" / "schema"
VALIDATE_URS = f"{PACKAGE}.gates.validate_urs"
RENDER_RESUME = f"{PACKAGE}.urs.render_resume"
PREVIEW_TEMPLATES = f"{PACKAGE}.urs.preview_templates"
SCORE_PROJECTS = f"{PACKAGE}.score_projects"
CHECK_PROSE = f"{PACKAGE}.gates.check_prose"
PREFLIGHT = f"{PACKAGE}.preflight"
EXAMPLE_URS = SCHEMA_DIR / "example.resume.json"


def urs_module(name):
    """Import a module from the urs package the renderer itself uses.

    `urs.plan` and `jsk_okf.urs.plan` name the same module now, so the bare spelling
    callers already use is qualified here rather than at every call site.
    """
    if not name.startswith(PACKAGE):
        name = f"{PACKAGE}.{name}"
    return importlib.import_module(name)


def urs_package():
    """Import the urs package the renderer uses, for plan-level assertions."""
    return urs_module("urs.plan")


def instant(value, precision="month"):
    return {"value": value, "precision": precision}


def ended(start, end):
    return {"start": instant(start), "end": instant(end), "state": "ended"}


def ongoing(start):
    return {"start": instant(start), "state": "ongoing"}


def achievement(text, metrics=(), aid="ach_one", status="confirmed", **extra):
    node = {
        "id": aid,
        "text": text,
        "metrics": list(metrics),
        "provenance": {"status": status},
    }
    node.update(extra)
    return node


def urs_doc(**overrides):
    """A minimal document that passes validate_urs.py, for tests to break."""
    doc = {
        "urs": "1.0.0",
        "meta": {"lang": "en", "updated": "2026-08-25"},
        "person": {
            "name": {"full": "Test Person"},
            "headline": "Principal Engineer",
            "location": {"city": "Melbourne", "region": "VIC", "country": "AU"},
            "contacts": [
                {"kind": "email", "value": "test.person@example.com"},
                {"kind": "phone", "value": "+61 400 000 000"},
            ],
            "demographics": {
                "date_of_birth": instant("1988-04"),
                "nationality": ["IN"],
                "marital_status": "married",
            },
        },
        "work_authorization": [
            {"jurisdiction": "AU", "kind": "permanent", "status": "held",
             "label": "Australian Permanent Resident"}
        ],
        "languages": [{"language": "English", "native": True}],
        "organizations": [{"id": "org_acme", "name": "Acme Health"}],
        "engagements": [{
            "id": "eng_acme",
            "kind": "employment",
            "organization": "org_acme",
            "period": ongoing("2021-02"),
            "positions": [
                {"id": "pos_a", "title": "Senior Engineer",
                 "period": ended("2021-02", "2023-06"), "change": "hire"},
                {"id": "pos_b", "title": "Principal Engineer",
                 "period": ongoing("2023-07"), "change": "promotion"},
            ],
            "achievements": [
                achievement(
                    "Cut p95 latency from 5 minutes to under 1 second.",
                    metrics=[{
                        "kind": "delta", "subject": "p95 latency",
                        "baseline": {"value": 5, "unit": "min"},
                        "quantity": {"value": 1, "unit": "s"},
                        "direction": "decrease", "confidence": "measured",
                    }],
                    aid="ach_latency", weight=5),
                achievement("Rebuilt the ingestion pipeline end to end.",
                            aid="ach_pipeline", weight=3),
            ],
        }],
        "education": [{
            "id": "edu_meng", "institution": "Anna University", "level": "isced-7",
            "qualification": "Master of Engineering", "field": "Computer Science",
            "period": ended("2010", "2012"),
            "grade": {"scheme": "in-cgpa-10", "value": 8.4,
                      "scale": {"min": 0, "max": 10}, "direction": "higher-is-better"},
            "provenance": {"status": "confirmed"},
        }],
        "skills": [{"id": "skill_azure", "name": "Azure", "category": "cloud-platform",
                    "evidence": ["ach_latency"]}],
        "narratives": [{"id": "nar_default", "kind": "summary",
                        "text": "Engineer who owns platforms end to end.",
                        "provenance": {"status": "confirmed"}}],
        "views": [{
            "id": "view_default", "format_profile": "presentation",
            "region_profile": "urs:profile:au/1", "narrative": "nar_default",
            "provenance_floor": "confirmed", "budget": {"pages": 2},
        }],
    }
    doc.update(overrides)
    return doc


def write_urs(directory, doc, name="resume.json"):
    import json
    path = Path(directory) / name
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


def authoring_module(name):
    """Import a module from the authoring package the write commands use.

    Same shape as urs_module, and the same reason for qualifying the name here.
    """
    if not name.startswith(PACKAGE):
        name = f"{PACKAGE}.{name}"
    return importlib.import_module(name)


def query_module(name):
    """Import a module from the read layer the query commands use."""
    if not name.startswith(PACKAGE):
        name = f"{PACKAGE}.query.{name}"
    return importlib.import_module(name)


# --- a bundle with something of everything in it ---------------------------------
#
# The read layer's fixture. `test_okf_compile.build_bundle` is the seed and is still
# right for what it does - compile a bundle and render it - but a query has to be
# asked about things a compile never looks at: an open question, a capability
# vocabulary, a frozen archive, a file with no `type:` at all. Every one of those is
# a guarantee in tests/test_query*.py, so they live here rather than being rebuilt
# per test file.
#
# Deliberately not a clean bundle. It holds an inferred bullet, a project with no
# role, an uncited metric and a vocabulary term nothing uses, because those are what
# `okf list unconfirmed` and `okf list orphans` exist to find. A fixture that would
# pass every gate can only test the empty answer.

Q_INDEX = """---
type: Index
title: "Ada Vance - career record"
okf_bundle: 7
---

# Navigation

- [Projects](projects/index.md)
"""

Q_PERSON = """---
type: Person
title: "Ada Vance"
description: "Platform architect, eleven years, Melbourne."
status: confirmed
---

# Contact

| Field | Value |
|---|---|
| Name | Ada Vance |
| Location | Melbourne, VIC, Australia |
| Email | ada@example.com |
"""

Q_POSITIONING = """---
type: Positioning
title: "How the resume frames her"
status: confirmed
---

# Summary variant A - positioning-led (default)

> Platform architect who builds what other teams build on.

Use for: direct applications.

# Summary variant B - keyword-dense

> Azure platform architect with event-driven and data-sovereignty depth.
"""

Q_ORG = """---
type: Organisation
relationship: employer
title: "Meridian Health"
description: "Aged-care provider."
location: "Melbourne, VIC"
status: confirmed
---

# People

| Name | Role | How | Last contact |
|---|---|---|---|
| Jo Patel | hiring manager | referral | 2026-02-01 |
"""

Q_ORG_PROSPECT = """---
type: Organisation
relationship: prospect
title: "Kestrel Systems"
description: "Logistics platform, applied to in 2025."
status: confirmed
---
"""

Q_ROLE_ONE = """---
type: Role
title: "Senior Engineer"
description: "First role at Meridian."
organisation: meridian-health
start: 2019-04
end: 2021-12
state: ended
seniority: technical-ownership
change: hire
status: confirmed
---
"""

Q_ROLE_TWO = """---
type: Role
title: "Principal Engineer"
description: "After the platform shipped."
functional_title: "Platform Architect"
organisation: meridian-health
start: 2022-01
state: ongoing
seniority: architecture-ownership
change: promotion
status: confirmed
---
"""

# The flagship. Two bullets, one confirmed and one inferred, so `--status` has
# something to separate and `list unconfirmed` has a claim to find inside an
# otherwise confirmed concept.
Q_PROJECT = """---
type: Project
title: "Care coordination platform"
description: "Multi-tenant platform for aged-care providers."
role: principal-engineer
status: confirmed
strength: 5
recency: 2024
seniority: architecture-ownership
domains: [healthcare, aged-care]
capabilities: [ai-platform-architecture, event-driven-architecture]
technologies: [azure, bicep]
headline_metric: "event latency 5 min to under 1 s"
---

# The problem

The legacy scheduler could not express care-plan constraints, and event propagation
took five minutes across the estate.

# Bullets

- Cut event propagation from 5 minutes to under 1 second across the integrated estate.
  metric: Event propagation latency
  status: confirmed
- Led the data-sovereignty design so tenant records never left the region.
  status: inferred
"""

# No `role:`, lower strength, older. The orphan `list orphans` reports, and the row
# `--strength 4+` must exclude.
Q_PROJECT_ORPHAN = """---
type: Project
title: "Billing reconciliation tool"
description: "Weekend tool that stuck."
status: needs-verification
strength: 2
recency: 2019
seniority: hands-on
domains: [finance]
capabilities: [event-driven-architecture]
technologies: [python]
---

# The problem

Invoices and ledger entries disagreed and nobody could say by how much.
"""

# Two rows. The second is cited by no bullet, which is what `list orphans` reports
# and what `list metrics` counts as zero.
Q_METRICS = """---
type: Metric Set
title: "Verified metrics"
status: confirmed
---

# Confirmed numbers

| Metric | Value | Project | Source | Notes |
|---|---|---|---|---|
| Event propagation latency | **5 min to under 1 s** | [Care](../projects/care-platform.md) | interview | |
| Tenants onboarded | **34** | [Care](../projects/care-platform.md) | dashboard | |
"""

Q_SKILLS = """---
type: Skill Set
title: "Core competencies"
status: confirmed
---

# Skills

- C# / .NET
  id: skill_dotnet
  category: language
  aliases: C#, .NET, ASP.NET Core
- Azure
  category: cloud-platform
  aliases: Azure, Bicep, Azure AI Foundry
"""

Q_EDUCATION = """---
type: Education
title: "BE Computer Science"
description: "Bachelor of Engineering."
start: 2011
end: 2015
state: ended
status: confirmed
---
"""

Q_CERTIFICATION = """---
type: Certification Status
title: "Cloud certifications"
description: "What is held and what is current."
status: confirmed
---

# Held

- Azure Solutions Architect Expert
  issuer: Microsoft
  issued: 2024-05
  status: active
"""

# One term nothing carries - `list orphans` finds it, and `list capabilities` shows
# it at zero. The two that are used sit above it so the theme grouping is exercised.
Q_VOCABULARY = """---
type: Vocabulary
title: "Capability vocabulary"
status: confirmed
---

# Platform

- `ai-platform-architecture`
- `event-driven-architecture`
- `data-sovereignty`
"""

Q_QUESTIONS = """---
type: Open Questions
title: "Open questions"
status: confirmed
---

# Open

| Question | Why it matters | Asked | Resolved |
|---|---|---|---|
| How many tenants by the end of 2024? | sizes the platform claim | 2026-02-01 | |
| Did the sovereignty design ship? | a bullet rests on it | 2026-02-01 | |

# Resolved

| Question | Why it matters | Asked | Resolved |
|---|---|---|---|
| What was the team size? | sets the verb | 2026-01-10 | 2026-01-11 - six |
"""

Q_POSTING = """---
type: Job Posting
title: "Principal Engineer"
company: "Meridian Health"
seniority: architecture-ownership
domains: [healthcare]
requirements:
  - value: ai-platform-architecture
    kind: capability
    necessity: required
    label: "platform architecture"
  - value: azure
    kind: technology
    necessity: preferred
    label: "Azure"
---

# Advertisement

Meridian Health is hiring a principal engineer for its care platform. Event-driven
experience and low latency systems are what we care about.
"""

Q_GAPS = """---
type: Gap Assessment
title: "Meridian - what is missing"
status: confirmed
---

# Verdict

Strong fit. The sovereignty bullet is inferred and needs confirming.
"""

# The view selects the *first* bullet and not the second, so a query can tell an
# included claim from an excluded one.
#
# The shape matters and the wrong one is silent. `ref` names an owner - an engagement or
# a project - and the claim ids go in `achievements` and `skills`, per
# `references/view-format.md` and `authoring.claims._selected`. This fixture first wrote
# `- ref: ach_...`, which `urs/resolve.py` keys by owner id and therefore ignores: the
# view rendered nothing, `okf bullet rm` would not have refused on it, and every test
# written against it would still have passed.
Q_VIEW = """---
type: View
id: view_meridian_principal
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
narrative: nar_a_positioning_led_default
budget:
  pages: 2
include:
  - ref: eng_meridian_health
    order: 1
    achievements: [ach_projects_care_platform_md_1]
skills: [skill_dotnet]
---
"""

# The archive. Every read defaults to not seeing this, and every hit in it must say
# it is frozen - so the text below deliberately repeats a word the working copies
# also use, giving `--archive` something to find that is not already in the answer.
Q_APPLICATION = """---
type: Application
title: "Kestrel Systems - staff engineer"
company: "Kestrel Systems"
role: "Staff Engineer"
posting: "2025-11-03-kestrel-staff.posting.md"
assessment: "2025-11-03-kestrel-staff.gaps.md"
view_file: "2025-11-03-kestrel-staff.view.md"
company_ref: "../../../organisations/kestrel-systems.md"
view: view_kestrel_staff
submitted: 2025-11-03
channel: "Workday portal"
status: confirmed
---

# Timeline

| Date | Event | Channel | Note | Due |
|---|---|---|---|---|
| 2025-11-03 | submitted | Workday | ATS variant uploaded | |
| 2025-11-20 | rejected | email | Went internal | |
"""

Q_FROZEN_POSTING = """---
type: Job Posting
title: "Staff Engineer"
company: "Kestrel Systems"
frozen: true
frozen_date: "2025-11-03"
requirements:
  - value: event-driven-architecture
    kind: capability
    necessity: required
    label: "event-driven systems"
---

# Advertisement

Kestrel Systems needs a staff engineer for low latency logistics eventing.
"""

Q_FROZEN_VIEW = """---
type: View
title: "Kestrel - staff engineer (as sent)"
frozen: true
frozen_date: "2025-11-03"
id: view_kestrel_staff
format_profile: presentation
region_profile: urs:profile:au/1
provenance_floor: confirmed
budget:
  pages: 2
---
"""

# No frontmatter at all. `okf_compile.concepts()` drops it; `okf search` must find it
# and `okf list` must not show it.
Q_UNTYPED = """# Scratch

Notes from the retro: the latency work was the thing people remembered.
"""

Q_LOG = """---
type: Log
title: "Change log"
status: confirmed
---

# 2026-02-01

- Recorded the care platform.
"""

# (directory, filename, text). Ordered as a person would read the bundle.
QUERY_FILES = (
    ("", "index.md", Q_INDEX),
    ("", "log.md", Q_LOG),
    ("profile", "identity.md", Q_PERSON),
    ("profile", "positioning.md", Q_POSITIONING),
    ("organisations", "meridian-health.md", Q_ORG),
    ("organisations", "kestrel-systems.md", Q_ORG_PROSPECT),
    ("roles", "senior-engineer.md", Q_ROLE_ONE),
    ("roles", "principal-engineer.md", Q_ROLE_TWO),
    ("projects", "care-platform.md", Q_PROJECT),
    ("projects", "billing-reconciliation.md", Q_PROJECT_ORPHAN),
    ("achievements", "metrics.md", Q_METRICS),
    ("skills", "competencies.md", Q_SKILLS),
    ("education", "be-computer-science.md", Q_EDUCATION),
    ("education", "cloud-certifications.md", Q_CERTIFICATION),
    ("framework", "capability-vocabulary.md", Q_VOCABULARY),
    ("resume-generation", "open-questions.md", Q_QUESTIONS),
    ("sources", "retro-notes.md", Q_UNTYPED),
    ("tailoring/targets", "meridian-principal.posting.md", Q_POSTING),
    ("tailoring/targets", "meridian-principal.gaps.md", Q_GAPS),
    ("tailoring/targets", "meridian-principal.view.md", Q_VIEW),
    ("tailoring/applications/2025", "2025-11-03-kestrel-staff.md", Q_APPLICATION),
    ("tailoring/applications/2025", "2025-11-03-kestrel-staff.posting.md",
     Q_FROZEN_POSTING),
    ("tailoring/applications/2025", "2025-11-03-kestrel-staff.view.md", Q_FROZEN_VIEW),
)

# Every directory gets one, because bundle-spec.md says every directory gets one and
# because `walk.py` skips them by name - a fixture without them cannot show that.
QUERY_INDEX = "---\ntype: Index\ntitle: \"{name}\"\n---\n\n# Contents\n"


def query_bundle(root, files=QUERY_FILES):
    """Write the read layer's fixture bundle and return its path."""
    root = Path(root)
    for folder, name, text in files:
        directory = root / folder if folder else root
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text, encoding="utf-8")
    for folder in sorted({folder for folder, _, _ in files if folder}):
        index = root / folder / "index.md"
        if not index.exists():
            index.write_text(QUERY_INDEX.format(name=folder), encoding="utf-8")
    return root
