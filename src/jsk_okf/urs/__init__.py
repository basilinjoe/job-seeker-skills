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

The three CLIs that drive all of the above live here too - `render_resume`
(`okf render`), `preview_templates` (`okf preview`) and `fit_pages` (`okf fit`).
They sat at the top of the package until it was measured: between this package
and the rest of it there are exactly two import edges, `render_resume` reaching
for `okf_compile` to turn a bundle into a record and `profiles` reaching for the
packaged schema path, and both are lazy. Everything on either side of that line
is one subject, so it is one package.

Standard library only, and pymupdf where a page has to be counted.
"""

__all__ = ["plan", "resolve", "formatting", "profiles",
           "emit_latex", "emit_text", "tex", "themes",
           "render_resume", "preview_templates", "fit_pages"]
