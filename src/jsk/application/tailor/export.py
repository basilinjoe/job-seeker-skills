"""`jsk kb export`: choosing the bullets a resume.json shows, forming it, and writing the file.

`short_file` is the short resume.json: the ids a resume shows and its settings, and nothing
the career holds - the render reads the words, the numbers and the dates from the career as
it stands, so there is no copy to go stale and nothing to refresh
(docs/superpowers/specs/2026-09-25-short-resume-json-design.md).

What `select` narrows is the experience: a project brings its bullets, a bullet brings
only itself (and its project), a role brings itself. An employer comes with every role
held there, so a promotion history is never cut in half. The rest - the person, rights to
work, languages, skills, education, credentials, the positioning - comes across whole:
it is short, and the view decides what renders.

Choosing is three steps, because the command says what each found before the next can
refuse: the career is opened and checked (`opened`), the selection is made for a posting,
by rank or not at all (`selection`), and the short file is formed from it with the
numbers its bullets state checked (`short`). Writing it is `write`. Nothing here prints:
adapters/cli/kb/export.py does.

The pieces that read the career or the disk are given as parameters - the selection
(`selector`), the posting lookup, which region profiles ship (`ships`) - so this imports
nothing outside the application and the domain.
"""
import difflib
import os
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.record.career import Career, local
from ...domain.record.state import KB
from ..record.check import untraced_lines
from ..record.refusals import Failing, Refused, Unclean

SELECTS = ("Project", "Achievement", "Position")


class ExportError(Exception):
    """A --select the export cannot honour, or a selection with no bullet, and the fix."""

    def __init__(self, message, fix):
        """Say what cannot be exported.

        Args:
            message: what is wrong.
            fix: what to do about it.
        """
        super().__init__(message)
        self.fix = fix


