"""URS - Universal Resume Schema tooling.

The pipeline is one-way and has a single narrow waist:

    bundle -> resume.json (URS) -> render plan -> {latex+pdf, txt}

`plan.py` makes every content decision exactly once - selection, ordering,
provenance filtering, profile gating, ASCII folding, date formatting. The
emitters translate that plan into markup and decide nothing. That split is the
whole point: the PDF and the plain text built from the same view cannot say
different things, because neither one chose what to say.

`themes.py` sits below `emit_latex`: it owns palette, typeface and rhythm and
nothing else, so a theme can change how the PDF looks and cannot change what it
says. Every theme extracts to the same text, and the tests check that rather
than assert it.

`plan` is the public face of two modules either side of a second seam:
`resolve` decides what the document says, `formatting` decides how a single
value reads. Import `plan`; the split is behind it.

Standard library only.
"""

__all__ = ["plan", "resolve", "formatting", "profiles",
           "emit_latex", "emit_text", "tex", "themes"]
