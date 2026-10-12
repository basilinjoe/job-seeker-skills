"""A person's "no" - `j:Absence` - and how long it stands.

Ruling 8 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md: "never used
Kafka" is a claim in the career, so the next posting asking for Kafka is answered from it
instead of asking again (Ruling 9, domain/assessment/derive.py). A no is judgement, and a
stale one hides a skill learnt since; so it counts only once the person confirmed it, and it
lapses LAPSE_DAYS after it was said. The lapse is computed, never stored: changing the
constant changes every absence at once, and no triple goes stale.

Pure: the day it is measured against is passed in, never read.
"""
import datetime
from dataclasses import dataclass

# A year: long enough that a person is not asked the same thing every posting, short enough
# that a skill picked up since is asked about again. The plan's figure (Ruling 8).
LAPSE_DAYS = 365


@dataclass(frozen=True)
class Absence:
    """One k:abs_ entry, as the match reads it."""

    iri: str
    concept: str            # the concept's iri
    said: datetime.date
    answer: str             # the person's words
    provenance: str         # confirmed, inferred, needs-verification or disputed
    retired: bool = False


def day(value):
    """`value` as a date: a date, or its ISO form."""
    return value if isinstance(value, datetime.date) else datetime.date.fromisoformat(value)


def live(said, today):
    """Whether a no said on `said` still stands on `today`: under LAPSE_DAYS old.

    Args:
        said: the day it was said, a date or ISO text.
        today: the day it is measured against, a date or ISO text.

    Returns:
        True until LAPSE_DAYS have passed.
    """
    return (day(today) - day(said)).days < LAPSE_DAYS


def of_triples(triples):
    """The absences a career graph holds.

    Args:
        triples: the kb graph's triples or quads.

    Returns:
        [Absence], by id.
    """
    from .. import ontology as O

    props = {}
    for t in triples:
        if O.class_of(t.subject.value) == "Absence" and t.predicate.value.startswith(O.J):
            props.setdefault(t.subject.value, {})[t.predicate.value[len(O.J):]] = t.object.value
    return [Absence(s, p["concept"], day(p["said"]), p["answer"],
                    p.get("provenance", "").removeprefix(O.J), "retired" in p)
            for s, p in sorted(props.items())
            if {"concept", "said", "answer"} <= set(p)]


def standing(absences, today):
    """{concept iri: Absence} for the absences the match may use: confirmed, not retired,
    and live on `today`. An inferred no is the analyst's reading, not the person's word."""
    return {a.concept: a for a in absences
            if a.provenance == "confirmed" and not a.retired and live(a.said, today)}


def due(absences, today):
    """The confirmed, unretired absences that have lapsed by `today`: what a refresh asks
    the person again, by the day they were said."""
    return sorted((a for a in absences if a.provenance == "confirmed" and not a.retired
                   and not live(a.said, today)), key=lambda a: (a.said, a.iri))
