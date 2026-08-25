"""URS - Universal Resume Schema tooling.

The pipeline is one-way and has a single narrow waist:

    bundle -> resume.json (URS) -> render plan -> {docx, latex, txt}

`plan.py` makes every content decision exactly once - selection, ordering,
provenance filtering, profile gating, ASCII folding, date formatting. The
emitters translate that plan into markup and decide nothing. That split is the
whole point: a DOCX and a PDF built from the same view cannot say different
things, because neither one chose what to say.

Standard library only.
"""

__all__ = ["plan", "profiles", "emit_docx", "emit_latex", "emit_text"]
