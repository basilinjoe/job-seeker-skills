"""Render one target's selection in every template, so the choice can be made by looking.

This module is the entry point the `resume_preview` tool (jsk mcp) calls, through
dispatch.call_gate as `preview_templates.py`. `jsk resume preview` was retired in 6.0
(2026-10-04, docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 5): it exits 2 naming
the tool.

Usage:
  resume_preview(target, out)
  as arguments: <stem>|resumes/<name> --out DIR [--region CC]
                                    [--ats-max] [--only NAME,NAME]

Writes DIR/<template>.tex and DIR/<template>.pdf, plus DIR/<template>.png of the
first page when `pymupdf` is installed. Prints the page count for each, because
that is the one difference between templates that is not a matter of taste: the
same resume is one page in a dense template and two in an airy one, and a
two-page resume where a one-page resume was possible is a decision, not a
side effect.

Exit 0 = every template rendered.  Exit 1 = at least one did not, or the
application is frozen.  Exit 2 = usage error, a selection that does not load, a
resume.json (read until 6.0, which reads none), or no TeX engine.

This exists because `--list-templates` can only describe a template, and nobody
picks a resume design from a sentence. The templates differ in what they
emphasise, and which emphasis is right depends on the employer - which is a
judgement the person applying has to make with the pages in front of them.

Nothing here decides anything about the document: application/render/preview_templates.py
renders each template through the render use case, from the one loaded selection and
region, so the only variable is the look. The extracted text is identical in all of them,
and `tests/test_themes.py` is what says so. This module parses the flags and prints.
"""
import datetime
import os

from .cliutil import docstring_usage, wants_help
from .render import arg


def main(argv):
    """The resume_preview entry point: every template rendered, compiled and listed with its page count.

    Args:
        argv: the whole argv, the program name first.

    Returns:
        The exit code. Prints the report; writes DIR/<template>.{tex,pdf,png}. Each
        template compiles through compose.preview's Tex, which looks the engine up there.
    """
    if len(argv) < 2 or argv[1].startswith("--"):
        print(docstring_usage(__doc__))
        # Asking for help is not calling the command wrong; only a real misuse is.
        return 0 if wants_help(argv) else 2
    src = argv[1]
    from ...application.guards import is_resume_json, resume_json_refusal
    from ...application.render.selection import parse_ref
    from ..compose.selection import ref_for

    if is_resume_json(src):
        print("\n".join(resume_json_refusal(
            "resume_preview(<resume.json>, out)",
            "resume_preview(<stem>, out=DIR) (or resumes/<name>) - the target's stored "
            "selection")))
        return 2

    # A target names its selection graph, as the resume_render tool reads one (P2 of
    # docs/superpowers/plans/2026-10-03-retire-file-pipeline.md); no file is there to find.
    src = ref_for(src, dirs=True) or src
    if not parse_ref(src):
        print(f"no such target: {src}")
        print("fix:  name the target: <stem> or resumes/<name> - the resume_select tool "
              "makes its selection")
        return 2

    if "--view" in argv:
        # Before the TeX check: it is a call error on every machine. A selection is
        # one resume, and render_resume.py would refuse --view once per template.
        print("usage: a resume.json is one resume; drop --view")
        return 2
    out_dir = arg(argv, "--out")
    if not out_dir:
        print("usage: --out DIR is required - previews are scratch, not deliverables")
        return 2
    os.makedirs(out_dir, exist_ok=True)

    from ...application.render.preview_templates import PreviewStopped, preview_templates
    from ...domain.resume.short import ShortError
    from ...infra import outputs, pdf, profiles
    from ..compose.preview import Tex
    from ..compose.resume import loaded_resume
    from ..compose.timeline import frozen

    try:
        result = preview_templates(
            src, out_dir, arg(argv, "--only"), region=arg(argv, "--region"),
            ats_max="--ats-max" in argv, today=datetime.date.today(), load=loaded_resume,
            profiles=profiles, tex=Tex(), reader=pdf, outputs=outputs, frozen=frozen)
    except ShortError as err:
        print(f"FAIL  {err}")
        print(f"fix:  {err.fix}")
        return 2
    except PreviewStopped as stop:
        print(stopped(stop))
        return stop.code
    return report(result, argv[1], out_dir)


def stopped(stop):
    """What a preview that could not start prints (PreviewStopped)."""
    from ...domain.render import themes

    if stop.kind == "frozen":
        return "\n".join(stop.detail)
    if stop.kind == "no-engine":
        return ("NO RENDERER - previews are pages, and there is nothing to make one with.\n"
                "  Install tectonic, or see preflight.py.")
    return (f"unknown template(s): {', '.join(stop.detail)}\n"
            f"  choose from: {', '.join(themes.names())}")


def said(template):
    """What went wrong with a template that did not build, as its render or compile said."""
    failure = template.failure
    if failure is None:
        return template.note
    from ...application.render.render_resume import RenderStopped

    if isinstance(failure, RenderStopped):
        return f"FAIL  {failure.detail}"
    return f"render_resume.py raised {type(failure).__name__}: {failure}"


def report(result, src, out_dir):
    """Print each template's page count and blurb, or its failure, in the order asked.

    Returns:
        The exit code: 1 when any template did not build.
    """
    print(f"previewing {os.path.basename(src)} in {len(result.templates)} templates\n")
    for t in result.templates:
        if not t.pdf:
            tail = (said(t) or "").strip().splitlines()[-3:]
            print(f"  {t.name:<10} FAILED")
            for line in tail:
                print(f"             {line}")
            continue
        if t.thumbnail_note:
            print(f"  note   {t.thumbnail_note}")
        count = f"{t.pages} page{'s' if t.pages != 1 else ''}" if t.pages else "rendered"
        print(f"  {t.name:<10} {count:<8} {t.blurb}")

    print(f"\nwrote to {out_dir}")
    if result.failed:
        print(f"\nFAILED: {', '.join(result.failed)}")
        print("  A template that does not build is not a template. Report it rather")
        print("  than picking another one - the others may be about to break too.")
        return 1
    print("\nOpen them side by side and pick one. They say the same words in the")
    print("same order; what differs is which of those words a reader sees first.")
    return 0
