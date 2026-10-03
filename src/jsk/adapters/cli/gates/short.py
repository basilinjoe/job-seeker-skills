"""The short file's own check of one target's selection: its shape and its ids, PASS or FAIL.

The record gate (adapters/cli/gates/record.py) asks this and everything else of a
selection; this is the check with no gate behind it, over domain/resume/short.py's rules
and the selection and career compose.resume reads. It read a resume.json until 6.0, which
reads none.
"""
from ..cliutil import utf8_stdout


def main(argv):
    """Check one target's selection's shape and ids against the career it sits in.

    Args:
        argv: the whole argv, the program name first, then the target's ref.

    Returns:
        The exit code: 0 PASS, 1 FAIL, 2 called wrong. Prints the verdict; loads the
        workspace.
    """
    from ....domain.resume.short import ShortError, ids, shape
    from ..compose.resume import career, read, workspace

    args = argv[1:]
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: jsk resume check <stem>|resumes/<name>")
        return 2
    path = args[0]
    utf8_stdout()
    print(f"checking: {path}")
    try:
        doc = read(path)
        root = workspace(path)
        fails = shape(doc) or ids(doc, career(root))
    except ShortError as e:
        print(f"FAIL  {e}\n      fix: {e.fix}")
        return 1
    for line in fails:
        print(f"FAIL  {line}")
    if fails:
        print(f"FAIL {len(fails)}")
        return 1
    print("PASS - safe to render")
    return 0
