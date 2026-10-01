"""A graph-native application, named by its stem: where its graphs are, what its posting
graph holds, and the refusals every graph-native use case shares.

Ruling 11 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: an
application is graph-native when its posting graph holds `j:AdvertLine`s, and legacy when
its posting was built from files (a posting graph without lines, or a posting.md on disk).
No application is both, so each side refuses the other, naming what the other side uses:
the use cases here name `jsk posting build`, and the file verbs name the MCP tool (TOOLS).
Ruling 12: the application is `applications/<stem>`, and nothing here creates its
directory - the first render does.

It reads no file and opens no store itself: the use cases pass in the loaded Store and the
ports adapters/cli/compose/native.py binds. A candidate graph is validated as
`write_application` validates one (application/timeline/records.py): the workspace loaded
with the candidate standing in, and only what it newly breaks refused.
"""
import os
import re
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.naming import app_graph
from ...domain.posting.errors import POSTING, Refused

# The MCP tools (Ruling 18's table) a file verb names when it refuses a graph-native
# application: what does that verb's work for one whose record is all in the store.
TOOLS = {"jsk tailor match": "assessment_derive",
         "jsk posting extract": "app_show (part: lines)",
         "jsk posting build": "posting_decide",
         "jsk tailor match --gaps": "assessment_review",
         "jsk tailor match --draft-gaps": "assessment_derive",
         "jsk tailor prepare --draft-gaps": "assessment_derive"}
# How many projects the cover may use, as `jsk tailor match` defaults it.
COVER = 3


@dataclass(frozen=True)
class App:
    """One application, as the store names it."""

    root: str                   # the workspace
    stem: str                   # the directory's name: applications/<stem>
    app_dir: str                # where its directory is, or will be
    rel: str                    # applications/<stem>
    ids: str                    # the stem its ids carry: k:post_<ids>, k:req_<ids>_<slug>

    @property
    def post(self):
        """The posting's iri."""
        return f"{O.K}post_{self.ids}"

    def graph(self, kind):
        """The name of this application's `kind` graph."""
        return app_graph(self.rel, kind)


def app_of(root, stem):
    """The App for `applications/<stem>` in the workspace at `root`.

    Args:
        root: the workspace root.
        stem: the application's directory name, as `jsk tailor match applications/<stem>`
            would name it; a leading date is not part of its ids.

    Returns:
        The App.

    Raises:
        Refused: `stem` is a path, or gives no usable id.
    """
    from .extract import dir_stem

    if not stem or re.search(r"[\\/:]", stem) or stem.strip(".") == "":
        raise Refused(f"{stem!r} is not an application's name",
                      "fix:  name it as applications/<stem> names it - lowercase words "
                      "joined by `-`, e.g. acme-platform-engineer")
    app_dir = os.path.join(root, "applications", stem)
    ids = dir_stem(app_dir)
    if not re.fullmatch(O.SLUG, ids):
        raise Refused(f"{stem!r} gives no usable posting id ({ids!r})",
                      "fix:  name it with lowercase words, e.g. acme-platform-engineer")
    return App(root, stem, app_dir, f"applications/{stem}", ids)


def loaded(app, ports):
    """The workspace, loaded.

    Raises:
        Refused: there is no store at the root.
    """
    if not ports.has_store(app.root):
        raise Refused(f"no workspace (career/store/) at {app.root}",
                      "fix:  `jsk kb new` creates one, or run from inside a workspace")
    return ports.load(app.root)


def has_lines(quads):
    """Whether a posting graph holds the advert's lines: Ruling 11's graph-native mark."""
    return any(O.class_of(q.subject.value) == "AdvertLine" for q in quads)


def kind(store, app, is_file):
    """"native", "legacy", or None when the application holds no posting yet.

    Args:
        store: the loaded workspace.
        app: the App.
        is_file: path -> whether there is a file there.
    """
    parsed = store.parsed.get(app.graph("posting"))
    if parsed is not None and has_lines(parsed.quads):
        return "native"
    if parsed is not None or is_file(os.path.join(app.app_dir, POSTING)):
        return "legacy"
    return None


