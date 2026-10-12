"""`resume_select`, `resume_update` and the selection read: a graph-native resume's choice of
bullets and settings, kept as the graph `applications/<stem>/resume` or
`resumes/<name>/resume`, never as a resume.json.

Ruling 6 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: the
selection is a graph, and domain/resume/selection.py turns it into the resume.json dict and
back, so short.shape, short.ids and plan.build read it unchanged. `select` makes it the way
the resume_select tool (jsk mcp) makes a file - `from_match` the selection for the application's posting
(`--from-match`), `ranked` the one for no posting (`--ranked`) - through
application/tailor/export.py's `short`, so the two paths choose alike. `update` changes
given fields and checks the whole dict again; a summary or headline whose text changes
drops to inferred, its answer and hash with it, as a changed claim does in the career
(Ruling 6, the plan's P3). `confirm` is the career_confirm tool (jsk mcp)'s graph-native branch
(application/record/confirm.py calls it). Every write is validated as P3a's are: the
workspace loaded with the candidate standing in, and only what it newly breaks refused.

A target is named as Ruling 12 names it: an application's stem (`applications/<stem>`,
graph-native - Ruling 11's mark is its posting's advert lines) or `resumes/<name>`, a
general resume answering no posting. The render reaches a target through `ref`: the path
the selection graph would have on disk, `<root>/<target>/resume`. No file is ever there;
it is the one string the record gate, the render and the gates pass between them where a
resume.json path used to go, so the resume_ship tool runs every step on a target with no
step knowing (`load_resume` and adapters/compose/resume.py read it as the graph).
Since 6.0 it is the only record they take (docs/superpowers/plans/
2026-10-03-retire-file-pipeline.md, P2).

It refuses an application made from files, one with no posting, a draft posting for
`from_match`, a frozen application (sent or held back), an existing selection unless
`replace`, and a `from_match` for a general resume. `update`'s FAILs are short.shape's and short.ids' -
an unknown key or id, a retired one, a bullet under no role, a bad setting - and nothing
is written when one fires. Nothing here prints.
"""
import os
import re
from dataclasses import dataclass

from ...domain.naming import resume_graph
from ...domain.posting.errors import Refused
from ...domain.resume import selection as S
from ..posting import native as N

# The two ways a selection is first made: for the posting (the analyst's match) or by the
# career's own ranking, with no posting - the resume_select tool (jsk mcp) and `--ranked`.
MODES = ("from_match", "ranked")
# The pseudo-file a target's selection goes by where a resume.json path used to: the last
# part of its graph's name. Nothing writes a file of that name.
REF = "resume"
# A general resume's name: lowercase words, as an application's stem is. Its ids use `_`.
CV_NAME = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
# The one-line message an update that changed nothing comes back with, in place of a write.
UNCHANGED = "nothing to change: the selection already says that"


@dataclass(frozen=True)
class Target:
    """A graph-native application or a general resume, as its selection is named."""

    root: str                   # the workspace
    rel: str                    # applications/<stem> or resumes/<name>
    name: str                   # the stem, or the general resume's name
    app: N.App | None           # the application; None for a general resume

    @property
    def graph(self):
        """The selection graph's name: `<rel>/resume`."""
        return f"{self.rel}/resume"

    @property
    def out_dir(self):
        """The directory a render of it writes into, created by the first render."""
        return os.path.join(self.root, *self.rel.split("/"))

    @property
    def ref(self):
        """The path the render, the record gate and the gates pass for it (REF)."""
        return os.path.join(self.out_dir, REF)

    @property
    def named(self):
        """How the tools name it: the stem, or `resumes/<name>`."""
        return self.rel.removeprefix("applications/")

    @property
    def sel_id(self):
        """The Selection's local id: `sel_app_<ids>` or `sel_cv_<name>`."""
        if self.app is not None:
            return f"sel_app_{self.app.ids}"
        return "sel_cv_" + self.name.replace("-", "_")


@dataclass(frozen=True)
class Selected:
    """What one select, update or confirm did."""

    target: str | None          # the selection graph's name; None when nothing was written
    doc: dict                   # the selection as resume.json's dict: written, or refused
    findings: tuple             # (severity, text, fix)
    notes: tuple = ()           # what forming it noted: a skills row cut, a headline retuned
    gaps: tuple = ()            # what the posting asks that no confirmed bullet carries
    written: tuple = ()         # the graph names written


