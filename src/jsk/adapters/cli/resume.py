"""`jsk resume check TARGET`: the gates a target calls for, chosen by what it is.

A resume.json gets the record gate, a render (.pdf, .tex, .txt) the parse and prose gates -
`--only` narrowing that to one - and a render's directory all four
(adapters/cli/gates/check.py runs each). Ruling 10 of the onion design folds the three
commands that did this - `validate`, `check` and `gates` - into this one.
"""
import os

from ...cliutil import wants_help
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


def cmd_resume_check(args):
    """`jsk resume check TARGET`: the gates its target calls for.

    A resume.json gets the record gate (cmd_validate), a render the parse and prose gates
    (cmd_check), and a render's directory all four (cmd_gates).

    Args:
        args: the arguments after the verb.

    Returns:
        The exit code of the gates run, or of the usage. Prints them.
    """
    target = target_of(args)
    if target is None:
        print(RESUME_CHECK_USAGE)
        return 0 if wants_help(args) else 2
    run = {"record": cmd_validate, "render": cmd_check, "directory": cmd_gates}
    return run[kind_of(target)](args)
