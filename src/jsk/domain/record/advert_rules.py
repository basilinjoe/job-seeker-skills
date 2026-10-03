"""Tier 2's reads of an advert: what quote-verbatim, necessity-wording and advert-uncovered
compare a posting's requirements against.

A graph-native posting is checked against the lines its graph holds (Rulings 2 and 3 of
docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md), and a draft one not at
all - it may be half-decided. A posting built from files is checked against posting.md and
decisions.txt beside it, read through the Reads rules.py is given - and since 6.0 only once
it is frozen: Ruling 2 of docs/superpowers/plans/2026-10-03-retire-file-pipeline.md keeps
that read path, read-only, for the archive of what was sent. An unsent one is not judged;
`jsk kb check` names it `file-made-unsent` instead (Ruling 5), and nothing in this CLI can
change it. Split out of rules.py (2026-10-02) when the graph-native reads took it past its
size; the rule rows stay there.
"""
from collections import defaultdict

from .. import ontology as O
from ..posting.advert import OPTIONAL_WORDS, REQUIRED_WORDS, advert_lines, asked_lines, asked_of
from ..posting.advert import squash


def folder_of(file):
    """The folder a graph's name puts it in: `applications/acme` for
    `applications/acme/posting`, "" for a name with none."""
    return file.rpartition("/")[0]


def frozen_folder(store, folder):
    """Whether the application at `folder` is frozen - its application graph is in the
    store, sent or held back - so its files are the archive Ruling 2 keeps reading."""
    return f"{folder}/application" in store.parsed


def unquoted(rows, store, reads):
    """A requirement whose quote is not in the advert beside it, word for word.

    A graph-native posting's advert is its stored lines, and a draft one is not judged.

    Args:
        rows: the SELECT's rows, ?focus a requirement, ?q its quote and ?p its posting.
        store: the loaded workspace.
        reads: the Reads whose adverts supply each posting.md.

    Returns:
        The rows whose quote fails, each with "why".
    """
    from ..posting.lines import lines_of, native
    from .parsed import Missing, NotUtf8, Unreadable
    from .rules import v

    out, adverts, graph, stored = [], {}, native(store), {}
    for r in rows:
        post = v(r, "p")
        if post in graph:
            if graph[post] == "draft":
                continue
            if post not in stored:
                stored[post] = [squash(x.text) for x in lines_of(store, post)[0]]
            quote = squash(v(r, "q"))
            if not quote:
                out.append({**r, "why": "the quote is empty"})
            elif not any(quote in text for text in stored[post]):
                out.append({**r, "why": "no line of the advert says it"})
            continue
        file = store.file_of(v(r, "focus"))
        if not file:
            continue
        advert = folder_of(file)
        if not frozen_folder(store, advert):
            continue                        # unsent and made from files: not judged (6.0)
        if advert not in adverts:
            # (text, None), or (None, why it could not be read) - the finding says which.
            try:
                adverts[advert] = (squash(reads.adverts.advert(store.root, advert)), None)
            except Missing:
                adverts[advert] = (None, "posting.md is missing beside it")
            except NotUtf8:
                adverts[advert] = (None, "posting.md beside it is not UTF-8 - save it as UTF-8")
            except Unreadable as e:
                adverts[advert] = (None, f"posting.md beside it could not be read: {e}")
        text, unread = adverts[advert]
        if not squash(v(r, "q")):
            out.append({**r, "why": "the quote is empty"})     # "" is in every advert
        elif unread:
            out.append({**r, "why": unread})
        elif squash(v(r, "q")) not in text:
            out.append({**r, "why": "posting.md does not say it"})
    return out


def worded_otherwise(rows, store, reads):
    from .rules import v

    out = []
    for r in rows:
        quote, need = v(r, "q"), v(r, "n")[len(O.J):]
        if need == "required" and (said := OPTIONAL_WORDS.search(quote)):
            out.append({**r, "said": said.group(0), "need": need})
        elif need in ("preferred", "implicit") and (said := REQUIRED_WORDS.search(quote)):
            out.append({**r, "said": said.group(0), "need": need})
    return out


def dropped_lines(adverts, root, folder, advert):
    """The advert lines decisions.txt beside posting.md drops with a reason: answered, not
    skipped, so not uncovered. A decisions.txt that does not parse drops nothing - `jsk
    posting build` refuses it long before this reads it.

    Args:
        adverts: the AdvertSource decisions.txt is read through.
        root: the workspace root.
        folder: the application's folder, relative to `root`.
        advert: posting.md's text.

    Returns:
        {str}: the squashed text of each dropped line.
    """
    from .decisions import DecisionsError
    from .parsed import Unreadable

    try:
        drops = adverts.decisions(root, folder).drops
    except (Unreadable, DecisionsError):
        return set()
    lines = {x.n: x.text for x in advert_lines(advert)}
    return {lines[d.n] for d in drops if d.n in lines}


def uncovered(rows, store, reads):
    """An advert line that asks something no requirement of its posting quotes.

    A graph-native posting's lines and drops are in the graph; a draft one is skipped.

    Args:
        rows: the SELECT's rows, ?focus a posting and ?q each quote of it.
        store: the loaded workspace.
        reads: the Reads whose adverts supply posting.md and decisions.txt.

    Returns:
        A row per uncovered line, with the "line".
    """
    from ..posting.lines import lines_of, native
    from .parsed import Unreadable
    from .rules import node, v

    quotes = defaultdict(list)
    for r in rows:
        # Stripped as the line is below: a quote ending in its line's full stop is not
        # in the line once the line has lost it.
        quotes[v(r, "focus")].append(squash(v(r, "q") or "").casefold().rstrip(".;, "))
    out, graph = [], native(store)
    for post, said in quotes.items():
        if post in graph:
            if graph[post] == "draft":
                continue
            lines, drops = lines_of(store, post)
            asked = asked_of(lines)
            dropped = {x.text for x in lines if x.n in drops}
        else:
            file = store.file_of(post)
            if not file:
                continue
            folder = folder_of(file)
            if not frozen_folder(store, folder):
                continue                    # unsent and made from files: not judged (6.0)
            try:
                advert = reads.adverts.advert(store.root, folder)
            except Unreadable:
                continue                    # quote-verbatim says why it could not be read
            asked = asked_lines(advert)
            dropped = dropped_lines(reads.adverts, store.root, folder, advert)
        said = [q for q in said if q]
        for line in asked:
            if line in dropped:
                continue                    # dropped with a reason, which the assessment shows
            low = line.casefold().rstrip(".;, ")
            if not any(q in low or low in q for q in said):
                out.append({"focus": node(post), "line": line})
    return out
