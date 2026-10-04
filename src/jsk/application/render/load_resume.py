"""A target's selection loaded: its workspace's career loaded, the selection read from it, both
checked.

Loaded once, so a render building two variants reads the career once. How a career is
loaded and the selection read are the caller's to give; adapters/cli/compose/resume.py binds
the real ones.

A target - a graph-native application or a general resume - comes as its ref
(application/render/selection.py): the dict is its selection graph's, read from the career
just loaded. A resume.json path was read here too until 6.0, which reads none
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2): anything that is not a ref
is refused, naming the target form, and the dict keeps resume.json's shape only as the
interchange shape short.shape and plan.build take (Ruling 3).
"""
from dataclasses import dataclass

from ...domain.record.parsed import GraphError
from ...domain.resume.short import ShortError, ids, shape


@dataclass(frozen=True)
class LoadedResume:
    """A target's selection that passed its checks, with the career it is built from."""

    store: object          # the loaded workspace (domain.record.store.Store)
    doc: dict
    root: str


def not_a_target(path):
    """The ShortError for a record path that is no target's ref: a resume.json, or any file.

    Args:
        path: the record as given.
    """
    return ShortError(f"{path}: not a target - jsk 6.0 reads no resume.json, only a target's "
                      "selection in the store",
                      "name the target: `<stem>` or `resumes/<name>` (the resume_select tool "
                      "makes its selection)")


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


def load_resume(path, *, load_store, selections):
    """The selection a target's ref names and the career it is built from, checked.

    Args:
        path: the target's ref (selection.ref).
        load_store: loads its workspace (compose.record.load).
        selections: the selection's bound ports (compose.selection.Ports).

    Returns:
        A LoadedResume. Reads the selection graph and the career.

    Raises:
        ShortError: a path that is no target's ref, a target with no selection, or a
            selection that fails its shape or id checks.
    """
    from .selection import parse_ref, target_name

    ref = parse_ref(path)
    if ref is None:
        raise not_a_target(path)
    root = ref[0]
    store = career_of(root, load_store)
    doc = selected_doc(path, store, root, selections)
    fails = shape(doc, target_name(path)) or ids(doc, store)
    if fails:
        raise ShortError(f"{path}: " + "; ".join(fails),
                         "call the resume_check tool on it and fix what it names")
    return LoadedResume(store, doc, root)
