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
    jsk new PATH --name NAME    scaffold career/store/ - the career and its log at r1 -
                                and applications/
    jsk posting fetch URL APP   an Ashby, Greenhouse or Lever posting, as APP/posting.md
      ... extract APP           its lines, numbered, with the concepts each names
      ... build APP             decisions.txt to APP's posting, every quote the advert's own
    jsk match APP               a posting against the graph record, through the vocabulary
    jsk tailor prepare APP      the match and everything an assessment reads, in one digest
    jsk kb VERB [...]           the graph record: apply a changeset, confirm, show, check
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

The career is the graph record, in career/store/: changed through `jsk kb apply`, read with
`jsk kb show` and `jsk kb view`, validated on every load. `jsk kb export` writes an
application's short resume.json - the bullets chosen, as ids - out of it, every render
builds from the career and that file, and `jsk validate` checks the file and the bullets it
selects before anything renders - the last point at which a mistake is still cheap.

pyoxigraph for the graph record, and pymupdf to read a PDF.
"""

import contextlib
import glob
import importlib
import io
import json
import os
import re
import sys

from . import __version__
from .application.guards import frozen_refusal, unloaded_refusal
from .cliutil import parse_flags, refused, utf8_stdout, wants_help

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
    "tailor": "prepare.py",
    "kb": "kbcli.py",
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
#   render/ rendering, the preview and the page fitter, over the record->document
#           pipeline they drive. One edge leaves it, and it is lazy.
#   gates/  the record, parse and prose gates. The record gate (record.py) reads the
#           graph, lazily; inside, check_prose borrows numbers.py's numeral detector.
SUBPACKAGE = {
    "render_resume.py": "render",
    "preview_templates.py": "render",
    "fit_pages.py": "render",
    "check_ats.py": "gates",
    "check_prose.py": "gates",
    "record.py": "gates",
    "letter.py": "gates",
    "layout.py": "gates",
    "match.py": "graph",
    "prepare.py": "graph",
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
    utf8_stdout()
    code, output = call_gate(script, args, capture=False)
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return code


def cmd_doctor(args):
    """Preflight, verifying end to end unless told otherwise - then the record's store."""
    if "--quick" in args:
        args = [a for a in args if a != "--quick"]
    elif "--verify" not in args:
        args = list(args) + ["--verify"]
    code = run_in_process("preflight.py", args)
    if wants_help(args) or "--json" in args:
        return code
    kb = args[args.index("--kb") + 1] if "--kb" in args[:-1] else None
    lines, broken = store_report(kb)
    print("\nThe record:")
    print("\n".join(lines))
    return max(code, 1 if broken else 0)


def store_report(start=None):
    """(lines, broken) saying where the record's store stands: there, readable, its
    revision, and whether .jsk/backup.trig - the dump every write refreshes, and what
    `jsk kb load` restores from - is there, at which revision. `start` is a workspace, a
    path inside one, or its career/store/; by default the current directory."""
    from .infra.oxigraph import db
    from .infra.oxigraph import record as R
    from .infra.files import find_root

    here = start or os.getcwd()
    if os.path.isfile(here):
        here = os.path.dirname(os.path.abspath(here))
    root = find_root(here)
    if root is None:
        return [f"  gap   no workspace at or above {here}",
                "           `jsk new PATH --name NAME` starts one"], False
    refusal = unloaded_refusal(root)
    if refusal:
        return [f"  FAIL  {refusal[0]}", f"           {refusal[1]}"], True
    try:
        graphs = db.read(root)
    except db.StoreError as e:
        return [f"  FAIL  {db.path(root)}: {e}", f"           {e.fix}"], True
    revision = R.header_revision(graphs.get(R.KB, []))
    lines = [f"  ok    store    {db.path(root)}",
             f"           readable, at r{revision}" if revision is not None
             else "           readable, and it holds no career revision"]
    backup = os.path.join(root, R.BACKUP)
    if not os.path.isfile(backup):
        lines += ["  gap   backup   no .jsk/backup.trig yet",
                  "           the next write refreshes it; `jsk kb dump` writes one now"]
        return lines, False
    try:
        from .infra.files import read_text
        at = R.header_revision(db.parse_dump(read_text(backup, R.BACKUP)).get(R.KB, []))
    except Exception as e:                   # noqa: BLE001 - reported, never a crash
        lines += [f"  gap   backup   {backup} does not read back: {e}"]
        return lines, False
    lines.append(f"  ok    backup   {backup}")
    lines.append(f"           at r{at}" + ("" if at == revision else
                                          f" - one write behind the store's r{revision}; the "
                                          "next write refreshes it"))
    return lines, False


