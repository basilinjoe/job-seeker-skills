"""Turtle and TriG in and out of pyoxigraph: a text parsed, and numbers as the engine keeps
them. pyoxigraph is imported inside each function, so importing this costs nothing."""
from ...domain.ontology import kind_of
from ...domain.record.parsed import NUMERIC, GraphError, Parsed, comments, normalise, sha256, subject_lines


def parse_text(text, file, kind=None):
    """Parse one file's text. Raises GraphError on a syntax error."""
    import pyoxigraph as ox

    kind = kind or kind_of(file)
    text = normalise(text)
    fmt = ox.RdfFormat.TRIG if kind == "changeset" else ox.RdfFormat.TURTLE
    try:
        # A set, as RDF means it: the parser keeps a line copied twice as two quads, which
        # would read as two values and write back as `"A", "A"`.
        quads = list(dict.fromkeys(ox.parse(text.encode("utf-8"), format=fmt)))
    except SyntaxError as e:
        raise GraphError(f"{file}:{e.lineno}:{e.offset}: {e.msg}",
                         "fix the syntax there; the rest of the file was not read",
                         file, e.lineno, e.offset) from None
    return Parsed(file, kind, quads, subject_lines(text), comments(text), sha256(text), text)


def canonical_numbers(quads):
    """(quads with every number as Oxigraph keeps it, [(quad, canonical literal)] for each
    one that changed).

    The store keeps a number by value: `8.40` comes back `8.4`, `007` comes back `7`. Asked
    of Oxigraph itself - a round trip through an in-memory store - so the answer is the
    store's and not a guess at XSD's canonical forms. A lexical form that is not a number
    at all comes back as it went in, and tier 1's datatype rule is what names it."""
    import pyoxigraph as ox

    numbers = [q for q in quads if isinstance(q.object, ox.Literal)
               and q.object.datatype.value in NUMERIC]
    if not numbers:
        return list(quads), []
    probe, g = ox.Store(), ox.NamedNode("tag:jsk,2026:probe")
    subject = ox.NamedNode("tag:jsk,2026:n")
    for i, q in enumerate(numbers):
        probe.add(ox.Quad(subject, ox.NamedNode(f"tag:jsk,2026:{i}"), q.object, g))
    back = {int(q.predicate.value.rsplit(":", 1)[1]): q.object
            for q in probe.quads_for_pattern(None, None, None, g)}
    changed = {numbers[i]: lit for i, lit in back.items() if lit != numbers[i].object}
    out = [ox.Quad(q.subject, q.predicate, changed[q], q.graph_name) if q in changed else q
           for q in quads]
    return out, list(changed.items())
