"""The TeX engine a .tex is compiled with."""
from typing import Protocol


class TexCompiler(Protocol):
    """Whichever installed engine compiles a render's .tex into its PDF."""

    def available_engine(self) -> str | None:
        """The engine compile_pdf would use, or None when none is installed."""
        ...

    def compile_pdf(self, tex_path: str, out_dir: str) -> tuple[str | None, str]:
        """Compile with the first engine that produces a PDF.

        Args:
            tex_path: the .tex.
            out_dir: where the PDF goes, named after the .tex.

        Returns:
            (the PDF's path, or None when no engine produced one; a note saying why).
            Runs a subprocess and writes into `out_dir`.
        """
        ...
