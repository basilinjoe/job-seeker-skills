#!/usr/bin/env python3
"""`jsk resume preview`'s old module path: where its ports are bound until P6.

The command is adapters/cli/preview.py and the preview application/render/
preview_templates.py; this module keeps the path, and the TeX engine as `compile_pdf`
and `available_engine`, which a test patches here (Ruling 4 of the onion design).
"""
import sys

from ..infra.tex import available_engine, compile_pdf


class Tex:
    """The TeX engine as this module names it, looked up at each call.

    A test patches preview_templates.compile_pdf and .available_engine, so the preview
    is handed this rather than infra.tex itself: the patches are then what it runs.
    """

    def available_engine(self):
        """The engine compile_pdf would use, or None (infra.tex)."""
        return available_engine()

    def compile_pdf(self, tex_path, out_dir):
        """(the PDF's path or None, a note), from this module's compile_pdf (infra.tex)."""
        return compile_pdf(tex_path, out_dir)


def main(argv):
    """`jsk resume preview` (adapters.cli.preview.main), with this module's TeX engine."""
    from ..adapters.cli.preview import main as preview

    return preview(argv, tex=Tex())


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.render.preview_templates", "jsk resume preview"))
