#!/usr/bin/env python3
"""jsk - one entry point for the Job Seeker Skill's rendering and verification tools.

A convenience layer, never a replacement. Each subcommand calls the module that does
the work in this interpreter, with the same arguments and the same exit code, so
anything documented for the underlying module is still true here:

    jsk check resume.pdf      ==     python -m jsk.gates.check_ats resume.pdf
                                     python -m jsk.gates.check_prose resume.tex

Every module with a CLI runs as `python -m jsk.<module>`. This exists so that nobody
has to remember every name to get started.

    jsk doctor                  what works on this machine
    jsk new PATH --name NAME    scaffold career/kb.ttl, its log at r1, and applications/
    jsk posting fetch URL APP   an Ashby, Greenhouse or Lever posting, as APP/posting.md
    jsk match POSTING.ttl       a posting against the graph record, through the vocabulary
    jsk kb VERB [...]           the graph record: apply a changeset, confirm, show, check
    jsk migrate KB.md           user-knowledgebase.md to career/kb.ttl, once, round-trip checked
    jsk validate RESUME.json    the record gate, before anything renders
    jsk render RESUME [...]     one resume.json to a PDF and plain text
    jsk preview RESUME --out D  the same resume in every template, to pick a look
    jsk check PDF [--strict]    the parse gate and the prose gate, both
      ... --only parse|prose    one of them, for re-checking one repaired file
      ... --only layout         fonts, tofu, stranded headings, date column, paper
      ... LETTER --only letter --record R   a cover letter's length, prose and numbers
    jsk gates DIR [--record R]  the record, parse, prose and layout gates over one render
    jsk fit TEX [...]           fit a render to a page budget
    jsk ship RESUME --out D     validate, render and gate, in one pass
    jsk freeze APP --submitted DATE|false --channel TEXT   archive a sent application
    jsk event APP KIND --date DATE      add a screen, an offer, a rejection to one

The career is the graph record, career/kb.ttl: changed through `jsk kb apply`, read with
`jsk kb show` and `jsk kb view`, validated on every load. `jsk kb export` writes an
application's short resume.json - the bullets chosen, as ids - out of it, every render
builds from the career and that file, and `jsk validate` checks the file and the bullets it
selects before anything renders - the last point at which a mistake is still cheap.
Only `jsk migrate` reads a user-knowledgebase.md, once, and it writes nothing into it.

pyoxigraph for the graph record, pymupdf to read a PDF, and markdown-it-py with pyyaml
for `jsk migrate`.
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

# Where `jsk --help` stops: the paragraph naming the dependencies is for whoever opens
# this file. Named once, here, and a test holds the docstring to it, so rewording that
# paragraph fails a test rather than quietly printing it as part of the help.
HELP_ENDS_BEFORE = "\n\npyoxigraph for the graph record"

# subcommand -> the script it runs, arguments unchanged. What each one does is said
# once, in the docstring above, which is what `jsk --help` prints.
SIMPLE = {
    "new": "kb.py",
    "posting": "posting.py",
    "match": "match.py",
    "kb": "kbcli.py",
    "migrate": "migrate.py",
    "event": "timeline.py",
    "render": "render_resume.py",
    "preview": "preview_templates.py",
    "fit": "fit_pages.py",
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

# Gates `--only` reaches that the default pass never runs: they check another document,
# not the render. Arguments pass through unchanged.
CHECK_ALONE = {"letter": "letter.py"}   # a cover letter: --only letter --record resume.json
# The layout gate reads the render, but only the PDF - a default pass over a .txt would
# report it SKIPPED. `jsk gates` and `jsk ship` run it; here it is asked for by name.
CHECK_ALONE["layout"] = "layout.py"

CHECK_USAGE = "usage: jsk check <resume.pdf> [--strict] [--only parse|prose|layout]"


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
#   gates/  the record, parse and prose gates. The record gate (record.py) reads the
#           graph, lazily; inside, check_prose borrows numbers.py's numeral detector.
SUBPACKAGE = {
    "render_resume.py": "urs",
    "preview_templates.py": "urs",
    "fit_pages.py": "urs",
    "check_ats.py": "gates",
    "check_prose.py": "gates",
    "record.py": "gates",
    "letter.py": "gates",
    "layout.py": "gates",
    "match.py": "graph",
    "kbcli.py": "graph",
    "timeline.py": "graph",
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
WHOLE_ARGV = {"render_resume.py", "preview_templates.py", "preflight.py", "record.py"}


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

VALIDATE_USAGE = "usage: jsk validate <resume.json> [--strict] [--max-findings N]"


def record_refusal(target):
    """Why `target` is not a record the record gate can read, or None if it is.

    Shared by `jsk validate` and `jsk ship`, so that the two commands that start at a
    record turn the same wrong file away in the same words.
    """
    if os.path.isdir(target):
        return [f"FAIL  cannot validate a directory: {target}",
                "fix:  there is no bundle format any more. Pass the application's",
                "      resume.json - `jsk kb export` writes one"]
    if not os.path.exists(target):
        return [f"file not found: {target}"]
    if target.endswith(FROZEN):
        return [f"FAIL  cannot validate: {target}",
                "fix:  this is an archived UJD or UGS document from an application",
                "      that has already been sent. Both formats are retired, and a",
                "      frozen document is meant to be read, not re-checked."]
    if target.endswith(".md"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  a user-knowledgebase.md is an old career: `jsk migrate` moves it to",
                "      career/kb.ttl, which `jsk kb check` validates. This gate reads an",
                "      application's choice from the career - pass resume.json"]
    if target.endswith(".ttl"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  the graph record is validated on every load - `jsk kb check`",
                "      shows its findings. This gate reads an application's choice from",
                "      it - pass resume.json"]
    if not target.endswith(".json"):
        return [f"FAIL  cannot validate: {target}",
                "fix:  pass the application's resume.json"]
    return None


# The line every command that took --view prints now. A resume.json is one resume: the
# view that picked a slice of a 41KB record went with the record (2026-09-25), and a
# shell history or an old mode file still passes it, so it is named, not "unknown flag".
VIEW_GONE = ["--view is gone: a resume.json is one resume", "fix:  drop --view"]


def view_refusal(args):
    """VIEW_GONE when `args` pass --view, else None."""
    return VIEW_GONE if "--view" in args else None


def cmd_validate(args):
    """The record gate, over one short resume.json."""
    if wants_help(args):
        print(VALIDATE_USAGE)
        return 0
    if not args:
        print(VALIDATE_USAGE)
        return 2
    refusal = view_refusal(args) or record_refusal(args[0])
    if refusal:
        print("\n".join(refusal))
        return 2
    return run_in_process("record.py", args)


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
        keys = [gate[0] for gate in CHECK_GATES] + list(CHECK_ALONE)
        if only not in keys:
            print(f"unknown gate: {only}")
            print(f"fix:  one of {', '.join(keys)} - or leave --only off to run both")
            return 2
        del args[at:at + 2]
    if only in CHECK_ALONE:
        return run_in_process(CHECK_ALONE[only], args)
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
# The same gates jsk-verifier.md runs, in its order - record, parse, prose, layout - but in
# this interpreter rather than five child ones.
#
# It is deliberately file-driven rather than a fixed list of five commands, because
# the render profile decides which files exist: every render writes
# <name>_Resume.{tex,pdf} beside <name>_Resume_ATS.txt, and --ats-max changes which
# variant that one PDF holds - strict_for() reads which from the PDF, not the name.
GATES_USAGE = ("usage: jsk gates <out-dir> [--record <resume.json>] "
               "[--pages N] [--json] [--max-findings N]")

DOC_GATES = [
    ("parse gate", "check_ats.py", (".pdf", ".txt")),
    ("prose gate", "check_prose.py", (".tex", ".txt")),
]

# The glob jsk-verifier.md already tells the agent to use when a file name is not
# given. render_resume.py's stems all contain `_Resume`, so this finds a render and
# nothing else that happens to be sitting in the directory.
RENDERED = "*_Resume*"

GATES_VALUE_FLAGS = ("--record", "--pages", "--max-findings")

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
                      "fix:  --pages 2   - the budget the resume asked for"]
    return int(pages), None


def call_gate(script, args, argv0=None, capture=True):
    """(exit code, everything the gate printed). Imported, never spawned.

    The output is captured so that --json can carry it whole; it is printed back
    unchanged either way. A gate whose findings the caller cannot read is a gate
    nobody checked, and summarising one here would be the same defect as an agent
    paraphrasing it. With `capture=False` the script prints straight through, and
    what comes back is only what this function itself had to say.

    `argv0` defaults to whether the script is in WHOLE_ARGV - record.main()
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
        # down with it. Report it as its own failure and keep going. The hint names the
        # module, not the file: `python fit_pages.py` stops at its first relative import.
        return 2, buf.getvalue() + (
            f"FAIL  {script} raised {type(exc).__name__}: {exc}\n"
            f"fix:  run it directly to see the whole story - "
            f"python -m {name} {' '.join(str(a) for a in args)}\n")
    return (code if isinstance(code, int) else 0), buf.getvalue()


