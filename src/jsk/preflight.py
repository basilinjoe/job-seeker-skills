#!/usr/bin/env python3
"""Report what this machine can actually do, and what each gap disables.

Usage: jsk doctor [--quick] [--kb PATH] [--json]
       python -m jsk doctor [the same flags], where `jsk` is not on PATH
       --quick    check the toolchain without the end-to-end render, which it runs
                  otherwise: the shipped example rendered, and every gate over it
       --kb       check a specific career/store/ (or its workspace) rather than searching
       --json     machine-readable output

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
from .paths import EXAMPLE_SELECTION, EXAMPLE_TARGET, EXAMPLE_WORKSPACE, SCHEMA_DIR as SCHEMA

HERE = os.path.dirname(os.path.abspath(__file__))

MIN_PYTHON = (3, 10)

# The whole career, in one store: career/store/ in a workspace. A workspace from before
# the store holds career/kb.ttl instead, which nothing reads until `jsk kb load` imports it.
STORE_DIRNAME = "store"
GRAPH_KB_FILENAME = "kb.ttl"

# Module names rather than filenames since these became a package. A filename check
# answered "is this file on disk", which stopped being the interesting question: a
# module can be present and unimportable - a syntax error, a missing dependency of
# its own, a half-finished editable checkout - and find_spec is what notices.
#
# The packages, never a module inside one: the rings, and the packages that still hold code
# (Ruling 4 of docs/superpowers/specs/2026-09-30-onion-architecture-design.md). Internal
# modules move between rings, and a list that named them would report a sound install broken
# after every move. find_spec answers "is the code here" without importing the package, even
# on a machine without the engine - the engine is its own check below.
MODULES = ["cli", "paths", "domain", "ports", "application", "infra", "adapters"]
GRAPH_MODULES = ["domain.record", "application.record", "infra.oxigraph"]
GATE_MODULES = ["domain.gates", "application.gates"]
# The renderer's ring packages: the plan builder, the emitters and the use cases that drive
# them. A render with no builder is as broken as one with no emitter, so they are one check.
RENDER_MODULES = ["domain.resume", "domain.render", "application.render"]

SCHEMA_FILES = ["profile.schema.json"]
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
                   "note": "The graph engine: holds the career in career/store/, and reads, "
                           "validates and queries it and the applications. A dependency "
                           "of jsk-resume, so a missing one "
                           "means the install skipped dependencies."},
    "mcp": {"pip": "jsk-resume",
            "note": "The SDK `jsk mcp` serves the career through: its tools are the only "
                    "way to change a career since 6.0. A dependency of jsk-resume, so a "
                    "missing one means the install skipped dependencies."},
}


def module_available(name):
    try:
        __import__(name)
        return True
    except Exception:  # noqa: BLE001 - a broken install raises anything; doctor reports it missing
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
        except Exception:  # noqa: BLE001 - a broken subpackage raises; the same finding (see above)
            missing.append(name)
    return missing


def which_any(names):
    for n in names:
        path = shutil.which(n)
        if path:
            return n, path
    return None, None


def walk_for(start, found):
    """The first path `found(root, files)` returns, three directories down at most."""
    start = os.path.abspath(start)
    for root, dirs, files in os.walk(start):
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "__", "node_modules")))
        if depth(root, start) > 3:
            dirs[:] = []
            continue
        hit = found(root, files)
        if hit:
            return hit
    return None


def record_in(career):
    """The record a `career` folder holds: its store/, else - a workspace not yet loaded
    into one - its kb.ttl, else None."""
    store = os.path.join(career, STORE_DIRNAME)
    if os.path.isdir(store):
        return store
    kb = os.path.join(career, GRAPH_KB_FILENAME)
    return kb if os.path.isfile(kb) else None


def is_store(path):
    return os.path.basename(os.path.normpath(path)) == STORE_DIRNAME


def find_kb(start="."):
    """The career record, `career/store/`, found by its name and its folder - or a
    workspace's `career/kb.ttl` from before the store, which is found so it can be named.

    Searched for by name rather than by a directory shape. A bundle used to be
    recognised by the folders inside it, which meant a half-created one - `projects/`
    made, `resume-generation/` not yet - was invisible to this check and reported as
    "no bundle" while the person was looking straight at it. `store` alone is not
    enough of a name, nor `kb.ttl` - `.jsk/kb.last.ttl` was a cache, and a stray one
    elsewhere is nobody's career - so they count only inside a folder named `career`.
    """
    return walk_for(start, lambda root, files: record_in(root)
                    if os.path.basename(root) == "career" else None)


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


# The two packages jsk-resume requires, and what a machine without each loses.
#   pyoxigraph: the career is in career/store/, which only it opens. Every render builds from
#     it, the resume_ship tool runs the record gate against it before it renders, and `jsk kb`
#     and `jsk mcp` start there, so without it no resume comes from the career at all.
#   mcp: since 6.0 `jsk mcp`'s tools are the only way to change a career - the CLI's
#     `jsk kb apply` and `confirm` went with them - so without the SDK nothing is written.
DEPENDENCIES = {
    "pyoxigraph": "cannot open, read or validate the graph record (career/store/): `jsk kb`, "
                  "`jsk mcp` and every render and record gate cannot start",
    "mcp": "`jsk mcp` cannot start, so the agents' graph tools are gone and with them every "
           "way to change the career",
}


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

    missing_mod = present(RENDER_MODULES)
    checks.append(Check(
        "renderer package", not missing_mod,
        disables=f"missing: {', '.join(missing_mod)}" if missing_mod
                 else "", detail=os.path.join(HERE, "domain", "render")))

    missing_graph = present(GRAPH_MODULES)
    checks.append(Check(
        "graph record package", not missing_graph,
        disables=f"missing: {', '.join(missing_graph)}" if missing_graph
                 else "", detail=os.path.join(HERE, "domain", "record")))

    missing_gates = present(GATE_MODULES)
    checks.append(Check(
        "gates package", not missing_gates,
        disables=f"missing: {', '.join(missing_gates)}" if missing_gates
                 else "", detail=os.path.join(HERE, "domain", "gates")))

    missing_schema = [f for f in SCHEMA_FILES if not os.path.exists(os.path.join(SCHEMA, f))]
    missing_prof = [p for p in PROFILES
                    if not os.path.exists(os.path.join(SCHEMA, "profiles", p))]
    checks.append(Check(
        f"profile schema and {len(PROFILES) - len(missing_prof)} region profiles",
        not (missing_schema or missing_prof),
        disables=f"missing: {', '.join(missing_schema + missing_prof)}"
                 if (missing_schema or missing_prof) else ""))

    engine, path = which_any(TEX_ENGINES)
    checks.append(Check(
        f"TeX engine ({engine})" if engine else "TeX engine", bool(engine), key="tex",
        disables="no PDF at all. The PDF is the only rendered deliverable, so "
                 "without an engine there is nothing to send, nothing to check "
                 "and nothing to measure - the resume_render tool with pdf=True reports "
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

    # REQUIRED, and dependencies of jsk-resume, so a missing one means the install skipped
    # dependencies (DEPENDENCIES says what each costs). find_spec, not an import - this
    # module stays standard-library only.
    for name, disables in DEPENDENCIES.items():
        checks.append(Check(name, importlib.util.find_spec(name) is not None, key=name,
                            disables=disables))

    kb, problem = resolve_kb(kb_arg)
    if kb and is_store(kb):
        # The path once, on the detail line: in the name as well, it printed twice.
        checks.append(Check("knowledge base", True, detail=kb))
    elif kb:
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(kb)))
        checks.append(Check(
            "knowledge base", False,
            disables=f"{kb} is not read any more - the career lives in career/store/. "
                     f"`jsk kb load .` in {workspace} imports it, once"))
    elif problem:
        checks.append(Check("knowledge base", False, disables=problem))
    else:
        checks.append(Check(
            "knowledge base", False,
            disables="nothing to render from yet - `jsk kb new PATH --name NAME` creates "
                     "career/store/"))

    return checks, kb


def resolve_kb(kb_arg=None):
    """(career/store/ - or a career/kb.ttl not yet loaded into one - or None, what is
    wrong with `--kb` or None).

    `--kb` may name the store, or the workspace folder. Anything else is refused by name
    rather than taken on trust: `--kb pyproject.toml` used to report "ok knowledge
    base", and a path that does not exist said there was nothing to render from yet,
    which reads as an empty career rather than a typo. A kb.ttl is taken, so the report
    can say it has not been imported rather than that it is not a career.
    """
    if kb_arg is None:
        return find_kb(), None
    wanted = f"pass career/{STORE_DIRNAME}/, or the workspace folder holding it"
    if not os.path.exists(kb_arg):
        return None, f"--kb {kb_arg} does not exist - {wanted}"
    parent = os.path.dirname(os.path.abspath(kb_arg))
    if os.path.isdir(kb_arg):
        if is_store(kb_arg) and os.path.basename(parent) == "career":
            return kb_arg, None
        found = record_in(os.path.join(kb_arg, "career"))
        if found:
            return found, None
        return None, (f"--kb {kb_arg} holds no career/{STORE_DIRNAME}/, so it is not a "
                      f"career workspace - {wanted}")
    if os.path.basename(kb_arg) == GRAPH_KB_FILENAME:
        return kb_arg, None
    return None, f"--kb {kb_arg} is not a career record - {wanted}"


# LibreOffice used to appear here. It rendered the .docx for page measurement;
# with the .docx gone it has no job left in this pipeline.
#
# A TeX engine and pymupdf moved the other way, from optional to required. They
# were survivable while the .docx was the portal artefact and the PDF was a
# nicety. Now the PDF is the only rendered deliverable, so a machine without
# them cannot produce a resume at all - reporting that as a degraded install
# would be telling someone their toolchain works when it does not.
#
# pyoxigraph is required for the same reason: the career is in its store, and every render
# and the record gate the resume_ship tool runs read it. mcp joined them in 6.0, when its tools
# became the only way to change a career.
REQUIRED = {"Python", "modules", "renderer package", "gates package", "graph record package",
            "profile schema", "TeX engine", "pymupdf", "pyoxigraph", "mcp"}


def is_required(check):
    return any(check.name.startswith(r) for r in REQUIRED)


def verify(tmp):
    """Render the shipped example and run every gate that can run here."""
    steps = []

    # Spawned, not imported: doctor proves each entry point runs from cold. The resume_*
    # tools are not commands since 2026-10-04 (docs/superpowers/plans/2026-10-04-mcp-first.md),
    # so a step runs the entry point the tool calls, in an interpreter of its own, and `jsk kb
    # load` is still a command. Run in the scratch directory, so the workspace around the
    # caller's own directory is not asked whether it is loaded: the example is the only
    # workspace these steps read.
    def spawn(args, prefix):
        proc = subprocess.run([sys.executable, *prefix, *args], capture_output=True,
                              text=True, cwd=tmp)
        return proc.returncode == 0, (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]

    def run(label, args):
        ok, tail = spawn(args, ["-m", __package__])
        steps.append((label, ok, tail))
        return ok

    # What resume_check and resume_render call (adapters/mcp/rendering.py), by the name the
    # tool has, so that a step reads as the tool call it proves.
    entries = {
        "resume_check": f"import sys; from {__package__}.adapters.entry.resume import "
                        f"cmd_resume_check; sys.exit(cmd_resume_check(sys.argv[1:]))",
        "resume_render": f"import sys; from {__package__}.adapters.entry.render import main; "
                         f"sys.exit(main(['render_resume.py'] + sys.argv[1:]))",
    }

    def run_tool(label, tool, args):
        ok, tail = spawn(args, ["-c", entries[tool]])
        steps.append((label, ok, tail))
        return ok

    if not os.path.exists(EXAMPLE_SELECTION):
        steps.append(("example document present", False,
                      [f"{EXAMPLE_SELECTION} missing"]))
        return steps

    # The example ships as files - a package cannot carry a store, whose format is the
    # installed pyoxigraph's - so it is imported into a store of its own, as `jsk kb load`
    # imports a person's, its general resume's selection with it, and everything after reads
    # it from there, as a person's does.
    workspace = os.path.join(tmp, "example")
    os.makedirs(workspace, exist_ok=True)
    if not run("load the example career into a store",
               ["kb", "load", EXAMPLE_WORKSPACE, "--root", workspace]):
        return steps
    # The selection the render reads: validating a record the render did not touch passed
    # a check on the wrong one, when the example was a URS record. The record gate, as
    # the resume_ship tool runs it: shape, ids and every number traced in the example career.
    target = os.path.join(workspace, *EXAMPLE_TARGET.split("/"))
    run_tool("validate the example resume", "resume_check", [target])
    # --pdf, because the PDF is the deliverable: a render that stops at the .tex
    # proves the builder works and nothing about whether anything can be sent.
    ok = run_tool("render the example to a PDF", "resume_render",
                  [target, "--out", tmp, "--pdf"])
    if not ok:
        return steps

    pdf = os.path.join(tmp, "Priya_Raman_Resume.pdf")
    tex = os.path.join(tmp, "Priya_Raman_Resume.tex")
    run_tool("parse gate, rendered PDF", "resume_check", [pdf, "--only", "parse"])
    # No render writes the plain text: the parse gate emits it from the plan in memory, as
    # the resume_check tool runs it. No command takes a selection to that one pass, so its
    # adapter is spawned directly, from cold like the rest, with the record DIR gives it.
    entry = (f"import sys; from {__package__}.adapters.entry.gates.ats import main; "
             f"sys.exit(main(sys.argv[1:]))")
    ref = os.path.join(target, "resume")
    proc = subprocess.run([sys.executable, "-c", entry, ref, "--strict"],
                          capture_output=True, text=True, cwd=tmp)
    steps.append(("parse gate, plain text (strict)", proc.returncode == 0,
                  (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]))
    run_tool("prose gate", "resume_check", [tex, "--only", "prose"])
    # The record names the region, so the paper is checked against it, not warned about.
    run_tool("layout gate", "resume_check",
             [pdf, "--only", "layout", "--record", target])
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
    print(f"python -m {__package__}.preflight was retired: it is jsk doctor now "
          f"(python -m {__package__} doctor)")
    sys.exit(2)
