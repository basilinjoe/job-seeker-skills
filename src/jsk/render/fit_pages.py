#!/usr/bin/env python3
"""Fit a rendered resume to a page budget by applying density levers in a fixed order.

Usage: jsk fit resume.tex [--target-pages 2] [--dry-run] [-o out.tex] [--in-place]
       python -m jsk.render.fit_pages resume.tex [the same flags]

Measures geometry FIRST, then applies levers, cheapest-looking first, stopping at the
floors `references/ats-rules.md` sets rather than crossing them:

    1  inter-paragraph spacing   floor 0pt
    2  bullet spacing            floor 0pt
    3  margins                   floor 0.5in
    4  body font size            floor 10pt

Exit 0 = fits.  Exit 1 = cannot fit without breaching a floor; the remedy is to cut
evidence, not to shrink type.  Exit 2 = usage or environment error.

This measured a .docx through LibreOffice while the deliverable was a PDF built by
LaTeX from the same record. The two did not agree: a document this reported as 2
pages shipped as a 3-page PDF, and the one gate whose job is to check what a page
looks like was passing on a document nobody was sending. It now rewrites the .tex
and measures the PDF that .tex compiles to, so the page count describes the artefact
that goes out.

Needs a TeX engine and `pymupdf`. Both are external; with either missing this reports
loudly and exits 2, because a page count nobody measured is a page count nobody knows.
"""
import argparse
import os
import sys
import tempfile


from ..infra.pdf import measure as measure_pdf
from ..infra.tex import available_engine, compile_pdf
from ..cliutil import utf8_stdout

from ..domain.render.fit_levers import BODY_FONT as BODY_FONT
from ..domain.render.fit_levers import ENTRY_GAP as ENTRY_GAP
from ..domain.render.fit_levers import FONT_FLOOR_PT as FONT_FLOOR_PT
from ..domain.render.fit_levers import ITEMSEP as ITEMSEP
from ..domain.render.fit_levers import MARGIN as MARGIN
from ..domain.render.fit_levers import MARGIN_FLOOR_IN as MARGIN_FLOOR_IN
from ..domain.render.fit_levers import SECTION_GAP as SECTION_GAP
from ..domain.render.fit_levers import TOPSEP as TOPSEP
from ..domain.render.fit_levers import apply_state as apply_state
from ..domain.render.fit_levers import body_font_pt as body_font_pt
from ..domain.render.fit_levers import current_margin_in as current_margin_in
from ..domain.render.fit_levers import describe as describe
from ..domain.render.fit_levers import diagnose as diagnose
from ..domain.render.fit_levers import fill_percent as fill_percent
from ..domain.render.fit_levers import lever_plan as lever_plan
from ..domain.render.fit_levers import lines_over as lines_over
from ..domain.render.fit_levers import scale_bullet_spacing as scale_bullet_spacing
from ..domain.render.fit_levers import scale_spacing as scale_spacing
from ..domain.render.fit_levers import set_margins as set_margins
from ..domain.render.fit_levers import shrink_font as shrink_font


# --- reporting ------------------------------------------------------------------

def report_pages(pages, indent="  "):
    for i, p in enumerate(pages, 1):
        print(f"{indent}page {i}   fill {fill_percent(p):3.0f}%")


def report_overflow(gap, target, indent="  "):
    if not gap:
        return
    print(f"{indent}overflow: page {target + 1} opens with {gap['text']!r} "
          f"({gap['needs']:.0f}pt tall); page {target} had {gap['free']:.0f}pt free")


