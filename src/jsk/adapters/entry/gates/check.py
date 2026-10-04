"""The three things the resume_check tool does, by target, and how their steps print.

cmd_validate is the record gate over one target's selection, cmd_check the two document gates
over one render (or one gate, with --only), and cmd_gates all four over a render's
directory (application/gates/run_gates.py) with the render gate said out loud after them.
Each gate runs in this interpreter through its own adapter, contained the way
cli.call_gate contains a module: a gate that raised is reported as its own failure and
the others still run.
"""
import contextlib
import importlib
import io
import json
import os

from ....application.gates.run_gates import DEFAULT_RECORD as DEFAULT_RECORD
from ....application.gates.run_gates import DOC_GATES as DOC_GATES
from ....application.gates.run_gates import RENDERED as RENDERED
from ....application.gates.run_gates import rendered_documents as rendered_documents
from ..cliutil import parse_flags, utf8_stdout, wants_help

# The gates the resume_check tool runs, in order. Both always run: a document that fails the parse
# gate can still have prose findings worth seeing in the same pass.
#
# They no longer read the same file. check_ats.py reads what is actually sent - the
# PDF - while check_prose.py reads the .tex it was compiled from, where a bullet is
# an \item rather than a glyph that a text extractor may or may not have kept. Pass
# either one and the other is found beside it.
CHECK_GATES = [
    # key for --only, script, label, forwards --strict, extensions it reads
    ("parse", "check_ats.py", "parse gate", True, (".pdf",)),
    ("prose", "check_prose.py", "prose gate", False, (".tex",)),
]

# A file both document gates read when it is named, and never look for beside another: no
# render writes a .txt any more (its text is emitted in memory), but a cover letter or a
# pasted resume is one, and a person may still check it by hand.
BY_HAND = (".txt",)

# The gate `--only` reaches that the default pass never runs, its arguments passed through
# unchanged. The layout gate reads the render, but only the PDF - a default pass over a .txt
# would report it SKIPPED. The resume_check and resume_ship tools run it; here it is asked for by name.
CHECK_ALONE = {"layout": "layout.py"}

CHECK_USAGE = ("usage: the resume_check tool (jsk mcp): resume_check(<resume.pdf>, strict=False, "
               "only=\"parse\"|\"prose\"|\"layout\")")

VALIDATE_USAGE = ("usage: the resume_check tool (jsk mcp): resume_check(<stem>|resumes/<name>, "
                  "strict=False)")

GATES_USAGE = ("usage: the resume_check tool (jsk mcp): resume_check(<out-dir>, "
               "record=<stem>|resumes/<name>, pages=N)")

GATES_VALUE_FLAGS = ("--record", "--pages", "--max-findings")

# Each gate's script, as the headings and the tables above name it, and the adapter
# module under this package that runs it.
ADAPTERS = {"record.py": "record", "check_ats.py": "ats", "check_prose.py": "prose",
            "layout.py": "layout", "terms.py": "terms", "letter.py": "letter"}

# The tool call that runs each gate alone, for the hint after one that raised. Tools, as in
# dispatch.COMMANDS, since the commands went on 2026-10-04 and a hint naming one would send the
# reader to an exit 2.
COMMANDS = {"record.py": "resume_check(<stem>)",
            "check_ats.py": "resume_check(<pdf>, only=\"parse\")",
            "check_prose.py": "resume_check(<tex>, only=\"prose\")",
            "layout.py": "resume_check(<pdf>, only=\"layout\")",
            "terms.py": "resume_check(<out-dir>, record=<stem>)",
            "letter.py": "letter_check(<stem>)"}


def gate_target(path, accepts):
    """The file a gate reads, given whichever sibling the caller named.

    Args:
        path: the file named.
        accepts: the extensions the gate reads, in order of preference.

    Returns:
        The path itself when the gate reads it or it is a file named by hand (BY_HAND), else
        the first sibling that exists, else None.
    """
    stem, ext = os.path.splitext(path)
    if ext.lower() in accepts + BY_HAND and os.path.exists(path):
        return path
    for want in accepts:
        if os.path.exists(stem + want):
            return stem + want
    return None


