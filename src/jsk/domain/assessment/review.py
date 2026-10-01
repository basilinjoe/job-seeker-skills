"""The analyst's review as the review graph holds it: overlay.Overlay to triples and back.

Ruling 4 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: what
gaps.txt held for a file-built application, a graph-native one keeps in
`applications/<stem>/review`, which survives what the gaps graph does not - a
re-derivation, a posting rebuild. Read back it is the same Overlay, so fold.check and
fold.fold run on it unchanged.

Ids are derived, never chosen: `k:rvw_<stem>` for the review, `k:rvr_<stem>_<slug>` for the
row about `k:req_<stem>_<slug>`, `k:rvi_<stem>_<kind>_<i>` for the i-th short, surplus or
ask line. Not `rev_`, which is a log entry's. Nothing here reads a file or the store.
"""
from .overlay import Overlay, Row

# The Overlay lists that become ordered items, by the item's kind (ENUMS["reviewItem"]).
ITEMS = ("short", "surplus", "ask")


def triples(overlay, stem, state=None):
    """The review graph's triples for `overlay`.

    Args:
        overlay: the analyst's overlay.Overlay.
        stem: the posting's stem: the review is of k:post_<stem>.
        state: draft or complete, or None.

    Returns:
        [Triple].
    """
    import pyoxigraph as ox

    from .. import ontology as O

    def j(name):
        return ox.NamedNode(O.J + name)

    def k(local):
        return ox.NamedNode(O.K + local)

    review = k(f"rvw_{stem}")
    out = [ox.Triple(review, j("posting"), k(f"post_{stem}"))]
    if overlay.fit:
        out.append(ox.Triple(review, j("fit"), j(overlay.fit)))
    if overlay.eligibility:
        out.append(ox.Triple(review, j("eligibility"), ox.Literal(overlay.eligibility)))
    if state:
        out.append(ox.Triple(review, j("state"), j(state)))
    for row in overlay.rows:
        s = k(f"rvr_{stem}_{row.slug}")
        out += [ox.Triple(s, j("review"), review),
                ox.Triple(s, j("requirement"), k(f"req_{stem}_{row.slug}")),
                ox.Triple(s, j("verdict"), j(row.verdict))]
        if row.reason:
            out.append(ox.Triple(s, j("shortfall"), ox.Literal(row.reason)))
    for kind in ITEMS:
        for i, text in enumerate(getattr(overlay, kind), 1):
            s = k(f"rvi_{stem}_{kind}_{i}")
            out += [ox.Triple(s, j("review"), review), ox.Triple(s, j("kind"), j(kind)),
                    ox.Triple(s, j("position"),
                              ox.Literal(str(i), datatype=ox.NamedNode(O.XSD + "integer"))),
                    ox.Triple(s, j("text"), ox.Literal(text))]
    return out


def overlay_of(triples):
    """The Overlay a review graph holds.

    A row's `line` is its place in slug order, from 1: the graph keeps no file, and a row is
    named by its requirement, never by where it was written.

    Args:
        triples: the review graph's triples or quads.

    Returns:
        overlay.Overlay: rows by slug; each kind's items by position.
    """
    from .. import ontology as O

    props = {}
    for t in triples:
        if t.predicate.value.startswith(O.J):
            props.setdefault(t.subject.value, {})[t.predicate.value[len(O.J):]] = t.object.value
    out = Overlay()
    stem = next((s[len(O.K) + len("rvw_"):] for s in props if O.class_of(s) == "Review"), "")
    rows, items = [], {kind: [] for kind in ITEMS}
    for s, p in props.items():
        cls = O.class_of(s)
        if cls == "Review":
            out.fit = p["fit"].removeprefix(O.J) if "fit" in p else None
            out.eligibility = p.get("eligibility")
        elif cls == "ReviewRow":
            # The row is named by its requirement, k:req_<stem>_<slug>, as gaps.txt names it.
            slug = p["requirement"].removeprefix(f"{O.K}req_{stem}_")
            rows.append((slug, p["verdict"].removeprefix(O.J), p.get("shortfall", "")))
        elif cls == "ReviewItem":
            items[p["kind"].removeprefix(O.J)].append((int(p["position"]), p["text"]))
    out.rows = [Row(n, slug, verdict, reason)
                for n, (slug, verdict, reason) in enumerate(sorted(rows), 1)]
    for kind in ITEMS:
        setattr(out, kind, [text for _, text in sorted(items[kind])])
    return out
