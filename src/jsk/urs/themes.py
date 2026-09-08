"""Visual themes for the LaTeX render: palette, typeface, rhythm, hierarchy.

A theme decides how the document *looks*. It cannot decide what the document
*says* - that was settled in `resolve.py` long before a theme is consulted, and
the same view rendered under every theme in this file extracts to the same text.
That is the property the whole pipeline is built on, and it is what makes a
coloured resume safe: colour lives in the drawing instructions of a PDF, never
in its text layer, so a parser reading `\\textcolor{jskaccent}{EXPERIENCE}` reads
`EXPERIENCE`. `tests/test_themes.py` asserts it against real compiled PDFs
rather than trusting the claim.

## What a theme may move, and what it may not

Permitted: colour, typeface, type size of display elements, rule weight and
width, vertical rhythm, margin, alignment of the header block.

Forbidden, because `references/ats-rules.md` forbids the structures that would
express them: a second column, a table, a text box, an image, a header or a
footer. No theme loads a package that could draw one - the package list is
pinned by `tests/test_render_resume.py` and every theme shares it.

Two further prohibitions are less obvious and were arrived at the hard way:

* **No letterspacing.** `soul`/`microtype` letterspacing is the standard way to
  get airy capitals, and it sets each character as its own positioned glyph -
  so `\\so{SUMMARY}` extracts as `S U M M A R Y` and the heading a parser is
  matching on stops existing. Airiness here comes from size, weight, colour and
  space instead.
* **No `microtype` protrusion.** It pushes punctuation past the margin, and
  `tests/test_render_resume.py` measures that nothing does.
* **No uppercased name.** Two themes shipped `\\MakeUppercase` on the name
  because a heavy all-caps name is the strongest possible anchor at the top of
  the page. It is also the one transformation on this list that a parser can
  see: `\\MakeUppercase` changes the glyphs, so the text layer said `PRIYA
  RAMAN` where every other theme said `Priya Raman`. Uppercase headings are
  fine - `check_ats.py` lowercases before matching, and a heading is matched
  against a known word. A name is not matched against anything; it is
  *extracted*, by a heuristic that expects a name to look like a name. That is
  the highest-value field on the document, so the option is gone rather than
  discouraged. Section heads may still uppercase.

## Display sizes and the fitter

`fit_pages.py` finds the body size by the literal `\\fontsize{11pt}{13.2pt}`
form. Every display size in a theme is therefore written *without* the unit -
`\\fontsize{21}{25}`, which LaTeX reads as points just the same - so the fitter
shrinks the body copy and leaves the name and the section heads alone. Shrinking
the anchors is exactly the wrong response to a document that runs long.

## Typefaces

Loads are guarded with `\\IfFileExists`. A distribution without TeX Gyre still
builds; it substitutes Latin Modern and warns. A resume that needs
`texlive-full` to compile is a resume that will not compile on the machine you
actually have, and that rule does not stop applying because the output is
prettier.
"""

# Family codes, so a theme can name a face without depending on which package
# last claimed \rmdefault or \sfdefault. Loading two sans packages is otherwise
# a coin toss decided by load order.
FAMILIES = {
    "termes": ("tgtermes", "qtm"),      # Times-like serif: conventional, compact
    "pagella": ("tgpagella", "qpl"),    # Palatino-like serif: warm, wide, editorial
    "schola": ("tgschola", "qcs"),      # Century Schoolbook: sturdy, roomy
    "heros": ("tgheros", "qhv"),        # Helvetica-like sans: neutral workhorse
    "adventor": ("tgadventor", "qag"),  # Avant Garde-like geometric sans
    "latin": ("lmodern", "lmr"),        # Latin Modern: the guaranteed fallback
    "latinsans": ("lmodern", "lmss"),
}

# Colour roles every theme fills. The names are what the LaTeX commands use, so
# a theme changes the palette without touching a single command definition.
#
# Contrast floors, checked against white and enforced by tests/test_themes.py:
# body ink >= 12:1, and any colour carrying words >= 4.5:1. A resume is read on
# a laptop at 60% brightness, printed in greyscale, and forwarded as a phone
# screenshot; an accent that only works on a calibrated monitor is a decoration
# that costs information.
ROLES = ("ink", "accent", "muted", "rule")