def legacy_refusal(app):
    """The Refused for a graph-native tool asked about an application made from files."""
    return Refused(f"{app.rel} was made from files (posting.md, decisions.txt, gaps.txt): "
                   "its record stays on the file path",
                   f"fix:  `jsk posting build {app.rel}` and `jsk tailor match {app.rel} "
                   "--gaps` keep working on it; a new posting is a new application")


def native_refusal(rel, verb):
    """(message, fix) for the file verb `verb` asked about a graph-native application.

    Args:
        rel: the application, `applications/<dir>`.
        verb: the verb as TOOLS names it.
    """
    return (f"{rel} is graph-native: its advert, requirements and review are in the store, "
            f"not in files, so `{verb}` does not apply",
            f"fix:  use the `{TOOLS[verb]}` tool (`jsk mcp`) on {rel.split('/', 1)[-1]}")


def native_graphs(graphs):
    """Whether an application's {kind: triples} make it graph-native (Ruling 11)."""
    return has_lines(graphs.get("posting") or ())


def refused_verb(graphs, rel, verb):
    """The two lines a file verb prints refusing a graph-native application, or None when
    the application is not one.

    Args:
        graphs: the application's {kind: triples} (records.app_graphs).
        rel: the application, `applications/<dir>`.
        verb: the verb as TOOLS names it.
    """
    if not native_graphs(graphs):
        return None
    message, fix = native_refusal(rel, verb)
    return f"FAIL  {message}\n      fix: {fix.removeprefix('fix:').strip()}"


@dataclass
class Stored:
    """A graph-native posting graph, read back into what decide.triples writes."""

    head: dict                  # company, title, url
    seniority: str
    domains: list               # the domains' iris
    captured: str               # ISO
    state: str | None           # draft or complete
    lines: list                 # [advert.AdvertLine] by number
    drops: dict                 # {n: reason}
    reqs: dict                  # {slug: (asked, need, (concept iris), quote, n)}, in order


def stored(store, app):
    """The application's posting graph, read back.

    Args:
        store: the loaded workspace.
        app: the App.

    Returns:
        The Stored. Requirements come in line order, then slug: the graph keeps no order.
    """
    from ...domain.posting.lines import from_triples

    quads = store.graph(app.graph("posting"))
    props = {}
    for q in quads:
        if q.predicate.value.startswith(O.J):
            props.setdefault(q.subject.value, {}).setdefault(
                q.predicate.value[len(O.J):], []).append(q.object.value)

    def one(p, key, default: str | None = ""):
        return p.get(key, [default])[0]

    post = props.get(app.post, {})
    lines, drops = from_triples(quads)
    reqs = []
    head = f"{O.K}req_{app.ids}_"
    for s, p in props.items():
        if O.class_of(s) != "Requirement" or not s.startswith(head):
            continue
        line = one(p, "line", None)
        n = int(line.rsplit("_", 1)[1]) if line else 0
        reqs.append((n, s[len(head):], (one(p, "asked"), one(p, "necessity").removeprefix(O.J),
                                        tuple(sorted(p.get("concept", []))), one(p, "quote"),
                                        n)))
    state = one(post, "state", None)
    return Stored({"company": one(post, "company"), "title": one(post, "title"),
                   "url": one(post, "url")},
                  one(post, "seniority").removeprefix(O.J), sorted(post.get("domain", [])),
                  one(post, "captured"), state.removeprefix(O.J) if state else None,
                  lines, drops, {slug: row for _, slug, row in sorted(reqs)})


def triples(app, s, state):
    """The posting graph's triples for the Stored `s`, at `state` (domain.posting.decide)."""
    from ...domain.posting.decide import triples as posting_triples

    reqs = [(slug, asked, need, list(iris), quote, n)
            for slug, (asked, need, iris, quote, n) in s.reqs.items()]
    return posting_triples(app.post, app.ids, s.head, s.seniority, s.domains, s.captured, reqs,
                           lines=s.lines, drops=s.drops, state=state)


