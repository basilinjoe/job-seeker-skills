"""An application's record: what `jsk freeze` writes, and `jsk event` adds to.

Usage: jsk event <app-dir> <kind> --date YYYY-MM-DD|unknown [--channel TEXT] [--note TEXT]
                 [--due YYYY-MM-DD]

  <kind>   one of the pipeline vocabulary: submitted, acknowledged, screen-scheduled,
           screen-done, interview-scheduled, interview-done, onsite-scheduled, onsite-done,
           offer, offer-accepted, rejected, withdrawn, no-response, offer-declined,
           follow-up-sent, note, referral, recruiter-contact

Adds one event, k:evt_<stem>_<date>_<kind>, to applications/<dir>/application.ttl - never
edits one, never removes one. The same kind on the same day is already recorded, and is
refused. The whole workspace is validated with the event in it before the file is
written, and the file is written in the canonical layout. application.ttl is not logged
in career/log.ttl: the log is the career's, and an application is not the career.

A stage is not stored anywhere: `jsk kb query pipeline` derives it from the latest event.

Exit 0 added; 1 refused, with why; 2 called wrong.
"""
import datetime
import difflib
import hashlib
import os
import sys

from . import ontology as O

APPLICATION = "application.ttl"
POSTING = "posting.ttl"
RANK = {"confirmed": 3, "inferred": 2, "needs-verification": 1, "disputed": 0}
KINDS = O.ENUMS["eventKind"]


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


def event_quads(app, stem, date, kind, channel=None, note=None, due=None):
    s = event_iri(stem, date, kind)
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
    """(posting iri, stem) of the Posting in <rel_dir>/posting.ttl, or (None, None)."""
    parsed = store.parsed.get(f"{rel_dir}/{POSTING}")
    if parsed is None:
        return None, None
    for q in parsed.quads:
        if O.class_of(q.subject.value) == "Posting":
            iri = q.subject.value
            return iri, iri[len(O.K) + len("post_"):]
    return None, None


# --- what an application sent --------------------------------------------------------

def sent_achievements(doc, view_id):
    """The achievement ids the view renders, in order - resolve.py's own selection: the
    view's provenance floor, and its include lists where they name bullets."""
    view = next((v for v in doc.get("views") or [] if v.get("id") == view_id), {})
    floor = RANK.get(view.get("provenance_floor", "confirmed"), 3)
    chosen = {inc["ref"]: inc.get("achievements") for inc in view.get("include") or []
              if isinstance(inc, dict) and "ref" in inc}
    projects = {p.get("id"): p for p in doc.get("projects") or [] if isinstance(p, dict)}

    def keep(n):
        status = ((n or {}).get("provenance") or {}).get("status", "confirmed")
        return RANK.get(status, 0) >= floor

    def of(owner, oid):
        items = [a for a in owner.get("achievements") or [] if isinstance(a, dict) and keep(a)]
        if chosen.get(oid):
            items = [a for a in items if a.get("id") in chosen[oid]]
        return [a.get("id") for a in items if a.get("id")]

    out = []
    for e in doc.get("engagements") or []:
        out += of(e, e.get("id"))
        for pid in e.get("projects") or []:
            if pid in projects and keep(projects[pid]):
                out += of(projects[pid], pid)
    return list(dict.fromkeys(out))


def carried(doc, view_id, store):
    """(achievement iris, metric version iris): the bullets the view sent that kb.ttl
    holds, and the version of each metric they cite that is current now - what `jsk kb
    query stale` compares against when a metric is later revised."""
    from ..gates.claims import Career

    career = Career(store)
    bullets = [O.K + a for a in sent_achievements(doc, view_id) if O.K + a in career.kb]
    record = {a.get("id"): a for a, _ in walk(doc)}
    versions = set()
    for b in bullets:
        metrics = set(career.cites.get(b, ()))
        for m in (record.get(b[len(O.K):]) or {}).get("metrics") or []:
            mid = m.get("id") if isinstance(m, dict) else None
            if isinstance(mid, str) and O.K + mid in career.versions:
                metrics.add(O.K + mid)
        versions |= {v for m in metrics for v, _, _ in career.current(m)}
    return bullets, sorted(versions)


def walk(doc):
    from ..gates.validate_urs import walk_achievements
    return walk_achievements(doc)


