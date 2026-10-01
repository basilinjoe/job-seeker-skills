"""A short resume.json's ports, bound: the file read from disk, its workspace found, the career
loaded, and the render plan built under the shipped region profiles.

The file's checks are domain/resume/short.py's, the loading application/render/
load_resume.py's and the plan domain/resume/plan.py's; this module hands them the disk, the
store and the clock. Nothing is imported until a call.
"""
import datetime


def read(path):
    """The resume.json at `path`, as a dict (application.render.load_resume.read_short).

    Args:
        path: the file.

    Returns:
        The dict. Reads the file.

    Raises:
        ShortError: the file is missing, unreadable, or not a version-2 resume.json.
    """
    from ....application.render.load_resume import read_short
    from ....infra import files

    return read_short(path, files)


def workspace(path):
    """The workspace root above the file, walked up to the folder holding career/store/.

    Args:
        path: the resume.json.

    Returns:
        The root.

    Raises:
        ShortError: the file is not inside a workspace.
    """
    from ....application.render.load_resume import workspace_of
    from ....infra.files import find_root

    return workspace_of(path, find_root)


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
    """The resume.json at `path` as application/render/load_resume.py loads it, bound to the
    workspace on disk.

    Args:
        path: the resume.json.

    Returns:
        A LoadedResume. Reads the file and loads the career.

    Raises:
        ShortError: as load_resume does.
    """
    from ....application.render.load_resume import load_resume
    from ....infra import files
    from .record import load as load_store

    return load_resume(path, files=files, find_root=files.find_root, load_store=load_store)


def load(path):
    """(store, doc, root) for the resume.json at `path`, checked - loaded once, so a render
    building two variants reads the career once.

    Args:
        path: the resume.json.

    Returns:
        (the loaded Store, the resume.json as a dict, the workspace root).

    Raises:
        ShortError: a file that cannot be read, sits outside a workspace, or fails its
            checks.
    """
    loaded = loaded_resume(path)
    return loaded.store, loaded.doc, loaded.root


def build(store, doc, *, region=None, fmt=None, today=None):
    """The plan for `doc` (a short resume.json, already checked) over the career in `store`,
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
    """(plan, workspace root) for the resume.json at `path`.

    Args:
        path: the resume.json.
        region: overrides the file's region.
        fmt: overrides the file's format.
        today: the declaration's date; a caller that has not read the clock gets today.

    Returns:
        (the render plan, the workspace root). Reads the file and loads the career.

    Raises:
        ShortError: as loaded_resume does.
    """
    from ....application.render.build_plan import build_plan
    from ....infra import profiles

    built = build_plan(path, load=loaded_resume, profiles=profiles,
                       today=today or datetime.date.today(), region=region, fmt=fmt)
    return built.plan, built.root
