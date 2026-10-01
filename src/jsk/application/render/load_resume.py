"""A short resume.json loaded: read, its workspace found, the career loaded, both checked.

Loaded once, so a render building two variants reads the career once. Where the file's
text comes from, how a workspace is found and how a career is loaded are the caller's to
give; adapters/cli/compose/resume.py binds the real ones.

A graph-native target comes as its ref (application/render/selection.py): the dict is
then its selection graph's, read from the career just loaded, and the checks are the
same. A resume.json inside a graph-native application is refused, naming the tool that
changes its selection (Ruling 11 of docs/superpowers/plans/
2026-10-01-graph-native-applications-mcp.md); a legacy one reads as it always has.
"""
import os
from dataclasses import dataclass

from ...domain.record.parsed import GraphError, Missing, Unreadable
from ...domain.resume.short import ShortError, ids, parse, shape


@dataclass(frozen=True)
class LoadedResume:
    """A resume.json that passed its checks, with the career it is built from."""

    store: object          # the loaded workspace (domain.record.store.Store)
    doc: dict
    root: str


def read_short(path, files):
    """The resume.json at `path`, as a dict.

    Args:
        path: the file.
        files: reads it (ports.files.TextFiles).

    Returns:
        The dict. Reads the file.

    Raises:
        ShortError: the file is missing, unreadable, or not a version-2 resume.json.
    """
    try:
        text = files.read_text(path)
    except Missing:
        raise ShortError(f"{path}: no such file", "pass the application's resume.json") from None
    except Unreadable as err:
        # An editor's cp1252 save: the bytes are the fault, not the JSON.
        raise ShortError(str(err), err.fix) from None
    return parse(text, path)


def workspace_of(path, find_root):
    """The workspace root above the file. Walked up, never worked out: the real one is
    the folder holding career/store/.

    Args:
        path: the resume.json.
        find_root: the nearest workspace at or above a folder, or None (infra.files).

    Returns:
        The root.

    Raises:
        ShortError: the file is not inside a workspace.
    """
    root = find_root(os.path.dirname(os.path.abspath(path)))
    if root is None:
        raise ShortError(f"{path} is not inside a workspace",
                         "keep resume.json under the folder holding career/store/ - "
                         "the resume is built from the career in it")
    return root


def career_of(root, load_store):
    """The workspace at `root`, loaded.

    Args:
        root: the workspace root.
        load_store: loads it (compose.record.load).

    Returns:
        The loaded store.

    Raises:
        ShortError: a store that will not open, with its fix - never a traceback.
    """
    try:
        return load_store(root)
    except GraphError as e:
        raise ShortError(str(e), e.fix) from None


def selected_doc(path, store, root, selections):
    """The selection a target's ref names, as resume.json's dict.

    Args:
        path: the ref.
        store: its workspace, loaded.
        root: that workspace's root.
        selections: the selection's bound ports (compose.selection.Ports).

    Raises:
        ShortError: no selection, a legacy application or one with no posting - its fix
            the tool or verb that answers it.
    """
    from ...domain.posting.errors import Refused
    from .selection import doc_in, parse_ref

    try:
        return doc_in(store, root, (parse_ref(path) or ("", ""))[1], selections)
    except Refused as e:
        raise ShortError(str(e), (e.fix or "").removeprefix("fix:").strip()) from None


def load_resume(path, *, files, find_root, load_store, selections=None):
    """The resume.json at `path` and the career it is built from, checked.

    Args:
        path: the resume.json, or a target's ref (selection.ref).
        files: reads it (ports.files.TextFiles).
        find_root: finds its workspace (infra.files.find_root).
        load_store: loads that workspace (compose.record.load).
        selections: the selection's bound ports (compose.selection.Ports), which a ref
            needs; None reads only files.

    Returns:
        A LoadedResume. Reads the file, or the selection graph, and the career.

    Raises:
        ShortError: a file that cannot be read, sits outside a workspace, lies inside a
            graph-native application, or fails its shape or id checks; a ref with no
            selection.
    """
    from .selection import file_refusal, parse_ref, target_name

    ref = parse_ref(path) if selections is not None else None
    if ref is not None:
        root = ref[0]
        store = career_of(root, load_store)
        doc = selected_doc(path, store, root, selections)
    else:
        doc = read_short(path, files)
        root = workspace_of(path, find_root)
        store = career_of(root, load_store)
        refused = file_refusal(path, root, store)
        if refused:
            raise ShortError(*refused)
    fails = shape(doc, target_name(path) if ref else None) or ids(doc, store)
    if fails:
        raise ShortError(f"{path}: " + "; ".join(fails),
                         "`jsk resume check` it and fix what it names")
    return LoadedResume(store, doc, root)
