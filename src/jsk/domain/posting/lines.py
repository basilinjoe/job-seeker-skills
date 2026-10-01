"""An advert's lines as the posting graph holds them: advert.AdvertLine to triples and back.

Ruling 1 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: a
graph-native posting keeps no posting.md, so the lines a requirement quotes are stored -
`k:line_<stem>_<n>`, each with its number, section, text and flags, and the analyst's reason
when it was dropped. The fields are advert_lines' own; nothing here numbers an advert again.
Concepts are not stored on a line: they follow the vocabulary, which changes, so a reader
finds them when it reads the lines.

It reads no file and opens no store: `lines_of` asks a loaded one it is given.
"""
from .advert import AdvertLine


def line_id(stem, n):
    """The local id of a posting's line `n`: `line_<stem>_<n>` - derived, never chosen, so a
    rewrite of the posting names each line as it did."""
    return f"line_{stem}_{n}"


def triples(post, stem, lines, drops=None):
    """The triples of a posting's lines.

    Args:
        post: the posting's iri.
        stem: its stem, which each line's id carries.
        lines: [advert.AdvertLine].
        drops: {n: the analyst's reason} for each line left out, or None.

    Returns:
        [Triple]. A false flag is left out, as an unset one reads.
    """
    import pyoxigraph as ox

    from .. import ontology as O

    def j(name):
        return ox.NamedNode(O.J + name)

    def typed(value, kind):
        return ox.Literal(value, datatype=ox.NamedNode(O.XSD + kind))

    drops = drops or {}
    out, p = [], ox.NamedNode(post)
    for line in lines:
        s = ox.NamedNode(O.K + line_id(stem, line.n))
        out += [ox.Triple(s, j("posting"), p), ox.Triple(s, j("n"), typed(str(line.n), "integer")),
                ox.Triple(s, j("section"), j(line.section)),
                ox.Triple(s, j("text"), ox.Literal(line.text))]
        if line.optional:
            out.append(ox.Triple(s, j("optional"), typed("true", "boolean")))
        if line.elig:
            out.append(ox.Triple(s, j("eligibility"), typed("true", "boolean")))
        if drops.get(line.n):
            out.append(ox.Triple(s, j("dropped"), ox.Literal(drops[line.n])))
    return out


def from_triples(triples):
    """A posting graph's lines, read back.

    Args:
        triples: the graph's triples or quads; whatever is not a line is ignored.

    Returns:
        ([advert.AdvertLine] by number, {n: the reason} for each dropped line).
    """
    from .. import ontology as O

    props = {}
    for t in triples:
        s = t.subject.value
        if O.class_of(s) == "AdvertLine" and t.predicate.value.startswith(O.J):
            props.setdefault(s, {})[t.predicate.value[len(O.J):]] = t.object.value
    return built(props.values())


def built(rows):
    """([AdvertLine] by number, {n: reason}) from one dict of local values per line."""
    from .. import ontology as O

    lines, drops = [], {}
    for r in rows:
        n = int(r["n"])
        lines.append(AdvertLine(n, r["section"].removeprefix(O.J), r["text"],
                                r.get("optional") == "true", r.get("eligibility") == "true"))
        if r.get("dropped"):
            drops[n] = r["dropped"]
    return sorted(lines, key=lambda x: x.n), drops


def lines_of(store, post):
    """The stored lines of the posting `post`, from a loaded workspace.

    Args:
        store: a loaded workspace (domain.record.store.Store).
        post: the posting's iri.

    Returns:
        ([advert.AdvertLine] by number, {n: reason}); ([], {}) for a posting built from
        files, which keeps its advert in posting.md.
    """
    from .. import ontology as O

    rows = store.select(O.SPARQL_PREFIX + f"""
        SELECT ?l ?n ?section ?text ?optional ?eligibility ?dropped WHERE {{
          ?l a j:AdvertLine ; j:posting <{post}> ; j:n ?n ; j:section ?section ; j:text ?text .
          OPTIONAL {{ ?l j:optional ?optional }} OPTIONAL {{ ?l j:eligibility ?eligibility }}
          OPTIONAL {{ ?l j:dropped ?dropped }} }}""")
    return built([{k: r[k].value for k in r if k != "l"} for r in rows])


def native(store):
    """{posting iri: its j:state's local name, or None} for every posting whose lines the
    graph holds - Ruling 11's graph-native postings. One built from files is not in it."""
    from .. import ontology as O

    rows = store.select(O.SPARQL_PREFIX + """
        SELECT DISTINCT ?p ?state WHERE { ?l a j:AdvertLine ; j:posting ?p .
          OPTIONAL { ?p j:state ?state } }""")
    return {r["p"].value: r["state"].value.removeprefix(O.J) if "state" in r else None
            for r in rows}