def application_quads(stem, posting, view, submitted, channel, documents, record_bytes,
                      bullets, versions):
    """application.ttl's triples: the application, and its submitted event when it was
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


def freeze(root, app_dir, doc, view, submitted, channel, documents, record_bytes):
    """(application.ttl text, None) for the directory as it is now, validated with the
    whole workspace - or (None, [lines saying why not]).

    Validated where it stands, before any rename: renaming the directory changes no
    triple, and the posting beside it, which the rules read, is there only now."""
    from . import store as S
    from .kbcli import new_failures
    from .writer import write

    store = S.load(root)
    rel = S.file_name(os.path.abspath(app_dir), store.root)
    posting, stem = posting_of(store, rel)
    if posting is None:
        broken = [f.text() for f in store.findings if f.file == f"{rel}/{POSTING}"]
        return None, ([f"no {POSTING} in {app_dir} with a posting in it"] + broken +
                      ["the application.ttl names the posting it answered; the analyst "
                       "writes posting.ttl beside posting.md"])
    bullets, versions = carried(doc, view, store)
    _, quads = application_quads(stem, posting, view, submitted, channel, documents,
                                 record_bytes, bullets, versions)
    text = write(quads, "application")
    after = S.load(root, texts={f"{rel}/{APPLICATION}": text})
    broken = new_failures(store, after)
    if broken:
        return None, (["the application.ttl it would write does not validate:"]
                      + [f.text() for f in broken])
    return text, None


# --- jsk event -----------------------------------------------------------------------

def usage(message):
    print(message)
    print("usage: jsk event <app-dir> <kind> --date YYYY-MM-DD|unknown [--channel TEXT] "
          "[--note TEXT] [--due YYYY-MM-DD]")
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


def main(argv=None):
    from ..cliutil import wants_help

    args = list(sys.argv[1:] if argv is None else argv)
    if wants_help(args):
        print(__doc__.split("\n\nAdds", 1)[0])
        return 0
    flags, positional, values = {}, [], ("--date", "--channel", "--note", "--due")
    while args:
        token = args.pop(0)
        if token in values:
            if not args:
                return usage(f"{token} needs a value")
            flags[token] = args.pop(0)
        elif token.startswith("-"):
            return usage(f"unknown flag: {token}")
        else:
            positional.append(token)
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
    if not os.path.isdir(app_dir):
        return usage(f"not a directory: {app_dir}")
    path = os.path.join(app_dir, APPLICATION)
    if not os.path.isfile(path):
        if os.path.isfile(os.path.join(app_dir, "application.md")):
            return refuse([f"{app_dir} was frozen as application.md, which this command does "
                           f"not write"], "append the row to its # Timeline table by hand, or "
                          "`jsk migrate` the workspace to the graph record")
        return refuse([f"no {APPLICATION} in {app_dir}"],
                      "an application gets one when it is frozen: `jsk freeze`")
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk event needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    return add(os.path.dirname(os.path.dirname(os.path.abspath(app_dir))), path, kind, date,
               flags.get("--channel"), flags.get("--note"), due)


def add(root, path, kind, date, channel, note, due):
    from . import record as R
    from . import store as S
    from .kbcli import diff, new_failures
    from .writer import WriteError, curie, write

    store = S.load(root)
    rel = S.file_name(os.path.abspath(path), store.root)
    parsed = store.parsed.get(rel)
    if parsed is None:
        return refuse([f.text() for f in store.findings if f.file == rel] or
                      [f"{rel} does not parse"], "`jsk kb check` shows where")
    if parsed.comments:
        return refuse([f"{rel}:{n} {text}" for n, text in parsed.comments],
                      f"move each into a j:note, or `jsk kb fmt {rel} --drop-comments`")
    try:
        canonical = write(parsed.quads, "application") == parsed.text
    except WriteError as e:
        return refuse([f"{rel}: {e}"], "`jsk kb check` shows what is wrong with it")
    if not canonical:
        return refuse([f"{rel} is not in the canonical layout this jsk writes"],
                      f"`jsk kb fmt {rel}` first, so the event is the only change in its diff")
    app = next((q.subject.value for q in parsed.quads
                if O.class_of(q.subject.value) == "Application"), None)
    if app is None:
        return refuse([f"{rel} holds no application"], "`jsk freeze` writes one")
    stem = app[len(O.K) + len("app_"):]
    iri, quads = event_quads(app, stem, date, kind, channel, note, due)
    if iri in store.homes:
        return refuse([f"{curie(iri)} is already recorded: one {kind} on {date}"],
                      f"`jsk kb show {curie(iri)}`; an event is never edited - add a `note` "
                      "event to say more")
    text = write(list(parsed.quads) + quads, "application")
    after = S.load(root, texts={rel: text})
    broken = new_failures(store, after)
    if broken:
        return refuse([f"the event would leave {rel} failing:"] + [f.text() for f in broken],
                      "check the date against the application's; `jsk kb check` shows the rest")
    R.replace(R.staged(path, text), path)
    print(diff(parsed.text, text, rel), end="")
    print(f"added    {curie(iri)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
