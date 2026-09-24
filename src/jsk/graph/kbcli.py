"""jsk kb - the career record: changed through changesets, read by id.

Usage: jsk kb <verb> [arguments] [--root DIR]

  apply <changeset.trig> [--dry-run]   merge a changeset into career/kb.ttl; prints the diff

--root is the workspace, the folder holding career/; by default the nearest one above
the current directory. `jsk kb <verb> --help` says more about one verb.

Every write goes through the same gate: the workspace validates, kb.ttl is exactly what
the log last recorded (a hand edit is adopted first, so it is logged as one), and the
record it would write validates too. Then kb.ttl, then log.ttl, and the diff.

Exit 0 done (or nothing to do), 1 refused, 2 called wrong.
"""
import datetime
import difflib
import inspect
import os
import sys

from ..cliutil import docstring_usage, wants_help

VERBS = {}


def verb(fn):
    VERBS[fn.__name__.removeprefix("cmd_")] = fn
    return fn


def find_root(start):
    """The nearest folder at or above `start` holding career/kb.ttl, or None."""
    here = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(here, "career", "kb.ttl")):
            return here
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up


def take(args, flag, value=False):
    """Remove `flag` (and its value) from args; the value, True, or None."""
    if flag not in args:
        return None
    at = args.index(flag)
    if not value:
        del args[at]
        return True
    if at + 1 >= len(args):
        raise SystemExit(usage(f"{flag} needs a value"))
    found = args[at + 1]
    del args[at:at + 2]
    return found


def usage(message):
    print(message)
    print("usage: jsk kb <verb> [arguments] [--root DIR] - `jsk kb --help` lists the verbs")
    return 2


def refuse(lines, fix=None):
    """Print why nothing was written. Returns the exit code."""
    for line in lines:
        print(f"REFUSED  {line}")
    if fix:
        print(f"        fix: {fix}")
    print("nothing was written")
    return 1


def show_findings(findings, title):
    from ..gates.validate_urs import show
    from . import store as S

    rep = S.Store("", findings=findings).report()
    print(title)
    show(rep.fails, "FAIL", 25)


GUIDE = {
    "unlogged": ("career/kb.ttl has no log yet", "run `jsk kb adopt` to start log.ttl from it"),
    "hand-edited": (None, "run `jsk kb adopt` first, so the hand edit is logged as one"),
    "torn": (None, "run `jsk kb adopt`: it logs the write that did not reach log.ttl"),
    "out-of-sync": (None, "restore the file that went back on its own, or `jsk kb adopt`"),
    "missing": ("there is no career/kb.ttl", "run `jsk migrate` or `jsk new`"),
    "unreadable": ("career/kb.ttl or career/log.ttl does not parse", "`jsk kb check` shows where"),
}


def writable(store, allow=("clean",)):
    """None when the record may be written; otherwise the exit code of a refusal."""
    from . import record as R
    from .writer import write

    blocking = [f for f in store.fails() if f.rule not in ("log-sync",)
                and (not f.file.startswith("applications/") or f.rule == "syntax")]
    if blocking:
        show_findings(blocking, f"REFUSED  the career has {len(blocking)} failures - fix them first:")
        print("nothing was written")
        return 1
    st = R.state(store)
    if st.kind not in allow:
        message, fix = GUIDE[st.kind]
        return refuse([message or st.detail], fix)
    if st.kind == "clean" and write(store.graph(R.KB), "kb") != store.parsed[R.KB].text:
        return refuse(["career/kb.ttl is not in the canonical layout this jsk writes"],
                      "run `jsk kb fmt` - a reformat is logged on its own, so no change hides in it")
    return None


def key(f):
    return (f.rule, f.file, f.focus, f.detail)


def new_failures(before, after):
    """What a write would break: any FAIL in the career or the vocabulary, and a FAIL
    anywhere that was not already there - an old application's fault is not this one's."""
    had = {key(f) for f in before.fails()}
    return [f for f in after.fails() if not f.file.startswith("applications/") or key(f) not in had]


def diff(old, new, name="career/kb.ttl"):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        f"a/{name}", f"b/{name}"))


