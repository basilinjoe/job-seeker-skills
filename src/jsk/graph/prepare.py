"""`jsk tailor prepare`'s old module path: where its ports are bound until P6.

The command is adapters/cli/tailor.py and the digest application/tailor/prepare.py; this
module keeps the path, the names tests reach through it - CAP among them, the very dict the
digest caps its sections by - and the named reads the digest shows (Reads), bound to
graph.named (Ruling 4 of the onion design).
"""
import sys

from ..application.tailor.prepare import CAP as CAP
from ..application.tailor.prepare import PROJECTS as PROJECTS
from ..application.tailor.prepare import capped as capped


class Reads:
    """The named reads the digest shows, and their table, from graph.named."""

    def evidence_for(self, store, *terms):
        """(columns, rows): what the record holds for each term (graph.named.evidence_for)."""
        from .named import evidence_for

        return evidence_for(store, *terms)

    def person(self, store):
        """(columns, rows) of the person's facts (graph.named.person)."""
        from .named import person

        return person(store)

    def unconfirmed(self, store):
        """(columns, rows) of what the career holds unconfirmed (graph.named.unconfirmed)."""
        from .named import unconfirmed

        return unconfirmed(store)

    def table(self, columns, rows):
        """The rows as a markdown table (graph.named.table)."""
        from .named import table

        return table(columns, rows)


def main(argv=None):
    """`jsk tailor` (adapters.cli.tailor.main), over sys.argv when no argv is given."""
    from ..adapters.cli.tailor import main as tailor

    return tailor(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.graph.prepare", "jsk tailor prepare"))