def contained(script, args, capture=True):
    """One gate run in this interpreter, with cli.call_gate's contract.

    The output is captured so that --json can carry it whole; it is printed back
    unchanged either way. With `capture=False` the gate prints straight through, and
    what comes back is only what this function itself had to say.

    Args:
        script: the gate's script name, a key of ADAPTERS.
        args: its arguments alone.
        capture: capture what it prints rather than let it through.

    Returns:
        (exit code, output, outcome): the outcome is what the gate returned - a
        GateResult, the GateStopped it stopped with, or None.
    """
    name = f"{__package__}.{ADAPTERS[script]}"
    try:
        module = importlib.import_module(name)
    except ImportError as exc:
        return 2, (f"FAIL  cannot load {script}: {exc}\n"
                   f"fix:  the install is incomplete - expected the module {name}\n"), None
    buf = io.StringIO()
    sink = contextlib.redirect_stdout(buf) if capture else contextlib.nullcontext()
    try:
        with sink:
            code, outcome = module.gate(list(args))
    except SystemExit as exc:
        # A bare sys.exit() is a clean exit in a child interpreter and has to be one here.
        code = 0 if exc.code is None else (exc.code if isinstance(exc.code, int) else 2)
        return code, buf.getvalue(), None
    except Exception as exc:                      # noqa: BLE001 - deliberately broad
        # In-process gates share this interpreter, so an unhandled error inside one
        # would print a traceback where a verdict belongs and take the other gates
        # down with it. Report it as its own failure and keep going.
        return 2, buf.getvalue() + (
            f"FAIL  {script} raised {type(exc).__name__}: {exc}\n"
            f"fix:  run it directly to see the whole story - "
            f"{COMMANDS[script]} {' '.join(str(a) for a in args)}\n"), None
    return code, buf.getvalue(), outcome


def through(script, args):
    """Run one gate with its output printed as it goes. Exit code unchanged.

    Args:
        script: the gate's script name.
        args: its arguments alone.

    Returns:
        The gate's exit code. Prints its output.
    """
    # A path or a title under a non-ASCII name reaches a cp1252 console as a
    # UnicodeEncodeError from inside the print, which loses the whole verdict.
    utf8_stdout()
    code, output, _ = contained(script, args, capture=False)
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return code


def cmd_validate(args):
    """The resume_check tool's record gate, over one target's selection.

    Args:
        args: the arguments after the command.

    Returns:
        The exit code. Prints the verdict.
    """
    from ....application.guards import record_refusal, view_refusal

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
    return through("record.py", args)


def only_gate(args):
    """(the gate --only names or None, the arguments without it, exit code or None).

    Args:
        args: the resume_check tool's arguments; not changed.

    Returns:
        The exit code is 2, after printing why, when --only has no value or names no gate.
    """
    args = list(args)
    if "--only" not in args:
        return None, args, None
    at = args.index("--only")
    if at + 1 >= len(args):
        print("--only needs a value")
        print("fix:  --only parse   or   --only prose")
        return None, args, 2
    only = args[at + 1]
    keys = [gate[0] for gate in CHECK_GATES] + list(CHECK_ALONE)
    if only not in keys:
        print(f"unknown gate: {only}")
        print(f"fix:  one of {', '.join(keys)} - or leave --only off to run both")
        return None, args, 2
    del args[at:at + 2]
    return only, args, None


def cmd_check(args):
    """Both document gates, in one pass, on one file - or one of them, with --only.

    `--only` is here because mode-resume.md names a single gate when one file has been
    repaired and only that gate needs re-running: "the right thing for re-checking one
    file after one repair". That was the one call `jsk` could not express, so those
    lines reached past it to check_ats.py and check_prose.py directly.

    Args:
        args: the arguments after the command.

    Returns:
        The worst exit code. Prints each gate under its heading, then what did not run.
    """
    from ...compose.selection import selection_ref

    only, args, code = only_gate(args)
    if code is not None:
        return code
    if only in CHECK_ALONE:
        return through(CHECK_ALONE[only], args)
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
        beside = selection_ref(os.path.dirname(os.path.abspath(path)))
        if script == "check_ats.py" and path.lower().endswith(".pdf") and beside:
            # The selection a target's directory holds in the store: its plan's plain text
            # is the order the PDF must extract in. It was a resume.json beside the render
            # until 6.0 read none.
            gate_args += ["--record", beside]
        worst = max(worst, through(script, gate_args))
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
            print(f"  {'resume_check(' + os.path.basename(target) + ')':<30} the other document gate")
        print("  resume_check(<stem>)            before rendering")
        print("  open the PDF and read it       nobody else can do this one")
    return worst