def rendered_documents(out_dir, extensions, only=None):
    """The files a render left in `out_dir` that one gate reads, in a fixed order.

    `only` narrows it to named paths. A directory keeps every earlier render, so
    `jsk ship --ats-max` after a default ship left both PDFs beside each other, and
    gating the directory failed a run on a file it never made.
    """
    keep = None if only is None else {os.path.normcase(os.path.abspath(p)) for p in only}
    found = []
    for ext in extensions:
        found.extend(p for p in sorted(glob.glob(os.path.join(out_dir, RENDERED + ext)))
                     if keep is None or os.path.normcase(os.path.abspath(p)) in keep)
    return found


def skipped_gate(gate, command, why):
    """A gate that had nothing to read. Same wording as `jsk check`, deliberately."""
    return {"gate": gate, "command": command, "status": "SKIPPED", "exit": 1,
            "output": f"SKIPPED - {why}\n  A gate that did not run is not a gate "
                      f"that passed.\n"}


def gate_result(gate, command, code, output):
    status = {0: "PASS", 1: "FAIL"}.get(code, "ERROR")
    if code == 1 and output.startswith("SKIPPED"):
        # The layout gate without pymupdf: it says so itself, and a failure either way.
        status = "SKIPPED"
    return {"gate": gate, "command": command, "status": status, "exit": code,
            "output": output}


