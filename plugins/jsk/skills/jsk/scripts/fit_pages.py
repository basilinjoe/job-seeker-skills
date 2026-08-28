#!/usr/bin/env python3
"""Fit a rendered resume to a page budget by applying density levers in a fixed order.

Usage: python3 fit_pages.py resume.docx [--target-pages 2] [--renderer soffice]
                                        [--dry-run] [-o out.docx] [--in-place]

On Windows use `python` or `py -3` in place of `python3`.

Measures geometry FIRST, then applies levers, cheapest-looking first, stopping at the
floors `references/ats-rules.md` sets rather than crossing them:

    1  inter-paragraph spacing   floor 0pt
    2  bullet spacing            floor 0pt
    3  margins                   floor 0.5in
    4  body font size            floor 10pt

Exit 0 = fits.  Exit 1 = cannot fit without breaching a floor; the remedy is to cut
evidence, not to shrink type.  Exit 2 = usage or environment error.

Needs a PDF renderer (LibreOffice `soffice`) and `pymupdf` for geometry. Both are
external; with either missing this reports loudly and exits 2, because a page count
nobody measured is a page count nobody knows.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

TWIPS_PER_INCH = 1440
TWIPS_PER_POINT = 20
MARGIN_FLOOR_IN = 0.5
MARGIN_FLOOR = int(MARGIN_FLOOR_IN * TWIPS_PER_INCH)   # 720
FONT_FLOOR_PT = 10.0
FONT_FLOOR_SZ = int(FONT_FLOOR_PT * 2)                 # w:sz is half-points

RENDERER_NAMES = ("soffice", "libreoffice")
RENDER_TIMEOUT = 180

PARA = re.compile(r"<w:p(?:\s[^>]*)?>.*?</w:p>", re.S)
SPACING = re.compile(r'<w:spacing\b[^>]*/?>')
ATTR = re.compile(r'(w:(?:after|before))="(\d+)"')
SZ = re.compile(r'<w:(sz|szCs)\s+w:val="(\d+)"\s*/>')
PGMAR = re.compile(r'<w:pgMar\b[^>]*/>')
MAR_ATTR = re.compile(r'(w:(?:top|bottom|left|right))="(-?\d+)"')


# --- the lever plan -------------------------------------------------------------
#
# A state is (spacing, bullet_spacing, margin_twips, font_delta_halfpoints). Each step
# is derived from the ORIGINAL document rather than from the previous step, so repeated
# rounding cannot drift a value past a floor. `None` means "leave this alone".

def lever_plan():
    steps = []
    for f in (0.75, 0.5, 0.25, 0.0):
        steps.append((f"inter-paragraph spacing x{f:g}", (f, None, None, 0)))
    base = 0.0
    for f in (0.5, 0.0):
        steps.append((f"bullet spacing x{f:g}", (base, f, None, 0)))
    for inches in (0.9, 0.75, 0.6, MARGIN_FLOOR_IN):
        steps.append((f"margins {inches:.2f}in",
                      (base, 0.0, int(round(inches * TWIPS_PER_INCH)), 0)))
    for d in (1, 2, 3, 4):
        steps.append((f"body font -{d / 2:g}pt",
                      (base, 0.0, MARGIN_FLOOR, d)))
    return steps


# --- XML transforms -------------------------------------------------------------

def _scale_spacing_tag(tag, factor):
    return ATTR.sub(lambda m: f'{m.group(1)}="{int(int(m.group(2)) * factor)}"', tag)


def scale_spacing(xml, factor, lists):
    """Scale w:spacing before/after. `lists` selects which paragraphs are touched.

    True  -> only paragraphs carrying <w:numPr> (bullets)
    False -> only paragraphs without it
    None  -> everything, for parts like styles.xml that have no paragraphs
    """
    if factor is None:
        return xml
    if lists is None:
        return SPACING.sub(lambda m: _scale_spacing_tag(m.group(0), factor), xml)

    def fix(m):
        para = m.group(0)
        if ("<w:numPr" in para) != lists:
            return para
        return SPACING.sub(lambda s: _scale_spacing_tag(s.group(0), factor), para)

    return PARA.sub(fix, xml)


def set_margins(xml, twips):
    """Shrink page margins toward `twips`, clamped at the 0.5in floor. Never grows one."""
    if twips is None:
        return xml
    target = max(int(twips), MARGIN_FLOOR)

    def fix(m):
        return MAR_ATTR.sub(
            lambda a: f'{a.group(1)}="{min(int(a.group(2)), target)}"'
            if int(a.group(2)) > 0 else a.group(0),
            m.group(0))

    return PGMAR.sub(fix, xml)


def shrink_fonts(xml, delta):
    """Drop every run size by `delta` half-points, clamped at the 10pt floor."""
    if not delta:
        return xml
    return SZ.sub(
        lambda m: f'<w:{m.group(1)} w:val="{max(int(m.group(2)) - delta, FONT_FLOOR_SZ)}"/>',
        xml)


def apply_state(parts, state):
    """Return a new {part_name: text} with one lever state applied to the original."""
    spacing, bullets, margins, font = state
    out = dict(parts)
    doc = out.get("word/document.xml", "")
    doc = scale_spacing(doc, spacing, lists=False)
    doc = scale_spacing(doc, bullets, lists=True)
    doc = set_margins(doc, margins)
    doc = shrink_fonts(doc, font)
    out["word/document.xml"] = doc
    if "word/styles.xml" in out:
        styles = out["word/styles.xml"]
        # styles.xml has no paragraphs to classify, so inter-paragraph spacing there
        # moves with lever 1 and bullet spacing has no separate handle.
        styles = scale_spacing(styles, spacing, lists=None)
        styles = shrink_fonts(styles, font)
        out["word/styles.xml"] = styles
    return out


# --- docx read/write ------------------------------------------------------------

XML_PARTS = ("word/document.xml", "word/styles.xml")


def read_docx(path):
    """(editable_parts, raw_zip_entries). Raises for anything that is not a .docx."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if "word/document.xml" not in names:
            raise KeyError("no word/document.xml inside")
        parts = {n: z.read(n).decode("utf8", "replace") for n in XML_PARTS if n in names}
        raw = {n: z.read(n) for n in names if n not in parts}
    return parts, raw


