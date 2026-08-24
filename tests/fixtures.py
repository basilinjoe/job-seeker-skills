"""Builders and helpers for the career-okf script tests.

Standard library only, matching the scripts under test. Every artefact is written
to a caller-supplied temp directory, so nothing lands in the repo and .gitignore's
`*.docx` rule never comes into it.
"""
import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "plugins" / "career-okf" / "skills" / "career-okf" / "scripts"
CHECK_ATS = SCRIPTS / "check_ats.py"
VALIDATE_BUNDLE = SCRIPTS / "validate_bundle.py"
INIT_BUNDLE = SCRIPTS / "init_bundle.py"
FIT_PAGES = SCRIPTS / "fit_pages.py"


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

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
V_NS = 'xmlns:v="urn:schemas-microsoft-com:vml"'


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def paragraph(text, style=None, font="Calibri"):
    props = f'<w:pStyle w:val="{style}"/>' if style else ""
    props += f'<w:rPr><w:rFonts w:ascii="{font}"/></w:rPr>'
    return (f"<w:p><w:pPr>{props}</w:pPr>"
            f'<w:r><w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>')


def build_docx(path, paragraphs=(), body_extra="", extra_parts=None, font="Calibri"):
    """Write a minimal but well-formed .docx.

    paragraphs: iterable of `text` or `(text, style)`.
    body_extra: raw OOXML appended inside <w:body> (tables, text boxes, sectPr).
    extra_parts: {zip_entry_name: content} for headers, media, diagrams.
    """
    body = ""
    for item in paragraphs:
        text, style = (item, None) if isinstance(item, str) else item
        body += paragraph(text, style, font)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f"<w:document {W_NS} {V_NS}><w:body>{body}{body_extra}</w:body></w:document>")
    with zipfile.ZipFile(str(path), "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("_rels/.rels", "<Relationships/>")
        z.writestr("word/document.xml", doc)
        for name, content in (extra_parts or {}).items():
            z.writestr(name, content)
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
