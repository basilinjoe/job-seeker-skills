#!/usr/bin/env python3
"""okf - one entry point for the jsk tools.

A convenience layer, never a replacement. Each subcommand forwards to the script that
does the work, with the same arguments and the same exit code, so anything documented
for the underlying script is still true here:

    okf check resume.pdf      ==     check_ats.py resume.pdf
                                     check_prose.py resume.tex

The scripts remain the stable, documented API. They are callable directly and always
will be. This exists so that nobody has to remember every name to get started.

    okf doctor                  what works on this machine
    okf new PATH --name NAME    scaffold a bundle
    okf compile BUNDLE          build the record from the concepts, deterministically
    okf validate TARGET         a record, posting or gaps .json, or a bundle
    okf render RECORD [...]     one record to a PDF and plain text
    okf preview RECORD --out D  the same record in every template, to pick a look
    okf check PDF [--strict]    the parse gate and the prose gate, both
    okf score RECORD POSTING    rank projects against a posting
    okf fit TEX [...]           fit a render to a page budget
    okf migrate BUNDLE [--apply]  bring an older bundle up to the current layout
    okf pipeline BUNDLE [...]     what the job search needs from you this week

Standard library only.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# subcommand -> (script, what it does)
SIMPLE = {
    "new": ("init_bundle.py", "scaffold an empty bundle"),
    "compile": ("okf_compile.py", "the bundle, as the record everything downstream reads"),
    "render": ("render_resume.py", "one record to .tex/PDF plus .txt"),
    "preview": ("preview_templates.py", "one record in every template, side by side"),
    "score": ("score_projects.py", "rank projects against a posting"),
    "fit": ("fit_pages.py", "fit a render to a page budget"),
    "migrate": ("migrate_bundle.py", "bring an older bundle up to the current layout"),
    "pipeline": ("pipeline.py", "what the job search needs from you this week"),
}

# The gates okf check runs, in order. Both always run: a document that fails the parse
# gate can still have prose findings worth seeing in the same pass.
#
# They no longer read the same file. check_ats.py reads what is actually sent - the
# PDF - while check_prose.py reads the .tex it was compiled from, where a bullet is
# an \item rather than a glyph that a text extractor may or may not have kept. Pass
# either one and the other is found beside it.
CHECK_GATES = [
    ("check_ats.py", "parse gate", True, (".pdf", ".txt")),   # True: forward --strict
    ("check_prose.py", "prose gate", False, (".tex", ".txt")),
]


def gate_target(path, accepts):
    """The file a gate reads, given whichever sibling the caller named."""
    stem, ext = os.path.splitext(path)
    if ext.lower() in accepts and os.path.exists(path):
        return path
    for want in accepts:
        if os.path.exists(stem + want):
            return stem + want
    return None


def run(script, args):
    """Forward to a sibling script. Returns its exit code, unchanged."""
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        print(f"FAIL  missing script: {script}")
        print(f"fix:  the skill install is incomplete - expected it at {path}")
        return 2
    # The child writes to this console directly. Without a flush our own buffered
    # output lands after it, which puts every heading under the wrong section.
    sys.stdout.flush()
    return subprocess.call([sys.executable, path] + list(args))


def cmd_doctor(args):
    """Preflight, verifying end to end unless told otherwise."""
    if "--quick" in args:
        args = [a for a in args if a != "--quick"]
    elif "--verify" not in args:
        args = list(args) + ["--verify"]
    return run("preflight.py", args)


# Which validator owns which document, by the filename each format reserves.
# Dispatching on the extension rather than on the content keeps a truncated or
# malformed file going to the validator that can explain what is wrong with it.
JSON_VALIDATORS = (
    (".posting.json", "validate_ujd.py"),   # UJD - the job posting
    (".gaps.json", "validate_ugs.py"),      # UGS - the assessment
)


def cmd_validate(args):
    """A record, a posting, an assessment or a bundle - dispatch on the target."""
    if not args:
        print("usage: okf validate "
              "<resume.json | posting.json | gaps.json | bundle-directory> [...]")
        return 2
    target = args[0]
    if os.path.isdir(target):
        return run("validate_bundle.py", args)
    if target.endswith(".json"):
        for suffix, script in JSON_VALIDATORS:
            if target.endswith(suffix):
                return run(script, args)
        return run("validate_urs.py", args)
    if not os.path.exists(target):
        print(f"file not found: {target}")
        return 2
    print(f"FAIL  cannot validate: {target}")
    print("fix:  pass a .json document or a bundle directory")
    return 2


def cmd_check(args):
    """Both document gates, in one pass, on one file."""
    if not args:
        print("usage: okf check <resume.pdf> [--strict]")
        return 2
    target = args[0]
    strict = "--strict" in args
    worst = 0
    for script, label, takes_strict, accepts in CHECK_GATES:
        path = gate_target(target, accepts)
        if not path:
            print(f"--- {label}: {script}")
            print(f"SKIPPED - no {' or '.join(accepts)} beside {os.path.basename(target)}.")
            print("  A gate that did not run is not a gate that passed.")
            worst = max(worst, 1)
            print()
            continue
        print(f"--- {label}: {script} {path}" + (" --strict" if strict and takes_strict else ""))
        gate_args = [path] + (["--strict"] if strict and takes_strict else [])
        code = run(script, gate_args)
        worst = max(worst, code)
        print()
    if worst == 0:
        print("Both document gates passed. The record and render gates are separate:")
        print("  okf validate <record>.json     before rendering")
        print("  open the PDF and read it       nobody else can do this one")
    return worst


HANDLERS = {
    "doctor": cmd_doctor,
    "validate": cmd_validate,
    "check": cmd_check,
}


def usage():
    print(__doc__.strip().split("\n\n", 1)[1].rsplit("\n\nStandard library", 1)[0])
    return 2


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        return usage()
    sub, rest = args[0], args[1:]
    if sub in HANDLERS:
        return HANDLERS[sub](rest)
    if sub in SIMPLE:
        return run(SIMPLE[sub][0], rest)
    print(f"unknown command: {sub}")
    known = sorted(list(HANDLERS) + list(SIMPLE))
    print(f"fix:  one of {', '.join(known)} - or run okf --help")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
