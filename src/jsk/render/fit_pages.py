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
import math
import os
import re
import sys
import tempfile


from .tex import available_engine, compile_pdf
from ..cliutil import utf8_stdout

MARGIN_FLOOR_IN = 0.5
FONT_FLOOR_PT = 10.0

# The four knobs emit_latex.py promises to keep literal and one per line.
SECTION_GAP = re.compile(r"(\\setlength\{\\sectiongap\}\{)([\d.]+)pt(\})")
ENTRY_GAP = re.compile(r"(\\setlength\{\\entrygap\}\{)([\d.]+)pt(\})")
TOPSEP = re.compile(r"(topsep=)([\d.]+)pt")
ITEMSEP = re.compile(r"(itemsep=)([\d.]+)pt")
MARGIN = re.compile(r"(margin=)([\d.]+)(in\])")
BODY_FONT = re.compile(r"(\\fontsize\{)([\d.]+)pt\}\{([\d.]+)pt(\})")


# --- the lever plan -------------------------------------------------------------
#
# A state is (spacing, bullet_spacing, margin_inches, font_delta_points). Each step is
# derived from the ORIGINAL document rather than from the previous step, so repeated
# rounding cannot drift a value past a floor. `None` means "leave this alone".

def lever_plan():
    steps = []
    for f in (0.75, 0.5, 0.25, 0.0):
        steps.append((f"inter-paragraph spacing x{f:g}", (f, None, None, 0)))
    base = 0.0
    for f in (0.5, 0.0):
        steps.append((f"bullet spacing x{f:g}", (base, f, None, 0)))
    for inches in (0.7, 0.6, 0.55, MARGIN_FLOOR_IN):
        steps.append((f"margins {inches:.2f}in", (base, 0.0, inches, 0)))
    for d in (0.5, 1.0):
        steps.append((f"body font -{d:g}pt", (base, 0.0, MARGIN_FLOOR_IN, d)))
    return steps


# --- LaTeX transforms -----------------------------------------------------------
#
# Each is a pure string -> string, so the floors can be tested without a TeX engine.

def _scale(pattern, tex, factor, groups=3):
    def fix(m):
        value = float(m.group(2)) * factor
        tail = "".join(m.group(i) for i in range(3, groups + 1))
        return f"{m.group(1)}{value:g}pt{tail}"
    return pattern.sub(fix, tex)


def scale_spacing(tex, factor):
    """Section and entry gaps. A lever must only ever remove space."""
    tex = _scale(SECTION_GAP, tex, factor)
    return _scale(ENTRY_GAP, tex, factor)


def scale_bullet_spacing(tex, factor):
    tex = _scale(TOPSEP, tex, factor, groups=2)
    return _scale(ITEMSEP, tex, factor, groups=2)


def set_margins(tex, inches):
    """Never below the 0.5in floor, whatever the caller asks for."""
    inches = max(float(inches), MARGIN_FLOOR_IN)
    return MARGIN.sub(lambda m: f"{m.group(1)}{inches:g}{m.group(3)}", tex)


def shrink_font(tex, delta_pt):
    """Lower the body size by delta, never below the 10pt floor."""
    def fix(m):
        size = max(float(m.group(2)) - float(delta_pt), FONT_FLOOR_PT)
        return f"{m.group(1)}{size:g}pt}}{{{size * 1.2:g}pt{m.group(4)}"
    return BODY_FONT.sub(fix, tex)


def apply_state(tex, state):
    spacing, bullet, margin_in, font_delta = state
    if spacing is not None:
        tex = scale_spacing(tex, spacing)
    if bullet is not None:
        tex = scale_bullet_spacing(tex, bullet)
    if margin_in is not None:
        tex = set_margins(tex, margin_in)
    if font_delta:
        tex = shrink_font(tex, font_delta)
    return tex


def describe(state):
    """Every lever a state moves, in plan order, each at the value it sets.

    The plan's labels name only the step that was reached, and each step carries the
    ones before it: "margins 0.60in" is also no paragraph and no bullet spacing. `jsk
    ship` prints this line, so what it says it applied is everything it applied."""
    spacing, bullet, margin_in, font_delta = state
    moved = []
    if spacing is not None:
        moved.append(f"inter-paragraph spacing x{spacing:g}")
    if bullet is not None:
        moved.append(f"bullet spacing x{bullet:g}")
    if margin_in is not None:
        moved.append(f"margins {margin_in:g}in")
    if font_delta:
        moved.append(f"body font -{font_delta:g}pt")
    return ", ".join(moved)


def current_margin_in(tex):
    m = MARGIN.search(tex)
    return float(m.group(2)) if m else None


def body_font_pt(tex):
    m = BODY_FONT.search(tex)
    return float(m.group(2)) if m else None


# --- measurement ----------------------------------------------------------------

def measure_pdf(pdf_path):
    """[{height, bottom, first_text, first_height}] one entry per page, in points."""
    import pymupdf                                    # noqa: PLC0415 - optional dependency

    pages = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            blocks = [b for b in page.get_text("blocks") if (b[4] or "").strip()]
            first = blocks[0] if blocks else None
            pages.append({
                "height": page.rect.height,
                "top": min((b[1] for b in blocks), default=0.0),
                "bottom": max((b[3] for b in blocks), default=0.0),
                "first_text": " ".join((first[4] or "").split())[:60] if first else "",
                "first_height": (first[3] - first[1]) if first else 0.0,
            })
    return pages


def fill_percent(page):
    h = page["height"] or 1
    return 100.0 * page["bottom"] / h


def diagnose(pages, target, bottom_margin_pt):
    """Why the document spills: what opened the overflow page, and what room was left.

    This is the measurement the issue says was taken last instead of first. A block
    held together either fits in the remaining space or it does not, and trimming
    words elsewhere cannot change that unless it frees a whole line.
    """
    if len(pages) <= target or target < 1:
        return None
    spilled = pages[target]
    previous = pages[target - 1]
    free = previous["height"] - bottom_margin_pt - previous["bottom"]
    return {
        "text": spilled["first_text"],
        "needs": spilled["first_height"],
        "free": max(free, 0.0),
    }


def lines_over(pages, target, margin_pt, line_pt):
    """About how many body lines the pages past the budget hold, less the room left
    on the last page inside it. 0 when the document fits.

    The Arrow run (2026-09-29) was told only that it could not fit, and cut three
    confirmed bullets to make room nobody had measured. A line count says how much
    evidence the budget costs, which is what the person deciding the cut needs."""
    if len(pages) <= target or target < 1 or line_pt <= 0:
        return 0
    last = pages[target - 1]
    free = max(last["height"] - margin_pt - last["bottom"], 0.0)
    spill = sum(max(p["bottom"] - p.get("top", margin_pt), 0.0) for p in pages[target:])
    return max(math.ceil((spill - free) / line_pt), 1)


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
