"""A graph-native resume's selection, bound: select, update, read and confirm over
career/store/, and a ship by target (application/render/selection.py, application/ship.py;
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md, P3).

Each writing function takes the workspace's turn before it reads (Ruling 14), as
compose/native.py's do. `ship_target` is `jsk resume ship` on a target: the same ship
run, bound to the ports adapters/cli/ship.py binds (adapter to adapter, Ruling 20), into
the target's own directory, with each step's output captured as the CLI prints it.
`ref_for` is how the CLI reads a positional that names a target rather than a file.
Nothing here prints.
"""
import os

from ....infra.oxigraph import record as R
from .native import Ports as NativePorts


class Ports(NativePorts):
    """What the selection use cases ask of the world, beyond the graph-native ones."""

    def state(self, store):
        """Where the career and its log stand (infra.oxigraph.record.state)."""
        return R.state(store)

    def ships(self, code):
        """Whether a region profile ships for `code` (infra.profiles.ships)."""
        from ....infra import profiles

        return profiles.ships(code)

    def select(self, store, post, today, budget):
        """The Selection for the posting `post` (compose.match.select)."""
        from .match import select

        return select(store, post, today, budget)

    def ranked(self, store, today):
        """The Selection with no posting (compose.match.ranked)."""
        from .match import ranked

        return ranked(store, today)

    def write_graphs(self, root, graphs):
        """Replace `graphs` in one update (infra.oxigraph.record.write_graphs).

        Raises:
            RecordError: nothing was written; Written when it landed and the close failed.
        """
        R.write_graphs(root, graphs)


def select(root, target, *, mode, replace=False, today):
    """The target's selection made and written (application.render.selection.select).

    Returns:
        The Selected.

    Raises:
        Refused: as select does.
    """
    from ....application.render.selection import select as selected

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return selected(root, target, mode=mode, replace=replace, today=today, ports=Ports())


def update(root, target, *, today, **fields):
    """The target's selection changed (application.render.selection.update); `fields` are
    update's keyword arguments.

    Returns:
        The Selected.

    Raises:
        Refused: as update does.
    """
    from ....application.render.selection import update as updated

    with R.turn(root, dry_run=not Ports().has_store(root)):
        return updated(root, target, today=today, ports=Ports(), **fields)


def read(root, target):
    """The target's selection as resume.json's dict (application.render.selection.read);
    no turn.

    Raises:
        Refused: as read does.
    """
    from ....application.render.selection import read as doc

    return doc(root, target, ports=Ports())


def confirm(root, target, block, answer):
    """The selection's summary or headline confirmed with the person's words: what the MCP
    `career_confirm(target=, block=, answer=)` calls (application.record.confirm.
    confirm_summary's graph-native branch).

    Args:
        root: the workspace root.
        target: `<stem>` or `resumes/<name>`.
        block: "summary" or "headline".
        answer: the person's words.

    Returns:
        SummaryConfirmed: the selection before and after as JSON text, both None when it
        was confirmed already.

    Raises:
        application.record.refusals.Refused: the answer says nothing, or as
            selection.confirm refuses.
    """
    from ....application.record.confirm import confirm_summary
    from ....application.record.refusals import Refused

    if block not in ("summary", "headline"):
        raise Refused([f"{block!r} is not a block a selection confirms"],
                      "summary or headline")
    with R.turn(root, dry_run=not Ports().has_store(root)):
        return confirm_summary(target, answer, root, key=block, ports=Ports())


