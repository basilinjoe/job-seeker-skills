"""An application's record: what `jsk freeze` writes, and `jsk event` adds to.

Usage: jsk event <app-dir> <kind> --date YYYY-MM-DD|unknown [--channel TEXT] [--note TEXT]
                 [--due YYYY-MM-DD] [--today YYYY-MM-DD]

  <kind>   one of the pipeline vocabulary: submitted, acknowledged, screen-scheduled,
           screen-done, interview-scheduled, interview-done, onsite-scheduled, onsite-done,
           offer, offer-accepted, rejected, withdrawn, no-response, offer-declined,
           follow-up-sent, note, referral, recruiter-contact

Adds one event, k:evt_<stem>_<date>_<kind>, to the application's record (the graph
applications/<dir>/application) - never edits one, never removes one. A second of the
same kind on the same day - another note, a second interview round - is
k:evt_..._<kind>_2, then _3; only an event identical to one already there (kind, date,
channel, note and due) is refused. The whole workspace is validated with the event in it
before anything is written. The application is not logged in the career's log: the log
is the career's, and an application is not the career.

A stage is not stored anywhere: `jsk kb query pipeline` derives it from the latest event.

The date is the day it happened - a screen-scheduled event's is the day it was booked,
the screen itself its --due. Both are printed back with their weekday and distance from
today (--today, for a test), so "last Tuesday" worked out wrong shows as the wrong
weekday; a --date after today is a WARN, since nothing has happened yet on it.

Exit 0 added; 1 refused, with why; 2 called wrong.
"""
import datetime
import difflib
import hashlib
import os
import re
import sys
import time

from ..domain import ontology as O

# An application's record graphs, by kind: in career/store/ as applications/<dir>/<kind>.
RECORD = ("posting", "application", "gaps")
REPLACE_TRIES = 6                                # a Windows lock usually clears in ms
KINDS = O.ENUMS["eventKind"]
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def node(iri):
    import pyoxigraph as ox
    return ox.NamedNode(iri)


def lit(value, dtype=None):
    import pyoxigraph as ox
    return ox.Literal(value, datatype=ox.NamedNode(O.XSD + dtype)) if dtype else ox.Literal(value)


def quad(s, p, o):
    import pyoxigraph as ox
    return ox.Quad(node(s), node(O.J + p), o)


def date_literal(text):
    return lit(text, "string") if text == "unknown" else lit(text, "date")


def event_iri(stem, date, kind):
    """k:evt_<stem>_<date>_<kind>: the date's and kind's hyphens as underscores."""
    return f"{O.K}evt_{stem}_{date.replace('-', '_')}_{kind.replace('-', '_')}"


def event_quads(app, stem, date, kind, channel=None, note=None, due=None, iri=None):
    s = iri or event_iri(stem, date, kind)
    out = [quad(s, "application", node(app)), quad(s, "date", date_literal(date)),
           quad(s, "kind", node(O.J + kind))]
    if channel:
        out.append(quad(s, "channel", lit(channel)))
    if note:
        out.append(quad(s, "note", lit(note)))
    if due:
        out.append(quad(s, "due", lit(due, "date")))
    return s, out


def posting_of(store, rel_dir):
    """(posting iri, stem) of the Posting in the application <rel_dir>, or (None, None)."""
    from ..domain.naming import app_graph

    parsed = store.parsed.get(app_graph(rel_dir, "posting"))
    if parsed is None:
        return None, None
    for q in parsed.quads:
        if O.class_of(q.subject.value) == "Posting":
            iri = q.subject.value
            return iri, iri[len(O.K) + len("post_"):]
    return None, None


# --- what a sent application keeps ---------------------------------------------------
#
# Two tests, both here so that no command writes its own. `frozen`: `jsk freeze` has run,
# so the documents and resume.json in the directory are what went out - a render or a
# confirm must not touch them. `sent_day`: the application's record holds the day it was
# sent, so the posting it answered and the assessment of it are what they said then. A
# held-back application (submitted false) is frozen but not sent. An application.md is
# one frozen before the career was a graph, and is as frozen as an application record.
#
# The record is the store's application graph and nothing else: `jsk kb load` leaves the
# .ttl files where they were, and a stray application.ttl there must not freeze, or
# unfreeze, anything.