# Commands that make a record, report on one, or dispatch their own verbs - `jsk kb load`
# is the import itself, so kbcli refuses for the other kb verbs.
NO_RECORD = {"new", "doctor", "kb"}


def workspace_refusal(sub, rest):
    """unloaded_refusal for the workspace a command runs in - the one around the current
    directory, or around any path it was given - or None."""
    from .infra.files import find_root

    if sub in NO_RECORD or wants_help(rest):
        return None
    starts = [os.getcwd()] + [a for a in rest if not a.startswith("-") and os.path.exists(a)]
    for start in starts:
        refusal = unloaded_refusal(find_root(start))
        if refusal:
            return refusal
    return None


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
                "fix:  the career is in career/store/, which `jsk kb check` validates. This",
                "      gate reads an application's choice from the career - pass resume.json"]
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
        from .infra.files import Unreadable, read_text  # noqa: PLC0415
        try:
            variant = variant_of(path)
        except ImportError:
            variant = None
        if variant is None:
            # No .tex, or one that is not UTF-8, is no keyword: the name decides.
            try:
                found = VARIANT_KEYWORD.search(read_text(os.path.splitext(path)[0] + ".tex"))
                variant = found.group(1) if found else None
            except Unreadable:
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
                from .render import render_resume        # noqa: PLC0415 - only when asked
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
    utf8_stdout()
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
# The fit step's outcome, as ship_fit() and fit_pages.py print it.
FITTED = re.compile(r"^\s*(fit: .+?|over by ~\d+ lines? at the floors)\s*$", re.M)


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
            # One line per line held back, however many variants carried it - each
            # named, because the Arrow run (2026-09-29) shipped a second time only to
            # grep for which bullet the count was counting.
            withheld = list(dict.fromkeys(what.split()[-1]
                                          for what in WITHHELD.findall(output)))
            parts.append(f"withheld {len(withheld)} below the floor"
                         + (f": {', '.join(withheld)}" if withheld else ""))
        if result["gate"] == "fit":
            parts.extend(FITTED.findall(output)[-1:])
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
              "[--template N] [--pages N] [--no-fit] [--json]")

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


