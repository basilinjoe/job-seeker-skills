"""How `jsk` runs a command in this interpreter: the module behind it found, its main() called.

Until the entry-point modules go (P6 of the onion design), the real ports are bound in them
(jsk.render.render_resume, jsk.graph.match, ...), and the tests' patches land there. So a
verb still reaches its adapter through the module that binds it, by the documented script
name that module had.
"""
import contextlib
import importlib
import io
import os

from ...application.guards import unloaded_refusal
from ...cliutil import utf8_stdout, wants_help

PACKAGE = __name__.split(".")[0]

# Which subpackage each script lives in. The tables are keyed by the documented script
# names - what every comment in the codebase and every shell history call them - so the
# file moves and the name does not.
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
    "timeline.py": "graph",
}

# The scripts that are their adapter now: the documented name kept, the module named whole,
# since the adapter is called for the noun it serves and not for the old file.
ADAPTERS = {
    "kbcli.py": "adapters.cli.kb",
}

# The command each script answers to, for the hint that says how to run one by hand.
COMMANDS = {
    "kb.py": "jsk kb new",
    "kbcli.py": "jsk kb",
    "posting.py": "jsk posting",
    "match.py": "jsk tailor match",
    "prepare.py": "jsk tailor",
    "timeline.py": "jsk app event",
    "render_resume.py": "jsk resume render",
    "preview_templates.py": "jsk resume preview",
    "fit_pages.py": "jsk resume fit",
    "preflight.py": "jsk doctor",
}


def module_for(script):
    """The module a documented script name is.

    Args:
        script: e.g. `check_ats.py`.

    Returns:
        Its dotted name, e.g. `jsk.gates.check_ats`, or `jsk.adapters.cli.kb` for `kbcli.py`.
    """
    if script in ADAPTERS:
        return f"{PACKAGE}.{ADAPTERS[script]}"
    stem = script[:-3]
    where = SUBPACKAGE.get(script)
    return f"{PACKAGE}.{where}.{stem}" if where else f"{PACKAGE}.{stem}"


# The scripts whose main() takes the whole argv, program name first, the way
# `sys.exit(main(sys.argv))` hands it over. The others take the arguments alone.
WHOLE_ARGV = {"render_resume.py", "preview_templates.py", "preflight.py", "record.py"}


def run_in_process(script, args):
    """Call a script's main() in this interpreter. Exit code unchanged.

    Every dispatch used to spawn a child interpreter per call, which cost a Python
    start-up and a fresh import of the package each time. call_gate() does the loading
    and the two failure modes an in-process call adds: a module that will not import, and
    one that raises where it should have returned a verdict.

    Not captured: the script writes to this stdout as it goes, so a heading printed
    before the call is above the script's output and a long `jsk resume fit` still shows
    its progress.

    Args:
        script: the documented script name, a key of SUBPACKAGE or a root module's.
        args: its arguments alone.

    Returns:
        The script's exit code. Prints what it prints.
    """
    # A path or a title under a non-ASCII name reaches a cp1252 console as a
    # UnicodeEncodeError from inside the print, which loses the whole verdict.
    utf8_stdout()
    code, output = call_gate(script, args, capture=False)
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return code


def call_gate(script, args, argv0=None, capture=True):
    """(exit code, everything the script printed). Imported, never spawned.

    The output is captured so that --json can carry it whole; it is printed back
    unchanged either way. A gate whose findings the caller cannot read is a gate
    nobody checked, and summarising one here would be the same defect as an agent
    paraphrasing it. With `capture=False` the script prints straight through, and
    what comes back is only what this function itself had to say.

    Args:
        script: the documented script name.
        args: its arguments alone.
        argv0: whether its main() takes the program name first; by default whether the
            script is in WHOLE_ARGV.
        capture: capture what it prints rather than let it through.

    Returns:
        (exit code, output). Imports the module and runs its main().
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
        # In-process scripts share this interpreter, so an unhandled error inside one
        # would print a traceback where a verdict belongs and take the other gates
        # down with it. Report it as its own failure and keep going.
        return 2, buf.getvalue() + (
            f"FAIL  {script} raised {type(exc).__name__}: {exc}\n"
            f"fix:  run it directly to see the whole story - "
            f"{COMMANDS.get(script, 'jsk')} {' '.join(str(a) for a in args)}\n")
    return (code if isinstance(code, int) else 0), buf.getvalue()


# Nouns that make a record, report on one, or dispatch their own verbs - `jsk kb load`
# is the import itself, so the kb adapter refuses for the other kb verbs.
NO_RECORD = {"doctor", "kb"}


def workspace_refusal(noun, rest):
    """unloaded_refusal for the workspace a command runs in - the one around the current
    directory, or around any path it was given - or None.

    Args:
        noun: the command's noun.
        rest: the arguments after its verb.

    Returns:
        The refusal's lines, or None. Reads only whether paths exist.
    """
    from ...infra.files import find_root

    if noun in NO_RECORD or wants_help(rest):
        return None
    starts = [os.getcwd()] + [a for a in rest if not a.startswith("-") and os.path.exists(a)]
    for start in starts:
        refusal = unloaded_refusal(find_root(start))
        if refusal:
            return refusal
    return None