def curies(iris):
    from .writer import curie
    return ", ".join(curie(i) for i in sorted(iris))


def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None,
                 content=True, dry_run=False, notes=()):
    """Stamp, validate, print and - unless a dry run - write. Returns the exit code."""
    from . import record as R
    from . import store as S
    from .io import parse_text

    today = datetime.date.today()
    rev, kb_text, log_text = R.prepare(store, quads, today, by, summary, touched, minted,
                                       answer, content)
    # gofmt's promise, checked every time: what was written parses back to what was meant.
    if set(parse_text(kb_text, R.KB).quads) != set(R.stamp(quads, rev, today, content)):
        return refuse(["the writer did not reproduce the record it was given - a jsk bug"],
                      "report it; kb.ttl is untouched")
    after = S.load(root, texts={R.KB: kb_text, R.LOG: log_text})
    broken = new_failures(store, after)
    if broken:
        show_findings(broken, f"REFUSED  the change would leave {len(broken)} failures:")
        print("nothing was written")
        return 1
    print(diff(store.parsed[R.KB].text, kb_text), end="")
    for label, ids in (("minted", minted), ("touched", touched)):
        if ids:
            print(f"{label:8} {curies(ids)}")
    for note in notes:
        print(f"note     {note}")
    if dry_run:
        print(f"dry run: r{rev} not written")
        return 0
    try:
        R.commit(root, kb_text, log_text)
    except R.RecordError as e:
        print(f"FAIL  {e}\n        fix: {e.fix}")
        return 1
    print(f"r{rev} written: career/kb.ttl and career/log.ttl")
    return 0


@verb
def cmd_apply(args, root):
    """jsk kb apply <changeset.trig> [--dry-run]

    Merges a changeset (op:add, op:set, op:retire, op:delete; see docs/SCRIPTS.md) into
    career/kb.ttl, then logs it. A changed claim drops to j:inferred and is asked about; a
    new bullet gets its id; a sent metric version gets a successor instead of a change.
    --dry-run prints the diff and writes nothing.
    """
    from . import changeset, edit
    from . import store as S
    from .io import GraphError

    dry = bool(take(args, "--dry-run"))
    if len(args) != 1:
        return usage("jsk kb apply takes one changeset")
    path = args[0]
    if path == "-":
        return usage("a changeset is a file: write it to changes.trig and pass that path - "
                     "stdin is refused, because a pipe that never closes hangs the command")
    if not path.endswith(".trig") or not os.path.isfile(path):
        return usage(f"{path}: not a .trig file")
    store = S.load(root)
    code = writable(store)
    if code is not None:
        return code
    try:
        with open(path, encoding="utf-8") as fh:
            cs = changeset.read(fh.read(), os.path.basename(path))
        e = edit.apply(store, cs, datetime.date.today())
    except GraphError as err:
        return refuse([str(err)], err.fix)
    except changeset.Refused as err:
        return refuse([r.text() for r in err.refusals])
    if not e.touched and not e.minted:
        print("nothing to change: the record already says all of that")
        return 0
    summary = cs.summary or (f"Applied {os.path.basename(path)}: {len(e.minted)} added, "
                             f"{len(e.touched)} changed.")
    return write_logged(store, root, e.quads, "apply", summary, e.touched, e.minted,
                        dry_run=dry, notes=e.notes)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (wants_help(args) and args[0] not in VERBS):
        print(docstring_usage(__doc__))
        return 0 if args else 2
    name, rest = args[0], args[1:]
    if name not in VERBS:
        return usage(f"unknown verb: {name} - one of {', '.join(VERBS)}")
    if wants_help(rest):
        print(inspect.cleandoc(VERBS[name].__doc__))
        return 0
    try:
        root = take(rest, "--root", value=True) or find_root(os.getcwd())
    except SystemExit as e:
        return e.code
    if root is None or not os.path.isdir(root):
        return usage("no workspace here: run it inside one, or pass --root DIR "
                     "(the folder holding career/)")
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk kb needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    try:
        return VERBS[name](rest, os.path.abspath(root))
    except SystemExit as e:
        return e.code


if __name__ == "__main__":
    sys.exit(main())
