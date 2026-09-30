"""The graph engine a loaded record runs on: queries, updates and quads in and out."""
from typing import Any, Iterable, Protocol


class GraphEngine(Protocol):
    """An in-memory RDF store over which the record's rules and queries run.

    Rule text stays SPARQL in the domain (Ruling 3); this is the narrow surface it runs
    through, so the domain never holds a pyoxigraph Store.
    """

    def select(self, sparql: str) -> list[dict[str, Any]]:
        """Run a SELECT over the union of every graph.

        Args:
            sparql: the query, prefixes included.

        Returns:
            One {variable: term} per solution, unbound variables left out.
        """
        ...

    def update(self, sparql: str) -> None:
        """Run a SPARQL update. Changes the store in place."""
        ...

    def add(self, quads: Iterable[Any]) -> None:
        """Add `quads`. Changes the store in place."""
        ...

    def remove(self, quad: Any) -> None:
        """Remove one quad. Changes the store in place."""
        ...

    def contains(self, quad: Any) -> bool:
        """Whether the store holds `quad`."""
        ...
