"""The questions features ask of a loaded record, by name rather than as SPARQL (Ruling 3).

A feature's projection is storage knowledge - which graph holds the derived paths, how a
retired entry is marked - so the query text lives with the engine, in
infra/oxigraph/queries.py, and a use case asks for what it needs by method.
"""
from typing import Any, Protocol


class RecordQueries(Protocol):
    """The feature reads over a loaded career."""

    def metric_facts(self) -> tuple[dict[str, str], dict[str, set[str]], dict[str, list[Any]]]:
        """What the untraced-number check compares.

        Returns:
            (each bullet's words, the metrics each cites, each metric's versions as
            (version, {numbers}, closed day or None)). Runs two SELECTs.
        """
        ...

    def requirements(self, post: str) -> list[Any]:
        """A posting's requirements: [domain.matching.model.Requirement] in iri order."""
        ...

    def label_pairs(self) -> list[tuple[str, str]]:
        """(concept, label) for every label and former label, as written."""
        ...

    def concepts(self) -> set[str]:
        """Every concept iri any graph states something about."""
        ...

    def retired_concepts(self) -> set[str]:
        """The concepts a merge or the person retired."""
        ...

    def paths_to(self, concept: str) -> list[tuple[str, str, int, bool]]:
        """(project, held, hops, implied) for every live project holding what counts as
        `concept`."""
        ...

    def broader_held(self, concept: str) -> list[tuple[str, str]]:
        """(project, held) where the project holds only something `concept` counts as."""
        ...

    def evidence_levels(self, project: str, concepts: Any) -> set[str]:
        """The provenances of the project's live, undisputed bullets showing one of
        `concepts` (an iri or several) without an implies edge."""
        ...

    def confirmed_texts(self, project: str, concepts: Any) -> list[str]:
        """The sorted words of the project's live, confirmed bullets showing one of
        `concepts` without an implies edge."""
        ...

    def projects(self) -> dict[str, tuple[int, int, str | None]]:
        """{project: (strength, recency, seniority)} for every live project."""
        ...

    def posting_seniority(self, post: str) -> str | None:
        """The seniority a posting asks for, or None."""
        ...

    def posting_of(self, req: str) -> str | None:
        """The posting a requirement belongs to, or None."""
        ...

    def answered(self, post: str | None = None) -> dict[tuple[str, str], set[str]]:
        """{(asked, concept): postings}: what analysts named on the postings but `post`,
        retired concepts left out."""
        ...

    def live_bullets(self) -> dict[str, tuple[str, int, str]]:
        """{bullet: (project, rank, provenance)} for every live bullet."""
        ...

    def bullet_shows(self) -> dict[str, set[str]]:
        """{bullet: the concepts it shows or counts as, without an implies edge}."""
        ...

    def citing_current(self) -> set[str]:
        """The bullets citing a metric that has a current version."""
        ...
