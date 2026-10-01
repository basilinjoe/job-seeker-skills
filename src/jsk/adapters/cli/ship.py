"""`jsk resume ship`: its flags and refusals, the ship run (application/ship.py), every step said.

Each step's output is what its own command prints - the record gate's, `jsk resume render`'s,
`jsk resume fit`'s, each gate's - captured as it runs, and the summary and --json are what
`jsk resume check` prints over its steps.

A graph-native target - `<stem>` or `resumes/<name>` - ships from its selection graph into
its own directory, with no --out (compose.selection.ref_for reads the positional).
"""
import contextlib
import io
import json
import os

from .cliutil import parse_flags, wants_help

SHIP_USAGE = ("usage: jsk resume ship <resume.json> --out DIR [--ats-max] "
              "[--template N] [--pages N] [--no-fit] [--json]\n"
              "       jsk resume ship <stem>|resumes/<name> [--ats-max] [--template N] "
              "[--pages N] [--no-fit] [--json]")

SHIP_VALUE_FLAGS = ("--out", "--template", "--pages")


def called(args):
    """The ship a call asks for, or the exit code of one that is called wrong.

    Args:
        args: the arguments after `ship`.

    Returns:
        (record, its flags, the page budget or None), or 0 for --help, 1 for a frozen
        application and 2 for a call error, having printed why. A graph-native target
        (`<stem>`, `resumes/<name>`) comes back as its ref, its directory as --out.
    """
    from ...application.guards import (VIEW_GONE, frozen_refusal, record_refusal,
                                       view_refusal)
    from .compose.timeline import frozen
    from .gates.check import parse_pages

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
    from .compose.selection import ref_for

    ref = ref_for(record, dirs=True)
    if ref is not None:
        # A graph-native target ships into its own directory (Ruling 12 of the graph-native
        # plan): `applications/<stem>/` or `resumes/<name>/`, made by the render.
        home = os.path.dirname(ref)
        out = flags.get("--out")
        if out and os.path.normcase(os.path.abspath(out)) != os.path.normcase(home):
            print(f"--out {out}: {record} renders into its own directory, {home}")
            print("fix:  drop --out")
            return 2
        record, flags["--out"] = ref, home
    refusal = record_refusal(record)
    if refusal:
        print("\n".join(refusal))
        return 2
    if not flags.get("--out"):
        print("--out is required")
        print("fix:  --out names the directory to render into - the application's own")
        return 2
    # Before anything renders (Review Focus 5): the render writes over the PDF and .txt
    # that the application's record says were sent, and the archive would then describe
    # files it no longer holds.
    refusal = frozen_refusal(flags["--out"], os.path.dirname(os.path.abspath(record)),
                             frozen=frozen)
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
        from ...domain.render import themes
        try:
            themes.get(template)
        except KeyError as exc:
            print(f"usage: {exc.args[0]}")
            return 2
    return record, flags, pages


def held(script, call, args):
    """One step run in this interpreter with its output captured, contained as
    dispatch.call_gate contains a module: a step that raised is reported as its own failure.

    Args:
        script: the step's documented script name, e.g. "render_resume.py".
        call: () -> (exit code, its result).
        args: the step's arguments, for the hint a step that raised prints.

    Returns:
        (exit code, everything it printed, its result or None).
    """
    from .dispatch import COMMANDS

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code, result = call()
    except SystemExit as exc:
        # argparse's --help exits 0 by raising; so would a bare sys.exit().
        code = 0 if exc.code is None else (exc.code if isinstance(exc.code, int) else 2)
        return code, buf.getvalue(), None
    except Exception as exc:                      # noqa: BLE001 - deliberately broad
        # The steps share this interpreter, so an unhandled error inside one would print
        # a traceback where a verdict belongs.
        return 2, buf.getvalue() + (
            f"FAIL  {script} raised {type(exc).__name__}: {exc}\n"
            f"fix:  run it directly to see the whole story - "
            f"{COMMANDS[script]} {' '.join(str(a) for a in args)}\n"), None
    return (code if isinstance(code, int) else 0), buf.getvalue(), result


def render(args):
    """`jsk resume render` over `args`, with compose.render's TeX engine.

    Returns:
        (exit code, its output, the RenderResult or None).
    """
    from .compose.render import Tex, company_of
    from .render import rendered

    return held("render_resume.py", lambda: rendered(
        ["render_resume.py"] + list(args), tex=Tex(), company_of=company_of), args)


def fit(args):
    """`jsk resume fit` over `args`, with compose.fit's TeX engine.

    Returns:
        (exit code, its output, the FitResult or None).
    """
    from .compose.fit import Tex
    from .fit import fitted

    return held("fit_pages.py", lambda: fitted(list(args), tex=Tex()), args)


def main(args):
    """`jsk resume ship`: record gate, render, fit, mechanical gates - one process.

    Args:
        args: the arguments after `ship`.

    Returns:
        The exit code: 0 or 1 once it runs, 2 for a call error. Prints each step's output
        and the summary, or --json; renders into --out.
    """
    call = called(args)
    if isinstance(call, int):
        return call
    record, flags, pages = call
    out_dir = flags["--out"]

    from ...application.ship import ship
    from ...infra import outputs
    from ...infra.files import rel
    from .compose import render as bound
    from .gates.check import Shown, contained, measure, print_results, strict_for

    result = ship(record, out_dir, ats_max=bool(flags.get("--ats-max")),
                  template=flags.get("--template"), pages=pages,
                  fit=not flags.get("--no-fit"), run=contained, render=render, fitter=fit,
                  tex_engine=bound.Tex(), page_count=bound.page_count,
                  outputs=outputs, rel=rel, strict=strict_for, measure=measure)
    steps = [Shown(s) for s in result.steps]
    if flags.get("--json"):
        print(json.dumps({"record": record, "out_dir": out_dir,
                          "exit": result.exit, "steps": steps}, indent=2))
        return result.exit
    print_results(f"ship: {record} -> {out_dir}", steps)
    return result.exit
