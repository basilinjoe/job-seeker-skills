"""The tailoring commands' ports, bound: what `jsk tailor prepare` and `jsk tailor match`
hand their use cases.

Each binding is built inside the call that needs it (Ruling 6 of the onion design): nothing
here reads the record or the disk at import.
"""


class Reads:
    """The named reads the digest shows, and their table (application/tailor/prepare.py's
    `reads`): application.record.queries over the engine's feature reads."""

    def evidence_for(self, store, *terms):
        """What the record holds for each term (application.record.queries.evidence_for).

        Args:
            store: a loaded workspace.
            *terms: the terms.

        Returns:
            (columns, rows).
        """
        from ....application.record.queries import evidence_for
        from ....infra.oxigraph.queries import OxigraphQueries

        return evidence_for(store, *terms, queries=OxigraphQueries(store))

    def person(self, store):
        """The person's facts (application.record.queries.person).

        Args:
            store: a loaded workspace.

        Returns:
            (columns, rows).
        """
        from ....application.record.queries import person

        return person(store)

    def unconfirmed(self, store):
        """What the career holds unconfirmed (application.record.queries.unconfirmed).

        Args:
            store: a loaded workspace.

        Returns:
            (columns, rows).
        """
        from ....application.record.queries import unconfirmed

        return unconfirmed(store)

    def table(self, columns, rows):
        """The rows as a markdown table (adapters.cli.presenters.table).

        Args:
            columns: the column names.
            rows: the rows, as dicts.

        Returns:
            The table's text.
        """
        from ..presenters import table

        return table(columns, rows)
