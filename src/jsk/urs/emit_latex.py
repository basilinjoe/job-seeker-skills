"""LaTeX emitter, for the PDF a human reads.

Deliberately narrow dependencies: `geometry`, `enumitem`, `xcolor` and
`hyperref`, all present in any TeX distribution worth the name, plus optional typeface packages
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
# with a zero kern costs nothing visually and keeps the text layer flat.
#
# An empty group was the break until the Everforth render: it holds in a short
# word, but when TeX hyphenates a long skills line it rebuilds the word and the
# ligature comes back - "Verif{}ication" reached the PDF as "Veri<fi>cation".
# A kern survives the rebuild.
#
# Every face a theme can select forms the same pairs, so this stayed here rather
# than moving into themes.py with the rest of the typography: it is a property
# of the text layer, not of the look.
LIGATURE_BREAK = re.compile(r"(?<=f)(?=[fil])|(?<=-)(?=-)")
BREAK = r"\kern0pt{}"

# T1 sets ' and ` as curly quotes, U+2019 and U+2018, so "platform's" left the
# ASCII variant non-ASCII and failed the strict parse gate - and the run asked
# the person to reword their bullet. These glyphs extract as the ASCII byte.
ASCII_QUOTES = {"'": r"\textquotesingle{}", "`": r"\textasciigrave{}"}

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
    if not ascii_safe:
        return "".join(SPECIALS.get(ch, ch) for ch in str(text))
    out = "".join(SPECIALS.get(ch) or ASCII_QUOTES.get(ch, ch) for ch in str(text))
    return LIGATURE_BREAK.sub(lambda m: BREAK, out)


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
        margin_in=0.8 if pages > 1 else 0.9, bullet=bullet,
        pdf_info=pdf_info(plan))]

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
        if i == 0 and headline and line == headline:
            out.append(r"\resumeheadline{%s}" % esc(line))
        else:
            out.append(r"\resumecontact{%s}" % link_contacts(esc(line)))
    out.append(r"\headerclose")
    out.append(r"\headerrule")
    return out


# --- PDF metadata and header links ---------------------------------------------

# The keyword that names the render variant, read back by check_ats.variant_of().
# In the metadata because the file name is the person's to change: "_ATS" in the
# stem was the only marker, and a renamed file lost it.
VARIANT_KEYWORD = "jsk-variant:"


def pdf_info(plan):
    """Title, author and variant for the PDF's information dictionary.

    Escaped with the plain mapping, never the ligature break: a kern is a
    typesetting instruction and has no meaning in a PDF string - hyperref drops
    it with a warning at best.
    """
    name = esc(plan.get("name"))
    return {
        "pdftitle": f"{name} - Resume" if name else "",
        "pdfauthor": name,
        "pdfkeywords": esc(VARIANT_KEYWORD + str(plan.get("format") or "presentation")),
    }


# Email and web contacts, matched on a token of the ESCAPED line. The link goes
# round the escaped text unchanged, so the visible text - and the text layer -
# is exactly what it was; only an annotation is added. Matching after escaping
# is what makes the URL safe to write: a token that needed escaping carries a
# backslash and is skipped, because `\href`'s URL argument is read inside
# \resumecontact's, where catcodes are already frozen and an escaped `\_` or
# `\%` would reach the URL as the escape rather than the character.
EMAIL = re.compile(r"[A-Za-z0-9.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# A domain with a path, a scheme or www - or a bare domain, which a portfolio
# often is. The TLD must be letters, so a version number or "3.5" never links;
# the header carries place, email, phone and profiles, never a skills list, so
# "Node.js" is not a token this can meet.
WEB = re.compile(r"(?:https?://)?(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[A-Za-z0-9./?=+-]*)?")
TOKEN = re.compile(r"\S+")
TRAILING = ".,;:)"


def link_contacts(escaped):
    r"""`escaped` with each email wrapped in a mailto: link and each web address
    in an https:// one. Tokens are whitespace-delimited, so it does not matter
    whether the contacts arrive on one line or two, or which separator joins
    them. Trailing punctuation stays outside the link.
    """
    def wrap(m):
        token = m.group(0)
        core = token.rstrip(TRAILING)
        tail = token[len(core):]
        # The ligature break is the one escape that is not in the address: a
        # handle with "fi" in it carries \kern0pt{} in the ATS variant, and the
        # link has to point at the handle, not at the kern.
        target = core.replace(BREAK, "")
        if not target or "\\" in target or "{" in target or "}" in target:
            return token
        if EMAIL.fullmatch(target):
            url = "mailto:" + target
        elif WEB.fullmatch(target) and "@" not in target:
            url = target if re.match(r"https?://", target) else "https://" + target
        else:
            return token
        return r"\href{%s}{%s}%s" % (url, core, tail)

    return TOKEN.sub(wrap, escaped)


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
            lines = [esc(line) + r"\par" for line in entry["lines"]]
            if any(role.get("bullets") for role in entry["roles"]):
                # Per role: the role line, then that role's bullets, then the
                # next role - an ATS credits a bullet to the title above it. The
                # engagement's own lines go under its head line: the employer
                # line where there is one, else the first role line.
                if entry.get("org_line"):
                    out.extend(lines)
                for n, role in enumerate(entry["roles"]):
                    out.append(r"\roleline{%s}{%s}" % (esc(role["left"]), esc(role.get("right"))))
                    if n == 0 and not entry.get("org_line"):
                        out.extend(lines)
                    out.extend(_itemize(role["bullets"], esc))
            else:
                for role in entry["roles"]:
                    out.append(r"\roleline{%s}{%s}" % (esc(role["left"]), esc(role.get("right"))))
                out.extend(lines)
            out.extend(_itemize(entry["bullets"], esc))
    return out


def _itemize(bullets, esc):
    """A list environment for `bullets`, or nothing: an empty itemize is a TeX error."""
    if not bullets:
        return []
    return [r"\begin{itemize}", *(r"  \item %s" % esc(b) for b in bullets), r"\end{itemize}"]
