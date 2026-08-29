"""LaTeX emitter, for the PDF a human reads.

Deliberately narrow dependencies: `geometry`, `enumitem` and `xcolor`, all
present in any TeX distribution worth the name, plus optional typeface packages
loaded behind `\\IfFileExists` so their absence costs appearance and never a
build. A resume that needs texlive-full to build is a resume that will not build
on the machine you actually have.

The PDF this produces is the only rendered deliverable, in whichever variant
--ats-max selected, so this template is now the single place a structural ATS
hazard could enter a document. It cannot express one - there is no table, no
text box, no image, no second column and no header - which is why check_ats.py
stopped checking for them per render and a golden-file test guards this file
instead.

How the document *looks* moved to `themes.py`; what it *says* was settled in
`resolve.py`. This module is the seam: it walks the plan and hands each piece to
a command the theme defined. That split is why a theme cannot change a word, and
why `tests/test_themes.py` can prove it by extracting text from five differently
coloured PDFs and finding one document.

The density levers near the end of the preamble are rewritten in place by
fit_pages.py. Keep them literal, one per line, and in point units.
"""
import re

from . import themes
from .formatting import LETTER_REGIONS

# Variants resolve.py folds to ASCII, and which therefore cannot carry a
# U+2022 bullet in the rendered text layer either.
ASCII_VARIANTS = ("ats-maximal", "plaintext")

# Body size in points. fit_pages.py may lower it in the .tex, never below 10.
BODY_PT = 11

# T1 Computer Modern forms ligatures for ff, fi, fl, ffi and ffl, and turns two
# hyphens into an en dash. Each becomes a SINGLE non-ASCII codepoint in the PDF
# text layer - U+FB01 for "fi" - so a parser extracting "efficiency" reads
# "e<ffi>ciency" and the word is gone. The record is ASCII, the .txt is ASCII,
# and check_ats.py passed the .docx: only the render was never ASCII, and
# nothing looked at it until the PDF became the deliverable. Breaking the pair
# with an empty group costs nothing visually and keeps the text layer flat.
#
# Every face a theme can select forms the same pairs, so this stayed here rather
# than moving into themes.py with the rest of the typography: it is a property
# of the text layer, not of the look.
LIGATURE_BREAK = re.compile(r"(?<=f)(?=[fil])|(?<=-)(?=-)")

SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    # U+00B7 is the separator resolve.sep() emits for the presentation
    # variant. Passed through raw it reaches the TeX as byte 0xB7, which
    # under [T1]{fontenc} is u-with-ring - so every contact line rendered
    # as "name <u-ring> email" in the PDF, while the .docx and all three
    # checkers, none of which ever see the TeX, reported clean.
    "·": r"\textperiodcentered{}",
}


def esc(text, ascii_safe=False):
    """Escape for LaTeX. No value in SPECIALS contains a ligature pair, so the
    break can safely run after the mapping rather than before it - running it
    before would see its own braces escaped."""
    if text is None:
        return ""
    out = "".join(SPECIALS.get(ch, ch) for ch in str(text))
    return LIGATURE_BREAK.sub("{}", out) if ascii_safe else out


def emit(plan, template=None):
    """The .tex for one render plan, in one theme.

    `template` names a theme in `themes.py`. An unknown name raises rather than
    falling back: a resume rendered in a theme nobody chose is a resume nobody
    has looked at, and it would look fine.
    """
    theme = themes.get(template or plan.get("template"))
    pages = plan.get("pages") or 2
    # A4 was hardcoded here while the .docx emitter honoured the region, so a US
    # view produced a Letter .docx and an A4 PDF of the same document.
    paper = "letterpaper" if plan.get("region") in LETTER_REGIONS else "a4paper"
    # In a PDF the bullet is a glyph in the text layer, not list structure the
    # way it was in the .docx - so an ATS-maximal render whose marker is U+2022
    # fails its own ASCII rule. The variant that promises pure ASCII has to use
    # a marker that is pure ASCII. Colour is applied by the theme around it and
    # changes neither the glyph nor its extraction.
    ascii_safe = plan.get("format") in ASCII_VARIANTS
    bullet = "{-}" if ascii_safe else r"\textbullet"

    def esc_(text):
        return esc(text, ascii_safe)

    body = [themes.preamble(
        theme, body_pt=BODY_PT, baseline_pt=f"{BODY_PT * 1.2:g}", paper=paper,
        margin_in=0.8 if pages > 1 else 0.9, bullet=bullet)]

    body.extend(_header(plan, theme, esc_))

    if plan.get("photo"):
        # Recorded rather than embedded: a graphics dependency for a decorative
        # element is a build failure waiting to happen on someone else's machine.
        body.append("%% photo available at %s - insert manually if wanted" % plan["photo"])

    for section in plan["sections"]:
        if section.get("heading"):
            body.append(r"\sectionhead{%s}" % esc_(section["heading"]))
        body.extend(_section(section, esc_))

    body.append(r"\end{document}")
    return "\n".join(body) + "\n"


def _header(plan, theme, esc):
    """Name, then the headline, then everything else.

    The headline is `person.headline` and `resolve.header()` puts it first in
    `header_lines`; the plan repeats it under its own key so this can tell it
    apart from a contact line without re-deriving anything. Recruiters' first
    pass is spent almost entirely on six items and the current title is one of
    them, so it is worth a size of its own. A phone number is not.
    """
    headline = plan.get("headline")
    out = [r"\headeropen", r"\resumename{%s}" % esc(plan["name"])]
    for i, line in enumerate(plan["header_lines"]):
        macro = "resumeheadline" if (i == 0 and headline and line == headline) else "resumecontact"
        out.append(r"\%s{%s}" % (macro, esc(line)))
    out.append(r"\headerclose")
    out.append(r"\headerrule")
    return out


def _section(section, esc):
    kind = section["kind"]
    out = []
    if kind == "text":
        for para in section["paragraphs"]:
            out.append(esc(para) + r"\par")
    elif kind == "lines":
        for line in section["lines"]:
            out.append(esc(line) + r"\par")
    elif kind == "rows":
        for row in section["rows"]:
            out.append(r"\skillrow{%s}{%s}" % (esc(row["label"]),
                                               esc(", ".join(row["items"]))))
    elif kind == "entries":
        for index, entry in enumerate(section["entries"]):
            # The gap separates one entry from the previous one, so the first
            # entry does not get one: stacked on top of the space the section
            # rule already leaves, it put more air between a heading and its
            # own first employer than between that employer and the section
            # above. The section head owns the space above the section; the
            # entry gap owns the space between entries.
            if index:
                out.append(r"\vspace{\entrygap}")
            if entry.get("org_line"):
                out.append(r"\entryline{%s}{%s}" % (esc(entry["org_line"]), esc(entry.get("org_right"))))
            for role in entry["roles"]:
                out.append(r"\roleline{%s}{%s}" % (esc(role["left"]), esc(role.get("right"))))
            for line in entry["lines"]:
                out.append(esc(line) + r"\par")
            if entry["bullets"]:
                out.append(r"\begin{itemize}")
                out.extend(r"  \item %s" % esc(b) for b in entry["bullets"])
                out.append(r"\end{itemize}")
    return out
