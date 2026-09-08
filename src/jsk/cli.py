#!/usr/bin/env python3
"""jsk - one entry point for the Job Seeker Skill's rendering and verification tools.

A convenience layer, never a replacement. Each subcommand reaches the script that does
the work - forwarding to it, or calling it in this interpreter where several run
together - with the same arguments and the same exit code, so anything documented for
the underlying script is still true here:

    jsk check resume.pdf      ==     check_ats.py resume.pdf
                                     check_prose.py resume.tex

The scripts remain the stable, documented API. They are callable directly and always
will be. This exists so that nobody has to remember every name to get started.

    jsk doctor                  what works on this machine
    jsk new PATH --name NAME    scaffold user-knowledgebase.md and applications/
    jsk validate RECORD.json    the record gate, before anything renders
    jsk render RECORD [...]     one record to a PDF and plain text
    jsk preview RECORD --out D  the same record in every template, to pick a look
    jsk check PDF [--strict]    the parse gate and the prose gate, both
      ... --only parse|prose    one of them, for re-checking one repaired file
    jsk gates DIR [--record R]  the record, parse and prose gates over one render
    jsk fit TEX [...]           fit a render to a page budget

There is nothing here that reads `user-knowledgebase.md`. That file is Markdown a
person and the skill edit with ordinary file tools, and the skill writes the URS
record out of it. This package starts at the record: it is the last point at which a
mistake is still cheap, which is why `jsk validate` runs before anything renders.

Standard library only, and pymupdf to read a PDF.
"""

import contextlib
import glob
import importlib
import importlib.util          # find_spec: `import importlib` alone does not bind it
import io
import json
import os
import subprocess
import sys

from . import __version__
from .cliutil import wants_help

# subcommand -> (script, what it does)
SIMPLE = {
    "new": ("kb.py", "scaffold an empty knowledge base"),
    "render": ("render_resume.py", "one record to .tex/PDF plus .txt"),
    "preview": ("preview_templates.py", "one record in every template, side by side"),
    "fit": ("fit_pages.py", "fit a render to a page budget"),
}

# The gates jsk check runs, in order. Both always run: a document that fails the parse
# gate can still have prose findings worth seeing in the same pass.
#
# They no longer read the same file. check_ats.py reads what is actually sent - the
# PDF - while check_prose.py reads the .tex it was compiled from, where a bullet is
# an \item rather than a glyph that a text extractor may or may not have kept. Pass
# either one and the other is found beside it.
CHECK_GATES = [
    # key for --only, script, label, forwards --strict, extensions it reads
    ("parse", "check_ats.py", "parse gate", True, (".pdf", ".txt")),
    ("prose", "check_prose.py", "prose gate", False, (".tex", ".txt")),
]

CHECK_USAGE = "usage: jsk check <resume.pdf> [--strict] [--only parse|prose]"


def gate_target(path, accepts):
    """The file a gate reads, given whichever sibling the caller named."""
    stem, ext = os.path.splitext(path)
    if ext.lower() in accepts and os.path.exists(path):
        return path
    for want in accepts:
        if os.path.exists(stem + want):
            return stem + want
    return None


# Which subpackage each script lives in. The tables above are keyed by the documented
# script names - what docs/SCRIPTS.md, every comment in the codebase and every shell
# history call them - so the file moves and the name does not.
#
# Both groupings were measured before they were made, because a package whose members
# do not import each other is a folder, not a module:
#
#   urs/    rendering, the preview and the page fitter, over the record->document
#           pipeline they drive. One edge leaves it, and it is lazy.
#   gates/  the record, parse and prose gates. One edge leaves it - validate_urs
#           reaching for the packaged region profiles - and one edge inside, where
#           check_prose borrows validate_urs's numeral detector.
SUBPACKAGE = {
    "render_resume.py": "urs",
    "preview_templates.py": "urs",
    "fit_pages.py": "urs",
    "check_ats.py": "gates",
    "check_prose.py": "gates",
    "validate_urs.py": "gates",
}


