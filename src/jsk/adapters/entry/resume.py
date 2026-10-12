"""The resume check's entry point: the gates a target calls for, chosen by what it is.

This module is what the `resume_check` tool (jsk mcp) calls (`cmd_resume_check`).
`jsk resume check` was retired in 6.0 (2026-10-04, docs/superpowers/plans/2026-10-04-mcp-first.md,
Ruling 5): it exits 2 naming the tool, and the tool takes `target`, `record`, `only`, `strict`
and `pages`. The usage text below is what a call with no target prints.

A target's selection gets the record gate, a render (.pdf, .tex, or a .txt named by hand) the
parse and prose gates - `--only` narrowing that to one - and a render's directory all four
(adapters/entry/gates/check.py runs each). Ruling 10 of the onion design folds the three
commands that did this - `validate`, `check` and `gates` - into this one, and a flag that
does not fit the target's kind is a usage error naming the kind.

A target - `<stem>` or `resumes/<name>`, with no file of that name - is a record: its
selection graph gets the record gate (Ruling 12 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md). A directory that exists
is still a directory. A resume.json got the record gate until 6.0, which reads none: one is
told the target form, exit 2.
"""
import os

from .cliutil import wants_help
from .gates.check import cmd_check, cmd_gates, cmd_validate

RESUME_CHECK_USAGE = (
    "usage: resume_check(<stem>|resumes/<name>, strict=)\n"
    "       resume_check(<resume.pdf|.tex|.txt>, strict=, only=parse|prose|layout)\n"
    "       resume_check(<out-dir>, record=<stem>, pages=N)")

# Every flag of the resume_check tool that takes a value, the layout gate's included: what is
# after one is its value, never the target.
VALUE_FLAGS = ("--only", "--record", "--pages", "--max-findings", "--region")

# A record file the record gate turns away by name (guards.record_refusal): a resume.json,
# retired in 6.0, and the career's own formats.
RECORD_SUFFIXES = (".json", ".md", ".ttl")

# kind -> (what it is called, what it gets, the flags it takes, its usage line). A flag of
# another kind's is a usage error that names the kind: `--pages` on a target reads as a
# typo for the directory, and ignoring it would read as a page budget that was checked.
KINDS = {
    "record": ("a target", "the record gate", ("--strict", "--max-findings"),
               "resume_check(<stem>|resumes/<name>, strict=)"),
    "render": ("a render", "the parse and prose gates", ("--strict", "--only"),
               "resume_check(<resume.pdf|.tex|.txt>, strict=, only=parse|prose|layout)"),
    "directory": ("a render's directory", "all four gates",
                  ("--record", "--pages", "--json", "--max-findings"),
                  "resume_check(<out-dir>, record=<stem>, pages=N)"),
}
FLAGS = {flag for kind in KINDS.values() for flag in kind[2]} | {"--region"}

# `--only layout` hands its arguments to the layout gate, and these are its flags.
LAYOUT_FLAGS = ("--record", "--region", "--pages")


def target_of(args):
    """The target the resume_check tool was given: its first argument not a flag's value.

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
        the gates then refuse as not a directory); "record" for a record file the record
        gate turns away by name; "render" for anything else, which the document gates read
        or report SKIPPED.
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


def file_made_refusal(target):
    """The lines refusing the resume_check tool on an application made from files, or None
    when `target` names none. It has no selection to check: frozen, its files are the
    archive; unsent, Ruling 5's note says what still finishes it.

    Args:
        target: the positional, a name that is neither a target nor a directory.
    """
    from ...application.timeline.unsent import note
    from ..compose.selection import file_made

    made = file_made(target)
    if made is None:
        return None
    rel, frozen, post = made
    if not frozen:
        text, fix = note(rel.removeprefix("applications/"))
        return [text, f"fix:  {fix}"]
    show = f"the career_show tool (jsk mcp) on {post} or " if post else ""
    return [f"{target} names {rel}, a frozen application made from files: it has no "
            "selection to check - its files are the archive of what was sent",
            f"fix:  read it with {show}the app_show tool (jsk mcp); resume_check(<dir>) "
            "checks a render's directory"]


def cmd_resume_check(args):
    """The exit code of the gates the resume_check tool runs, chosen by its target.

    A target gets the record gate (cmd_validate), a render the parse and prose gates
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
    from ..compose.selection import ref_for

    ref = None if os.path.exists(target) else ref_for(target)
    if ref is not None:
        args = [ref if a is target else a for a in args]
    kind = "record" if ref is not None else kind_of(target)
    if kind == "record" and ref is None:
        # A resume.json, or a career file: told what to name instead, whatever the flags -
        # a flag that does not fit a form 6.0 retired is not the thing to fix first.
        from ...application.guards import record_refusal

        refusal = record_refusal(target)
        if refusal:
            print("\n".join(refusal))
            return 2
    if kind == "directory" and not os.path.isdir(target):
        refusal = file_made_refusal(target)
        if refusal:
            print("\n".join(refusal))
            return 2
    if kind == "render" and only_of(args) == "letter":
        print("--only letter left the resume_check tool: a cover letter is checked by the "
              "letter_check tool now")
        print("fix:  the letter_check tool (jsk mcp): letter_check(letter, record=<stem>)")
        return 2
    flag = misfit(args, kind)
    if flag:
        called, gets, _, line = KINDS[kind]
        print(f"{flag} does not fit {called}, which gets {gets}: {target}")
        print(f"fix:  {line}")
        return 2
    run = {"record": cmd_validate, "render": cmd_check, "directory": cmd_gates}
    return run[kind](args)
