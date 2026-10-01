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
import datetime
import importlib
import io
import json
import os
import re
import sys

from . import __version__
from .adapters.cli.gates.check import CHECK_GATES as CHECK_GATES
from .adapters.cli.gates.check import DEFAULT_RECORD as DEFAULT_RECORD
from .adapters.cli.gates.check import DOC_GATES as DOC_GATES
from .adapters.cli.gates.check import PAGES as PAGES
from .adapters.cli.gates.check import cmd_check as cmd_check
from .adapters.cli.gates.check import cmd_gates as cmd_gates
from .adapters.cli.gates.check import cmd_validate as cmd_validate
from .adapters.cli.gates.check import gate_result as gate_result
from .adapters.cli.gates.check import gate_results as gate_results
from .adapters.cli.gates.check import parse_pages as parse_pages
from .adapters.cli.gates.check import print_results as print_results
from .adapters.cli.gates.check import rendered_documents as rendered_documents
from .adapters.cli.gates.check import worst_exit as worst_exit
from .application.guards import VIEW_GONE as VIEW_GONE
from .application.guards import frozen_refusal as frozen_refusal
from .application.guards import record_refusal as record_refusal
from .application.guards import unloaded_refusal as unloaded_refusal
from .application.guards import view_refusal as view_refusal
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


# --- jsk freeze -----------------------------------------------------------------
#
# mode-ship.md's "Freeze the application", which was three edits and a rename made by
# hand: the directory renamed to the day it was sent, the archive written, and
# nothing in the directory edited again. The command does the first two and refuses
# whenever the third is already true or the documents would not survive their gates.
#
# It writes the application's record - what was sent, and the bullets and metric versions
# it carried - and later events go in with `jsk event`.
FREEZE_USAGE = ("usage: jsk freeze <app-dir> --submitted YYYY-MM-DD|false "
                "--channel TEXT [--doc FILE ...]")

APPLICATION = "application.md"
WORKING_FILES = ("gaps.txt", "decisions.txt")
GRAPH_STORE = os.path.join("career", "store")
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


def freeze_refusal(*lines):
    print("REFUSED - " + lines[0])
    for line in lines[1:]:
        print("  " + line)
    return 1