def module_for(script):
    """`check_ats.py` -> `jsk.gates.check_ats`."""
    stem = script[:-3]
    where = SUBPACKAGE.get(script)
    return f"{__package__}.{where}.{stem}" if where else f"{__package__}.{stem}"


def run(script, args):
    """Forward to a sibling module in a child interpreter. Exit code unchanged.

    `-m` rather than a file path: inside a package a module run as a loose file has no
    package context, so its own `from . import ...` would fail on the way in.
    """
    module = module_for(script)
    if importlib.util.find_spec(module) is None:
        print(f"FAIL  missing script: {script}")
        print(f"fix:  the install is incomplete - expected the module {module}")
        return 2
    # The child writes to this console directly. Without a flush our own buffered
    # output lands after it, which puts every heading under the wrong section.
    sys.stdout.flush()
    return subprocess.call([sys.executable, "-m", module] + list(args))


def run_in_process(script, args, argv0=False):
    """Call a sibling script's main() in this interpreter and print what it said.

    The import-instead-of-spawn that `jsk gates` already does, for the commands that
    dispatch to exactly one script. call_gate() - defined further down, beside the
    gates that first needed it - does the loading, the argv0 normalisation and the
    two failure modes an in-process call adds: a module that will not import, and one
    that raises where it should have returned a verdict.
    """
    # A path or a title under a non-ASCII name reaches a cp1252 console as a
    # UnicodeEncodeError from inside the print, which loses the whole verdict.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    code, output = call_gate(script, args, argv0=argv0)
    print(output, end="" if output.endswith("\n") else "\n")
    return code


def cmd_doctor(args):
    """Preflight, verifying end to end unless told otherwise."""
    if "--quick" in args:
        args = [a for a in args if a != "--quick"]
    elif "--verify" not in args:
        args = list(args) + ["--verify"]
    return run("preflight.py", args)


# The three formats an application archive may still hold from an older layout.
# Nothing writes them and nothing reads them: a sent application is frozen, so its
# posting and its assessment are there to be re-read by a person, not re-checked.
FROZEN = (".posting.json", ".gaps.json")

VALIDATE_USAGE = "usage: jsk validate <resume.json> [--strict] [--level N]"


def cmd_validate(args):
    """The record gate, over one URS document."""
    if wants_help(args):
        print(VALIDATE_USAGE)
        return 0
    if not args:
        print(VALIDATE_USAGE)
        return 2
    target = args[0]
    if os.path.isdir(target):
        print(f"FAIL  cannot validate a directory: {target}")
        print("fix:  there is no bundle format any more. Pass the resume.json the")
        print("      skill wrote from user-knowledgebase.md")
        return 2
    if not os.path.exists(target):
        print(f"file not found: {target}")
        return 2
    if target.endswith(FROZEN):
        print(f"FAIL  cannot validate: {target}")
        print("fix:  this is an archived UJD or UGS document from an application")
        print("      that has already been sent. Both formats are retired, and a")
        print("      frozen document is meant to be read, not re-checked.")
        return 2
    if target.endswith(".md"):
        print(f"FAIL  cannot validate: {target}")
        print("fix:  the knowledge base is prose and is not machine-checked. What is")
        print("      checked is the record written from it - pass resume.json")
        return 2
    if target.endswith(".json"):
        # argv0: validate_urs.main() reads argv[1:] the way a script's main does.
        # Normalised here rather than in that script: its CLI is the documented API
        # and must not move to suit a caller.
        return run_in_process("validate_urs.py", args, argv0=True)
    print(f"FAIL  cannot validate: {target}")
    print("fix:  pass a URS record - resume.json")
    return 2


