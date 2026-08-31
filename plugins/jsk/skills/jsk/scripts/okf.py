#!/usr/bin/env python3
"""okf - one entry point for the jsk tools.

A convenience layer, never a replacement. Each subcommand reaches the script that does
the work - forwarding to it, or calling it in this interpreter where several run
together - with the same arguments and the same exit code, so anything documented for
the underlying script is still true here:

    okf check resume.pdf      ==     check_ats.py resume.pdf
                                     check_prose.py resume.tex

The scripts remain the stable, documented API. They are callable directly and always
will be. This exists so that nobody has to remember every name to get started.

    okf doctor                  what works on this machine
    okf new PATH --name NAME    scaffold a bundle
    okf project add [...]       write a Project concept, and the files that implies
    okf compile BUNDLE          build the record from the concepts, deterministically
    okf validate TARGET         a record, posting or gaps .json, or a bundle
    okf render RECORD [...]     one record to a PDF and plain text
    okf preview RECORD --out D  the same record in every template, to pick a look
    okf check PDF [--strict]    the parse gate and the prose gate, both
    okf gates DIR --view ID     the record, parse and prose gates over one render
    okf score BUNDLE POSTING.md rank projects against a posting
    okf fit TEX [...]           fit a render to a page budget
    okf migrate BUNDLE [--apply]  bring an older bundle up to the current layout
    okf pipeline BUNDLE [...]     what the job search needs from you this week

Standard library only.
"""

import contextlib
import glob
import importlib
import io
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


# --- okf gates ------------------------------------------------------------------
#
# The same gates jsk-verifier.md runs, in its order - record, parse, prose - but in
# this interpreter rather than five child ones. On a 100-posting bundle the five
# commands cost 723ms together and this costs 461ms (medians of 11); the difference
# is four interpreter starts spent calling functions that return an int. What is
# left is irreducible without a cache, and the design forbids one: 190ms of it is
# the compile the record gate checks, and 164ms is pymupdf loading so the parse
# gate can read the PDF.
#
# It is deliberately file-driven rather than a fixed list of five commands, because
# the render profile decides which files exist: the default writes
# <name>_Resume.{tex,pdf} beside <name>_Resume_ATS.txt, while --profile ats-maximal
# writes <name>_Resume_ATS.{tex,pdf,txt} and nothing else.
GATES_USAGE = ("usage: okf gates <out-dir> --view <id> [--bundle <dir>] [--pages N] "
               "[--json] [--max-findings N]")

DOC_GATES = [
    ("parse gate", "check_ats.py", (".pdf", ".txt")),
    ("prose gate", "check_prose.py", (".tex", ".txt")),
]

# The glob jsk-verifier.md already tells the agent to use when a file name is not
# given. render_resume.py's stems all contain `_Resume`, so this finds a render and
# nothing else that happens to be sitting in the directory.
RENDERED = "*_Resume*"

GATES_VALUE_FLAGS = ("--view", "--bundle", "--pages", "--max-findings")


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
    name = script[:-3]
    try:
        module = importlib.import_module(name)
    except ImportError as exc:
        return 2, (f"FAIL  cannot load {script}: {exc}\n"
                   f"fix:  the skill install is incomplete - expected it at "
                   f"{os.path.join(HERE, script)}\n")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = module.main(([script] if argv0 else []) + list(args))
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:                      # noqa: BLE001 - deliberately broad
        # In-process gates share this interpreter, so an unhandled error inside one
        # would print a traceback where a verdict belongs and take the other four
        # gates down with it. Report it as its own failure and keep going.
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
    """A gate that had nothing to read. Same wording as `okf check`, deliberately."""
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
    can run, and an `okf gates` that exited 0 without saying so would teach every
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
                import render_resume               # noqa: PLC0415 - only when asked
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

    `okf check` covers two of them and spawns a child for each; this covers three
    and spawns nothing. What it does not cover is the render gate - see
    render_section() for why that is stated rather than silently omitted.
    """
    parsed, problem = parse_gates(args)
    if problem:
        print(problem)
        print(GATES_USAGE)
        return 2
    positional, flags = parsed
    if len(positional) != 1:
        print(GATES_USAGE)
        return 2
    out_dir = positional[0]
    view = flags.get("--view")
    if not view:
        print("--view is required")
        print("fix:  name the view that was rendered - it is what the evidence below")
        print("      belongs to, and nothing else in the directory records it")
        return 2
    if not os.path.isdir(out_dir):
        print(f"not a directory: {out_dir}")
        print("fix:  pass the directory render_resume.py --out wrote to")
        return 2
    bundle = flags.get("--bundle")
    # A path that was given and is wrong is a call error; a path that was not given
    # is a missing input, which is SKIPPED and a failure further down. The two are
    # different mistakes and reporting them the same way hides one of them.
    if bundle is not None and not os.path.isdir(bundle):
        print(f"not a bundle directory: {bundle}")
        print("fix:  --bundle takes the bundle the resume was compiled from")
        return 2
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

    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    results = []
    if bundle is None:
        results.append(skipped_gate("record gate", "validate_urs.py",
                                    "no bundle given; pass --bundle <dir>."))
    else:
        record_args = [bundle] + (["--max-findings", str(limit)] if limit is not None
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
        print(json.dumps({"out_dir": out_dir, "view": view, "bundle": bundle,
                          "exit": worst, "gates": results}, indent=2))
        return worst

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(f"gates: {out_dir}   view: {view}")
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


def cmd_project(args):
    """The write layer's Project commands, in this interpreter.

    Imported rather than spawned, for the same reason `okf gates` imports its gates:
    the whole point of a write command is that it costs about the interpreter floor,
    and a subprocess would double that to do nothing but forward.
    """
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from authoring import commands   # noqa: PLC0415 - only when the subcommand runs
    return commands.main(list(args))


HANDLERS = {
    "doctor": cmd_doctor,
    "project": cmd_project,
    "validate": cmd_validate,
    "check": cmd_check,
    "gates": cmd_gates,
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