def target_of(root, target):
    """The Target `target` names in the workspace at `root`.

    Args:
        root: the workspace root.
        target: `<stem>`, `applications/<stem>` or `resumes/<name>`.

    Returns:
        The Target.

    Raises:
        Refused: it names neither.
    """
    name = (target or "").replace("\\", "/").strip().strip("/")
    if name.startswith("resumes/"):
        cv = name[len("resumes/"):]
        if not CV_NAME.fullmatch(cv):
            raise Refused(f"{target!r} is not a general resume's name",
                          "fix:  resumes/<name>, lowercase words - e.g. resumes/general")
        return Target(root, resume_graph(cv).rsplit("/", 1)[0], cv, None)
    app = N.app_of(root, name.removeprefix("applications/"))
    return Target(root, app.rel, app.stem, app)


def parse_ref(path):
    """(workspace root, target) when `path` is a target's ref, else None. Pure: it reads
    only the path's parts, never the disk.

    Args:
        path: a record path as the render and the gates pass one, a str or a PathLike.
    """
    if isinstance(path, os.PathLike):
        path = os.fspath(path)
    if not isinstance(path, str) or os.path.basename(path) != REF:
        return None
    here = os.path.dirname(os.path.abspath(path))
    kind = os.path.basename(os.path.dirname(here))
    if kind not in ("applications", "resumes"):
        return None
    return os.path.dirname(os.path.dirname(here)), f"{kind}/{os.path.basename(here)}"


def target_name(path):
    """The name the tools give the target whose ref `path` is - `<stem>` or
    `resumes/<name>` - or None for a path that is no ref: what a finding's fix names
    (short.confirm_hint)."""
    found = parse_ref(path)
    return found[1].removeprefix("applications/") if found else None


def shown_name(path):
    """How a finding names a record: a ref by its graph, a file by its basename."""
    found = parse_ref(path)
    return f"{found[1]}/{REF}" if found else os.path.basename(path)


def loaded(root, ports):
    """The workspace, loaded.

    Raises:
        Refused: there is no store at the root.
    """
    if not ports.has_store(root):
        raise Refused(f"no workspace (career/store/) at {root}",
                      "fix:  `jsk kb new` creates one, or run from inside a workspace")
    return ports.load(root)


def checked(store, t, ports, *, posting=None, writing=False):
    """Refuse what no selection use case may touch: an application made from files, one
    with no posting (or in the wrong state), and - when `writing` - a frozen one, sent or
    held back."""
    if t.app is None:
        return
    N.native(store, t.app, ports, posting=posting)
    if writing:
        N.refuse_if_frozen(t.app, store, ports)


def stored(store, t):
    """The selection the target holds, as resume.json's dict.

    Raises:
        Refused: it holds none yet.
    """
    if t.graph not in store.parsed:
        raise Refused(f"{t.graph} holds no selection yet",
                      f"fix:  the `resume_select` tool chooses one ({t.rel})")
    return S.doc_of(store.graph(t.graph))


def doc_in(store, root, rel, ports):
    """The selection `rel` holds in the loaded `store`, checked as `read` checks it.

    Args:
        store: the workspace, loaded.
        root: its root.
        rel: the target, as parse_ref gives it.
        ports: the bound ports (compose.selection.Ports).

    Raises:
        Refused: as read does.
    """
    t = target_of(root, rel)
    checked(store, t, ports)
    return stored(store, t)


def read(root, target, *, ports):
    """The target's selection, as resume.json's dict - what plan.build renders.

    Args:
        root: the workspace root.
        target: `<stem>` or `resumes/<name>`.
        ports: the bound ports (compose.selection.Ports).

    Returns:
        The dict.

    Raises:
        Refused: no store, a legacy application, no posting, or no selection yet.
    """
    t = target_of(root, target)
    return doc_in(loaded(root, ports), root, t.rel, ports)


def write(t, store, doc, ports):
    """Write `doc` as the target's selection once the workspace with it in validates.

    Returns:
        (the graph names written, []), or ([], the (severity, text, fix) FAILs) with
        nothing written.
    """
    from ...domain.record.state import RecordError, Written, new_failures

    triples = S.triples_of(doc, t.sel_id)
    if t.app is not None:
        return N.write(t.app, store, {"resume": triples}, ports)
    after = ports.load(t.root, graphs={t.graph: triples})
    broken = new_failures(store, after)
    if broken:
        return [], [("FAIL", f"what it would write does not validate: {f.text()}",
                     "fix:  correct the entry it names") for f in broken]
    try:
        ports.write_graphs(t.root, {t.graph: triples})
    except (Written, RecordError) as e:
        return [], [("FAIL", f"{t.graph}: not written - {e}", f"fix:  {e.fix}")]
    return [t.graph], []