def cmd_check(args):
    """Both document gates, in one pass, on one file - or one of them, with --only.

    `--only` is here because mode-resume.md names a single gate when one file has been
    repaired and only that gate needs re-running: "the right thing for re-checking one
    file after one repair". That was the one call `jsk` could not express, so those
    lines reached past it to check_ats.py and check_prose.py directly.
    """
    args = list(args)
    only = None
    if "--only" in args:
        at = args.index("--only")
        if at + 1 >= len(args):
            print("--only needs a value")
            print("fix:  --only parse   or   --only prose")
            return 2
        only = args[at + 1]
        keys = [gate[0] for gate in CHECK_GATES]
        if only not in keys:
            print(f"unknown gate: {only}")
            print(f"fix:  one of {', '.join(keys)} - or leave --only off to run both")
            return 2
        del args[at:at + 2]
    if not args or args[0].startswith("-"):
        print(CHECK_USAGE)
        return 0 if wants_help(args) else 2
    target = args[0]
    strict = "--strict" in args
    gates = [gate for gate in CHECK_GATES if only is None or gate[0] == only]
    ran = None
    worst = 0
    for _, script, label, takes_strict, accepts in gates:
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
        ran = label
        print()
    if worst == 0:
        # Naming what did not run is the whole point of this trailer, so --only has to
        # count the gate it skipped. Saying "both gates passed" after running one is
        # the exact false green the wording exists to prevent.
        if only is None:
            print("Both document gates passed. The record and render gates are separate:")
        else:
            print(f"The {ran} passed. Three gates did not run:")
            # Padded to the same column as the two fixed lines below it.
            print(f"  {'jsk check ' + os.path.basename(target):<30} the other document gate")
        print("  jsk validate <record>.json     before rendering")
        print("  open the PDF and read it       nobody else can do this one")
    return worst


# --- jsk gates ------------------------------------------------------------------
#
# The same gates jsk-verifier.md runs, in its order - record, parse, prose - but in
# this interpreter rather than five child ones.
#
# It is deliberately file-driven rather than a fixed list of five commands, because
# the render profile decides which files exist: the default writes
# <name>_Resume.{tex,pdf} beside <name>_Resume_ATS.txt, while --profile ats-maximal
# writes <name>_Resume_ATS.{tex,pdf,txt} and nothing else.
GATES_USAGE = ("usage: jsk gates <out-dir> [--record <resume.json>] [--view <id>] "
               "[--pages N] [--json] [--max-findings N]")

DOC_GATES = [
    ("parse gate", "check_ats.py", (".pdf", ".txt")),
    ("prose gate", "check_prose.py", (".tex", ".txt")),
]

# The glob jsk-verifier.md already tells the agent to use when a file name is not
# given. render_resume.py's stems all contain `_Resume`, so this finds a render and
# nothing else that happens to be sitting in the directory.
RENDERED = "*_Resume*"

GATES_VALUE_FLAGS = ("--view", "--record", "--pages", "--max-findings")

# The name the skill writes beside a render, and what `--record` defaults to. Named
# rather than searched: a directory holding two records has no way to say which one
# the documents came from, and guessing would put a passing record gate against a
# resume it never described.
DEFAULT_RECORD = "resume.json"


def parse_gates(args):
    """((positional, flags), None) or (None, what was wrong with the call)."""
    positional, flags, pending = [], {}, None
    for token in args:
        if pending:
            flags[pending] = token
            pending = None
        elif token in GATES_VALUE_FLAGS:
            pending = token
        elif token == "--json":
            flags[token] = True
        elif token.startswith("-"):
            return None, f"unknown flag: {token}"
        else:
            positional.append(token)
    if pending:
        return None, f"{pending} needs a value"
    return (positional, flags), None


def call_gate(script, args, argv0=False):
    """(exit code, everything the gate printed). Imported, never spawned.

    The output is captured so that --json can carry it whole; it is printed back
    unchanged either way. A gate whose findings the caller cannot read is a gate
    nobody checked, and summarising one here would be the same defect as an agent
    paraphrasing it.

    `argv0` because validate_urs.main() takes the whole argv where the two document
    gates take the arguments alone. Normalised here rather than in those scripts:
    their CLIs are the documented API and must not move to suit a caller.
    """
    name = module_for(script)
    try:
        module = importlib.import_module(name)
    except ImportError as exc:
        return 2, (f"FAIL  cannot load {script}: {exc}\n"
                   f"fix:  the install is incomplete - expected the module {name}\n")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = module.main(([script] if argv0 else []) + list(args))
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:                      # noqa: BLE001 - deliberately broad
        # In-process gates share this interpreter, so an unhandled error inside one
        # would print a traceback where a verdict belongs and take the other gates
        # down with it. Report it as its own failure and keep going.
        return 2, buf.getvalue() + (
            f"FAIL  {script} raised {type(exc).__name__}: {exc}\n"
            f"fix:  run it directly to see the whole story - "
            f"python {script} {' '.join(str(a) for a in args)}\n")
    return (code if isinstance(code, int) else 0), buf.getvalue()


