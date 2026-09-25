#!/usr/bin/env python3
"""Scaffold a career workspace: the graph record, its log, and a place to file applications.

Usage: python3 -m jsk.kb <path> --name "Their Name" [--force]
       <path>     the workspace folder to create; career/ goes inside it
       --name     the person's full name; the record's header says whose it is
       --force    start an existing career/kb.ttl over from the empty record, logged

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = written. Exit 1 = refused, because something was already there, or pyoxigraph
is missing. Exit 2 = called wrongly.

It writes:

  career/kb.ttl     the empty record, in the canonical layout: the header naming the
                    person and every section banner, in the order they are always written
  career/log.ttl    k:rev_1, `j:by j:new`, holding kb.ttl's hash - so the record is clean
                    at r1 and `jsk kb apply` works on it straight away
  applications/     with a README saying what each application directory holds
  .gitattributes    `*.ttl` and `*.trig` kept LF, so a Windows checkout cannot change the
                    hash the log holds

Written through the same writer and the same kb.ttl-then-log.ttl commit every `jsk kb`
write uses: a record that started any other way would first have to be adopted.

The guidance the old Markdown template carried in HTML comments is not in kb.ttl: a
comment is not a triple, and `jsk kb fmt` and `adopt` refuse a file holding one. What each
section holds is the format reference's job, and every write names what it refused.
"""
import datetime
import os
import sys

from .cliutil import docstring_usage, wants_help

KB = "career/kb.ttl"
LOG = "career/log.ttl"
MARKDOWN_KB = "user-knowledgebase.md"

# Both lines, whatever else the file already says. Turtle is text, and git's autocrlf
# would otherwise hand a Windows checkout a kb.ttl whose bytes - and so whose hash - are
# not the ones log.ttl recorded.
GITATTRIBUTES = ("*.ttl text eol=lf", "*.trig text eol=lf")

APPLICATIONS_README = """# Applications

One directory per submission, named `<yyyy-mm-dd>-<company>-<role>` - the date being
the day it was sent. Each holds the whole of that application:

| File | Is |
|---|---|
| `posting.md` | the advertisement verbatim, nothing added |
| `posting.ttl` | what it asks for: each requirement with the advert's own words |
| `gaps.md` | the assessment of the career against it, and the question queue |
| `resume.json` | the URS record this submission rendered from |
| `<Name>_<Company>_Resume.{tex,pdf,txt}` | the files actually sent |
| `application.ttl` | written by `jsk freeze`: what was sent, the bullets and metric versions it carried, and every event since (`jsk event`) |

**Everything in here is frozen at submission.** The career keeps moving; an application
that pointed at a moving record could not answer what it was answering.

An application worked through and then held back is still a real application:
`jsk freeze <dir> --submitted false`.
"""


def empty_record(name, today):
    """The canonical kb.ttl of a career with nothing in it yet, at revision 1."""
    from .graph import record as R
    from .graph.writer import write

    return write(R.stamp(header(name), 1, today), "kb")


def header(name):
    import pyoxigraph as ox

    from .graph import ontology as O

    kb = ox.NamedNode(O.K + "kb")
    return [ox.Quad(kb, ox.NamedNode(O.J + "format"),
                    ox.Literal(str(O.FORMAT), datatype=ox.NamedNode(O.XSD + "integer"))),
            ox.Quad(kb, ox.NamedNode(O.J + "name"), ox.Literal(name))]


def first_write(root, name, today):
    """(kb_text, log_text) for a workspace with no career yet: r1 by `new`."""
    from .graph import record as R
    from .graph.io import sha256
    from .graph.writer import write

    kb_text = empty_record(name, today)
    log = R.entry(1, today, "new", f"Created by jsk new for {name}: an empty record.",
                  sha256(kb_text))
    return kb_text, write(log, "log")


def restart(root, name, today):
    """(kb_text, log_text, revision) replacing an existing kb.ttl with the empty record,
    as the next revision of the log already there - or (None, refusal lines)."""
    import contextlib
    import io

    from .gates.validate_urs import show
    from .graph import record as R
    from .graph import store as S

    store = S.load(root)
    if R.state(store).kind == "unreadable":
        return None, [f"REFUSED  {KB} or {LOG} does not parse, so there is no revision to "
                      "start over from",
                      "        fix: `jsk kb check` shows where; or move career/ aside"]
    rev, kb_text, log_text = R.prepare(
        store, header(name), today, "new",
        f"Started over by jsk new --force for {name}: kb.ttl replaced by the empty record. "
        f"The revision before this one is the last of the old record; git has its text.")
    after = S.load(root, texts={KB: kb_text, LOG: log_text})
    if after.fails():
        lines = [f"REFUSED  starting over would leave {len(after.fails())} failures - an "
                 "application that carried an entry the empty record does not have:"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            show(after.report().fails, "FAIL", 25)
        lines += buf.getvalue().rstrip("\n").splitlines()
        lines.append("        fix: a frozen application keeps its links; move career/ aside "
                     "and start a new workspace instead")
        return None, lines
    return (kb_text, log_text, rev), None


def gitattributes(root):
    """Add whichever of GITATTRIBUTES the workspace's .gitattributes lacks. Never removes."""
    path = os.path.join(root, ".gitattributes")
    have = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            have = fh.read()
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
    kb = os.path.join(root, KB)
    exists = os.path.exists(kb)
    if exists and not force:
        return 1, [f"REFUSED  already exists: {kb}",
                   "        fix: change it with `jsk kb apply`; or --force to start over from "
                   "the empty record (logged, and the old one stays in git)"]
    markdown = os.path.join(root, MARKDOWN_KB)
    if not exists and os.path.exists(markdown) and not force:
        return 1, [f"REFUSED  {markdown} is here: this career is already written down",
                   f"        fix: `jsk migrate {markdown}` moves it to {KB}, checked; "
                   "--force starts an empty record beside it instead"]
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        return 1, ["FAIL  jsk new writes the graph record, and needs pyoxigraph",
                   '      fix: python -m pip install "jsk-resume"   - it is a dependency']

    from .graph import record as R

    lines = []
    if exists:
        done, refusal = restart(root, name, today)
        if refusal:
            return 1, refusal + ["nothing was written"]
        kb_text, log_text, rev = done
    else:
        kb_text, log_text = first_write(root, name, today)
        rev = 1
    os.makedirs(os.path.join(root, "career"), exist_ok=True)
    try:
        R.commit(root, kb_text, log_text)
    except R.RecordError as e:
        return 1, [f"FAIL  {e}", f"        fix: {e.fix}"]
    lines.append(f"wrote  {kb}")
    lines.append(f"wrote  {os.path.join(root, LOG)} (r{rev}, by new)")

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
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # pragma: no cover
        pass
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
