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
CHECK_ATS = f"{PACKAGE}.check_ats"
VALIDATE_BUNDLE = f"{PACKAGE}.validate_bundle"
INIT_BUNDLE = f"{PACKAGE}.init_bundle"
MIGRATE_BUNDLE = f"{PACKAGE}.migrate_bundle"
PIPELINE = f"{PACKAGE}.pipeline"
PIPELINE_MODEL = f"{PACKAGE}.pipeline_model"
FIT_PAGES = f"{PACKAGE}.fit_pages"
OKF_COMPILE = f"{PACKAGE}.okf_compile"


def load_script(name):
    """Import one of the package's modules, so its pure functions can be tested directly.

    This used to exec a loose file through `spec_from_file_location`, because the
    scripts were CLIs sitting outside any importable path. They are a package now, so
    an import is an import - and two modules reached the same way are the same object,
    which the file-loading version could not promise.
    """
    if not str(name).startswith(PACKAGE):
        # A Path, or a bare module name, from a caller written before the move.
        name = f"{PACKAGE}.{Path(str(name)).stem}"
    return importlib.import_module(str(name))


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
VALIDATE_URS = f"{PACKAGE}.validate_urs"
RENDER_RESUME = f"{PACKAGE}.render_resume"
PREVIEW_TEMPLATES = f"{PACKAGE}.preview_templates"
SCORE_PROJECTS = f"{PACKAGE}.score_projects"
CHECK_PROSE = f"{PACKAGE}.check_prose"
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