def rendered_documents(out_dir, extensions):
    """The files a render left in `out_dir` that one gate reads, in a fixed order."""
    found = []
    for ext in extensions:
        found.extend(sorted(glob.glob(os.path.join(out_dir, RENDERED + ext))))
    return found


def skipped_gate(gate, command, why):
    """A gate that had nothing to read. Same wording as `jsk check`, deliberately."""
    return {"gate": gate, "command": command, "status": "SKIPPED", "exit": 1,
            "output": f"SKIPPED - {why}\n  A gate that did not run is not a gate "
                      f"that passed.\n"}


def gate_result(gate, command, code, output):
    status = {0: "PASS", 1: "FAIL"}.get(code, "ERROR")
    return {"gate": gate, "command": command, "status": status, "exit": code,
            "output": output}


def render_section(out_dir, pages):
    """The gate this command will never run, said out loud.

    Every other line of output here is a checker's. This one is not, and it is the
    reason the command can be trusted: a resume whose parse and prose gates passed
    has still been read by nobody. `mode-ship.md` calls this the gate nobody else
    can run, and a `jsk gates` that exited 0 without saying so would teach every
    caller that the render gate is decorative - which is exactly the lesson
    render_resume.py's UNVERIFIED exit was added to unteach.
    """
    lines = []
    pdfs = rendered_documents(out_dir, (".pdf",))
    if pages is not None:
        if not pdfs:
            lines.append(f"  pages  budget {pages}, not measured - there is no PDF "
                         f"to count")
        else:
            # render_resume.py's own line, reused rather than restated. Over budget
            # is reported and not failed there because fit_pages.py owns that
            # verdict and is the only thing that can act on it; two places printing
            # one measurement in different words is how they start disagreeing.
            try:
                from .urs import render_resume           # noqa: PLC0415 - only when asked
            except ImportError as exc:
                lines.append(f"  pages  budget {pages}, not measured - "
                             f"render_resume.py would not load: {exc}")
            else:
                lines.extend(
                    render_resume.page_report(os.path.basename(pdf),
                                              render_resume.page_count(pdf), pages)
                    for pdf in pdfs)
    if pdfs:
        lines.append(f"UNVERIFIED - open {os.path.basename(pdfs[0])} and read every page.")
    else:
        lines.append(f"UNVERIFIED - there is no PDF in {out_dir} for anyone to read.")
    lines.append("  Does it look right, and is it true? Nothing above can see a stranded")
    lines.append("  heading, a tofu box, or a verb that overstates ownership. The gates")
    lines.append("  that passed say nothing about this one.")
    return {"gate": "render gate", "command": None, "status": "UNVERIFIED",
            "exit": None, "output": "\n".join(lines) + "\n"}