def ref_for(arg, *, dirs=False, root=None):
    """The target's ref when the CLI argument `arg` names a target, else None.

    A target is `<stem>`, `applications/<stem>` or `resumes/<name>` with no file there - an
    application only when its posting graph is graph-native, a general resume always - or,
    with `dirs`, such a directory that exists. A ref passed back (a step's own command line) is one already.
    Anything with an extension is a file, and the file path is unchanged for legacy.

    Args:
        arg: the positional as given.
        dirs: an existing directory may name a target (`jsk resume ship`).
        root: the workspace, or None to find it from the argument or the working directory.

    Returns:
        The ref (application.render.selection.Target.ref), or None. Reads the store's
        graph names.
    """
    from ....application.posting.native import has_lines
    from ....application.render.selection import parse_ref, target_of
    from ....domain.posting.errors import Refused
    from ....infra import files
    from ....infra.oxigraph import db

    if parse_ref(arg):
        return arg
    if os.path.splitext(arg)[1] or os.path.isfile(arg):
        return None
    named = arg.replace("\\", "/").strip("/")
    if os.path.isdir(arg) and not dirs:
        return None
    if os.path.isdir(arg) or os.path.isabs(arg) or named.count("/") > 1 or \
            named.startswith("."):
        # A path: its workspace is the one around it, whether or not it exists yet.
        root = root or files.find_root(os.path.dirname(os.path.abspath(arg)))
        rel = files.file_name(os.path.abspath(arg), root) if root else None
    else:
        root = root or files.find_root(os.getcwd())
        rel = named if "/" in named else f"applications/{named}"
    if root is None or rel is None or rel.count("/") != 1 or \
            not rel.startswith(("applications/", "resumes/")) or not db.exists(root):
        return None
    try:
        t = target_of(root, rel)
    except Refused:
        return None
    if t.app is not None and not has_lines(db.read(root).get(t.app.graph("posting")) or ()):
        # Only a graph-native application is a target (Ruling 11): a legacy one, or a
        # name the store does not know, keeps the answer the file path always gave it.
        return None
    return t.ref


def selection_ref(out_dir):
    """The ref of the selection a render's directory holds in the store, or None: what `jsk
    resume check <dir>` reads as the record when no resume.json is beside the render."""
    ref = ref_for(out_dir, dirs=True)
    if ref is None:
        return None
    from ....application.render.selection import parse_ref
    from ....infra.oxigraph import db

    root, rel = parse_ref(ref) or ("", "")
    return ref if f"{rel}/resume" in db.read(root) else None


def ship_target(root, target, *, ats_max=False, template=None, pages=None, fit=True,
                today=None):
    """`jsk resume ship` on a target: record gate, render, fit and gates into the target's
    own directory (application.ship.ship over adapters/cli/ship.py's ports).

    Args:
        root: the workspace root.
        target: `<stem>` or `resumes/<name>`.
        ats_max: render the ATS-maximal variant.
        template: the visual theme, or None for the default.
        pages: the page budget, or None for the selection's own.
        fit: fit a render over its budget before the gates read it.
        today: unused - the render dates its declaration as `jsk resume render` does;
            kept so every use case is called alike.

    Returns:
        The ShipResult: each GateStep's gate, status, exit and output. Writes the .pdf and
        the .tex into `applications/<stem>/` or `resumes/<name>/`, making it first.

    Raises:
        Refused (domain.posting.errors): no selection, a legacy application, a frozen one,
            or an unknown template.
    """
    from ....application.guards import frozen_refusal
    from ....application.render.selection import target_of
    from ....application.ship import ship
    from ....domain.posting.errors import Refused
    from ....domain.render import themes
    from ....infra import outputs
    from ....infra.files import rel
    from .. import ship as cli
    from ..gates.check import contained, measure, strict_for
    from . import render as bound
    from .timeline import frozen, sent_day

    t = target_of(root, target)
    read(root, target)
    refusal = frozen_refusal(t.out_dir, frozen=frozen, sent=sent_day, native=t.app is not None)
    if refusal:
        raise Refused(refusal[0], refusal[1])
    if template is not None:
        try:
            themes.get(template)
        except KeyError as exc:
            raise Refused(str(exc.args[0]), "fix:  `jsk resume render --list-templates` "
                                            "names them") from None
    return ship(t.ref, t.out_dir, ats_max=ats_max, template=template, pages=pages, fit=fit,
                run=contained, render=cli.render, fitter=cli.fit, tex_engine=bound.Tex(),
                page_count=bound.page_count, outputs=outputs, rel=rel, strict=strict_for,
                measure=measure)