def write_docx(path, parts, raw):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in parts.items():
            z.writestr(name, text.encode("utf8"))
        for name, blob in raw.items():
            z.writestr(name, blob)


def current_margins(doc):
    m = PGMAR.search(doc or "")
    if not m:
        return {}
    return {k.split(":")[1]: int(v) for k, v in MAR_ATTR.findall(m.group(0))}


def smallest_font_pt(parts):
    sizes = [int(v) for part in parts.values() for _, v in SZ.findall(part)]
    return min(sizes) / 2 if sizes else None


# --- rendering and measurement --------------------------------------------------

def find_renderer(explicit):
    if explicit:
        return shutil.which(explicit) or (explicit if os.path.exists(explicit) else None)
    for name in RENDERER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def render_pdf(renderer, docx_path, outdir):
    """Convert to PDF and return the produced path, or None if the renderer did not."""
    try:
        subprocess.run(
            [renderer, "--headless", "--convert-to", "pdf", "--outdir", outdir, docx_path],
            capture_output=True, timeout=RENDER_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
    return pdf if os.path.exists(pdf) else None


def measure_pdf(pdf_path):
    """[{height, bottom, first_text, first_height}] one entry per page, in points."""
    import pymupdf                                    # noqa: PLC0415 - optional dependency

    pages = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            blocks = [b for b in page.get_text("blocks") if (b[4] or "").strip()]
            first = blocks[0] if blocks else None
            pages.append({
                "height": page.rect.height,
                "bottom": max((b[3] for b in blocks), default=0.0),
                "first_text": " ".join((first[4] or "").split())[:60] if first else "",
                "first_height": (first[3] - first[1]) if first else 0.0,
            })
    return pages


def fill_percent(page):
    h = page["height"] or 1
    return 100.0 * page["bottom"] / h


def diagnose(pages, target, bottom_margin_pt):
    """Why the document spills: what opened the overflow page, and what room was left.

    This is the measurement the issue says was taken last instead of first. A block
    held together by keepNext either fits in the remaining space or it does not, and
    trimming words elsewhere cannot change that unless it frees a whole line.
    """
    if len(pages) <= target or target < 1:
        return None
    spilled = pages[target]
    previous = pages[target - 1]
    free = previous["height"] - bottom_margin_pt - previous["bottom"]
    return {
        "text": spilled["first_text"],
        "needs": spilled["first_height"],
        "free": max(free, 0.0),
    }


# --- reporting ------------------------------------------------------------------

def report_pages(pages, indent="  "):
    for i, p in enumerate(pages, 1):
        print(f"{indent}page {i}   fill {fill_percent(p):3.0f}%")


def report_overflow(gap, target, indent="  "):
    if not gap:
        return
    print(f"{indent}overflow: page {target + 1} opens with {gap['text']!r} "
          f"({gap['needs']:.0f}pt tall); page {target} had {gap['free']:.0f}pt free")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fit a rendered resume to a page budget without breaching the "
                    "10pt / 0.5in floors.")
    ap.add_argument("docx")
    ap.add_argument("--target-pages", type=int, default=2)
    ap.add_argument("--renderer", help="path to soffice/libreoffice; found on PATH by default")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and diagnose only; apply nothing")
    ap.add_argument("-o", "--output", help="where to write the fitted file")
    ap.add_argument("--in-place", action="store_true", help="overwrite the input file")
    a = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if a.target_pages < 1:
        print("usage: --target-pages must be at least 1")
        return 2
    if not os.path.exists(a.docx):
        print(f"file not found: {a.docx}")
        return 2
    if a.in_place and a.output:
        print("usage: pass either --in-place or -o, not both")
        return 2

    try:
        parts, raw = read_docx(a.docx)
    except zipfile.BadZipFile:
        print(f"not a readable .docx: {a.docx} is not a zip archive")
        return 2
    except (KeyError, OSError) as e:
        print(f"not a readable .docx: {e}")
        return 2

    renderer = find_renderer(a.renderer)
    if not renderer:
        print("NO RENDERER - cannot verify the page count.")
        print("  fit_pages.py needs LibreOffice to convert .docx to PDF. Install it, or")
        print("  pass --renderer /path/to/soffice. Page count is unverifiable without one,")
        print("  so this is reported rather than passed over: treat the resume as unfitted.")
        return 2
    try:
        import pymupdf                                # noqa: F401,PLC0415
    except ImportError:
        print("NO PDF LIBRARY - cannot measure the render.")
        print("  fit_pages.py needs pymupdf for page geometry:  pip install pymupdf")
        print("  Without it the page count is unverifiable; treat the resume as unfitted.")
        return 2

    name = os.path.basename(a.docx)
    print(f"fitting: {name}   target: {a.target_pages} pages   "
          f"renderer: {os.path.basename(renderer)}")

    with tempfile.TemporaryDirectory() as tmp:
        def measure(state, label):
            """Write the state to a scratch .docx, render it, and measure. None on failure."""
            candidate = os.path.join(tmp, f"{label}.docx")
            staged = apply_state(parts, state) if state else dict(parts)
            write_docx(candidate, staged, raw)
            pdf = render_pdf(renderer, candidate, tmp)
            if not pdf:
                return None, staged
            return measure_pdf(pdf), staged

        pages, _ = measure(None, "baseline")
        if pages is None:
            print(f"RENDER FAILED - {os.path.basename(renderer)} produced no PDF.")
            print("  Close any running LibreOffice instance and retry; a headless convert")
            print("  cannot share a profile with an open one.")
            return 2

        bottom_margin = current_margins(parts.get("word/document.xml", "")).get(
            "bottom", 0) / TWIPS_PER_POINT
        print(f"baseline: {len(pages)} pages")
        report_pages(pages)
        report_overflow(diagnose(pages, a.target_pages, bottom_margin), a.target_pages)

        if len(pages) <= a.target_pages:
            print(f"\nPASS - already fits {a.target_pages} pages; no levers applied")
            return 0
        if a.dry_run:
            print("\ndry run - measured only, nothing applied")
            return 1

        print("\napplying levers:")
        applied, final, final_parts = None, None, None
        for i, (label, state) in enumerate(lever_plan(), 1):
            measured, staged = measure(state, f"step{i}")
            if measured is None:
                print(f"  {i:2}  {label:<28} render failed - stopping")
                break
            print(f"  {i:2}  {label:<28} {len(measured)} pages"
                  f"{'   <- target met' if len(measured) <= a.target_pages else ''}")
            if len(measured) <= a.target_pages:
                applied, final, final_parts = label, measured, staged
                break

        if final is None:
            gap = diagnose(pages, a.target_pages, bottom_margin)
            print(f"\nFAIL - cannot reach {a.target_pages} pages without breaching a floor")
            print(f"  every lever is at its floor: {FONT_FLOOR_PT:g}pt body, "
                  f"{MARGIN_FLOOR_IN}in margins")
            if gap:
                print(f"  page {a.target_pages + 1} still carries {gap['text']!r}, "
                      f"needing {gap['needs']:.0f}pt")
            print("  Remove evidence rather than shrinking type: cut the lowest-ranked")
            print("  bullets per the treatment table in references/mode-tailor.md.")
            return 1

        out = a.docx if a.in_place else (
            a.output or os.path.splitext(a.docx)[0] + "-fitted.docx")
        write_docx(out, final_parts, raw)

        margins = current_margins(final_parts["word/document.xml"])
        smallest = smallest_font_pt(final_parts)
        print(f"\nresult: {len(final)} pages   levers applied through: {applied}")
        report_pages(final)
        if margins and smallest:
            print(f"  floors respected: smallest font {smallest:g}pt, "
                  f"smallest margin {min(margins.values()) / TWIPS_PER_INCH:.2f}in")
        print(f"wrote: {out}")
        print(f"\nPASS - fits {a.target_pages} pages")
        print("Re-run check_ats.py on the fitted file, and look at the render: "
              "fitting changes layout, and layout is what the render gate checks.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
