"""`jsk resume check TARGET`: the gates a target calls for, chosen by what it is.

A resume.json gets the record gate, a render (.pdf, .tex, or a .txt named by hand) the parse and
prose gates -
`--only` narrowing that to one - and a render's directory all four
(adapters/cli/gates/check.py runs each). Ruling 10 of the onion design folds the three
commands that did this - `validate`, `check` and `gates` - into this one, and a flag that
does not fit the target's kind is a usage error naming the kind.
"""
import os

from .cliutil import wants_help
from .gates.check import cmd_check, cmd_gates, cmd_validate

RESUME_CHECK_USAGE = (
    "usage: jsk resume check <resume.json> [--strict] [--max-findings N]\n"
    "       jsk resume check <resume.pdf|.tex|.txt> [--strict] [--only parse|prose|layout]\n"
    "       jsk resume check <out-dir> [--record <resume.json>] [--pages N] [--json] "
    "[--max-findings N]")

# Every flag of `jsk resume check` that takes a value, the layout gate's included: what is
# after one is its value, never the target.
VALUE_FLAGS = ("--only", "--record", "--pages", "--max-findings", "--region")

# A record file, or one the record gate turns away by name (guards.record_refusal).
RECORD_SUFFIXES = (".json", ".md", ".ttl")

# kind -> (what it is called, what it gets, the flags it takes, its usage line). A flag of
# another kind's is a usage error that names the kind: `--pages` on a resume.json reads as a
# typo for the directory, and ignoring it would read as a page budget that was checked.
KINDS = {
    "record": ("a resume.json", "the record gate", ("--strict", "--max-findings"),
               "jsk resume check <resume.json> [--strict] [--max-findings N]"),
    "render": ("a render", "the parse and prose gates", ("--strict", "--only"),
               "jsk resume check <resume.pdf|.tex|.txt> [--strict] [--only parse|prose|layout]"),
    "directory": ("a render's directory", "all four gates",
                  ("--record", "--pages", "--json", "--max-findings"),
                  "jsk resume check <out-dir> [--record <resume.json>] [--pages N] [--json] "
                  "[--max-findings N]"),
}
FLAGS = {flag for kind in KINDS.values() for flag in kind[2]} | {"--region"}

# `--only layout` hands its arguments to the layout gate, and these are its flags.
LAYOUT_FLAGS = ("--record", "--region", "--pages")


def target_of(args):
    """The target `jsk resume check` was given: its first argument not a flag's value.

    Args:
        args: the arguments after the verb.

    Returns:
        The target, or None when there is none.
    """
    after_value = False
    for arg in args:
        if after_value:
            after_value = False
        elif arg in VALUE_FLAGS:
            after_value = True
        elif not arg.startswith("-"):
            return arg
    return None


def kind_of(target):
    """Which gates a target gets: "record", "render" or "directory".

    Args:
        target: the path named.

    Returns:
        "directory" for a directory, or a name with no extension that is not there (which
        the gates then refuse as not a directory); "record" for a resume.json, or a record
        file the record gate turns away by name; "render" for anything else, which the
        document gates read or report SKIPPED.
    """
    ext = os.path.splitext(target)[1].lower()
    if os.path.isdir(target) or (not ext and not os.path.exists(target)):
        return "directory"
    if ext in RECORD_SUFFIXES:
        return "record"
    return "render"


def only_of(args):
    """The value of --only in `args`, or None.

    Args:
        args: the arguments after the verb.

    Returns:
        The gate named, or None when --only is absent or ends the arguments.
    """
    if "--only" in args[:-1]:
        return args[args.index("--only") + 1]
    return None


def misfit(args, kind):
    """The first flag in `args` that `kind` of target does not take, or None.

    Args:
        args: the arguments after the verb.
        kind: a key of KINDS.

    Returns:
        The flag, or None. A flag no kind takes is left to the gate, which refuses it.
    """
    takes = set(KINDS[kind][2])
    if kind == "render" and only_of(args) == "layout":
        takes |= set(LAYOUT_FLAGS)
    return next((a for a in args if a in FLAGS and a not in takes), None)


def cmd_resume_check(args):
    """`jsk resume check TARGET`: the gates its target calls for.

    A resume.json gets the record gate (cmd_validate), a render the parse and prose gates
    (cmd_check), and a render's directory all four (cmd_gates). A flag the kind does not
    take, and --only letter, are refused before anything runs.

    Args:
        args: the arguments after the verb.

    Returns:
        The exit code of the gates run, or of the usage. Prints them.
    """
    target = target_of(args)
    if target is None:
        print(RESUME_CHECK_USAGE)
        return 0 if wants_help(args) else 2
    kind = kind_of(target)
    if kind == "render" and only_of(args) == "letter":
        at = args.index("--only")
        rest = args[:at] + args[at + 2:]
        print("--only letter left jsk resume check: a cover letter is jsk letter check now")
        print(f"fix:  jsk letter check {' '.join(rest)}")
        return 2
    flag = misfit(args, kind)
    if flag:
        called, gets, _, line = KINDS[kind]
        print(f"{flag} does not fit {called}, which gets {gets}: {target}")
        print(f"fix:  {line}")
        return 2
    run = {"record": cmd_validate, "render": cmd_check, "directory": cmd_gates}
    return run[kind](args)
