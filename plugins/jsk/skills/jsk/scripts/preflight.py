#!/usr/bin/env python3
"""Report what this machine can actually do, and what each gap disables.

Usage: python3 preflight.py [--verify] [--bundle PATH] [--json]
       --verify   render the shipped example end to end and run every gate
       --bundle   check a specific bundle path rather than searching
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
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.normpath(os.path.join(HERE, ".."))
SCHEMA = os.path.join(SKILL, "schema")
EXAMPLE = os.path.join(SCHEMA, "example.resume.json")

MIN_PYTHON = (3, 8)

SCRIPTS = [
    "init_bundle.py", "validate_bundle.py", "check_ats.py", "check_prose.py",
    "score_projects.py", "fit_pages.py", "validate_urs.py", "render_resume.py",
    "migrate_bundle.py", "pipeline.py", "pipeline_model.py",
]
URS_MODULES = ["__init__.py", "plan.py", "profiles.py",
               "emit_docx.py", "emit_latex.py", "emit_text.py"]
SCHEMA_FILES = ["urs-v1.schema.json", "profile.schema.json", "example.resume.json"]
PROFILES = ["default.json", "au.json", "in.json", "ae.json"]

TEX_ENGINES = ["tectonic", "latexmk", "pdflatex", "xelatex", "lualatex"]
OFFICE = ["soffice", "libreoffice"]

INSTALL = {
    "tex": {
        "win32": "winget install --id TectonicProject.Tectonic",
        "darwin": "brew install tectonic",
        "linux": "cargo install tectonic   # or: apt install texlive-latex-recommended",
        "note": "tectonic is a single self-contained binary; TeX Live and MiKTeX are "
                "gigabytes and only worth it if you already wanted them.",
    },
    "office": {
        "win32": "winget install --id TheDocumentFoundation.LibreOffice",
        "darwin": "brew install --cask libreoffice",
        "linux": "apt install libreoffice-writer",
        "note": "Used only to measure page count and to render the .docx to PDF.",
    },
    "pyyaml": {"pip": "pyyaml", "note": "Reads bundle frontmatter."},
    "jsonschema": {"pip": "jsonschema",
                   "note": "Full URS schema validation. Without it the structural "
                           "rules still run, but a mistyped key is not caught."},
    "pymupdf": {"pip": "pymupdf", "note": "Measures the rendered page fill."},
}


def module_available(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def which_any(names):
    for n in names:
        path = shutil.which(n)
        if path:
            return n, path
    return None, None


def find_bundle(start="."):
    """A bundle is a directory holding both projects/ and resume-generation/."""
    start = os.path.abspath(start)
    for root, dirs, _ in os.walk(start):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__", "node_modules"))]
        if depth(root, start) > 3:
            dirs[:] = []
            continue
        if os.path.isdir(os.path.join(root, "projects")) and \
           os.path.isdir(os.path.join(root, "resume-generation")):
            return root
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


def gather(bundle_arg=None):
    checks = []

    checks.append(Check(
        f"Python {'.'.join(str(v) for v in sys.version_info[:3])}",
        sys.version_info >= MIN_PYTHON,
        disables="everything - this toolchain needs Python "
                 f"{'.'.join(str(v) for v in MIN_PYTHON)} or newer"))

    missing = [s for s in SCRIPTS if not os.path.exists(os.path.join(HERE, s))]
    checks.append(Check(
        f"scripts ({len(SCRIPTS) - len(missing)}/{len(SCRIPTS)})", not missing,
        disables=f"missing: {', '.join(missing)}" if missing else "",
        detail=HERE))

    urs_dir = os.path.join(HERE, "urs")
    missing_mod = [m for m in URS_MODULES if not os.path.exists(os.path.join(urs_dir, m))]
    checks.append(Check(
        "urs renderer package", not missing_mod,
        disables=f"missing: {', '.join(missing_mod)}" if missing_mod
                 else "", detail=urs_dir))

    missing_schema = [f for f in SCHEMA_FILES if not os.path.exists(os.path.join(SCHEMA, f))]
    missing_prof = [p for p in PROFILES
                    if not os.path.exists(os.path.join(SCHEMA, "profiles", p))]
    checks.append(Check(
        f"URS schema and {len(PROFILES) - len(missing_prof)} region profiles",
        not (missing_schema or missing_prof),
        disables=f"missing: {', '.join(missing_schema + missing_prof)}"
                 if (missing_schema or missing_prof) else ""))

    checks.append(Check(
        "pyyaml", module_available("yaml"), key="pyyaml",
        disables="validate_bundle.py and score_projects.py cannot run, so the "
                 "bundle goes unchecked and tailoring falls back to guesswork"))

    checks.append(Check(
        "jsonschema", module_available("jsonschema"), key="jsonschema",
        disables="URS structural rules still run, but a mistyped key is not "
                 "caught - and an ignored key is a field that silently vanishes"))

    engine, path = which_any(TEX_ENGINES)
    checks.append(Check(
        f"TeX engine ({engine})" if engine else "TeX engine", bool(engine), key="tex",
        disables="no PDF from LaTeX. render_resume.py --pdf writes the .tex and "
                 "reports the resume UNVERIFIED, which is correct and still means "
                 "nobody has looked at a rendered page",
        detail=path or ""))

    office, opath = which_any(OFFICE)
    checks.append(Check(
        f"LibreOffice ({office})" if office else "LibreOffice", bool(office),
        key="office",
        disables="fit_pages.py cannot measure the render, so a page budget is a "
                 "guess rather than a measurement",
        detail=opath or ""))

    # The module name fit_pages.py actually imports. Probing the legacy `fitz`
    # alias instead answers a different question and prints a deprecation
    # warning while doing it.
    checks.append(Check(
        "pymupdf", module_available("pymupdf"), key="pymupdf",
        disables="fit_pages.py cannot read per-page fill"))

    bundle = bundle_arg or find_bundle()
    checks.append(Check(
        f"career bundle at {bundle}" if bundle else "career bundle", bool(bundle),
        disables="nothing to render from yet - setup mode creates one",
        detail=bundle or ""))

    return checks, bundle


REQUIRED = {"Python", "scripts", "urs renderer package", "URS schema"}


def is_required(check):
    return any(check.name.startswith(r) for r in REQUIRED)


def verify(tmp):
    """Render the shipped example and run every gate that can run here."""
    steps = []

    def run(label, args):
        proc = subprocess.run([sys.executable] + args, capture_output=True, text=True)
        steps.append((label, proc.returncode == 0,
                      (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]))
        return proc.returncode == 0

    if not os.path.exists(EXAMPLE):
        steps.append(("example document present", False, ["schema/example.resume.json missing"]))
        return steps

    run("validate the example record",
        [os.path.join(HERE, "validate_urs.py"), EXAMPLE, "--level", "2"])
    ok = run("render every format",
             [os.path.join(HERE, "render_resume.py"), EXAMPLE, "--out", tmp,
              "--view", "view_au_default"])
    if not ok:
        return steps

    presentation = os.path.join(tmp, "Priya_Raman_Resume.docx")
    ats = os.path.join(tmp, "Priya_Raman_Resume_ATS.docx")
    run("parse gate, presentation variant", [os.path.join(HERE, "check_ats.py"), presentation])
    run("parse gate, ATS variant (strict)",
        [os.path.join(HERE, "check_ats.py"), ats, "--strict"])
    run("prose gate", [os.path.join(HERE, "check_prose.py"), presentation])
    return steps


def main(argv):
    as_json = "--json" in argv
    bundle_arg = None
    if "--bundle" in argv:
        try:
            bundle_arg = argv[argv.index("--bundle") + 1]
        except IndexError:
            print("--bundle needs a path")
            return 2

    checks, bundle = gather(bundle_arg)
    blocked = [c for c in checks if not c.ok and is_required(c)]
    degraded = [c for c in checks if not c.ok and not is_required(c)]

    steps = []
    if "--verify" in argv and not blocked:
        with tempfile.TemporaryDirectory() as tmp:
            steps = verify(tmp)

    if as_json:
        print(json.dumps({
            "ok": not blocked and all(s[1] for s in steps),
            "bundle": bundle,
            "checks": [{"name": c.name, "ok": c.ok, "required": is_required(c),
                        "disables": c.disables} for c in checks],
            "verify": [{"step": s[0], "ok": s[1]} for s in steps],
        }, indent=2))
        return 1 if blocked or any(not s[1] for s in steps) else 0

    print("career-okf preflight")
    print(f"skill: {SKILL}\n")
    for c in checks:
        mark = "ok  " if c.ok else ("FAIL" if is_required(c) else "gap ")
        print(f"  {mark}  {c.name}")
        if c.ok and c.detail and c.detail != SKILL:
            print(f"           {c.detail}")
        if not c.ok and c.disables:
            print(f"           {c.disables}")

    if degraded:
        print("\nTo close the gaps:")
        for c in degraded:
            if not c.key:
                continue
            line, note = hint(c.key)
            if line:
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