def strict_for(path):
    """Whether a rendered document is held to the ATS-maximal rules.

    A PDF says which variant it holds in its own metadata (jsk-variant:), because the
    ATS PDF no longer carries `_ATS` in its name - that was the name a recruiter read on
    the file. A PDF whose engine wrote no metadata falls back to the .tex it was
    compiled from, whose hypersetup line carries the same keyword; one rendered before
    the marker existed, and every .txt, still go by the name."""
    name = os.path.basename(path)
    if path.lower().endswith(".pdf"):
        from .gates.check_ats import VARIANT_KEYWORD, variant_of   # noqa: PLC0415
        try:
            variant = variant_of(path)
        except ImportError:
            variant = None
        if variant is None:
            try:
                with open(os.path.splitext(path)[0] + ".tex", encoding="utf8") as fh:
                    found = VARIANT_KEYWORD.search(fh.read())
                variant = found.group(1) if found else None
            except OSError:
                variant = None
        if variant is not None:
            return variant == "ats-maximal"
    return "_ATS" in name


def render_section(out_dir, pages, only=None):
    """The gate this command will never run, said out loud.

    Every other line of output here is a checker's. This one is not, and it is the
    reason the command can be trusted: a resume whose parse and prose gates passed
    has still been read by nobody. `mode-ship.md` calls this the gate nobody else
    can run, and a `jsk gates` that exited 0 without saying so would teach every
    caller that the render gate is decorative - which is exactly the lesson
    render_resume.py's UNVERIFIED exit was added to unteach.
    """
    lines = []
    pdfs = rendered_documents(out_dir, (".pdf",), only)
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
                                              render_resume.page_count(pdf), pages,
                                              render_resume.last_page_fill(pdf))
                    for pdf in pdfs)
    if pdfs:
        lines.append(f"UNVERIFIED - open {os.path.basename(pdfs[0])} and read every page.")
    else:
        lines.append(f"UNVERIFIED - there is no PDF in {out_dir} for anyone to read.")
    lines.append("  Does it look right as a whole, and is it true? The layout gate measures")
    lines.append("  fonts, tofu, headings, dates and paper; nothing above can see a verb that")
    lines.append("  overstates ownership. The gates that passed say nothing about this one.")
    return {"gate": "render gate", "command": None, "status": "UNVERIFIED",
            "exit": None, "output": "\n".join(lines) + "\n"}


