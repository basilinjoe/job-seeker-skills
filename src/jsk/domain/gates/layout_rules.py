"""The layout gate's rules: what a rendered PDF's geometry and fonts say, as plain values.

These lived in layout.py beside the pymupdf read. What is judged is only what that read
returns - page sizes, lines with their boxes and fonts, the Type3 font names - so it is
here and testable without a PDF; layout.py keeps the read, the flags and the printing.
"""
import re
import unicodedata

# The section titles build.py writes. A heading is found by its words rather than its
# size: circuit sets its heads at the body's own 11pt, in another family.
SECTION_TITLES = ("Professional Summary", "Skills", "Technical Skills",
                  "Professional Experience", "Education", "Certifications", "Languages")

# The face each themes.FAMILIES key embeds as, once normalised by family().
# Measured from every template's render of the shipped example (2026-09-26).
PDF_FAMILY = {"latin": "LMRoman", "latinsans": "LMSans", "termes": "TeXGyreTermes",
              "pagella": "TeXGyrePagella", "schola": "TeXGyreSchola",
              "heros": "TeXGyreHeros", "adventor": "TeXGyreAdventor"}

# Faces that draw a bullet or a rule, not words. No shipped template embeds one - its
# \textbullet is set in the body face - but in OT1 a LaTeX bullet comes from CMSY, and
# a symbol face is not a second typeface to a reader.
SYMBOL_FACES = ("Symbol", "Dingbat", "CMSY", "CMMI", "LMMath", "FontAwesome")

# Points, in either orientation's order. 2pt either way is well inside any real error.
PAPERS = {"A4": (595.28, 841.89), "Letter": (612.0, 792.0)}
PAPER_SLACK = 2.0

# Every template right-aligns dates with the same \hfill, so they end within a tenth of
# a point of each other; ragged-right body text never lands on that edge by accident.
DATE_SLACK = 1.5
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
DATE_LINE = re.compile(rf"^(?:{MONTH} )?\d{{4}} ?[-–—] ?(?:(?:{MONTH} )?\d{{4}}|Present)$"
                       rf"|^{MONTH} \d{{4}}$")

SUBSET = re.compile(r"^[A-Z]{6}\+")


def family(font):
    """`ABCDEF+LMRoman12-Bold` -> `LMRoman`. Subset prefix, weight and style after the
    hyphen or comma, the PostScript `MT`/`PS` tails and a LaTeX optical size go.

    Args:
        font: a font name as the PDF embeds it.

    Returns:
        The family name, or `font` itself when nothing is left after normalising.
    """
    base = re.split(r"[-,]", SUBSET.sub("", font), maxsplit=1)[0]
    base = re.sub(r"(?:PSMT|PS|MT)$", "", base)
    return re.sub(r"\d+$", "", base) or font


def declared_pairs():
    """The two-family sets a shipped template asks for: its body face and its head face.

    Returns:
        {template name: frozenset of its two PDF family names}, for each template whose
        body and heading faces differ.
    """
    from ..render import themes                          # noqa: PLC0415 - only when two faces show
    return {name: frozenset((PDF_FAMILY[t["body"]], PDF_FAMILY[t["head"]]))
            for name, t in themes.THEMES.items() if t["body"] != t["head"]}


def paper_name(rect):
    """Name a page's paper size, in either orientation.

    Args:
        rect: the page's size, anything with `width` and `height` in points.

    Returns:
        "A4" or "Letter" within PAPER_SLACK, otherwise the size as "WxHpt".
    """
    w, h = sorted((rect.width, rect.height))
    for name, (pw, ph) in PAPERS.items():
        if abs(w - pw) <= PAPER_SLACK and abs(h - ph) <= PAPER_SLACK:
            return name
    return f"{w:.0f}x{h:.0f}pt"


def expected_paper(region):
    """The paper a region renders on.

    Args:
        region: a region code, e.g. "US" or "AU", in either case.

    Returns:
        "Letter" for a Letter region, "A4" for any other.
    """
    from ..render.formatting import LETTER_REGIONS     # noqa: PLC0415
    return "Letter" if region.upper() in LETTER_REGIONS else "A4"


def is_tofu(c):
    """Is `c` a glyph that shows as a box: the replacement character or a private-use one?

    Args:
        c: a single character.

    Returns:
        True for U+FFFD or a codepoint in a private-use area.
    """
    return c == "�" or unicodedata.category(c) == "Co"


