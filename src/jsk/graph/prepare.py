"""`jsk tailor prepare`'s old module path: where its ports are bound until P6.

The command is adapters/cli/tailor.py and the digest application/tailor/prepare.py; this
module keeps the path and the names tests reach through it - CAP among them, the very dict
the digest caps its sections by (Ruling 4 of the onion design). The named reads the digest
shows are adapters/cli/compose/tailor.py's Reads.
"""
import sys

from ..application.tailor.prepare import CAP as CAP
from ..application.tailor.prepare import PROJECTS as PROJECTS
from ..application.tailor.prepare import capped as capped


def main(argv=None):
    """`jsk tailor` (adapters.cli.tailor.main), over sys.argv when no argv is given."""
    from ..adapters.cli.tailor import main as tailor

    return tailor(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.graph.prepare", "jsk tailor prepare"))
