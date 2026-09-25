"""What an application starts from, out of career/kb.ttl.

`short_file` is what `jsk kb export` writes: the short resume.json, the ids a resume
shows and its settings, and nothing the career holds - the render reads the words, the
numbers and the dates from kb.ttl as it stands, so there is no copy to go stale and
nothing to refresh (docs/superpowers/specs/2026-09-25-short-resume-json-design.md).

What `select` narrows is the experience: a project brings its bullets, a bullet brings
only itself (and its project), a role brings itself. An employer comes with every role
held there, so a promotion history is never cut in half. The rest - the person, rights to
work, languages, skills, education, credentials, the positioning - comes across whole:
it is short, and the view decides what renders.
"""
import difflib
import os

from ..paths import SCHEMA_DIR
from ..resume.career import Career, local
from . import ontology as O

SELECTS = ("Project", "Achievement", "Position")


class ExportError(Exception):
    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


def chosen(career, select):
    """(projects, bullets, roles) to export: sets of iris, or None for all of them."""
    if not select:
        return None
    projects, bullets, roles = set(), set(), set()
    known = set(career.sub.cls)
    for text in select:
        iri = O.K + text.removeprefix("k:")
        if iri not in known:
            near = difflib.get_close_matches(iri, sorted(known), n=1)
            raise ExportError(f"{text} is not in career/kb.ttl",
                              f"did you mean {local(near[0])}?" if near
                              else "`jsk kb view` lists the ids")
        cls = career.sub.cls[iri].name
        if cls == "OpenSource":
            # URS has no open-source section. On the ElevenLabs run the refusal below
            # sent the author to rewrite a confirmed bullet around the repo's URL.
            raise ExportError(f"{text} is open source ({career.get(iri, 'url')}), and a "
                              "resume.json has no section for it",
                              "the person's contacts carry their github profile already; the "
                              "repo link goes in a bullet's words only if the person confirms "
                              "that wording - a changed bullet drops to inferred")
        if cls not in SELECTS:
            raise ExportError(f"{text} is a {cls}, and selects nothing: export selects "
                              "projects (prj_), bullets (ach_) and roles (pos_)",
                              "select the bullets that cite it, or their project")
        if career.get(iri, "retired"):
            raise ExportError(f"{text} was retired on {career.get(iri, 'retired')} "
                              f"({career.get(iri, 'reason', 'no reason given')})",
                              "leave it out: a retired entry does not belong on a resume")
        {"Project": projects, "Achievement": bullets, "Position": roles}[cls].add(iri)
    return projects, bullets, roles


def region_code(country):
    """The profile code for a country, or None when no profile ships for it - the builder
    then falls back to the person's country itself, and so to the default profile."""
    token = (country or "").lower()
    if token and os.path.exists(os.path.join(SCHEMA_DIR, "profiles", f"{token}.json")):
        return token
    return None


def short_file(store, selection=None, select=None, notes=None):
    """The short resume.json for a selection, as a dict: ids and settings, nothing the
    career holds. Raises ExportError for a `select` it cannot honour, or a selection
    holding no bullet a resume can render.

    `selection` is select.py's choice for one posting: its bullets, project by project in
    its order, and its skills in the posting's order; `select` then adds only roles.
    Without it, `select` names what to show - a project brings every live bullet of it by
    j:rank, a bullet only itself (and narrows its project to the bullets named), a role
    itself - and with neither, the whole career. A bullet whose project names no role is
    left out and said in `notes`: it would render under no employer, and the record gate
    fails a file naming it.

    `pages` is 2, as the URS draft's budget was: the short file's default is the region
    profile's (3 for AU and IN), and an export defaulting to that would have made every
    exported resume a page longer than the same export made the day before."""
    from . import record as R

    career = Career(store.graph(R.KB))
    picked = chosen(career, select)

    def rank(a):
        return (int(career.get(a, "rank", 0)), a)

    roles = []
    if selection is not None:
        projects = list(selection.projects)
        bullets_of = {p: list(selection.bullets.get(p, [])) for p in projects}
        if picked is not None:
            roles = sorted(picked[2])
    else:
        live = sorted(career.live("Achievement"), key=rank)
        projects = sorted(career.live("Project"),
                          key=lambda p: (-int(career.get(p, "recency", 0)), p))
        bullets_of = {p: [a for a in live if career.get(a, "project") == p] for p in projects}
        if picked is not None:
            want, named, extra = picked
            homes = {career.get(a, "project") for a in named}
            projects = [p for p in projects if p in want or p in homes]
            for p in projects:
                if p in homes:                          # a bullet named narrows its project
                    bullets_of[p] = [a for a in bullets_of[p] if a in named]
            roles = sorted(extra)
    bullets = []
    for p in projects:
        if not career.get(p, "position"):
            if bullets_of.get(p) and notes is not None:
                notes.append(f"NOTE  {local(p)} names no role (j:position), so its bullets are "
                             "left out - they would render under no employer")
            continue
        bullets += [local(a) for a in bullets_of.get(p, []) if local(a) not in bullets]
    if not bullets:
        raise ExportError("the selection holds no bullet, and a resume.json is its bullets",
                          "confirm a bullet the GAP lines name, or add one with --select")
    doc = {"resume": 2}
    region = region_code(career.get(O.K + "person", "country"))
    if region:
        doc["region"] = region
    doc["pages"] = 2
    doc["bullets"] = bullets
    if roles:
        doc["roles"] = [local(r) for r in roles]
    if selection is not None and selection.skills:
        doc["skills"] = [local(s) for s in selection.skills]
    return doc
