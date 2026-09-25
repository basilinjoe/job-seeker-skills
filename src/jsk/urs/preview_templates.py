#!/usr/bin/env python3
"""Render one resume.json in every template, so the choice can be made by looking.

Usage:
  jsk preview resume.json --out DIR [--region CC]
                                    [--ats-max] [--only NAME,NAME]
  python -m jsk.urs.preview_templates resume.json --out DIR [the same flags]

Writes DIR/<template>.tex and DIR/<template>.pdf, plus DIR/<template>.png of the
first page when `pymupdf` is installed. Prints the page count for each, because
that is the one difference between templates that is not a matter of taste: the
same resume is one page in a dense template and two in an airy one, and a
two-page resume where a one-page resume was possible is a decision, not a
side effect.

Exit 0 = every template rendered.  Exit 1 = at least one did not.
Exit 2 = usage error, or no TeX engine.

This exists because `--list-templates` can only describe a template, and nobody
picks a resume design from a sentence. The templates differ in what they
emphasise, and which emphasis is right depends on the employer - which is a
judgement the person applying has to make with the pages in front of them.

Nothing here decides anything about the document: it calls render_resume.py once
per template with the same resume.json and region, so the only variable is the
look. The .tex files are written one after another in this interpreter; the TeX
compiles, which are external processes and nearly all of the time, run side by side. The extracted text is identical in all of them, and
`tests/test_themes.py` is what says so.
"""
import contextlib
import io
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from ..cliutil import docstring_usage, wants_help
from . import render_resume, themes
from .tex import available_engine, compile_pdf


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


def render_tex(src, stage, name, passthrough):
    """(exit code, what render_resume.py said) for one template's .tex, no PDF yet.

    In this interpreter rather than a child one, and captured: only the tail of a
    failure is shown, the way the tail of a spawned render's output used to be.
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = render_resume.main(
                ["render_resume.py", src, "--out", stage, "--template", name,
                 "--format", "latex", "--name", name] + passthrough)
    except Exception as exc:                        # noqa: BLE001 - one template, reported
        return 2, buf.getvalue() + f"render_resume.py raised {type(exc).__name__}: {exc}"
    return code, buf.getvalue()


def main(argv):
    if len(argv) < 2 or argv[1].startswith("--"):
        print(docstring_usage(__doc__))
        # Asking for help is not calling the command wrong; only a real misuse is.
        return 0 if wants_help(argv) else 2
    src = argv[1]
    if not os.path.exists(src):
        print(f"file not found: {src}")
        return 2

    if "--view" in argv:
        # Before the TeX check: it is a call error on every machine. A resume.json is
        # one resume, and render_resume.py would refuse --view once per template.
        print("usage: a resume.json is one resume; drop --view")
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
    for flag in ("--region",):
        value = arg(argv, flag)
        if value:
            passthrough += [flag, value]
    if "--ats-max" in argv:
        passthrough.append("--ats-max")

    print(f"previewing {os.path.basename(src)} in {len(wanted)} templates\n")
    failed = []
    with contextlib.ExitStack() as stack:
        # Each render is staged in its own scratch directory, because
        # render_resume.py names its outputs after the person rather than the
        # template: five templates sharing one directory is one filename five
        # times, and the last would win silently. Separate directories are also
        # what lets the compiles below run at once without touching each other.
        stages, problems = {}, {}
        for name in wanted:
            stage = stack.enter_context(tempfile.TemporaryDirectory())
            code, said = render_tex(src, stage, name, passthrough)
            tex = os.path.join(stage, f"{name}_Resume.tex")
            if code != 0 or not os.path.exists(tex):
                problems[name] = said
            else:
                stages[name] = tex

        # Threads, not processes: each one only waits on a TeX engine, which is its
        # own process already. map() hands the results back in submission order, and
        # the report below walks `wanted`, so it reads the same however the
        # compiles finished.
        workers = max(1, min(len(stages), os.cpu_count() or 1))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            compiled = dict(zip(stages, pool.map(
                lambda tex: compile_pdf(tex, os.path.dirname(tex)), stages.values())))

        for name in wanted:
            pdf, note = compiled.get(name, (None, problems.get(name, "")))
            if not pdf:
                failed.append(name)
                tail = (note or "").strip().splitlines()[-3:]
                print(f"  {name:<10} FAILED")
                for line in tail:
                    print(f"             {line}")
                continue
            final_pdf = os.path.join(out_dir, f"{name}.pdf")
            os.replace(pdf, final_pdf)
            os.replace(stages[name], os.path.join(out_dir, f"{name}.tex"))

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