LEGACY = "application.md"


def workspace_of_app(app_dir):
    """(workspace root, `applications/<dir>`) for a directory at
    <root>/applications/<dir>, else (None, None). Both named as they are on disk
    (store.spelled): the graph name is the folder's, however the path was typed."""
    from ..infra.files import spelled

    here = os.path.abspath(app_dir)
    apps = os.path.dirname(here)
    root = os.path.dirname(apps)
    if spelled(root, os.path.basename(apps)) != "applications":
        return None, None
    return root, "applications/" + spelled(apps, os.path.basename(here))


def app_graphs(app_dir, store=None):
    """{kind: triples} of the record graphs the application holds in its workspace's
    store - {} when it is in no workspace with a store. Read from `store` when it is that
    workspace's, loaded; from the store on disk if not."""
    from ..infra.oxigraph import db
    from ..domain.naming import app_graph

    root, rel = workspace_of_app(app_dir)
    if root is None or not db.exists(root):
        return {}
    if store is not None and store.stored and \
            os.path.normcase(os.path.abspath(store.root)) == os.path.normcase(root):
        graphs = {n: p.quads for n, p in store.parsed.items()}
    else:
        graphs = db.read(root)
    return {kind: graphs[app_graph(rel, kind)] for kind in RECORD
            if app_graph(rel, kind) in graphs}


def has_record(app_dir, kind, store=None):
    """Does the application hold its `kind` graph (posting, application, gaps)?"""
    return kind in app_graphs(app_dir, store)


class Unwritable(Exception):
    """A write to an application directory that did not happen. Carries the fix."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


class Frozen(Unwritable):
    """Refused because the application is sent."""


def frozen(app_dir, store=None):
    """What says `app_dir` was frozen, else None: the application graph's name
    (`applications/<dir>/application`), or a legacy application.md's path."""
    if "application" in app_graphs(app_dir, store):
        return f"{workspace_of_app(app_dir)[1]}/application"
    path = os.path.join(app_dir, LEGACY)
    return path if os.path.isfile(path) else None


def submitted_day(triples):
    """The application's j:submitted date, or None (held back: `false`)."""
    for q in triples:
        if q.predicate.value == O.J + "submitted" and \
                getattr(q.object, "datatype", None) is not None and \
                q.object.datatype.value == O.XSD + "date":
            return q.object.value
    return None


def sent_day(app_dir, store=None):
    """The day `app_dir` says it was sent - its application record's j:submitted, or a
    legacy application.md's `submitted:` - or None. Raises GraphError when that cannot be
    read: whether it was sent is then unknown, and the writers below refuse rather than
    guess."""
    from .io import GraphError, Unreadable, read_text

    graphs = app_graphs(app_dir, store)
    if "application" in graphs:
        return submitted_day(graphs["application"])
    path = frozen(app_dir, store)
    if path is None:
        return None
    try:
        return legacy_submitted(read_text(path, LEGACY))
    except Unreadable as e:
        raise GraphError(str(e), e.fix, os.path.basename(path)) from None


def legacy_submitted(text):
    """The `submitted:` date in an application.md's frontmatter, or None - `false`, a
    held-back application, is None too. Only that one line is read, so no YAML parser is
    needed; a frontmatter that never closes raises GraphError, as a file that cannot be
    read."""
    from ..domain.record.parsed import GraphError

    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        raise GraphError(f"{LEGACY}'s frontmatter never closes", "end it with a --- line",
                         LEGACY)
    for line in lines[1:closing]:
        m = re.match(r"submitted:\s*[\"']?([^\"'#\s]*)", line)
        if m:
            return m.group(1) if is_date(m.group(1)) else None
    return None


