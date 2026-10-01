"""A short resume.json loaded: read, its workspace found, the career loaded, both checked.

Loaded once, so a render building two variants reads the career once. Where the file's
text comes from, how a workspace is found and how a career is loaded are the caller's to
give; resume/short.py and resume/build.py bind the real ones.
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


def load_resume(path, *, files, find_root, load_store):
    """The resume.json at `path` and the career it is built from, checked.

    Args:
        path: the resume.json.
        files: reads it (ports.files.TextFiles).
        find_root: finds its workspace (infra.files.find_root).
        load_store: loads that workspace (compose.record.load).

    Returns:
        A LoadedResume. Reads the file and the career.

    Raises:
        ShortError: a file that cannot be read, sits outside a workspace, or fails its
            shape or id checks.
    """
    doc = read_short(path, files)
    root = workspace_of(path, find_root)
    store = career_of(root, load_store)
    fails = shape(doc) or ids(doc, store)
    if fails:
        raise ShortError(f"{path}: " + "; ".join(fails),
                         "`jsk resume check` it and fix what it names")
    return LoadedResume(store, doc, root)
