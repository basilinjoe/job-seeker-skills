"""The questions a tailoring round should ask of a posting's matches."""
from .model import Question
from .nearest import nearest
from .resolve import evidence


def questions(queries, matches):
    """The questions a tailoring round should ask - each one a named gap in the join.

    Args:
        queries: a RecordQueries over a loaded workspace.
        matches: resolve.match's {requirement iri: Match}.

    Returns:
        [Question], by requirement label, then kind.
    """
    out = []
    near = None
    for m in matches.values():
        asked = m.requirement.asked
        if m.state == "ambiguous":
            out.append(Question("ambiguous", asked, m.resolution.concepts))
        elif m.state == "candidate":
            near = near or nearest(queries, post=queries.posting_of(m.requirement.iri))
            out.append(Question("unknown-term", asked, near(asked)))
        elif m.state == "near":
            kind = "implied" if any("implied" in why for why in m.near.values()) else "broader-held"
            out.append(Question(kind, asked, tuple(sorted(m.near))))
        elif m.state == "matched":
            levels = {p: evidence(queries, p, m.concepts) for p in m.carriers}
            if "confirmed" not in levels.values():
                out.append(Question("tag-only", asked, tuple(sorted(levels))))
    return sorted(out, key=lambda q: (q.requirement, q.kind))