# Where the accent is allowed to land. More than three sites and the eye has no
# path to follow, because everything is emphasised and so nothing is.
ACCENT_BUDGET = 3

# The margin bar in `head_bar` themes: width, and the gap to the heading text.
# Both are needed to compute how far to back out of the margin, so they are
# named once rather than written three times.
BAR_WIDTH_PT = 2.6
BAR_GAP_PT = 7


def _theme(**kw):
    """A theme with the defaults filled in, so each entry states only its idea."""
    base = {
        # palette
        "ink": "1A1A1A", "accent": "1A1A1A", "muted": "5A6472", "rule": "C7CDD4",
        # typeface
        "body": "latin", "head": "latin",
        # header block
        "align": "center", "name_pt": 21, "name_color": "jskink",
        "headline_pt": 11.5, "headline_color": "jskaccent",
        "contact_pt": 10.5, "contact_color": "jskmuted", "header_rule": "none",
        # section heads
        "head_pt": 12, "head_case": "upper", "head_color": "jskaccent",
        "head_bar": False, "head_rule": "full", "head_rule_pt": 0.6,
        "head_rule_color": "jskrule", "head_stub_width": 34,
        # entries. The role line is one of the six items a recruiter's first
        # pass is spent on, so it is ink in every theme; only shape varies.
        # Muting a top-six anchor to grey is how a resume loses an anchor while
        # looking more designed.
        "org_color": "jskink", "role_shape": "italic", "role_color": "jskink",
        "date_color": "jskmuted", "label_color": "jskaccent",
        "bullet_color": "jskaccent",
        # grid
        "rhythm": 3.5, "margin_in": None, "list_indent": 12, "justify": False,
    }
    base.update(kw)
    return base


# The order here is the order --list-templates prints, running from the most
# conservative to the most expressive. Someone picking blind should be able to
# read down the list and stop at the first one that is not too much.
THEMES = {
    "monolith": _theme(
        blurb="Ink only, centred, full rules. The conservative default.",
        best_for="Banking, law, government, academia, any employer whose brand is restraint.",
        # Deliberately identical in structure and typeface to the render this
        # skill shipped before themes existed, so the default output did not
        # silently change under anyone mid-search. Only the rhythm is new.
        body="latin", head="latin",
        ink="111111", accent="111111", muted="333333", rule="111111",
        head_rule_pt=0.4, head_rule_color="jskink",
        headline_color="jskink", contact_color="jskink",
        label_color="jskink", bullet_color="jskink",
        role_color="jskmuted", contact_pt=None, rhythm=3.5, justify=True,
    ),
    "meridian": _theme(
        blurb="Navy accent, left-aligned block, sans throughout. Modern corporate.",
        best_for="Consulting, product, platform and engineering leadership.",
        body="heros", head="heros",
        # Deep navy: reads as ink at a glance and as considered on second look.
        ink="16191D", accent="14456B", muted="5C6672", rule="C7CDD4",
        align="left", name_pt=24, headline_pt=12, header_rule="full",
        head_pt=11.5, head_rule="full", head_rule_pt=0.6,
        rhythm=4,
    ),
    "ember": _theme(
        blurb="Warm serif, terracotta stub rules, centred. Editorial and senior.",
        best_for="Design, brand, research, writing, and senior individual contributors.",
        body="pagella", head="pagella",
        ink="1C1917", accent="A6432B", muted="6B6259", rule="D9D2C7",
        name_pt=25, headline_pt=12,
        # Pagella is wide, and a centred contact line that wraps leaves a
        # dangling separator at the end of the first line. A step down in size
        # keeps it on one line at every realistic contact length.
        contact_pt=10,
        head_pt=12, head_rule="stub", head_rule_pt=2, head_rule_color="jskaccent",
        head_stub_width=30, role_color="jskmuted",
        rhythm=4.5, margin_in=0.85,
    ),
    "circuit": _theme(
        blurb="Teal accent bars in the left margin, geometric heads. Technical.",
        best_for="Software, data, security, infrastructure - dense evidence, fast scan.",
        body="heros", head="adventor",
        ink="14181C", accent="0E6E6E", muted="55606B", rule="CBD3D9",
        align="left", name_pt=23, headline_pt=11.5, header_rule="hair",
        head_pt=11, head_bar=True, head_rule="none",
        rhythm=4, list_indent=11,
    ),
    "atrium": _theme(
        blurb="Hairlines, wide margins, muted slate. Maximum white space.",
        best_for="Executive one-pagers and short senior resumes with room to breathe.",
        body="pagella", head="heros",
        ink="1B1F23", accent="30414B", muted="6A737D", rule="DDE1E6",
        align="left", name_pt=26, headline_pt=12, header_rule="hair",
        # Larger than the body copy it sits over, because atrium has no rule
        # weight and no colour doing the separating - the head has to carry it
        # alone or the employer names outrank the sections above them.
        head_pt=11.5, head_rule="hair", head_rule_pt=0.4,
        rhythm=6, margin_in=1.0, list_indent=14,
    ),
}

