"""Freezing an application: the directory renamed to the day it was sent, its record written.

mode-ship.md's "Freeze the application", which was three edits and a rename made by hand:
the directory renamed to the day it was sent, the archive written, and nothing in the
directory edited again. This does the first two and refuses whenever the third is already
true or the documents would not survive their gates. It writes the application's record -
what was sent, and the bullets and metric versions it carried - and later events go in with
the app_event tool (jsk mcp). An application's record is the selection the store holds (Ruling 11 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md), hashed as Ruling 7 says
(P5, 2026-10-02). An application made from files was frozen from its resume.json until 6.0,
which freezes none (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2): it is
refused with Ruling 5's fix, the release that still finishes one or `jsk app drop`. One
frozen before then stays as it was.

Four steps, each the adapter's to call in turn: check (the record it would freeze), plan
(the documents and the name), gate (every document through a gate) and write (inside the
record's turn). It prints nothing: adapters/cli/freeze.py says what each step did.
"""
import os
import re
from dataclasses import dataclass

from ...domain.record.state import RecordError, Written
from ...domain.resume.short import ShortError

APPLICATION = "application.md"
WORKING_FILES = ("gaps.txt", "decisions.txt")
# The plain text a render wrote before Ruling 23 of the graph-native plan: not a letter, and
# no longer a document. Named with --doc it is still listed, and the letter gate reads it.
RETIRED_TEXT = "_resume_ats.txt"
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


class FreezeRefused(Exception):
    """A freeze that stopped with nothing renamed or written.

    `lines` is what it says: the reason first, then what to do about it.
    """

    def __init__(self, *lines):
        super().__init__(lines[0])
        self.lines = lines


class FreezeLanded(Exception):
    """The application's record was written and the store failed after it.

    The folder keeps its new name, since its graphs are there under it. `fix` is the
    store's.
    """

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


@dataclass(frozen=True)
class Checked:
    """The application's record, as check() read it and the builder planned it: its stored
    selection."""

    record: str                 # the selection's ref
    record_bytes: bytes         # what the record's hash pins: canonical()'s text
    plan: dict                  # the builder's plan: its `sent` names the bullets rendered


@dataclass(frozen=True)
class FreezePlan:
    """What a freeze will gate and write: the documents sent and the folder's final name."""

    app_dir: str
    record: str
    record_bytes: bytes
    plan: dict
    documents: tuple            # the documents sent, by name
    sent: tuple                 # their paths, and each one's .tex beside it
    final: str                  # the folder's path once renamed; app_dir when it is not


@dataclass(frozen=True)
class Gated:
    """Every gate's result, the render gate last, and the refusal when one failed."""

    results: list
    refusal: tuple | None


@dataclass(frozen=True)
class FreezeResult:
    """What a freeze wrote."""

    written: str                # the application graph's name
    app_dir: str
    final: str


def check(app_dir, *, record, build):
    """The application's record, read and planned, when the application can be frozen.

    Args:
        app_dir: the application directory.
        record: the application's record graphs (adapters/cli/freeze.py's Applications):
            `frozen`, `has_record`, and `selection` - None for an application made from
            files, else (its ref, its stored selection or None).
        build: the builder over a ref, returning (plan, anything).

    Returns:
        A Checked. Reads the stored selection and the store.

    Raises:
        FreezeRefused: frozen already, no posting, an application made from files, or a
            graph-native application with no selection stored or one that will not build.
    """
    # Frozen is what the record says: its application graph. An application.md is one
    # frozen before the career was a graph, and is as frozen as one.
    held = record.frozen(app_dir)
    if held:
        later = ("It was frozen as Markdown before the career was a graph."
                 if held.endswith(APPLICATION) else "Later events are the app_event tool (jsk mcp), one each.")
        raise FreezeRefused(f"{held} already exists. A frozen application is never re-frozen.",
                            later)

    # company and title live in the posting; timeline.freeze() reads and checks it.
    stem = os.path.basename(os.path.abspath(app_dir))
    if not record.has_record(app_dir, "posting"):
        raise FreezeRefused(f"no posting in {app_dir}",
                            "the application's record names the posting it answered: the "
                            f"`posting_capture` tool (`jsk mcp`) stores its advert for {stem}.")

    native = record.selection(app_dir)
    if native is None:
        from .unsent import note

        raise FreezeRefused(f"applications/{stem} was made from files, and jsk 6.0 no longer "
                            "freezes such an application",
                            f"fix: {note(stem)[1]}", "nothing was renamed or written.")
    return selected(app_dir, native, build)


