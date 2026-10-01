"""Render a short resume.json into a .tex (and PDF).

Usage:
  jsk resume render <resume.json> --out DIR [options]

  --format F         latex | all                   (default: all; txt is retired)
  --region CC        override the file's region profile, e.g. AU, IN, AE
  --profile P        override the file's format: presentation | ats-maximal | plaintext
  --ats-max          shorthand for --profile ats-maximal: renders the PDF in the
                     ATS-maximal variant instead of the presentation one
  --template NAME    visual theme for the PDF (default: monolith)
  --list-templates   print the themes with what each is for, and exit
  --pdf              compile the .tex with whatever TeX engine is installed
  --name N           basename for the outputs (default: the person's name in the career)

Exit 0 = rendered. Exit 1 = nothing written, or --pdf produced no PDF.
Exit 2 = usage error.

Every content decision is made once, in domain/resume/plan.py, and the emitters translate
that plan into markup without choosing anything. Which is the point: the PDF and
the plain text the gates read from one resume.json cannot say different things.

There is one rendered deliverable, the PDF, and --ats-max chooses which variant
it holds. The page count therefore describes the document actually being sent -
which it did not while the fitter measured a .docx nobody submitted.
"""
import datetime
import os

from .cliutil import docstring_usage, wants_help
from ...domain.render import themes


def arg(argv, flag, default=None):
    """The value after `flag` in `argv`; `default` when the flag or its value is missing."""
    if flag in argv:
        try:
            return argv[argv.index(flag) + 1]
        except IndexError:
            return default
    return default


def list_templates():
    """The catalogue, in the order themes.py declares - conservative first.

    Printed rather than documented only, because the choice is a judgement about
    an employer and the person making it is at a terminal, not in the docs.

    Returns:
        0. Prints the catalogue.
    """
    print("templates (--template NAME):")
    for name, blurb, best_for in themes.catalogue():
        mark = "  *" if name == themes.DEFAULT else "   "
        print(f"\n{mark} {name:<10} {blurb}")
        print(f"      for: {best_for}")
    print()
    print("  * = default. Every template extracts to identical text; the choice")
    print("      changes nothing a parser sees, only what a person sees.")
    return 0


def refused(argv):
    """The exit code for a call that is wrong before anything loads, or None.

    Args:
        argv: the whole argv, the program name first.

    Returns:
        2 (0 for --help) after printing why, or None when the call can go ahead. Creates
        --out's directory once the file is known to exist.
    """
    if len(argv) < 2 or argv[1].startswith("--"):
        # Everything from the usage line down to the Windows note: paragraph [1] is
        # the bare invocation and [2] is the flag list, so printing only [1] left
        # `--pdf`, `--ats-max` and `--template` undocumented at the one
        # place SKILL.md sends a reader to look them up.
        print(docstring_usage(__doc__))
        # Asking for help is not calling the command wrong; only a real misuse is.
        return 0 if wants_help(argv) else 2
    if arg(argv, "--format") == "txt":
        print(TXT_RETIRED)
        return 2
    src = argv[1]
    from ...application.render.selection import parse_ref

    # A graph-native target's ref names its selection graph; no file is there to find.
    if not os.path.exists(src) and not parse_ref(src):
        print(f"file not found: {src}")
        return 2
    os.makedirs(arg(argv, "--out", "."), exist_ok=True)
    try:
        themes.get(arg(argv, "--template"))
    except KeyError as e:
        # Failing here rather than at write time: an unknown template that
        # quietly rendered the default would produce a resume nobody chose,
        # and it would look perfectly fine.
        print(f"usage: {e.args[0]}")
        return 2
    if os.path.isdir(src):
        # There is no bundle format any more, so a directory here is almost always
        # somebody reaching for the old call. Say which file to pass rather than
        # failing on a JSONDecodeError from a path that is not a file.
        print(f"FAIL  cannot render a directory: {src}")
        print("fix:  pass the short resume.json - applications/<stem>/resume.json")
        return 2
    if arg(argv, "--view"):
        # A resume.json is one resume: the view, which chose a slice of a full URS
        # record, went with that record (2026-09-25).
        print("usage: a resume.json is one resume; drop --view")
        return 2
    return None


def main(argv):
    """`jsk resume render`: render one resume.json and say what was written.

    Args:
        argv: the whole argv, the program name first.

    Returns:
        The exit code. Prints the report; writes the render. The TeX engine and the
        posting's employer are compose.render's, looked up there at the call.
    """
    from .compose.render import Tex, company_of

    return rendered(argv, tex=Tex(), company_of=company_of)[0]