DEFAULT = "monolith"


def names():
    return list(THEMES)


def get(name):
    """A theme by name. An unknown name is an error, never a silent default -
    a resume rendered in a theme the caller did not ask for is a resume nobody
    has looked at."""
    if not name:
        return THEMES[DEFAULT]
    key = str(name).strip().lower()
    if key not in THEMES:
        raise KeyError(f"unknown template {name!r} - choose from: "
                       + ", ".join(names()))
    return THEMES[key]


def catalogue():
    """`[(name, blurb, best_for)]` for --list-templates and the docs."""
    return [(n, t["blurb"], t["best_for"]) for n, t in THEMES.items()]


# --- LaTeX fragments -----------------------------------------------------------
#
# Each returns a string. They are separate so a change to one piece of the
# preamble cannot silently reshape another, and so the tests can read them.

def _font_setup(theme):
    """Guarded package loads, then explicit family codes.

    lmodern is loaded first and unconditionally-guarded because it is the
    fallback every other face degrades to: without it, [T1]{fontenc} leaves you
    on bitmap EC fonts, which embed poorly and extract worse.
    """
    body_pkg, body_code = FAMILIES[theme["body"]]
    head_pkg, head_code = FAMILIES[theme["head"]]
    lines = []
    for pkg in dict.fromkeys(("lmodern", body_pkg, head_pkg)):
        lines.append(r"\IfFileExists{%s.sty}{\usepackage{%s}}{}" % (pkg, pkg))
    lines.append(r"\renewcommand{\familydefault}{%s}" % body_code)
    lines.append(r"\newcommand{\headfamily}{\fontfamily{%s}\selectfont}" % head_code)
    return "\n".join(lines)


def _palette(theme):
    defs = [r"\definecolor{jsk%s}{HTML}{%s}" % (role, theme[role].upper())
            for role in ROLES]
    # Aliases, so every command below names a job rather than a colour. A theme
    # repoints the alias; no command definition changes.
    for alias, key in (("name", "name_color"), ("headline", "headline_color"),
                       ("contact", "contact_color"), ("head", "head_color"),
                       ("headrule", "head_rule_color"), ("org", "org_color"),
                       ("role", "role_color"), ("date", "date_color"),
                       ("label", "label_color"), ("bullet", "bullet_color")):
        defs.append(r"\colorlet{jsk%s}{%s}" % (alias, theme[key]))
    return "\n".join(defs)


def rhythm_lengths(theme):
    """The four density levers, as multiples of the theme's rhythm unit.

    Returned as numbers rather than LaTeX so `fit_pages.py`'s floors and this
    module's grid cannot drift apart without a test noticing.
    """
    unit = theme["rhythm"]
    return {
        # Above a section head. Deliberately the largest gap in the document:
        # it is the only signal that one section has ended and another begun,
        # and it has to beat the gap between entries inside a section or the
        # sections stop being visible as sections.
        "sectiongap": round(unit * 2.8, 2),
        "entrygap": round(unit * 1.15, 2),
        "topsep": round(unit * 0.55, 2),
        "itemsep": round(unit * 0.3, 2),
    }


