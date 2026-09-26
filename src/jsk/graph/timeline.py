"""An application's record: what `jsk freeze` writes, and `jsk event` adds to.

Usage: jsk event <app-dir> <kind> --date YYYY-MM-DD|unknown [--channel TEXT] [--note TEXT]
                 [--due YYYY-MM-DD] [--today YYYY-MM-DD]

  <kind>   one of the pipeline vocabulary: submitted, acknowledged, screen-scheduled,
           screen-done, interview-scheduled, interview-done, onsite-scheduled, onsite-done,
           offer, offer-accepted, rejected, withdrawn, no-response, offer-declined,
           follow-up-sent, note, referral, recruiter-contact

Adds one event, k:evt_<stem>_<date>_<kind>, to applications/<dir>/application.ttl - never
edits one, never removes one. A second of the same kind on the same day - another note,
a second interview round - is k:evt_..._<kind>_2, then _3; only an event identical to
one already there (kind, date, channel, note and due) is refused. The whole workspace is validated with the event in it before the file is
written, and the file is written in the canonical layout. application.ttl is not logged
in career/log.ttl: the log is the career's, and an application is not the career.

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
import sys

from . import ontology as O

APPLICATION = "application.ttl"
POSTING = "posting.ttl"
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


def sent_versions(store, bullets):
    """The current version of each metric the bullets cite - what `jsk kb query stale`
    compares against when a metric is later revised."""
    from . import queries as Q

    if not bullets:
        return []
    values = " ".join(f"<{b}>" for b in bullets)
    rows = store.select(Q.PRE + f"""
        SELECT DISTINCT ?v WHERE {{ VALUES ?b {{ {values} }} ?b j:cites ?m . ?v j:of ?m .
                                    FILTER NOT EXISTS {{ ?v j:validUntil ?u }} }}""")
    return sorted(r["v"].value for r in rows)


def freeze(root, app_dir, plan, short_bytes, submitted, channel, documents):
    """(application.ttl text, None) for an application whose resume.json is a short file,
    validated with the whole workspace - or (None, [lines saying why not]).

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
    bullets, versions = carried_of(store)
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
    from ..cliutil import wants_help

    args = list(sys.argv[1:] if argv is None else argv)
    if wants_help(args):
        print(__doc__.split("\n\nAdds", 1)[0])
        return 0
    flags, positional, values = {}, [], ("--date", "--channel", "--note", "--due", "--today")
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
    today = flags.get("--today", datetime.date.today().isoformat())
    if not is_date(today):
        return usage(f"--today needs YYYY-MM-DD, got {today!r}")
    if not os.path.isdir(app_dir):
        return usage(f"not a directory: {app_dir}")
    if os.path.basename(os.path.dirname(os.path.abspath(app_dir))) != "applications":
        # The loader finds applications/*/application.ttl and nothing else, so an event
        # written anywhere else would be one no query ever reads.
        return usage(f"{app_dir} is not in an applications/ folder - pass "
                     "applications/<dir>, beside career/")
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
               flags.get("--channel"), flags.get("--note"), due,
               datetime.date.fromisoformat(today))


def free_iri(store, base, quads):
    """(iri to mint, None), or (None, the iri of an event that is this one exactly).

    Two notes on one day, a round-1 and a round-2 interview-done, two recruiter-contacts
    dated unknown are all real, so the id is the first of base, base_2, base_3... that is
    free - as `jsk migrate` mints a timeline's repeats. Only an event identical in every
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


def add(root, path, kind, date, channel, note, due, today=None):
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
    iri, same = free_iri(store, iri, quads)
    if same:
        return refuse([f"{curie(same)} is already recorded: this {kind} on {date}, with the "
                       "same channel, note and due"],
                      f"`jsk kb show {curie(same)}`; an event is never edited - add a `note` "
                      "event to say more")
    iri, quads = event_quads(app, stem, date, kind, channel, note, due, iri=iri)
    text = write(list(parsed.quads) + quads, "application")
    after = S.load(root, texts={rel: text})
    broken = new_failures(store, after)
    if broken:
        return refuse([f"the event would leave {rel} failing:"] + [f.text() for f in broken],
                      "check the date against the application's; `jsk kb check` shows the rest")
    R.replace(R.staged(path, text), path)
    print(diff(parsed.text, text, rel), end="")
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