def main(argv=None):
    # prog pinned: `jsk fit` calls this in process, where sys.argv[0] is jsk's own.
    ap = argparse.ArgumentParser(
        prog="fit_pages.py",
        description="Fit a rendered resume to a page budget without breaching the "
                    "10pt / 0.5in floors.")
    ap.add_argument("tex", help="the .tex the deliverable PDF is compiled from")
    ap.add_argument("--target-pages", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and diagnose only; apply nothing")
    ap.add_argument("-o", "--output", help="where to write the fitted file")
    ap.add_argument("--in-place", action="store_true", help="overwrite the input file")
    a = ap.parse_args(argv)

    utf8_stdout()

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

    from ..infra.files import Unreadable, read_text
    try:
        original = read_text(a.tex)
    except Unreadable as e:
        print(f"not a readable .tex: {e}")
        print(f"  fix: {e.fix}")
        return 2

    if not BODY_FONT.search(original) or not MARGIN.search(original):
        print("NO LEVERS FOUND - this .tex was not written by emit_latex.py.")
        print("  fit_pages.py rewrites named knobs in the preamble; without them")
        print("  there is nothing to move. Re-render with render_resume.py.")
        return 2

    engine = available_engine()
    if not engine:
        print("NO RENDERER - cannot verify the page count.")
        print("  fit_pages.py needs a TeX engine to compile the .tex to a PDF. Install")
        print("  tectonic, or see preflight.py. Page count is unverifiable without one,")
        print("  so this is reported rather than passed over: treat the resume as unfitted.")
        return 2
    try:
        import pymupdf                                # noqa: F401,PLC0415
    except ImportError:
        print("NO PDF LIBRARY - cannot measure the render.")
        print("  fit_pages.py needs pymupdf for page geometry:  pip install pymupdf")
        print("  Without it the page count is unverifiable; treat the resume as unfitted.")
        return 2

    name = os.path.basename(a.tex)
    print(f"fitting: {name}   target: {a.target_pages} pages   engine: {engine}")

    with tempfile.TemporaryDirectory() as tmp:
        def measure(state, label):
            """Write the state to a scratch .tex, compile it, and measure. None on failure."""
            staged = apply_state(original, state) if state else original
            candidate = os.path.join(tmp, f"{label}.tex")
            with open(candidate, "w", encoding="utf-8") as fh:
                fh.write(staged)
            pdf, note = compile_pdf(candidate, tmp)
            if not pdf:
                return None, staged, note
            return measure_pdf(pdf), staged, note

        pages, _, note = measure(None, "baseline")
        if pages is None:
            print(f"RENDER FAILED - {engine} produced no PDF from the unmodified .tex.")
            print(f"  {note}")
            return 2

        # The margin is the same on all four sides in this template.
        bottom_margin = (current_margin_in(original) or 0.0) * 72.0
        print(f"baseline: {len(pages)} pages")
        report_pages(pages)
        report_overflow(diagnose(pages, a.target_pages, bottom_margin), a.target_pages)

        if len(pages) <= a.target_pages:
            print(f"\nPASS - already fits {a.target_pages} pages; no levers applied")
            return 0
        if a.dry_run:
            print("\ndry run - measured only, nothing applied")
            return 1

        print("\napplying levers:")
        applied, final, final_tex, broke = None, None, None, False
        last = (pages, original)                  # the furthest the levers got
        for i, (label, state) in enumerate(lever_plan(), 1):
            measured, staged, note = measure(state, f"step{i}")
            if measured is None:
                # A compile failure is an environment problem, not a document that
                # is too dense. Reporting it as the latter sent people to cut
                # evidence over a broken toolchain.
                print(f"  {i:2}  {label:<28} render failed - stopping")
                print(f"      {note}")
                broke = True
                break
            print(f"  {i:2}  {label:<28} {len(measured)} pages"
                  f"{'   <- target met' if len(measured) <= a.target_pages else ''}")
            last = (measured, staged)
            if len(measured) <= a.target_pages:
                applied, final, final_tex = state, measured, staged
                break

        if broke:
            print(f"\nRENDER FAILED - {engine} stopped compiling part-way through.")
            print("  This is a toolchain failure, not a document that is too long.")
            return 2

        if final is None:
            gap = diagnose(pages, a.target_pages, bottom_margin)
            floor_pages, floor_tex = last
            over = lines_over(floor_pages, a.target_pages,
                              (current_margin_in(floor_tex) or MARGIN_FLOOR_IN) * 72.0,
                              (body_font_pt(floor_tex) or FONT_FLOOR_PT) * 1.2)
            print(f"\nFAIL - cannot reach {a.target_pages} pages without breaching a floor")
            print(f"  every lever is at its floor: {FONT_FLOOR_PT:g}pt body, "
                  f"{MARGIN_FLOOR_IN}in margins")
            print(f"  over by ~{over} line{'' if over == 1 else 's'} at the floors")
            if gap:
                print(f"  page {a.target_pages + 1} still carries {gap['text']!r}, "
                      f"needing {gap['needs']:.0f}pt")
            print("  Remove evidence rather than shrinking type: cut the lowest-ranked")
            print("  bullets per the treatment table in references/mode-tailor.md.")
            return 1

        out = a.tex if a.in_place else (
            a.output or os.path.splitext(a.tex)[0] + "-fitted.tex")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(final_tex)

        print(f"\nresult: {len(final)} pages")
        report_pages(final)
        print(f"  levers: {describe(applied)}")
        # Each value beside its floor. `floors respected: margins 0.6in` was read, in
        # the Arrow run (2026-09-29), as the floor itself - and three confirmed bullets
        # were cut for room that 0.1in of margin still had.
        print(f"  body font {body_font_pt(final_tex):g}pt (floor {FONT_FLOOR_PT:g}pt), "
              f"margins {current_margin_in(final_tex):g}in (floor {MARGIN_FLOOR_IN:g}in)")
        print(f"wrote: {out}")
        print(f"\nPASS - fits {a.target_pages} pages")
        print("Recompile that .tex and re-run check_ats.py on the new PDF, then look at "
              "the render: fitting changes layout, and layout is what the render gate checks.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
