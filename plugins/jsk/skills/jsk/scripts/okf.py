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
    okf score BUNDLE POSTING.md rank projects against a posting
    okf fit TEX [...]           fit a render to a page budget
    okf migrate BUNDLE [--apply]  bring an older bundle up to the current layout
    okf pipeline BUNDLE [...]     what the job search needs from you this week

Standard library only.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# subcommand -> (script, what it does)
SIMPLE = {
    "new": ("init_bundle.py", "scaffold an empty bundle"),
    "compile": ("okf_compile.py", "the bundle, as the record everything downstream reads"),
    "render": ("render_resume.py", "one record to .tex/PDF plus .txt"),
    "preview": ("preview_templates.py", "one record in every template, side by side"),
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


# The two formats an archive may still hold. Nothing writes them and nothing
# reads them: a sent application is frozen, so its posting and its assessment are
# there to be re-read by a person, not re-checked by a tool.
FROZEN = (".posting.json", ".gaps.json")


def cmd_validate(args):
    """A bundle or a record - dispatch on the target."""
    if not args:
        print("usage: okf validate <bundle-directory | resume.json> [...]")
        return 2
    target = args[0]
    if os.path.isdir(target):
        return run("validate_bundle.py", args)
    if not os.path.exists(target):
        print(f"file not found: {target}")
        return 2
    if target.endswith(FROZEN):
        print(f"FAIL  cannot validate: {target}")
        print("fix:  this is an archived UJD or UGS document from an application")
        print("      that has already been sent. Both formats are retired, and a")
        print("      frozen document is meant to be read, not re-checked.")
        return 2
    if target.endswith(".json"):
        return run("validate_urs.py", args)
    print(f"FAIL  cannot validate: {target}")
    print("fix:  pass a bundle directory, or an archived resume.json")
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


def cmd_score(args):
    """Rank the bundle's projects against a posting.

    Both sides are compiled here rather than in `score_projects.py`, which reads JSON
    and only JSON. That is deliberate: the scorer is arithmetic over two documents and
    has no business knowing how a bundle is stored, so the shape it wants is built for
    it and handed over.
    """
    if len(args) < 2:
        print("usage: okf score <bundle-dir | record.json> <posting.md | posting.json> [...]")
        return 2
    sys.path.insert(0, HERE)
    try:
        import okf_compile
    except SystemExit:
        return 2

    tmp = tempfile.mkdtemp(prefix="okf-score-")
    paths = []
    try:
        for arg, kind in ((args[0], "record"), (args[1], "posting")):
            if os.path.isdir(arg) or arg.endswith(".md"):
                try:
                    # views=[]: the scorer reads requirements and projects and never a
                    # view, and this call is on the tailor-analyst's hot path - a hundred
                    # views it will not open is a hundred views it should not be handed.
                    doc = (okf_compile.load(arg, views=[]) if os.path.isdir(arg)
                           else okf_compile.posting(arg))
                except okf_compile.Problem as exc:
                    print(f"FAIL  {exc}")
                    return 1
                path = os.path.join(tmp, kind + ".json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh, default=str)
                paths.append(path)
            else:
                paths.append(arg)
        return run("score_projects.py", paths + list(args[2:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


HANDLERS = {
    "doctor": cmd_doctor,
    "validate": cmd_validate,
    "check": cmd_check,
    "score": cmd_score,
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
