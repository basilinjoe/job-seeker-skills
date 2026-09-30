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

The levers are domain/render/fit_levers.py, the fit application/render/fit_pages.py and
the command adapters/cli/fit.py. This module keeps the path, the levers' names, and the
TeX engine as `compile_pdf` and `available_engine`, which a test patches here (Ruling 4
of the onion design).
"""
import sys

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
from ..infra.tex import available_engine, compile_pdf


class Tex:
    """The TeX engine as this module names it, looked up at each call.

    A test patches fit_pages.compile_pdf and .available_engine, so the fit is handed
    this rather than infra.tex itself: the patches are then what it compiles with.
    """

    def available_engine(self):
        """The engine compile_pdf would use, or None (infra.tex)."""
        return available_engine()

    def compile_pdf(self, tex_path, out_dir):
        """(the PDF's path or None, a note), from this module's compile_pdf (infra.tex)."""
        return compile_pdf(tex_path, out_dir)


def main(argv=None):
    """`jsk fit` (adapters.cli.fit.main), with this module's TeX engine."""
    from ..adapters.cli.fit import main as fit

    return fit(argv, tex=Tex())


if __name__ == "__main__":
    sys.exit(main())
