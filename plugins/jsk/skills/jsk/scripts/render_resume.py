#!/usr/bin/env python3
"""Render a URS document into a .tex (and PDF), or plain text.

Usage:
  python3 render_resume.py resume.json --out DIR [options]

  --view ID          which view to render (default: the first one)
  --format F         latex | txt | all             (default: all)
  --region CC        override the view's region profile, e.g. AU, IN, AE
  --profile P        override format_profile: presentation | ats-maximal | plaintext
  --ats-max          shorthand for --profile ats-maximal: renders the PDF in the
                     ATS-maximal variant instead of the presentation one
  --pdf              compile the .tex with whatever TeX engine is installed
  --name N           basename for the outputs (default: from person.name.full)

On Windows use `python` or `py -3` in place of `python3`.

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

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from urs import emit_latex, emit_text, plan as planner  # noqa: E402
from urs.tex import compile_pdf  # noqa: E402

# One record, one rendered deliverable, plus the paste-in-box text. Which
# variant the PDF holds is a choice at the call site, not a second file.
DEFAULT_TARGETS = [
    ("presentation", "latex", "{name}_Resume"),
    ("plaintext", "txt", "{name}_Resume_ATS"),
]


# The stem follows the VARIANT. It used to follow the format, so
# `--format latex --profile ats-maximal` wrote `{name}_Resume.tex` and silently
# overwrote the presentation render with a different document.
STEMS = {
    "presentation": "{name}_Resume",
    "ats-maximal": "{name}_Resume_ATS",
    "plaintext": "{name}_Resume_ATS",
}


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
    if len(argv) < 2 or argv[1].startswith("--"):
        print(__doc__.strip().split("\n\n")[1])
        return 2
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

    with open(src, encoding="utf8") as fh:
        doc = json.load(fh)

    base = arg(argv, "--name") or safe_name(
        ((doc.get("person") or {}).get("name") or {}).get("full"))

    targets = select_targets(fmt, profile)

    written, warnings, notes, first = [], [], [], None
    unverified = False
    for variant, kind, stem in targets:
        try:
            rendered = planner.build(doc, view_id=view_id, region=region, fmt=variant)
        except KeyError as e:
            print(f"FAIL  {e}")
            return 1
        if first is None:
            first = rendered
        warnings.extend(f"[{variant}/{kind}] {w}" for w in rendered["warnings"])
        stem_name = stem.format(name=base)
        path = os.path.join(out_dir, stem_name)

        if kind == "latex":
            tex = path + ".tex"
            with open(tex, "w", encoding="utf8") as fh:
                fh.write(emit_latex.emit(rendered))
            written.append(tex)
            if want_pdf:
                pdf, note = compile_pdf(tex, out_dir)
                notes.append(note)
                if pdf:
                    written.append(pdf)
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
          f"page budget: {first['pages']}")
    for path in written:
        print(f"  wrote  {os.path.relpath(path, out_dir)}")
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
            strict = " --strict" if "_ATS" in name else ""
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