def parse_gates(args):
    """The resume_check tool's arguments, as cliutil.parse_flags reads them."""
    return parse_flags(args, GATES_VALUE_FLAGS)


def parse_pages(pages):
    """(budget or None, None) or (None, the lines saying what was wrong).

    Args:
        pages: --pages's value, or None.

    Returns:
        The budget as an int when it is a whole number of at least one page.
    """
    if pages is None:
        return None, None
    if not str(pages).isdigit() or int(pages) < 1:
        return None, [f"--pages needs a whole number of pages, got {pages!r}",
                      "fix:  --pages 2   - the budget the resume asked for"]
    return int(pages), None


def gates_call(args):
    """(out_dir, record, pages, limit, json) for the resume_check tool, or an exit code.

    Args:
        args: the arguments after the command.

    Returns:
        The exit code (0 for --help, else 2) after printing why the call is wrong, or the
        call's parts.
    """
    from ....application.guards import VIEW_GONE, view_refusal

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
        print("fix:  pass the directory the resume_render tool wrote to (its out argument)")
        return 2

    # A record that was named and is wrong is a call error; one that was neither
    # named nor sitting where the skill writes it is a missing input, which is
    # SKIPPED and a failure further down. The two are different mistakes and
    # reporting them the same way hides one of them.
    from ....application.guards import is_resume_json, resume_json_refusal
    from ....application.render.selection import parse_ref
    from ...compose.selection import ref_for, selection_ref

    record = flags.get("--record")
    if record is not None:
        if is_resume_json(record):
            print("\n".join(resume_json_refusal(
                "resume_check(<out-dir>, record=<resume.json>)",
                "resume_check(<out-dir>, record=<stem>) (or resumes/<name>)")))
            return 2
        record = ref_for(record, dirs=True) or record
        if not parse_ref(record):
            print(f"not a target: {record}")
            print("fix:  --record takes the target the documents rendered from: <stem> "
                  "or resumes/<name>")
            return 2
    else:
        # The record is the selection the directory's target holds in the store (Ruling 6
        # of the graph-native plan); a resume.json beside the render was read until 6.0.
        record = selection_ref(out_dir)

    pages, problem = parse_pages(flags.get("--pages"))
    if problem:
        print("\n".join(problem))
        return 2
    limit = flags.get("--max-findings")
    if limit is not None and not str(limit).isdigit():
        print(f"--max-findings needs a whole number, got {limit!r}")
        print("fix:  --max-findings 50   - or 0 to print every finding")
        return 2
    return out_dir, record, pages, limit, flags.get("--json")


def cmd_gates(args):
    """The record, parse, prose and layout gates over one rendered resume, in one process.

    cmd_check covers two of them; this covers four, and every render the directory
    holds. What it does not cover is the render gate - see
    run_gates.render_section() for why that is stated rather than silently omitted.

    Args:
        args: the arguments after the command.

    Returns:
        The worst exit code. Prints each gate's output and the summary, or --json.
    """
    call = gates_call(args)
    if isinstance(call, int):
        return call
    out_dir, record, pages, limit, as_json = call
    results = gate_results(out_dir, record, pages, limit)
    worst = worst_exit(results)

    if as_json:
        print(json.dumps({"out_dir": out_dir, "record": record,
                          "exit": worst, "gates": results}, indent=2))
        return worst

    print_results(f"gates: {out_dir}", results)
    return worst



class Shown(dict):
    """A step as --json prints it - gate, command, status, exit, output - with the counts,
    page measurements, withheld lines and fit the summary restates kept beside it rather
    than in it."""

    def __init__(self, step):
        super().__init__(gate=step.gate, command=step.command, status=step.status,
                         exit=step.exit, output=step.output)
        self.counts = step.counts
        self.pages = step.pages
        self.withheld = step.withheld
        self.fitted = step.fitted


