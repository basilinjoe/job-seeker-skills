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
    okf compile BUNDLE          build the record from the concepts, deterministically
    okf validate TARGET         a record, posting or gaps .json, or a bundle
    okf render RECORD [...]     one record to a PDF and plain text
    okf preview RECORD --out D  the same record in every template, to pick a look
    okf check PDF [--strict]    the parse gate and the prose gate, both
      ... --only parse|prose    one of them, for re-checking one repaired file
    okf gates DIR --view ID     the record, parse and prose gates over one render
    okf score BUNDLE POSTING.md rank projects against a posting
    okf fit TEX [...]           fit a render to a page budget
    okf migrate BUNDLE [--apply]  bring an older bundle up to the current layout
    okf pipeline BUNDLE [...]     what the job search needs from you this week

Writing to a bundle is a typed command per noun. Every one takes --bundle, --dry-run,
--json and --set key=value, and every one refuses rather than writing something a gate
would reject later. `okf <noun>` lists its verbs; references/write-commands.md has the
whole surface.

    okf project|role|org|education add|set|retire|rm  the career concepts
    okf bullet|skill|credential add|set|rm|mv         the claims inside them
    okf metric add|set          a verified number, recorded once
    okf capability add          a term in the vocabulary the ranking matches on
    okf question add|resolve    the queue a person still has to answer
    okf log --message "..."     a dated row, for a change no verb covers
    okf reindex                 repair an index entry a torn write left behind
    okf posting add|requirement the advertisement, and what it asks for
    okf gaps write              the assessment it was answering
    okf view create|set|include which evidence renders, and in what order
    okf application file|event  freeze a submission, and record what came back

Standard library only, and pyyaml to read a concept back.
"""

import contextlib
import glob
import importlib
import importlib.util          # find_spec: `import importlib` alone does not bind it
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import __version__

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
    # key for --only, script, label, forwards --strict, extensions it reads
    ("parse", "check_ats.py", "parse gate", True, (".pdf", ".txt")),
    ("prose", "check_prose.py", "prose gate", False, (".tex", ".txt")),
]

CHECK_USAGE = "usage: okf check <resume.pdf> [--strict] [--only parse|prose]"


def gate_target(path, accepts):
    """The file a gate reads, given whichever sibling the caller named."""
    stem, ext = os.path.splitext(path)
    if ext.lower() in accepts and os.path.exists(path):
        return path
    for want in accepts:
        if os.path.exists(stem + want):
            return stem + want
    return None


# The three that live in the urs package rather than at the top level. Rendering, the
# preview and the page fitter are all one module with the record->document pipeline
# they drive: between them and the rest of the package there are exactly two import
# edges, and both are lazy. Kept as a table here rather than as a rename, because the
# file names are what every comment, doc heading and shell history calls them.
IN_URS = {"render_resume.py", "preview_templates.py", "fit_pages.py"}


def module_for(script):
    """`check_ats.py` -> `jsk_okf.check_ats`. The tables are keyed by the documented
    script names, which are still what docs/SCRIPTS.md and every mode file call them."""
    stem = script[:-3]
    return f"{__package__}.urs.{stem}" if script in IN_URS else f"{__package__}.{stem}"


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

    The import-instead-of-spawn that `okf gates` already does, for the commands that
    dispatch to exactly one script. call_gate() - defined further down, beside the
    gates that first needed it - does the loading, the argv0 normalisation and the
    two failure modes an in-process call adds: a module that will not import, and one
    that raises where it should have returned a verdict.
    """
    # A path or a title under a non-ASCII name reaches a cp1252 console as a
    # UnicodeEncodeError from inside the print, which loses the whole verdict. The
    # same two lines cmd_gates and authoring/commands.py carry, for the same reason.
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
        # In-process since validate_bundle.py gained a main(argv). It ran everything at
        # import and exited from module scope before that, so this was the one dispatch
        # here that had no choice but to spawn.
        return run_in_process("validate_bundle.py", args)
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
        # argv0: validate_urs.main() reads argv[1:], where validate_bundle.main() takes
        # the arguments alone. call_gate() carries that difference so neither script's
        # CLI - the documented API - has to move to suit this caller.
        return run_in_process("validate_urs.py", args, argv0=True)
    print(f"FAIL  cannot validate: {target}")
    print("fix:  pass a bundle directory, or an archived resume.json")
    return 2


def cmd_check(args):
    """Both document gates, in one pass, on one file - or one of them, with --only.

    `--only` is here because mode-resume.md names a single gate when one file has been
    repaired and only that gate needs re-running: "the right thing for re-checking one
    file after one repair". That was the one call `okf` could not express, so those
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
        return 2
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
            print(f"  {'okf check ' + os.path.basename(target):<30} the other document gate")
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
    try:
        from . import okf_compile
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


# Every noun the write layer answers to. Listed here rather than imported from
# authoring.commands, because `okf --help` and `okf <unknown>` have to name them
# without paying for the import - and the import is the only thing in this script
# that reaches pyyaml. `WriteNounsAreTheSameOnBothSides` in tests/test_okf.py
# asserts this list and the parser's own subcommands cannot drift apart.
WRITE_NOUNS = ("project", "role", "org", "education",
               "bullet", "skill", "credential", "metric",
               "capability", "question", "log", "reindex",
               "posting", "gaps", "view", "application")


def cmd_write(noun):
    """One write noun, dispatched in this interpreter.

    Imported rather than spawned, for the same reason `okf gates` imports its gates:
    the whole point of a write command is that it costs about the interpreter floor,
    and a subprocess would double that to do nothing but forward.
    """
    def run_write(args):
        from .authoring import commands  # noqa: PLC0415 - only when a write runs
        return commands.main([noun] + list(args))
    return run_write


HANDLERS = {
    "doctor": cmd_doctor,
    "validate": cmd_validate,
    "check": cmd_check,
    "gates": cmd_gates,
    "score": cmd_score,
}
HANDLERS.update({noun: cmd_write(noun) for noun in WRITE_NOUNS})


def usage():
    print(__doc__.strip().split("\n\n", 1)[1].rsplit("\n\nStandard library", 1)[0])
    return 2


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        return usage()
    if args[0] in ("--version", "-V", "version"):
        print(f"jsk-okf {__version__}")
        return 0
    sub, rest = args[0], args[1:]
    if sub in HANDLERS:
        return HANDLERS[sub](rest)
    if sub in SIMPLE:
        return run(SIMPLE[sub][0], rest)
    print(f"unknown command: {sub}")
    known = sorted(list(HANDLERS) + list(SIMPLE))
    print(f"fix:  one of {', '.join(known)} - or run okf --help")
    return 2


def main_console():
    """The `okf` and `jsk-okf` console scripts.

    Separate from main() because main() takes the whole argv the way a script's does -
    that is the documented shape every in-process caller here already uses, and the
    generated console wrapper passes no arguments at all.
    """
    return main(sys.argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