def _rule_line(width, weight, color, above, below):
    r"""A horizontal rule that occupies its own height and not a whole line.

    `\rule` starts a paragraph, so the rule sits in a line box that takes a full
    `\baselineskip` whatever the rule's own height is. Every section head in the
    first cut therefore had ~13pt of dead space under it: the gap *below* a
    heading was larger than the gap *above* it, which inverts proximity - each
    heading looked attached to the section it had just ended rather than to the
    one it was opening. It read as sloppy spacing and was in fact a hierarchy
    error, and no amount of tuning `\sectiongap` could fix it, because the
    space being tuned was not the space that was wrong.

    `\nointerlineskip` on both sides drops the interline glue, so the rule
    contributes exactly its own weight and the two `\vspace`s below are the
    whole story. `\rule` is kept rather than `\hrule` because it honours
    `\color`; a `\hrule` in vertical mode does not, reliably.
    """
    return (r"\par\nobreak\vspace{%gpt}\nointerlineskip"
            r"{\color{%s}\rule{%s}{%gpt}}"
            r"\par\nointerlineskip\vspace{%gpt}"
            % (above, color, width, weight, below))


def _section_rule(theme):
    kind = theme["head_rule"]
    weight = theme["head_rule_pt"]
    if kind == "none":
        body = r"\par\nobreak\vspace{%gpt}" % (theme["rhythm"] * 0.5)
    elif kind == "stub":
        # A short bar under the heading: the strongest available "you are here"
        # marker that is still just a rule. A full-width rule reads as a
        # divider, which separates the heading from its own section; a stub
        # reads as a marker, which points at it.
        #
        # It needs more clearance than a full-width rule, and that is not a
        # matter of taste. At 2pt a 30pt bar under a 200pt heading stops
        # reading as a marker and starts reading as an underline of the first
        # word - "PRO" underlined, in the middle of PROFESSIONAL SUMMARY.
        body = _rule_line(f"{theme['head_stub_width']:g}pt", weight,
                          "jskheadrule", 6, theme["rhythm"] * 0.9)
    else:
        body = _rule_line(r"\linewidth", weight, "jskheadrule",
                          4, theme["rhythm"] * 0.85)
    return r"\newcommand{\sectionrule}{%s}" % body


def _section_head(theme):
    """The single most important command in the file.

    Eye-tracking on resumes is consistent about two things: the top third of
    page one takes most of the attention, and what attention is left runs down
    the left edge. Section heads are the only element on that edge, so they are
    where hierarchy is won or lost. Size, weight and colour all move together
    here rather than one at a time, because a heading that is merely bigger
    reads as bigger text, not as a new section.
    """
    case = r"\MakeUppercase{#1}" if theme["head_case"] == "upper" else "#1"
    # Hung in the left margin, so the heading text still starts on the same
    # vertical as every body line. Set inline instead, the bar indented each
    # heading by its own width and broke the one edge the whole F-pattern
    # argument rests on - the marker meant to anchor the left edge was the
    # thing destroying it.
    #
    # Backed out of the margin with \hspace* rather than the obvious
    # \makebox[0pt][r]{...}: check_prose.py strips a command and ONE optional
    # argument, so a second bracket group survives into the text it scans and
    # `[r]` was reported as an unresolved placeholder. The gate was right to
    # flag a stray bracket; the template was wrong to emit one.
    bar = ""
    if theme["head_bar"]:
        width, gap = BAR_WIDTH_PT, BAR_GAP_PT
        bar = (r"\hspace*{-%gpt}{\color{jskaccent}\rule[-0.12em]{%gpt}{0.86em}}"
               r"\hspace{%gpt}" % (width + gap, width, gap))
    return (r"\newcommand{\sectionhead}[1]{%%" "\n"
            r"  \vspace{\sectiongap}%%" "\n"
            r"  {\headfamily\fontsize{%g}{%g}\selectfont\bfseries\color{jskhead}%s%s}%%" "\n"
            r"  \sectionrule}"
            % (theme["head_pt"], theme["head_pt"] * 1.15, bar, case))


