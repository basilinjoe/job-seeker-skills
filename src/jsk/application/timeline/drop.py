"""An unsent application set aside: its graphs removed from the store, its folder kept under
dropped/.

Ruling 5 of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md first said an unsent
file-made application is dropped by "the career_apply tool (jsk mcp) a changeset retiring its posting". A
changeset writes only the career graph, never an application's, and many such applications
have no posting graph at all, so that fix could not be followed (amended 2026-10-03). This is
the tool the fix names now: app_drop.

Only an application that is not frozen is dropped - made from files or graph-native. A frozen
one, sent or held back, is the archive of what went out, and is refused. The order is the
store first, then the folder: every graph the store holds for the application goes in one
update, validated with the workspace as the other writers validate theirs, and only then is
the folder moved to `<workspace>/dropped/<stem>/` (`-2`, `-3` when that is taken) with a
DROPPED.txt saying when, why and what left the store. A move that fails after the store was
written leaves a folder with no graphs, which running the command again moves: the second
run finds nothing to remove and finishes the first.

It prints nothing: adapters/cli/drop.py says what it did. The clock is read by the adapter
and handed in as `today`.
"""
import os
from dataclasses import dataclass

from ...domain.naming import app_graph
from ...domain.timeline.errors import Unwritable
from .records import MOVED, app_graphs, frozen, write_app_graphs

# The folder beside applications/ a dropped application's files go to: outside
# applications/, so no listing, check or query counts it as an application again.
DROPPED = "dropped"
# The note written into the dropped folder. Upper case so it sorts first and is not taken
# for one of the application's own documents.
NOTE = "DROPPED.txt"


class NotAnApplication(Exception):
    """The path names no application: no folder under applications/ and no graph in the store,
    or no workspace at all. A call made wrongly; carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


class DropRefused(Exception):
    """A drop that did not happen, with nothing written or moved. Carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


