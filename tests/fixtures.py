"""Builders and helpers for the jsk tests.

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
PACKAGE = "jsk"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The modules the tests drive as commands. These are module names, not file paths: a
# module inside a package run as a loose file has no package context, so its own
# `from . import ...` fails on the way in. `run()` invokes them with `-m`.
SCRIPTS = REPO_ROOT / "src" / PACKAGE      # for tests that read a module's source text
CLI = f"{PACKAGE}.cli"
KB = f"{PACKAGE}.kb"
CHECK_ATS = f"{PACKAGE}.gates.check_ats"
FIT_PAGES = f"{PACKAGE}.urs.fit_pages"


def load_script(name):
    """Import one of the package's modules, so its pure functions can be tested directly.

    This used to exec a loose file through `spec_from_file_location`, because the
    scripts were CLIs sitting outside any importable path. They are a package now, so
    an import is an import - and two modules reached the same way are the same object,
    which the file-loading version could not promise.

    A caller may name a module three ways: fully qualified, as a bare stem, or as the
    documented script filename that most of the codebase's comments still use. Which
    subpackage a filename lives in is `cli.SUBPACKAGE`'s answer and not a second copy
    here - that map is what `jsk` itself dispatches on, so a module that moves without
    it being updated fails in the CLI before it fails in a test.
    """
    name = str(name)
    if not name.startswith(PACKAGE + "."):
        from jsk.cli import SUBPACKAGE              # noqa: PLC0415 - test helper
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


def kb_text(directory):
    """Read the Markdown knowledge base in `directory`."""
    return (Path(directory) / "user-knowledgebase.md").read_text(encoding="utf-8")


def scaffold_markdown_kb(directory, name, date="2026-09-01"):
    """Write the `kb: 2` template into `directory`: exactly the user-knowledgebase.md
    `jsk new` wrote before it wrote the graph record (git 364ca6f:src/jsk/kb.py). Every
    Markdown knowledge base on disk started from it, so `jsk migrate` is held to it for
    as long as `jsk migrate` exists."""
    template = (Path(__file__).parent / "kb2_template.md").read_text(encoding="utf-8")
    path = Path(directory) / "user-knowledgebase.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template.replace("__NAME__", name).replace("__DATE__", date),
                    encoding="utf-8", newline="\n")
    return path


# --- the render ---------------------------------------------------------------

# The skill still exists and still has references/ and its mode files; what moved out
# of it is the code and the schema. test_plugin_surface.py reads the skill, the tests
# below read the package.
PLUGIN = REPO_ROOT / "plugins" / "jsk"
SCHEMA_DIR = SRC / PACKAGE / "data" / "schema"
RENDER_RESUME = f"{PACKAGE}.urs.render_resume"
CHECK_PROSE = f"{PACKAGE}.gates.check_prose"
PREFLIGHT = f"{PACKAGE}.preflight"
# The shipped example workspace's short resume.json: what `jsk doctor` renders, and what
# a render test reaches for when any resume will do. (example.resume.json, the full URS
# record it replaced, went on 2026-09-25.)
EXAMPLE_SHORT = SRC / PACKAGE / "data" / "example" / "resume.json"


def urs_module(name):
    """Import a module from the urs package the renderer itself uses.

    `urs.emit_latex` and `jsk.urs.emit_latex` name the same module now, so the bare
    spelling callers already use is qualified here rather than at every call site.
    """
    if not name.startswith(PACKAGE + "."):
        name = f"{PACKAGE}.{name}"
    return importlib.import_module(name)
