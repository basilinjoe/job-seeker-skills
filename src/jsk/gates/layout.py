#!/usr/bin/env python3
"""The layout gate: what the render gate's checklist could measure, measured.

Usage: jsk check resume.pdf --only layout [--record R] [--region CC] [--pages N]
       python -m jsk.gates.layout resume.pdf [the same flags]
       --record R   the resume.json it rendered from: the region and page budget
                    are read from it. Default: a resume.json beside the PDF
       --region CC  the region whose paper the PDF must be on, e.g. US, AU
       --pages N    the page budget, when the record is not the one to ask

Exit 0 = pass. Exit 1 = do not send this file, or pymupdf is missing and nothing
was checked. Exit 2 = usage error.

A model reading page images was asked to see tofu, a second typeface, a heading
stranded at a page foot, a date out of its column and the wrong paper. Each is in
the PDF's own geometry and fonts, and a model reading pictures is neither reliable
nor free at any of them:

  FAIL  U+FFFD or a private-use codepoint in the text layer, or a Type3 font - the
        bitmap faces TeX falls back to without lmodern, which extract as garbage
  FAIL  more than one text family, unless the pair is one a shipped template
        declares for body and headings (circuit, atrium) - the check follows the
        templates, not the checklist's "one family", because two templates were
        designed with two
  FAIL  a section heading that is the last text on its page
  FAIL  a date range out of the right-hand column every other one sits in
  FAIL  paper neither A4 nor Letter, or not the one the region renders on

The page count is printed, never failed: `jsk fit` owns that verdict. What stays a
person's is whether it looks right as a whole, the region's work-rights line or
declaration, and whether it is true.
"""
import os
import re
import sys
import unicodedata

from ..cliutil import docstring_usage, wants_help

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
    hyphen or comma, the PostScript `MT`/`PS` tails and a LaTeX optical size go."""
    base = re.split(r"[-,]", SUBSET.sub("", font), maxsplit=1)[0]
    base = re.sub(r"(?:PSMT|PS|MT)$", "", base)
    return re.sub(r"\d+$", "", base) or font


def declared_pairs():
    """The two-family sets a shipped template asks for: its body face and its head face."""
    from ..urs import themes                   # noqa: PLC0415 - only when two faces show
    return {name: frozenset((PDF_FAMILY[t["body"]], PDF_FAMILY[t["head"]]))
            for name, t in themes.THEMES.items() if t["body"] != t["head"]}


def paper_name(rect):
    w, h = sorted((rect.width, rect.height))
    for name, (pw, ph) in PAPERS.items():
        if abs(w - pw) <= PAPER_SLACK and abs(h - ph) <= PAPER_SLACK:
            return name
    return f"{w:.0f}x{h:.0f}pt"


def expected_paper(region):
    from ..urs.formatting import LETTER_REGIONS     # noqa: PLC0415
    return "Letter" if region.upper() in LETTER_REGIONS else "A4"


def read(path):
    """[(page rect, [(text, bbox, fonts)]), ...] and the Type3 fonts. ImportError without
    pymupdf."""
    import pymupdf                                 # noqa: PLC0415 - optional dependency

    pages, type3 = [], set()
    with pymupdf.open(path) as doc:
        for page in doc:
            lines = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    spans = [s for s in line["spans"] if s["text"].strip()]
                    if spans:
                        lines.append(("".join(s["text"] for s in line["spans"]).strip(),
                                      line["bbox"], {s["font"] for s in spans}))
            pages.append((page.rect, lines))
            type3.update(f[3] for f in page.get_fonts() if f[2] == "Type3")
    return pages, sorted(type3)


def is_tofu(c):
    return c == "�" or unicodedata.category(c) == "Co"


def check(pages, type3, region=None):
    """(fails, warns, text families, paper names) over what read() returned."""
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
                             f"        fix: `jsk fit` to the budget, or cut a bullet above "
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
        why = f"the {region.upper()} region renders on {want}" if want else "neither A4 nor Letter"
        fails.append(f"paper {', '.join(odd)} - {why}\n"
                     f"        fix: set `region` in resume.json to the market it is going "
                     f"to, and re-render")
    elif not want:
        warns.append("paper not checked against a region - pass --record or --region")
    return fails, warns, text_faces, papers


def arg(argv, flag):
    if flag in argv:
        at = argv.index(flag)
        return argv[at + 1] if at + 1 < len(argv) else ""
    return None


def from_record(record, pdf):
    """(region, page budget, None) from the plan the render built, or (None, None, why)."""
    from .check_ats import variant_of              # noqa: PLC0415
    from ..resume import build                     # noqa: PLC0415 - only with a record
    try:
        plan, _ = build.from_path(record, fmt=variant_of(pdf))
    except Exception as exc:                       # noqa: BLE001 - reported, never fatal
        return None, None, f"{type(exc).__name__}: {exc}"
    return plan.get("region"), plan.get("pages"), None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if wants_help(argv):
        print(docstring_usage(__doc__))
        return 0
    if not argv or argv[0].startswith("-"):
        print("usage: python -m jsk.gates.layout resume.pdf [--record R] [--region CC] "
              "[--pages N]")
        return 2
    path = argv[0]
    if not path.lower().endswith(".pdf"):
        # `jsk check` finds a gate's file from whichever sibling was named.
        path = os.path.splitext(path)[0] + ".pdf"
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2
    region, pages_flag, record = arg(argv, "--region"), arg(argv, "--pages"), arg(argv, "--record")
    if "" in (region, pages_flag, record):
        print("--record, --region and --pages each need a value")
        return 2
    if pages_flag is not None and not pages_flag.isdigit():
        print(f"--pages needs a whole number of pages, got {pages_flag!r}")
        return 2
    if record is not None and not os.path.isfile(record):
        print(f"not a record file: {record}")
        print("fix:  --record takes the resume.json the PDF rendered from")
        return 2

    try:
        import pymupdf  # noqa: F401,PLC0415 - optional dependency
    except ImportError:
        print(f"SKIPPED - pymupdf is not installed, so {os.path.basename(path)} was not read.")
        print("  fix:  pip install pymupdf")
        print("  A gate that did not run is not a gate that passed.")
        return 1

    notes = []
    if record is None:
        beside = os.path.join(os.path.dirname(os.path.abspath(path)), "resume.json")
        record = beside if os.path.isfile(beside) else None
    budget = int(pages_flag) if pages_flag else None
    if record is not None and (region is None or budget is None):
        planned_region, planned_pages, why = from_record(record, path)
        if why:
            notes.append(f"{os.path.basename(record)} unread, so no region or budget: {why}")
        region = region or planned_region
        budget = budget or planned_pages

    try:
        pages, type3 = read(path)
    except Exception as exc:                       # noqa: BLE001 - the verdict, not a crash
        print(f"checking: {os.path.basename(path)}")
        print("\nFAIL 1   WARN 0")
        print(f"  FAIL  unreadable: {type(exc).__name__}: {exc}")
        print("\nDO NOT SEND - fix the failures above")
        return 1
    fails, warns, faces, papers = check(pages, type3, region)
    warns = notes + warns

    count = f"{len(pages)} page{'' if len(pages) == 1 else 's'}"
    if budget:
        count += f" of a budget of {budget} (reported; jsk fit owns that verdict)"
    print(f"checking: {os.path.basename(path)}   region: {(region or 'unknown').upper()}")
    print(f"pages: {count}   paper: {', '.join(papers)}   families: {', '.join(faces) or 'n/a'}")
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    for f in fails:
        print("  FAIL  " + f)
    for w in warns:
        print("  warn  " + w)
    print("\nPASS - the layout holds" if not fails else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
