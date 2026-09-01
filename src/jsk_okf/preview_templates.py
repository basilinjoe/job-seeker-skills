#!/usr/bin/env python3
"""Render one URS record in every template, so the choice can be made by looking.

Usage:
  python3 preview_templates.py resume.json --out DIR [--view ID] [--region CC]
                                           [--ats-max] [--only NAME,NAME]

On Windows use `python` or `py -3` in place of `python3`.

Writes DIR/<template>.tex and DIR/<template>.pdf, plus DIR/<template>.png of the
first page when `pymupdf` is installed. Prints the page count for each, because
that is the one difference between templates that is not a matter of taste: the
same record is one page in a dense template and two in an airy one, and a
two-page resume where a one-page resume was possible is a decision, not a
side effect.

Exit 0 = every template rendered.  Exit 1 = at least one did not.
Exit 2 = usage error, or no TeX engine.

This exists because `--list-templates` can only describe a template, and nobody
picks a resume design from a sentence. The templates differ in what they
emphasise, and which emphasis is right depends on the employer - which is a
judgement the person applying has to make with the pages in front of them.

Nothing here decides anything about the document: it calls render_resume.py once
per template with the same record, view and region, so the only variable is the
look. The extracted text is identical in all of them, and
`tests/test_themes.py` is what says so.
"""
import os
import subprocess
import sys
import tempfile


from .urs import themes
from .urs.tex import available_engine

# `-m`, not a file path: a module inside a package run as a loose file gets no package
# context, so render_resume's own relative imports would fail on the way in.
RENDER = f"{__package__}.render_resume"


def arg(argv, flag, default=None):
    if flag in argv:
        try:
            return argv[argv.index(flag) + 1]
        except IndexError:
            return default
    return default


def thumbnail(pdf, png, dpi=110):
    """First page as a PNG. Optional: the PDFs are the deliverable and a
    missing pymupdf costs a convenience, not the preview."""
    try:
        import pymupdf                              # noqa: PLC0415
    except ImportError:
        return None
    try:
        with pymupdf.open(pdf) as doc:
            doc[0].get_pixmap(dpi=dpi).save(png)
            return doc.page_count
    except Exception as e:                          # noqa: BLE001 - reported, never fatal
        print(f"  note   could not read {os.path.basename(pdf)}: {e}")
        return None


def main(argv):
    if len(argv) < 2 or argv[1].startswith("--"):
        print(__doc__.strip().split("\n\n")[1])
        return 2
    src = argv[1]
    if not os.path.exists(src):
        print(f"file not found: {src}")
        return 2

    out_dir = arg(argv, "--out")
    if not out_dir:
        print("usage: --out DIR is required - previews are scratch, not deliverables")
        return 2
    os.makedirs(out_dir, exist_ok=True)

    if not available_engine():
        print("NO RENDERER - previews are pages, and there is nothing to make one with.")
        print("  Install tectonic, or see preflight.py.")
        return 2

    only = arg(argv, "--only")
    wanted = [n.strip() for n in only.split(",")] if only else themes.names()
    unknown = [n for n in wanted if n not in themes.names()]
    if unknown:
        print(f"unknown template(s): {', '.join(unknown)}")
        print(f"  choose from: {', '.join(themes.names())}")
        return 2

    passthrough = []
    for flag in ("--view", "--region"):
        value = arg(argv, flag)
        if value:
            passthrough += [flag, value]
    if "--ats-max" in argv:
        passthrough.append("--ats-max")

    print(f"previewing {os.path.basename(src)} in {len(wanted)} templates\n")
    failed = []
    for name in wanted:
        # Each render is staged in its own scratch directory, because
        # render_resume.py names its outputs after the person rather than the
        # template: five templates sharing one directory is one filename five
        # times, and the last would win silently.
        with tempfile.TemporaryDirectory() as stage:
            proc = subprocess.run(
                [sys.executable, "-m", RENDER, src, "--out", stage, "--template", name,
                 "--format", "latex", "--pdf", "--name", name] + passthrough,
                capture_output=True, text=True)
            pdf = os.path.join(stage, f"{name}_Resume.pdf")
            if proc.returncode != 0 or not os.path.exists(pdf):
                failed.append(name)
                tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-3:]
                print(f"  {name:<10} FAILED")
                for line in tail:
                    print(f"             {line}")
                continue
            final_pdf = os.path.join(out_dir, f"{name}.pdf")
            os.replace(pdf, final_pdf)
            os.replace(os.path.join(stage, f"{name}_Resume.tex"),
                       os.path.join(out_dir, f"{name}.tex"))

        pages = thumbnail(final_pdf, os.path.join(out_dir, f"{name}.png"))
        blurb = themes.get(name)["blurb"]
        count = f"{pages} page{'s' if pages != 1 else ''}" if pages else "rendered"
        print(f"  {name:<10} {count:<8} {blurb}")

    print(f"\nwrote to {out_dir}")
    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        print("  A template that does not build is not a template. Report it rather")
        print("  than picking another one - the others may be about to break too.")
        return 1
    print("\nOpen them side by side and pick one. They say the same words in the")
    print("same order; what differs is which of those words a reader sees first.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