def ship_fit(out_dir, wrote, render_output, pages=None):
    """The fit step: each PDF the render put over its budget, fitted. [] when none is.

    The Arrow run (2026-09-29) spent 3 minutes and 13 turns here by hand: `jsk fit`
    three times, three confirmed bullets cut, then `mv`, `tectonic` and `jsk gates`.
    The first fit had already reached 2 pages at 0.6in margins, inside the 0.5in floor.

    fit_pages.py is deterministic and writes one file, `<stem>-fitted.tex`, and only
    when the levers reached the budget inside the floors. That file is moved over the
    render's .tex and compiled by the function the render compiled with, so the PDF
    the gates then read is built the way the render built it. At the floors, nothing is
    written and the unfitted render is kept: cutting evidence is the author's call. The
    page count stays reported and not failed, as the render reports it - so the step's
    exit is None then, and the verdict is what it was before ship fitted anything.

    The budget is ship's --pages when given, else the render's own, which is
    `ats_pages` under --ats-max: the one the render's page line was measured against.
    """
    from .render import render_resume              # noqa: PLC0415 - only when asked

    measured = {name: (int(count), int(budget))
                for name, count, budget in PAGES.findall(render_output)}
    results = []
    for pdf in (p for p in wrote if p.lower().endswith(".pdf")):
        name = os.path.basename(pdf)
        tex = os.path.splitext(pdf)[0] + ".tex"
        if name not in measured or not os.path.isfile(tex):
            continue                              # unmeasured: nothing to fit against
        count, budget = measured[name][0], pages or measured[name][1]
        if count <= budget:
            continue
        fitted = os.path.splitext(tex)[0] + "-fitted.tex"
        with contextlib.suppress(FileNotFoundError):
            os.remove(fitted)                    # an earlier fit's is not this one's
        fit_args = [tex, "--target-pages", str(budget)]
        command = " ".join(["fit_pages.py", os.path.basename(tex)] + fit_args[1:])
        code, output = call_gate("fit_pages.py", fit_args)
        output += "" if output.endswith("\n") else "\n"
        if code == 1:
            results.append({"gate": "fit", "command": command, "status": "OVER BUDGET",
                            "exit": None,
                            "output": output + "\nkept the unfitted render; nothing was "
                                               "cut - that is the author's call, with a "
                                               "reason\n"})
            continue
        if code != 0 or not os.path.isfile(fitted):
            # Exit 0 with nothing written is a fitter that measured the render inside the
            # budget the render measured it over. Two counts of one document disagreeing
            # is a broken toolchain, and neither count can be trusted.
            results.append(gate_result("fit", command, code if code else 2, output + (
                "" if code else f"FAIL  fit_pages.py found {os.path.basename(tex)} inside "
                                f"{budget} pages; the render counted {count}\n")))
            continue
        levers = re.findall(r"^  levers: (.+?)\s*$", output, re.M)
        os.replace(fitted, tex)
        built, note = render_resume.compile_pdf(tex, out_dir)
        if not built:
            results.append(gate_result("fit", command, 2, output + (
                f"\nRENDER FAILED - {os.path.basename(tex)} was fitted and did not "
                f"recompile:\n  {note}\n")))
            continue
        now = render_resume.page_count(built)
        results.append(gate_result("fit", command, 0, output + (
            f"\nmoved {os.path.basename(fitted)} over {os.path.basename(tex)} and "
            f"recompiled it ({note}); the gates below read the fitted render.\n"
            f"fit: {levers[-1] if levers else 'levers applied'}, "
            f"{now if now is not None else 'unmeasured'} "
            f"page{'' if now == 1 else 's'}\n")))
    return results


def cmd_ship(args):
    """Record gate, render, fit, mechanical gates - one process, stopping at a failure.

    Every step is an existing function: the record gate is what `jsk validate`
    runs, the render is render_resume.py's main(), the fit is fit_pages.py's main()
    (ship_fit), and the gates are gate_results(), so none of their verdicts is
    restated here. A legacy URS record is turned away by the record gate itself, with
    `jsk kb export` as the fix, before anything renders.
    """
    if wants_help(args):
        print(SHIP_USAGE)
        return 0
    if view_refusal(args):
        print("\n".join(VIEW_GONE))
        return 2
    parsed, problem = parse_flags(args, SHIP_VALUE_FLAGS, ("--json", "--ats-max", "--no-fit"))
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
    # that the application's record says were sent, and the archive would then describe files it
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
        from .domain.render import themes                     # noqa: PLC0415 - only when asked
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
            if not flags.get("--no-fit"):
                # Before the gates, so that what they read is what is sent.
                results.extend(ship_fit(out_dir, wrote, output, pages))
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


def cmd_freeze(args):
    """`jsk freeze` (adapters.cli.freeze.main).

    Args:
        args: the arguments after `freeze`.

    Returns:
        The exit code.
    """
    from .adapters.cli.freeze import main as freeze   # noqa: PLC0415 - only when asked

    return freeze(args)


# Subcommands that went, with what replaced them. Said by name rather than as an unknown
# command: a shell history or an old mode file still holds them, and "unknown command"
# reads as a broken install.
RETIRED = {
    "index": "it read user-knowledgebase.md, and the career is career/store/ now.\n"
             "fix:  `jsk match applications/<dir>` ranks the career against a "
             "posting;\n      `jsk kb view` reads it",
    "migrate": "it moved a user-knowledgebase.md into the career, and jsk no longer reads "
               "the Markdown format.\n"
               "fix:  `jsk new PATH --name NAME` starts a career/store/; `jsk kb export` "
               "writes an application's short resume.json",
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
    refusal = (sub in HANDLERS or sub in SIMPLE) and workspace_refusal(sub, rest)
    if refusal:
        return refused(refusal)
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
