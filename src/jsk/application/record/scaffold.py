"""`jsk kb new`: a career workspace scaffolded - the record, its log, and a place to file
applications - or an existing record started over from the empty one, logged.

It writes through the same gate every `jsk kb` write uses (record.write_graphs), inside
the writer's turn. What holds the record, and the disk the rest is written to, are the
caller's to give; adapters/cli/kb/new.py says what was done.
"""
import os
from dataclasses import dataclass

from ...domain.record.state import KB, LOG, RecordError
from .refusals import Failing, Unclean

STORE = "career/store"

# The store is RocksDB's files, some of them text-like: git's autocrlf must never touch
# them. Whatever else the file already says, this is added.
GITATTRIBUTES = ("career/store/** binary",)

APPLICATIONS_README = """# Applications

One directory per submission, named `<yyyy-mm-dd>-<company>-<role>` - the date being
the day it was sent. Each holds the whole of that application:

| File | Is |
|---|---|
| `posting.md` | the advertisement verbatim, nothing added |
| `resume.json` | the short record this submission rendered from |
| `<Name>_<Company>_Resume.{tex,pdf}` | the PDF actually sent, and the .tex it compiled from |

What the posting asks for, the assessment of the career against it (`jsk tailor match`
prints it), and what was sent - the bullets and metric versions it carried, and every
event since (`jsk app event`) - are kept in the record, career/store/, beside the career.

**Everything in here is frozen at submission.** The career keeps moving; an application
that pointed at a moving record could not answer what it was answering.

An application worked through and then held back is still a real application:
`jsk app freeze <dir> --submitted false`.
"""


class NoEngine(Exception):
    """pyoxigraph is not installed, and the record is a pyoxigraph store."""


class LaidOutAsFiles(Exception):
    """The workspace holds a record still laid out as files, at `path` (its kb.ttl)."""

    def __init__(self, path):
        super().__init__(path)
        self.path = path


class Exists(Exception):
    """A store is there already, at `store`, and --force was not given."""

    def __init__(self, store):
        super().__init__(store)
        self.store = store


class NotKept(Exception):
    """The old record could not be kept at `path`: nothing was written."""

    def __init__(self, path, error):
        super().__init__(f"{path}: {error}")
        self.path = path
        self.error = error


class Unwritten(Exception):
    """The store refused the write (`error`, a RecordError), after the old record was kept
    at `kept` (or None)."""

    def __init__(self, error, kept):
        super().__init__(str(error))
        self.error = error
        self.kept = kept


def header(name):
    """The empty career's header: its format, and whose it is.

    Args:
        name: the person's full name.

    Returns:
        The header's quads.
    """
    import pyoxigraph as ox

    from ...domain import ontology as O

    kb = ox.NamedNode(O.K + "kb")
    return [ox.Quad(kb, ox.NamedNode(O.J + "format"),
                    ox.Literal(str(O.FORMAT), datatype=ox.NamedNode(O.XSD + "integer"))),
            ox.Quad(kb, ox.NamedNode(O.J + "name"), ox.Literal(name))]


def first_write(name, today):
    """{graph: quads} for a workspace with no career yet: the empty record, r1 by `new`.

    Args:
        name: the person's full name.
        today: the day r1 is dated.

    Returns:
        The career and its log.
    """
    from ...domain.record.parsed import sha256
    from ...domain.record.state import entry, stamp
    from ...domain.record.writer import write

    kb = stamp(header(name), 1, today)
    log = entry(1, today, "new", f"Created by jsk kb new for {name}: an empty record.",
                sha256(write(kb, "kb")))
    return {KB: kb, LOG: log}


def kept_name(root, revision):
    """career/kb.r<N>.trig - or kb.r<N>-2.trig, -3... - the first that is not there yet.

    Beside the store, where the person will see it: .jsk/ is a cache that ignores itself,
    and a workspace need not be a git repository. A dump, so `jsk kb load` reads it back.

    Args:
        root: the workspace.
        revision: the old record's last revision.

    Returns:
        The path, relative to the workspace.
    """
    base = f"career/kb.r{revision}"
    rel, n = f"{base}.trig", 2
    while os.path.exists(os.path.join(root, rel)):
        rel, n = f"{base}-{n}.trig", n + 1
    return rel


def restart(root, name, today, *, load, record, db):
    """(graphs, revision, kept, dump text) replacing the career with the empty record, as
    the next revision of the log already there, the whole old record to be kept as a dump
    at `kept`.

    Only a clean record is started over: anything else was written outside jsk, and the
    log could not say what was replaced.

    Args:
        root: the workspace.
        name: the person's full name.
        today: the day the entry is dated.
        load: loads the workspace (compose.record.load).
        record: the write gate (infra.oxigraph.record): state, prepared.
        db: the store on disk (infra.oxigraph.db): read, dump_text.

    Returns:
        The tuple. Reads the record.

    Raises:
        Unclean: the record is not clean. Failing: the empty record would leave an
            application with FAILs.
    """
    store = load(root)
    st = record.state(store)
    if st.kind != "clean":
        raise Unclean(st)
    kept = kept_name(root, st.kb_revision)
    p = record.prepared(store, header(name), today, "new",
                        f"Started over by jsk kb new --force for {name}: the career replaced by the "
                        f"empty record. r{st.kb_revision}, the last of the old record, is kept as "
                        f"{kept}.")
    after = load(root, graphs=p.graphs())
    if after.fails():
        raise Failing(after.fails(), f"REFUSED  starting over would leave {len(after.fails())} "
                                     "failures - an application that carried an entry the "
                                     "empty record does not have:")
    return p.graphs(), p.revision, kept, db.dump_text(db.read(root))