def cmd_freeze(args):
    """Archive one application directory: rename it to its day and write its record.

    Never touches the career or its log. `jsk event` records what happens to the
    application afterwards; this command only freezes what was sent.
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
    if not os.path.isdir(os.path.join(workspace, GRAPH_STORE)):
        print(f"no career/store/ beside {apps}")
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

    # Frozen is what the record says: its application graph. An application.md is one
    # frozen before the career was a graph, and is as frozen as one.
    from .graph import timeline                       # noqa: PLC0415 - only when asked
    held = timeline.frozen(app_dir)
    if held:
        later = ("It was frozen as Markdown before the career was a graph."
                 if held.endswith(APPLICATION) else "Later events are `jsk event`, one each.")
        return freeze_refusal(
            f"{held} already exists. A frozen application is never re-frozen.", later)

    # company and title live in the posting; timeline.freeze() reads and checks it.
    if not timeline.has_record(app_dir, "posting"):
        return freeze_refusal(f"no posting in {app_dir}",
                              "the application's record names the posting it answered: "
                              f"`jsk posting build {app_dir}` writes it from posting.md.")

    record = os.path.join(app_dir, DEFAULT_RECORD)
    try:
        with open(record, "rb") as fh:
            record_bytes = fh.read()
    except OSError as exc:
        return freeze_refusal(f"cannot read the record {record}: {exc}",
                              "the application's record keeps its hash, and its gate "
                              "has to pass.")
    # What was sent is what the builder renders from the short file now, over the career
    # as it stands - the same build the PDF beside it came from. A legacy URS record is
    # refused here with `jsk kb export` as the fix (short.read).
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
        # --doc path instead of writing the application's record.
        for named in flags["--doc"]:
            name = os.path.basename(named)
            if not os.path.isfile(os.path.join(app_dir, name)):
                return freeze_refusal(f"--doc {named}: no {name} in {app_dir}",
                                      "a frozen application lists what is in it.")
            documents.append(name)
    else:
        # gaps.txt and decisions.txt are the tailoring run's working files, not documents
        # anyone was sent: listed, the letter gate read them as letters and failed them.
        documents = sorted(name for name in os.listdir(app_dir)
                           if name.lower().endswith((".pdf", ".txt"))
                           and name.lower() not in WORKING_FILES
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
        from .infra.files import spelled              # noqa: PLC0415 - only when asked
        # As the folder is spelled on disk, not as typed: the renamed folder keeps its case.
        base = spelled(apps, os.path.basename(os.path.abspath(app_dir)))
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
    # The gates above read `*_Resume*` renders and nothing else, while `documents` is
    # whatever was sent. A cover letter beside the resume was archived as sent with no
    # gate having opened it (Ruling 5, 2026-09-28). What they read is asked of
    # rendered_documents(), the function that chose it, so the two lists cannot drift.
    extensions = sorted({ext for _, _, exts in DOC_GATES for ext in exts} | {".pdf"})
    read = {os.path.normcase(os.path.abspath(p))
            for p in rendered_documents(app_dir, extensions, sent)}
    letters, lettered = [], set()
    for name in documents:
        path = os.path.join(app_dir, name)
        if (name.lower().endswith((".txt", ".md"))
                and os.path.normcase(os.path.abspath(path)) not in read):
            # Against the application's own resume.json: the letter's numbers are the
            # resume's claims in a looser paragraph, and are traced the same way.
            code, output = call_gate("letter.py", [path, "--record", record])
            letters.append(gate_result("letter gate",
                                       f"letter.py {name} --record {DEFAULT_RECORD}",
                                       code, output))
            read.add(os.path.normcase(os.path.abspath(path)))
            lettered.add(os.path.normcase(os.path.splitext(name)[0]))
    results[-1:-1] = letters                        # the render gate stays last
    print_results(f"gates: {app_dir}", results)
    if worst_exit(results):
        return freeze_refusal(
            "a gate above did not pass. A failing document is never frozen -",
            "an archive of something that was not sendable reads, later, as though it was.")
    # Anything still unread - a PDF cover letter, say - is refused. A PDF letter is read
    # through its .txt: the letter gate reads text only, and a .txt of the same name
    # beside it is the one extra file Ruling 5 accepts as the price of checking it.
    unread = [name for name in documents
              if os.path.normcase(os.path.abspath(os.path.join(app_dir, name))) not in read
              and not (name.lower().endswith(".pdf")
                       and os.path.normcase(os.path.splitext(name)[0]) in lettered)]
    if unread:
        return freeze_refusal(
            f"no gate read {', '.join(unread)}. A document freeze lists is one a gate has "
            f"checked -",
            "fix: send the letter's .txt beside it, or leave it out with --doc.",
            "nothing was renamed or written.")

    from .infra.oxigraph import record as R                    # noqa: PLC0415 - only when asked

    # The turn before the record is read: what freeze() validates is what it writes over.
    with R.turn(workspace):
        written = freeze_write(workspace, app_dir, final, plan, record_bytes, submitted,
                               channel, documents)
    if isinstance(written, int):
        return written
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


def freeze_write(workspace, app_dir, final, plan, record_bytes, submitted, channel,
                 documents):
    """Validate the application's record, rename the directory, write the record. Returns
    what was written, or the exit code of a refusal - each one leaving the directory and
    the record as they were."""
    from .infra.oxigraph import record as R                    # noqa: PLC0415 - only when asked
    from .graph import timeline                       # noqa: PLC0415

    from .infra.oxigraph import db                             # noqa: PLC0415

    sealed, problems = timeline.freeze(workspace, app_dir, plan, record_bytes, submitted,
                                       channel, documents)
    if problems:
        return freeze_refusal(*problems, "nothing was renamed or written.")
    if final != app_dir:
        try:
            os.rename(app_dir, final)
        except OSError as exc:
            return freeze_refusal(f"cannot rename {app_dir} to {final}: {exc}",
                                  "nothing was written.")
    try:
        return timeline.write_frozen(workspace, sealed, final)
    except R.Written as exc:
        # The graphs are in the store under the new name: the folder stays with them.
        print(f"FAIL  the application's record was written, and then: {exc}")
        print(f"      fix: {exc.fix}")
        return 1
    except (R.RecordError, db.StoreError, OSError) as exc:
        # The store refused, so the directory goes back to the name its graphs still have.
        undone = final == app_dir
        if not undone:
            with contextlib.suppress(OSError):
                os.rename(final, app_dir)
                undone = True
        return freeze_refusal(f"the record was not written: {exc}",
                              f"fix: {getattr(exc, 'fix', 'run the command again')}",
                              "nothing was written" + ("." if undone else
                                                       f", and {final} could not be renamed "
                                                       f"back to {app_dir}."))


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
