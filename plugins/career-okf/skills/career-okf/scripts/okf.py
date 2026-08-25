#!/usr/bin/env python3
"""okf - one entry point for the career-okf tools.

A convenience layer, never a replacement. Each subcommand forwards to the script that
does the work, with the same arguments and the same exit code, so anything documented
for the underlying script is still true here:

    okf check resume.docx     ==     check_ats.py resume.docx
                                     check_prose.py resume.docx

The nine scripts remain the stable, documented API. They are callable directly and
always will be. This exists so that nobody has to remember nine names to get started.

    okf doctor                  what works on this machine
    okf new PATH --name NAME    scaffold a bundle
    okf validate TARGET         a record (.json) or a bundle (directory)
    okf render RECORD [...]     one record to every format
    okf check DOCX [--strict]   the parse gate and the prose gate, both
    okf score BUNDLE TARGET     rank projects against a posting
    okf fit DOCX [...]          fit a render to a page budget

Standard library only.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# subcommand -> (script, what it does)
SIMPLE = {
    "new": ("init_bundle.py", "scaffold an empty bundle"),
    "render": ("render_resume.py", "one record to .tex/PDF, both .docx variants and .txt"),
    "score": ("score_projects.py", "rank projects against a posting"),
    "fit": ("fit_pages.py", "fit a render to a page budget"),
}

# The gates okf check runs, in order. Both always run: a document that fails the parse
# gate can still have prose findings worth seeing in the same pass.
CHECK_GATES = [
    ("check_ats.py", "parse gate", True),   # True: forward --strict
    ("check_prose.py", "prose gate", False),
]


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


def cmd_validate(args):
    """A record or a bundle - dispatch on what the target actually is."""
    if not args:
        print("usage: okf validate <resume.json | bundle-directory> [...]")
        return 2
    target = args[0]
    if os.path.isdir(target):
        return run("validate_bundle.py", args)
    if target.endswith(".json"):
        return run("validate_urs.py", args)
    if not os.path.exists(target):
        print(f"file not found: {target}")
        return 2
    print(f"FAIL  cannot validate: {target}")
    print("fix:  pass a .json record or a bundle directory")
    return 2


def cmd_check(args):
    """Both document gates, in one pass, on one file."""
    if not args:
        print("usage: okf check <resume.docx> [--strict]")
        return 2
    docx = args[0]
    strict = "--strict" in args
    worst = 0
    for script, label, takes_strict in CHECK_GATES:
        print(f"--- {label}: {script} {docx}" + (" --strict" if strict and takes_strict else ""))
        gate_args = [docx] + (["--strict"] if strict and takes_strict else [])
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