def _header_block(theme):
    """Name, headline, contact. Nothing here is a container - `center` is an
    alignment environment, not a column, and the extracted order is the source
    order either way."""
    open_, close = ((r"\begin{center}", r"\end{center}")
                    if theme["align"] == "center" else ("", ""))
    rule = {
        "none": r"\par\vspace{2pt}",
        "hair": _rule_line(r"\linewidth", 0.4, "jskrule", 6, 1),
        "full": _rule_line(r"\linewidth", 1, "jskaccent", 6, 1),
    }[theme["header_rule"]]
    contact_pt = theme["contact_pt"]
    contact_size = (r"\fontsize{%g}{%g}\selectfont" % (contact_pt, contact_pt * 1.25)
                    if contact_pt else "")
    return "\n".join([
        r"\newcommand{\headeropen}{%s}" % open_,
        r"\newcommand{\headerclose}{%s}" % close,
        # Never \MakeUppercase - see the module docstring. The name is extracted,
        # not matched, and uppercasing it is the one theme choice a parser sees.
        r"\newcommand{\resumename}[1]{{\headfamily\fontsize{%g}{%g}\selectfont"
        r"\bfseries\color{jskname}#1}\par}"
        % (theme["name_pt"], theme["name_pt"] * 1.12),
        # The headline is the professional title, one of the six items that take
        # most of a recruiter's first pass. It gets its own size and colour; the
        # contact lines that follow deliberately do not.
        r"\newcommand{\resumeheadline}[1]{\vspace{3pt}{\fontsize{%g}{%g}\selectfont"
        r"\color{jskheadline}#1}\par}" % (theme["headline_pt"], theme["headline_pt"] * 1.2),
        r"\newcommand{\resumecontact}[1]{\vspace{2.5pt}{%s\color{jskcontact}#1}\par}"
        % contact_size,
        r"\newcommand{\headerrule}{%s}" % rule,
    ])


def _entry_commands(theme):
    # Employer bold, title italic, both ink. The first cut set both bold, and
    # an entry then read as three interchangeable bold lines - "Northbridge
    # Digital / Solution Architect / Member of Technical Staff" with nothing
    # saying which was the company. Weight separates the two anchors; colour
    # would have cost one of them its prominence.
    role_open = r"\itshape" if theme["role_shape"] == "italic" else ""
    return "\n".join([
        # A two-column line without a two-column layout: text left, date right.
        # Both halves of the guard matter, and neither works alone.
        #
        # \mbox stops TeX breaking *inside* the date. Plain `#1\hfill #2` on a
        # long left side - which functional_title makes common, "Member of
        # Technical Staff, Grade IV (Principal Platform Engineer)" - collapses
        # the \hfill to zero and breaks the date itself, leaving
        # "...Engineer)Aug 2016" on one line and "- Feb 2019" on the next.
        # \mbox alone then overflows the right margin instead, because an
        # unbreakable date with no legal breakpoint before it has nowhere to go.
        #
        # \rightskip gives every line infinite stretch, so TeX will break the
        # *title* at a space and carry the intact date to the next line. \hfill
        # is fill order and \rightskip is fil, so on a line that fits the \hfill
        # still wins outright and the date sits flush right exactly as before.
        #
        # Neither is a layout container: no package, no box in the hazard list,
        # and the extracted text layer is identical either way.
        r"\newcommand{\dateright}[2]{{\rightskip=0pt plus 1fil\relax #1\hfill"
        r"\mbox{{\color{jskdate}#2}}\par}}",
        r"\newcommand{\entryline}[2]{\dateright{{\color{jskorg}\bfseries #1}}{#2}}",
        r"\newcommand{\roleline}[2]{\dateright{{\color{jskrole}%s #1}}{#2}}" % role_open,
        # Skills rows. The label is the left-edge anchor for the one section a
        # recruiter re-reads after deciding they are interested, so it carries
        # the accent even in themes that are otherwise sparing with it.
        r"\newcommand{\skillrow}[2]{{\color{jsklabel}\bfseries #1:} #2\par}",
    ])


