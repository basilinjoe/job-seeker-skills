#!/usr/bin/env python3
"""Report what this machine can actually do, and what each gap disables.

Usage: python3 preflight.py [--verify] [--kb PATH] [--json]
       --verify   render the shipped example end to end and run every gate
       --kb       check a specific user-knowledgebase.md rather than searching
       --json     machine-readable output

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = the core pipeline works. Exit 1 = something required is broken.

Missing dependencies are reported as *lost capabilities*, not as package names.
"pymupdf: not found" tells someone nothing; "cannot measure page count, so a
two-page resume is a guess" tells them whether they care. Several of these gaps
are survivable and one of them - no TeX engine - silently downgrades a resume to
unverified, which is the one worth knowing about before you need it.

Standard library only. A preflight that needs installing first is not a
preflight.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import __version__
from .paths import EXAMPLE_RECORD as EXAMPLE, SCHEMA_DIR as SCHEMA

HERE = os.path.dirname(os.path.abspath(__file__))

MIN_PYTHON = (3, 10)

# The whole career, in one file. Named here because this is the only module that goes
# looking for it - everything else in the package starts at the record written from it.
KB_FILENAME = "user-knowledgebase.md"

# Module names rather than filenames since these became a package. A filename check
# answered "is this file on disk", which stopped being the interesting question: a
# module can be present and unimportable - a syntax error, a missing dependency of
# its own, a half-finished editable checkout - and find_spec is what notices.
MODULES = ["cli", "cliutil", "kb", "kbindex", "paths"]
# The graph record (docs/superpowers/specs/2026-09-24-graph-core-design.md). None of
# these imports pyoxigraph at module top, so find_spec answers "is the code here" even on
# a machine without the engine - the engine is its own check below.
GRAPH_MODULES = ["graph", "graph.ontology", "graph.io", "graph.writer", "graph.shapes",
                 "graph.rules", "graph.store", "graph.queries", "graph.match", "graph.record",
                 "graph.changeset", "graph.edit", "graph.kbcli", "graph.named", "graph.view"]
GATE_MODULES = ["gates", "gates.check_ats", "gates.check_prose", "gates.validate_urs",
                "gates.claims"]
# Rendering, the preview and the page fitter moved in here: they drive the
# record->document pipeline and import nothing else, so a broken urs package takes all
# three with it and reporting them separately would name three symptoms of one cause.
URS_MODULES = ["urs", "urs.plan", "urs.profiles", "urs.tex",
               "urs.emit_latex", "urs.emit_text",
               "urs.render_resume", "urs.preview_templates", "urs.fit_pages"]

SCHEMA_FILES = ["profile.schema.json", "example.resume.json"]
PROFILES = ["default.json", "au.json", "in.json", "ae.json"]

TEX_ENGINES = ["tectonic", "latexmk", "pdflatex", "xelatex", "lualatex"]

INSTALL = {
    "tex": {
        "win32": "winget install --id TectonicProject.Tectonic",
        "darwin": "brew install tectonic",
        "linux": "cargo install tectonic   # or: apt install texlive-latex-recommended",
        "note": "tectonic is a single self-contained binary; TeX Live and MiKTeX are "
                "gigabytes and only worth it if you already wanted them.",
    },
    "pymupdf": {"pip": "pymupdf",
                "note": "Reads the PDF: check_ats.py extracts its text and "
                        "fit_pages.py measures its pages."},
    "pyoxigraph": {"pip": "pyoxigraph",
                   "note": "The graph engine: reads, validates and queries kb.ttl and the "
                           "applications. A dependency of jsk-resume, so a missing one "
                           "means the install skipped dependencies."},
    "index": {"pip": "markdown-it-py pyyaml",
              "note": "Reads the knowledge base for jsk index: its headings and its "
                      "yaml blocks."},
}


def module_available(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def present(names):
    """Which of this package's own modules cannot be found, without importing them.

    `find_spec` on a submodule imports its parent, so a broken subpackage raises here
    rather than returning None - which is the same finding and has to be reported the
    same way.
    """
    missing = []
    for name in names:
        full = f"{__package__}.{name}"
        try:
            if importlib.util.find_spec(full) is None:
                missing.append(name)
        except Exception:
            missing.append(name)
    return missing


def which_any(names):
    for n in names:
        path = shutil.which(n)
        if path:
            return n, path
    return None, None


def find_kb(start="."):
    """The knowledge base is one file, so finding it is finding that file.

    Searched for by name rather than by a directory shape. A bundle used to be
    recognised by the folders inside it, which meant a half-created one - `projects/`
    made, `resume-generation/` not yet - was invisible to this check and reported as
    "no bundle" while the person was looking straight at it.
    """
    start = os.path.abspath(start)
    for root, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__", "node_modules"))]
        if depth(root, start) > 3:
            dirs[:] = []
            continue
        if KB_FILENAME in files:
            return os.path.join(root, KB_FILENAME)
    return None


def depth(path, base):
    return len(os.path.relpath(path, base).split(os.sep)) if path != base else 0


def hint(key):
    entry = INSTALL.get(key, {})
    if "pip" in entry:
        line = f"{os.path.basename(sys.executable)} -m pip install {entry['pip']}"
    else:
        line = entry.get(sys.platform) or entry.get("linux", "")
    return line, entry.get("note", "")


class Check:
    def __init__(self, name, ok, disables="", key=None, detail=""):
        self.name = name
        self.ok = ok
        self.disables = disables
        self.key = key
        self.detail = detail


def gather(kb_arg=None):
    checks = []

    checks.append(Check(
        f"Python {'.'.join(str(v) for v in sys.version_info[:3])}",
        sys.version_info >= MIN_PYTHON,
        disables="everything - this toolchain needs Python "
                 f"{'.'.join(str(v) for v in MIN_PYTHON)} or newer"))

    missing = present(MODULES)
    checks.append(Check(
        f"modules ({len(MODULES) - len(missing)}/{len(MODULES)})", not missing,
        disables=f"missing: {', '.join(missing)}" if missing else "",
        detail=HERE))

    missing_mod = present(URS_MODULES)
    checks.append(Check(
        "urs renderer package", not missing_mod,
        disables=f"missing: {', '.join(missing_mod)}" if missing_mod
                 else "", detail=os.path.join(HERE, "urs")))

    missing_graph = present(GRAPH_MODULES)
    checks.append(Check(
        "graph record package", not missing_graph,
        disables=f"missing: {', '.join(missing_graph)}" if missing_graph
                 else "", detail=os.path.join(HERE, "graph")))

    missing_gates = present(GATE_MODULES)
    checks.append(Check(
        "gates package", not missing_gates,
        disables=f"missing: {', '.join(missing_gates)}" if missing_gates
                 else "", detail=os.path.join(HERE, "gates")))

    missing_schema = [f for f in SCHEMA_FILES if not os.path.exists(os.path.join(SCHEMA, f))]
    missing_prof = [p for p in PROFILES
                    if not os.path.exists(os.path.join(SCHEMA, "profiles", p))]
    checks.append(Check(
        f"URS schema and {len(PROFILES) - len(missing_prof)} region profiles",
        not (missing_schema or missing_prof),
        disables=f"missing: {', '.join(missing_schema + missing_prof)}"
                 if (missing_schema or missing_prof) else ""))

    engine, path = which_any(TEX_ENGINES)
    checks.append(Check(
        f"TeX engine ({engine})" if engine else "TeX engine", bool(engine), key="tex",
        disables="no PDF at all. The PDF is the only rendered deliverable, so "
                 "without an engine there is nothing to send, nothing to check "
                 "and nothing to measure - render_resume.py --pdf reports "
                 "UNVERIFIED and exits non-zero",
        detail=path or ""))

    # The module name fit_pages.py actually imports. Probing the legacy `fitz`
    # alias instead answers a different question and prints a deprecation
    # warning while doing it.
    checks.append(Check(
        "pymupdf", module_available("pymupdf"), key="pymupdf",
        disables="the PDF cannot be read: check_ats.py cannot extract its text "
                 "and fit_pages.py cannot measure its pages, so the parse gate "
                 "and the page budget are both unverifiable"))

    # Not REQUIRED while nothing on the render path reads the graph: a machine without
    # it still renders and gates a resume from a hand-written record. find_spec, not an
    # import - this module stays standard-library only.
    checks.append(Check(
        "pyoxigraph", importlib.util.find_spec("pyoxigraph") is not None, key="pyoxigraph",
        disables="cannot read or validate the graph record (kb.ttl) - matching and "
                 "career writes are unavailable"))

    # Optional: a machine without them still renders and gates a resume. What it
    # loses is the index, so the tailor-analyst stops and asks for the install.
    checks.append(Check(
        "markdown-it-py and pyyaml",
        module_available("markdown_it") and module_available("yaml"), key="index",
        disables="jsk index cannot run, so tailoring stops before the ranking: the "
                 "analyst reads the knowledge base through the index"))

    kb = kb_arg or find_kb()
    checks.append(Check(
        f"knowledge base at {kb}" if kb else "knowledge base", bool(kb),
        disables="nothing to render from yet - `jsk new` creates one",
        detail=kb or ""))

    return checks, kb


# LibreOffice used to appear here. It rendered the .docx for page measurement;
# with the .docx gone it has no job left in this pipeline.
#
# A TeX engine and pymupdf moved the other way, from optional to required. They
# were survivable while the .docx was the portal artefact and the PDF was a
# nicety. Now the PDF is the only rendered deliverable, so a machine without
# them cannot produce a resume at all - reporting that as a degraded install
# would be telling someone their toolchain works when it does not.
REQUIRED = {"Python", "modules", "urs renderer package", "gates package", "graph record package",
            "URS schema", "TeX engine", "pymupdf"}


def is_required(check):
    return any(check.name.startswith(r) for r in REQUIRED)


def verify(tmp):
    """Render the shipped example and run every gate that can run here."""
    steps = []

    # Spawned, not imported: doctor proves each `python -m` entry point runs from cold.
    def run(label, args):
        proc = subprocess.run([sys.executable, "-m"] + args, capture_output=True, text=True)
        steps.append((label, proc.returncode == 0,
                      (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]))
        return proc.returncode == 0

    if not os.path.exists(EXAMPLE):
        steps.append(("example document present", False,
                      [f"{EXAMPLE} missing"]))
        return steps

    run("validate the example record",
        [f"{__package__}.gates.validate_urs", EXAMPLE])
    # --pdf, because the PDF is the deliverable: a render that stops at the .tex
    # proves the resolver works and nothing about whether anything can be sent.
    ok = run("render the example to a PDF",
             [f"{__package__}.urs.render_resume", EXAMPLE, "--out", tmp,
              "--view", "view_au_default", "--pdf"])
    if not ok:
        return steps

    pdf = os.path.join(tmp, "Priya_Raman_Resume.pdf")
    tex = os.path.join(tmp, "Priya_Raman_Resume.tex")
    txt = os.path.join(tmp, "Priya_Raman_Resume_ATS.txt")
    run("parse gate, rendered PDF", [f"{__package__}.gates.check_ats", pdf])
    run("parse gate, plain text (strict)",
        [f"{__package__}.gates.check_ats", txt, "--strict"])
    run("prose gate", [f"{__package__}.gates.check_prose", tex])
    return steps


def main(argv):
    if "--help" in argv or "-h" in argv:
        # Reading the usage checks nothing: running the preflight here meant a --verify
        # render, and an exit of 1 on any machine without a TeX engine.
        print(next(p for p in __doc__.split("\n\n") if p.startswith("Usage:")))
        return 0
    as_json = "--json" in argv
    kb_arg = None
    if "--kb" in argv:
        try:
            kb_arg = argv[argv.index("--kb") + 1]
        except IndexError:
            print("--kb needs a path")
            return 2

    checks, kb = gather(kb_arg)
    blocked = [c for c in checks if not c.ok and is_required(c)]
    degraded = [c for c in checks if not c.ok and not is_required(c)]

    steps = []
    if "--verify" in argv and not blocked:
        with tempfile.TemporaryDirectory() as tmp:
            steps = verify(tmp)

    if as_json:
        print(json.dumps({
            "ok": not blocked and all(s[1] for s in steps),
            "knowledge_base": kb,
            "checks": [{"name": c.name, "ok": c.ok, "required": is_required(c),
                        "disables": c.disables} for c in checks],
            "verify": [{"step": s[0], "ok": s[1]} for s in steps],
        }, indent=2))
        return 1 if blocked or any(not s[1] for s in steps) else 0

    print("jsk preflight")
    print(f"jsk {__version__}")
    print(f"package: {HERE}\n")
    for c in checks:
        mark = "ok  " if c.ok else ("FAIL" if is_required(c) else "gap ")
        print(f"  {mark}  {c.name}")
        if c.ok and c.detail and c.detail != HERE:
            print(f"           {c.detail}")
        if not c.ok and c.disables:
            print(f"           {c.disables}")

    # Only the gaps something can be installed for. The knowledge base is a gap with
    # no `key` and no install line, so it used to print this heading over nothing -
    # a "to close the gaps" with no gaps under it reads as truncated output.
    fixable = [c for c in degraded if c.key and hint(c.key)[0]]
    if fixable:
        print("\nTo close the gaps:")
        for c in fixable:
            line, note = hint(c.key)
            print(f"  {line}")
            if note:
                print(f"      {note}")

    if steps:
        print("\nEnd-to-end check on the shipped example:")
        for label, ok, tail in steps:
            print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
            if not ok and tail:
                print(f"           {tail[0]}")

    failed_steps = [s for s in steps if not s[1]]
    print()
    if blocked:
        print("BLOCKED - the core pipeline cannot run. Fix the FAIL lines above.")
    elif failed_steps:
        print("BROKEN - the toolchain is present but the pipeline did not pass its own gates.")
    elif degraded:
        print("READY, with gaps - the core pipeline works. "
              "Read what each gap disables before deciding to ignore it.")
    else:
        print("READY - everything works, including the PDF path.")
    return 1 if (blocked or failed_steps) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
