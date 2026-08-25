#!/usr/bin/env python3
"""Render a URS document into a .docx, a .tex (and PDF), or plain text.

Usage:
  python3 render_resume.py resume.json --out DIR [options]

  --view ID          which view to render (default: the first one)
  --format F         docx | latex | txt | all      (default: all)
  --region CC        override the view's region profile, e.g. AU, IN, AE
  --profile P        override format_profile: presentation | ats-maximal | plaintext
  --pdf              compile the .tex with whatever TeX engine is installed
  --name N           basename for the outputs (default: from person.name.full)

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = rendered. Exit 1 = nothing written. Exit 2 = usage error.

Every content decision is made once, in urs/plan.py, and the emitters translate
that plan into markup without choosing anything. Which is the point: a .docx and
a PDF built from one view cannot say different things.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from urs import emit_docx, emit_latex, emit_text, plan as planner  # noqa: E402

TEX_ENGINES = [
    ("tectonic", ["tectonic", "--keep-logs", "-o"]),
    ("latexmk", ["latexmk", "-pdf", "-interaction=nonstopmode", "-outdir"]),
    ("pdflatex", ["pdflatex", "-interaction=nonstopmode", "-output-directory"]),
]

# ats-maximal is what goes into a portal, so it is what gets the .docx and the
# .txt. The presentation variant is what a human reads, so it gets the PDF.
DEFAULT_TARGETS = [
    ("presentation", "latex", "{name}_Resume"),
    ("presentation", "docx", "{name}_Resume"),
    ("ats-maximal", "docx", "{name}_Resume_ATS"),
    ("plaintext", "txt", "{name}_Resume_ATS"),
]


def arg(argv, flag, default=None):
    if flag in argv:
        try:
            return argv[argv.index(flag) + 1]
        except IndexError:
            return default
    return default


def compile_pdf(tex_path, out_dir):
    """Compile with the first engine present. Returns (pdf_path, note)."""
    for name, base in TEX_ENGINES:
        if not shutil.which(name):
            continue
        cmd = base + [out_dir, tex_path]
        try:
            proc = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, f"{name} failed to run: {e}"
        pdf = os.path.splitext(tex_path)[0] + ".pdf"
        if os.path.exists(pdf):
            return pdf, f"compiled with {name}"
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-6:]
        return None, f"{name} produced no PDF:\n    " + "\n    ".join(tail)
    return None, ("no TeX engine found (tectonic, latexmk or pdflatex) - "
                  "the .tex is written but unrendered, so the resume is UNVERIFIED")


def safe_name(text):
    keep = [c if c.isalnum() else "_" for c in (text or "Resume")]
    return "".join(keep).strip("_").replace("__", "_") or "Resume"


def main(argv):
    if len(argv) < 2 or argv[1].startswith("--"):
        print(__doc__.strip().split("\n\n")[1])
        return 2
    src = argv[1]
    if not os.path.exists(src):
        print(f"file not found: {src}")
        return 2

    out_dir = arg(argv, "--out", ".")
    os.makedirs(out_dir, exist_ok=True)
    view_id = arg(argv, "--view")
    fmt = arg(argv, "--format", "all")
    region = arg(argv, "--region")
    profile = arg(argv, "--profile")
    want_pdf = "--pdf" in argv

    with open(src, encoding="utf8") as fh:
        doc = json.load(fh)

    base = arg(argv, "--name") or safe_name(
        ((doc.get("person") or {}).get("name") or {}).get("full"))

    if fmt == "all":
        targets = DEFAULT_TARGETS
    else:
        targets = [(profile or "presentation", fmt, "{name}_Resume")]
    if profile and fmt != "all":
        targets = [(profile, fmt, "{name}_Resume")]

    written, warnings, notes, first = [], [], [], None
    for variant, kind, stem in targets:
        try:
            rendered = planner.build(doc, view_id=view_id, region=region, fmt=variant)
        except KeyError as e:
            print(f"FAIL  {e}")
            return 1
        if first is None:
            first = rendered
        warnings.extend(f"[{variant}/{kind}] {w}" for w in rendered["warnings"])
        stem_name = stem.format(name=base)
        path = os.path.join(out_dir, stem_name)

        if kind == "docx":
            emit_docx.emit(rendered, path + ".docx")
            written.append(path + ".docx")
        elif kind == "latex":
            tex = path + ".tex"
            with open(tex, "w", encoding="utf8") as fh:
                fh.write(emit_latex.emit(rendered))
            written.append(tex)
            if want_pdf:
                pdf, note = compile_pdf(tex, out_dir)
                notes.append(note)
                if pdf:
                    written.append(pdf)
        elif kind == "txt":
            txt = path + ".txt"
            with open(txt, "w", encoding="ascii", errors="replace") as fh:
                fh.write(emit_text.emit(rendered))
            written.append(txt)
        else:
            print(f"unknown --format {kind!r}: use docx, latex, txt or all")
            return 2

    print(f"view: {first['view']}   profile: {first['profile']}   "
          f"page budget: {first['pages']}")
    for path in written:
        print(f"  wrote  {os.path.relpath(path, out_dir)}")
    for note in notes:
        print(f"  note   {note}")

    seen = set()
    unique = [w for w in warnings if not (w in seen or seen.add(w))]
    if unique:
        print(f"\nWARN {len(unique)}")
        for w in unique:
            print("  warn  " + w)

    # Name only files that exist. A hint pointing at a document nobody wrote
    # teaches people the gates are decorative.
    docx = [p for p in written if p.endswith(".docx")]
    if docx:
        print("\nRendered. Now run the gates - a rendered resume is not a checked one:")
        for path in docx:
            name = os.path.basename(path)
            strict = " --strict" if "_ATS" in name else ""
            print(f"  check_ats.py {name}{strict}")
        print(f"  check_prose.py {os.path.basename(docx[0])}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