def refuse_if_sent(app_dir, name, store=None, graph=False):
    """Raise Frozen when `name` in `app_dir` must not change: the application was sent,
    or whether it was cannot be read. `graph`: `name` is a graph's (applications/<dir>/
    gaps), not a file in the directory."""
    from ..domain.record.parsed import GraphError

    try:
        day = sent_day(app_dir, store)
    except GraphError as e:
        raise Frozen(f"{name}: {os.path.basename(frozen(app_dir, store) or LEGACY)} "
                     f"beside it cannot be read, so whether it was sent is unknown ({e})",
                     "`jsk kb check` shows what is wrong with it") from None
    if day:
        raise Frozen(f"{name if graph else os.path.join(app_dir, name)}: the application was "
                     f"sent on {day}, and this is what it answered", "copy the application "
                     "to a new dated directory to reuse it")


def write_app_graphs(app_dir, graphs, store=None):
    """Replace the application's `graphs` ({kind: triples, or None to drop it}) in its
    workspace's store, in one update - or raise Unwritable, writing nothing: Frozen when
    the application is sent. Returns the graph names written. The posting and the
    assessment come through here; the application graph is `jsk freeze`'s and `jsk
    event`'s, which write to a sent application, and does not."""
    from ..infra.oxigraph import record as R
    from ..domain.naming import app_graph

    root, rel = workspace_of_app(app_dir)
    names = {kind: app_graph(rel, kind) for kind in graphs}
    for kind in graphs:
        refuse_if_sent(app_dir, names[kind], store, graph=True)
    try:
        R.write_graphs(root, {names[k]: t for k, t in graphs.items()})
    except R.Written as e:
        raise Unwritable(f"{rel}: {e}", e.fix) from None
    except R.RecordError as e:
        raise Unwritable(f"{rel}: not written - {e}", e.fix) from None
    return [names[k] for k, t in graphs.items() if t]


def write_app_file(app_dir, name, text, store=None):
    """Write the document `name` in `app_dir` (gaps.md) - or raise Unwritable, writing
    nothing: Frozen when the application is sent, else the file is locked or the disk
    refused. The record's graphs go through write_app_graphs."""
    refuse_if_sent(app_dir, name, store)
    return write_document(os.path.join(app_dir, name), text)