def doc_faults(doc, store, t):
    """short.shape's FAILs, then - when the shape holds - short.ids', as findings; a hint
    names the tool and the Target `t`, never a resume.json."""
    from ...domain.resume.short import ids, shape

    found = shape(doc, t.named) or ids(doc, store)
    return [("FAIL", text, "fix:  correct it and send the update again") for text in found]


def select(root, target, *, mode, replace=False, today, ports):
    """The target's selection made from the career and written. The caller holds the
    workspace's turn.

    Args:
        root: the workspace root.
        target: `<stem>` or `resumes/<name>`.
        mode: `from_match` (the application's posting; its posting complete) or `ranked`.
        replace: make it again over the one there.
        today: the day recency is counted from and the numbers are checked on.
        ports: the bound ports (compose.selection.Ports).

    Returns:
        The Selected; with a FAIL among its findings nothing was written. A number in a
        chosen bullet the career cannot back is a WARN: a question for the person.

    Raises:
        Refused: an unknown mode, `from_match` for a general resume, a legacy application,
            no posting or a draft one, a frozen application, an existing selection without
            `replace`, or no career.
    """
    from ...domain.matching.report import blocks
    from ...domain.record.state import KB
    from ..record.refusals import Refused as Unexported
    from ..tailor.export import short

    if mode not in MODES:
        raise Refused(f"{mode!r} is not a way to select", f"fix:  one of {', '.join(MODES)}")
    t = target_of(root, target)
    if mode == "from_match" and t.app is None:
        raise Refused(f"{t.rel} answers no posting, so there is no match to select from",
                      "fix:  mode ranked chooses by the career's own ranking")
    store = loaded(root, ports)
    checked(store, t, ports, posting="complete" if mode == "from_match" else None,
            writing=True)
    if t.graph in store.parsed and not replace:
        raise Refused(f"{t.graph} holds a selection already",
                      "fix:  the `resume_update` tool changes it; select with replace to "
                      "make it again")
    if KB not in store.parsed:
        raise Refused("the workspace holds no career", "fix:  `jsk kb new`, then the career")
    blocking = [f for f in store.fails() if f.rule != "log-sync" and f.file != t.graph
                and blocks(f, t.rel + "/")]
    if blocking:
        return Selected(None, {}, tuple(("FAIL", f"a resume would carry it: {f.text()}",
                                         "fix:  the career_check tool shows it; correct it first")
                                        for f in blocking))
    post = t.app.post if mode == "from_match" and t.app is not None else None
    chosen = (ports.select(store, post, today, N.COVER) if post is not None
              else ports.ranked(store, today))
    try:
        made = short(store, chosen, None, today, ships=ports.ships,
                     queries=ports.queries(store), post=post, target=t.named)
    except Unexported as e:
        return Selected(None, {}, tuple(("FAIL", line, f"fix:  {e.fix}") for line in e.lines),
                        gaps=tuple(g.line() for g in chosen.gaps))
    notes = tuple(n.removeprefix("NOTE").strip() for n in made.notes)
    gaps = tuple(g.line() for g in chosen.gaps)
    warns = tuple(("WARN", f"a chosen bullet's number the career cannot back: {line}",
                   "fix:  ask the person, and answer it in the career (`career_apply`) "
                   "before any word is retuned") for line in made.faults)
    fails = doc_faults(made.doc, store, t)
    if fails:
        return Selected(None, made.doc, tuple(fails) + warns, notes, gaps)
    written, fails = write(t, store, made.doc, ports)
    return Selected(t.graph if written else None, made.doc, tuple(fails) + warns, notes,
                    gaps, tuple(written))


