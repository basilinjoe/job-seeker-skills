"""LaTeX emitter, for the PDF a human reads.

Deliberately narrow dependencies: `geometry` and `enumitem` only, both present
in any TeX distribution worth the name. A resume that needs texlive-full to
build is a resume that will not build on the machine you actually have.

The PDF is the presentation artefact. The .docx remains what goes into a portal,
because ats-rules.md says so and a PDF does not stop being harder to parse just
because it is prettier.
"""

SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}

PREAMBLE = r"""\documentclass[%(pt)spt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=%(margin)s]{geometry}
\usepackage{enumitem}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\newcommand{\sectionrule}{\vspace{1pt}\rule{\linewidth}{0.4pt}\vspace{2pt}\par}
\newcommand{\sectionhead}[1]{%%
  \vspace{7pt}{\large\bfseries\MakeUppercase{#1}}\par\sectionrule}
\newcommand{\entryline}[2]{\textbf{#1}\hfill #2\par}
\newcommand{\roleline}[2]{#1\hfill #2\par}
\setlist[itemize]{leftmargin=12pt,topsep=2pt,itemsep=1pt,parsep=0pt,label=\textbullet}
\begin{document}
"""


def esc(text):
    if text is None:
        return ""
    return "".join(SPECIALS.get(ch, ch) for ch in str(text))


def emit(plan):
    pages = plan.get("pages") or 2
    body = [PREAMBLE % {"pt": "11", "margin": "0.8in" if pages > 1 else "0.9in"}]

    body.append(r"\begin{center}")
    body.append(r"{\LARGE\bfseries %s}\par" % esc(plan["name"]))
    for line in plan["header_lines"]:
        body.append(r"\vspace{2pt}%s\par" % esc(line))
    body.append(r"\end{center}")

    if plan.get("photo"):
        # Recorded rather than embedded: a graphics dependency for a decorative
        # element is a build failure waiting to happen on someone else's machine.
        body.append("%% photo available at %s - insert manually if wanted" % plan["photo"])

    for section in plan["sections"]:
        if section.get("heading"):
            body.append(r"\sectionhead{%s}" % esc(section["heading"]))
        body.extend(_section(section))

    body.append(r"\end{document}")
    return "\n".join(body) + "\n"


def _section(section):
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
            out.append(r"\vspace{4pt}")
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
