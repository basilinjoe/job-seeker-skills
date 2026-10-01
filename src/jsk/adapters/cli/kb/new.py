"""Scaffold a career workspace: the graph record, its log, and a place to file applications.

Usage: jsk kb new <path> --name "Their Name" [--force]
       <path>     the workspace folder to create; career/ goes inside it
       --name     the person's full name; the record's header says whose it is
       --force    start an existing record over from the empty one, logged, the old
                  record kept beside it as a dump, career/kb.r<N>.trig

Exit 0 = written. Exit 1 = refused, because something was already there, or pyoxigraph
is missing (the record is a pyoxigraph store). Exit 2 = called wrongly.

It writes:

  career/store/     the record: the empty career - the header naming the person - at r1,
                    and its log, k:rev_1 `j:by j:new` - so `jsk kb apply` works on it
                    straight away
  applications/     with a README saying what each application directory holds
  .gitattributes    `career/store/** binary`, so git never rewrites the store's line ends

Written through the same gate every `jsk kb` write uses (record.write_graphs): one
update, and .jsk/backup.trig after it.
"""
import datetime
import os
import sys

from ..cliutil import docstring_usage, utf8_stdout, wants_help

INSTALL = 'python -m pip install "jsk-resume"   - pyoxigraph is one of its dependencies'


class Disk:
    """The scaffold's own files, written as text with LF line ends."""

    def create_text(self, path, text):
        """Write a new file; OSError, and nothing written, when `path` is there already."""
        with open(path, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def write_text(self, path, text):
        """Write `path`, replacing it."""
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def append_text(self, path, text):
        """Append `text` to `path`, creating it."""
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def makedirs(self, path):
        """Make the folder and its parents, if they are not there."""
        os.makedirs(path, exist_ok=True)


def scaffold(root, name, force=False, today=None):
    """(exit code, lines to print). Writes the workspace, or refuses and says why.

    Args:
        root: the workspace folder.
        name: the person's full name.
        force: start an existing record over.
        today: the day the log entry is dated; the clock's today when None.

    Returns:
        The exit code and the lines `jsk kb new` prints. Writes the workspace.
    """
    from ....application.record import scaffold as N
    from ....application.record.refusals import Failing, Unclean
    from ..compose.record import load
    from ....infra import files, legacy_import as legacy
    from ....infra.oxigraph import db
    from ....infra.oxigraph import record as R

    today = today or datetime.date.today()
    try:
        done = N.scaffold(root, name, force, today, load=load, record=R, db=db,
                          legacy=legacy, files=files, disk=Disk())
    except N.NoEngine:
        return 1, no_engine()
    except (N.LaidOutAsFiles, N.Exists, Unclean, Failing, N.NotKept, N.Unwritten) as err:
        return 1, refusal(err)
    lines = []
    if done.kept:
        lines.append(f"kept   {done.kept} (the record --force replaces; `jsk kb load` reads it)")
    lines.append(f"wrote  {done.store} (r{done.revision}, by new)")
    if done.readme:
        lines.append(f"wrote  {done.readme}")
    lines.append(attributes(done.attributes))
    lines.append("")
    lines.append("Next: a changeset adding k:person - j:fullName, an email and a phone - and")
    lines.append("`jsk kb apply` it. Without an email and a phone the parse gate fails, so")
    lines.append("nothing sendable renders. `jsk kb view` reads the record back.")
    return 0, lines


def no_engine():
    """The lines refusing a Python without pyoxigraph."""
    return ["FAIL  jsk kb new writes the record into a pyoxigraph store, and this Python "
            "has not got pyoxigraph",
            f"      fix: {INSTALL}"]


def refusal(err):
    """The lines saying why nothing (or, for Unwritten, only the kept dump) was written."""
    import contextlib
    import io

    from ....application.record import scaffold as N
    from ....application.record.refusals import Failing, Unclean
    from ..cliutil import show
    from ....domain.record.store import Store
    from ..presenters import GUIDE

    if isinstance(err, N.LaidOutAsFiles):
        return [f"REFUSED  {err.path} is a record still laid out as files",
                "        fix: `jsk kb load .` in that workspace moves it into "
                "career/store/ - nothing is started over",
                "nothing was written"]
    if isinstance(err, N.Exists):
        return [f"REFUSED  already exists: {err.store}",
                "        fix: change it with `jsk kb apply`; or --force to start over "
                "from the empty record (logged, the old record kept beside it as a "
                "dump, career/kb.r<N>.trig)"]
    if isinstance(err, Unclean):
        message, fix = GUIDE[err.state.kind]
        return [f"REFUSED  {message or err.state.detail} - starting over now would replace "
                "a record the log does not account for",
                f"        fix: {fix}; then --force again", "nothing was written"]
    if isinstance(err, Failing):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            show(Store("", findings=err.findings).report().fails, "FAIL", 25)
        return [err.title, *buf.getvalue().rstrip("\n").splitlines(),
                "        fix: a frozen application keeps its links; start a new "
                "workspace elsewhere instead", "nothing was written"]
    if isinstance(err, N.NotKept):
        return [f"FAIL  could not keep the old record at {err.path}: {err.error}",
                "        fix: free the path, or check the folder is writable",
                "nothing was written"]
    kept = [f"kept   {err.kept} (the record --force replaces; `jsk kb load` reads it)"] \
        if err.kept else []
    return kept + [f"FAIL  {err.error}", f"        fix: {err.error.fix}"]


def attributes(done):
    """The line saying what became of .gitattributes (application.record.scaffold.Attributes)."""
    from ....application.record.scaffold import GITATTRIBUTES

    if done.done == "left":
        return (f"left   {done.path}: {done.error}\n        fix: {done.error.fix}, then add "
                + "; ".join(f"`{rule}`" for rule in GITATTRIBUTES))
    if done.done == "kept":
        return f"kept   {done.path}"
    return f"{'added to' if done.done == 'added' else 'wrote '} {done.path}"


def main(argv=None):
    """`jsk kb new`: parse the path, --name and --force, scaffold, print what was done.

    Args:
        argv: the arguments after `new`; by default sys.argv's.

    Returns:
        The exit code: 0 written, 1 refused, 2 called wrongly.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if wants_help(argv) or not argv:
        print(docstring_usage(__doc__))
        return 0 if wants_help(argv) else 2

    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]

    name = None
    if "--name" in argv:
        at = argv.index("--name")
        if at + 1 >= len(argv):
            print("--name needs a value")
            print('fix:  --name "Their Name"')
            return 2
        name = argv[at + 1]
        del argv[at:at + 2]

    if len(argv) != 1:
        print("usage: jsk kb new <path> --name \"Their Name\"")
        return 2
    if not name or not name.strip():
        print("--name is required")
        print("fix:  the record's header says whose career it is, and a record that")
        print("      cannot say whose it is renders nothing sendable")
        return 2

    code, lines = scaffold(argv[0], name.strip(), force=force, today=datetime.date.today())
    utf8_stdout()
    for line in lines:
        print(line)
    return code
