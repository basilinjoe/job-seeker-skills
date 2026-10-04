"""What the CLI-shaped tools share: an internal entry point run inside the workspace, with what it
printed captured and turned into a tool's answer.

docs/superpowers/plans/2026-10-04-mcp-first.md, Ruling 5: `resume_ship` already ran the render,
the fit and every gate through the entry points their commands had (`render.rendered`,
`fit.fitted`, each gate's `main(argv)` through dispatch.call_gate). The tools that replaced
`jsk kb check|pack|merge`, `jsk resume check|render|preview|fit` and `jsk app drop` call them the
same way, so their verdict lines are the words the tests pin, byte for byte, and no second
reading of the flags exists to drift from the first.

Those entry points find the workspace and resolve relative paths from the working directory,
as a command run in a shell did. The server's working directory need not be the workspace
(JSK_ROOT), so each call runs inside it and goes back. The server answers one call at a time,
so the process-wide directory is never shared between two.
"""
import contextlib
import io
import os

from .server import result


@contextlib.contextmanager
def inside(root):
    """The working directory as `root` for the length of the block, then as it was.
    contextlib.chdir would do, but it came in 3.11 and jsk supports 3.10."""
    before = os.getcwd()
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(before)


def ran(root, script, args):
    """(exit code, everything it printed) of a documented script's main(), run inside `root`
    through dispatch.call_gate, which reports an import failure or a raise as exit 2."""
    from ..cli.dispatch import call_gate

    with inside(root):
        return call_gate(script, [str(a) for a in args])


def called(root, fn, args):
    """(exit code, everything it printed) of `fn(args)`, run inside `root`: for an entry point
    with no documented script name (adapters/cli/resume.cmd_resume_check). An argparse exit is
    its exit code; any other raise reaches Tools.call, which reports it as a FAIL.

    Args:
        root: the workspace root.
        fn: list of arguments -> exit code, printing as it goes.
        args: its arguments.
    """
    buf = io.StringIO()
    with inside(root), contextlib.redirect_stdout(buf):
        try:
            code = fn([str(a) for a in args])
        except SystemExit as exc:
            code = 0 if exc.code is None else (exc.code if isinstance(exc.code, int) else 2)
    return (code if isinstance(code, int) else 0), buf.getvalue()


def findings_in(output):
    """(severity, text, fix or None) for each FAIL and WARN line `output` holds, in order.

    Two spellings carry a fix: domain/gates/report.line's, the fix indented on the next line
    ("        fix: ..."), and a refusal's "fix:  ..." line under its FAIL. A finding's
    continuation lines are left in `output`, which every answer carries whole.
    """
    lines = output.splitlines()
    found = []
    for at, ln in enumerate(lines):
        # `jsk kb check` indents its findings two spaces under its "1 FAIL, 0 WARN" line;
        # without the strip, career_check answered ok false with one "exited 1" finding and
        # none of the FAILs it had printed (found 2026-10-04, in tests/test_mcp_upkeep.py).
        ln = ln.lstrip()
        severity = ln[:4]
        if severity not in ("FAIL", "WARN") or ln[4:5] not in (" ", ""):
            continue
        # The gates' count line, "FAIL 0   WARN 0", is a tally and not a finding: read as one
        # it made a passing parse gate not ok (2026-10-04, resume_check on a render).
        if ln[5:6].isdigit():
            continue
        nxt = lines[at + 1].strip() if at + 1 < len(lines) else ""
        found.append((severity, ln[4:].strip(), nxt if nxt.startswith("fix:") else None))
    return found


def answered(code, output, **data):
    """The tool's answer for an entry point that exited `code` having printed `output`.

    The findings are findings_in(output). An exit that is not 0 with no FAIL among them gets
    one, saying so, so `ok` never reads true over a refusal worded some other way. `verdict`
    is the last verdict line printed (VERDICTS), else the last line; `output` is all of it,
    since a gate whose findings the caller cannot read is a gate nobody checked
    (dispatch.call_gate).
    """
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    found = findings_in(output)
    if code and not any(f[0] == "FAIL" for f in found):
        found.append(("FAIL", f"exited {code}: {lines[0] if lines else 'nothing printed'}",
                      "the whole of what it printed is in output"))
    verdicts = [ln for ln in lines if ln.startswith(VERDICTS)]
    return result(found, exit=code, verdict=(verdicts or lines or [None])[-1], output=output,
                  **data)


# How a verdict line starts, as the gates, the fit and the ship print one. Not the last line
# alone: the parse gate closes with "open the PDF and read it" and the fit with "Recompile
# that .tex", advice after the verdict, which a caller reading `verdict` would take for it
# (2026-10-04, the first resume_check and resume_fit tools).
VERDICTS = ("PASS - ", "FAIL - ", "DO NOT ", "verdict: ")