@dataclass(frozen=True)
class Attributes:
    """What became of the workspace's .gitattributes: "kept" (it had every rule), "added"
    (the missing ones appended), "wrote" (it is new), or "left" (it could not be read,
    `error` says why)."""

    path: str
    done: str
    error: object = None


def gitattributes(root, *, files, disk):
    """Add whichever of GITATTRIBUTES the workspace's .gitattributes lacks. Never removes.

    Args:
        root: the workspace.
        files: reads it (infra.files.read_text).
        disk: appends to it.

    Returns:
        Attributes.
    """
    from ...domain.record.parsed import Missing, Unreadable

    path = os.path.join(root, ".gitattributes")
    try:
        have = files.read_text(path, ".gitattributes")
    except Missing:
        have = ""
    except Unreadable as e:
        # The person's own file, and the record is already written: say what to add
        # rather than append to bytes that could not be read.
        return Attributes(path, "left", e)
    lines = {line.strip() for line in have.splitlines()}
    missing = [rule for rule in GITATTRIBUTES if rule not in lines]
    if not missing:
        return Attributes(path, "kept")
    disk.append_text(path, ("\n" if have and not have.endswith("\n") else "")
                     + "\n".join(missing) + "\n")
    return Attributes(path, "added" if have else "wrote")


@dataclass(frozen=True)
class Scaffolded:
    """A workspace written: the store, the revision, the old record kept (or None), the
    applications README written (or None), and the .gitattributes."""

    store: str
    revision: int
    kept: str | None
    readme: str | None
    attributes: Attributes


def written(root, name, force, today, *, load, record, db, legacy, disk):
    """The record written inside the writer's turn: (graphs' revision, kept path or None).

    The turn before the question "is there a store?": two `jsk kb new` at once would both
    find none and both write r1. --force reads the record it replaces, likewise.
    """
    store = os.path.normpath(os.path.join(root, STORE))
    kept = None
    with record.turn(root):
        exists = db.exists(root)
        if not exists and legacy.has_files(root):
            raise LaidOutAsFiles(os.path.normpath(os.path.join(root, "career", "kb.ttl")))
        if exists and not force:
            raise Exists(store)
        if exists:
            graphs, rev, kept, dump = restart(root, name, today, load=load, record=record, db=db)
            kept = os.path.normpath(os.path.join(root, kept))
            try:
                disk.create_text(kept, dump)                            # never overwrites
            except OSError as e:
                raise NotKept(kept, e) from None
        else:
            graphs, rev = first_write(name, today), 1
            disk.makedirs(os.path.join(root, "career"))
        try:
            record.write_graphs(root, graphs, create=not exists)
        except RecordError as e:
            raise Unwritten(e, kept) from None
    return rev, kept


def scaffold(root, name, force, today, *, load, record, db, legacy, files, disk):
    """Write the workspace at `root` for the person called `name`.

    Args:
        root: the workspace folder; career/ goes inside it.
        name: the person's full name, for the record's header.
        force: start an existing record over from the empty one.
        today: the day the log entry is dated.
        load: loads the workspace (compose.record.load).
        record: the write gate (infra.oxigraph.record): turn, state, prepared, write_graphs.
        db: the store on disk (infra.oxigraph.db): exists, read, dump_text.
        legacy: the workspace laid out as files (infra.legacy_import): has_files.
        files: reads a text (infra.files.read_text).
        disk: writes the scaffold's files: create_text, write_text, append_text, makedirs.

    Returns:
        Scaffolded. Writes career/store/, the kept dump, applications/README.md and
        .gitattributes.

    Raises:
        NoEngine, LaidOutAsFiles, Exists, Unclean, Failing, NotKept, Unwritten: nothing
            was written, but for Unwritten after the old record was kept.
    """
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        raise NoEngine() from None
    rev, kept = written(root, name, force, today, load=load, record=record, db=db,
                        legacy=legacy, disk=disk)
    apps = os.path.join(root, "applications")
    readme = os.path.join(apps, "README.md")
    wrote = None
    if not os.path.exists(readme):
        disk.makedirs(apps)
        disk.write_text(readme, APPLICATIONS_README)
        wrote = readme
    return Scaffolded(os.path.normpath(os.path.join(root, STORE)), rev, kept, wrote,
                      gitattributes(root, files=files, disk=disk))
