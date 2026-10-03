"""A target's selection's ports, bound: its workspace found, the career loaded, the selection
read from it, and the render plan built under the shipped region profiles.

The checks are domain/resume/short.py's, the loading application/render/load_resume.py's
and the plan domain/resume/plan.py's; this module hands them the store and the clock.
Nothing is imported until a call.

Every record path the record gate, the render and the gates pass is a target's ref
(application/render/selection.py): `read` gives its selection graph's dict and `workspace`
the root the ref names. A resume.json path was read here too until 6.0
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2); one is refused now,
naming the target form (load_resume.not_a_target).
"""
import datetime


def read(path):
    """A target's selection as resume.json's dict (application.render.load_resume.selected_doc).

    Args:
        path: the target's ref.

    Returns:
        The dict. Reads the selection graph and the career.

    Raises:
        ShortError: no target's ref, or a target with no selection.
    """
    from ....application.render.load_resume import not_a_target, selected_doc
    from ....application.render.selection import parse_ref

    ref = parse_ref(path)
    if ref is None:
        raise not_a_target(path)
    from .selection import Ports

    return selected_doc(path, career(ref[0]), ref[0], Ports())


def workspace(path):
    """The workspace root a target's ref names.

    Args:
        path: the target's ref.

    Returns:
        The root.

    Raises:
        ShortError: no target's ref.
    """
    from ....application.render.load_resume import not_a_target
    from ....application.render.selection import parse_ref

    ref = parse_ref(path)
    if ref is None:
        raise not_a_target(path)
    return ref[0]


def career(root):
    """The workspace at `root`, loaded. A store that will not open is a ShortError with its
    fix, as a file that cannot be read is - never a traceback.

    Args:
        root: the workspace root.

    Returns:
        The loaded Store.

    Raises:
        ShortError: the store will not open.
    """
    from ....application.render.load_resume import career_of
    from .record import load

    return career_of(root, load)


def loaded_resume(path):
    """A target's selection as application/render/load_resume.py loads it, bound to the
    store on disk.

    Args:
        path: the target's ref.

    Returns:
        A LoadedResume. Reads the selection and loads the career.

    Raises:
        ShortError: as load_resume does.
    """
    from ....application.render.load_resume import load_resume
    from .record import load as load_store
    from .selection import Ports

    return load_resume(path, load_store=load_store, selections=Ports())


def load(path):
    """(store, doc, root) for a target's ref, checked - loaded once, so a render building
    two variants reads the career once.

    Args:
        path: the target's ref.

    Returns:
        (the loaded Store, the selection as resume.json's dict, the workspace root).

    Raises:
        ShortError: no target's ref, no selection, or one that fails its checks.
    """
    loaded = loaded_resume(path)
    return loaded.store, loaded.doc, loaded.root


def build(store, doc, *, region=None, fmt=None, today=None):
    """The plan for `doc` (a selection as resume.json's dict, already checked) over the career in `store`,
    under the shipped region profiles.

    Args:
        store: the loaded workspace.
        doc: the resume.json.
        region: overrides the file's region.
        fmt: overrides the file's format.
        today: the declaration's date; a caller that has not read the clock gets today.

    Returns:
        The render plan (domain.resume.plan.build).
    """
    from ....domain.resume.plan import build as plan
    from ....infra import profiles

    return plan(store, doc, profiles=profiles, today=today or datetime.date.today(),
                region=region, fmt=fmt)


def from_path(path, *, region=None, fmt=None, today=None):
    """(plan, workspace root) for a target's ref.

    Args:
        path: the target's ref.
        region: overrides the file's region.
        fmt: overrides the file's format.
        today: the declaration's date; a caller that has not read the clock gets today.

    Returns:
        (the render plan, the workspace root). Reads the selection and the career.

    Raises:
        ShortError: as loaded_resume does.
    """
    from ....application.render.build_plan import build_plan
    from ....infra import profiles

    built = build_plan(path, load=loaded_resume, profiles=profiles,
                       today=today or datetime.date.today(), region=region, fmt=fmt)
    return built.plan, built.root