def cmd_gates(args):
    """The record, parse, prose and layout gates over one rendered resume, in one process.

    `jsk check` covers two of them; this covers four, and every render the directory
    holds. What it does not cover is the render gate - see
    render_section() for why that is stated rather than silently omitted.
    """
    if wants_help(args):
        # Before parse_gates, which would otherwise read --help as an unknown flag.
        print(GATES_USAGE)
        return 0
    if view_refusal(args):
        print("\n".join(VIEW_GONE))
        return 2
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

    results = gate_results(out_dir, record, pages, limit)
    worst = worst_exit(results)

    if flags.get("--json"):
        print(json.dumps({"out_dir": out_dir, "record": record,
                          "exit": worst, "gates": results}, indent=2))
        return worst

    print_results(f"gates: {out_dir}", results)
    return worst


def gate_results(out_dir, record, pages=None, limit=None, record_gate=True, only=None):
    """Every `jsk gates` result over one directory, the render gate last.

    Separate from cmd_gates() so that `jsk ship` and `jsk freeze` run these gates
    rather than a second copy of them: three commands that each decided what "the
    mechanical gates" meant would be three chances to disagree about it.

    `record_gate=False` is for `jsk ship`, which has just run that gate on the same
    file and stopped had it failed. `only` names the documents to gate - see
    rendered_documents(). The record gate reads the career itself, so there is no
    claims gate beside it: the claims gate joined a copy of the career with the career,
    and the copy went with the URS record (2026-09-25).
    """
    results = []
    if record_gate and record is None:
        results.append(skipped_gate(
            "record gate", "record.py",
            f"no record given, and no {DEFAULT_RECORD} in {out_dir}; "
            f"pass --record <resume.json>."))
    elif record_gate:
        record_args = [record] + (["--max-findings", str(limit)] if limit is not None
                                  else [])
        code, output = call_gate("record.py", record_args)
        results.append(gate_result("record gate", " ".join(["record.py"] + record_args),
                                   code, output))

    for gate, script, extensions in DOC_GATES:
        found = rendered_documents(out_dir, extensions, only)
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
            strict = script == "check_ats.py" and strict_for(path)
            command = f"{script} {name}" + (" --strict" if strict else "")
            code, output = call_gate(script, [path] + (["--strict"] if strict else []))
            results.append(gate_result(gate, command, code, output))

    # The PDF alone: it reads the region and budget from the record the render used.
    pdfs = rendered_documents(out_dir, (".pdf",), only)
    if not pdfs:
        results.append(skipped_gate("layout gate", "layout.py",
                                    f"no .pdf render in {out_dir}."))
    for path in pdfs:
        layout_args = ([path] + (["--record", record] if record else [])
                       + (["--pages", str(pages)] if pages else []))
        code, output = call_gate("layout.py", layout_args)
        results.append(gate_result("layout gate", f"layout.py {os.path.basename(path)}",
                                   code, output))

    results.append(render_section(out_dir, pages, only))
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
    print("\n".join(summary_lines(results)))


# A gate's own count line, and the render's: every checker prints `FAIL n   WARN n`
# after its heading, and render_resume.py prints `WARN n` over its warnings.
COUNTS = re.compile(r"^(?:FAIL (\d+)\s+)?WARN (\d+)\s*$", re.M)
PAGES = re.compile(r"^  pages  (.+?): (\d+) pages? against a budget of (\d+)", re.M)
# build.py's warning for a line below the floor, as render_resume.py prints it:
# once per variant rendered, `  warn  [<variant>/<kind>] withheld <what> - ...`.
WITHHELD = re.compile(r"^  warn  \[[^\]]*\] withheld (.+?) - provenance", re.M)


