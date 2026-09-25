#!/usr/bin/env python3
"""Render a URS record into a .tex (and PDF), or plain text.

Usage:
  jsk render <resume.json> --out DIR [options]
  python -m jsk.urs.render_resume <resume.json> --out DIR [options]

  --view ID          which view to render; required where the record holds more
                     than one, because there is no sensible way to pick for you
  --format F         latex | txt | all             (default: all)
  --region CC        override the view's region profile, e.g. AU, IN, AE
  --profile P        override format_profile: presentation | ats-maximal | plaintext
  --ats-max          shorthand for --profile ats-maximal: renders the PDF in the
                     ATS-maximal variant instead of the presentation one
  --template NAME    visual theme for the PDF (default: monolith)
  --list-templates   print the themes with what each is for, and exit
  --pdf              compile the .tex with whatever TeX engine is installed
  --name N           basename for the outputs (default: from person.name.full)

Exit 0 = rendered. Exit 1 = nothing written, or --pdf produced no PDF.
Exit 2 = usage error.

Every content decision is made once, in urs/plan.py, and the emitters translate
that plan into markup without choosing anything. Which is the point: the PDF and
the plain text built from one view cannot say different things.

There is one rendered deliverable, the PDF, and --ats-max chooses which variant
it holds. The page count therefore describes the document actually being sent -
which it did not while the fitter measured a .docx nobody submitted.
"""
import json
import os
import sys

from ..cliutil import docstring_usage, wants_help
from . import emit_latex, emit_text, plan as planner, themes
from .resolve import ViewNotNamed
from .tex import compile_pdf

# The stem follows the VARIANT. It used to follow the format, so
# `--format latex --profile ats-maximal` wrote `{name}_Resume.tex` and silently
# overwrote the presentation render with a different document.
#
# The ATS-maximal PDF shares the presentation stem. It was `{name}_Resume_ATS.pdf`, and
# that is the name a recruiter reads on the file they were sent. --ats-max switches
# which variant the one PDF holds and never adds a second, so the two cannot collide;
# the gates tell them apart by the jsk-variant keyword in the PDF's own metadata
# (check_ats.variant_of), not by the name. The .txt keeps its suffix: it is pasted into
# a box, never attached.
STEMS = {
    "presentation": "{name}_Resume",
    "ats-maximal": "{name}_Resume",
    "plaintext": "{name}_Resume_ATS",
}


def company_of(record_path):
    """The employer from the posting.ttl beside the record, or None.

    mode-tailor.md has always laid an application out as
    `<Name>_<Company>_Resume.{tex,pdf,txt}`, and the renderer wrote `<Name>_Resume`:
    a recruiter holding five candidates' files could not tell whose was for them."""
    import re
    posting = os.path.join(os.path.dirname(os.path.abspath(record_path)), "posting.ttl")
    try:
        with open(posting, encoding="utf8") as fh:
            found = re.search(r'j:company\s+"([^"]+)"', fh.read())
    except OSError:
        return None
    return found.group(1) if found else None


def select_targets(fmt, profile):
    """(variant, kind, stem) rows to render.

    --profile names the variant the document is rendered IN; --format names a
    file kind. They compose. --profile used to be discarded entirely whenever
    --format was left at its default of `all`, so asking for an ATS-maximal
    render quietly gave you a presentation one.

    --ats-max switches the variant the PDF holds; it never adds a second PDF.
    The plain text rides along either way - it is the paste-in-box artefact and
    it is ASCII-folded whatever the PDF holds.
    """
    variant = profile or "presentation"
    if fmt != "all":
        return [(variant, fmt, STEMS.get(variant, "{name}_Resume"))]
    return [
        (variant, "latex", STEMS.get(variant, "{name}_Resume")),
        ("plaintext", "txt", STEMS["plaintext"]),
    ]


