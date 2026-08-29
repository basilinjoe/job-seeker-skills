"""LaTeX emitter, for the PDF a human reads.

Deliberately narrow dependencies: `geometry` and `enumitem` only, both present
in any TeX distribution worth the name. A resume that needs texlive-full to
build is a resume that will not build on the machine you actually have.

The PDF this produces is the only rendered deliverable, in whichever variant
--ats-max selected, so this template is now the single place a structural ATS
hazard could enter a document. It cannot express one - there is no table, no
text box, no image, no second column and no header - which is why check_ats.py
stopped checking for them per render and a golden-file test guards this file
instead.

The density levers near the end of the preamble are rewritten in place by
fit_pages.py. Keep them literal, one per line, and in point units.
"""
import re

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

PREAMBLE = r"""\documentclass[%(pt)spt,%(paper)s]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=%(margin)s]{geometry}
\usepackage{enumitem}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
%% --- density levers: fit_pages.py rewrites the values on the next three lines,
%% and the margin above. Keep them literal and one per line so it can. ---
\newlength{\sectiongap}\setlength{\sectiongap}{7pt}
\newlength{\entrygap}\setlength{\entrygap}{4pt}
\setlist[itemize]{leftmargin=12pt,topsep=2pt,itemsep=1pt,parsep=0pt,label=%(bullet)s}
%% -------------------------------------------------------------------------
\newcommand{\sectionrule}{\vspace{1pt}\rule{\linewidth}{0.4pt}\vspace{2pt}\par}
\newcommand{\sectionhead}[1]{%%
  \vspace{\sectiongap}{\large\bfseries\MakeUppercase{#1}}\par\sectionrule}
%% A two-column line without a two-column layout: text left, date right. Both
%% halves of the guard matter, and neither works alone.
%%
%% \mbox stops TeX breaking *inside* the date. Plain `#1\hfill #2` on a long left
%% side - which functional_title makes common, "Member of Technical Staff, Grade
%% IV (Principal Platform Engineer)" - collapses the \hfill to zero and breaks the
%% date itself, leaving "...Engineer)Aug 2016" on one line and "- Feb 2019" on the
%% next. \mbox alone then overflows the right margin instead, because an
%% unbreakable date with no legal breakpoint before it has nowhere to go.
%%
%% \rightskip gives every line infinite stretch, so TeX will break the *title* at
%% a space and carry the intact date to the next line. \hfill is fill order and
%% \rightskip is fil, so on a line that fits the \hfill still wins outright and
%% the date sits flush right exactly as before.
%%
%% Neither is a layout container: no package, no box in the hazard list, and the
%% extracted text layer is identical either way.
\newcommand{\dateright}[2]{{\rightskip=0pt plus 1fil\relax #1\hfill\mbox{#2}\par}}
\newcommand{\entryline}[2]{\dateright{\textbf{#1}}{#2}}
\newcommand{\roleline}[2]{\dateright{#1}{#2}}
\begin{document}
%% The body size is set here rather than only in \documentclass, because the
%% class accepts 10, 11 or 12pt and nothing between - and the font lever moves
%% in half-points.
\fontsize{%(pt)spt}{%(baseline)spt}\selectfont
"""


def esc(text, ascii_safe=False):
    """Escape for LaTeX. No value in SPECIALS contains a ligature pair, so the
    break can safely run after the mapping rather than before it - running it
    before would see its own braces escaped."""
    if text is None:
        return ""
    out = "".join(SPECIALS.get(ch, ch) for ch in str(text))
    return LIGATURE_BREAK.sub("{}", out) if ascii_safe else out


def emit(plan):
    pages = plan.get("pages") or 2
    # A4 was hardcoded here while the .docx emitter honoured the region, so a US
    # view produced a Letter .docx and an A4 PDF of the same document.
    paper = "letterpaper" if plan.get("region") in LETTER_REGIONS else "a4paper"
    # In a PDF the bullet is a glyph in the text layer, not list structure the
    # way it was in the .docx - so an ATS-maximal render whose marker is U+2022
    # fails its own ASCII rule. The variant that promises pure ASCII has to use
    # a marker that is pure ASCII.
    ascii_safe = plan.get("format") in ASCII_VARIANTS
    bullet = "{-}" if ascii_safe else "\\textbullet"

    def esc_(text):
        return esc(text, ascii_safe)

    body = [PREAMBLE % {"pt": BODY_PT, "baseline": f"{BODY_PT * 1.2:g}",
                        "paper": paper, "bullet": bullet,
                        "margin": "0.8in" if pages > 1 else "0.9in"}]

    body.append(r"\begin{center}")
    body.append(r"{\LARGE\bfseries %s}\par" % esc_(plan["name"]))
    for line in plan["header_lines"]:
        body.append(r"\vspace{2pt}%s\par" % esc_(line))
    body.append(r"\end{center}")

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
            out.append(r"\textbf{%s:} %s\par" % (esc(row["label"]), esc(", ".join(row["items"]))))
    elif kind == "entries":
        for entry in section["entries"]:
            out.append(r"\vspace{\entrygap}")
            if entry.get("org_line"):
                out.append(r"\entryline{%s}{%s}" % (esc(entry["org_line"]), esc(entry.get("org_right"))))
            for role in entry["roles"]:
                out.append(r"\roleline{\textit{%s}}{%s}" % (esc(role["left"]), esc(role.get("right"))))
            for line in entry["lines"]:
                out.append(esc(line) + r"\par")
            if entry["bullets"]:
                out.append(r"\begin{itemize}")
                out.extend(r"  \item %s" % esc(b) for b in entry["bullets"])
                out.append(r"\end{itemize}")
    return out
