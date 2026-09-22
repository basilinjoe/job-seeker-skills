#!/usr/bin/env python3
"""jsk - one entry point for the Job Seeker Skill's rendering and verification tools.

A convenience layer, never a replacement. Each subcommand calls the script that does
the work in this interpreter, with the same arguments and the same exit code, so
anything documented for the underlying script is still true here:

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
    jsk ship RECORD --out D --view ID   validate, render and gate, in one pass
    jsk freeze APP --submitted DATE|false --channel TEXT   archive a sent application

There is nothing here that reads `user-knowledgebase.md`. That file is Markdown a
person and the skill edit with ordinary file tools, and the skill writes the URS
record out of it. This package starts at the record: it is the last point at which a
mistake is still cheap, which is why `jsk validate` runs before anything renders.

Standard library only, and pymupdf to read a PDF.
"""

import contextlib
import datetime
import glob
import importlib
import io
import json
import os
import re
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


# The scripts whose main() takes the whole argv, program name first, the way
# `sys.exit(main(sys.argv))` hands it over. The others take the arguments alone.
# Normalised here rather than in those scripts: their CLIs are the documented API and
# must not move to suit a caller.
WHOLE_ARGV = {"validate_urs.py", "render_resume.py", "preview_templates.py",
              "preflight.py"}


def run_in_process(script, args):
    """Call a sibling script's main() in this interpreter. Exit code unchanged.

    Every dispatch used to spawn a child interpreter per call, which cost a Python
    start-up and a fresh import of the package each time - most of the wall time of
    `jsk check`. call_gate() - defined further down, beside the gates that first
    needed it - does the loading and the two failure modes an in-process call adds: a
    module that will not import, and one that raises where it should have returned a
    verdict.

    Not captured: the script writes to this stdout as it goes, so a heading printed
    before the call is above the script's output and a long `jsk fit` still shows its
    progress. The flush a child interpreter needed to keep the two in order has
    nothing left to order.
    """
    # A path or a title under a non-ASCII name reaches a cp1252 console as a
    # UnicodeEncodeError from inside the print, which loses the whole verdict.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    code, output = call_gate(script, args, capture=False)
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return code


def cmd_doctor(args):
    """Preflight, verifying end to end unless told otherwise."""
    if "--quick" in args:
        args = [a for a in args if a != "--quick"]
    elif "--verify" not in args:
        args = list(args) + ["--verify"]
    return run_in_process("preflight.py", args)


# The three formats an application archive may still hold from an older layout.
# Nothing writes them and nothing reads them: a sent application is frozen, so its
# posting and its assessment are there to be re-read by a person, not re-checked.
FROZEN = (".posting.json", ".gaps.json")

VALIDATE_USAGE = "usage: jsk validate <resume.json> [--strict] [--level N]"