def summary_lines(results):
    """The verdicts again, one line a step, printed after all of them.

    The ElevenLabs ship (2026-09-25) ran to about 6KB - nineteen prose WARNs among it -
    and was read through `tail -60`, which cut the record gate off the top;
    the whole ship was run a second time into a file to grep for them. This block is
    derived from the results already printed above it and restates no verdict: each
    count is the gate's own line, read back."""
    width = max(len(r["gate"]) for r in results)
    lines = ["=== summary"]
    rendered = any(r["gate"] == "render" for r in results)
    for result in results:
        output = result["output"] or ""
        parts = [result["status"]]
        counts = COUNTS.findall(output)
        if counts:
            fails, warns = counts[-1]
            parts.append((f"FAIL {fails}   " if fails else "") + f"WARN {warns}")
        command = result["command"] or ""
        if result["gate"] in ("parse gate", "prose gate", "layout gate") and command:
            parts.append(command.split()[1] if len(command.split()) > 1 else command)
        # The render's measurement, or - under `jsk gates`, which renders nothing -
        # the render gate's under --pages. Never both: ship's --pages is a second
        # budget for the same count.
        if result["gate"] == "render" or (result["gate"] == "render gate"
                                          and not rendered):
            parts.extend(f"{name} {count} of {budget} pages"
                         for name, count, budget in PAGES.findall(output))
        if result["gate"] == "render":
            # One line per line held back, however many variants carried it.
            withheld = set(WITHHELD.findall(output))
            parts.append(f"withheld {len(withheld)} below the floor")
        lines.append(f"  {result['gate']:<{width}}  " + "   ".join(parts))
    worst = worst_exit(results)
    if worst:
        failed = [r["gate"] for r in results if r["exit"]]
        lines.append(f"verdict: FAIL - {', '.join(dict.fromkeys(failed))}; "
                     f"read that section above")
    else:
        lines.append("verdict: PASS on the mechanical gates - the render gate is still "
                     "a person's: open the PDF and read every page")
    return lines


# --- jsk ship -------------------------------------------------------------------
#
# The three commands mode-ship.md used to have an agent run by hand - validate, render
# with --pdf, gates - in one process and in that order, each stopping the next. A
# record that fails its gate is never rendered: rendering it would produce a PDF that
# looks sendable and is not.
SHIP_USAGE = ("usage: jsk ship <resume.json> --out DIR [--ats-max] "
              "[--template N] [--pages N] [--json]")

SHIP_VALUE_FLAGS = ("--out", "--template", "--pages")


def not_rendered(why):
    """The render gate's entry when ship stopped before there was anything to read.

    render_section() would look in the output directory, and a PDF left there by an
    earlier run would be named as the thing to read - a document this run never made.
    """
    return {"gate": "render gate", "command": None, "status": "UNVERIFIED",
            "exit": None,
            "output": f"UNVERIFIED - {why}, so nothing was rendered and there is no\n"
                      f"  PDF from this run for anyone to read.\n"}


def frozen_refusal(*dirs):
    """Lines refusing a render into, or from, a frozen application - or None."""
    for d in dirs:
        path = os.path.join(d, APPLICATION_TTL)
        if os.path.isfile(path):
            return [f"frozen: {path} - re-rendering would overwrite what was sent",
                    "fix:  copy the application to a new dated directory to reuse it"]
    return None


def cmd_ship(args):
    """Record gate, render, mechanical gates - one process, stopping at a failure.

    Every step is an existing function: the record gate is what `jsk validate`
    runs, the render is render_resume.py's main(), and the gates are gate_results(),
    so none of their verdicts is restated here. A legacy URS record is turned away by
    the record gate itself, with `jsk migrate` as the fix, before anything renders.
    """
    if wants_help(args):
        print(SHIP_USAGE)
        return 0
    if view_refusal(args):
        print("\n".join(VIEW_GONE))
        return 2
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
    if not flags.get("--out"):
        print("--out is required")
        print("fix:  --out names the directory to render into - the application's own")
        return 2
    # Before anything renders (Review Focus 5): the render writes over the PDF and .txt
    # that application.ttl says were sent, and the archive would then describe files it
    # no longer holds.
    refusal = frozen_refusal(flags["--out"], os.path.dirname(os.path.abspath(record)))
    if refusal:
        print("\n".join(refusal))
        return 1
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
    out_dir = flags["--out"]

    results = []
    code, output = call_gate("record.py", [record])
    results.append(gate_result("record gate", f"record.py {record}", code, output))
    if code != 0:
        # A number the career replaced renders as a sendable PDF with that number in it.
        results.append(not_rendered("the record gate did not pass"))
    else:
        render_args = [record, "--out", out_dir, "--pdf"]
        render_args += ["--ats-max"] if flags.get("--ats-max") else []
        render_args += ["--template", template] if template else []
        code, output = call_gate("render_resume.py", render_args)
        results.append(gate_result("render", " ".join(["render_resume.py"] + render_args),
                                   code, output))
        if code != 0:
            results.append(not_rendered("the render did not finish"))
        else:
            # The render names each file it wrote; those, and nothing an earlier
            # ship left in the same directory, are what this ship gates.
            wrote = [os.path.join(out_dir, rel)
                     for rel in re.findall(r"^  wrote  (.+?)\s*$", output, re.M)]
            results.extend(gate_results(out_dir, record, pages, record_gate=False,
                                        only=wrote))

    # 0 or 1 only. A step's own exit 2 - an ERROR from a gate that raised, or a render
    # refusing a file - is a failure of this ship, not a mistake in how it was called.
    worst = 1 if worst_exit(results) else 0
    if flags.get("--json"):
        print(json.dumps({"record": record, "out_dir": out_dir,
                          "exit": worst, "steps": results}, indent=2))
        return worst
    print_results(f"ship: {record} -> {out_dir}", results)
    return worst


