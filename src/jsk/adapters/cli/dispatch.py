"""How `jsk` runs a command in this interpreter: the adapter behind it found, its main() called.

Each verb is named by the documented script name its command had - what every comment in the
codebase and every shell history call it - and ADAPTERS says which adapter module serves it,
so the file moves and the name does not. The adapter binds its own ports from compose/.
"""
import contextlib
import importlib
import io
import os

from ...application.guards import unloaded_refusal
from .cliutil import utf8_stdout, wants_help

PACKAGE = __name__.split(".")[0]

# The adapter module each documented script name is served by, under the package. A name
# not here is a root module of its own (preflight.py).
ADAPTERS = {
    "kb.py": "adapters.cli.kb.new",
    "kbcli.py": "adapters.cli.kb",
    "render_resume.py": "adapters.cli.render",
    "preview_templates.py": "adapters.cli.preview",
    "fit_pages.py": "adapters.cli.fit",
    "check_ats.py": "adapters.cli.gates.ats",
    "check_prose.py": "adapters.cli.gates.prose",
    "record.py": "adapters.cli.gates.record",
    "letter.py": "adapters.cli.gates.letter",
    "layout.py": "adapters.cli.gates.layout",
}

# What answers for each script, for the hint that says how to run one again. The commands
# that remain are named as commands; the rest went on 2026-10-04 and their tools are named
# (docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 4), since a hint naming a retired
# command would send the reader to an exit 2.
COMMANDS = {
    "kb.py": "jsk kb new",
    "kbcli.py": "the career_check, career_pack or career_merge tool (jsk mcp)",
    "render_resume.py": "the resume_render tool (jsk mcp)",
    "preview_templates.py": "the resume_preview tool (jsk mcp)",
    "fit_pages.py": "the resume_fit tool (jsk mcp)",
    "preflight.py": "jsk doctor",
}


def rerun_hint(script, args):
    """The `fix:` line for a script that raised: how to run it again and see the whole story.

    Args:
        script: its documented script name.
        args: its arguments, repeated after a command and left out after a tool, whose
            arguments are named by the tool.

    Returns:
        One line, without its newline.
    """
    answers = COMMANDS.get(script, "jsk")
    if answers.startswith("the "):
        return f"fix:  call {answers} again with the same arguments to see the whole story"
    shown = " ".join(str(a) for a in args)
    return f"fix:  run it directly to see the whole story - {answers} {shown}"


def module_for(script):
    """The module a documented script name is.

    Args:
        script: e.g. `check_ats.py`.

    Returns:
        Its dotted name, e.g. `jsk.adapters.cli.gates.ats`, or `jsk.preflight` for
        `preflight.py`.
    """
    return f"{PACKAGE}.{ADAPTERS.get(script, script[:-3])}"


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
    before the call is above the script's output and a long resume_fit still shows
    its progress.

    Args:
        script: the documented script name, a key of ADAPTERS or a root module's.
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
            f"{rerun_hint(script, args)}\n")
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
