"""What a hand edit of the career raised: a provenance moved up, an entry added as
confirmed, or a claim changed under a confirmation it no longer earns.

A provenance raised by hand renders as confirmed with no answer behind it, and once the
files are imported no text is left to show it was, so `jsk kb load` names each one.
"""
from ..resume.constants import PROVENANCE_RANK


def provenances(quads):
    """{subject iri: its provenance's name} for every entry in `quads` that has one."""
    from .. import ontology as O
    return {q.subject.value: q.object.value[len(O.J):] for q in quads
            if q.predicate.value == O.J + "provenance"}


def claims(quads, s):
    """The (predicate, object) pairs of `s` whose change resets its provenance."""
    from .. import ontology as O
    names = O.resets(O.class_named(s))
    return {(q.predicate.value, q.object.value) for q in quads
            if q.subject.value == s and q.predicate.value[len(O.J):] in names}


def upgrades(before, after):
    """What a hand edit raised, between two versions of the career.

    Args:
        before: the career's quads as the log last recorded them.
        after: the career's quads as edited.

    Returns:
        One line per entry raised, in iri order.
    """
    from .writer import curie

    now, was, out = provenances(after), provenances(before), []
    for s, p in sorted(now.items()):
        if s not in was:
            if p == "confirmed":
                out.append(f"{curie(s)}: added as confirmed")
        elif PROVENANCE_RANK.get(p, 0) > PROVENANCE_RANK.get(was[s], 0):
            out.append(f"{curie(s)}: {was[s]} -> {p}")
        elif p == "confirmed" and claims(before, s) != claims(after, s):
            changed = sorted({curie(pred) for pred, _ in claims(before, s) ^ claims(after, s)})
            out.append(f"{curie(s)}: {', '.join(changed)} changed while confirmed")
    return out
