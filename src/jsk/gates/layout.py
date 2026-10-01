#!/usr/bin/env python3
"""`python -m jsk.gates.layout`: the layout gate's documented entry point.

The command is adapters/cli/gates/layout.py and the gate application/gates/layout.py; this
module keeps the path, the names callers and tests reach through it, and how a record's
region and budget are read (Ruling 4 of the onion design).
"""
import sys

from ..domain.gates.layout_rules import SECTION_TITLES as SECTION_TITLES
from ..domain.gates.layout_rules import PDF_FAMILY as PDF_FAMILY
from ..domain.gates.layout_rules import SYMBOL_FACES as SYMBOL_FACES
from ..domain.gates.layout_rules import PAPERS as PAPERS
from ..domain.gates.layout_rules import PAPER_SLACK as PAPER_SLACK
from ..domain.gates.layout_rules import DATE_SLACK as DATE_SLACK
from ..domain.gates.layout_rules import MONTH as MONTH
from ..domain.gates.layout_rules import DATE_LINE as DATE_LINE
from ..domain.gates.layout_rules import SUBSET as SUBSET
from ..domain.gates.layout_rules import family as family
from ..domain.gates.layout_rules import declared_pairs as declared_pairs
from ..domain.gates.layout_rules import paper_name as paper_name
from ..domain.gates.layout_rules import expected_paper as expected_paper
from ..domain.gates.layout_rules import is_tofu as is_tofu
from ..domain.gates.layout_rules import check as check


def from_record(record, pdf):
    """(region, page budget, None) from the plan the render built, or (None, None, why)."""
    from .check_ats import variant_of              # noqa: PLC0415
    from ..resume import build                     # noqa: PLC0415 - only with a record
    try:
        plan, _ = build.from_path(record, fmt=variant_of(pdf))
    except Exception as exc:                       # noqa: BLE001 - reported, never fatal
        return None, None, f"{type(exc).__name__}: {exc}"
    return plan.get("region"), plan.get("pages"), None


def main(argv=None):
    """The gate, as an exit code (adapters.cli.gates.layout.main).

    Args:
        argv: the arguments alone; by default sys.argv's.

    Returns:
        The exit code. Prints the verdict.
    """
    from ..adapters.cli.gates.layout import main as layout

    return layout(sys.argv[1:] if argv is None else list(argv))


if __name__ == "__main__":
    from ..cliutil import retired_path

    sys.exit(retired_path("jsk.gates.layout", "jsk resume check RESUME.pdf --only layout"))
