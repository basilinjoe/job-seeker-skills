"""Fitting a rendered .tex to a page budget: the levers applied in order, each measured.

The levers and the measurements are domain/render/fit_levers.py's. This stages each
candidate in a scratch directory, compiles it with the TeX engine, measures the PDF, and
writes the first one inside the budget. It prints nothing: adapters/cli/fit.py says what
it did.
"""
import os
from dataclasses import dataclass
from typing import Any

from ...domain.record.parsed import Unreadable
from ...domain.render.fit_levers import (BODY_FONT, FONT_FLOOR_PT, MARGIN, MARGIN_FLOOR_IN,
                                         apply_state, body_font_pt, current_margin_in,
                                         diagnose, lever_plan, lines_over)


class FitStopped(Exception):
    """A fit that could not start: `kind` says why.

    "unreadable" (`detail` and `fix` say what and what to do), "no-levers" (the .tex was
    not written by emit_latex.py), "no-engine" (no TeX engine) or "no-pdf-library"
    (nothing to measure a PDF with). Each is exit 2: the page count is unknowable.
    """

    def __init__(self, kind, detail="", fix=""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail
        self.fix = fix


@dataclass(frozen=True)
class FitStep:
    """One lever tried: its place in the plan, its label, and the pages it came to."""

    number: int
    label: str
    pages: int | None           # None when the candidate did not compile
    note: str                   # what the TeX engine said


@dataclass(frozen=True)
class FitResult:
    """How a fit went.

    `outcome` is "no-baseline" (the unmodified .tex did not compile), "fits" (already
    inside the budget), "dry-run" (measured only), "broke" (a candidate stopped
    compiling), "floor" (every lever at its floor, still over) or "fitted" (written to
    `out`).
    """

    name: str                   # the .tex's file name
    target: int
    engine: str
    outcome: str
    note: str = ""              # the baseline's compile note, for "no-baseline"
    baseline: tuple = ()        # the unmodified render's pages, as fit_levers measures them
    gap: dict | None = None     # fit_levers.diagnose over the baseline
    steps: tuple = ()           # FitStep, in the order tried
    over: int = 0               # body lines over the budget at the floors, for "floor"
    final: tuple = ()           # the fitted render's pages
    applied: tuple | None = None    # the lever state that fitted
    font_pt: float | None = None
    margin_in: float | None = None
    out: str = ""


def fit_pages(tex_path, target, *, dry_run, out, files, tex, reader, outputs):
    """Fit the .tex at `tex_path` to `target` pages.

    Args:
        tex_path: the .tex the deliverable PDF is compiled from.
        target: the page budget, at least 1.
        dry_run: measure and diagnose only.
        out: where the fitted .tex goes.
        files: reads the .tex (ports.files.TextFiles).
        tex: compiles each candidate (ports.tex.TexCompiler).
        reader: measures each PDF (ports.pdf.PdfInspector).
        outputs: stages the candidates and writes the result (ports.outputs.RenderOutputs).

    Returns:
        A FitResult. Compiles in a scratch directory; writes `out` only when it fits.

    Raises:
        FitStopped: the .tex cannot be read or has no levers, or there is no TeX engine
            or PDF reader to measure with.
    """
    try:
        original = files.read_text(tex_path)
    except Unreadable as e:
        raise FitStopped("unreadable", str(e), e.fix) from None
    if not BODY_FONT.search(original) or not MARGIN.search(original):
        raise FitStopped("no-levers")
    engine = tex.available_engine()
    if not engine:
        raise FitStopped("no-engine")
    if not reader.available():
        raise FitStopped("no-pdf-library")

    head: dict[str, Any] = {"name": os.path.basename(tex_path), "target": target,
                            "engine": engine}
    with outputs.scratch() as tmp:
        def measure(state, label):
            """Write the state to a scratch .tex, compile it, and measure. None on failure."""
            staged = apply_state(original, state) if state else original
            candidate = os.path.join(tmp, f"{label}.tex")
            outputs.write_text(candidate, staged)
            pdf, note = tex.compile_pdf(candidate, tmp)
            if not pdf:
                return None, staged, note
            return reader.measure(pdf), staged, note

        pages, _, note = measure(None, "baseline")
        if pages is None:
            return FitResult(**head, outcome="no-baseline", note=note)

        # The margin is the same on all four sides in this template.
        gap = diagnose(pages, target, (current_margin_in(original) or 0.0) * 72.0)
        head.update(baseline=tuple(pages), gap=gap)
        if len(pages) <= target:
            return FitResult(**head, outcome="fits")
        if dry_run:
            return FitResult(**head, outcome="dry-run")
        return levered(head, original, pages, measure, out, outputs)


def levered(head, original, pages, measure, out, outputs):
    """The levers applied in plan order until one fits, one breaks, or all are spent.

    Args:
        head: the FitResult fields known before the levers.
        original: the .tex's text.
        pages: the baseline's pages.
        measure: (state, label) -> (pages or None, staged text, note).
        out: where a fitted .tex goes.
        outputs: writes it (ports.outputs.RenderOutputs).

    Returns:
        A FitResult: "broke", "floor" or "fitted". Writes `out` when it fits.
    """
    target, steps = head["target"], []
    last = (pages, original)                  # the furthest the levers got
    for i, (label, state) in enumerate(lever_plan(), 1):
        measured, staged, note = measure(state, f"step{i}")
        if measured is None:
            # A compile failure is an environment problem, not a document that is too
            # dense. Reporting it as the latter sent people to cut evidence over a broken
            # toolchain.
            steps.append(FitStep(i, label, None, note))
            return FitResult(**head, outcome="broke", steps=tuple(steps))
        steps.append(FitStep(i, label, len(measured), note))
        last = (measured, staged)
        if len(measured) <= target:
            outputs.write_text(out, staged)
            return FitResult(**head, outcome="fitted", steps=tuple(steps),
                             final=tuple(measured), applied=state,
                             font_pt=body_font_pt(staged), margin_in=current_margin_in(staged),
                             out=out)

    floor_pages, floor_tex = last
    over = lines_over(floor_pages, target,
                      (current_margin_in(floor_tex) or MARGIN_FLOOR_IN) * 72.0,
                      (body_font_pt(floor_tex) or FONT_FLOOR_PT) * 1.2)
    return FitResult(**head, outcome="floor", steps=tuple(steps), over=over)
