"""The resume_preview tool's TeX engine, bound.

The preview is application/render/preview_templates.py and the command
adapters/entry/preview.py. A test patches `compile_pdf` and `available_engine` here, so the
preview is handed this module's Tex, which looks both up at each call (Ruling 4 of the
onion design).
"""
from ...infra.tex import available_engine, compile_pdf


class Tex:
    """The TeX engine as this module names it, looked up at each call.

    A test patches compose.preview.compile_pdf and .available_engine, so the preview is
    handed this rather than infra.tex itself: the patches are then what it runs.
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