def chosen(career, select):
    """What --select names, each id checked against the career.

    Args:
        career: the career graph (domain.record.career.Career).
        select: the ids --select named, or None.

    Returns:
        (projects, bullets, roles) to export: sets of iris, or None for all of them.

    Raises:
        ExportError: an id the career does not hold, an open-source entry, an id of a
            class that selects nothing, or a retired entry or one under a retired home.
    """
    if not select:
        return None
    projects, bullets, roles = set(), set(), set()
    known = set(career.sub.cls)
    for text in select:
        iri = O.K + text.removeprefix("k:")
        if iri not in known:
            near = difflib.get_close_matches(iri, sorted(known), n=1)
            raise ExportError(f"{text} is not in the career",
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
        # Its project and role, which it renders under: only live ones are walked, so a
        # bullet of a retired project had no home and left the file with nothing said.
        home = iri
        for key in {"Achievement": ("project", "position"), "Project": ("position",)}.get(cls, ()):
            home = career.get(home, key)
            if home and career.get(home, "retired"):
                raise ExportError(f"{text} is under {local(home)}, retired on "
                                  f"{career.get(home, 'retired')} "
                                  f"({career.get(home, 'reason', 'no reason given')})",
                                  "leave it out, or move it to a live "
                                  f"{'project' if key == 'project' else 'role'} with `jsk kb apply`")
            if not home:
                break
        {"Project": projects, "Achievement": bullets, "Position": roles}[cls].add(iri)
    return projects, bullets, roles


def region_code(country, ships):
    """The profile code for a country, or None when no profile ships for it - the builder
    then falls back to the person's country itself, and so to the default profile.

    Args:
        country: the person's country, or None.
        ships: (code) -> whether a region profile ships for it (infra.profiles.ships).

    Returns:
        The lowercased code, or None.
    """
    token = (country or "").lower()
    if token and ships(token):
        return token
    return None


def rows(career, skills):
    """The skills block's rows, as the builder forms them: grouped by category in the order
    a category's first skill comes, each name once across the block, first occurrence
    winning.

    Args:
        career: the career graph.
        skills: the skill iris, in order.

    Returns:
        {category: the skills its row renders}.
    """
    groups, seen = {}, set()
    for s in skills:
        groups.setdefault(career.get(s, "category") or "other", []).append(s)
    out = {}
    for cat, members in groups.items():
        for s in members:
            name = (career.get(s, "name") or "").strip().casefold()
            if name and name not in seen:
                seen.add(name)
                out.setdefault(cat, []).append(s)
    return out


def capped(career, skills, notes=None):
    """`skills` with each row cut to the MAX_SKILLS_PER_ROW that render, the first kept.

    The order is select.py's, the posting's asks first, so what a row keeps is what the
    posting asked for. Schneider's export named about 110 skills and Arrow rendered rows
    of 15-18 where 10 show; the builder dropped the rest with a WARN, and the main thread
    trimmed the file by hand. A skill cut from one row can let the same name show in a
    later one, so the cut runs until no row is over.

    Args:
        career: the career graph.
        skills: the skill iris, in order.
        notes: a list a NOTE line per row cut is appended to, or None.

    Returns:
        The skills kept, in order.
    """
    from ...domain.resume.constants import MAX_SKILLS_PER_ROW

    kept, left = list(skills), {}
    while True:
        over = {cat: members[MAX_SKILLS_PER_ROW:]
                for cat, members in rows(career, kept).items()
                if len(members) > MAX_SKILLS_PER_ROW}
        if not over:
            break
        for cat, cut in over.items():
            left.setdefault(cat, []).extend(cut)
        cut = {s for members in over.values() for s in members}
        kept = [s for s in kept if s not in cut]
    if notes is not None:
        for cat, cut in left.items():
            notes.append(f"NOTE  skills row {cat!r} keeps its first {MAX_SKILLS_PER_ROW}, the "
                         f"posting's first; {len(cut)} left out: "
                         f"{', '.join(local(s) for s in cut)}")
    return kept


def short_file(store, selection=None, select=None, notes=None, *, ships):
    """The short resume.json for a selection, as a dict: ids and settings, nothing the
    career holds.

    `selection` is select.py's choice for one posting: its bullets, project by project in
    its order, and its skills in the posting's order; `select` then adds only roles.
    Without it, `select` names what to show - a project brings every live bullet of it by
    j:rank, a bullet only itself (and narrows its project to the bullets named), a role
    itself - and with neither, the whole career. A bullet whose project names no role is
    left out and said in `notes`: it would render under no employer, and the record gate
    fails a file naming it.

    `pages` is 2, as the URS draft's budget was: the short file's default is the region
    profile's (3 for AU and IN), and an export defaulting to that would have made every
    exported resume a page longer than the same export made the day before.

    Args:
        store: a loaded workspace.
        selection: the Selection for a posting or by rank, or None.
        select: the ids --select named, or None.
        notes: a list the NOTE lines are appended to, or None.
        ships: (code) -> whether a region profile ships for it (infra.profiles.ships).

    Returns:
        The short file as a dict.

    Raises:
        ExportError: a `select` it cannot honour, or a selection holding no bullet a
            resume can render.
    """
    career = Career(store.graph(KB))
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
    doc: dict = {"resume": 2}
    region = region_code(career.get(O.K + "person", "country"), ships)
    if region:
        doc["region"] = region
    doc["pages"] = 2
    doc["bullets"] = bullets
    if roles:
        doc["roles"] = [local(r) for r in roles]
    if selection is not None and selection.skills:
        doc["skills"] = [local(s) for s in capped(career, selection.skills, notes)]
    return doc


def opened(root, app, posting, out, replace, *, load, state, file_name, blocks):
    """The career, loaded and checked for what would stop a resume.

    Args:
        root: the workspace.
        app: the application directory for --from-match, or None.
        posting: --from-match as given (truthy when there is one).
        out: --out, or None.
        replace: whether --replace was given.
        load: loads the workspace (compose.record.load).
        state: where the career and its log stand (infra.oxigraph.record.state).
        file_name: a path as a finding names it (infra.files.file_name).
        blocks: whether a finding stops a match of the application
            (domain.matching.report.blocks).

    Returns:
        The loaded store. Reads the record.

    Raises:
        Unclean: there is no career. Failing: the career (or the posting) has FAILs a
            resume would carry. Refused: --out exists and --replace was not given.
    """
    store = load(root)
    if KB not in store.parsed:
        raise Unclean(state(store))
    # The career always; with --from-match, the application's own directory too, as jsk
    # match.
    here = file_name(app, store.root) + "/" if posting else None
    blocking = [f for f in store.fails() if f.rule != "log-sync"
                and (not f.file.startswith("applications/") or (here and blocks(f, here)))]
    if blocking:
        where = "the career and the posting have" if posting else "the career has"
        raise Failing(blocking, f"REFUSED  {where} {len(blocking)} failures - "
                                "a resume would carry them:", written=False)
    if out and os.path.exists(out) and not replace:
        raise Refused([f"{out} exists - export writes a new resume.json, never over one "
                       "unless told to"],
                      "edit it, or pass --replace to export it again - it holds only ids and "
                      "settings, and the career is read afresh at every render")
    return store


def selection(store, app, posting, select, by_rank, today, budget, *, selector, posting_in):
    """The selection for a posting (--from-match) or by rank (--ranked), or None for neither.

    Args:
        store: the loaded workspace.
        app: the application directory, with --from-match.
        posting: --from-match as given.
        select: the ids --select named, or None.
        by_rank: --ranked.
        today: the date recency is counted from.
        budget: the most projects the cover may use (--cover).
        selector: the selection: ranked, select (compose.match).
        posting_in: the posting an application holds (compose.match.posting_in).

    Returns:
        domain.selection.select.Selection, or None.

    Raises:
        Refused: a --select that cannot be honoured, or an application with no posting.
    """
    if not (posting or by_rank):
        return None
    try:
        chosen(Career(store.graph(KB)), select)      # a bad --select refuses first
    except ExportError as err:
        raise Refused([str(err)], err.fix) from None
    extra = [O.K + t.removeprefix("k:") for t in select or []]
    if by_rank:
        return selector.ranked(store, today, extra)
    post = posting_in(store, app)
    if post is None:
        raise Refused([f"{posting} holds no posting"],
                      f"`jsk posting build {posting}` writes it from posting.md")
    return selector.select(store, post, today, budget, extra)


@dataclass(frozen=True)
class Short:
    """The short resume.json, what forming it noted, and the number checks it fails."""

    doc: dict
    notes: tuple                # NOTE lines: a skills row cut, a project with no role
    faults: tuple               # untraced_lines over the chosen bullets


def short(store, chosen, select, today, *, ships, queries):
    """The short resume.json for `chosen` (or `select`, or the whole career).

    Args:
        store: the loaded workspace.
        chosen: the Selection, or None.
        select: the ids --select named, or None.
        today: the date the number check runs on.
        ships: (code) -> whether a region profile ships for it (infra.profiles.ships).
        queries: the RecordQueries over the store.

    Returns:
        Short.

    Raises:
        Refused: a --select it cannot honour, or a selection with no bullet.
    """
    notes = []
    try:
        doc = short_file(store, selection=chosen, select=select, notes=notes, ships=ships)
    except ExportError as err:
        raise Refused([str(err)], err.fix) from None
    faults = untraced_lines(store, queries, today, [O.K + b for b in doc["bullets"]])
    return Short(doc, tuple(notes), tuple(faults))


@dataclass(frozen=True)
class Written:
    """A resume.json written: where, at which revision, and each bullet's first words."""

    path: str
    revision: int | None
    bullets: tuple              # (id, its first 100 characters)


def write(store, path, text, doc, *, state, write_text):
    """Write the short file to `path`.

    Args:
        store: the loaded workspace the file was chosen from.
        path: --out.
        text: the file's text.
        doc: the file as data.
        state: where the career and its log stand (infra.oxigraph.record.state).
        write_text: writes a text file, its folder made first.

    Returns:
        Written. Writes the file.
    """
    write_text(path, text)
    revision = state(store).log_revision
    career = Career(store.graph(KB))
    bullets = tuple((b, " ".join((career.get(O.K + b, "text") or "").split())[:100])
                    for b in doc["bullets"])
    return Written(path, revision, bullets)