def write_document(path, text, tries=REPLACE_TRIES, wait=0.05):
    """`text` staged beside `path` as path.tmp, flushed, then renamed over it - the one step
    the filesystem makes atomic, so a crash leaves the old document or the new one. The
    rename is retried: on Windows an editor, a sync client or a virus scanner holding the
    file makes it fail for a moment, and a moment later it succeeds. Raises Unwritable,
    having written nothing."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        for n in range(tries):
            try:
                os.replace(tmp, path)
                return path
            except PermissionError:
                if n == tries - 1:
                    raise Unwritable(f"{path}: not written - it is locked by another "
                                     "program - an editor, a sync client or a virus scanner",
                                     "close it and run the command again") from None
                time.sleep(wait * (n + 1))
    except OSError as e:
        raise Unwritable(f"{path}: not written - {e.strerror or e}",
                         "check the folder and its permissions") from None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def remove_app_file(app_dir, name, store=None):
    """Remove `name` from `app_dir` if it is there - or raise Unwritable (Frozen when the
    application is sent). True when a file was removed."""
    refuse_if_sent(app_dir, name, store)
    path = os.path.join(app_dir, name)
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
    except OSError as e:
        raise Unwritable(f"{path}: not removed - {e.strerror or e}",
                         "close whatever holds it and run the command again") from None
    return True


# --- what an application sent --------------------------------------------------------

def application_quads(stem, posting, view, submitted, channel, documents, record_bytes,
                      bullets, versions):
    """The application graph's triples: the application, and its submitted event when it was
    sent - a held-back one has none, an accurate blank rather than a false green."""
    app = f"{O.K}app_{stem}"
    out = [quad(app, "posting", node(posting))]
    if view:
        out.append(quad(app, "view", lit(view)))
    out.append(quad(app, "submitted", lit("false", "boolean") if submitted == "false"
                    else lit(submitted, "date")))
    if channel:
        out.append(quad(app, "channel", lit(channel)))
    out += [quad(app, "document", lit(d)) for d in documents]
    out.append(quad(app, "recordSha256", lit(hashlib.sha256(record_bytes).hexdigest())))
    out += [quad(app, "carried", node(b)) for b in bullets]
    out += [quad(app, "carriedVersion", node(v)) for v in versions]
    if submitted != "false":
        out += event_quads(app, stem, submitted, "submitted", channel)[1]
    return app, out


def sent_versions(store, bullets):
    """The current version of each metric the bullets cite - what `jsk kb query stale`
    compares against when a metric is later revised."""
    from ..infra.oxigraph.queries import OxigraphQueries

    if not bullets:
        return []
    return OxigraphQueries(store).cited_current_versions(bullets)


class Sealed:
    """What freeze() validated inside the turn, for write_frozen: the application's graph
    name as it stands, the application graph to write, and the graphs a rename moves - as
    that load read them, so nothing is read again once the folder has moved."""

    def __init__(self, rel, quads, moves):
        self.rel, self.quads, self.moves = rel, quads, moves


def freeze(root, app_dir, plan, short_bytes, submitted, channel, documents):
    """(Sealed, None) for an application whose resume.json is a short file, validated with
    the whole workspace - or (None, [lines saying why not]). write_frozen writes it.

    `plan` is what the builder rendered: its `sent` names the bullets that cleared the
    floor, so a bullet the file lists but the render withheld is not claimed as sent. No
    copy of the words is kept - the PDF, .txt and .tex beside it are what went out - so
    the short file's own hash is what `recordSha256` pins."""
    def sent(store):
        bullets = [O.K + b for b in plan["sent"]]
        return bullets, sent_versions(store, bullets)

    return write_application(root, app_dir, "resume", submitted, channel, documents,
                             short_bytes, sent)


def write_application(root, app_dir, view, submitted, channel, documents, record_bytes,
                      carried_of):
    """Validated where it stands, before any rename: renaming the directory changes no
    triple, and the posting beside it, which the rules read, is there only now.
    `carried_of(store)` is (bullet iris, metric version iris) for what was sent."""
    from . import store as S
    from ..domain.record.state import new_failures

    store = S.load(root)
    # Asked again here, inside the turn: another freeze of this application may have
    # landed since `jsk freeze` asked, while this one waited.
    held = frozen(app_dir, store)
    if held:
        return None, [f"{held} already exists. A frozen application is never re-frozen.",
                      "Later events are `jsk event`, one each."]
    rel = S.file_name(os.path.abspath(app_dir), store.root)
    posting, stem = posting_of(store, rel)
    if posting is None:
        broken = [f.text() for f in store.findings if f.file == S.app_graph(rel, "posting")]
        return None, ([f"no posting in {app_dir}"] + broken +
                      ["the application record names the posting it answered: "
                       f"`jsk posting build {app_dir}` writes it from posting.md"])
    bullets, versions = carried_of(store)
    _, quads = application_quads(stem, posting, view, submitted, channel, documents,
                                 record_bytes, bullets, versions)
    after = S.load(root, graphs={S.app_graph(rel, "application"): quads})
    broken = new_failures(store, after)
    if broken:
        return None, (["the application record it would write does not validate:"]
                      + [f.text() for f in broken])
    moves = {kind: store.graph(S.app_graph(rel, kind)) for kind in ("posting", "gaps")
             if S.app_graph(rel, kind) in store.parsed}
    return Sealed(rel, quads, moves), None