def selected(app_dir, native, build):
    """A graph-native application's record: its stored selection, read and planned.

    Ruling 11 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: such
    an application keeps no resume.json, and one beside it is never read. What the hash pins
    is the selection as `canonical` writes it (Ruling 7), and what was sent is the plan built
    from the selection through its ref, as the record gate and the render build it.

    Args:
        app_dir: the application directory.
        native: (the target's ref, the selection as resume.json's dict, or None when the
            application stores none) - Applications.selection.
        build: the builder over a record path or a ref, returning (plan, anything).

    Returns:
        A Checked whose `record` is the ref.

    Raises:
        FreezeRefused: no selection stored, or one that will not build.
    """
    from ...domain.resume.selection import canonical

    ref, doc = native
    if doc is None:
        stem = os.path.basename(os.path.abspath(app_dir))
        raise FreezeRefused(f"no resume stored for {stem}",
                            f"fix: the `resume_select` tool (`jsk mcp`) chooses one for {stem}, "
                            f"and `jsk resume ship {stem}` renders it.",
                            "nothing was renamed or written.")
    try:
        plan, _ = build(ref)
    except ShortError as exc:
        raise FreezeRefused(str(exc), f"fix: {exc.fix}",
                            "nothing was renamed or written.") from None
    return Checked(ref, canonical(doc).encode("utf-8"), plan)


def plan(app_dir, submitted, named, checked, *, spelled):
    """The documents a freeze lists and the name the folder takes.

    Args:
        app_dir: the application directory.
        submitted: the day it was sent, YYYY-MM-DD, or "false" for one held back.
        named: the --doc paths, or None to list the directory's documents.
        checked: what check() returned.
        spelled: (folder, name) -> the name as the folder spells it on disk.

    Returns:
        A FreezePlan. Lists the directory.

    Raises:
        FreezeRefused: a named document that is not there, two PDFs and none named, no
            document at all, or a dated name another application already has.
    """
    if named:
        documents = []
        # `name`, not `doc`: that name once held the record, which timeline.freeze()
        # read below, and a graph freeze given --doc raised AttributeError on the last
        # --doc path instead of writing the application's record.
        for given in named:
            name = os.path.basename(given)
            if not os.path.isfile(os.path.join(app_dir, name)):
                raise FreezeRefused(f"--doc {given}: no {name} in {app_dir}",
                                    "a frozen application lists what is in it.")
            documents.append(name)
    else:
        # gaps.txt and decisions.txt are the tailoring run's working files, not documents
        # anyone was sent: listed, the letter gate read them as letters and failed them.
        # The documents are the PDFs and the letters: a render writes no .txt any more, so
        # a .txt here is a letter - except the plain text an earlier render left behind.
        documents = sorted(name for name in os.listdir(app_dir)
                           if name.lower().endswith((".pdf", ".txt"))
                           and name.lower() not in WORKING_FILES
                           and not name.lower().endswith(RETIRED_TEXT)
                           and os.path.isfile(os.path.join(app_dir, name)))
        pdfs = [d for d in documents if d.lower().endswith(".pdf")]
        if len(pdfs) > 1:
            # Two renders in one directory, and only the person knows which was sent.
            # Listing both would archive a document nobody submitted as though it was.
            raise FreezeRefused(f"{len(pdfs)} PDFs in {app_dir}: {', '.join(pdfs)}",
                                "name the documents that were sent with --doc.")
    if not documents:
        raise FreezeRefused(f"no .pdf or .txt in {app_dir}",
                            "there is nothing here that could have been sent.")
    # What was sent, and the .tex each was compiled from - the prose gate reads that.
    sent = [os.path.join(app_dir, d) for d in documents]
    sent += [os.path.splitext(p)[0] + ".tex" for p in sent
             if os.path.isfile(os.path.splitext(p)[0] + ".tex")]
    return FreezePlan(app_dir, checked.record, checked.record_bytes, checked.plan,
                      tuple(documents), tuple(sent), final_name(app_dir, submitted, spelled))


def final_name(app_dir, submitted, spelled):
    """The folder's path once it is renamed to the day it was sent.

    Args:
        app_dir: the application directory.
        submitted: YYYY-MM-DD, or "false", which renames nothing.
        spelled: (folder, name) -> the name as the folder spells it on disk.

    Returns:
        The new path, or `app_dir` when the name already carries that day or nothing was
        sent.

    Raises:
        FreezeRefused: the new name is another folder's already.
    """
    if submitted == "false":
        return app_dir
    parent = os.path.dirname(os.path.abspath(app_dir))
    # As the folder is spelled on disk, not as typed: the renamed folder keeps its case.
    base = spelled(parent, os.path.basename(os.path.abspath(app_dir)))
    dated = DATED.match(base)
    rest = dated.group(2) if dated else base
    if dated and dated.group(1) == submitted:
        return app_dir
    final = os.path.join(parent, f"{submitted}-{rest}")
    if os.path.exists(final):
        raise FreezeRefused(f"cannot rename to {final}: it already exists",
                            "two applications sent the same day to the same role - "
                            "name one apart.")
    return final


