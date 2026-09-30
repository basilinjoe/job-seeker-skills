"""The match's values: a requirement, what it resolves to, a match, a ranking row, a question."""
from dataclasses import dataclass, field

from .. import ontology as O


@dataclass(frozen=True)
class Requirement:
    """One requirement of a posting, as its graph states it."""
    iri: str
    asked: str
    quote: str
    necessity: str
    concepts: tuple = ()         # the analyst's answer: the concepts meant, any one satisfies


@dataclass(frozen=True)
class Resolution:
    """The concepts a requirement was taken to ask for, and how they were found."""
    state: str                   # resolved | ambiguous | candidate
    concepts: tuple              # iris, sorted
    via: str | None = None       # concept | id | label


@dataclass
class Match:
    """A requirement against the career: its state, the projects carrying it, the near ones."""
    requirement: Requirement
    resolution: Resolution
    state: str | None = None     # matched | near | missing | ambiguous | candidate | implicit
    carriers: dict = field(default_factory=dict)   # project -> (held, hops, implied)
    near: dict = field(default_factory=dict)       # project -> why

    @property
    def concept(self):
        """The first concept meant, for display; `concepts` is what matching reads."""
        return self.resolution.concepts[0] if self.resolution.state == "resolved" else None

    @property
    def concepts(self):
        """Every concept meant - any one satisfies - when resolved; () otherwise."""
        return self.resolution.concepts if self.resolution.state == "resolved" else ()


@dataclass(frozen=True)
class Row:
    """One project's place in the ranking: its score and the requirements it carries."""
    project: str
    score: float
    required: tuple
    preferred: tuple


@dataclass(frozen=True)
class Question:
    """A named gap in the join, for a tailoring round to ask."""
    kind: str                    # ambiguous | unknown-term | implied | broader-held | tag-only
    requirement: str             # the label as the posting wrote it
    detail: tuple


def local(iri):
    """The name after the j: namespace.

    Args:
        iri: any iri.

    Returns:
        `iri` without the j: namespace when it is in it, else `iri` unchanged.
    """
    return iri[len(O.J):] if iri.startswith(O.J) else iri
