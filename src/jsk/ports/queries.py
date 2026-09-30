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