# --- jsk freeze -----------------------------------------------------------------
#
# mode-ship.md's "Freeze the application", which was three edits and a rename made by
# hand: the directory renamed to the day it was sent, the archive written, and
# nothing in the directory edited again. The command does the first two and refuses
# whenever the third is already true or the documents would not survive their gates.
#
# It writes application.ttl - what was sent, and the bullets and metric versions it
# carried - and later events go in with `jsk event`. A workspace whose career is still
# user-knowledgebase.md is refused and pointed at `jsk migrate`: only migrate reads the
# Markdown, and an application.md written here would be an archive in a format nothing
# else reads, of a career no gate could check it against.
FREEZE_USAGE = ("usage: jsk freeze <app-dir> --submitted YYYY-MM-DD|false "
                "--channel TEXT [--doc FILE ...]")

APPLICATION = "application.md"
APPLICATION_TTL = "application.ttl"
POSTING_TTL = "posting.ttl"
KNOWLEDGE_BASE = "user-knowledgebase.md"
GRAPH_KB = os.path.join("career", "kb.ttl")
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


def freeze_refusal(*lines):
    print("REFUSED - " + lines[0])
    for line in lines[1:]:
        print("  " + line)
    return 1


def cmd_freeze(args):
    """Archive one application directory: rename it to its day and write application.ttl.

    Never touches the career: not kb.ttl or log.ttl. `jsk event` records what happens
    to the application afterwards; this command only freezes what was sent.
    """
    if wants_help(args):
        print(FREEZE_USAGE)
        return 0
    if view_refusal(args):
        print("\n".join(VIEW_GONE))
        return 2
    parsed, problem = parse_flags(args, ("--submitted", "--channel"), (),
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
    # An applications/ that is not beside the knowledge base is one the been-here-before
    # check never looks in, so an application frozen there is invisible to every later
    # round. It happened: a session wrote them relative to its working directory.
    apps = os.path.dirname(os.path.abspath(app_dir))
    workspace = os.path.dirname(apps)
    if not os.path.isfile(os.path.join(workspace, GRAPH_KB)):
        markdown = os.path.join(workspace, KNOWLEDGE_BASE)
        if os.path.isfile(markdown):
            # Refused rather than frozen as Markdown: only `jsk migrate` reads a
            # user-knowledgebase.md, and it moves every application.md across with it.
            return freeze_refusal(
                f"the career beside {apps} is still {KNOWLEDGE_BASE}, not career/kb.ttl.",
                f"Run `jsk migrate {markdown}` first; nothing was renamed or written.")
        print(f"no career/kb.ttl beside {apps}")
        print("fix:  move the directory into the applications/ folder next to career/")
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

    # An application.md is one frozen before the career moved to kb.ttl - `jsk migrate`
    # writes an application.ttl beside each - and is as frozen as an application.ttl.
    for name, later in ((APPLICATION_TTL, "Later events are `jsk event`, one each."),
                        (APPLICATION, "It was frozen as Markdown before the career moved "
                                      "to career/kb.ttl.")):
        target = os.path.join(app_dir, name)
        if os.path.exists(target):
            return freeze_refusal(
                f"{target} already exists. A frozen application is never re-frozen.", later)

    # company and title live in posting.ttl; timeline.freeze() reads and checks it.
    if not os.path.isfile(os.path.join(app_dir, POSTING_TTL)):
        return freeze_refusal(f"no {POSTING_TTL} in {app_dir}",
                              "application.ttl names the posting it answered; the "
                              "analyst writes posting.ttl beside posting.md.")

    record = os.path.join(app_dir, DEFAULT_RECORD)
    try:
        with open(record, "rb") as fh:
            record_bytes = fh.read()
    except OSError as exc:
        return freeze_refusal(f"cannot read the record {record}: {exc}",
                              "application.ttl records its hash, and its gate has to pass.")
    # What was sent is what the builder renders from the short file now, over the career
    # as it stands - the same build the PDF beside it came from. A legacy URS record is
    # refused here with `jsk migrate` as the fix (short.read).
    from .resume import build, short                 # noqa: PLC0415 - only when asked
    try:
        plan, _ = build.from_path(record)
    except short.ShortError as exc:
        return freeze_refusal(str(exc), f"fix: {exc.fix}",
                              "nothing was renamed or written.")

    if flags.get("--doc"):
        documents = []
        # `named`, not `doc`: that name once held the record, which timeline.freeze()
        # read below, and a graph freeze given --doc raised AttributeError on the last
        # --doc path instead of writing application.ttl.
        for named in flags["--doc"]:
            name = os.path.basename(named)
            if not os.path.isfile(os.path.join(app_dir, name)):
                return freeze_refusal(f"--doc {named}: no {name} in {app_dir}",
                                      "a frozen application lists what is in it.")
            documents.append(name)
    else:
        documents = sorted(name for name in os.listdir(app_dir)
                           if name.lower().endswith((".pdf", ".txt"))
                           and os.path.isfile(os.path.join(app_dir, name)))
        pdfs = [d for d in documents if d.lower().endswith(".pdf")]
        if len(pdfs) > 1:
            # Two renders in one directory, and only the person knows which was sent.
            # Listing both would archive a document nobody submitted as though it was.
            return freeze_refusal(f"{len(pdfs)} PDFs in {app_dir}: {', '.join(pdfs)}",
                                  "name the documents that were sent with --doc.")
    if not documents:
        return freeze_refusal(f"no .pdf or .txt in {app_dir}",
                              "there is nothing here that could have been sent.")
    # What was sent, and the .tex each was compiled from - the prose gate reads that.
    sent = [os.path.join(app_dir, d) for d in documents]
    sent += [os.path.splitext(p)[0] + ".tex" for p in sent
             if os.path.isfile(os.path.splitext(p)[0] + ".tex")]

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
    results = gate_results(app_dir, record, only=sent)
    print_results(f"gates: {app_dir}", results)
    if worst_exit(results):
        return freeze_refusal(
            "a gate above did not pass. A failing document is never frozen -",
            "an archive of something that was not sendable reads, later, as though it was.")

    from .graph import timeline                       # noqa: PLC0415 - only when asked
    text, problems = timeline.freeze(workspace, app_dir, plan, record_bytes, submitted,
                                     channel, documents)
    if problems:
        return freeze_refusal(*problems, "nothing was renamed or written.")

    if final != app_dir:
        try:
            os.rename(app_dir, final)
        except OSError as exc:
            return freeze_refusal(f"cannot rename {app_dir} to {final}: {exc}",
                                  "nothing was written.")
    written = os.path.join(final, APPLICATION_TTL)
    with open(written, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"froze  {written}")
    if final != app_dir:
        print(f"moved  {app_dir} -> {final}")
    print(final)
    print()
    print("Frozen on the mechanical gates. The render gate is a person's: freezing")
    print("assumes somebody opened the PDF and read it. Nothing in this directory is")
    print("edited again; later events are `jsk event <dir> <kind> --date ...`, and")
    print("`jsk kb query pipeline` gives each application's stage.")
    return 0


# Subcommands that went, with what replaced them. Said by name rather than as an unknown
# command: a shell history or an old mode file still holds them, and "unknown command"
# reads as a broken install. kbindex.py stays one more release because `jsk migrate`
# reads the Markdown with it; release N+1 deletes both.
RETIRED = {
    "index": "it read user-knowledgebase.md, and the career is career/kb.ttl now.\n"
             "fix:  `jsk match applications/<dir>/posting.ttl` ranks the career against a "
             "posting;\n      `jsk kb view` reads it; `jsk migrate user-knowledgebase.md` "
             "moves an old file across, once",
}


HANDLERS = {
    "doctor": cmd_doctor,
    "validate": cmd_validate,
    "check": cmd_check,
    "gates": cmd_gates,
    "ship": cmd_ship,
    "freeze": cmd_freeze,
}


def usage():
    print(__doc__.strip().split("\n\n", 1)[1].split(HELP_ENDS_BEFORE, 1)[0])
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
        return run_in_process(SIMPLE[sub], rest)
    if sub in RETIRED:
        print(f"jsk {sub} was retired: {RETIRED[sub]}")
        return 2
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
