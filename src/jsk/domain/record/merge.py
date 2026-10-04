"""`jsk kb merge c:a --into c:b`: two concepts that are one, drafted as a changeset.

Every career triple pointing at c:a points at c:b instead - a project's j:uses and
j:domain, an organisation's j:industry, a bullet's j:shows, another concept's edges. c:a's
labels and former labels move to c:b, and so does its id as words ("ai agent design"),
so wording that found c:a finds c:b. Its own edges move with it, unless one would make a
cycle or cross a distinct wall. Nothing is applied: the career_preview tool (jsk mcp) reads it.

A bullet whose j:shows changes is a claim changed, so applying it drops the bullet to
j:inferred and asks about it: those bullets are the re-confirm list, printed with it.

Then c:a goes. A posting is not a changeset's to edit, and one whose requirement
still names c:a through j:concept would dangle - the `dangling` rule is a FAIL, and
edit.referenced refuses the delete for it. So c:a is deleted when nothing outside the career
names it, and retired, with a reason naming c:b, when a posting still does: the posting
then reads `retired-referenced`, a WARN that says to re-point it.
"""
from .. import ontology as O
from .pack import EDGES, Walls, cur, edges, names, node, slug


class Refused(Exception):
    """Why the merge was not drafted: (detail, fix) pairs, all of them."""

    def __init__(self, reasons):
        """Hold every reason.

        Args:
            reasons: (detail, fix) pairs.
        """
        super().__init__(f"{len(reasons)} refusal(s)")
        self.reasons = reasons


def concept_iri(text):
    """c:kafka, kafka or a full iri, as a concept iri."""
    if text.startswith(O.C):
        return text
    return O.C + (text[2:] if text.startswith("c:") else text)


def draft(store, a, b):
    """{"delete": [...], "add": [...], "retire": [...], "entries": [...], "reconfirm":
    [bullet iris], "notes": [...]} for merging concept iri `a` into `b`. Raises Refused."""
    import pyoxigraph as ox

    from .pack import classes
    from .state import KB
    from ..naming import graph_iri

    kinds = classes(store)
    problems = []
    if a == b:
        problems.append((f"{cur(a)} into itself", "name two concepts"))
    for c in dict.fromkeys((a, b)):
        if c not in store.homes:
            problems.append((f"{cur(c)} is not in the record",
                             "check the id: the career_query tool (jsk mcp) lists them"))
    if problems:
        raise Refused(problems)
    if [f for f in store.definitions[a] if f != KB]:
        problems.append((f"{cur(a)} is defined by the shipped vocabulary, so it outlives "
                         "any merge", "merge a concept of your own into it instead, or "
                         "narrow it with j:unlabel / j:unlink"))
    if kinds.get(a) != kinds.get(b):
        problems.append((f"{cur(a)} is {' or '.join(sorted(kinds.get(a, ()))) or 'untyped'}, "
                         f"{cur(b)} is {' or '.join(sorted(kinds.get(b, ()))) or 'untyped'}",
                         "a merge keeps one class: op:set the class of one first, if they "
                         "really are one thing"))
    known = edges(store)
    if (a, "distinct", b) in known or (b, "distinct", a) in known:
        problems.append((f"{cur(a)} and {cur(b)} are declared distinct",
                         "drop the j:distinct first, if they really are one thing"))
    if problems:
        raise Refused(problems)

    kb = {(q.subject, q.predicate, q.object) for q in store.graph(KB)}
    A, B = node(a), node(b)
    delete, add, notes, reconfirm = [], [], [], set()
    walls = Walls({e for e in known if a not in (e[0], e[2])})

    # Pointers at c:a, from anywhere in the career. j:unlink names a shipped edge to drop, and
    # c:a is not shipped, so there is nothing of it to redirect.
    for s, p, o in sorted(kb, key=str):
        if o != A or s == A or p.value == O.J + "unlink":
            continue
        delete.append((s, p, o))
        k = p.value[len(O.J):]
        if s == B:
            continue            # c:b isA c:a would become c:b isA c:b
        if k in EDGES:
            why = walls.trouble(s.value, k, b)
            if why:
                raise Refused([(f"{cur(s.value)} j:{k} {cur(a)} cannot become j:{k} {cur(b)}: "
                                f"{why}", "untangle the two first, then merge")])
            walls.put(s.value, k, b)
        if (s, p, B) not in kb:
            add.append((s, p, B))
        if k == "shows":
            reconfirm.add(s.value)

    # c:a's own names and edges, onto c:b.
    taken = names(store, skip={a})
    own = sorted(((p, o) for s, p, o in kb if s == A), key=str)
    for p, o in own:
        k = p.value[len(O.J):] if p.value.startswith(O.J) else None
        if k in ("label", "former"):
            if B.value not in taken[O.norm(o.value)]:
                add.append((B, p, o))
                taken[O.norm(o.value)].add(b)
        elif k in EDGES and o != B:
            why = walls.trouble(b, k, o.value)
            if why:
                notes.append(f"{cur(a)} j:{k} {cur(o.value)} not moved to {cur(b)}: {why}")
            elif (B, p, o) not in kb:
                walls.put(b, k, o.value)
                add.append((B, p, o))
    words = slug(a).replace("-", " ")
    owners = taken[O.norm(words)] - {b}
    if owners:
        notes.append(f"{words!r} not added as a label of {cur(b)}: it already names "
                     + ", ".join(cur(x) for x in sorted(owners)))
    elif b not in taken[O.norm(words)]:
        add.append((B, node(O.J + "label"), ox.Literal(words)))

    # Deleted, unless a posting still names it: then retired, its names and edges gone.
    rows = store.select(f"""PREFIX j: <{O.J}> SELECT DISTINCT ?s WHERE {{ GRAPH ?g {{ ?s ?p <{a}> }}
        FILTER(?g != j:derived && ?g != <{graph_iri(KB)}>) FILTER(?p NOT IN (j:touched, j:minted)) }}""")
    held = sorted(r["s"].value for r in rows)
    out = {"delete": delete, "add": add, "retire": [], "entries": [], "notes": notes,
           "reconfirm": sorted(reconfirm), "named_by": held}
    retired = any(p.value == O.J + "retired" for s, p, o in kb if s == A)
    if not held:
        out["entries"] = [a]
    else:
        out["delete"] += [(A, p, o) for p, o in own
                          if p.value != O.RDF_TYPE and p.value[len(O.J):] not in ("retired", "reason", "note")]
        if not retired:
            out["retire"] = [(A, node(O.J + "reason"),
                              ox.Literal(f"Merged into {cur(b)}; "
                                         f"{', '.join(cur(h) for h in held)} still names it."))]
    return out


def summary(a, b, out):
    """The merge changeset's op:summary.

    Args:
        a: the concept IRI merged away.
        b: the concept IRI it was merged into.
        out: what draft returned; its "entries" say whether `a` was deleted or retired.

    Returns:
        "Merged c:a into c:b; c:a deleted." or "... retired."
    """
    gone = "deleted" if out["entries"] else "retired"
    return f"Merged {cur(a)} into {cur(b)}; {cur(a)} {gone}."