def list_templates():
    """The catalogue, in the order themes.py declares - conservative first.

    Printed rather than documented only, because the choice is a judgement about
    an employer and the person making it is at a terminal, not in the docs.
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


def page_count(pdf):
    """Pages in the PDF just written, or None if it cannot be measured.

    Optional here in the way it is not in fit_pages.py, which exits 2 without it:
    that script's whole job is the page count, where this one reports it beside the
    budget. Same import guard, different consequence.
    """
    try:
        import pymupdf                              # noqa: PLC0415 - optional dependency
    except ImportError:
        return None
    try:
        with pymupdf.open(pdf) as doc:
            return doc.page_count
    except Exception:                               # noqa: BLE001 - reported, never fatal
        return None


LAST_PAGE_FLOOR = 50      # percent of the last page's height its text reaches


def last_page_fill(pdf):
    """How far down the last page the text reaches, in percent, or None.

    fit_pages.py's own measurement, reused. The Everforth render filled 45% of page 1
    with a padded skills block and left page 2 half empty, and the page count - two,
    against a budget of two - reported it as a success."""
    try:
        from .fit_pages import fill_percent, measure_pdf    # noqa: PLC0415
        pages = measure_pdf(pdf)
    except Exception:                               # noqa: BLE001 - reported, never fatal
        return None
    return fill_percent(pages[-1]) if pages else None


def page_report(name, count, budget, fill=None):
    """One line about what was actually produced, against what was asked for.

    This printed the budget alone, which is a number nobody measured - the resume
    that prompted the fix rendered on one page against a budget of two and said so
    nowhere. Over budget is reported rather than failed: fit_pages.py owns that
    verdict, and it is the script that can do something about it. So is a last page
    under half full: it is room the budget paid for, or a page too many.
    """
    if count is None:
        return (f"  pages  {name}: budget {budget}, not measured - "
                f"pip install pymupdf to have this checked")
    measured = f"{count} page{'' if count == 1 else 's'} against a budget of {budget}"
    if count > budget:
        return f"  pages  {name}: {measured} - OVER BUDGET, run fit_pages.py"
    if count > 1 and fill is not None and fill < LAST_PAGE_FLOOR:
        return (f"  pages  {name}: {measured} - page {count} is {fill:.0f}% full: add the "
                f"evidence the budget allows, or fit it to {count - 1} "
                f"page{'' if count == 2 else 's'}")
    return f"  pages  {name}: {measured}"


def arg(argv, flag, default=None):
    if flag in argv:
        try:
            return argv[argv.index(flag) + 1]
        except IndexError:
            return default
    return default


def safe_name(text):
    keep = [c if c.isalnum() else "_" for c in (text or "Resume")]
    return "".join(keep).strip("_").replace("__", "_") or "Resume"


def main(argv):
    if "--list-templates" in argv:
        return list_templates()
    if len(argv) < 2 or argv[1].startswith("--"):
        # Everything from the usage line down to the Windows note: paragraph [1] is
        # the bare invocation and [2] is the flag list, so printing only [1] left
        # `--view`, `--pdf`, `--ats-max` and `--template` undocumented at the one
        # place SKILL.md sends a reader to look them up.
        print(docstring_usage(__doc__))
        # Asking for help is not calling the command wrong; only a real misuse is.
        return 0 if wants_help(argv) else 2
    src = argv[1]
    if not os.path.exists(src):
        print(f"file not found: {src}")
        return 2

    out_dir = arg(argv, "--out", ".")
    os.makedirs(out_dir, exist_ok=True)
    view_id = arg(argv, "--view")
    fmt = arg(argv, "--format", "all")
    region = arg(argv, "--region")
    profile = "ats-maximal" if "--ats-max" in argv else arg(argv, "--profile")
    want_pdf = "--pdf" in argv
    template = arg(argv, "--template")
    try:
        themes.get(template)
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
        print("fix:  pass the URS record - applications/<stem>/resume.json")
        return 2
    try:
        with open(src, encoding="utf8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        print(f"FAIL  file not found: {src}")
        print("fix:  pass the URS record - `jsk kb export --urs` drafts one from the career")
        return 2
    except json.JSONDecodeError as exc:
        print(f"FAIL  {os.path.basename(src)} is not valid JSON: {exc}")
        print("fix:  a record is retuned by hand after `jsk kb export --urs`, so this is")
        print("      the ordinary first failure - run `jsk validate` on it once it parses")
        return 1

    if isinstance(doc, dict) and "resume" in doc:
        # The short file: built from the career it sits in. One resume per file, so
        # there is no view to name.
        from ..resume import build as B
        from ..resume.short import ShortError

        if view_id:
            print("usage: a resume.json is one resume; drop --view")
            return 2
        try:
            store, short_doc, _ = B.load(src)
        except ShortError as err:
            print(f"FAIL  {err}")
            print(f"fix:  {err.fix}")
            return 2

        def plan_for(variant):
            return B.build(store, short_doc, region=region, fmt=variant)
        name_of = None
    else:
        def plan_for(variant):
            return planner.build(doc, view_id=view_id, region=region, fmt=variant)
        name_of = ((doc.get("person") or {}).get("name") or {}).get("full")

    base = arg(argv, "--name")
    if not base:
        base = safe_name(name_of if name_of is not None else plan_for("presentation")["name"])
        company = company_of(src)
        if company:
            base = f"{base}_{safe_name(company)}"

    targets = select_targets(fmt, profile)

    written, warnings, notes, first = [], [], [], None
    held = {}                      # pdf path -> the variant it holds
    pages = []
    unverified = False
    for variant, kind, stem in targets:
        try:
            rendered = plan_for(variant)
        except KeyError as e:
            print(f"FAIL  {e}")
            return 1
        except ViewNotNamed as e:
            # Exit 2, not 1: nothing is wrong with the record, the call left out the
            # one thing only the person can decide.
            print(f"FAIL  {e}")
            print("      fix: name the one to render with --view <id>")
            return 2
        except ValueError as e:
            # Anything else is the record: a date like 2021-xx, a value the planner
            # cannot read. The validator names the field; this only says which.
            print(f"FAIL  the record holds a value the renderer cannot read: {e}")
            print("      fix: run `jsk validate` on it, then correct the field it names")
            return 1
        if first is None:
            first = rendered
        warnings.extend(f"[{variant}/{kind}] {w}" for w in rendered["warnings"])
        stem_name = stem.format(name=base)
        path = os.path.join(out_dir, stem_name)

        if kind == "latex":
            tex = path + ".tex"
            with open(tex, "w", encoding="utf8") as fh:
                fh.write(emit_latex.emit(rendered, template=template))
            written.append(tex)
            if want_pdf:
                pdf, note = compile_pdf(tex, out_dir)
                notes.append(note)
                if pdf:
                    written.append(pdf)
                    held[pdf] = variant
                    pages.append(page_report(os.path.basename(pdf), page_count(pdf),
                                             rendered["pages"], last_page_fill(pdf)))
                else:
                    unverified = True
        elif kind == "txt":
            txt = path + ".txt"
            with open(txt, "w", encoding="ascii", errors="replace") as fh:
                fh.write(emit_text.emit(rendered))
            written.append(txt)
        else:
            print(f"unknown --format {kind!r}: use latex, txt or all")
            return 2

    print(f"view: {first['view']}   profile: {first['profile']}   "
          f"page budget: {first['pages']}   template: {template or themes.DEFAULT}")
    for path in written:
        print(f"  wrote  {os.path.relpath(path, out_dir)}")
    for line in pages:
        print(line)
    for note in notes:
        print(f"  note   {note}")

    seen = set()
    unique = [w for w in warnings if not (w in seen or seen.add(w))]
    if unique:
        print(f"\nWARN {len(unique)}")
        for w in unique:
            print("  warn  " + w)

    # Name only files that exist. A hint pointing at a document nobody wrote
    # teaches people the gates are decorative.
    checkable = [p for p in written if p.endswith((".pdf", ".txt"))]
    if checkable:
        print("\nRendered. Now run the gates - a rendered resume is not a checked one:")
        for path in checkable:
            name = os.path.basename(path)
            ats = held.get(path) == "ats-maximal" if path.endswith(".pdf") else "_ATS" in name
            strict = " --strict" if ats else ""
            print(f"  check_ats.py {name}{strict}")
        for path in written:
            if path.endswith((".tex", ".txt")):
                print(f"  check_prose.py {os.path.basename(path)}")
    if not written:
        return 1
    if unverified:
        # A .tex nobody rendered is a resume nobody has looked at. Exiting 0
        # here taught every caller that the render gate was decorative.
        print("")
        print("UNVERIFIED - --pdf was requested and no PDF was produced.")
        print("  Nobody has seen a rendered page, so the page count and the layout")
        print("  are both unknown. A passing check_ats.py does not cover this.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