class DropLanded(Exception):
    """The graphs left the store, and setting the folder aside failed after. Carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


@dataclass(frozen=True)
class Dropped:
    """One application dropped, or what a dry run would drop."""

    rel: str                    # applications/<stem>, as the store names it
    removed: tuple              # the graph names removed from the store, in RECORD's order
    folder: str | None          # the application's folder, absolute, or None with no folder
    to: str                     # where its files go: <workspace>/dropped/<name>, absolute
    note: str | None            # DROPPED.txt's path once written; None on a dry run
    dry_run: bool


def note_text(rel, removed, today, reason, folder):
    """DROPPED.txt's text: the day, the reason, and what left the store.

    Args:
        rel: the application as the store named it, `applications/<stem>`.
        removed: the graph names removed.
        today: the date the drop ran on.
        reason: --reason's text, or None.
        folder: whether the application had a folder that was moved here.
    """
    lines = [f"dropped   {today.isoformat()}",
             f"reason    {reason.strip() if reason and reason.strip() else 'none given'}",
             f"was       {rel}/" + ("" if folder else " (no folder; this note is all there is)"),
             ""]
    if removed:
        lines.append("removed from career/store/:")
        lines += [f"  {name}" for name in removed]
    else:
        lines.append("removed from career/store/: nothing - it held no graph for this application")
    lines += ["", "Set aside by the app_drop tool: it was never frozen, so nothing here was sent."]
    if folder:
        lines += ["The files are as they were. The graphs above are gone from the store: moving",
                  "this folder back to applications/ brings back the files, not the graphs."]
    else:
        # Until 2026-10-04 this case read "The files are as they were... moving this folder
        # back", of a folder there never was (the P3 review).
        lines += ["It had no folder, so no file was moved. The graphs above are gone from the",
                  "store, and nothing here brings them back."]
    lines.append("")
    return "\n".join(lines)


def drop(app_dir, *, reason, today, dry_run, load, records, files, store_errors=()):
    """The Dropped result of setting `app_dir` aside, or of a dry run of it.

    Runs inside the record's turn, which the caller holds (none on a dry run): what is
    validated is what is written over.

    Args:
        app_dir: the application's directory, `<workspace>/applications/<stem>`; it need not
            exist when the store holds graphs for it.
        reason: why, for DROPPED.txt, or None.
        today: the date the call runs on, read once at the edge.
        dry_run: say what would be removed and moved, and write nothing.
        load: root, graphs= -> the loaded workspace (compose.record.load).
        records: the folder and the store (ports.applications.ApplicationRecords).
        files: the folder moved and the note written (ports.files.ApplicationFiles).
        store_errors: what else the store raises for a write that did not happen.

    Returns:
        The Dropped result. Removes the graphs, moves the folder and writes DROPPED.txt,
        unless `dry_run`.

    Raises:
        NotAnApplication: no workspace with a store, or nothing there for this path.
        DropRefused: frozen, or the workspace would not validate without the graphs, or
            the store refused - nothing written or moved.
        DropLanded: the graphs were removed and the folder could not be set aside.
    """
    store, plan = planned(app_dir, load=load, records=records, files=files)
    if dry_run:
        return plan
    rel, removed, folder, to = plan.rel, plan.removed, plan.folder, plan.to
    if removed:
        try:
            write_app_graphs(app_dir, dict.fromkeys(name.rsplit("/", 1)[1] for name in removed),
                             store, records=records)
        except Unwritable as e:
            raise DropRefused(str(e), e.fix) from None
        except store_errors as e:
            raise DropRefused(f"{rel}: not written - {e}", "run the command again") from None
    again = f'call the app_drop tool again, app_drop(app="{rel}") - it moves what is left'
    if folder:
        try:
            files.move_directory(folder, to)
        except OSError as e:
            raise DropLanded(f"{rel}: its graphs left the store, and the folder could not be "
                             f"moved to {to}: {e}", "close whatever holds the folder and "
                             + again) from None
    note = os.path.join(to, NOTE)
    try:
        files.write_new(to, note, note_text(rel, removed, today, reason, bool(folder)))
    except OSError as e:
        raise DropLanded(f"{rel}: set aside in {to}, and {NOTE} could not be written: {e}",
                         "the drop is done; the note is the only thing missing") from None
    return Dropped(rel, removed, folder, to, note, False)


def planned(app_dir, *, load, records, files):
    """(the workspace as loaded, the Dropped a dry run reports): every check made, nothing
    written.

    Args:
        app_dir: the application's directory.
        load, records, files: as drop() takes them.

    Raises:
        NotAnApplication, DropRefused: as drop() says.
    """
    from ...domain.record.state import new_failures

    root, rel = records.workspace_of_app(app_dir)
    if root is None or rel is None or not records.has_store(root):
        raise NotAnApplication(f"{app_dir} is not an application in a workspace",
                               "pass applications/<stem>, in the applications/ folder beside "
                               "career/store/")
    store = load(root)
    held = frozen(app_dir, store, records=records)
    if held:
        raise DropRefused(f"{rel} is frozen ({held}): a frozen application is an archive of "
                          "what went out, sent or held back, and is never dropped",
                          "record what became of it instead: the app_event tool (jsk mcp), "
                          f'app_event(app="{rel}", kind="withdrawn", date=<YYYY-MM-DD>)')
    graphs = app_graphs(app_dir, store, records=records)
    kinds = [kind for kind in MOVED if kind in graphs]
    folder = os.path.abspath(app_dir)
    has_folder = files.is_dir(folder)
    if not kinds and not has_folder:
        raise NotAnApplication(f"{rel} is no application: no folder, and no graph for it in "
                               "career/store/",
                               "the career_query tool (jsk mcp) and the app_list tool name the "
                               "applications there are")
    removed = tuple(app_graph(rel, kind) for kind in kinds)
    if kinds:
        after = load(root, graphs=dict.fromkeys(removed))
        broken = new_failures(store, after)
        if broken:
            raise DropRefused(f"{rel}: the workspace would not validate without its graphs - "
                              + "; ".join(f.text() for f in broken),
                              "correct what it names, then run the command again")
    aside = os.path.join(root, DROPPED)
    to = os.path.join(aside, files.free_directory(aside, rel.split("/", 1)[1]))
    return store, Dropped(rel, removed, folder if has_folder else None, to, None, True)
