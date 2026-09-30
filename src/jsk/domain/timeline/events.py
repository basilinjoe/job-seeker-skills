"""An application's graph and its events as triples, and the dates they carry.

Pure: the quads are built from values, the dates read from text; nothing here reads the
store, the disk or the clock.
"""
import datetime
import hashlib
import re

from .. import ontology as O

# An application frozen before the career was a graph: its record is this file beside it.
LEGACY = "application.md"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def node(iri):
    """The IRI as a term.

    Args:
        iri: the full IRI.

    Returns:
        A NamedNode.
    """
    import pyoxigraph as ox
    return ox.NamedNode(iri)


def lit(value, dtype=None):
    """A literal, typed when `dtype` is given.

    Args:
        value: its lexical form.
        dtype: an XSD local name (date, boolean, string); None for a plain literal.

    Returns:
        A Literal.
    """
    import pyoxigraph as ox
    return ox.Literal(value, datatype=ox.NamedNode(O.XSD + dtype)) if dtype else ox.Literal(value)


def quad(s, p, o):
    """One triple of the application's record, in the default graph.

    Args:
        s: the subject's IRI.
        p: the predicate's local name in the j: vocabulary.
        o: the object, already a term.

    Returns:
        A Quad.
    """
    import pyoxigraph as ox
    return ox.Quad(node(s), node(O.J + p), o)


def date_literal(text):
    """An event's j:date: an xsd:date, or the string `unknown` when the day is not known.

    Args:
        text: YYYY-MM-DD or `unknown`.

    Returns:
        A Literal.
    """
    return lit(text, "string") if text == "unknown" else lit(text, "date")


def event_iri(stem, date, kind):
    """k:evt_<stem>_<date>_<kind>: the date's and kind's hyphens as underscores."""
    return f"{O.K}evt_{stem}_{date.replace('-', '_')}_{kind.replace('-', '_')}"


def event_quads(app, stem, date, kind, channel=None, note=None, due=None, iri=None):
    """One event's triples.

    Args:
        app: the application's IRI.
        stem: the application's stem, which names the event.
        date: the day it happened, YYYY-MM-DD or `unknown`.
        kind: its eventKind.
        channel, note, due: the optional fields; a falsy one writes no triple.
        iri: the event's IRI, when the default one (event_iri) is taken.

    Returns:
        (event iri, [quads]).
    """
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


def submitted_day(triples):
    """The application's j:submitted date, or None (held back: `false`)."""
    for q in triples:
        if q.predicate.value == O.J + "submitted" and \
                getattr(q.object, "datatype", None) is not None and \
                q.object.datatype.value == O.XSD + "date":
            return q.object.value
    return None


def legacy_submitted(text):
    """The `submitted:` date in an application.md's frontmatter, or None - `false`, a
    held-back application, is None too. Only that one line is read, so no YAML parser is
    needed; a frontmatter that never closes raises GraphError, as a file that cannot be
    read."""
    from ..record.parsed import GraphError

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


def is_date(text):
    """Is `text` a calendar date written YYYY-MM-DD, exactly as isoformat writes it?

    Args:
        text: the candidate; any value, since a flag may be missing.

    Returns:
        True or False.
    """
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
