"""Builders and helpers for the jsk script tests.

Standard library only, matching the scripts under test. Every artefact is written
to a caller-supplied temp directory, so nothing lands in the repo and .gitignore's
`*.pdf` rule never comes into it.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "plugins" / "jsk" / "skills" / "jsk" / "scripts"
CHECK_ATS = SCRIPTS / "check_ats.py"
VALIDATE_BUNDLE = SCRIPTS / "validate_bundle.py"
INIT_BUNDLE = SCRIPTS / "init_bundle.py"
MIGRATE_BUNDLE = SCRIPTS / "migrate_bundle.py"
PIPELINE = SCRIPTS / "pipeline.py"
PIPELINE_MODEL = SCRIPTS / "pipeline_model.py"
FIT_PAGES = SCRIPTS / "fit_pages.py"
OKF_COMPILE = SCRIPTS / "okf_compile.py"


def load_script(path):
    """Import a script as a module, so its pure functions can be tested directly.

    The scripts are CLIs, not packages, and live outside any importable path. The
    parts worth unit-testing — XML transforms, scoring, geometry — are pure, and
    exercising them through a subprocess would say much less about them.
    """
    path = Path(path)
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

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


def run(script, *args):
    """Run a script as the CLI does. Returns (exit_code, combined_output)."""
    proc = subprocess.run(
        [sys.executable, str(script)] + [str(a) for a in args],
        capture_output=True, text=True,
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

SKILL_DIR = REPO_ROOT / "plugins" / "jsk" / "skills" / "jsk"
SCHEMA_DIR = SKILL_DIR / "schema"
VALIDATE_URS = SCRIPTS / "validate_urs.py"
RENDER_RESUME = SCRIPTS / "render_resume.py"
EXAMPLE_URS = SCHEMA_DIR / "example.resume.json"


def urs_module(name):
    """Import a module from the urs package the renderer itself uses."""
    import importlib
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
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

    Same shape as urs_module: the scripts directory is not on the path, because
    these are CLIs rather than an installed package.
    """
    import importlib
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(name)
