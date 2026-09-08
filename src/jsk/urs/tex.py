"""Compiling a .tex to a PDF.

Shared by render_resume.py and fit_pages.py so the two cannot disagree about
which engine ran or how it was invoked. A fitter that measures a PDF built
differently from the one that ships is exactly the defect this module exists to
prevent - the page count has to describe the artefact being sent.

Standard library only. The engines themselves are external and optional; their
absence is reported, never assumed away.
"""
import os
import shutil
import subprocess

# Order matters: the first engine present wins. tectonic is a single
# self-contained binary, which is why it leads.
#
# The last two are the reason preflight.py advertises five engines: it always
# did, while render_resume.py only ever tried three, so a machine with nothing
# but xelatex was told it could render and then could not.
TEX_ENGINES = [
    ("tectonic", ["tectonic", "--keep-logs", "-o"]),
    ("latexmk", ["latexmk", "-pdf", "-interaction=nonstopmode", "-outdir"]),
    ("pdflatex", ["pdflatex", "-interaction=nonstopmode", "-output-directory"]),
    ("xelatex", ["xelatex", "-interaction=nonstopmode", "-output-directory"]),
    ("lualatex", ["lualatex", "-interaction=nonstopmode", "-output-directory"]),
]

TIMEOUT = 180

NO_ENGINE = ("no TeX engine found ("
             + ", ".join(name for name, _ in TEX_ENGINES)
             + ") - the .tex is written but unrendered, so the resume is UNVERIFIED")


def available_engine():
    """The engine compile_pdf would use, or None."""
    for name, _ in TEX_ENGINES:
        if shutil.which(name):
            return name
    return None


def pdf_path_for(tex_path, out_dir):
    """Where every engine puts the PDF: out_dir, named after the .tex."""
    stem = os.path.splitext(os.path.basename(tex_path))[0]
    return os.path.join(os.path.abspath(out_dir), stem + ".pdf")


def compile_pdf(tex_path, out_dir):
    """Compile with the first engine that produces one. Returns (pdf_path, note).

    Paths are absolutised because the engines run with `cwd=out_dir`: a relative
    `-o out_dir` resolved against itself, so `--out rel_dir` failed while the
    caller saw nothing but a note and an exit code of 0.

    A stale PDF is removed first, so "the file exists" means this run wrote it.
    An engine that exits non-zero is not trusted even when a PDF appears - a
    partial resume is worse than none, because it looks like a whole one.
    """
    tex_path = os.path.abspath(tex_path)
    out_dir = os.path.abspath(out_dir)
    pdf = pdf_path_for(tex_path, out_dir)

    tried = []
    for name, base in TEX_ENGINES:
        if not shutil.which(name):
            continue
        try:
            os.remove(pdf)
        except OSError:
            pass
        try:
            proc = subprocess.run(base + [out_dir, tex_path], cwd=out_dir,
                                  capture_output=True, text=True, timeout=TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as e:
            tried.append(f"{name} failed to run: {e}")
            continue
        if proc.returncode == 0 and os.path.exists(pdf):
            return pdf, f"compiled with {name}"
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        tried.append(f"{name} produced no PDF:\n    " + "\n    ".join(tail))

    if not tried:
        return None, NO_ENGINE
    # Every engine present was tried; report each, because "tectonic failed" is
    # not the same problem as "tectonic failed and so did pdflatex".
    return None, "UNVERIFIED - " + "\n  ".join(tried)
