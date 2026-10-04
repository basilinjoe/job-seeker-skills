"""The resume_fit tool's TeX engine, bound.

The fit is application/render/fit_pages.py and the command adapters/entry/fit.py. A test
patches `compile_pdf` and `available_engine` here, so the fit is handed this module's Tex,
which looks both up at each call (Ruling 4 of the onion design).
"""
from ...infra.tex import available_engine, compile_pdf


class Tex:
    """The TeX engine as this module names it, looked up at each call.

    A test patches compose.fit.compile_pdf and .available_engine, so the fit is handed
    this rather than infra.tex itself: the patches are then what it compiles with.
    """

    def available_engine(self):
        """The engine compile_pdf would use (infra.tex).

        Returns:
            Its name, or None when no TeX engine is installed.
        """
        return available_engine()

    def compile_pdf(self, tex_path, out_dir):
        """Compile a .tex with this module's compile_pdf (infra.tex).

        Args:
            tex_path: the .tex.
            out_dir: where the PDF goes.

        Returns:
            (the PDF's path or None, a note). Runs the TeX engine.
        """
        return compile_pdf(tex_path, out_dir)
