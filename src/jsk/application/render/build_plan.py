"""The render plan for a resume.json on disk: the file loaded, then the plan built over it."""
from dataclasses import dataclass

from ...domain.resume.plan import build


@dataclass(frozen=True)
class BuiltPlan:
    """A resume.json's render plan, and the workspace whose career it was built from."""

    plan: dict
    root: str


def build_plan(path, *, load, profiles, today, region=None, fmt=None):
    """The plan for the resume.json at `path`.

    Args:
        path: the resume.json.
        load: loads and checks it (load_resume, bound to its ports).
        profiles: the region profiles (ports.profiles.Profiles).
        today: the date a declaration is signed on.
        region: overrides the file's region.
        fmt: overrides the file's format.

    Returns:
        A BuiltPlan. Reads the file and the career.

    Raises:
        ShortError: from `load`.
    """
    loaded = load(path)
    return BuiltPlan(build(loaded.store, loaded.doc, profiles=profiles, today=today,
                           region=region, fmt=fmt), loaded.root)