def strict_for(path):
    """Whether a rendered document is held to the ATS-maximal rules
    (application.gates.run_gates.strict_for, over the PDF's metadata and its .tex).

    Args:
        path: the document.

    Returns:
        True for the ATS-maximal variant. Reads the PDF, and maybe the .tex beside it.
    """
    from ....application.gates.run_gates import strict_for as held
    from ....infra.pdf import VARIANT_KEYWORD, variant_of
    from ....infra.files import Unreadable, read_text

    def pdf_variant(pdf):
        try:
            return variant_of(pdf)
        except ImportError:
            return None

    def tex_variant(tex):
        # No .tex, or one that is not UTF-8, is no keyword: the name decides.
        try:
            found = VARIANT_KEYWORD.search(read_text(tex))
        except Unreadable:
            return None
        return found.group(1) if found else None

    return held(path, pdf_variant=pdf_variant, tex_variant=tex_variant)


def measure(pdf):
    """(pages, last page's fill) of a PDF, as the resume_render tool measures one
    (compose.render).

    Raises:
        ImportError: the render's bindings will not load - the render gate says so.
    """
    from ...compose import render as bound

    return bound.page_count(pdf), bound.last_page_fill(pdf)


def gate_results(out_dir, record, pages=None, limit=None, record_gate=True, only=None):
    """Every resume_check tool step over one directory, the render gate last, as Shown dicts.

    the resume_ship tool and the app_freeze tool call this too (application.gates.run_gates.run_gates says
    why), and print and serialise what it returns beside steps of their own.

    Returns:
        The steps, each a Shown. Runs every gate, in this interpreter.
    """
    from ....application.gates.run_gates import run_gates

    return [Shown(s) for s in run_gates(out_dir, record, pages, limit, record_gate, only,
                                        run=contained, strict=strict_for, measure=measure)]


def gate_result(gate, command, code, output):
    """The step for a gate whose output was captured by cli.call_gate.

    Args:
        gate: its label.
        command: how it was called.
        code: its exit code.
        output: what it printed.

    Returns:
        The step's dict: PASS, FAIL or ERROR by exit code, SKIPPED for a gate whose output
        says it did not run (the layout gate without pymupdf).
    """
    status = {0: "PASS", 1: "FAIL"}.get(code, "ERROR")
    if code == 1 and output.startswith("SKIPPED"):
        # The layout gate without pymupdf: it says so itself, and a failure either way.
        status = "SKIPPED"
    return {"gate": gate, "command": command, "status": status, "exit": code,
            "output": output}


def worst_exit(results):
    """The highest exit code among the steps that have one; 0 when none has."""
    return max([r["exit"] for r in results if r["exit"] is not None] or [0])


def print_results(title, results):
    """Each result under its `--- ` heading, its output verbatim, then the summary.

    Args:
        title: the first line.
        results: the steps, each a Shown.

    Returns:
        None. Writes to stdout.
    """
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
    print("\n".join(summary(results)))


def summary(results):
    """The verdicts again, one line a step, printed after all of them.

    The ElevenLabs ship (2026-09-25) ran to about 6KB - nineteen prose WARNs among it -
    and was read through `tail -60`, which cut the record gate off the top;
    the whole ship was run a second time into a file to grep for them. This block
    restates no verdict: each count is the gate's own.

    Args:
        results: the steps, as print_results takes them.

    Returns:
        The lines, "=== summary" first and the verdict last.
    """
    width = max(len(r["gate"]) for r in results)
    lines = ["=== summary"]
    rendered = any(r["gate"] == "render" for r in results)
    for result in results:
        counts, pages = result.counts, result.pages
        withheld, fitted = result.withheld, result.fitted
        parts = [result["status"]]
        if counts:
            fails, warns = counts
            parts.append((f"FAIL {fails}   " if fails is not None else "") + f"WARN {warns}")
        command = result["command"] or ""
        if result["gate"] in ("parse gate", "prose gate", "layout gate") and command:
            parts.append(command.split()[1] if len(command.split()) > 1 else command)
        # The render's measurement, or - under the resume_check tool, which renders nothing -
        # the render gate's under --pages. Never both: ship's --pages is a second
        # budget for the same count.
        if result["gate"] == "render" or (result["gate"] == "render gate"
                                          and not rendered):
            parts.extend(f"{name} {count} of {budget} pages" for name, count, budget in pages)
        if result["gate"] == "render":
            # One line per line held back, however many variants carried it - each
            # named, because the Arrow run (2026-09-29) shipped a second time only to
            # grep for which bullet the count was counting.
            parts.append(f"withheld {len(withheld)} below the floor"
                         + (f": {', '.join(withheld)}" if withheld else ""))
        if result["gate"] == "fit" and fitted:
            parts.append(fitted)
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