def check(pages, type3, region=None):
    """Every layout rule over a PDF's pages, as layout.read() returns them.

    Args:
        pages: [(page size, [(text, bbox, fonts)])], one entry per page; the size needs
            only `width` and `height`, a bbox is (x0, y0, x1, y1).
        type3: the names of the Type3 fonts the PDF embeds.
        region: the region whose paper the PDF must be on, or None to check only that it
            is A4 or Letter.

    Returns:
        (fails, warns, text families, paper names).
    """
    fails, warns = [], []

    # --- tofu ---
    bad = sorted({c for _, lines in pages for text, _, _ in lines for c in text if is_tofu(c)})
    if bad:
        fails.append(f"{len(bad)} unmappable character{'s' if len(bad) > 1 else ''} in the "
                     f"text layer: {', '.join(f'U+{ord(c):04X}' for c in bad[:4])} - a box "
                     f"on the page and noise to a parser\n"
                     f"        fix: re-render with the shipped templates; a PDF made "
                     f"elsewhere needs a font that carries the glyph")
    if type3:
        fails.append(f"Type3 (bitmap) font{'s' if len(type3) > 1 else ''}: "
                     f"{', '.join(type3[:3])} - TeX fell back to bitmaps, which blur in "
                     f"print and extract badly\n"
                     f"        fix: install lmodern (`jsk doctor` names it) and re-render")

    # --- families ---
    found = sorted({family(f) for _, lines in pages for _, _, fonts in lines for f in fonts}
                   - {""})
    text_faces = [f for f in found if not any(s.lower() in f.lower() for s in SYMBOL_FACES)]
    if len(text_faces) > 1:
        pairs = declared_pairs()
        if not (len(text_faces) == 2 and frozenset(text_faces) in pairs.values()):
            shown = "; ".join(f"{n}: {' + '.join(sorted(p))}" for n, p in pairs.items())
            fails.append(f"{len(text_faces)} type families: {', '.join(text_faces)} - one, "
                         f"or the body and heading pair a template declares ({shown})\n"
                         f"        fix: a face the template names is not installed and TeX "
                         f"substituted another - `jsk doctor`, then re-render")

    # --- a heading stranded at the foot of a page ---
    # "Below" is a top edge past the heading's middle: line boxes overlap by a point or
    # two at tight leading, and a date on the heading's own row is not content under it.
    titles = {t.casefold() for t in SECTION_TITLES}
    for number, (_, lines) in enumerate(pages, 1):
        for text, bbox, _ in lines:
            middle = (bbox[1] + bbox[3]) / 2
            if text.casefold() in titles and not any(
                    other[1] > middle for _, other, _ in lines if other is not bbox):
                fails.append(f"heading {text!r} is the last text on page {number} - its "
                             f"content starts overleaf\n"
                             f"        fix: the resume_fit tool to the budget, or cut a bullet above "
                             f"it in resume.json, and re-render")

    # --- dates out of their column ---
    dates = [(text, bbox[2], number) for number, (_, lines) in enumerate(pages, 1)
             for text, bbox, _ in lines if DATE_LINE.match(text)]
    if len(dates) > 1:
        edge = max(x for _, x, _ in dates)
        off = [(t, n) for t, x, n in dates if edge - x > DATE_SLACK]
        if off:
            fails.append(f"{len(off)} date{'s' if len(off) > 1 else ''} not flush with the "
                         f"date column: {off[0][0]!r} on page {off[0][1]}\n"
                         f"        fix: re-render - every template right-aligns dates; a "
                         f"PDF made elsewhere needs its dates tab-aligned")

    # --- paper ---
    papers = sorted({paper_name(rect) for rect, _ in pages})
    want = expected_paper(region) if region else None
    odd = [p for p in papers if p not in PAPERS or (want and p != want)]
    if odd:
        why = f"the {region.upper()} region renders on {want}" if want and region else "neither A4 nor Letter"
        fails.append(f"paper {', '.join(odd)} - {why}\n"
                     f"        fix: set `region` in resume.json to the market it is going "
                     f"to, and re-render")
    elif not want:
        warns.append("paper not checked against a region - pass --record or --region")
    return fails, warns, text_faces, papers
