"""`jsk app freeze`: its flags, the application frozen, its gates and what was written said.

Archives one application directory: renames it to its day and writes its record - a
graph-native application's from the selection the store holds, not a resume.json. Never
touches the career or its log. `jsk app event` records what happens to the application
afterwards; this command only freezes what was sent. The freeze itself is
application/timeline/freeze.py, bound and run by compose/timeline.py's freeze_app, which
the `app_freeze` MCP tool calls too.
"""
import datetime
import os

from .cliutil import parse_flags, wants_help

FREEZE_USAGE = ("usage: jsk app freeze <app-dir> --submitted YYYY-MM-DD|false "
                "--channel TEXT [--doc FILE ...]")
GRAPH_STORE = os.path.join("career", "store")


def freeze_refusal(*lines):
    """Print a refused freeze: the reason, then each further line indented.

    Args:
        *lines: what the refusal says, the reason first.

    Returns:
        1, the exit code of a refused freeze.
    """
    print("REFUSED - " + lines[0])
    for line in lines[1:]:
        print("  " + line)
    return 1


def called(args):
    """The freeze a call asks for, or the exit code of one that is called wrong.

    Args:
        args: the arguments after `freeze`.

    Returns:
        (app_dir, workspace, submitted, channel, the --doc paths or None), or 0 for --help
        and 2 for a call error, having printed why.
    """
    from ... import cli

    if wants_help(args):
        print(FREEZE_USAGE)
        return 0
    if cli.view_refusal(args):
        print("\n".join(cli.VIEW_GONE))
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
    return app_dir, workspace, submitted, channel, flags.get("--doc")


def main(args):
    """`jsk app freeze`: archive one application directory, once every gate has passed.

    Args:
        args: the arguments after `freeze`.

    Returns:
        The exit code: 0 frozen, 1 refused, 2 called wrong. Prints the gates' output and
        what was written; renames the directory and writes the store.
    """
    call = called(args)
    if isinstance(call, int):
        return call
    app_dir, workspace, submitted, channel, named = call

    from ... import cli
    from ...application.timeline import freeze as F
    from .compose.timeline import freeze_app

    try:
        result = freeze_app(app_dir, workspace, submitted, channel, named,
                            gated=lambda results: cli.print_results(f"gates: {app_dir}",
                                                                    results))
    except F.FreezeRefused as refusal:
        return freeze_refusal(*refusal.lines)
    except F.FreezeLanded as landed:
        print(f"FAIL  the application's record was written, and then: {landed}")
        print(f"      fix: {landed.fix}")
        return 1
    return froze(result)


def froze(result):
    """Print what a freeze wrote and what it could not check.

    Args:
        result: the FreezeResult.

    Returns:
        0.
    """
    print(f"froze  {result.written}")
    if result.final != result.app_dir:
        print(f"moved  {result.app_dir} -> {result.final}")
    print(result.final)
    print()
    print("Frozen on the mechanical gates. The render gate is a person's: freezing")
    print("assumes somebody opened the PDF and read it. Nothing in this directory is")
    print("edited again; later events are `jsk app event <dir> <kind> --date ...`, and")
    print("`jsk kb query pipeline` gives each application's stage.")
    return 0