def record_refusal(target):
    """Why `target` is not a record the record gate can read, or None if it is.

    Shared by `jsk validate` and `jsk ship`, so that the two commands that start at a
    record turn the same wrong file away in the same words.
    """
    if os.path.isdir(target):
        return [f"FAIL  cannot validate a directory: {target}",
                "fix:  there is no bundle format any more. Pass the resume.json the",
                "      skill wrote from user-knowledgebase.md"]
    if not os.path.exists(target):
        return [f"file not found: {target}"]
    if target.endswith(FROZEN):
        return [f"FAIL  cannot validate: {target}",
                "fix:  this is an archived UJD or UGS document from an application",
                "      that has already been sent. Both formats are retired, and a",
                "      frozen document is meant to be read, not re-checked."]
    if target.endswith(".md"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  the knowledge base is prose and is not machine-checked. What is",
                "      checked is the record written from it - pass resume.json"]
    if not target.endswith(".json"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  pass a URS record - resume.json"]
    return None


def cmd_validate(args):
    """The record gate, over one URS document."""
    if wants_help(args):
        print(VALIDATE_USAGE)
        return 0
    if not args:
        print(VALIDATE_USAGE)
        return 2
    refusal = record_refusal(args[0])
    if refusal:
        print("\n".join(refusal))
        return 2
    return run_in_process("validate_urs.py", args)


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
        code = run_in_process(script, gate_args)
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


def parse_flags(args, values, switches=("--json",), repeats=()):
    """((positional, flags), None) or (None, what was wrong with the call).

    `values` take one argument, `switches` none, and `repeats` one argument each time
    they appear, collected into a list.
    """
    positional, flags, pending = [], {}, None
    for token in args:
        if pending:
            if pending in repeats:
                flags.setdefault(pending, []).append(token)
            else:
                flags[pending] = token
            pending = None
        elif token in values or token in repeats:
            pending = token
        elif token in switches:
            flags[token] = True
        elif token.startswith("-"):
            return None, f"unknown flag: {token}"
        else:
            positional.append(token)
    if pending:
        return None, f"{pending} needs a value"
    return (positional, flags), None


def parse_gates(args):
    return parse_flags(args, GATES_VALUE_FLAGS)


def parse_pages(pages):
    """(budget or None, None) or (None, the lines saying what was wrong)."""
    if pages is None:
        return None, None
    if not str(pages).isdigit() or int(pages) < 1:
        return None, [f"--pages needs a whole number of pages, got {pages!r}",
                      "fix:  --pages 2   - the budget the view asked for"]
    return int(pages), None


def call_gate(script, args, argv0=None, capture=True):
    """(exit code, everything the gate printed). Imported, never spawned.

    The output is captured so that --json can carry it whole; it is printed back
    unchanged either way. A gate whose findings the caller cannot read is a gate
    nobody checked, and summarising one here would be the same defect as an agent
    paraphrasing it. With `capture=False` the script prints straight through, and
    what comes back is only what this function itself had to say.

    `argv0` defaults to whether the script is in WHOLE_ARGV - validate_urs.main()
    takes the whole argv where the two document gates take the arguments alone.
    """
    if argv0 is None:
        argv0 = script in WHOLE_ARGV
    name = module_for(script)
    try:
        module = importlib.import_module(name)
    except ImportError as exc:
        return 2, (f"FAIL  cannot load {script}: {exc}\n"
                   f"fix:  the install is incomplete - expected the module {name}\n")
    buf = io.StringIO()
    sink = contextlib.redirect_stdout(buf) if capture else contextlib.nullcontext()
    try:
        with sink:
            code = module.main(([script] if argv0 else []) + list(args))
    except SystemExit as exc:
        # argparse's --help exits 0 by raising; so would a bare sys.exit(). Both are
        # a clean exit in a child interpreter and have to be one here.
        code = 0 if exc.code is None else (exc.code if isinstance(exc.code, int) else 2)
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

    `jsk check` covers two of them; this covers three, and every render the directory
    holds. What it does not cover is the render gate - see
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

    pages, problem = parse_pages(flags.get("--pages"))
    if problem:
        print("\n".join(problem))
        return 2
    limit = flags.get("--max-findings")
    if limit is not None and not str(limit).isdigit():
        print(f"--max-findings needs a whole number, got {limit!r}")
        print("fix:  --max-findings 50   - or 0 to print every finding")
        return 2
    view = flags.get("--view")

    results = gate_results(out_dir, record, pages, limit)
    worst = worst_exit(results)

    if flags.get("--json"):
        print(json.dumps({"out_dir": out_dir, "view": view, "record": record,
                          "exit": worst, "gates": results}, indent=2))
        return worst

    print_results(f"gates: {out_dir}" + (f"   view: {view}" if view else ""), results)
    return worst


def gate_results(out_dir, record, pages=None, limit=None, record_gate=True):
    """Every `jsk gates` result over one directory, the render gate last.

    Separate from cmd_gates() so that `jsk ship` and `jsk freeze` run these gates
    rather than a second copy of them: three commands that each decided what "the
    mechanical gates" meant would be three chances to disagree about it.

    `record_gate=False` is for `jsk ship`, which has just run that gate on the same
    file with the same arguments and stopped had it failed.
    """
    results = []
    if record_gate and record is None:
        results.append(skipped_gate(
            "record gate", "validate_urs.py",
            f"no record given, and no {DEFAULT_RECORD} in {out_dir}; "
            f"pass --record <resume.json>."))
    elif record_gate:
        record_args = [record] + (["--max-findings", str(limit)] if limit is not None
                                  else [])
        code, output = call_gate("validate_urs.py", record_args)
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
    return results


def worst_exit(results):
    return max([r["exit"] for r in results if r["exit"] is not None] or [0])


def print_results(title, results):
    """Each result under its `--- ` heading, its output verbatim."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(title)
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


# --- jsk ship -------------------------------------------------------------------
#
# The three commands mode-ship.md used to have an agent run by hand - validate, render
# with --pdf, gates - in one process and in that order, each stopping the next. A
# record that fails its gate is never rendered: rendering it would produce a PDF that
# looks sendable and is not.
SHIP_USAGE = ("usage: jsk ship <resume.json> --out DIR --view ID [--ats-max] "
              "[--template N] [--pages N] [--json]")

SHIP_VALUE_FLAGS = ("--out", "--view", "--template", "--pages")


def not_rendered(why):
    """The render gate's entry when ship stopped before there was anything to read.

    render_section() would look in the output directory, and a PDF left there by an
    earlier run would be named as the thing to read - a document this run never made.
    """
    return {"gate": "render gate", "command": None, "status": "UNVERIFIED",
            "exit": None,
            "output": f"UNVERIFIED - {why}, so nothing was rendered and there is no\n"
                      f"  PDF from this run for anyone to read.\n"}


def cmd_ship(args):
    """Record gate, render, mechanical gates - one process, stopping at a failure.

    Every step is an existing function: the record gate is what `jsk validate`
    runs, the render is render_resume.py's main(), and the gates are gate_results(),
    so none of their verdicts is restated here.
    """
    if wants_help(args):
        print(SHIP_USAGE)
        return 0
    parsed, problem = parse_flags(args, SHIP_VALUE_FLAGS, ("--json", "--ats-max"))
    if problem:
        print(problem)
        print(SHIP_USAGE)
        return 2
    positional, flags = parsed
    if len(positional) != 1:
        print(SHIP_USAGE)
        return 2
    record = positional[0]
    refusal = record_refusal(record)
    if refusal:
        print("\n".join(refusal))
        return 2
    for flag, why in (("--out", "the directory to render into - the application's own"),
                      ("--view", "the view this application is for; a record may hold "
                                 "several")):
        if not flags.get(flag):
            print(f"{flag} is required")
            print(f"fix:  {flag} names {why}")
            return 2
    pages, problem = parse_pages(flags.get("--pages"))
    if problem:
        print("\n".join(problem))
        return 2
    template = flags.get("--template")
    if template is not None:
        # Checked before anything runs: an unknown template is a call error, and
        # finding it after the record gate would report it as a failed render.
        from .urs import themes                        # noqa: PLC0415 - only when asked
        try:
            themes.get(template)
        except KeyError as exc:
            print(f"usage: {exc.args[0]}")
            return 2
    out_dir, view = flags["--out"], flags["--view"]

    results = []
    code, output = call_gate("validate_urs.py", [record])
    results.append(gate_result("record gate", f"validate_urs.py {record}", code, output))
    if code != 0:
        results.append(not_rendered("the record gate did not pass"))
    else:
        render_args = [record, "--out", out_dir, "--view", view, "--pdf"]
        render_args += ["--ats-max"] if flags.get("--ats-max") else []
        render_args += ["--template", template] if template else []
        code, output = call_gate("render_resume.py", render_args)
        results.append(gate_result("render", " ".join(["render_resume.py"] + render_args),
                                   code, output))
        if code != 0:
            results.append(not_rendered("the render did not finish"))
        else:
            results.extend(gate_results(out_dir, record, pages, record_gate=False))

    # 0 or 1 only. A step's own exit 2 - an ERROR from a gate that raised, or a render
    # refusing a view - is a failure of this ship, not a mistake in how it was called.
    worst = 1 if worst_exit(results) else 0
    if flags.get("--json"):
        print(json.dumps({"record": record, "out_dir": out_dir, "view": view,
                          "exit": worst, "steps": results}, indent=2))
        return worst
    print_results(f"ship: {record} -> {out_dir}   view: {view}", results)
    return worst


# --- jsk freeze -----------------------------------------------------------------
#
# mode-ship.md's "Freeze the application", which was three edits and a rename made by
# hand: the directory renamed to the day it was sent, application.md written, and
# nothing in the directory edited again. The command does the first two and refuses
# whenever the third is already true or the documents would not survive their gates.
FREEZE_USAGE = ("usage: jsk freeze <app-dir> --submitted YYYY-MM-DD|false "
                "--channel TEXT [--view ID] [--doc FILE ...]")

APPLICATION = "application.md"
POSTING = "posting.md"
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


def frontmatter_scalars(path):
    """{key: raw value} for the top-level scalar lines of a Markdown file's frontmatter.

    Not a YAML parser, deliberately: the package imports neither pyyaml nor
    jsonschema, and the two keys read here are one-line scalars. Indented lines are
    skipped, so a block list such as `requirements:` cannot lend a key to its items.
    The value is kept as written - quotes included - so writing it back out into
    application.md cannot change what it means.
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    found = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z_][\w-]*):(.*)$", line)
        if match:
            value = match.group(2).strip()
            if not value.startswith(("'", '"')):
                value = re.sub(r"\s+#.*$", "", value)
            found[match.group(1)] = value
    return found


