"""The fit's entry point: its flags parsed, the fit run (application/render/fit_pages.py), the result said.

This module is what the `resume_fit` tool (jsk mcp) calls, through dispatch.call_gate as
`fit_pages.py`. `jsk resume fit` was retired in 6.0 (2026-10-04,
docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 5): it exits 2 naming the tool.

Usage: resume_fit(tex, target_pages=2)
  as arguments: resume.tex [--target-pages 2] [--dry-run] [-o out.tex] [--in-place]

Measures geometry FIRST, then applies levers (domain/render/fit_levers.py), cheapest-looking
first, stopping at the floors `references/ats-rules.md` sets rather than crossing them:
inter-paragraph spacing and bullet spacing (floor 0pt), margins (0.5in), body font size
(10pt). Exit 0 = fits. Exit 1 = cannot fit without breaching a floor; the remedy is to cut
evidence, not to shrink type. Exit 2 = usage or environment error.

It rewrites the .tex and measures the PDF that .tex compiles to, so the page count describes
the artefact that goes out: a .docx measured through LibreOffice once reported 2 pages for
a resume that shipped as a 3-page PDF. Needs a TeX engine and `pymupdf`; with either missing
it reports loudly and exits 2, because a page count nobody measured is a page count nobody
knows. The engine is compose.fit's.
"""
import argparse
import os

from ...domain.render.fit_levers import FONT_FLOOR_PT, MARGIN_FLOOR_IN, describe, fill_percent

# Why a fit could not start, as it is printed (application.render.fit_pages.FitStopped).
STOPPED = {
    "no-levers": ["NO LEVERS FOUND - this .tex was not written by emit_latex.py.",
                  "  fit_pages.py rewrites named knobs in the preamble; without them",
                  "  there is nothing to move. Re-render with render_resume.py."],
    "no-engine": ["NO RENDERER - cannot verify the page count.",
                  "  fit_pages.py needs a TeX engine to compile the .tex to a PDF. Install",
                  "  tectonic, or see preflight.py. Page count is unverifiable without one,",
                  "  so this is reported rather than passed over: treat the resume as "
                  "unfitted."],
    "no-pdf-library": ["NO PDF LIBRARY - cannot measure the render.",
                       "  fit_pages.py needs pymupdf for page geometry:  pip install pymupdf",
                       "  Without it the page count is unverifiable; treat the resume as "
                       "unfitted."],
}

# The exit code for each way a fit ends (application.render.fit_pages.FitResult.outcome).
CODES = {"no-baseline": 2, "fits": 0, "dry-run": 1, "broke": 2, "floor": 1, "fitted": 0}


