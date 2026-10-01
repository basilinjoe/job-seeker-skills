"""What the `jsk kb` verbs print alike: a usage error, a refusal, a list of findings, and why
a record may not be written. Each reproduces the lines the verbs printed for themselves."""

# Why a record may not be written, and the fix: the states a stored record can be in
# other than clean (record.stored_state).
GUIDE = {
    "out-of-sync": (None, "restore the record from its backup: `jsk kb load .jsk/backup.trig` "
                          "into a new workspace (--root), then use that one"),
    "missing": ("there is no career record here",
                "run `jsk kb new`, or `jsk kb load` to import a workspace or a dump"),
}


def usage(message):
    """Print a `jsk kb` call that was wrong, and the usage line.

    Args:
        message: what was wrong with it.

    Returns:
        2, the exit code of a call made wrongly.
    """
    print(message)
    print("usage: jsk kb <verb> [arguments] [--root DIR] - `jsk kb --help` lists the verbs")
    return 2


def refuse(lines, fix=None):
    """Print why nothing was written.

    Args:
        lines: what is wrong, one line each.
        fix: the one fix for all of them, or None.

    Returns:
        1, the exit code of a refusal.
    """
    for line in lines:
        print(f"REFUSED  {line}")
    if fix:
        print(f"        fix: {fix}")
    print("nothing was written")
    return 1


def refuse_each(problems):
    """Print each problem with its own fix, then that nothing was written.

    Args:
        problems: [(what is wrong, its fix)].

    Returns:
        1, the exit code of a refusal.
    """
    for detail, fix in problems:
        print(f"REFUSED  {detail}\n        fix: {fix}")
    print("nothing was written")
    return 1


def show_findings(findings, title):
    """Print a title, then the FAIL findings under it, at most 25.

    Args:
        findings: domain.record.shapes.Finding, in the order found.
        title: the line above them.

    Returns:
        None.
    """
    from ...cliutil import show
    from ...domain.record.store import Store

    rep = Store("", findings=findings).report()
    print(title)
    show(rep.fails, "FAIL", 25)


def unclean(state):
    """Refuse a record in `state`, which is not clean, with its GUIDE line and fix.

    Args:
        state: the domain.record.state.State the record is in.

    Returns:
        1, the exit code of a refusal.
    """
    message, fix = GUIDE[state.kind]
    return refuse([message or state.detail], fix)


def unwritten(error):
    """Print a write the store refused (domain.record.state.RecordError), with its fix.

    Returns:
        1, the exit code of a failure.
    """
    print(f"FAIL  {error}\n        fix: {error.fix}")
    return 1