def updated(before, *, bullets, roles, skills, names, settings, prose):
    """`before` with the given fields applied: a list or `names` replaced whole (empty
    removes it), a setting set, and a summary or headline whose text changed made inferred
    afresh - its answer and hash were for the old words. Empty text removes the block."""
    doc = dict(before)

    def ident(value):
        return value.removeprefix("k:") if isinstance(value, str) else value

    for key, value in (("bullets", bullets), ("roles", roles), ("skills", skills)):
        if value is not None:
            if value:
                doc[key] = [ident(v) for v in value]
            else:
                doc.pop(key, None)
    if names is not None:
        if names:
            doc["names"] = {ident(k): v for k, v in dict(names).items()}
        else:
            doc.pop("names", None)
    for key, value in settings.items():
        if value is not None:
            doc[key] = value
    for key, text in prose.items():
        if text is None:
            continue
        if not isinstance(text, str):
            doc[key] = text                     # short.shape says what is wrong with it
        elif not text.strip():
            doc.pop(key, None)
        elif (before.get(key) or {}).get("text") != text:
            doc[key] = {"text": text, "status": "inferred"}
    return doc


def update(root, target, *, bullets=None, roles=None, skills=None, names=None, format=None,
           region=None, pages=None, ats_pages=None, floor=None, summary=None, headline=None,
           today, ports):
    """The target's selection with the given fields changed, checked whole and written.
    The caller holds the workspace's turn. A field left None is left as it is.

    Args:
        root: the workspace root.
        target: `<stem>` or `resumes/<name>`.
        bullets, roles, skills: ids in order (`k:` optional), replacing the list; [] drops
            roles or skills.
        names: {skill id: the name it renders under}, replacing them; {} drops them.
        format, region, pages, ats_pages, floor: resume.json's settings.
        summary, headline: the block's text. Changed text arrives inferred, to be read to
            the person and confirmed; "" drops the block.
        today: unused; kept so every use case is called alike.
        ports: the bound ports (compose.selection.Ports).

    Returns:
        The Selected: nothing written when a FAIL is among its findings, or when nothing
        changed (target None, no findings).

    Raises:
        Refused: a legacy application, no posting, a frozen application, or no selection.
    """
    t = target_of(root, target)
    store = loaded(root, ports)
    checked(store, t, ports, writing=True)
    before = stored(store, t)
    doc = updated(before, bullets=bullets, roles=roles, skills=skills, names=names,
                  settings={"format": format, "region": region, "pages": pages,
                            "ats_pages": ats_pages, "floor": floor},
                  prose={"summary": summary, "headline": headline})
    fails = doc_faults(doc, store, t)
    if fails:
        return Selected(None, doc, tuple(fails))
    if S.canonical(doc) == S.canonical(before):
        return Selected(None, doc, (), (UNCHANGED,))
    written, fails = write(t, store, doc, ports)
    return Selected(t.graph if written else None, doc, tuple(fails), (), (), tuple(written))


def confirm(root, target, key, answer, *, ports):
    """The selection's summary or headline confirmed with the person's `answer`: its
    status, the answer and the text's hash (short.confirmed), written to the graph. The
    caller holds the workspace's turn and has refused an answer that says nothing.

    Args:
        root: the workspace root.
        target: `<stem>` or `resumes/<name>`.
        key: "summary" or "headline".
        answer: the person's words.
        ports: the bound ports (compose.selection.Ports).

    Returns:
        (the selection before, after) as resume.json's dict, or (before, None) when it
        was confirmed already.

    Raises:
        Refused: a legacy application, no posting, a frozen one, no selection, no such
            block, a malformed one, or a write that did not validate.
    """
    from ...domain.resume import short as shape_of

    t = target_of(root, target)
    store = loaded(root, ports)
    checked(store, t, ports, writing=True)
    before = stored(store, t)
    block = before.get(key)
    if not isinstance(block, dict):
        raise Refused(f"{t.graph} has no {key} to confirm",
                      f"fix:  write one with the `resume_update` tool ({key}), then read it "
                      "to the person")
    earned = shape_of.unearned(block, key, t.named)
    faults = [f for f in shape_of.shape({"resume": shape_of.VERSION, "bullets": ["ach_"],
                                         key: block}, t.named) if f not in earned]
    if faults:
        raise Refused.every([(f"{t.graph}: {f}", f"fix:  correct the {key} with the "
                              "`resume_update` tool") for f in faults])
    if block.get("status") == "confirmed" and not earned:
        return before, None
    doc = dict(before)
    doc[key] = shape_of.confirmed(block, answer)
    _, fails = write(t, store, doc, ports)
    if fails:
        raise Refused.every([(text, fix) for _, text, fix in fails])
    return before, doc