def write_frozen(root, sealed, final):
    """Write what freeze() validated, once the directory is at `final` (renamed to the day
    it was sent, or left where it was). Returns the graph's name.

    A graph is named by its directory, so a rename moves the posting and the assessment
    to the new name in the same update that writes the application - all three land, or
    none does."""
    from ..infra.oxigraph import record as R
    from ..domain.naming import app_graph

    old, new = sealed.rel, workspace_of_app(final)[1]
    graphs = {}
    if old != new:
        for kind, triples in sealed.moves.items():
            graphs[app_graph(old, kind)] = None
            graphs[app_graph(new, kind)] = triples
    graphs[app_graph(new, "application")] = sealed.quads
    R.write_graphs(root, graphs)
    return app_graph(new, "application")


# --- jsk event -----------------------------------------------------------------------

def usage(message):
    print(message)
    print("usage: jsk event <app-dir> <kind> --date YYYY-MM-DD|unknown [--channel TEXT] "
          "[--note TEXT] [--due YYYY-MM-DD] [--today YYYY-MM-DD]")
    return 2


def refuse(lines, fix):
    for line in lines:
        print(f"REFUSED  {line}")
    print(f"        fix: {fix}")
    print("nothing was written")
    return 1


def is_date(text):
    try:
        return datetime.date.fromisoformat(text).isoformat() == text
    except (TypeError, ValueError):
        return False


def when(text, today):
    """`2026-09-22 (Tuesday, 4 days ago)`: a date as the person would say it. The model
    turns "last Tuesday" into a date by arithmetic, which errs silently; the weekday
    printed back is what it can check against what was said."""
    if text == "unknown":
        return text
    day = datetime.date.fromisoformat(text)
    n = (day - today).days
    ago = "today" if n == 0 else "yesterday" if n == -1 else "tomorrow" if n == 1 else \
        f"{-n} days ago" if n < 0 else f"in {n} days"
    return f"{text} ({WEEKDAYS[day.weekday()]}, {ago})"   # not %A: that follows the locale


def main(argv=None):
    from ..cliutil import parse_flags, wants_help

    args = list(sys.argv[1:] if argv is None else argv)
    if wants_help(args):
        # __doc__ is None only under -OO, which nothing runs jsk with.
        print(__doc__.split("\n\nAdds", 1)[0])  # pyright: ignore[reportOptionalMemberAccess]
        return 0
    parsed, problem = parse_flags(args, ("--date", "--channel", "--note", "--due", "--today"), ())
    if parsed is None:
        return usage(problem)
    positional, flags = parsed
    if len(positional) != 2:
        return usage("jsk event takes an application directory and a kind")
    app_dir, kind = positional[0].rstrip("/\\") or positional[0], positional[1]
    if kind not in KINDS:
        near = difflib.get_close_matches(kind, KINDS, n=1, cutoff=0.5)
        return usage(f"unknown kind: {kind!r} - " + (f"did you mean {near[0]!r}? " if near else "")
                     + f"one of {', '.join(KINDS)}")
    date = flags.get("--date")
    if date is None:
        return usage("--date is required: the day it happened, or `unknown`")
    if date != "unknown" and not is_date(date):
        return usage(f"--date needs YYYY-MM-DD or unknown, got {date!r}")
    due = flags.get("--due")
    if due is not None and not is_date(due):
        return usage(f"--due needs YYYY-MM-DD, got {due!r}")
    today = flags.get("--today", datetime.date.today().isoformat())
    if not is_date(today):
        return usage(f"--today needs YYYY-MM-DD, got {today!r}")
    if not os.path.isdir(app_dir):
        return usage(f"not a directory: {app_dir}")
    if workspace_of_app(app_dir)[0] is None:
        # An application's graph is named applications/<dir>/application, so an event
        # written anywhere else would be one no query ever reads.
        return usage(f"{app_dir} is not in an applications/ folder - pass "
                     "applications/<dir>, beside career/")
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk event needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    if not has_record(app_dir, "application"):
        if os.path.isfile(os.path.join(app_dir, "application.md")):
            return refuse([f"{app_dir} was frozen as application.md, which this command does "
                           f"not write"], "append the row to its # Timeline table by hand")
        return refuse([f"{app_dir} holds no application record"],
                      "an application gets one when it is frozen: `jsk freeze`")
    return add(workspace_of_app(app_dir)[0], app_dir, kind, date,
               flags.get("--channel"), flags.get("--note"), due,
               datetime.date.fromisoformat(today))