def rendered(argv, *, tex, company_of):
    """`jsk resume render` with what it rendered: `jsk resume ship` reads the files and pages off it.

    Args:
        argv: the whole argv, the program name first.
        tex: compiles the .tex (ports.tex.TexCompiler).
        company_of: (src, store) -> the posting's employer or None.

    Returns:
        (exit code, the RenderResult, or None when the render stopped or never ran).
        Prints the report; writes the render.
    """
    if "--list-templates" in argv:
        return list_templates(), None
    code = refused(argv)
    if code is not None:
        return code, None
    src, out_dir = argv[1], arg(argv, "--out", ".")

    # Built from the career the file sits in. A legacy URS record is refused by the load,
    # with `jsk kb export` as the fix.
    from ...application.render.render_resume import RenderStopped, render_resume
    from ...domain.resume.short import ShortError
    from ...infra import outputs, pdf, profiles
    from .compose.resume import loaded_resume
    from .compose.timeline import frozen

    try:
        result = render_resume(
            src, out_dir, load=loaded_resume, frozen=frozen, fmt=arg(argv, "--format", "all"),
            region=arg(argv, "--region"),
            profile="ats-maximal" if "--ats-max" in argv else arg(argv, "--profile"),
            template=arg(argv, "--template"), want_pdf="--pdf" in argv,
            name=arg(argv, "--name"), today=datetime.date.today(), profiles=profiles,
            company_of=company_of, tex=tex, reader=pdf, outputs=outputs)
    except ShortError as err:
        print(f"FAIL  {err}")
        print(f"fix:  {err.fix}")
        return 2, None
    except RenderStopped as stop:
        print(stopped(stop))
        return stop.code, None
    return report(result, out_dir), result


def stopped(stop):
    """What a render that stopped prints (application.render.render_resume.RenderStopped)."""
    if stop.kind == "frozen":
        return "\n".join(stop.detail)
    if stop.kind == "plan":
        return f"FAIL  {stop.detail}"
    if stop.kind == "txt":
        return TXT_RETIRED
    return f"unknown --format {stop.detail!r}: use latex or all"


# A retired option exits 2 and names its replacement (CLAUDE.md): never a silent shim.
TXT_RETIRED = ("--format txt is retired: the plain-text resume is no longer written.\n"
               "fix:  render with --format all (the .tex and, with --pdf, the PDF); the "
               "parse and terms gates\n      read the render's text in memory - "
               "jsk resume check <out-dir> --record <resume.json>")


def report(result, out_dir):
    """Print what a render wrote, measured and warned about, and the gates to run next.

    Args:
        result: the RenderResult.
        out_dir: where it wrote, which the file names are shown relative to.

    Returns:
        The exit code: 1 when nothing was written or a PDF was asked for and not made.
    """
    from ...infra.files import rel

    print(f"view: {result.view}   profile: {result.profile}   "
          f"page budget: {result.budget}   template: {result.template}")
    for path in result.written:
        print(f"  wrote  {rel(path, out_dir)}")
    for line in result.pages:
        print(line)
    for note in result.notes:
        print(f"  note   {note}")

    if result.warnings:
        print(f"\nWARN {len(result.warnings)}")
        for w in result.warnings:
            print("  warn  " + w)

    # Name only files that exist. A hint pointing at a document nobody wrote
    # teaches people the gates are decorative.
    checkable = [p for p in result.written if p.endswith(".pdf")]
    if checkable:
        print("\nRendered. Now run the gates - a rendered resume is not a checked one:")
        for path in checkable:
            strict = " --strict" if result.variants.get(path) == "ats-maximal" else ""
            print(f"  check_ats.py {os.path.basename(path)}{strict}")
        for path in result.written:
            if path.endswith(".tex"):
                print(f"  check_prose.py {os.path.basename(path)}")
    if not result.written:
        return 1
    if result.unverified:
        # A .tex nobody rendered is a resume nobody has looked at. Exiting 0
        # here taught every caller that the render gate was decorative.
        print("")
        print("UNVERIFIED - --pdf was requested and no PDF was produced.")
        print("  Nobody has seen a rendered page, so the page count and the layout")
        print("  are both unknown. A passing check_ats.py does not cover this.")
        return 1
    return 0