def native(store, app, ports, *, posting=None):
    """The Stored posting of a graph-native application, refusing anything else.

    Args:
        store: the loaded workspace.
        app: the App.
        ports: the bound ports (compose.native.Ports).
        posting: the state the posting must be in, or None for either.

    Returns:
        The Stored.

    Raises:
        Refused: no posting, a legacy one, or one in the wrong state.
    """
    found = kind(store, app, ports.is_file)
    if found == "legacy":
        raise legacy_refusal(app)
    if found is None:
        raise Refused(f"{app.rel} holds no posting",
                      f"fix:  the `posting_capture` tool stores its advert ({app.stem})")
    s = stored(store, app)
    if posting == "complete" and s.state != "complete":
        raise Refused(f"{app.graph('posting')} is a draft: its requirements are not settled",
                      f"fix:  the `posting_complete` tool checks and settles them ({app.stem})")
    return s


# The one way to reuse a frozen graph-native application through the tools: a directory
# cannot be copied by an agent holding no shell, so the advert is captured again under a
# new name and the run starts there.
REUSE = "fix:  capture the posting again under a new stem (`posting_capture`) to reuse it"


def refuse_if_frozen(app, store, ports):
    """Refuse a change to a frozen application before anything is built: one sent, or one
    `jsk app freeze --submitted false` held back.

    The test is the one `resume_ship` makes (application.guards.frozen_refusal): the
    application graph exists. Keyed on the day it was sent alone, a held-back freeze kept
    taking reviews, selections and re-derivations under the record that froze them - the
    end-to-end replay found it (2026-10-02).

    Raises:
        Refused: it is frozen, or whether it was sent cannot be read.
    """
    from ...domain.record.parsed import GraphError

    try:
        day = ports.sent_day(app.app_dir, store)
    except GraphError as e:
        raise Refused(f"{app.graph('application')}: {e}", f"fix:  {e.fix}") from None
    if day:
        raise Refused(f"{app.rel}: the application was sent on {day}, and this is what it "
                      "answered", REUSE)
    if app.graph("application") in store.parsed:
        raise Refused(f"{app.rel}: the application is frozen (held back, not sent), and this "
                      "is what it was frozen with", REUSE)


def write(app, store, graphs, ports):
    """Write the application's graphs once the workspace with them in validates.

    Args:
        app: the App.
        store: the workspace as loaded inside the turn.
        graphs: {kind: triples, or None to drop it}.
        ports: the bound ports (compose.native.Ports).

    Returns:
        (the graph names written, []), or ([], the (severity, text, fix) FAILs) with
        nothing written.
    """
    from ...domain.record.state import new_failures
    from ...domain.timeline.errors import Unwritable

    after = ports.load(app.root, graphs={app.graph(k): t for k, t in graphs.items()})
    broken = new_failures(store, after)
    if broken:
        return [], [("FAIL", f"what it would write does not validate: {f.text()}",
                     "fix:  correct the row it names") for f in broken]
    try:
        return ports.write(app.app_dir, graphs, store), []
    except Unwritable as e:
        return [], [("FAIL", str(e), f"fix:  {e.fix}")]


def field(item, name, default=None):
    """`name` of a row given as a dict or as an object with that attribute."""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def fails(findings):
    """Whether any (severity, text, fix) finding is a FAIL."""
    return any(severity == "FAIL" for severity, _, _ in findings)


def clean(findings):
    """The findings with one spelling of a fix: its words alone, or None. rows.py and the
    refusals write `fix:  ...`, fold.check the bare words; a caller reading structure gets
    one form (Ruling 16)."""
    return tuple((severity, text, (fix or "").removeprefix("fix:").strip() or None)
                 for severity, text, fix in findings)