def free_iri(store, base, quads):
    """(iri to mint, None), or (None, the iri of an event that is this one exactly).

    Two notes on one day, a round-1 and a round-2 interview-done, two recruiter-contacts
    dated unknown are all real, so the id is the first of base, base_2, base_3... that is
    free. Only an event identical in every
    field (kind, date, channel, note, due) is a duplicate: running the same command
    twice records nothing new."""
    want = {(q.predicate, q.object) for q in quads}
    iri, n = base, 2
    while iri in store.homes:
        have = {(q.predicate, q.object) for parsed in store.parsed.values()
                for q in parsed.quads if q.subject.value == iri}
        if have == want:
            return None, iri
        iri, n = f"{base}_{n}", n + 1
    return iri, None


def add(root, app_dir, kind, date, channel, note, due, today=None):
    """Add the event, inside this process's turn: taken before the application is read,
    so an event that queued behind another write is added to what that one left."""
    from ..infra.oxigraph import record as R

    with R.turn(root):
        return added(root, app_dir, kind, date, channel, note, due, today)


def added(root, app_dir, kind, date, channel, note, due, today):
    from ..infra.oxigraph import record as R
    from . import store as S
    from ..domain.record.state import diff, new_failures
    from ..domain.record.writer import curie, write

    store = S.load(root)
    rel = S.app_graph(S.file_name(os.path.abspath(app_dir), store.root), "application")
    parsed = store.parsed.get(rel)
    if parsed is None:
        return refuse([f.text() for f in store.findings if f.file == rel] or
                      [f"{rel} is not in the store"], "`jsk kb check` shows what is wrong")
    app = next((q.subject.value for q in parsed.quads
                if O.class_of(q.subject.value) == "Application"), None)
    if app is None:
        return refuse([f"{rel} holds no application"], "`jsk freeze` writes one")
    stem = app[len(O.K) + len("app_"):]
    iri, quads = event_quads(app, stem, date, kind, channel, note, due)
    iri, same = free_iri(store, iri, quads)
    if same:
        return refuse([f"{curie(same)} is already recorded: this {kind} on {date}, with the "
                       "same channel, note and due"],
                      f"`jsk kb show {curie(same)}`; an event is never edited - add a `note` "
                      "event to say more")
    iri, quads = event_quads(app, stem, date, kind, channel, note, due, iri=iri)
    new = list(parsed.quads) + quads
    after = S.load(root, graphs={rel: new})
    broken = new_failures(store, after)
    if broken:
        return refuse([f"the event would leave {rel} failing:"] + [f.text() for f in broken],
                      "check the date against the application's; `jsk kb check` shows the rest")
    try:
        R.write_graphs(root, {rel: new})
    except R.Written as e:
        # The event is in the store: not "nothing was written".
        print(f"FAIL     {e}")
        print(f"        fix: {e.fix}")
        return 1
    except R.RecordError as e:
        return refuse([str(e)], e.fix)
    print(diff(write(parsed.quads, "application"), write(new, "application"), rel), end="")
    print(f"added    {curie(iri)}")
    today = today or datetime.date.today()
    print(f"recorded {kind} on {when(date, today)}")
    if due:
        print(f"due {when(due, today)}")
    if date != "unknown" and datetime.date.fromisoformat(date) > today:
        # Every kind's date is the day it happened - a booking's too, its day is --due -
        # so a future one is arithmetic gone wrong, and it would sort as the latest stage.
        print(f"WARN  {date} is after today, and the date is the day it happened - "
              "a meeting still to come is the --due of its -scheduled event; an event is "
              "never edited, so correct this one with a `note` event")
    return 0


if __name__ == "__main__":
    sys.exit(main())