def key(path):
    """`path` as two spellings of one file compare equal."""
    return os.path.normcase(os.path.abspath(path))


def gate(planned, gates):
    """Every document the freeze lists through a gate; a failing one is never frozen.

    Last before the write, and in process: the most expensive check and the one the rest
    were getting the arguments for.

    Args:
        planned: the FreezePlan.
        gates: runs the gates (adapters/cli/freeze.py binds jsk.cli's): `run(dir, record,
            only)` the results over the render, `read(dir, only)` the paths those read,
            `letter(path, record, name)` the letter gate's result, `failed(results)`.

    Returns:
        A Gated: the results, a letter's before the render gate, and the refusal when a
        gate failed or a document went unread.
    """
    results = gates.run(planned.app_dir, planned.record, list(planned.sent))
    # The gates above read `*_Resume*` renders and nothing else, while `documents` is
    # whatever was sent. A cover letter beside the resume was archived as sent with no
    # gate having opened it (Ruling 5, 2026-09-28). What they read is asked of
    # rendered_documents(), the function that chose it, so the two lists cannot drift.
    read = {key(p) for p in gates.read(planned.app_dir, list(planned.sent))}
    letters, lettered = [], set()
    for name in planned.documents:
        path = os.path.join(planned.app_dir, name)
        if name.lower().endswith((".txt", ".md")) and key(path) not in read:
            # Against the application's own resume.json: the letter's numbers are the
            # resume's claims in a looser paragraph, and are traced the same way.
            letters.append(gates.letter(path, planned.record, name))
            read.add(key(path))
            lettered.add(os.path.normcase(os.path.splitext(name)[0]))
    results[-1:-1] = letters                        # the render gate stays last
    if gates.failed(results):
        return Gated(results, (
            "a gate above did not pass. A failing document is never frozen -",
            "an archive of something that was not sendable reads, later, as though it was."))
    # Anything still unread - a PDF cover letter, say - is refused. A PDF letter is read
    # through its .txt: the letter gate reads text only, and a .txt of the same name
    # beside it is the one extra file Ruling 5 accepts as the price of checking it.
    unread = [name for name in planned.documents
              if key(os.path.join(planned.app_dir, name)) not in read
              and not (name.lower().endswith(".pdf")
                       and os.path.normcase(os.path.splitext(name)[0]) in lettered)]
    if unread:
        return Gated(results, (
            f"no gate read {', '.join(unread)}. A document freeze lists is one a gate has "
            f"checked -",
            "fix: send the letter's .txt beside it, or leave it out with --doc.",
            "nothing was renamed or written."))
    return Gated(results, None)


def write(workspace, planned, submitted, channel, *, record, files, store_errors=()):
    """Validate the application's record, rename the directory, write the record.

    Runs inside the record's turn, which the caller holds: what record.freeze validates is
    what it writes over.

    Args:
        workspace: the workspace root.
        planned: the FreezePlan, gated.
        submitted: YYYY-MM-DD or "false".
        channel: where it was sent.
        record: the application's record graphs (compose.timeline): `freeze` validates the
            application graph and `write_frozen` writes it.
        files: renames the directory (ports.files.ApplicationFiles).
        store_errors: what else the store raises for a write that did not happen.

    Returns:
        A FreezeResult. Renames the directory and writes the store.

    Raises:
        FreezeRefused: the record would not validate, the rename failed, or the store
            refused - each leaving the directory and the record as they were, unless the
            folder could not be renamed back, which the refusal says.
        FreezeLanded: the record was written and the store failed after it; the folder
            keeps its new name.
    """
    app_dir, final = planned.app_dir, planned.final
    sealed, problems = record.freeze(workspace, app_dir, planned.plan, planned.record_bytes,
                                     submitted, channel, list(planned.documents))
    if problems:
        raise FreezeRefused(*problems, "nothing was renamed or written.")
    if final != app_dir:
        try:
            files.rename_directory(app_dir, final)
        except OSError as exc:
            raise FreezeRefused(f"cannot rename {app_dir} to {final}: {exc}",
                                "nothing was written.") from None
    try:
        written = record.write_frozen(workspace, sealed, final)
    except Written as exc:
        # The graphs are in the store under the new name: the folder stays with them.
        raise FreezeLanded(str(exc), exc.fix) from None
    except (RecordError, OSError, *store_errors) as exc:
        # The store refused, so the directory goes back to the name its graphs still have.
        undone = final == app_dir or files.restore_directory(final, app_dir)
        raise FreezeRefused(f"the record was not written: {exc}",
                            f"fix: {getattr(exc, 'fix', 'run the command again')}",
                            "nothing was written" + ("." if undone else
                                                     f", and {final} could not be renamed "
                                                     f"back to {app_dir}.")) from None
    return FreezeResult(written, app_dir, final)