def preamble(theme, *, body_pt, baseline_pt, paper, margin_in, bullet):
    """The whole preamble for one theme, ready to write.

    `margin_in` is the caller's page-budget margin; a theme may widen it but
    never narrow it, because narrowing is `fit_pages.py`'s job and it starts
    from what is written here.
    """
    gaps = rhythm_lengths(theme)
    margin = max(float(margin_in), float(theme["margin_in"] or 0))
    marker = r"\textcolor{jskbullet}{%s}" % bullet
    return PREAMBLE % {
        "pt": body_pt, "baseline": baseline_pt, "paper": paper,
        "margin": f"{margin:g}in", "bullet": marker,
        "fonts": _font_setup(theme), "palette": _palette(theme),
        "rhythm": theme["rhythm"], "indent": theme["list_indent"],
        "header": _header_block(theme), "rule": _section_rule(theme),
        "head": _section_head(theme), "entries": _entry_commands(theme),
        "align": "" if theme["justify"] else RAGGED,
        **gaps,
    }


# Ragged right. At a 6.5-inch measure, justification opens word gaps wide enough
# to read as rivers - visible in the first render's bullets - and every extra
# millimetre between words costs a scan that is being done in seven seconds.
#
# It is also compatible with \dateright, which is not obvious: \raggedright sets
# \rightskip to `0pt plus 1fil`, exactly what \dateright sets locally, and the
# \hfill that pushes the date right is `fill` - an infinity order above `fil` -
# so it still wins outright and the date still sits flush against the margin.
RAGGED = r"""%% Ragged right: at this measure justification opens gaps wide enough to read
%% as rivers, and \hfill (fill) still outranks this \rightskip (fil), so the
%% date column is unaffected. tests/test_themes.py measures that it is.
\raggedright"""


PREAMBLE = r"""%% Rendered by jsk render_resume.py. Every content decision was made in
%% urs/plan.py; this file only decides how those decisions look.
\documentclass[%(pt)spt,%(paper)s]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=%(margin)s]{geometry}
\usepackage{enumitem}
\usepackage{xcolor}
%% --- typeface -------------------------------------------------------------
%% Guarded: a distribution without TeX Gyre substitutes Latin Modern and warns.
%% It never fails to build, because a resume that needs texlive-full to compile
%% is a resume that will not compile on the machine you actually have.
%(fonts)s
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
%% --- palette --------------------------------------------------------------
%% Colour is a drawing instruction in a PDF, never part of the text layer, so
%% none of this is visible to a parser. tests/test_themes.py compiles each of
%% these and checks the extracted text is identical.
%(palette)s
\color{jskink}
%% --- density levers: fit_pages.py rewrites the values on the next three lines,
%% and the margin above. Keep them literal, one per line, and in point units so
%% it can. Each is a multiple of this theme's %(rhythm)gpt vertical rhythm. ---
\newlength{\sectiongap}\setlength{\sectiongap}{%(sectiongap)gpt}
\newlength{\entrygap}\setlength{\entrygap}{%(entrygap)gpt}
\setlist[itemize]{leftmargin=%(indent)gpt,topsep=%(topsep)gpt,itemsep=%(itemsep)gpt,parsep=0pt,label=%(bullet)s}
%% -------------------------------------------------------------------------
%% Display sizes below are written WITHOUT the unit - \fontsize{21}{25}, which
%% LaTeX reads as points just the same. That is deliberate: it keeps them out of
%% the regex above, so the fitter shrinks body copy and leaves the name and the
%% section heads at full size. Shrinking the anchors is the wrong answer to a
%% document that runs long; cutting evidence is the right one.
%(header)s
%(rule)s
%(head)s
%(entries)s
\begin{document}
%% The body size is set here rather than only in \documentclass, because the
%% class accepts 10, 11 or 12pt and nothing between - and the font lever moves
%% in half-points.
\fontsize{%(pt)spt}{%(baseline)spt}\selectfont
%(align)s
"""