def parse(argv):
    """The flags, parsed; argparse exits 2 on a bad call and 0 after --help."""
    # prog pinned: the resume_fit tool calls this in process, where sys.argv[0] is the server's.
    ap = argparse.ArgumentParser(
        prog="resume_fit",
        description="Fit a rendered resume to a page budget without breaching the "
                    "10pt / 0.5in floors.")
    ap.add_argument("tex", help="the .tex the deliverable PDF is compiled from")
    ap.add_argument("--target-pages", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and diagnose only; apply nothing")
    ap.add_argument("-o", "--output", help="where to write the fitted file")
    ap.add_argument("--in-place", action="store_true", help="overwrite the input file")
    return ap.parse_args(argv)


def refused(a):
    """The exit code for flags that cannot be run, after printing why; else None."""
    if a.target_pages < 1:
        print("usage: --target-pages must be at least 1")
        return 2
    if not os.path.exists(a.tex):
        print(f"file not found: {a.tex}")
        return 2
    if a.in_place and a.output:
        print("usage: pass either --in-place or -o, not both")
        return 2
    if os.path.splitext(a.tex)[1].lower() != ".tex":
        print(f"not a .tex: {a.tex}")
        print("  fit_pages.py rewrites the LaTeX the deliverable is compiled from.")
        print("  Pass <Name>_Resume.tex, not the PDF it produces.")
        return 2
    return None


def main(argv=None):
    """The resume_fit entry point: fit a rendered .tex to its page budget and say how.

    Args:
        argv: the arguments after the program name; None reads sys.argv.

    Returns:
        The exit code. Prints the report; may write the fitted .tex. The TeX engine is
        compose.fit's, looked up there at each compile.
    """
    from ..compose.fit import Tex

    return fitted(argv, tex=Tex())[0]


def fitted(argv, *, tex):
    """The resume_fit entry point with how it went: the resume_ship tool reads the levers off it.

    Args:
        argv: the arguments after the program name; None reads sys.argv.
        tex: compiles each candidate (ports.tex.TexCompiler).

    Returns:
        (exit code, the FitResult, or None when the fit could not start). Prints the
        report; may write the fitted .tex.

    Raises:
        SystemExit: from argparse, for a bad call or --help.
    """
    from .cliutil import utf8_stdout

    a = parse(argv)
    utf8_stdout()
    code = refused(a)
    if code is not None:
        return code, None

    from ...application.render.fit_pages import FitStopped, fit_pages
    from ...infra import files, outputs, pdf

    out = a.tex if a.in_place else (a.output or os.path.splitext(a.tex)[0] + "-fitted.tex")
    try:
        result = fit_pages(a.tex, a.target_pages, dry_run=a.dry_run, out=out, files=files,
                           tex=tex, reader=pdf, outputs=outputs)
    except FitStopped as stop:
        if stop.kind == "unreadable":
            print(f"not a readable .tex: {stop.detail}")
            print(f"  fix: {stop.fix}")
        else:
            print("\n".join(STOPPED[stop.kind]))
        return 2, None
    report(result)
    return CODES[result.outcome], result


def report_pages(pages, indent="  "):
    """Print each page's fill, one line a page."""
    for i, p in enumerate(pages, 1):
        print(f"{indent}page {i}   fill {fill_percent(p):3.0f}%")


def report_overflow(gap, target, indent="  "):
    """Print what opened the page past the budget and the room the last one had, if any."""
    if not gap:
        return
    print(f"{indent}overflow: page {target + 1} opens with {gap['text']!r} "
          f"({gap['needs']:.0f}pt tall); page {target} had {gap['free']:.0f}pt free")


def report(r):
    """Print a FitResult as the fit reads out: baseline, each lever, the verdict."""
    print(f"fitting: {r.name}   target: {r.target} pages   engine: {r.engine}")
    if r.outcome == "no-baseline":
        print(f"RENDER FAILED - {r.engine} produced no PDF from the unmodified .tex.")
        print(f"  {r.note}")
        return
    print(f"baseline: {len(r.baseline)} pages")
    report_pages(r.baseline)
    report_overflow(r.gap, r.target)
    if r.outcome == "fits":
        print(f"\nPASS - already fits {r.target} pages; no levers applied")
        return
    if r.outcome == "dry-run":
        print("\ndry run - measured only, nothing applied")
        return
    print("\napplying levers:")
    for step in r.steps:
        if step.pages is None:
            print(f"  {step.number:2}  {step.label:<28} render failed - stopping")
            print(f"      {step.note}")
        else:
            print(f"  {step.number:2}  {step.label:<28} {step.pages} pages"
                  f"{'   <- target met' if step.pages <= r.target else ''}")
    {"broke": report_broke, "floor": report_floor, "fitted": report_fitted}[r.outcome](r)


def report_broke(r):
    """Print a fit whose toolchain stopped part-way."""
    print(f"\nRENDER FAILED - {r.engine} stopped compiling part-way through.")
    print("  This is a toolchain failure, not a document that is too long.")


def report_floor(r):
    """Print a fit that reached every floor still over its budget."""
    print(f"\nFAIL - cannot reach {r.target} pages without breaching a floor")
    print(f"  every lever is at its floor: {FONT_FLOOR_PT:g}pt body, "
          f"{MARGIN_FLOOR_IN}in margins")
    print(f"  over by ~{r.over} line{'' if r.over == 1 else 's'} at the floors")
    if r.gap:
        print(f"  page {r.target + 1} still carries {r.gap['text']!r}, "
              f"needing {r.gap['needs']:.0f}pt")
    print("  Remove evidence rather than shrinking type: cut the lowest-ranked")
    print("  bullets per the treatment table in references/mode-tailor.md.")


def report_fitted(r):
    """Print a fit that reached its budget, and the file it wrote."""
    print(f"\nresult: {len(r.final)} pages")
    report_pages(r.final)
    print(f"  levers: {describe(r.applied)}")
    # Each value beside its floor. `floors respected: margins 0.6in` was read, in
    # the Arrow run (2026-09-29), as the floor itself - and three confirmed bullets
    # were cut for room that 0.1in of margin still had.
    print(f"  body font {r.font_pt:g}pt (floor {FONT_FLOOR_PT:g}pt), "
          f"margins {r.margin_in:g}in (floor {MARGIN_FLOOR_IN:g}in)")
    print(f"wrote: {r.out}")
    print(f"\nPASS - fits {r.target} pages")
    print("Recompile that .tex and re-run the resume_check tool on the new PDF, then look at "
          "the render: fitting changes layout, and layout is what the render gate checks.")
