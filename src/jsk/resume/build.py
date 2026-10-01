"""The career and a short resume.json, as the render plan the emitters take.

Every content decision happens here, exactly once: which evidence is shown, in what
order, whether a line clears the provenance floor, how a date reads, and whether the
text is folded to ASCII. The emitters receive finished strings and decide nothing, so
the PDF and the plain text built from one resume cannot disagree.

This was `render/resolve.py`, which read a URS record copied out of career/kb.ttl. It reads
the career itself now. What the resolver rendered from data the career cannot hold - date of
birth, a photo, referees, compensation, an engagement's location - is gone with the
copy: a feature comes back by giving its data a home in the ontology first.

The builder is domain/resume/plan.py and the loading application/render/load_resume.py;
this module binds them to the real region profiles, workspace and clock.
"""
import datetime

from ..application.render.build_plan import build_plan
from ..application.render.load_resume import load_resume
from ..domain.resume.constants import MAX_SKILLS_PER_ROW as MAX_SKILLS_PER_ROW
from ..domain.resume.constants import PROVENANCE_RANK as PROVENANCE_RANK
from ..domain.resume.plan import CATEGORY_ACRONYMS as CATEGORY_ACRONYMS
from ..domain.resume.plan import CATEGORY_ORDER as CATEGORY_ORDER
from ..domain.resume.plan import COUNTRY as COUNTRY
from ..domain.resume.plan import DIRECT_CONTACTS as DIRECT_CONTACTS
from ..domain.resume.plan import FILLABLE as FILLABLE
from ..domain.resume.plan import LANGUAGE as LANGUAGE
from ..domain.resume.plan import SAID_KINDS as SAID_KINDS
from ..domain.resume.plan import SECTIONS as SECTIONS
from ..domain.resume.plan import Builder as Builder
from ..domain.resume.plan import role_title as role_title
from ..infra import profiles


def build(store, doc, *, region=None, fmt=None, today=None):
    """The plan for `doc` (a short resume.json, already checked) over the career in
    `store`, under the shipped region profiles.

    Args:
        store: the loaded workspace.
        doc: the resume.json.
        region: overrides the file's region.
        fmt: overrides the file's format.
        today: the declaration's date; a caller that has not read the clock gets today.

    Returns:
        The render plan (domain.resume.plan.build).
    """
    from ..domain.resume.plan import build as plan

    return plan(store, doc, profiles=profiles, today=today or datetime.date.today(),
                region=region, fmt=fmt)


def load(path):
    """(store, doc, root) for the resume.json at `path`, checked. Raises
    short.ShortError for a file that cannot be read, sits outside a workspace, or fails
    its checks - loaded once, so a render building two variants reads the career once."""
    loaded = loaded_resume(path)
    return loaded.store, loaded.doc, loaded.root


def loaded_resume(path):
    """The resume.json at `path` as application/render/load_resume.py loads it, bound to
    the workspace on disk.

    Returns:
        A LoadedResume. Reads the file and loads the career.

    Raises:
        ShortError: as load_resume does.
    """
    from ..adapters.cli.compose.record import load as load_store
    from ..infra import files

    return load_resume(path, files=files, find_root=files.find_root, load_store=load_store)


def from_path(path, *, region=None, fmt=None, today=None):
    """(plan, workspace root) for the resume.json at `path`."""
    built = build_plan(path, load=loaded_resume, profiles=profiles,
                       today=today or datetime.date.today(), region=region, fmt=fmt)
    return built.plan, built.root
