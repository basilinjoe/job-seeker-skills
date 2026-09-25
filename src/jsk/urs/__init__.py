"""Rendering: the render plan to a PDF and plain text.

The pipeline is one-way and has a single narrow waist:

    career/kb.ttl + resume.json -> render plan -> {latex+pdf, txt}

`jsk.resume.build` makes every content decision exactly once - selection,
ordering, provenance filtering, ASCII folding, date formatting. The emitters
here translate that plan into markup and decide nothing. That split is the
whole point: the PDF and the plain text built from the same resume cannot say
different things, because neither one chose what to say.

The package keeps the name `urs` from the Universal Resume Schema record it
once rendered; the record went on 2026-09-25, and renaming the package would
move every import for no change in behaviour.

`themes.py` sits below `emit_latex`: it owns palette, typeface and rhythm and
nothing else, so a theme can change how the PDF looks and cannot change what it
says. Every theme extracts to the same text, and the tests check that rather
than assert it.

`formatting` decides how a single value reads - a period, a grade, a date -
and `profiles` loads a market's conventions; the builder uses both.

The three CLIs that drive all of the above live here too - `render_resume`
(`jsk render`), `preview_templates` (`jsk preview`) and `fit_pages` (`jsk fit`).
They sat at the top of the package until it was measured: between this package
and the rest of it there is exactly one import edge, `profiles` reaching for the
packaged schema path, and it is lazy. Everything on either side of that line is
one subject, so it is one package.

Standard library only, and pymupdf where a page has to be counted.
"""

__all__ = ["formatting", "profiles",
           "emit_latex", "emit_text", "tex", "themes",
           "render_resume", "preview_templates", "fit_pages"]