def cmd_gates(args):
    """The record, parse and prose gates over one rendered resume, in one process.

    `jsk check` covers two of them and spawns a child for each; this covers three
    and spawns nothing. What it does not cover is the render gate - see
    render_section() for why that is stated rather than silently omitted.
    """
    if wants_help(args):
        # Before parse_gates, which would otherwise read --help as an unknown flag.
        print(GATES_USAGE)
        return 0
    parsed, problem = parse_gates(args)
    if problem:
        print(problem)
        print(GATES_USAGE)
        return 2
    positional, flags = parsed
    if len(positional) != 1:
        print(GATES_USAGE)
        return 0 if wants_help(args) else 2
    out_dir = positional[0]
    if not os.path.isdir(out_dir):
        print(f"not a directory: {out_dir}")
        print("fix:  pass the directory render_resume.py --out wrote to")
        return 2

    # A record that was named and is wrong is a call error; one that was neither
    # named nor sitting where the skill writes it is a missing input, which is
    # SKIPPED and a failure further down. The two are different mistakes and
    # reporting them the same way hides one of them.
    record = flags.get("--record")
    if record is not None:
        if not os.path.isfile(record):
            print(f"not a record file: {record}")
            print("fix:  --record takes the resume.json the documents rendered from")
            return 2
    else:
        beside = os.path.join(out_dir, DEFAULT_RECORD)
        record = beside if os.path.isfile(beside) else None

    pages = flags.get("--pages")
    if pages is not None:
        if not str(pages).isdigit() or int(pages) < 1:
            print(f"--pages needs a whole number of pages, got {pages!r}")
            print("fix:  --pages 2   - the budget the view asked for")
            return 2
        pages = int(pages)
    limit = flags.get("--max-findings")
    if limit is not None and not str(limit).isdigit():
        print(f"--max-findings needs a whole number, got {limit!r}")
        print("fix:  --max-findings 50   - or 0 to print every finding")
        return 2
    view = flags.get("--view")

    results = []
    if record is None:
        results.append(skipped_gate(
            "record gate", "validate_urs.py",
            f"no record given, and no {DEFAULT_RECORD} in {out_dir}; "
            f"pass --record <resume.json>."))
    else:
        record_args = [record] + (["--max-findings", str(limit)] if limit is not None
                                  else [])
        code, output = call_gate("validate_urs.py", record_args, argv0=True)
        results.append(gate_result("record gate",
                                   " ".join(["validate_urs.py"] + record_args),
                                   code, output))

    for gate, script, extensions in DOC_GATES:
        found = rendered_documents(out_dir, extensions)
        if not found:
            results.append(skipped_gate(
                gate, script,
                f"no {' or '.join(extensions)} render in {out_dir}."))
            continue
        for path in found:
            name = os.path.basename(path)
            # The same rule render_resume.py prints after a render: the ATS-maximal
            # variant is the one aimed at a parser, so it is the one held to the
            # ATS-maximal rules.
            strict = script == "check_ats.py" and "_ATS" in name
            command = f"{script} {name}" + (" --strict" if strict else "")
            code, output = call_gate(script, [path] + (["--strict"] if strict else []))
            results.append(gate_result(gate, command, code, output))

    results.append(render_section(out_dir, pages))
    worst = max([r["exit"] for r in results if r["exit"] is not None] or [0])

    if flags.get("--json"):
        print(json.dumps({"out_dir": out_dir, "view": view, "record": record,
                          "exit": worst, "gates": results}, indent=2))
        return worst

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(f"gates: {out_dir}" + (f"   view: {view}" if view else ""))
    print()
    for result in results:
        header = result["gate"]
        if result["command"]:
            header += f": {result['command']}"
        elif result["gate"] == "render gate":
            header += ": nobody else can run this one"
        print(f"--- {header}")
        print(result["output"], end="" if result["output"].endswith("\n") else "\n")
        print()
    return worst


HANDLERS = {
    "doctor": cmd_doctor,
    "validate": cmd_validate,
    "check": cmd_check,
    "gates": cmd_gates,
}


def usage():
    print(__doc__.strip().split("\n\n", 1)[1].rsplit("\n\nStandard library", 1)[0])
    return 2


def main(argv):
    args = argv[1:]
    if not args:
        return usage()
    if args[0] in ("-h", "--help", "help"):
        usage()
        return 0
    if args[0] in ("--version", "-V", "version"):
        print(f"jsk {__version__}")
        return 0
    sub, rest = args[0], args[1:]
    if sub in HANDLERS:
        return HANDLERS[sub](rest)
    if sub in SIMPLE:
        return run(SIMPLE[sub][0], rest)
    print(f"unknown command: {sub}")
    known = sorted(list(HANDLERS) + list(SIMPLE))
    print(f"fix:  one of {', '.join(known)} - or run jsk --help")
    return 2


def main_console():
    """The `jsk` console script.

    Separate from main() because main() takes the whole argv the way a script's does -
    that is the documented shape every in-process caller here already uses, and the
    generated console wrapper passes no arguments at all.
    """
    return main(sys.argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
