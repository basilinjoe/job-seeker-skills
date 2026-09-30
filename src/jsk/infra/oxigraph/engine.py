"""The graph engine a loaded record runs on: an in-memory pyoxigraph Store.

It implements ports.engine.GraphEngine. pyoxigraph is imported when an engine is made,
never at module top, so importing this costs a command nothing.
"""

# For the checker alone: importing `typing` costs every command ~3 ms it never uses.
TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any


class OxigraphEngine:
    """An in-memory pyoxigraph Store, behind the narrow surface the record's logic uses."""

    def __init__(self):
        """Open an empty in-memory store."""
        import pyoxigraph as ox

        self._store = ox.Store()

    def select(self, sparql):
        """Rows of a SELECT over the union of every graph.

        Args:
            sparql: the query, prefixes included.

        Returns:
            One {variable: term} per solution, unbound variables left out.
        """
        # A SELECT always answers with solutions; the stubs type every query's answer.
        result: "Any" = self._store.query(sparql, use_default_graph_as_union=True)
        names = [var.value for var in result.variables]
        return [{n: sol[n] for n in names if sol[n] is not None} for sol in result]

    def update(self, sparql):
        """Run a SPARQL update. Changes the store in place."""
        self._store.update(sparql)

    def add(self, quads):
        """Add every quad in `quads`. Changes the store in place."""
        self._store.extend(quads)

    def remove(self, quad):
        """Remove one quad. Changes the store in place."""
        self._store.remove(quad)

    def contains(self, quad):
        """Whether the store holds `quad`."""
        return quad in self._store

    def __len__(self):
        """How many quads the store holds, derived ones included."""
        return len(self._store)
