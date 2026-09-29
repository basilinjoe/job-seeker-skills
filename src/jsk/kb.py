#!/usr/bin/env python3
"""Scaffold a career workspace: the graph record, its log, and a place to file applications.

Usage: jsk new <path> --name "Their Name" [--force]
       python -m jsk.kb <path> --name "Their Name" [--force]
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

from .cliutil import docstring_usage, utf8_stdout, wants_help

STORE = "career/store"

# The store is RocksDB's files, some of them text-like: git's autocrlf must never touch
# them. Whatever else the file already says, this is added.
GITATTRIBUTES = ("career/store/** binary",)

INSTALL = 'python -m pip install "jsk-resume"   - pyoxigraph is one of its dependencies'

APPLICATIONS_README = """# Applications

One directory per submission, named `<yyyy-mm-dd>-<company>-<role>` - the date being
the day it was sent. Each holds the whole of that application:

| File | Is |
|---|---|
| `posting.md` | the advertisement verbatim, nothing added |
| `gaps.md` | the assessment of the career against it, and the question queue |
| `resume.json` | the short record this submission rendered from |
| `<Name>_<Company>_Resume.{tex,pdf,txt}` | the files actually sent |

What the posting asks for, and what was sent - the bullets and metric versions it
carried, and every event since (`jsk event`) - are kept in the record, career/store/,
beside the career.

**Everything in here is frozen at submission.** The career keeps moving; an application
that pointed at a moving record could not answer what it was answering.

An application worked through and then held back is still a real application:
`jsk freeze <dir> --submitted false`.
"""


def header(name):
    import pyoxigraph as ox

    from .graph import ontology as O

    kb = ox.NamedNode(O.K + "kb")
    return [ox.Quad(kb, ox.NamedNode(O.J + "format"),
                    ox.Literal(str(O.FORMAT), datatype=ox.NamedNode(O.XSD + "integer"))),
            ox.Quad(kb, ox.NamedNode(O.J + "name"), ox.Literal(name))]


def first_write(name, today):
    """{graph: quads} for a workspace with no career yet: the empty record, r1 by `new`."""
    from .graph import record as R
    from .graph.io import sha256
    from .graph.writer import write

    kb = R.stamp(header(name), 1, today)
    log = R.entry(1, today, "new", f"Created by jsk new for {name}: an empty record.",
                  sha256(write(kb, "kb")))
    return {R.KB: kb, R.LOG: log}


def kept_name(root, revision):
    """career/kb.r<N>.trig - or kb.r<N>-2.trig, -3... - the first that is not there yet.

    Beside the store, where the person will see it: .jsk/ is a cache that ignores itself,
    and a workspace need not be a git repository. A dump, so `jsk kb load` reads it back."""
    base = f"career/kb.r{revision}"
    rel, n = f"{base}.trig", 2
    while os.path.exists(os.path.join(root, rel)):
        rel, n = f"{base}-{n}.trig", n + 1
    return rel


def restart(root, name, today):
    """((graphs, revision, kept, dump text), None) replacing the career with the empty
    record, as the next revision of the log already there, the whole old record to be kept
    as a dump at `kept` - or (None, refusal lines).

    Only a clean record is started over: anything else was written outside jsk, and the
    log could not say what was replaced."""
    import contextlib
    import io

    from .gates.report import show
    from .graph import db
    from .graph import record as R
    from .graph import store as S
    from .graph.kbcli import GUIDE

    store = S.load(root)
    st = R.state(store)
    if st.kind != "clean":
        message, fix = GUIDE[st.kind]
        return None, [f"REFUSED  {message or st.detail} - starting over now would replace "
                      "a record the log does not account for",
                      f"        fix: {fix}; then --force again"]
    kept = kept_name(root, st.kb_revision)
    p = R.prepared(store, header(name), today, "new",
                   f"Started over by jsk new --force for {name}: the career replaced by the "
                   f"empty record. r{st.kb_revision}, the last of the old record, is kept as "
                   f"{kept}.")
    after = S.load(root, graphs=p.graphs())
    if after.fails():
        lines = [f"REFUSED  starting over would leave {len(after.fails())} failures - an "
                 "application that carried an entry the empty record does not have:"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            show(after.report().fails, "FAIL", 25)
        lines += buf.getvalue().rstrip("\n").splitlines()
        lines.append("        fix: a frozen application keeps its links; start a new "
                     "workspace elsewhere instead")
        return None, lines
    return (p.graphs(), p.revision, kept, db.dump_text(db.read(root))), None


def gitattributes(root):
    """Add whichever of GITATTRIBUTES the workspace's .gitattributes lacks. Never removes."""
    from .graph.io import Missing, Unreadable, read_text

    path = os.path.join(root, ".gitattributes")
    try:
        have = read_text(path, ".gitattributes")
    except Missing:
        have = ""
    except Unreadable as e:
        # The person's own file, and the record is already written: say what to add
        # rather than append to bytes that could not be read.
        return (f"left   {path}: {e}\n        fix: {e.fix}, then add "
                + "; ".join(f"`{rule}`" for rule in GITATTRIBUTES))
    lines = {line.strip() for line in have.splitlines()}
    missing = [rule for rule in GITATTRIBUTES if rule not in lines]
    if not missing:
        return f"kept   {path}"
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        if have and not have.endswith("\n"):
            fh.write("\n")
        fh.write("\n".join(missing) + "\n")
    return f"{'added to' if have else 'wrote '} {path}"