def freeze_refusal(*lines):
    print("REFUSED - " + lines[0])
    for line in lines[1:]:
        print("  " + line)
    return 1


def application_text(company, title, view, submitted, channel, documents):
    """application.md in exactly mode-ship.md's shape."""
    lines = ["---", f"company: {company}", f"title: {title}", f"view: {view}",
             f"submitted: {submitted}", f"channel: {channel}", "documents:"]
    lines += [f"  - {doc}" for doc in documents]
    lines += ["---", "", "# Timeline", "",
              "| Date | Event | Channel | Note | Due |",
              "|---|---|---|---|---|"]
    if submitted != "false":
        # A held-back application has no submitted row, and that blank is correct.
        # Writing one to fill it would be the false green mode-ship.md forbids.
        lines.append(f"| {submitted} | submitted | {channel.replace('|', '/')} | | |")
    return "\n".join(lines) + "\n"


def cmd_freeze(args):
    """Archive one application directory: rename it to its day and write application.md.

    Never touches user-knowledgebase.md. The `## Log` row is the agent's, written in
    words a person reads; this command only freezes what the row points at.
    """
    if wants_help(args):
        print(FREEZE_USAGE)
        return 0
    parsed, problem = parse_flags(args, ("--submitted", "--channel", "--view"), (),
                                  repeats=("--doc",))
    if problem:
        print(problem)
        print(FREEZE_USAGE)
        return 2
    positional, flags = parsed
    if len(positional) != 1:
        print(FREEZE_USAGE)
        return 2
    app_dir = positional[0].rstrip("/\\") or positional[0]
    if not os.path.isdir(app_dir):
        print(f"not a directory: {app_dir}")
        print("fix:  pass the application directory - applications/<yyyy-mm-dd>-<company>-<role>/")
        return 2
    submitted = flags.get("--submitted")
    if submitted is None:
        print("--submitted is required")
        print("fix:  --submitted 2026-09-08   - the day it was sent, or `false` for one")
        print("      deliberately held back")
        return 2
    if submitted != "false":
        try:
            if datetime.date.fromisoformat(submitted).isoformat() != submitted:
                raise ValueError(submitted)
        except ValueError:
            print(f"--submitted needs YYYY-MM-DD or false, got {submitted!r}")
            print("fix:  --submitted 2026-09-08")
            return 2
    channel = (flags.get("--channel") or "").strip()
    if not channel:
        print("--channel is required")
        print("fix:  --channel \"Workday portal\"   - where it was sent")
        return 2

    target = os.path.join(app_dir, APPLICATION)
    if os.path.exists(target):
        return freeze_refusal(
            f"{target} already exists. A frozen application is never re-frozen.",
            "Later events are one appended row each in its # Timeline table.")

    posting = os.path.join(app_dir, POSTING)
    if not os.path.isfile(posting):
        return freeze_refusal(f"no {POSTING} in {app_dir}",
                              "company and title are read from its frontmatter.")
    scalars = frontmatter_scalars(posting)
    for key in ("company", "title"):
        if not scalars.get(key, "").strip("'\""):
            return freeze_refusal(f"{POSTING} has no `{key}:` in its frontmatter",
                                  "add it there - the archive names what it answered.")
    company, title = scalars["company"], scalars["title"]

    record = os.path.join(app_dir, DEFAULT_RECORD)
    try:
        with open(record, encoding="utf-8") as fh:
            views = [v.get("id") for v in json.load(fh).get("views") or []
                     if isinstance(v, dict)]
    except (OSError, ValueError, AttributeError) as exc:
        return freeze_refusal(f"cannot read the record {record}: {exc}",
                              "the view is read from it, and its gate has to pass.")
    view = flags.get("--view")
    if view is None:
        if len(views) > 1:
            print(f"the record holds {len(views)} views: {', '.join(views)}")
            print("fix:  name the one this application sent with --view <id>")
            return 2
        if not views:
            return freeze_refusal(f"{record} holds no views",
                                  "there is nothing it could have been rendered from.")
        view = views[0]
    elif view not in views:
        print(f"no view {view!r} in {record}; it holds: {', '.join(views) or 'none'}")
        print("fix:  --view names one of the record's views")
        return 2

    if flags.get("--doc"):
        documents = []
        for doc in flags["--doc"]:
            name = os.path.basename(doc)
            if not os.path.isfile(os.path.join(app_dir, name)):
                return freeze_refusal(f"--doc {doc}: no {name} in {app_dir}",
                                      "a frozen application lists what is in it.")
            documents.append(name)
    else:
        documents = sorted(name for name in os.listdir(app_dir)
                           if name.lower().endswith((".pdf", ".txt"))
                           and os.path.isfile(os.path.join(app_dir, name)))
    if not documents:
        return freeze_refusal(f"no .pdf or .txt in {app_dir}",
                              "there is nothing here that could have been sent.")

    final = app_dir
    if submitted != "false":
        base = os.path.basename(os.path.abspath(app_dir))
        dated = DATED.match(base)
        rest = dated.group(2) if dated else base
        if not dated or dated.group(1) != submitted:
            final = os.path.join(os.path.dirname(os.path.abspath(app_dir)),
                                 f"{submitted}-{rest}")
            if os.path.exists(final):
                return freeze_refusal(
                    f"cannot rename to {final}: it already exists",
                    "two applications sent the same day to the same role - name one apart.")

    # Last, and in process: the most expensive check and the one the rest were
    # getting the arguments for. A failing document is never frozen.
    results = gate_results(app_dir, record)
    print_results(f"gates: {app_dir}   view: {view}", results)
    if worst_exit(results):
        return freeze_refusal(
            "a gate above did not pass. A failing document is never frozen -",
            "an archive of something that was not sendable reads, later, as though it was.")

    if final != app_dir:
        try:
            os.rename(app_dir, final)
        except OSError as exc:
            return freeze_refusal(f"cannot rename {app_dir} to {final}: {exc}",
                                  "nothing was written.")
    written = os.path.join(final, APPLICATION)
    with open(written, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(application_text(company, title, view, submitted, channel, documents))
    print(f"froze  {written}")
    if final != app_dir:
        print(f"moved  {app_dir} -> {final}")
    print(final)
    print()
    print("Frozen on the mechanical gates. The render gate is a person's: freezing")
    print("assumes somebody opened the PDF and read it. Nothing in this directory is")
    print("edited again; append the ## Log row in user-knowledgebase.md yourself.")
    return 0


HANDLERS = {
    "doctor": cmd_doctor,
    "validate": cmd_validate,
    "check": cmd_check,
    "gates": cmd_gates,
    "ship": cmd_ship,
    "freeze": cmd_freeze,
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
        return run_in_process(SIMPLE[sub][0], rest)
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
