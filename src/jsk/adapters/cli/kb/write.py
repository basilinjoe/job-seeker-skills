"""`jsk kb apply`, and the logged write every writing verb prints through
(application/record/write.py's WriteLogged)."""
import os

from ..presenters import refuse, show_findings, unclean, unwritten, usage


def refused(err):
    """Print a refusal raised by a record use case (application/record/refusals.py).

    Args:
        err: Refused, Problems, Failing or Unclean.

    Returns:
        1, the exit code of a refusal.
    """
    from ....application.record.refusals import Failing, Problems, Unclean
    from ..presenters import refuse_each

    if isinstance(err, Failing):
        show_findings(err.findings, err.title)
        if err.written:
            print("nothing was written")
        return 1
    if isinstance(err, Unclean):
        return unclean(err.state)
    if isinstance(err, Problems):
        return refuse_each(err.problems)
    return refuse(err.lines, err.fix)


def writable(store):
    """None when the record may be written; otherwise the exit code of its refusal,
    printed."""
    from ....application.record import write as W
    from ....application.record.refusals import Failing, Unclean
    from ....infra.oxigraph import record as R

    try:
        W.writable(store, R.state)
    except (Failing, Unclean) as err:
        return refused(err)
    return None


def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None,
                 dry_run=False, notes=(), *, today):
    """Stamp, validate, print and - unless a dry run - write. Returns the exit code.

    The command already holds its turn (main takes it), so `store` is the record as it
    stands, and nothing lands between this validating the candidate and writing it."""
    from ....application.record.refusals import Failing, Refused
    from ....application.record.write import WriteLogged
    from ....domain.record.state import RecordError
    from ....domain.record.writer import curies
    from ..compose.record import load
    from ....infra.oxigraph import record as R

    gate = WriteLogged(root, load=load, record=R)
    try:
        c = gate.candidate(store, quads, by, summary, today, touched, minted, answer, notes)
    except (Failing, Refused) as err:
        return refused(err)
    print(c.diff, end="")
    for label, ids in (("minted", c.minted), ("touched", c.touched)):
        if ids:
            print(f"{label:8} {curies(ids)}")
    for note in c.notes:
        print(f"note     {note}")
    if dry_run:
        print(f"dry run: r{c.revision} not written")
        return 0
    try:
        gate.write(c)
    except RecordError as e:
        return unwritten(e)
    print(f"r{c.revision} written: career/store/")
    return 0


def changeset_text(path):
    """A changeset file's text. UTF-8, with or without a byte-order mark - and UTF-16 when a
    byte-order mark says so, because that is what Windows PowerShell 5.1's `>` and Out-File
    write. Anything else raises UnicodeDecodeError: guessing an encoding would guess words."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def cmd_apply(args, flags, root, today):
    """jsk kb apply <changeset.trig> [--dry-run]

    Merges a changeset (op:add, op:set, op:retire, op:delete; see docs/SCRIPTS.md) into
    the career, then logs it. A changed claim drops to j:inferred and is asked about; a
    new bullet gets its id; a sent metric version gets a successor instead of a change.
    --dry-run prints the diff and writes nothing.
    """
    from ....application.record.refusals import Problems, Refused
    from ....application.record.write import apply
    from ..compose.record import load, read_changeset
    from ..presenters import refuse_each

    if len(args) != 1:
        return usage("jsk kb apply takes one changeset")
    path = args[0]
    if path == "-":
        return usage("a changeset is a file: write it to changes.trig and pass that path - "
                     "stdin is refused, because a pipe that never closes hangs the command")
    if not path.endswith(".trig") or not os.path.isfile(path):
        return usage(f"{path}: not a .trig file")
    store = load(root)
    code = writable(store)
    if code is not None:
        return code
    try:
        text = changeset_text(path)
    except UnicodeDecodeError as err:
        return refuse([f"{path} is not UTF-8 ({err.reason} at byte {err.start})"],
                      "save it as UTF-8 - in PowerShell, `Set-Content -Encoding utf8`")
    try:
        applied = apply(store, text, os.path.basename(path), today,
                        read_changeset=read_changeset)
    except Refused as err:
        return refuse(err.lines, err.fix)
    except Problems as err:
        return refuse_each(err.problems)
    if applied is None:
        print("nothing to change: the record already says all of that")
        return 0
    return write_logged(store, root, applied.quads, "apply", applied.summary, applied.touched,
                        applied.minted, dry_run="--dry-run" in flags, notes=applied.notes,
                        today=today)