def scaffold(root, name, force=False, today=None):
    """(exit code, lines to print). Writes the workspace, or refuses and says why."""
    today = today or datetime.date.today()
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        return 1, ["FAIL  jsk new writes the record into a pyoxigraph store, and this Python "
                   "has not got pyoxigraph",
                   f"      fix: {INSTALL}"]
    from .graph import db, legacy
    from .graph import record as R

    store = os.path.normpath(os.path.join(root, STORE))
    exists = db.exists(root)
    if not exists and legacy.has_files(root):
        return 1, [f"REFUSED  {os.path.normpath(os.path.join(root, 'career', 'kb.ttl'))} is a "
                   "record still laid out as files",
                   "        fix: `jsk kb load .` in that workspace moves it into career/store/ - "
                   "nothing is started over",
                   "nothing was written"]
    if exists and not force:
        return 1, [f"REFUSED  already exists: {store}",
                   "        fix: change it with `jsk kb apply`; or --force to start over from "
                   "the empty record (logged, the old record kept beside it as a dump, "
                   "career/kb.r<N>.trig)"]
    lines = []
    # --force reads the record it replaces: its turn first, so nothing lands in between.
    with R.turn(root):
        if exists:
            done, refusal = restart(root, name, today)
            if refusal:
                return 1, refusal + ["nothing was written"]
            graphs, rev, kept, dump = done
            kept = os.path.normpath(os.path.join(root, kept))
            try:
                with open(kept, "x", encoding="utf-8", newline="\n") as fh:   # never overwrites
                    fh.write(dump)
            except OSError as e:
                return 1, [f"FAIL  could not keep the old record at {kept}: {e}",
                           "        fix: free the path, or check the folder is writable",
                           "nothing was written"]
            lines.append(f"kept   {kept} (the record --force replaces; `jsk kb load` reads it)")
        else:
            graphs, rev = first_write(name, today), 1
            os.makedirs(os.path.join(root, "career"), exist_ok=True)
        try:
            R.write_graphs(root, graphs, create=not exists)
        except R.RecordError as e:
            return 1, lines + [f"FAIL  {e}", f"        fix: {e.fix}"]
    lines.append(f"wrote  {store} (r{rev}, by new)")

    apps = os.path.join(root, "applications")
    readme = os.path.join(apps, "README.md")
    if not os.path.exists(readme):
        os.makedirs(apps, exist_ok=True)
        with open(readme, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(APPLICATIONS_README)
        lines.append(f"wrote  {readme}")
    lines.append(gitattributes(root))

    lines.append("")
    lines.append("Next: a changeset adding k:person - j:fullName, an email and a phone - and")
    lines.append("`jsk kb apply` it. Without an email and a phone the parse gate fails, so")
    lines.append("nothing sendable renders. `jsk kb view` reads the record back.")
    return 0, lines


def main(argv=None):
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
        print("usage: jsk new <path> --name \"Their Name\"")
        return 2
    if not name or not name.strip():
        print("--name is required")
        print("fix:  the record's header says whose career it is, and a record that")
        print("      cannot say whose it is renders nothing sendable")
        return 2

    code, lines = scaffold(argv[0], name.strip(), force=force)
    utf8_stdout()
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
