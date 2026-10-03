"""The commands that serve only applications made from files, which retire in 6.0, and what
each one says until then.

docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, Ruling 1: release 5.1 keeps every
file verb working and prints one WARN on each, used in its file form, naming the tool that
replaces it; release 6.0 makes each exit 2 through main.py's RETIRED table. The words and
the verb -> replacement map are here and nowhere else, so P2 turns REPLACEMENTS into RETIRED
entries rather than collecting them again from a dozen adapters. Ruling 5's note on an
unsent file-made application is application/timeline/unsent.py's.

It decides only from the arguments: whether `jsk app freeze`'s application was made from
files needs the store, so adapters/cli/freeze.py and the `app_freeze` tool ask and then
print warning("jsk app freeze") themselves. It never refuses and never changes an exit code.
"""
import sys

# The release the file verbs leave in. Named once: P2 bumps it with the version.
RETIRES_IN = "6.0"

# command -> what replaces it, the table of the plan's "What retires". The MCP tools are named
# with `(jsk mcp)` because a shell user reads the fix too; a target form is named where the
# CLI keeps one.
REPLACEMENTS = {
    "jsk kb export --out": "the resume_select tool (jsk mcp)",
    "jsk resume check <resume.json>":
        "`jsk resume check <stem>`, on the application's stored selection",
    "jsk resume render <resume.json>":
        "`jsk resume render <stem>`, on the application's stored selection",
    "jsk resume preview <resume.json>":
        "`jsk resume preview <stem> --out DIR`, on the application's stored selection",
    "jsk resume ship <resume.json>":
        "`jsk resume ship <stem>`, or the resume_ship tool (jsk mcp)",
    "jsk kb confirm --summary <resume.json>":
        "the career_confirm tool with target and block (jsk mcp), or "
        "`jsk kb confirm --summary <stem>`",
    "jsk kb confirm --headline <resume.json>":
        "the career_confirm tool with target and block (jsk mcp), or "
        "`jsk kb confirm --headline <stem>`",
    "jsk letter check --record <resume.json>":
        "the letter_check tool with record=<stem> (jsk mcp), or "
        "`jsk letter check LETTER --record <stem>`",
    "jsk app freeze": "the app_freeze tool on a graph-native application (jsk mcp)",
}

# The flags of `jsk resume check|render|preview|ship` that take a value: what follows one is
# its value, never the resume named (adapters/cli/resume.py's VALUE_FLAGS, ship.py's, and
# render's --template, --format and --view).
VALUE_FLAGS = ("--only", "--record", "--pages", "--max-findings", "--region", "--out",
               "--template", "--format", "--view")


def is_record_file(value):
    """Whether `value` names a resume.json - a record file - rather than a stem or a render."""
    return bool(value) and value.lower().endswith(".json")


def target_of(args):
    """The first argument that is not a flag or a flag's value, or None."""
    after_value = False
    for arg in args:
        if after_value:
            after_value = False
        elif arg in VALUE_FLAGS:
            after_value = True
        elif not arg.startswith("-"):
            return arg
    return None


def value_of(args, flag):
    """The value after `flag` in `args`, or None."""
    if flag in args[:-1]:
        return args[args.index(flag) + 1]
    return None


def file_form(noun, verb, args):
    """The REPLACEMENTS key of a call that uses a verb in its file form, else None.

    Args:
        noun, verb: the command's.
        args: the arguments after the verb.

    Returns:
        The command as REPLACEMENTS names it. `jsk app freeze` is never returned here: its
        file form is a property of the application, which the store says.
    """
    if noun == "kb" and verb == "export" and "--out" in args:
        return "jsk kb export --out"
    if noun == "kb" and verb == "confirm":
        for flag in ("--summary", "--headline"):
            if is_record_file(value_of(args, flag)):
                return f"jsk kb confirm {flag} <resume.json>"
        return None
    if noun == "resume" and verb in ("check", "render", "preview", "ship"):
        return f"jsk resume {verb} <resume.json>" if is_record_file(target_of(args)) else None
    if noun == "letter" and verb == "check" and is_record_file(value_of(args, "--record")):
        return "jsk letter check --record <resume.json>"
    return None


def warning(command):
    """(the WARN's words, its fix's words) for `command`, a REPLACEMENTS key.

    The words are Ruling 1's; the tools' findings and the CLI's line both say them.
    """
    return (f"{command} serves applications made from files and retires in {RETIRES_IN} - "
            "finish this application or drop it", REPLACEMENTS[command])


def lines(command):
    """The WARN as a command prints it: the line, then its fix indented beneath."""
    text, fix = warning(command)
    return f"WARN  {text}\n      fix: {fix}"


def warn(command, args):
    """Print the WARN for `command`: to stderr when `--json` is in `args`, since a reader
    parses that stdout whole, else to stdout above what the command prints.

    Args:
        command: a REPLACEMENTS key.
        args: the call's arguments.
    """
    print(lines(command), file=sys.stderr if "--json" in args else sys.stdout)

